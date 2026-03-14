"""Seed data generator for the patient-demographics module.

Populates all 9 MongoDB collections with realistic Indian hospital data
using the Faker library. Run this script directly to seed a fresh database.

Collections populated (in FK dependency order):
  1. departments       — 5 fixed departments
  2. physicians        — 10 physicians (2 per department)
  3. patients          — 25 patients with Indian demographics
  4. visits            — 3–5 per patient (~100 total)
  5. visit_departments — 1–2 department links per visit (M-to-N junction)
  6. appointments      — 2–3 per patient (~60 total)
  7. referrals         — 15–20 total
  8. alerts            — written automatically by visit triggers
  9. audit_logs        — written automatically by audit_log_trigger

Usage:
    python database/seed_data.py
"""

import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from faker import Faker

# Make the backend package importable when running this script directly.
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.database import DatabaseConnection
from backend.models import (
    Address,
    Appointment,
    AppointmentStatus,
    AuditAction,
    BloodGroup,
    Department,
    Gender,
    InsuranceInfo,
    Patient,
    Physician,
    Referral,
    ReferralStatus,
    Visit,
    VisitDepartment,
    VisitStatus,
)
from backend.triggers import (
    _serialize_doc,
    age_calculator_trigger,
    audit_log_trigger,
    visit_frequency_alert_trigger,
    abnormal_vitals_trigger,
)

load_dotenv()

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

_SEED_YEAR = 2024


# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

DEPARTMENTS: list[dict] = [
    {
        "department_id": "DEP-2024-001",
        "department_name": "Cardiology",
        "location": "Block A, Ground Floor",
    },
    {
        "department_id": "DEP-2024-002",
        "department_name": "Neurology",
        "location": "Block B, First Floor",
    },
    {
        "department_id": "DEP-2024-003",
        "department_name": "Orthopedics",
        "location": "Block C, Ground Floor",
    },
    {
        "department_id": "DEP-2024-004",
        "department_name": "General Medicine",
        "location": "Block A, Second Floor",
    },
    {
        "department_id": "DEP-2024-005",
        "department_name": "Pediatrics",
        "location": "Block D, First Floor",
    },
]

PHYSICIANS: list[dict] = [
    # Cardiology — 2 physicians
    {
        "physician_id": "PHY-2024-001",
        "first_name": "Rajesh",
        "last_name": "Sharma",
        "speciality": "Cardiology",
        "department_id": "DEP-2024-001",
        "phone": "+91-9811234567",
        "email": "rajesh.sharma@cityhospital.in",
    },
    {
        "physician_id": "PHY-2024-002",
        "first_name": "Priya",
        "last_name": "Nair",
        "speciality": "Interventional Cardiology",
        "department_id": "DEP-2024-001",
        "phone": "+91-9822345678",
        "email": "priya.nair@cityhospital.in",
    },
    # Neurology — 2 physicians
    {
        "physician_id": "PHY-2024-003",
        "first_name": "Suresh",
        "last_name": "Kumar",
        "speciality": "Neurology",
        "department_id": "DEP-2024-002",
        "phone": "+91-9833456789",
        "email": "suresh.kumar@cityhospital.in",
    },
    {
        "physician_id": "PHY-2024-004",
        "first_name": "Anitha",
        "last_name": "Reddy",
        "speciality": "Neuropsychiatry",
        "department_id": "DEP-2024-002",
        "phone": "+91-9844567890",
        "email": "anitha.reddy@cityhospital.in",
    },
    # Orthopedics — 2 physicians
    {
        "physician_id": "PHY-2024-005",
        "first_name": "Vikram",
        "last_name": "Singh",
        "speciality": "Orthopaedics",
        "department_id": "DEP-2024-003",
        "phone": "+91-9855678901",
        "email": "vikram.singh@cityhospital.in",
    },
    {
        "physician_id": "PHY-2024-006",
        "first_name": "Meena",
        "last_name": "Iyer",
        "speciality": "Sports Medicine and Orthopaedics",
        "department_id": "DEP-2024-003",
        "phone": "+91-9866789012",
        "email": "meena.iyer@cityhospital.in",
    },
    # General Medicine — 2 physicians
    {
        "physician_id": "PHY-2024-007",
        "first_name": "Arun",
        "last_name": "Pillai",
        "speciality": "General Medicine",
        "department_id": "DEP-2024-004",
        "phone": "+91-9877890123",
        "email": "arun.pillai@cityhospital.in",
    },
    {
        "physician_id": "PHY-2024-008",
        "first_name": "Kavitha",
        "last_name": "Menon",
        "speciality": "Internal Medicine",
        "department_id": "DEP-2024-004",
        "phone": "+91-9888901234",
        "email": "kavitha.menon@cityhospital.in",
    },
    # Pediatrics — 2 physicians
    {
        "physician_id": "PHY-2024-009",
        "first_name": "Deepak",
        "last_name": "Gupta",
        "speciality": "Pediatrics",
        "department_id": "DEP-2024-005",
        "phone": "+91-9899012345",
        "email": "deepak.gupta@cityhospital.in",
    },
    {
        "physician_id": "PHY-2024-010",
        "first_name": "Sunita",
        "last_name": "Joshi",
        "speciality": "Neonatology and Paediatrics",
        "department_id": "DEP-2024-005",
        "phone": "+91-9800123456",
        "email": "sunita.joshi@cityhospital.in",
    },
]

# Physicians grouped by department (used when picking a physician for a visit/appointment)
_DEPT_PHYSICIANS: dict[str, list[str]] = {
    "DEP-2024-001": ["PHY-2024-001", "PHY-2024-002"],
    "DEP-2024-002": ["PHY-2024-003", "PHY-2024-004"],
    "DEP-2024-003": ["PHY-2024-005", "PHY-2024-006"],
    "DEP-2024-004": ["PHY-2024-007", "PHY-2024-008"],
    "DEP-2024-005": ["PHY-2024-009", "PHY-2024-010"],
}

_ALL_DEPT_IDS: list[str] = [d["department_id"] for d in DEPARTMENTS]
_ALL_PHY_IDS: list[str] = [p["physician_id"] for p in PHYSICIANS]

# Department-specific diagnoses — realistic Indian clinical presentations
_DIAGNOSES: dict[str, list[str]] = {
    "DEP-2024-001": [
        "Hypertensive heart disease",
        "Acute myocardial infarction — STEMI",
        "Atrial fibrillation with rapid ventricular response",
        "Coronary artery disease with stable angina",
        "Heart failure with reduced ejection fraction",
        "Unstable angina pectoris",
        "Rheumatic mitral stenosis — moderate",
    ],
    "DEP-2024-002": [
        "Migraine with aura",
        "Transient ischaemic attack",
        "Epilepsy — generalised tonic-clonic seizures",
        "Parkinson's disease — early stage",
        "Cervical spondylosis with C5-C6 radiculopathy",
        "Ischaemic stroke — left middle cerebral artery territory",
        "Guillain-Barré syndrome",
    ],
    "DEP-2024-003": [
        "Osteoarthritis of knee — bilateral grade III",
        "Lumbar intervertebral disc herniation at L4-L5",
        "Rotator cuff tear — right shoulder",
        "Fracture of distal radius — Colles' type",
        "Grade II lateral ankle ligament sprain",
        "Osteoporosis with L2 vertebral compression fracture",
        "Anterior cruciate ligament tear — left knee",
    ],
    "DEP-2024-004": [
        "Type 2 diabetes mellitus with peripheral neuropathy",
        "Essential hypertension — stage II",
        "Community-acquired pneumonia — right lower lobe",
        "Acute gastroenteritis with mild dehydration",
        "Iron deficiency anaemia — moderate",
        "Primary hypothyroidism",
        "Dengue fever — non-severe with thrombocytopaenia",
        "Enteric fever — Typhoid",
        "COPD — moderate — GOLD stage II",
    ],
    "DEP-2024-005": [
        "Acute viral pharyngitis",
        "Childhood asthma — mild persistent",
        "Acute suppurative otitis media",
        "Simple febrile seizure",
        "Viral bronchiolitis",
        "Moderate acute malnutrition",
        "Acute watery diarrhoea with mild dehydration",
    ],
}

# Physician-to-primary-department mapping for quick lookup
_PHY_DEPT: dict[str, str] = {
    phy["physician_id"]: phy["department_id"] for phy in PHYSICIANS
}

_VISIT_REASONS: list[str] = [
    "Chest pain and shortness of breath",
    "Persistent headache and dizziness",
    "Knee pain and difficulty walking",
    "High-grade fever with body ache",
    "Follow-up for diabetes management",
    "Routine annual health check-up",
    "Cough, cold, and sore throat",
    "Abdominal pain and vomiting",
    "Back pain radiating to left leg",
    "Palpitations and irregular heartbeat",
    "Child with persistent cough and fever",
    "Post-surgery follow-up review",
    "Numbness and tingling in hands",
    "Joint swelling and morning stiffness",
    "Fatigue, weakness, and weight loss",
    "Breathlessness on exertion",
    "Swelling of feet and ankles",
    "Difficulty swallowing and hoarseness",
]

_APPOINTMENT_REASONS: list[str] = [
    "Cardiology outpatient consultation",
    "Neurology outpatient consultation",
    "Orthopaedics evaluation and review",
    "General medicine check-up",
    "Paediatric growth and development review",
    "Follow-up after hospitalisation",
    "Medication review and adjustment",
    "Pre-operative fitness assessment",
    "Post-operative follow-up",
    "Chronic disease monitoring visit",
    "Specialist referral appointment",
    "Vaccination and immunisation review",
]

_REFERRAL_REASONS: list[str] = [
    "Requires specialised cardiac catheterisation and intervention",
    "Complex neurological workup — EEG and MRI review needed",
    "Orthopaedic surgical evaluation for total knee replacement",
    "Uncontrolled hypertension with suspected secondary cause",
    "Suspected partial seizures — neurology opinion required",
    "Chronic knee pain unresponsive to conservative management",
    "Poorly controlled Type 2 diabetes — endocrinology referral",
    "Recurrent chest pain — coronary angiography recommended",
    "Persistent lumbar back pain — surgical opinion needed",
    "Childhood developmental delay — detailed neurological evaluation",
    "Post-stroke rehabilitation planning",
    "Paediatric asthma — poor response to inhaled steroids",
]

_CANCELLATION_REASONS: list[str] = [
    "Patient requested reschedule due to personal reasons",
    "Physician on leave — appointment rescheduled",
    "Patient admitted to emergency — OPD appointment cancelled",
    "Patient travelled out of city",
    "Duplicate booking — cancelled by front desk",
]

_INSURANCE_PROVIDERS: list[str] = [
    "Star Health and Allied Insurance",
    "HDFC ERGO Health Insurance",
    "Bajaj Allianz General Insurance",
    "New India Assurance Company",
    "United India Insurance Company",
    "Niva Bupa Health Insurance",
    "Aditya Birla Health Insurance",
    "ICICI Lombard General Insurance",
]

# (city, state, pin_prefix) — realistic Indian hospital catchment cities
_CITIES: list[tuple[str, str, str]] = [
    ("Mumbai", "Maharashtra", "400"),
    ("Delhi", "Delhi", "110"),
    ("Bengaluru", "Karnataka", "560"),
    ("Hyderabad", "Telangana", "500"),
    ("Chennai", "Tamil Nadu", "600"),
    ("Kolkata", "West Bengal", "700"),
    ("Pune", "Maharashtra", "411"),
    ("Ahmedabad", "Gujarat", "380"),
    ("Jaipur", "Rajasthan", "302"),
    ("Lucknow", "Uttar Pradesh", "226"),
    ("Dhanbad", "Jharkhand", "826"),
    ("Patna", "Bihar", "800"),
    ("Bhopal", "Madhya Pradesh", "462"),
    ("Kochi", "Kerala", "682"),
    ("Chandigarh", "Punjab", "160"),
]

_MALE_FIRST_NAMES: list[str] = [
    "Aarav", "Arjun", "Vijay", "Rahul", "Suresh", "Ravi", "Mohan",
    "Kiran", "Deepak", "Sandeep", "Anil", "Manoj", "Ramesh", "Sanjay",
    "Nikhil", "Harish", "Prakash", "Anand", "Rohit", "Amit",
    "Sachin", "Varun", "Gaurav", "Sumit", "Tarun",
]

_FEMALE_FIRST_NAMES: list[str] = [
    "Priya", "Ananya", "Divya", "Sunita", "Kavya", "Lakshmi", "Rekha",
    "Meena", "Pooja", "Nisha", "Geeta", "Anjali", "Sushma", "Radha",
    "Smita", "Archana", "Neha", "Shweta", "Puja", "Asha",
    "Ritu", "Swati", "Sapna", "Usha", "Manju",
]

_LAST_NAMES: list[str] = [
    "Sharma", "Verma", "Singh", "Kumar", "Gupta", "Mehta", "Joshi",
    "Reddy", "Nair", "Iyer", "Pillai", "Menon", "Patel", "Shah",
    "Rao", "Mishra", "Tiwari", "Pandey", "Chauhan", "Yadav",
    "Bose", "Das", "Mukherjee", "Banerjee", "Chatterjee",
]


# ---------------------------------------------------------------------------
# Private helper utilities
# ---------------------------------------------------------------------------

def _indian_phone() -> str:
    """Generate a realistic Indian mobile number with +91 country code.

    Returns:
        Phone number string in the format +91XXXXXXXXXX (10 digits after +91).
    """
    prefix = random.choice(["6", "7", "8", "9"])
    digits = "".join(str(random.randint(0, 9)) for _ in range(9))
    return f"+91{prefix}{digits}"


def _indian_address() -> Address:
    """Generate a realistic Indian postal address.

    Returns:
        An Address instance with Indian city, state, and PIN code.
    """
    house = random.randint(1, 999)
    street_names = [
        "MG Road", "Gandhi Nagar", "Nehru Street", "Anna Salai",
        "Rajpath", "Park Street", "Linking Road", "Brigade Road",
        "Connaught Place", "Camac Street", "Sarojini Nagar",
        "Sector 14", "Sector 22", "Civil Lines", "Model Town",
    ]
    city, state, pin_prefix = random.choice(_CITIES)
    pin = f"{pin_prefix}{random.randint(100, 999):03d}"
    return Address(
        street=f"{house}, {random.choice(street_names)}",
        city=city,
        state=state,
        postal_code=pin,
        country="India",
    )


def _insurance_info() -> InsuranceInfo:
    """Generate a realistic Indian health insurance record.

    Returns:
        An InsuranceInfo instance with provider, policy number, and expiry.
    """
    provider = random.choice(_INSURANCE_PROVIDERS)
    year = random.randint(2020, 2023)
    seq = random.randint(1000000, 9999999)
    policy_num = f"{provider[:3].upper()}-{year}-{seq}"
    valid_until = date(
        random.randint(2025, 2027),
        random.randint(1, 12),
        random.randint(1, 28),
    )
    return InsuranceInfo(
        provider=provider,
        policy_number=policy_num,
        group_number=f"GRP{random.randint(100, 999)}" if random.random() < 0.5 else None,
        valid_until=valid_until,
    )


def _past_date(days_back_min: int = 30, days_back_max: int = 365) -> date:
    """Return a random past date within the given range.

    Args:
        days_back_min: Minimum days in the past.
        days_back_max: Maximum days in the past.

    Returns:
        A date object in the past.
    """
    offset = random.randint(days_back_min, days_back_max)
    return date.today() - timedelta(days=offset)


def _future_datetime(hours_ahead_min: int = 24, hours_ahead_max: int = 720) -> datetime:
    """Return a random future datetime within the given range.

    Args:
        hours_ahead_min: Minimum hours in the future.
        hours_ahead_max: Maximum hours in the future.

    Returns:
        A datetime object in the future (UTC), with time in working hours (9–17).
    """
    offset_hours = random.randint(hours_ahead_min, hours_ahead_max)
    base = datetime.utcnow() + timedelta(hours=offset_hours)
    # Pin to a working-hours slot
    base = base.replace(
        hour=random.choice([9, 10, 11, 14, 15, 16]),
        minute=random.choice([0, 15, 30, 45]),
        second=0,
        microsecond=0,
    )
    return base


def _past_datetime(days_back_min: int = 7, days_back_max: int = 365) -> datetime:
    """Return a random past datetime within the given range.

    Args:
        days_back_min: Minimum days in the past.
        days_back_max: Maximum days in the past.

    Returns:
        A datetime object in the past (UTC), with time in working hours (9–17).
    """
    offset = random.randint(days_back_min, days_back_max)
    base = datetime.utcnow() - timedelta(days=offset)
    base = base.replace(
        hour=random.choice([9, 10, 11, 14, 15, 16]),
        minute=random.choice([0, 15, 30, 45]),
        second=0,
        microsecond=0,
    )
    return base


# ---------------------------------------------------------------------------
# Data clearing
# ---------------------------------------------------------------------------

def clear_all_data(db: DatabaseConnection) -> None:
    """Wipe all 9 collections before seeding to ensure a clean state.

    This function drops all documents from every collection managed by this
    module. It is always called at the start of main() to prevent duplicates
    on repeated runs.

    Args:
        db: Active DatabaseConnection.

    Raises:
        RuntimeError: If any collection cannot be cleared.
    """
    collections = [
        "patients",
        "physicians",
        "departments",
        "visits",
        "visit_departments",
        "appointments",
        "referrals",
        "alerts",
        "audit_logs",
    ]
    print("Clearing existing data from all collections...")
    try:
        for col in collections:
            result = db.get_collection(col).delete_many({})
            print(f"  Cleared '{col}': {result.deleted_count} documents removed")
    except Exception as exc:
        raise RuntimeError(f"Failed to clear collection data: {exc}") from exc


# ---------------------------------------------------------------------------
# Department seeding
# ---------------------------------------------------------------------------

def seed_departments(db: DatabaseConnection) -> list[str]:
    """Insert the 5 fixed departments into the 'departments' collection.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of department_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting departments...")
    inserted: list[str] = []
    try:
        for dept_data in DEPARTMENTS:
            dept = Department(
                department_id=dept_data["department_id"],
                department_name=dept_data["department_name"],
                location=dept_data["location"],
            )
            db.get_collection("departments").insert_one(
                _serialize_doc(dept.model_dump())
            )
            inserted.append(dept.department_id)
            print(f"  + {dept.department_name} ({dept.department_id})")
    except Exception as exc:
        raise RuntimeError(f"Error seeding departments: {exc}") from exc
    return inserted


# ---------------------------------------------------------------------------
# Physician seeding
# ---------------------------------------------------------------------------

def seed_physicians(db: DatabaseConnection) -> list[str]:
    """Insert 10 physicians into the 'physicians' collection.

    Each physician is pre-assigned to one of the 5 departments.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of physician_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting physicians...")
    inserted: list[str] = []
    try:
        for phy_data in PHYSICIANS:
            phy = Physician(
                physician_id=phy_data["physician_id"],
                first_name=phy_data["first_name"],
                last_name=phy_data["last_name"],
                speciality=phy_data["speciality"],
                department_id=phy_data["department_id"],
                phone=phy_data["phone"],
                email=phy_data["email"],
            )
            db.get_collection("physicians").insert_one(
                _serialize_doc(phy.model_dump())
            )
            inserted.append(phy.physician_id)
            print(
                f"  + Dr. {phy.first_name} {phy.last_name}"
                f" — {phy.speciality} ({phy.physician_id})"
            )
    except Exception as exc:
        raise RuntimeError(f"Error seeding physicians: {exc}") from exc
    return inserted


# ---------------------------------------------------------------------------
# Patient seeding
# ---------------------------------------------------------------------------

def seed_patients(db: DatabaseConnection) -> list[str]:
    """Generate and insert 25 patients with realistic Indian demographics.

    Fires age_calculator_trigger and audit_log_trigger for every patient.
    Age range is 18–75 years. PAT-IDs are PAT-2024-001 through PAT-2024-025.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of patient_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting patients...")
    inserted: list[str] = []

    # Pre-defined patient roster for reproducibility and realism
    patient_roster: list[tuple[str, Gender, int, int]] = [
        # (first_name, gender, age_min, age_max)
        ("Aarav", Gender.MALE, 28, 35),
        ("Priya", Gender.FEMALE, 22, 30),
        ("Ramesh", Gender.MALE, 50, 60),
        ("Sunita", Gender.FEMALE, 35, 45),
        ("Vijay", Gender.MALE, 40, 55),
        ("Kavya", Gender.FEMALE, 18, 28),
        ("Mohan", Gender.MALE, 60, 70),
        ("Rekha", Gender.FEMALE, 45, 55),
        ("Arjun", Gender.MALE, 25, 35),
        ("Divya", Gender.FEMALE, 30, 40),
        ("Suresh", Gender.MALE, 55, 65),
        ("Pooja", Gender.FEMALE, 20, 30),
        ("Sandeep", Gender.MALE, 38, 48),
        ("Lakshmi", Gender.FEMALE, 50, 65),
        ("Kiran", Gender.MALE, 42, 52),
        ("Meena", Gender.FEMALE, 25, 35),
        ("Anil", Gender.MALE, 65, 75),
        ("Anjali", Gender.FEMALE, 18, 25),
        ("Rohit", Gender.MALE, 30, 42),
        ("Geeta", Gender.FEMALE, 55, 70),
        ("Deepak", Gender.MALE, 35, 50),
        ("Nisha", Gender.FEMALE, 28, 38),
        ("Manoj", Gender.MALE, 48, 60),
        ("Smita", Gender.FEMALE, 40, 50),
        ("Sachin", Gender.MALE, 22, 32),
    ]

    last_names_pool = _LAST_NAMES[:]
    random.shuffle(last_names_pool)

    try:
        for idx, (first_name, gender, age_min, age_max) in enumerate(patient_roster, start=1):
            patient_id = f"PAT-{_SEED_YEAR}-{idx:03d}"
            last_name = last_names_pool[idx % len(last_names_pool)]

            age_years = random.randint(age_min, age_max)
            today = date.today()
            dob = date(
                today.year - age_years,
                random.randint(1, 12),
                random.randint(1, 28),
            )

            blood_group = random.choice(list(BloodGroup))
            email = (
                f"{first_name.lower()}.{last_name.lower()}"
                f"{random.randint(10, 99)}@gmail.com"
            )

            allergies: list[str] = []
            if random.random() < 0.35:
                allergies = random.sample(
                    ["Penicillin", "Sulfa drugs", "Aspirin", "NSAIDs",
                     "Iodine contrast", "Pollen", "Dust mites"],
                    k=random.randint(1, 2),
                )

            chronic_conditions: list[str] = []
            if age_years > 40 and random.random() < 0.5:
                chronic_conditions = random.sample(
                    ["Hypertension", "Type 2 Diabetes", "Hypothyroidism",
                     "Asthma", "COPD", "Chronic kidney disease stage II"],
                    k=random.randint(1, 2),
                )

            patient = Patient(
                patient_id=patient_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                gender=gender,
                phone=_indian_phone(),
                email=email,
                address=_indian_address(),
                insurance=_insurance_info() if random.random() < 0.85 else None,
                blood_group=blood_group,
                allergies=allergies,
                chronic_conditions=chronic_conditions,
            )

            doc = _serialize_doc(patient.model_dump())

            # TRIGGER: age_calculator_trigger — stamp computed age before insert
            doc["age"] = age_calculator_trigger(patient.date_of_birth)

            db.get_collection("patients").insert_one(doc)

            # TRIGGER: audit_log_trigger — log the CREATE action
            audit_log_trigger(
                db,
                patient_id=patient_id,
                action=AuditAction.CREATE,
                collection_name="patients",
                document_id=patient_id,
                performed_by="seed_data_script",
                performed_by_role="system",
            )

            inserted.append(patient_id)
            print(
                f"  + [{patient_id}] {first_name} {last_name}"
                f" — Age {doc['age']}, {gender.value.title()}"
            )

    except Exception as exc:
        raise RuntimeError(f"Error seeding patients: {exc}") from exc

    return inserted


# ---------------------------------------------------------------------------
# Visit seeding
# ---------------------------------------------------------------------------

def seed_visits(
    db: DatabaseConnection,
    patient_ids: list[str],
) -> list[str]:
    """Generate and insert 3–5 visits per patient (~100 visits total).

    Each visit is linked to a patient and a physician from a matching
    department. Fires audit_log_trigger, visit_frequency_alert_trigger,
    and abnormal_vitals_trigger for each visit.

    Args:
        db: Active DatabaseConnection.
        patient_ids: List of patient_id strings to create visits for.

    Returns:
        List of visit_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting visits...")
    inserted: list[str] = []
    visit_counter = 1

    try:
        for patient_id in patient_ids:
            num_visits = random.randint(3, 5)
            assigned_dept = random.choice(_ALL_DEPT_IDS)
            assigned_physician = random.choice(_DEPT_PHYSICIANS[assigned_dept])

            for _ in range(num_visits):
                visit_id = f"VIS-{_SEED_YEAR}-{visit_counter:03d}"
                visit_counter += 1

                visit_date = _past_date(days_back_min=1, days_back_max=365)
                diagnosis = random.choice(_DIAGNOSES[assigned_dept])
                reason = random.choice(_VISIT_REASONS)
                status = random.choices(
                    [VisitStatus.COMPLETED, VisitStatus.DISCHARGED, VisitStatus.ACTIVE],
                    weights=[60, 30, 10],
                )[0]

                visit = Visit(
                    visit_id=visit_id,
                    patient_id=patient_id,
                    physician_id=assigned_physician,
                    visit_date=visit_date,
                    reason=reason,
                    diagnosis=diagnosis,
                    status=status,
                )

                doc = _serialize_doc(visit.model_dump())
                db.get_collection("visits").insert_one(doc)

                # TRIGGER: audit_log_trigger
                audit_log_trigger(
                    db,
                    patient_id=patient_id,
                    action=AuditAction.CREATE,
                    collection_name="visits",
                    document_id=visit_id,
                    performed_by="seed_data_script",
                    performed_by_role="doctor",
                )

                # TRIGGER: visit_frequency_alert_trigger
                visit_frequency_alert_trigger(db, patient_id, visit_id)

                inserted.append(visit_id)

        print(f"  Inserted {len(inserted)} visits across {len(patient_ids)} patients")

    except Exception as exc:
        raise RuntimeError(f"Error seeding visits: {exc}") from exc

    return inserted


# ---------------------------------------------------------------------------
# VisitDepartment junction seeding
# ---------------------------------------------------------------------------

def seed_visit_departments(
    db: DatabaseConnection,
    visit_ids: list[str],
) -> int:
    """Create 1–2 VisitDepartment junction records per visit.

    Resolves the Visit ↔ Department M-to-N relationship defined in the ER diagram.

    Args:
        db: Active DatabaseConnection.
        visit_ids: List of visit_id strings that have already been inserted.

    Returns:
        Total number of junction records inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting visit_department junction records...")
    total = 0
    seen: set[tuple[str, str]] = set()

    try:
        for visit_id in visit_ids:
            num_depts = random.randint(1, 2)
            depts = random.sample(_ALL_DEPT_IDS, k=num_depts)

            for dept_id in depts:
                key = (visit_id, dept_id)
                if key in seen:
                    continue
                seen.add(key)

                junc = VisitDepartment(visit_id=visit_id, department_id=dept_id)
                db.get_collection("visit_departments").insert_one(
                    _serialize_doc(junc.model_dump())
                )
                total += 1

        print(f"  Inserted {total} visit_department links for {len(visit_ids)} visits")

    except Exception as exc:
        raise RuntimeError(f"Error seeding visit_departments: {exc}") from exc

    return total


# ---------------------------------------------------------------------------
# Appointment seeding
# ---------------------------------------------------------------------------

def seed_appointments(
    db: DatabaseConnection,
    patient_ids: list[str],
) -> list[str]:
    """Generate and insert 2–3 appointments per patient (~60 appointments total).

    Mix of statuses: scheduled (future), completed (past), confirmed (future),
    and cancelled (past). Fires audit_log_trigger on each insert.
    No conflict-checking is applied during seeding — appointments are spread
    across different time slots and physicians.

    Args:
        db: Active DatabaseConnection.
        patient_ids: List of patient_id strings to create appointments for.

    Returns:
        List of appointment_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting appointments...")
    inserted: list[str] = []
    appt_counter = 1

    # Track (physician_id, slot) pairs used so far to avoid conflicts in seed data
    used_slots: set[tuple[str, datetime]] = set()

    try:
        for patient_id in patient_ids:
            num_appts = random.randint(2, 3)
            physician_id = random.choice(_ALL_PHY_IDS)

            for _ in range(num_appts):
                appt_id = f"APT-{_SEED_YEAR}-{appt_counter:03d}"
                appt_counter += 1

                status = random.choices(
                    [
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.COMPLETED,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.CANCELLED,
                        AppointmentStatus.NO_SHOW,
                    ],
                    weights=[35, 30, 20, 10, 5],
                )[0]

                # Future slots for scheduled/confirmed, past for others
                if status in (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED):
                    appt_dt = _future_datetime(hours_ahead_min=48, hours_ahead_max=720)
                else:
                    appt_dt = _past_datetime(days_back_min=7, days_back_max=300)

                # Shift slot slightly if a collision exists for this physician
                attempts = 0
                while (physician_id, appt_dt) in used_slots and attempts < 10:
                    appt_dt = appt_dt + timedelta(hours=1)
                    attempts += 1
                used_slots.add((physician_id, appt_dt))

                cancellation_reason: Optional[str] = None
                if status == AppointmentStatus.CANCELLED:
                    cancellation_reason = random.choice(_CANCELLATION_REASONS)

                appt = Appointment(
                    appointment_id=appt_id,
                    patient_id=patient_id,
                    physician_id=physician_id,
                    appointment_date_and_time=appt_dt,
                    reason=random.choice(_APPOINTMENT_REASONS),
                    status=status,
                    cancellation_reason=cancellation_reason,
                )

                db.get_collection("appointments").insert_one(
                    _serialize_doc(appt.model_dump())
                )

                # TRIGGER: audit_log_trigger
                audit_log_trigger(
                    db,
                    patient_id=patient_id,
                    action=AuditAction.CREATE,
                    collection_name="appointments",
                    document_id=appt_id,
                    performed_by="seed_data_script",
                    performed_by_role="receptionist",
                )

                inserted.append(appt_id)

        print(f"  Inserted {len(inserted)} appointments across {len(patient_ids)} patients")

    except Exception as exc:
        raise RuntimeError(f"Error seeding appointments: {exc}") from exc

    return inserted


# ---------------------------------------------------------------------------
# Referral seeding
# ---------------------------------------------------------------------------

def seed_referrals(
    db: DatabaseConnection,
    patient_ids: list[str],
) -> list[str]:
    """Generate and insert 15–20 referrals linking patients across specialties.

    Each referral has distinct source and target physicians (inter-department
    referrals). Fires audit_log_trigger on each insert.

    Args:
        db: Active DatabaseConnection.
        patient_ids: List of patient_id strings eligible for referrals.

    Returns:
        List of referral_id strings that were inserted.

    Raises:
        RuntimeError: If insertion fails.
    """
    print("\nInserting referrals...")
    inserted: list[str] = []
    num_referrals = random.randint(15, 20)
    # Pick a random subset of patients for referrals (some patients get referred, not all)
    referred_patients = random.sample(patient_ids, k=min(num_referrals, len(patient_ids)))

    try:
        for idx, patient_id in enumerate(referred_patients, start=1):
            referral_id = f"REF-{_SEED_YEAR}-{idx:03d}"

            # Pick two distinct physicians from different departments
            source_dept, target_dept = random.sample(_ALL_DEPT_IDS, k=2)
            source_physician_id = random.choice(_DEPT_PHYSICIANS[source_dept])
            target_physician_id = random.choice(_DEPT_PHYSICIANS[target_dept])

            referral_date = datetime.utcnow() - timedelta(
                days=random.randint(1, 180)
            )

            status = random.choices(
                [
                    ReferralStatus.PENDING,
                    ReferralStatus.ACCEPTED,
                    ReferralStatus.COMPLETED,
                    ReferralStatus.REJECTED,
                ],
                weights=[30, 35, 25, 10],
            )[0]

            referral = Referral(
                referral_id=referral_id,
                patient_id=patient_id,
                source_physician_id=source_physician_id,
                target_physician_id=target_physician_id,
                referral_date=referral_date,
                reason=random.choice(_REFERRAL_REASONS),
                status=status,
            )

            db.get_collection("referrals").insert_one(
                _serialize_doc(referral.model_dump())
            )

            # TRIGGER: audit_log_trigger
            audit_log_trigger(
                db,
                patient_id=patient_id,
                action=AuditAction.CREATE,
                collection_name="referrals",
                document_id=referral_id,
                performed_by="seed_data_script",
                performed_by_role="doctor",
            )

            inserted.append(referral_id)

        print(f"  Inserted {len(inserted)} referrals")

    except Exception as exc:
        raise RuntimeError(f"Error seeding referrals: {exc}") from exc

    return inserted


# ---------------------------------------------------------------------------
# Summary reporting
# ---------------------------------------------------------------------------

def print_collection_counts(db: DatabaseConnection) -> None:
    """Print the total document count for every collection in the module.

    Args:
        db: Active DatabaseConnection.
    """
    collections = [
        "departments",
        "physicians",
        "patients",
        "visits",
        "visit_departments",
        "appointments",
        "referrals",
        "alerts",
        "audit_logs",
    ]
    print("\n" + "=" * 50)
    print("  COLLECTION COUNTS AFTER SEEDING")
    print("=" * 50)
    try:
        total = 0
        for col in collections:
            count = db.get_collection(col).count_documents({})
            total += count
            print(f"  {col:<22} : {count:>5} documents")
        print("-" * 50)
        print(f"  {'TOTAL':<22} : {total:>5} documents")
        print("=" * 50)
    except Exception as exc:
        print(f"[Warning] Could not fetch collection counts: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full seed pipeline in FK dependency order.

    Steps:
      1. Connect to MongoDB Atlas (reads MONGODB_URI from .env)
      2. Clear all existing documents
      3. Seed departments → physicians → patients → visits →
         visit_departments → appointments → referrals
      4. Print final collection counts

    Raises:
        SystemExit: With code 1 if the database connection fails.
    """
    print("=" * 50)
    print("  Patient Demographics — Seed Data Generator")
    print("=" * 50)

    db = DatabaseConnection()
    try:
        db.connect()
    except Exception as exc:
        print(f"\n[ERROR] Could not connect to MongoDB: {exc}")
        print("Make sure MONGODB_URI is set in your .env file.")
        sys.exit(1)

    try:
        clear_all_data(db)

        dept_ids = seed_departments(db)
        seed_physicians(db)
        patient_ids = seed_patients(db)
        visit_ids = seed_visits(db, patient_ids)
        seed_visit_departments(db, visit_ids)
        seed_appointments(db, patient_ids)
        seed_referrals(db, patient_ids)

        print_collection_counts(db)
        print("\nSeeding complete.\n")

    except RuntimeError as exc:
        print(f"\n[ERROR] Seeding failed: {exc}")
        sys.exit(1)
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
