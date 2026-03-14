"""Pydantic models for all collections in the patient-demographics module.

Entity structure mirrors the submitted ER diagram exactly:
  Patient ──< Appointment >── Physician >── Department
  Patient ──< Visit       >── Physician
  Visit   ><  Department  (via VisitDepartment junction)
  Patient ──< Referral (SourcePhysician, TargetPhysician)

Additional models for operational support: Alert, AuditLog.
"""

import re
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Gender(str, Enum):
    """Biological sex recorded for clinical purposes."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class BloodGroup(str, Enum):
    """ABO + Rh blood group."""

    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "unknown"


class VisitStatus(str, Enum):
    """Lifecycle states for a clinical visit (ER: Visit.Status)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    DISCHARGED = "discharged"
    CANCELLED = "cancelled"


class AppointmentStatus(str, Enum):
    """Lifecycle states for an appointment (ER: Appointment.Status)."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReferralStatus(str, Enum):
    """Lifecycle states for a referral (ER: Referral.Status)."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"


class AlertSeverity(str, Enum):
    """Clinical urgency of a system-generated alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Category of a system-generated alert."""

    ALLERGY = "allergy"
    DRUG_INTERACTION = "drug_interaction"
    ABNORMAL_VITALS = "abnormal_vitals"
    VISIT_FREQUENCY = "visit_frequency"
    LAB_RESULT = "lab_result"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class AuditAction(str, Enum):
    """Database operation captured in audit_logs."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


# ---------------------------------------------------------------------------
# Shared ID format validator
# ---------------------------------------------------------------------------

PATIENT_ID_PATTERN = re.compile(r"^PAT-\d{4}-\d{3}$")


def validate_patient_id(value: str) -> str:
    """Validate that a value matches the PAT-YYYY-NNN format.

    Args:
        value: The patient ID string to validate.

    Returns:
        The validated patient ID string.

    Raises:
        ValueError: If the format does not match PAT-YYYY-NNN.
    """
    if not PATIENT_ID_PATTERN.match(value):
        raise ValueError(
            f"patient_id must match PAT-YYYY-NNN (e.g. PAT-2024-001), got '{value}'"
        )
    return value


# ---------------------------------------------------------------------------
# Embedded / nested models
# ---------------------------------------------------------------------------

class Address(BaseModel):
    """Physical address (ER: Patient.Address — stored as embedded document)."""

    street: str = Field(..., description="Street address including house/flat number")
    city: str = Field(..., description="City or town")
    state: str = Field(..., description="State or province")
    postal_code: str = Field(..., description="ZIP / PIN code")
    country: str = Field(default="India", description="Country name")


class InsuranceInfo(BaseModel):
    """Insurance details (ER: Patient.Insurance — stored as embedded document)."""

    provider: str = Field(..., description="Name of the insurance provider")
    policy_number: str = Field(..., description="Policy number issued by the provider")
    group_number: Optional[str] = Field(None, description="Group / employer plan number")
    valid_until: Optional[date] = Field(None, description="Policy expiry date")


class EmergencyContact(BaseModel):
    """Emergency contact for a patient (supplementary operational field)."""

    name: str = Field(..., description="Full name of the emergency contact")
    relationship: str = Field(..., description="Relationship to the patient (e.g. spouse)")
    phone: str = Field(..., description="Primary phone number of the contact")


class VitalSigns(BaseModel):
    """Vital signs recorded during a visit.

    Not a separate ER entity but carried inside Visit documents so that
    the abnormal_vitals_trigger can evaluate them automatically.
    Normal clinical ranges are enforced at the trigger layer, not here.
    """

    blood_pressure_systolic: Optional[int] = Field(
        None, ge=50, le=300, description="Systolic BP in mmHg"
    )
    blood_pressure_diastolic: Optional[int] = Field(
        None, ge=20, le=200, description="Diastolic BP in mmHg"
    )
    heart_rate: Optional[int] = Field(None, ge=20, le=300, description="Heart rate in bpm")
    temperature_celsius: Optional[float] = Field(
        None, ge=30.0, le=45.0, description="Body temperature in °C"
    )
    respiratory_rate: Optional[int] = Field(
        None, ge=5, le=60, description="Breaths per minute"
    )
    oxygen_saturation: Optional[float] = Field(
        None, ge=50.0, le=100.0, description="SpO₂ percentage"
    )
    weight_kg: Optional[float] = Field(None, ge=0.5, le=700.0, description="Weight in kg")
    height_cm: Optional[float] = Field(None, ge=20.0, le=280.0, description="Height in cm")


# ---------------------------------------------------------------------------
# ER entities — core collection models
# ---------------------------------------------------------------------------

class Patient(BaseModel):
    """Document model for the 'patients' collection.

    ER attributes: PatientID, FirstName, LastName, DateOfBirth, Gender,
    Phone, Email, Address, Insurance.
    Additional operational fields: BloodGroup, EmergencyContact, allergies,
    chronic_conditions, current_medications, age (computed by trigger).
    """

    patient_id: str = Field(
        ...,
        description="ER: PatientID — unique identifier in PAT-YYYY-NNN format",
        examples=["PAT-2024-001"],
    )
    first_name: str = Field(..., min_length=1, description="ER: FirstName")
    last_name: str = Field(..., min_length=1, description="ER: LastName")
    date_of_birth: date = Field(..., description="ER: DateOfBirth (YYYY-MM-DD)")
    gender: Gender = Field(..., description="ER: Gender")
    phone: str = Field(..., description="ER: Phone — primary contact number")
    email: Optional[str] = Field(None, description="ER: Email")
    address: Optional[Address] = Field(None, description="ER: Address (embedded)")
    insurance: Optional[InsuranceInfo] = Field(
        None, description="ER: Insurance (embedded)"
    )
    # Computed by age_calculator_trigger on every insert — never set by caller
    age: Optional[int] = Field(
        None, ge=0, le=150, description="Age in years — auto-computed by trigger"
    )
    blood_group: BloodGroup = Field(
        default=BloodGroup.UNKNOWN, description="ABO + Rh blood group"
    )
    emergency_contact: Optional[EmergencyContact] = Field(
        None, description="Next-of-kin or emergency contact"
    )
    allergies: list[str] = Field(
        default_factory=list, description="Known drug or food allergies"
    )
    chronic_conditions: list[str] = Field(
        default_factory=list, description="Pre-existing or chronic medical conditions"
    )
    current_medications: list[str] = Field(
        default_factory=list, description="Medications currently being taken"
    )
    is_active: bool = Field(default=True, description="Whether the patient record is active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id format."""
        return validate_patient_id(v)

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date) -> date:
        """Ensure date of birth is not in the future."""
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v


class Department(BaseModel):
    """Document model for the 'departments' collection.

    ER attributes: DepartmentID, DepartmentName, Location.
    FK target of Physician.DepartmentID and VisitDepartment.DepartmentID.
    """

    department_id: str = Field(
        ..., description="ER: DepartmentID — unique identifier (e.g. DEP-2024-001)"
    )
    department_name: str = Field(..., min_length=1, description="ER: DepartmentName")
    location: str = Field(..., description="ER: Location — physical location in the hospital")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )


class Physician(BaseModel):
    """Document model for the 'physicians' collection.

    ER attributes: PhysicianID, FirstName, LastName, Speciality, DepartmentID.
    DepartmentID is a FK to the departments collection.
    """

    physician_id: str = Field(
        ..., description="ER: PhysicianID — unique identifier (e.g. PHY-2024-001)"
    )
    first_name: str = Field(..., min_length=1, description="ER: FirstName")
    last_name: str = Field(..., min_length=1, description="ER: LastName")
    speciality: str = Field(..., description="ER: Speciality (e.g. Cardiology)")
    department_id: str = Field(
        ..., description="ER: DepartmentID — FK to departments collection"
    )
    phone: Optional[str] = Field(None, description="Physician contact number")
    email: Optional[str] = Field(None, description="Physician email address")
    is_active: bool = Field(default=True, description="Whether the physician is currently active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )


class Appointment(BaseModel):
    """Document model for the 'appointments' collection.

    ER attributes: AppointmentID, AppointmentDateAndTime, Reason, Status,
    PatientID (FK), PhysicianID (FK).
    Relationship: Patient 1──N Appointment N──1 Physician.
    """

    appointment_id: str = Field(
        ..., description="ER: AppointmentID (e.g. APT-2024-001)"
    )
    patient_id: str = Field(..., description="ER: PatientID — FK to patients collection")
    physician_id: str = Field(
        ..., description="ER: PhysicianID — FK to physicians collection"
    )
    appointment_date_and_time: datetime = Field(
        ..., description="ER: AppointmentDateAndTime — scheduled UTC datetime"
    )
    reason: str = Field(..., description="ER: Reason — purpose of the appointment")
    status: AppointmentStatus = Field(
        default=AppointmentStatus.SCHEDULED, description="ER: Status"
    )
    notes: Optional[str] = Field(None, description="Additional scheduling notes")
    cancellation_reason: Optional[str] = Field(
        None, description="Reason provided when the appointment is cancelled"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id FK format."""
        return validate_patient_id(v)

    @model_validator(mode="after")
    def cancellation_reason_required_when_cancelled(self) -> "Appointment":
        """Ensure cancellation_reason is present when status is CANCELLED."""
        if (
            self.status == AppointmentStatus.CANCELLED
            and not self.cancellation_reason
        ):
            raise ValueError(
                "cancellation_reason is required when status is 'cancelled'"
            )
        return self


class Visit(BaseModel):
    """Document model for the 'visits' collection.

    ER attributes: VisitID, VisitDate, Reason, Diagnosis, Status,
    PatientID (FK), PhysicianID (FK).
    Relationship: Patient 1──N Visit N──1 Physician; Visit M──N Department
    via VisitDepartment junction.

    VitalSigns is an optional embedded sub-document (not in the ER but required
    by the abnormal_vitals_trigger specification).
    """

    visit_id: str = Field(..., description="ER: VisitID (e.g. VIS-2024-001)")
    patient_id: str = Field(..., description="ER: PatientID — FK to patients collection")
    physician_id: str = Field(
        ..., description="ER: PhysicianID — FK to physicians collection"
    )
    visit_date: date = Field(..., description="ER: VisitDate (YYYY-MM-DD)")
    reason: str = Field(..., description="ER: Reason — chief complaint / reason for visit")
    diagnosis: Optional[str] = Field(None, description="ER: Diagnosis — clinical diagnosis text")
    status: VisitStatus = Field(default=VisitStatus.ACTIVE, description="ER: Status")
    vital_signs: Optional[VitalSigns] = Field(
        None,
        description="Vital signs measured during the visit — evaluated by abnormal_vitals_trigger",
    )
    notes: Optional[str] = Field(None, description="Free-text clinical notes")
    follow_up_date: Optional[date] = Field(None, description="Recommended follow-up date")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id FK format."""
        return validate_patient_id(v)

    @field_validator("follow_up_date")
    @classmethod
    def follow_up_not_before_visit(cls, v: Optional[date]) -> Optional[date]:
        """Ensure follow-up date is not in the past."""
        if v is not None and v < date.today():
            raise ValueError("follow_up_date cannot be in the past")
        return v


class VisitDepartment(BaseModel):
    """Junction document for the Visit ↔ Department M-to-N relationship.

    ER: VisitDepartment(VisitID, DepartmentID) — resolves the many-to-many
    relationship between Visit and Department.
    Stored in the 'visit_departments' collection.
    """

    visit_id: str = Field(..., description="ER: VisitID — FK to visits collection")
    department_id: str = Field(
        ..., description="ER: DepartmentID — FK to departments collection"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Junction record creation timestamp (UTC)"
    )


class Referral(BaseModel):
    """Document model for the 'referrals' collection.

    ER attributes: ReferralID, ReferralDate, Reason, Status,
    SourcePhysicianID (FK), TargetPhysicianID (FK), PatientID (FK).
    Relationship: Patient 1──N Referral; two FK references to Physician.
    """

    referral_id: str = Field(
        ..., description="ER: ReferralID (e.g. REF-2024-001)"
    )
    patient_id: str = Field(..., description="ER: PatientID — FK to patients collection")
    source_physician_id: str = Field(
        ..., description="ER: SourcePhysicianID — FK to physicians (referring doctor)"
    )
    target_physician_id: str = Field(
        ..., description="ER: TargetPhysicianID — FK to physicians (specialist receiving referral)"
    )
    referral_date: datetime = Field(
        default_factory=datetime.utcnow, description="ER: ReferralDate — UTC datetime"
    )
    reason: str = Field(..., description="ER: Reason — clinical reason for the referral")
    status: ReferralStatus = Field(
        default=ReferralStatus.PENDING, description="ER: Status"
    )
    notes: Optional[str] = Field(None, description="Additional clinical notes")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record last-updated timestamp (UTC)"
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id FK format."""
        return validate_patient_id(v)


# ---------------------------------------------------------------------------
# Operational support models (not ER entities — required by system architecture)
# ---------------------------------------------------------------------------

class Alert(BaseModel):
    """Document model for the 'alerts' collection.

    Populated automatically by trigger functions (visit_frequency_alert_trigger,
    abnormal_vitals_trigger). Also feeds the Master DB global alerts view
    described in the project architecture slides.
    """

    alert_id: str = Field(..., description="Unique alert identifier (e.g. ALT-2024-001)")
    patient_id: str = Field(..., description="FK to patients collection")
    alert_type: AlertType = Field(..., description="Category of the alert")
    severity: AlertSeverity = Field(..., description="Clinical urgency level")
    title: str = Field(..., min_length=1, description="Short descriptive title")
    message: str = Field(..., min_length=1, description="Detailed alert message")
    source: str = Field(
        ...,
        description="System component or person that generated the alert",
    )
    is_acknowledged: bool = Field(default=False, description="Acknowledged by a clinician")
    acknowledged_by: Optional[str] = Field(None, description="Clinician who acknowledged")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgement timestamp")
    is_resolved: bool = Field(default=False, description="Underlying issue resolved")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    related_visit_id: Optional[str] = Field(None, description="Visit that triggered this alert")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id FK format."""
        return validate_patient_id(v)

    @model_validator(mode="after")
    def acknowledged_fields_consistent(self) -> "Alert":
        """Require acknowledged_by when is_acknowledged is True."""
        if self.is_acknowledged and not self.acknowledged_by:
            raise ValueError("acknowledged_by is required when is_acknowledged is True")
        return self


class AuditLog(BaseModel):
    """Document model for the 'audit_logs' collection.

    Written exclusively by audit_log_trigger. Feeds the Master DB's
    'Audit and access logs' requirement (project architecture slide 17).
    """

    log_id: str = Field(..., description="Unique log entry identifier (e.g. LOG-2024-001)")
    patient_id: str = Field(..., description="FK to patients collection")
    action: AuditAction = Field(..., description="CRUD operation performed")
    collection_name: str = Field(..., description="MongoDB collection that was touched")
    document_id: str = Field(..., description="ID of the document affected")
    performed_by: str = Field(..., description="User ID or system identifier")
    performed_by_role: str = Field(..., description="Role of the actor")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    changes: Optional[dict] = Field(
        None,
        description="Before/after diff: {'field': {'before': v1, 'after': v2}}",
    )
    reason: Optional[str] = Field(None, description="Optional justification for the action")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Exact UTC timestamp when the action occurred",
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id FK format."""
        return validate_patient_id(v)
