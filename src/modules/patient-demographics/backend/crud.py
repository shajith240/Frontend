"""PyMongo CRUD operations for all patient-demographics collections.

All write operations fire the relevant triggers automatically — callers never
need to invoke trigger functions directly, mirroring how SQL triggers work.

Trigger wiring:
  create_patient      → age_calculator_trigger, audit_log_trigger
  get_patient_by_id   → audit_log_trigger (READ)
  update_patient      → audit_log_trigger (UPDATE, with before/after diff)
  create_visit        → audit_log_trigger, visit_frequency_alert_trigger,
                        abnormal_vitals_trigger (when vital_signs present)
  create_appointment  → appointment_conflict_trigger, audit_log_trigger
  create_referral     → audit_log_trigger
"""

from datetime import datetime
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.database import DatabaseConnection
from backend.models import (
    Appointment,
    AppointmentStatus,
    AuditAction,
    Department,
    Patient,
    Physician,
    Referral,
    ReferralStatus,
    Visit,
    VisitDepartment,
)
from backend.triggers import (
    age_calculator_trigger,
    abnormal_vitals_trigger,
    appointment_conflict_trigger,
    audit_log_trigger,
    visit_frequency_alert_trigger,
    _serialize_doc,
)


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

    Fires age_calculator_trigger before insertion to populate the age field,
    then fires audit_log_trigger after successful insertion.

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
        doc = _serialize_doc(patient.model_dump())

        # TRIGGER: age_calculator_trigger — compute and stamp age before insert
        doc["age"] = age_calculator_trigger(patient.date_of_birth)

        db.get_collection("patients").insert_one(doc)

        # TRIGGER: audit_log_trigger — log the CREATE action
        audit_log_trigger(
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

    Fires audit_log_trigger (READ) when a matching document is found.

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
            # TRIGGER: audit_log_trigger — log the READ action
            audit_log_trigger(
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
    is_active: Optional[bool] = True,
    limit: int = 50,
    skip: int = 0,
) -> list[dict]:
    """Search patients by name substring, phone, or active status.

    All filters are combined with AND logic. Name matching is
    case-insensitive substring search across first_name and last_name.

    Args:
        db: Active DatabaseConnection.
        name: Optional substring to match against first_name + last_name.
        phone: Optional exact phone number filter.
        is_active: Filter by active status (default True). Pass None to skip.
        limit: Maximum results to return (default 50, max 200).
        skip: Number of documents to skip for pagination.

    Returns:
        List of matching patient dicts (without ``_id``), sorted by last_name.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        query: dict[str, Any] = {}
        if name:
            # Split into words so full-name queries like "Aarav Patel" work.
            # Each word must match either first_name or last_name.
            words = name.strip().split()
            if len(words) > 1:
                query["$and"] = [
                    {
                        "$or": [
                            {"first_name": {"$regex": word, "$options": "i"}},
                            {"last_name": {"$regex": word, "$options": "i"}},
                        ]
                    }
                    for word in words
                ]
            else:
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

    Automatically stamps updated_at. Fires audit_log_trigger with a
    before/after diff when the document is successfully modified.

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

    # If date_of_birth is being updated, recompute age via trigger
    if "date_of_birth" in updates:
        dob = updates["date_of_birth"]
        if hasattr(dob, "year") and not isinstance(dob, datetime):
            # TRIGGER: age_calculator_trigger — recompute age on DOB change
            updates["age"] = age_calculator_trigger(dob)

    try:
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
            after = {**before, **updates}
            # TRIGGER: audit_log_trigger — log UPDATE with before/after diff
            audit_log_trigger(
                db,
                patient_id=patient_id,
                action=AuditAction.UPDATE,
                collection_name="patients",
                document_id=patient_id,
                performed_by=performed_by,
                performed_by_role=performed_by_role,
                before=before,
                after=after,
            )
            return True
        return False
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while updating patient: {exc}") from exc


# ---------------------------------------------------------------------------
# Physicians
# ---------------------------------------------------------------------------

def create_physician(
    db: DatabaseConnection,
    physician: Physician,
) -> str:
    """Insert a new physician document into the 'physicians' collection.

    Verifies the referenced department exists before inserting.

    Args:
        db: Active DatabaseConnection.
        physician: Validated Physician Pydantic model.

    Returns:
        The physician_id of the newly created physician.

    Raises:
        ValueError: If the department does not exist or physician_id is duplicate.
        RuntimeError: On unexpected database error.
    """
    try:
        dept_exists = db.get_collection("departments").find_one(
            {"department_id": physician.department_id}, {"_id": 1}
        )
        if not dept_exists:
            raise ValueError(
                f"Cannot create physician: department '{physician.department_id}' "
                "does not exist."
            )
        doc = _serialize_doc(physician.model_dump())
        db.get_collection("physicians").insert_one(doc)
        return physician.physician_id
    except DuplicateKeyError:
        raise ValueError(
            f"Physician with physician_id='{physician.physician_id}' already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while creating physician: {exc}") from exc


def get_physician_by_id(
    db: DatabaseConnection,
    physician_id: str,
) -> Optional[dict]:
    """Fetch a single physician document by physician_id.

    Args:
        db: Active DatabaseConnection.
        physician_id: The physician identifier to look up.

    Returns:
        The physician document (without ``_id``), or None if not found.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        return db.get_collection("physicians").find_one(
            {"physician_id": physician_id}, {"_id": 0}
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while fetching physician: {exc}") from exc


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

def create_department(
    db: DatabaseConnection,
    department: Department,
) -> str:
    """Insert a new department document into the 'departments' collection.

    Args:
        db: Active DatabaseConnection.
        department: Validated Department Pydantic model.

    Returns:
        The department_id of the newly created department.

    Raises:
        ValueError: If a department with the same department_id already exists.
        RuntimeError: On unexpected database error.
    """
    try:
        doc = _serialize_doc(department.model_dump())
        db.get_collection("departments").insert_one(doc)
        return department.department_id
    except DuplicateKeyError:
        raise ValueError(
            f"Department with department_id='{department.department_id}' already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while creating department: {exc}") from exc


def get_department_by_id(
    db: DatabaseConnection,
    department_id: str,
) -> Optional[dict]:
    """Fetch a single department document by department_id.

    Args:
        db: Active DatabaseConnection.
        department_id: The department identifier to look up.

    Returns:
        The department document (without ``_id``), or None if not found.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        return db.get_collection("departments").find_one(
            {"department_id": department_id}, {"_id": 0}
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while fetching department: {exc}") from exc


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

    Verifies both patient and physician exist. Fires three triggers after
    successful insertion: audit_log_trigger, visit_frequency_alert_trigger,
    and abnormal_vitals_trigger (only when vital_signs are present).

    Args:
        db: Active DatabaseConnection.
        visit: Validated Visit Pydantic model.
        performed_by: Doctor or system creating the visit record.
        performed_by_role: Role of the actor.

    Returns:
        The visit_id of the newly created visit.

    Raises:
        ValueError: If the patient or physician does not exist, or visit_id is duplicate.
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

        physician_exists = db.get_collection("physicians").find_one(
            {"physician_id": visit.physician_id}, {"_id": 1}
        )
        if not physician_exists:
            raise ValueError(
                f"Cannot create visit: physician '{visit.physician_id}' does not exist."
            )

        doc = _serialize_doc(visit.model_dump())
        db.get_collection("visits").insert_one(doc)

        # TRIGGER: audit_log_trigger — log the CREATE action
        audit_log_trigger(
            db,
            patient_id=visit.patient_id,
            action=AuditAction.CREATE,
            collection_name="visits",
            document_id=visit.visit_id,
            performed_by=performed_by,
            performed_by_role=performed_by_role,
        )

        # TRIGGER: visit_frequency_alert_trigger — alert if >3 visits in 30 days
        visit_frequency_alert_trigger(db, visit.patient_id, visit.visit_id)

        # TRIGGER: abnormal_vitals_trigger — alert on out-of-range vitals
        if visit.vital_signs is not None:
            abnormal_vitals_trigger(
                db, visit.patient_id, visit.visit_id, visit.vital_signs
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
    """Return visit history for a patient, sorted by visit_date.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.
        limit: Maximum visits to return (default 20, max 100).
        skip: Number of documents to skip for pagination.
        sort_desc: Newest visits first when True (default).

    Returns:
        List of visit dicts (without ``_id``).

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
# VisitDepartment (junction)
# ---------------------------------------------------------------------------

def link_visit_department(
    db: DatabaseConnection,
    visit_department: VisitDepartment,
) -> None:
    """Insert a VisitDepartment junction record to associate a visit with a department.

    Verifies both visit and department exist before inserting. Resolves the
    Visit ↔ Department M-to-N relationship from the ER diagram.

    Args:
        db: Active DatabaseConnection.
        visit_department: Validated VisitDepartment junction model.

    Raises:
        ValueError: If the visit or department does not exist, or link already exists.
        RuntimeError: On unexpected database error.
    """
    try:
        visit_exists = db.get_collection("visits").find_one(
            {"visit_id": visit_department.visit_id}, {"_id": 1}
        )
        if not visit_exists:
            raise ValueError(
                f"Cannot link: visit '{visit_department.visit_id}' does not exist."
            )

        dept_exists = db.get_collection("departments").find_one(
            {"department_id": visit_department.department_id}, {"_id": 1}
        )
        if not dept_exists:
            raise ValueError(
                f"Cannot link: department '{visit_department.department_id}' does not exist."
            )

        doc = _serialize_doc(visit_department.model_dump())
        db.get_collection("visit_departments").insert_one(doc)
    except DuplicateKeyError:
        raise ValueError(
            f"Link between visit '{visit_department.visit_id}' and department "
            f"'{visit_department.department_id}' already exists."
        )
    except PyMongoError as exc:
        raise RuntimeError(f"Database error while linking visit to department: {exc}") from exc


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

    Fires appointment_conflict_trigger BEFORE insertion to block double-booking,
    then fires audit_log_trigger after successful insertion.

    Args:
        db: Active DatabaseConnection.
        appointment: Validated Appointment Pydantic model.
        performed_by: Staff member or system scheduling the appointment.
        performed_by_role: Role of the actor.

    Returns:
        The appointment_id of the newly created appointment.

    Raises:
        ValueError: If the patient/physician doesn't exist, appointment_id is
            duplicate, or physician has a scheduling conflict.
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

        physician_exists = db.get_collection("physicians").find_one(
            {"physician_id": appointment.physician_id}, {"_id": 1}
        )
        if not physician_exists:
            raise ValueError(
                f"Cannot create appointment: physician '{appointment.physician_id}' "
                "does not exist."
            )

        # TRIGGER: appointment_conflict_trigger — block double-booking BEFORE insert
        appointment_conflict_trigger(
            db,
            appointment.physician_id,
            appointment.appointment_date_and_time,
        )

        doc = _serialize_doc(appointment.model_dump())
        db.get_collection("appointments").insert_one(doc)

        # TRIGGER: audit_log_trigger — log the CREATE action
        audit_log_trigger(
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
        from_date: Optional lower bound for appointment_date_and_time (inclusive).
        to_date: Optional upper bound for appointment_date_and_time (inclusive).
        limit: Maximum results to return (default 20, max 100).
        skip: Number of documents to skip for pagination.

    Returns:
        List of appointment dicts (without ``_id``), sorted by
        appointment_date_and_time ascending.

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
            query["appointment_date_and_time"] = date_filter

        cursor = (
            db.get_collection("appointments")
            .find(query, {"_id": 0})
            .sort("appointment_date_and_time", ASCENDING)
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

    Verifies the patient, source physician, and target physician all exist.
    Fires audit_log_trigger after successful insertion.

    Args:
        db: Active DatabaseConnection.
        referral: Validated Referral Pydantic model.
        performed_by: Doctor or system creating the referral.
        performed_by_role: Role of the actor.

    Returns:
        The referral_id of the newly created referral.

    Raises:
        ValueError: If the patient/physicians don't exist or referral_id is duplicate.
        RuntimeError: On unexpected database error.
    """
    try:
        patient_exists = db.get_collection("patients").find_one(
            {"patient_id": referral.patient_id}, {"_id": 1}
        )
        if not patient_exists:
            raise ValueError(
                f"Cannot create referral: patient '{referral.patient_id}' does not exist."
            )

        for role, physician_id in [
            ("source", referral.source_physician_id),
            ("target", referral.target_physician_id),
        ]:
            phy_exists = db.get_collection("physicians").find_one(
                {"physician_id": physician_id}, {"_id": 1}
            )
            if not phy_exists:
                raise ValueError(
                    f"Cannot create referral: {role} physician '{physician_id}' "
                    "does not exist."
                )

        doc = _serialize_doc(referral.model_dump())
        db.get_collection("referrals").insert_one(doc)

        # TRIGGER: audit_log_trigger — log the CREATE action
        audit_log_trigger(
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
    source_physician_id: Optional[str] = None,
    target_physician_id: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
) -> list[dict]:
    """Return referrals for a patient with optional filters.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.
        status: Optional filter by ReferralStatus enum value.
        source_physician_id: Optional filter by referring physician.
        target_physician_id: Optional filter by specialist receiving the referral.
        limit: Maximum results to return (default 20, max 100).
        skip: Number of documents to skip for pagination.

    Returns:
        List of referral dicts (without ``_id``), sorted by referral_date descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    try:
        query: dict[str, Any] = {"patient_id": patient_id}
        if status:
            query["status"] = status.value
        if source_physician_id:
            query["source_physician_id"] = source_physician_id
        if target_physician_id:
            query["target_physician_id"] = target_physician_id

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
