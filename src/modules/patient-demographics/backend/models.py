"""Pydantic models for all 6 MongoDB collections in the patient demographics module."""

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


class AppointmentStatus(str, Enum):
    """Lifecycle states for an appointment."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReferralStatus(str, Enum):
    """Lifecycle states for a referral."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"


class AlertSeverity(str, Enum):
    """Clinical urgency of an alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Category of clinical alert."""

    ALLERGY = "allergy"
    DRUG_INTERACTION = "drug_interaction"
    ABNORMAL_VITALS = "abnormal_vitals"
    LAB_RESULT = "lab_result"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class AuditAction(str, Enum):
    """Database operation recorded in the audit log."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

PATIENT_ID_PATTERN = re.compile(r"^PAT-\d{4}-\d{3}$")


def validate_patient_id(value: str) -> str:
    """Validate that a patient_id matches the PAT-YYYY-NNN format.

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
    """Physical address of a patient."""

    street: str = Field(..., description="Street address including house/flat number")
    city: str = Field(..., description="City or town")
    state: str = Field(..., description="State or province")
    postal_code: str = Field(..., description="ZIP / PIN code")
    country: str = Field(default="India", description="Country name")


class EmergencyContact(BaseModel):
    """Emergency contact details for a patient."""

    name: str = Field(..., description="Full name of the emergency contact")
    relationship: str = Field(..., description="Relationship to the patient (e.g. spouse)")
    phone: str = Field(..., description="Primary phone number of the contact")


class VitalSigns(BaseModel):
    """Vital signs recorded during a clinical visit."""

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
# Collection models
# ---------------------------------------------------------------------------

class Patient(BaseModel):
    """Document model for the 'patients' MongoDB collection.

    Stores all demographic information for a registered patient.
    patient_id is the universal foreign key used across all collections.
    """

    patient_id: str = Field(
        ...,
        description="Unique patient identifier in PAT-YYYY-NNN format",
        examples=["PAT-2024-001"],
    )
    first_name: str = Field(..., min_length=1, description="Patient's first / given name")
    last_name: str = Field(..., min_length=1, description="Patient's last / family name")
    date_of_birth: date = Field(..., description="Date of birth (YYYY-MM-DD)")
    gender: Gender = Field(..., description="Patient's gender")
    blood_group: BloodGroup = Field(
        default=BloodGroup.UNKNOWN, description="ABO + Rh blood group"
    )
    phone: str = Field(..., description="Primary contact phone number")
    email: Optional[str] = Field(None, description="Email address")
    address: Optional[Address] = Field(None, description="Residential address")
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


class Visit(BaseModel):
    """Document model for the 'visits' MongoDB collection.

    Records each clinical encounter between a patient and a healthcare provider.
    """

    visit_id: str = Field(..., description="Unique identifier for this visit (e.g. VIS-2024-001)")
    patient_id: str = Field(..., description="Foreign key — references Patient.patient_id")
    visit_date: datetime = Field(..., description="Date and time of the visit (UTC)")
    department: str = Field(..., description="Hospital department (e.g. Cardiology)")
    attending_doctor: str = Field(..., description="Full name of the attending physician")
    doctor_id: str = Field(..., description="Unique identifier of the attending doctor")
    chief_complaint: str = Field(..., description="Primary reason for the visit")
    diagnosis: list[str] = Field(
        default_factory=list, description="ICD-10 diagnoses recorded during the visit"
    )
    vital_signs: Optional[VitalSigns] = Field(
        None, description="Vital signs measured during the visit"
    )
    prescriptions: list[str] = Field(
        default_factory=list, description="Medications prescribed at this visit"
    )
    lab_orders: list[str] = Field(
        default_factory=list, description="Laboratory investigations ordered"
    )
    imaging_orders: list[str] = Field(
        default_factory=list, description="Imaging studies ordered (X-ray, MRI, etc.)"
    )
    notes: Optional[str] = Field(None, description="Free-text clinical notes by the doctor")
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
        """Validate the patient_id foreign key format."""
        return validate_patient_id(v)

    @field_validator("follow_up_date")
    @classmethod
    def follow_up_after_visit(cls, v: Optional[date]) -> Optional[date]:
        """Ensure follow-up date is not in the past."""
        if v is not None and v < date.today():
            raise ValueError("follow_up_date cannot be in the past")
        return v


class Appointment(BaseModel):
    """Document model for the 'appointments' MongoDB collection.

    Tracks scheduled appointments for patients with specific doctors or departments.
    """

    appointment_id: str = Field(
        ..., description="Unique appointment identifier (e.g. APT-2024-001)"
    )
    patient_id: str = Field(..., description="Foreign key — references Patient.patient_id")
    doctor_id: str = Field(..., description="Unique identifier of the assigned doctor")
    doctor_name: str = Field(..., description="Full name of the assigned doctor")
    department: str = Field(..., description="Hospital department for the appointment")
    scheduled_at: datetime = Field(
        ..., description="Scheduled date and time of the appointment (UTC)"
    )
    duration_minutes: int = Field(
        default=30, ge=5, le=480, description="Appointment duration in minutes"
    )
    status: AppointmentStatus = Field(
        default=AppointmentStatus.SCHEDULED, description="Current appointment status"
    )
    reason: str = Field(..., description="Reason or purpose of the appointment")
    notes: Optional[str] = Field(None, description="Additional notes from scheduling staff")
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
        """Validate the patient_id foreign key format."""
        return validate_patient_id(v)

    @model_validator(mode="after")
    def cancellation_reason_required_when_cancelled(self) -> "Appointment":
        """Ensure cancellation_reason is provided when status is CANCELLED."""
        if (
            self.status == AppointmentStatus.CANCELLED
            and not self.cancellation_reason
        ):
            raise ValueError(
                "cancellation_reason is required when status is 'cancelled'"
            )
        return self


class Referral(BaseModel):
    """Document model for the 'referrals' MongoDB collection.

    Records inter-department or inter-hospital referrals for a patient.
    """

    referral_id: str = Field(
        ..., description="Unique referral identifier (e.g. REF-2024-001)"
    )
    patient_id: str = Field(..., description="Foreign key — references Patient.patient_id")
    referring_doctor_id: str = Field(
        ..., description="Unique identifier of the doctor initiating the referral"
    )
    referring_doctor_name: str = Field(
        ..., description="Full name of the referring doctor"
    )
    referring_department: str = Field(
        ..., description="Department from which the referral originates"
    )
    referred_to_doctor_id: Optional[str] = Field(
        None, description="Unique identifier of the specialist receiving the referral"
    )
    referred_to_doctor_name: Optional[str] = Field(
        None, description="Full name of the specialist receiving the referral"
    )
    referred_to_department: str = Field(
        ..., description="Destination department or specialty"
    )
    referred_to_hospital: Optional[str] = Field(
        None, description="External hospital name if the referral is outside this facility"
    )
    reason: str = Field(..., description="Clinical reason for the referral")
    urgency: AlertSeverity = Field(
        default=AlertSeverity.MEDIUM, description="Urgency level of the referral"
    )
    status: ReferralStatus = Field(
        default=ReferralStatus.PENDING, description="Current status of the referral"
    )
    notes: Optional[str] = Field(None, description="Additional clinical notes")
    referral_date: datetime = Field(
        default_factory=datetime.utcnow, description="Date and time the referral was created (UTC)"
    )
    accepted_at: Optional[datetime] = Field(
        None, description="Timestamp when the referral was accepted"
    )
    completed_at: Optional[datetime] = Field(
        None, description="Timestamp when the referral was completed"
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
        """Validate the patient_id foreign key format."""
        return validate_patient_id(v)


class Alert(BaseModel):
    """Document model for the 'alerts' MongoDB collection.

    Stores clinical alerts generated by the AI decision support system or
    clinical staff for a specific patient.
    """

    alert_id: str = Field(
        ..., description="Unique alert identifier (e.g. ALT-2024-001)"
    )
    patient_id: str = Field(..., description="Foreign key — references Patient.patient_id")
    alert_type: AlertType = Field(..., description="Category of the alert")
    severity: AlertSeverity = Field(..., description="Clinical urgency level")
    title: str = Field(..., min_length=1, description="Short descriptive title for the alert")
    message: str = Field(..., min_length=1, description="Detailed alert message")
    source: str = Field(
        ..., description="System or person that generated the alert (e.g. 'AI Engine', 'Dr. Smith')"
    )
    is_acknowledged: bool = Field(
        default=False, description="Whether a clinician has acknowledged the alert"
    )
    acknowledged_by: Optional[str] = Field(
        None, description="Name or ID of the clinician who acknowledged the alert"
    )
    acknowledged_at: Optional[datetime] = Field(
        None, description="Timestamp when the alert was acknowledged"
    )
    is_resolved: bool = Field(
        default=False, description="Whether the underlying issue has been resolved"
    )
    resolved_at: Optional[datetime] = Field(
        None, description="Timestamp when the alert was resolved"
    )
    related_visit_id: Optional[str] = Field(
        None, description="Visit ID that triggered this alert, if applicable"
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
        """Validate the patient_id foreign key format."""
        return validate_patient_id(v)

    @model_validator(mode="after")
    def acknowledged_fields_consistent(self) -> "Alert":
        """Ensure acknowledged_by and acknowledged_at are set when is_acknowledged is True."""
        if self.is_acknowledged and not self.acknowledged_by:
            raise ValueError(
                "acknowledged_by is required when is_acknowledged is True"
            )
        return self


class AuditLog(BaseModel):
    """Document model for the 'audit_logs' MongoDB collection.

    Records every create / read / update / delete operation on patient data
    for compliance, security, and traceability.
    """

    log_id: str = Field(
        ..., description="Unique log entry identifier (e.g. LOG-2024-001)"
    )
    patient_id: str = Field(..., description="Foreign key — references Patient.patient_id")
    action: AuditAction = Field(..., description="Type of database operation performed")
    collection_name: str = Field(
        ..., description="MongoDB collection that was modified (e.g. 'patients', 'visits')"
    )
    document_id: str = Field(
        ..., description="ID of the document that was created, read, updated, or deleted"
    )
    performed_by: str = Field(
        ..., description="User ID or system identifier that performed the action"
    )
    performed_by_role: str = Field(
        ..., description="Role of the actor (e.g. 'doctor', 'nurse', 'admin', 'system')"
    )
    ip_address: Optional[str] = Field(
        None, description="IP address of the client that initiated the request"
    )
    changes: Optional[dict] = Field(
        None,
        description=(
            "Dictionary describing what changed: "
            "{'field': {'before': old_value, 'after': new_value}}"
        ),
    )
    reason: Optional[str] = Field(
        None, description="Optional justification for the action (e.g. for record updates)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Exact UTC timestamp when the action occurred",
    )

    @field_validator("patient_id")
    @classmethod
    def check_patient_id(cls, v: str) -> str:
        """Validate the patient_id foreign key format."""
        return validate_patient_id(v)
