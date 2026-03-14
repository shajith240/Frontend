"""SQL-style trigger simulations for the patient-demographics module.

Each function in this module mirrors a database trigger — it fires automatically
inside the relevant CRUD operation without the caller needing to invoke it.
The caller never imports or calls these functions directly; crud.py wires them in.

Triggers implemented:
  1. audit_log_trigger          — logs every insert/update to audit_logs
  2. age_calculator_trigger     — computes patient age from DateOfBirth on insert
  3. visit_frequency_alert_trigger — raises alert if patient has >3 visits in 30 days
  4. abnormal_vitals_trigger    — raises alerts when recorded vitals are outside
                                   accepted clinical ranges
  5. appointment_conflict_trigger — blocks double-booking a physician at the same slot
"""

from datetime import date, datetime, timedelta
from typing import Optional

from pymongo.errors import PyMongoError

from backend.database import DatabaseConnection
from backend.models import (
    Alert,
    AlertSeverity,
    AlertType,
    AuditAction,
    AuditLog,
    VitalSigns,
)


# ---------------------------------------------------------------------------
# Normal clinical ranges used by abnormal_vitals_trigger
# ---------------------------------------------------------------------------

_VITALS_RANGES: dict[str, dict] = {
    "blood_pressure_systolic": {
        "low": 90,
        "high": 140,
        "unit": "mmHg",
        "severity_high": AlertSeverity.HIGH,
        "severity_low": AlertSeverity.HIGH,
    },
    "blood_pressure_diastolic": {
        "low": 60,
        "high": 90,
        "unit": "mmHg",
        "severity_high": AlertSeverity.HIGH,
        "severity_low": AlertSeverity.HIGH,
    },
    "heart_rate": {
        "low": 60,
        "high": 100,
        "unit": "bpm",
        "severity_high": AlertSeverity.MEDIUM,
        "severity_low": AlertSeverity.MEDIUM,
    },
    "temperature_celsius": {
        "low": 36.1,
        "high": 37.9,
        "unit": "°C",
        "severity_high": AlertSeverity.HIGH,
        "severity_low": AlertSeverity.MEDIUM,
    },
    "respiratory_rate": {
        "low": 12,
        "high": 20,
        "unit": "breaths/min",
        "severity_high": AlertSeverity.HIGH,
        "severity_low": AlertSeverity.MEDIUM,
    },
    "oxygen_saturation": {
        "low": 95.0,
        "high": 100.0,
        "unit": "%",
        "severity_high": AlertSeverity.LOW,       # hyperoxia is rarely dangerous
        "severity_low": AlertSeverity.CRITICAL,   # hypoxia is immediately dangerous
    },
}

# Slot window (minutes) used by appointment_conflict_trigger
_APPOINTMENT_SLOT_MINUTES = 30


# ---------------------------------------------------------------------------
# Helper — unique ID generators
# ---------------------------------------------------------------------------

def _make_id(prefix: str) -> str:
    """Generate a time-based unique ID with the given prefix.

    Format: PREFIX-YYYY-NNNNNN where NNNNNN is microsecond component.

    Args:
        prefix: Two- or three-letter prefix (e.g. 'LOG', 'ALT').

    Returns:
        A string ID that is unique within a single process run.
    """
    now = datetime.utcnow()
    return f"{prefix}-{now.strftime('%Y')}-{now.strftime('%f')}"


def _serialize_doc(doc: dict) -> dict:
    """Strip None values and coerce date → datetime for MongoDB insertion.

    Args:
        doc: Dictionary produced by a Pydantic model_dump() call.

    Returns:
        Cleaned dict safe for PyMongo insert_one.
    """
    result: dict = {}
    for key, value in doc.items():
        if value is None:
            continue
        if hasattr(value, "year") and not isinstance(value, datetime):
            value = datetime(value.year, value.month, value.day)
        elif isinstance(value, dict):
            value = _serialize_doc(value)
        elif isinstance(value, list):
            value = [
                _serialize_doc(item) if isinstance(item, dict) else item
                for item in value
            ]
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Trigger 1 — audit_log_trigger
# ---------------------------------------------------------------------------

def audit_log_trigger(
    db: DatabaseConnection,
    *,
    patient_id: str,
    action: AuditAction,
    collection_name: str,
    document_id: str,
    performed_by: str,
    performed_by_role: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """TRIGGER: auto-log every insert/update/delete to the audit_logs collection.

    Simulates an AFTER INSERT / AFTER UPDATE SQL trigger that writes an audit
    row whenever patient-related data is modified. Failures are swallowed and
    printed — audit writes must never abort the primary transaction.

    Fired by: create_patient, get_patient_by_id, update_patient, create_visit,
              create_appointment, create_referral.

    Args:
        db: Active DatabaseConnection.
        patient_id: PAT-YYYY-NNN identifier of the affected patient.
        action: The AuditAction (CREATE, READ, UPDATE, DELETE).
        collection_name: Collection that was written to.
        document_id: Primary ID of the affected document.
        performed_by: User ID or system name performing the action.
        performed_by_role: Role of the actor (e.g. 'doctor', 'receptionist').
        before: Document state before the operation (UPDATE only).
        after: Document state after the operation (UPDATE only).
        ip_address: Optional client IP address.
    """
    try:
        changes: Optional[dict] = None
        if before and after:
            changes = {
                field: {"before": before.get(field), "after": after.get(field)}
                for field in after
                if field not in {"updated_at", "_id"} and after.get(field) != before.get(field)
            }

        log = AuditLog(
            log_id=_make_id("LOG"),
            patient_id=patient_id,
            action=action,
            collection_name=collection_name,
            document_id=document_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
            changes=changes or None,
            ip_address=ip_address,
        )
        db.get_collection("audit_logs").insert_one(_serialize_doc(log.model_dump()))
    except Exception as exc:
        print(f"[audit_log_trigger] Warning — could not write audit log: {exc}")


# ---------------------------------------------------------------------------
# Trigger 2 — age_calculator_trigger
# ---------------------------------------------------------------------------

def age_calculator_trigger(date_of_birth: date) -> int:
    """TRIGGER: compute patient age in whole years from DateOfBirth.

    Simulates a BEFORE INSERT computed-column trigger that populates
    Patient.age automatically so the frontend can display it without
    recalculating on every read.

    Fired by: create_patient (before insertion, return value stamped into doc).

    Args:
        date_of_birth: The patient's date of birth.

    Returns:
        Age in complete years as of today.

    Raises:
        ValueError: If date_of_birth is in the future.
    """
    today = date.today()
    if date_of_birth > today:
        raise ValueError("date_of_birth cannot be in the future")

    age = today.year - date_of_birth.year
    # Subtract 1 if birthday hasn't occurred yet this calendar year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


# ---------------------------------------------------------------------------
# Trigger 3 — visit_frequency_alert_trigger
# ---------------------------------------------------------------------------

def visit_frequency_alert_trigger(
    db: DatabaseConnection,
    patient_id: str,
    visit_id: str,
    *,
    threshold: int = 3,
    window_days: int = 30,
) -> None:
    """TRIGGER: raise an alert when a patient visits more than threshold times
    within window_days.

    Simulates an AFTER INSERT trigger on the visits collection that counts
    recent visits and writes a high-severity alert to the alerts collection
    when the threshold is exceeded. This feeds the Master DB global alerts view.

    Fired by: create_visit (after successful insertion).

    Args:
        db: Active DatabaseConnection.
        patient_id: PAT-YYYY-NNN identifier of the patient.
        visit_id: The visit_id that was just inserted (for alert linkage).
        threshold: Number of visits within the window that triggers the alert.
        window_days: Rolling day window to count visits within.
    """
    try:
        since = datetime.utcnow() - timedelta(days=window_days)
        count = db.get_collection("visits").count_documents(
            {
                "patient_id": patient_id,
                "visit_date": {"$gte": since},
            }
        )

        if count > threshold:
            alert = Alert(
                alert_id=_make_id("ALT"),
                patient_id=patient_id,
                alert_type=AlertType.VISIT_FREQUENCY,
                severity=AlertSeverity.HIGH,
                title="High Visit Frequency Detected",
                message=(
                    f"Patient {patient_id} has had {count} visits in the last "
                    f"{window_days} days (threshold: {threshold}). "
                    "Clinical review recommended."
                ),
                source="visit_frequency_alert_trigger",
                related_visit_id=visit_id,
            )
            db.get_collection("alerts").insert_one(_serialize_doc(alert.model_dump()))
            print(
                f"[visit_frequency_alert_trigger] Alert raised for {patient_id}: "
                f"{count} visits in {window_days} days."
            )
    except PyMongoError as exc:
        print(f"[visit_frequency_alert_trigger] Warning — DB error: {exc}")
    except Exception as exc:
        print(f"[visit_frequency_alert_trigger] Warning — unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Trigger 4 — abnormal_vitals_trigger
# ---------------------------------------------------------------------------

def abnormal_vitals_trigger(
    db: DatabaseConnection,
    patient_id: str,
    visit_id: str,
    vital_signs: VitalSigns,
) -> None:
    """TRIGGER: create an alert for each vital sign outside the normal clinical range.

    Simulates an AFTER INSERT trigger on visits that inspects the embedded
    VitalSigns sub-document and writes one Alert per abnormal reading.

    Normal ranges applied:
      - Systolic BP   :  90–140 mmHg
      - Diastolic BP  :  60–90  mmHg
      - Heart rate    :  60–100 bpm
      - Temperature   :  36.1–37.9 °C
      - Resp. rate    :  12–20  breaths/min
      - SpO₂          :  ≥95 %  (no upper alert — hyperoxia handled clinically)

    Fired by: create_visit (after successful insertion, only when vital_signs present).

    Args:
        db: Active DatabaseConnection.
        patient_id: PAT-YYYY-NNN identifier of the patient.
        visit_id: The visit_id that was just inserted.
        vital_signs: The VitalSigns object from the Visit document.
    """
    vitals_dict = vital_signs.model_dump()

    for field, config in _VITALS_RANGES.items():
        value = vitals_dict.get(field)
        if value is None:
            continue

        direction: Optional[str] = None
        if value < config["low"]:
            direction = "low"
            severity = config["severity_low"]
            description = f"LOW ({value} {config['unit']}, normal ≥ {config['low']})"
        elif value > config["high"]:
            direction = "high"
            severity = config["severity_high"]
            description = f"HIGH ({value} {config['unit']}, normal ≤ {config['high']})"

        if direction is None:
            continue

        try:
            label = field.replace("_", " ").title()
            alert = Alert(
                alert_id=_make_id("ALT"),
                patient_id=patient_id,
                alert_type=AlertType.ABNORMAL_VITALS,
                severity=severity,
                title=f"Abnormal {label}",
                message=(
                    f"Patient {patient_id} — {label} is {description} "
                    f"during visit {visit_id}. Immediate clinical review advised."
                ),
                source="abnormal_vitals_trigger",
                related_visit_id=visit_id,
            )
            db.get_collection("alerts").insert_one(_serialize_doc(alert.model_dump()))
            print(
                f"[abnormal_vitals_trigger] {severity.upper()} alert: "
                f"{label} {description} for patient {patient_id}."
            )
        except PyMongoError as exc:
            print(f"[abnormal_vitals_trigger] Warning — DB error for {field}: {exc}")
        except Exception as exc:
            print(f"[abnormal_vitals_trigger] Warning — unexpected error for {field}: {exc}")


# ---------------------------------------------------------------------------
# Trigger 5 — appointment_conflict_trigger
# ---------------------------------------------------------------------------

def appointment_conflict_trigger(
    db: DatabaseConnection,
    physician_id: str,
    appointment_date_and_time: datetime,
    *,
    exclude_appointment_id: Optional[str] = None,
) -> None:
    """TRIGGER: block double-booking a physician within the same time slot.

    Simulates a BEFORE INSERT trigger on the appointments collection that
    queries existing non-cancelled, non-no-show appointments for the physician
    within ±_APPOINTMENT_SLOT_MINUTES of the requested time. Raises ValueError
    to abort the insert if a conflict is found — exactly like a SQL trigger
    raising an application error.

    Fired by: create_appointment (before insertion).

    Args:
        db: Active DatabaseConnection.
        physician_id: The physician to check for conflicts.
        appointment_date_and_time: The proposed appointment datetime.
        exclude_appointment_id: Optional appointment_id to exclude from the
            check (used when rescheduling an existing appointment).

    Raises:
        ValueError: If the physician already has an appointment within the slot window.
        RuntimeError: On unexpected database error.
    """
    slot_delta = timedelta(minutes=_APPOINTMENT_SLOT_MINUTES)
    window_start = appointment_date_and_time - slot_delta
    window_end = appointment_date_and_time + slot_delta

    # Statuses that occupy the physician's schedule
    blocking_statuses = ["scheduled", "confirmed"]

    try:
        query: dict = {
            "physician_id": physician_id,
            "appointment_date_and_time": {
                "$gte": window_start,
                "$lte": window_end,
            },
            "status": {"$in": blocking_statuses},
        }
        if exclude_appointment_id:
            query["appointment_id"] = {"$ne": exclude_appointment_id}

        conflict = db.get_collection("appointments").find_one(query, {"appointment_id": 1})
        if conflict:
            conflict_id = conflict.get("appointment_id", "unknown")
            raise ValueError(
                f"Scheduling conflict: physician '{physician_id}' already has appointment "
                f"'{conflict_id}' within {_APPOINTMENT_SLOT_MINUTES} minutes of "
                f"{appointment_date_and_time.isoformat()}. "
                "Choose a different time slot."
            )
    except ValueError:
        raise  # re-raise the conflict error unchanged
    except PyMongoError as exc:
        raise RuntimeError(
            f"[appointment_conflict_trigger] DB error during conflict check: {exc}"
        ) from exc
