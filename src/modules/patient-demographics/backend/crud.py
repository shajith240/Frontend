"""PyMongo CRUD operations for all 6 patient-demographics collections.

Each function receives a connected DatabaseConnection instance so the caller
controls the connection lifecycle (FastAPI lifespan, Streamlit session, tests).
All write operations also append a record to audit_logs for Master DB traceability
as required by the project architecture (Module DB → Category Views → Master DB).
"""

from datetime import datetime
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.database import DatabaseConnection
from backend.models import (
    Alert,
    Appointment,
    AppointmentStatus,
    AuditAction,
    AuditLog,
    Patient,
    Referral,
    ReferralStatus,
    Visit,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    """Convert a Pydantic model dict into a MongoDB-safe document.

    Replaces date objects with datetime so PyMongo can store them, and removes
    None values to keep documents compact.

    Args:
        doc: A dict produced by ``model.model_dump()``.

    Returns:
        A cleaned dict ready for insertion into MongoDB.
    """
    result: dict = {}
    for key, value in doc.items():
        if value is None:
            continue
        # date → datetime (MongoDB has no native date-only type)
        if hasattr(value, "year") and not isinstance(value, datetime):
            value = datetime(value.year, value.month, value.day)
        elif isinstance(value, dict):
            value = _serialize(value)
        elif isinstance(value, list):
            value = [
                _serialize(item) if isinstance(item, dict) else item
                for item in value
            ]
        result[key] = value
    return result


def _write_audit(
    db: DatabaseConnection,
    *,
    patient_id: str,
    action: AuditAction,
    collection_name: str,
    document_id: str,
    performed_by: str,
    performed_by_role: str,
    changes: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Append a record to audit_logs.

    Failures are logged to stdout but never raised — audit writes must not
    break the primary operation.

    Args:
        db: Active DatabaseConnection.
        patient_id: The patient this action relates to.
        action: CREATE, READ, UPDATE, or DELETE.
        collection_name: MongoDB collection that was touched.
        document_id: ID of the document affected.
        performed_by: User or system identifier.
        performed_by_role: Role of the actor (e.g. 'doctor', 'system').
        changes: Optional before/after diff dict.
        ip_address: Optional client IP.
    """
    try:
        log_id = (
            f"LOG-{datetime.utcnow().strftime('%Y')}-"
            f"{datetime.utcnow().strftime('%f')[:6]}"
        )
        log = AuditLog(
            log_id=log_id,
            patient_id=patient_id,
            action=action,
            collection_name=collection_name,
            document_id=document_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
            changes=changes,
            ip_address=ip_address,
        )
        db.get_collection("audit_logs").insert_one(_serialize(log.model_dump()))
    except Exception as exc:
        print(f"[audit] Warning: could not write audit log: {exc}")


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

def create_patient(
    db: DatabaseConnection,
    patient: Patient,
    *,
    performed_by: str = "system",
    performed_by_role: str = "system",
) -> str:
    """Insert a new patient document into the 'patients' collection.

    Args:
        db: Active DatabaseConnection.
        patient: Validated Patient Pydantic model.
        performed_by: ID or name of the actor creating the record.
        performed_by_role: Role of the actor.

    Returns:
        The patient_id of the newly created patient.

    Raises:
        ValueError: If a patient with the same patient_id already exists.
        RuntimeError: On unexpected database error.
    """
    try:
        doc = _serialize(patient.model_dump())
        db.get_collection("patients").insert_one(doc)
        _write_audit(
            db,
            patient_id=patient.patient_id,
            action=AuditAction.CREATE,
            collection_name="patients",
            document_id=patient.patient_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
        )
        return patient.patient_id
    except DuplicateKeyError:
        raise ValueError(
            f"Patient with patient_id='{patient.patient_id}' already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while creating patient: {exc}") from exc


def get_patient_by_id(
    db: DatabaseConnection,
    patient_id: str,
    *,
    performed_by: str = "system",
    performed_by_role: str = "system",
) -> Optional[dict]:
    """Fetch a single patient document by patient_id.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier to look up.
        performed_by: Actor performing the read (for audit).
        performed_by_role: Role of the actor.

    Returns:
        The patient document as a dict (without the MongoDB ``_id`` field),
        or None if no matching patient is found.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        doc = db.get_collection("patients").find_one(
            {"patient_id": patient_id}, {"_id": 0}
        )
        if doc:
            _write_audit(
                db,
                patient_id=patient_id,
                action=AuditAction.READ,
                collection_name="patients",
                document_id=patient_id,
                performed_by=performed_by,
                performed_by_role=performed_by_role,
            )
        return doc
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while fetching patient: {exc}") from exc


def search_patients(
    db: DatabaseConnection,
    *,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = True,
    limit: int = 50,
    skip: int = 0,
) -> list[dict]:
    """Search patients by name substring, phone, or active status.

    All provided filters are combined with AND logic. Partial, case-insensitive
    name matching is supported via a regex filter.

    Args:
        db: Active DatabaseConnection.
        name: Optional substring to match against first_name + last_name.
        phone: Optional exact phone number filter.
        department: Unused at patient level — included for future FK joins.
        is_active: Filter by active status (default True). Pass None to skip.
        limit: Maximum number of results to return (default 50, max 200).
        skip: Number of documents to skip for pagination.

    Returns:
        List of matching patient dicts (without ``_id``).

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        query: dict[str, Any] = {}
        if name:
            query["$or"] = [
                {"first_name": {"$regex": name, "$options": "i"}},
                {"last_name": {"$regex": name, "$options": "i"}},
            ]
        if phone:
            query["phone"] = phone
        if is_active is not None:
            query["is_active"] = is_active

        cursor = (
            db.get_collection("patients")
            .find(query, {"_id": 0})
            .sort("last_name", ASCENDING)
            .skip(skip)
            .limit(min(limit, 200))
        )
        return list(cursor)
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while searching patients: {exc}") from exc


def update_patient(
    db: DatabaseConnection,
    patient_id: str,
    updates: dict,
    *,
    performed_by: str = "system",
    performed_by_role: str = "system",
) -> bool:
    """Apply a partial update to an existing patient document.

    Automatically stamps ``updated_at`` to the current UTC time.
    Raises ValueError if the caller tries to overwrite ``patient_id`` or
    ``created_at`` (immutable fields).

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier of the patient to update.
        updates: Dict of fields to update (must not include patient_id/created_at).
        performed_by: Actor performing the update (for audit).
        performed_by_role: Role of the actor.

    Returns:
        True if a document was modified, False if patient_id was not found.

    Raises:
        ValueError: If caller attempts to modify immutable fields.
        RuntimeError: On unexpected database error.
    """
    immutable = {"patient_id", "created_at"}
    bad_keys = immutable & set(updates.keys())
    if bad_keys:
        raise ValueError(f"Cannot update immutable field(s): {bad_keys}")

    try:
        # Capture before-state for audit diff
        before = db.get_collection("patients").find_one(
            {"patient_id": patient_id}, {"_id": 0}
        )
        if not before:
            return False

        updates["updated_at"] = datetime.utcnow()
        result = db.get_collection("patients").update_one(
            {"patient_id": patient_id}, {"$set": updates}
        )

        if result.modified_count > 0:
            changes = {
                field: {"before": before.get(field), "after": updates[field]}
                for field in updates
                if field != "updated_at"
            }
            _write_audit(
                db,
                patient_id=patient_id,
                action=AuditAction.UPDATE,
                collection_name="patients",
                document_id=patient_id,
                performed_by=performed_by,
                performed_by_role=performed_by_role,
                changes=changes,
            )
            return True
        return False
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while updating patient: {exc}") from exc


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------

def create_visit(
    db: DatabaseConnection,
    visit: Visit,
    *,
    performed_by: str = "system",
    performed_by_role: str = "doctor",
) -> str:
    """Insert a new visit document into the 'visits' collection.

    Verifies the referenced patient exists before inserting.

    Args:
        db: Active DatabaseConnection.
        visit: Validated Visit Pydantic model.
        performed_by: Doctor or system creating the visit record.
        performed_by_role: Role of the actor.

    Returns:
        The visit_id of the newly created visit.

    Raises:
        ValueError: If the patient_id does not exist or visit_id is duplicate.
        RuntimeError: On unexpected database error.
    """
    try:
        patient_exists = db.get_collection("patients").find_one(
            {"patient_id": visit.patient_id}, {"_id": 1}
        )
        if not patient_exists:
            raise ValueError(
                f"Cannot create visit: patient '{visit.patient_id}' does not exist."
            )

        doc = _serialize(visit.model_dump())
        db.get_collection("visits").insert_one(doc)
        _write_audit(
            db,
            patient_id=visit.patient_id,
            action=AuditAction.CREATE,
            collection_name="visits",
            document_id=visit.visit_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
        )
        return visit.visit_id
    except DuplicateKeyError:
        raise ValueError(f"Visit with visit_id='{visit.visit_id}' already exists.")
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while creating visit: {exc}") from exc


def get_patient_visits(
    db: DatabaseConnection,
    patient_id: str,
    *,
    limit: int = 20,
    skip: int = 0,
    sort_desc: bool = True,
) -> list[dict]:
    """Return visit history for a patient, sorted by visit date.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.
        limit: Maximum number of visits to return (default 20, max 100).
        skip: Number of documents to skip for pagination.
        sort_desc: If True, newest visits are returned first.

    Returns:
        List of visit dicts (without ``_id``), ordered by visit_date.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        direction = DESCENDING if sort_desc else ASCENDING
        cursor = (
            db.get_collection("visits")
            .find({"patient_id": patient_id}, {"_id": 0})
            .sort("visit_date", direction)
            .skip(skip)
            .limit(min(limit, 100))
        )
        return list(cursor)
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while fetching visits: {exc}") from exc


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

def create_appointment(
    db: DatabaseConnection,
    appointment: Appointment,
    *,
    performed_by: str = "system",
    performed_by_role: str = "receptionist",
) -> str:
    """Insert a new appointment into the 'appointments' collection.

    Verifies the referenced patient exists before inserting.

    Args:
        db: Active DatabaseConnection.
        appointment: Validated Appointment Pydantic model.
        performed_by: Staff member or system scheduling the appointment.
        performed_by_role: Role of the actor.

    Returns:
        The appointment_id of the newly created appointment.

    Raises:
        ValueError: If the patient does not exist or appointment_id is duplicate.
        RuntimeError: On unexpected database error.
    """
    try:
        patient_exists = db.get_collection("patients").find_one(
            {"patient_id": appointment.patient_id}, {"_id": 1}
        )
        if not patient_exists:
            raise ValueError(
                f"Cannot create appointment: patient '{appointment.patient_id}' "
                "does not exist."
            )

        doc = _serialize(appointment.model_dump())
        db.get_collection("appointments").insert_one(doc)
        _write_audit(
            db,
            patient_id=appointment.patient_id,
            action=AuditAction.CREATE,
            collection_name="appointments",
            document_id=appointment.appointment_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
        )
        return appointment.appointment_id
    except DuplicateKeyError:
        raise ValueError(
            f"Appointment with appointment_id='{appointment.appointment_id}' "
            "already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(
            f"Database error while creating appointment: {exc}"
        ) from exc


def get_appointments(
    db: DatabaseConnection,
    patient_id: str,
    *,
    status: Optional[AppointmentStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 20,
    skip: int = 0,
) -> list[dict]:
    """Return appointments for a patient with optional status and date filters.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.
        status: Optional filter by AppointmentStatus enum value.
        from_date: Optional lower bound for scheduled_at (inclusive).
        to_date: Optional upper bound for scheduled_at (inclusive).
        limit: Maximum results to return (default 20, max 100).
        skip: Number of documents to skip for pagination.

    Returns:
        List of appointment dicts (without ``_id``), ordered by scheduled_at.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        query: dict[str, Any] = {"patient_id": patient_id}
        if status:
            query["status"] = status.value
        if from_date or to_date:
            date_filter: dict = {}
            if from_date:
                date_filter["$gte"] = from_date
            if to_date:
                date_filter["$lte"] = to_date
            query["scheduled_at"] = date_filter

        cursor = (
            db.get_collection("appointments")
            .find(query, {"_id": 0})
            .sort("scheduled_at", ASCENDING)
            .skip(skip)
            .limit(min(limit, 100))
        )
        return list(cursor)
    except PyMongoError as exc:
        raise RuntimeError(
            f"Database error while fetching appointments: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

def create_referral(
    db: DatabaseConnection,
    referral: Referral,
    *,
    performed_by: str = "system",
    performed_by_role: str = "doctor",
) -> str:
    """Insert a new referral into the 'referrals' collection.

    Verifies the referenced patient exists before inserting.

    Args:
        db: Active DatabaseConnection.
        referral: Validated Referral Pydantic model.
        performed_by: Doctor or system creating the referral.
        performed_by_role: Role of the actor.

    Returns:
        The referral_id of the newly created referral.

    Raises:
        ValueError: If the patient does not exist or referral_id is duplicate.
        RuntimeError: On unexpected database error.
    """
    try:
        patient_exists = db.get_collection("patients").find_one(
            {"patient_id": referral.patient_id}, {"_id": 1}
        )
        if not patient_exists:
            raise ValueError(
                f"Cannot create referral: patient '{referral.patient_id}' "
                "does not exist."
            )

        doc = _serialize(referral.model_dump())
        db.get_collection("referrals").insert_one(doc)
        _write_audit(
            db,
            patient_id=referral.patient_id,
            action=AuditAction.CREATE,
            collection_name="referrals",
            document_id=referral.referral_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
        )
        return referral.referral_id
    except DuplicateKeyError:
        raise ValueError(
            f"Referral with referral_id='{referral.referral_id}' already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while creating referral: {exc}") from exc


def get_referrals(
    db: DatabaseConnection,
    patient_id: str,
    *,
    status: Optional[ReferralStatus] = None,
    referred_to_department: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
) -> list[dict]:
    """Return referrals for a patient with optional status and department filters.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.
        status: Optional filter by ReferralStatus enum value.
        referred_to_department: Optional filter by destination department.
        limit: Maximum results to return (default 20, max 100).
        skip: Number of documents to skip for pagination.

    Returns:
        List of referral dicts (without ``_id``), ordered by referral_date descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        query: dict[str, Any] = {"patient_id": patient_id}
        if status:
            query["status"] = status.value
        if referred_to_department:
            query["referred_to_department"] = {
                "$regex": referred_to_department,
                "$options": "i",
            }

        cursor = (
            db.get_collection("referrals")
            .find(query, {"_id": 0})
            .sort("referral_date", DESCENDING)
            .skip(skip)
            .limit(min(limit, 100))
        )
        return list(cursor)
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while fetching referrals: {exc}") from exc
