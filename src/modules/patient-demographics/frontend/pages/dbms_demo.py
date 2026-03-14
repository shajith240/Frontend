"""DBMS Concepts demonstration page — the professor evaluates this directly.

Six clearly labeled sections demonstrate every core DBMS concept implemented
in Module 1:
  1. Schema & Normalization
  2. Indexes & Constraints
  3. Live Query Execution (all 10 aggregation pipelines)
  4. Trigger Demonstrations (all 5 triggers with live fire)
  5. Stored Procedures (3 procedure simulations with live execution)
  6. Audit Log Viewer (real-time proof that triggers are working)
"""

import inspect
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import (
    create_appointment,
    create_patient,
    create_visit,
    get_patient_by_id,
    update_patient,
)
from backend.database import DatabaseConnection
from backend.models import (
    Appointment,
    AppointmentStatus,
    AuditAction,
    Gender,
    Patient,
    Visit,
    VisitStatus,
    VitalSigns,
)
from backend.triggers import (
    abnormal_vitals_trigger,
    age_calculator_trigger,
    appointment_conflict_trigger,
    audit_log_trigger,
    visit_frequency_alert_trigger,
)
from database.queries.aggregations import (
    get_patients_with_visit_count,
    get_visit_frequency_by_month,
    get_top_diagnoses,
    get_patients_per_department,
    get_patients_with_pending_appointments,
    get_referral_network_summary,
    get_high_frequency_visitors,
    get_patient_full_profile,
    get_physician_workload,
    get_department_statistics,
    run_all_queries,
)

load_dotenv()


# ============================================================================
# Section 1 — Schema & Normalization
# ============================================================================

def _render_schema_section() -> None:
    """Render Section 1: Schema & Normalization with collection details and ER relationships."""
    st.subheader("1. Schema & Normalization")
    st.info(
        "Our database is normalized into **9 separate collections**, each storing "
        "a single entity type. This eliminates data redundancy and ensures referential "
        "integrity — the same principles behind 3NF in relational databases."
    )

    # Collection overview table
    collections_data = [
        {
            "Collection": "patients",
            "Primary Key": "patient_id (PAT-YYYY-NNN)",
            "Key Fields": "first_name, last_name, date_of_birth, gender, phone, email, address, insurance",
            "Purpose": "Core patient demographics — the central entity in the ER diagram",
            "Normalization": "1NF: atomic values; 2NF: all fields depend on patient_id; 3NF: no transitive deps",
        },
        {
            "Collection": "physicians",
            "Primary Key": "physician_id",
            "Key Fields": "first_name, last_name, speciality, department_id (FK)",
            "Purpose": "Physician registry with department assignment",
            "Normalization": "department_id is a FK — department details stored separately to avoid redundancy",
        },
        {
            "Collection": "departments",
            "Primary Key": "department_id",
            "Key Fields": "department_name, location",
            "Purpose": "Hospital department master data",
            "Normalization": "Separate collection prevents repeating department info in every physician record",
        },
        {
            "Collection": "visits",
            "Primary Key": "visit_id",
            "Key Fields": "visit_date, reason, diagnosis, status, patient_id (FK), physician_id (FK)",
            "Purpose": "Clinical visit records linking patient to physician",
            "Normalization": "FKs to patients and physicians — no embedded patient/physician data",
        },
        {
            "Collection": "appointments",
            "Primary Key": "appointment_id",
            "Key Fields": "appointment_date_and_time, reason, status, patient_id (FK), physician_id (FK)",
            "Purpose": "Scheduled appointments with conflict detection",
            "Normalization": "Same FK pattern as visits — patient and physician stored by reference",
        },
        {
            "Collection": "referrals",
            "Primary Key": "referral_id",
            "Key Fields": "referral_date, reason, status, patient_id (FK), source_physician_id (FK), target_physician_id (FK)",
            "Purpose": "Inter-physician referral tracking with two physician FKs",
            "Normalization": "Two FK references to physicians collection — no data duplication",
        },
        {
            "Collection": "visit_departments",
            "Primary Key": "(visit_id, department_id) composite",
            "Key Fields": "visit_id (FK), department_id (FK)",
            "Purpose": "Junction table resolving the Visit-Department M-to-N relationship",
            "Normalization": "Classic junction table pattern — eliminates M:N without data loss",
        },
        {
            "Collection": "alerts",
            "Primary Key": "alert_id",
            "Key Fields": "patient_id (FK), alert_type, severity, title, message, is_acknowledged",
            "Purpose": "System-generated clinical alerts from triggers",
            "Normalization": "Separate from visits/patients to track alert lifecycle independently",
        },
        {
            "Collection": "audit_logs",
            "Primary Key": "log_id",
            "Key Fields": "patient_id, action, collection_name, document_id, performed_by, changes",
            "Purpose": "Immutable audit trail for all CRUD operations",
            "Normalization": "Append-only collection — never updated, ensures audit integrity",
        },
    ]
    st.dataframe(collections_data, use_container_width=True, hide_index=True)

    # Junction table explanation
    with st.expander("VisitDepartment Junction Table — Resolving M-to-N"):
        st.markdown(
            "**Problem:** A single visit can involve multiple departments "
            "(e.g. Emergency + Radiology), and a department serves many visits. "
            "This is a classic Many-to-Many relationship."
        )

        st.code(
            """-- SQL equivalent of the junction table
CREATE TABLE visit_departments (
    visit_id       VARCHAR(20)  REFERENCES visits(visit_id),
    department_id  VARCHAR(20)  REFERENCES departments(department_id),
    created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (visit_id, department_id)
);

-- MongoDB equivalent
db.visit_departments.insertOne({
    visit_id: "VIS-2024-001",
    department_id: "DEP-2024-003",
    created_at: ISODate()
})""",
            language="sql",
        )

        st.success(
            "By introducing the junction table, the M:N relationship between "
            "Visit and Department is decomposed into two 1:N relationships, "
            "satisfying BCNF requirements."
        )

    # ER relationships table
    with st.expander("ER Diagram Relationships"):
        relationships = [
            {"Entity A": "Patient", "Relationship": "1 ──< N", "Entity B": "Visit", "FK Location": "visits.patient_id", "SQL": "FOREIGN KEY (patient_id) REFERENCES patients(patient_id)"},
            {"Entity A": "Patient", "Relationship": "1 ──< N", "Entity B": "Appointment", "FK Location": "appointments.patient_id", "SQL": "FOREIGN KEY (patient_id) REFERENCES patients(patient_id)"},
            {"Entity A": "Patient", "Relationship": "1 ──< N", "Entity B": "Referral", "FK Location": "referrals.patient_id", "SQL": "FOREIGN KEY (patient_id) REFERENCES patients(patient_id)"},
            {"Entity A": "Physician", "Relationship": "1 ──< N", "Entity B": "Visit", "FK Location": "visits.physician_id", "SQL": "FOREIGN KEY (physician_id) REFERENCES physicians(physician_id)"},
            {"Entity A": "Physician", "Relationship": "1 ──< N", "Entity B": "Appointment", "FK Location": "appointments.physician_id", "SQL": "FOREIGN KEY (physician_id) REFERENCES physicians(physician_id)"},
            {"Entity A": "Department", "Relationship": "1 ──< N", "Entity B": "Physician", "FK Location": "physicians.department_id", "SQL": "FOREIGN KEY (department_id) REFERENCES departments(department_id)"},
            {"Entity A": "Visit", "Relationship": "M ──>< N", "Entity B": "Department", "FK Location": "visit_departments (junction)", "SQL": "Decomposed via junction table into two 1:N"},
            {"Entity A": "Physician (source)", "Relationship": "1 ──< N", "Entity B": "Referral", "FK Location": "referrals.source_physician_id", "SQL": "FOREIGN KEY (source_physician_id) REFERENCES physicians(physician_id)"},
            {"Entity A": "Physician (target)", "Relationship": "1 ──< N", "Entity B": "Referral", "FK Location": "referrals.target_physician_id", "SQL": "FOREIGN KEY (target_physician_id) REFERENCES physicians(physician_id)"},
        ]
        st.dataframe(relationships, use_container_width=True, hide_index=True)


# ============================================================================
# Section 2 — Indexes & Constraints
# ============================================================================

def _render_indexes_section(db: DatabaseConnection) -> None:
    """Render Section 2: Indexes & Constraints with live index info and Pydantic rules.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("2. Indexes & Constraints")

    # Live index information
    st.markdown("**Indexes on `patients` collection**")
    st.info(
        "Indexes speed up queries the same way a SQL CREATE INDEX does. "
        "We create three indexes on the patients collection at connection time."
    )

    indexes_data = [
        {
            "Index Name": "patient_id_1",
            "Field(s)": "patient_id",
            "Type": "UNIQUE, ASCENDING",
            "SQL Equivalent": "CREATE UNIQUE INDEX idx_patient_id ON patients(patient_id)",
            "Purpose": "Primary key enforcement — prevents duplicate patient IDs",
        },
        {
            "Index Name": "name_1",
            "Field(s)": "name",
            "Type": "ASCENDING",
            "SQL Equivalent": "CREATE INDEX idx_name ON patients(name)",
            "Purpose": "Accelerates patient name search queries",
        },
        {
            "Index Name": "date_of_birth_1",
            "Field(s)": "date_of_birth",
            "Type": "ASCENDING",
            "SQL Equivalent": "CREATE INDEX idx_dob ON patients(date_of_birth)",
            "Purpose": "Speeds up age-range and DOB-based queries",
        },
    ]
    st.dataframe(indexes_data, use_container_width=True, hide_index=True)

    # Try to show live indexes from MongoDB
    with st.expander("Live Index Info from MongoDB"):
        try:
            live_indexes = list(db.get_collection("patients").list_indexes())
            for idx in live_indexes:
                idx_name = idx.get("name", "unknown")
                idx_key = dict(idx.get("key", {}))
                idx_unique = idx.get("unique", False)
                st.code(
                    f"Index: {idx_name}\n"
                    f"  Key:    {idx_key}\n"
                    f"  Unique: {idx_unique}",
                    language="text",
                )
        except Exception as exc:
            st.warning(f"Could not fetch live indexes: {exc}")

    st.divider()

    # Pydantic validation constraints
    st.markdown("**Pydantic Validation Constraints (equivalent to SQL CHECK / NOT NULL)**")

    constraints_data = [
        {
            "Model": "Patient",
            "Field": "patient_id",
            "Constraint": "Regex: PAT-\\d{4}-\\d{3}",
            "SQL Equivalent": "CHECK (patient_id ~ '^PAT-\\d{4}-\\d{3}$')",
            "Enforcement": "@field_validator with regex match",
        },
        {
            "Model": "Patient",
            "Field": "first_name",
            "Constraint": "min_length=1, NOT NULL",
            "SQL Equivalent": "VARCHAR NOT NULL CHECK (LENGTH(first_name) >= 1)",
            "Enforcement": "Pydantic Field(min_length=1)",
        },
        {
            "Model": "Patient",
            "Field": "date_of_birth",
            "Constraint": "Cannot be in the future",
            "SQL Equivalent": "CHECK (date_of_birth <= CURRENT_DATE)",
            "Enforcement": "@field_validator — dob_not_future",
        },
        {
            "Model": "Patient",
            "Field": "gender",
            "Constraint": "Enum: male, female, other, prefer_not_to_say",
            "SQL Equivalent": "CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say'))",
            "Enforcement": "Pydantic Gender(str, Enum)",
        },
        {
            "Model": "Patient",
            "Field": "age",
            "Constraint": "0 <= age <= 150",
            "SQL Equivalent": "CHECK (age BETWEEN 0 AND 150)",
            "Enforcement": "Field(ge=0, le=150) — auto-computed by trigger",
        },
        {
            "Model": "VitalSigns",
            "Field": "blood_pressure_systolic",
            "Constraint": "50 <= value <= 300",
            "SQL Equivalent": "CHECK (bp_systolic BETWEEN 50 AND 300)",
            "Enforcement": "Field(ge=50, le=300)",
        },
        {
            "Model": "VitalSigns",
            "Field": "oxygen_saturation",
            "Constraint": "50.0 <= value <= 100.0",
            "SQL Equivalent": "CHECK (spo2 BETWEEN 50.0 AND 100.0)",
            "Enforcement": "Field(ge=50.0, le=100.0)",
        },
        {
            "Model": "Appointment",
            "Field": "status + cancellation_reason",
            "Constraint": "cancellation_reason required when status='cancelled'",
            "SQL Equivalent": "CHECK (status != 'cancelled' OR cancellation_reason IS NOT NULL)",
            "Enforcement": "@model_validator — cross-field validation",
        },
        {
            "Model": "Visit",
            "Field": "follow_up_date",
            "Constraint": "Cannot be in the past",
            "SQL Equivalent": "CHECK (follow_up_date >= CURRENT_DATE)",
            "Enforcement": "@field_validator — follow_up_not_before_visit",
        },
        {
            "Model": "Alert",
            "Field": "is_acknowledged + acknowledged_by",
            "Constraint": "acknowledged_by required when is_acknowledged=True",
            "SQL Equivalent": "CHECK (NOT is_acknowledged OR acknowledged_by IS NOT NULL)",
            "Enforcement": "@model_validator — acknowledged_fields_consistent",
        },
    ]
    st.dataframe(constraints_data, use_container_width=True, hide_index=True)


# ============================================================================
# Section 3 — Live Query Execution
# ============================================================================

# Query metadata — maps function name to display info
_QUERY_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "Patients with Visit Count",
        "function": get_patients_with_visit_count,
        "sql": "SELECT p.patient_id, p.first_name, p.last_name, COUNT(v.visit_id) AS visit_count\nFROM patients p LEFT JOIN visits v ON p.patient_id = v.patient_id\nGROUP BY p.patient_id ORDER BY visit_count DESC",
        "key_ops": "$lookup (LEFT JOIN), $addFields + $size (COUNT), $sort (ORDER BY)",
        "args": lambda db: (db,),
    },
    {
        "name": "Visit Frequency by Month",
        "function": get_visit_frequency_by_month,
        "sql": "SELECT YEAR(visit_date) AS year, MONTH(visit_date) AS month, COUNT(*) AS visit_count\nFROM visits GROUP BY YEAR(visit_date), MONTH(visit_date)\nORDER BY year, month",
        "key_ops": "$addFields + $year/$month, $group (GROUP BY), $sort",
        "args": lambda db: (db,),
    },
    {
        "name": "Top Diagnoses",
        "function": get_top_diagnoses,
        "sql": "SELECT diagnosis, COUNT(*) AS frequency FROM visits\nWHERE diagnosis IS NOT NULL\nGROUP BY diagnosis ORDER BY frequency DESC LIMIT 10",
        "key_ops": "$match (WHERE), $group (GROUP BY + COUNT), $sort, $limit",
        "args": lambda db: (db,),
    },
    {
        "name": "Patients per Department",
        "function": get_patients_per_department,
        "sql": "SELECT d.department_name, COUNT(DISTINCT v.patient_id) AS unique_patients\nFROM departments d LEFT JOIN visit_departments vd ON d.department_id = vd.department_id\nLEFT JOIN visits v ON vd.visit_id = v.visit_id\nGROUP BY d.department_id",
        "key_ops": "$lookup (double JOIN via junction), $reduce + $setUnion (COUNT DISTINCT)",
        "args": lambda db: (db,),
    },
    {
        "name": "Patients with Pending Appointments",
        "function": get_patients_with_pending_appointments,
        "sql": "SELECT p.*, a.*, ph.first_name || ' ' || ph.last_name AS physician_name\nFROM appointments a JOIN patients p ON a.patient_id = p.patient_id\nJOIN physicians ph ON a.physician_id = ph.physician_id\nWHERE a.status IN ('scheduled', 'confirmed')",
        "key_ops": "$match (WHERE IN), $lookup x2 (double JOIN), $unwind, $concat",
        "args": lambda db: (db,),
    },
    {
        "name": "Referral Network Summary",
        "function": get_referral_network_summary,
        "sql": "SELECT sp.name AS source, tp.name AS target, COUNT(*) AS referral_count\nFROM referrals r JOIN physicians sp ON r.source_physician_id = sp.physician_id\nJOIN physicians tp ON r.target_physician_id = tp.physician_id\nGROUP BY r.source_physician_id, r.target_physician_id",
        "key_ops": "$group (composite _id), $lookup x2 (self-join on physicians), $concat",
        "args": lambda db: (db,),
    },
    {
        "name": "High Frequency Visitors",
        "function": get_high_frequency_visitors,
        "sql": "SELECT p.patient_id, COUNT(v.visit_id) AS visit_count\nFROM visits v JOIN patients p ON v.patient_id = p.patient_id\nWHERE v.visit_date >= NOW() - INTERVAL 30 DAY\nGROUP BY v.patient_id HAVING COUNT(*) >= 3",
        "key_ops": "$match (WHERE date), $group + $match (GROUP BY + HAVING), $lookup",
        "args": lambda db: (db,),
    },
    {
        "name": "Patient Full Profile",
        "function": get_patient_full_profile,
        "sql": "SELECT p.*, v.*, a.*, r.*, d.department_name\nFROM patients p LEFT JOIN visits v ... LEFT JOIN appointments a ...\nLEFT JOIN referrals r ... LEFT JOIN visit_departments vd ...\nLEFT JOIN departments d ... WHERE p.patient_id = :id",
        "key_ops": "Nested pipeline $lookup x5 (6-table JOIN in single pass), $unwind",
        "args": lambda db: (db, _get_sample_patient_id(db)),
    },
    {
        "name": "Physician Workload",
        "function": get_physician_workload,
        "sql": "SELECT ph.physician_id, ph.name, COALESCE(v.cnt, 0) + COALESCE(a.cnt, 0) AS workload\nFROM physicians ph LEFT JOIN (SELECT physician_id, COUNT(*) cnt FROM visits GROUP BY physician_id) v ...\nLEFT JOIN (SELECT physician_id, COUNT(*) cnt FROM appointments GROUP BY physician_id) a ...",
        "key_ops": "$lookup with pipeline (subquery JOINs), $ifNull (COALESCE), $add",
        "args": lambda db: (db,),
    },
    {
        "name": "Department Statistics",
        "function": get_department_statistics,
        "sql": "SELECT d.department_name, COUNT(vd.visit_id) AS total_visits,\nCOUNT(DISTINCT v.patient_id) AS unique_patients,\n(SELECT TOP 1 diagnosis ...) AS top_diagnosis\nFROM departments d LEFT JOIN visit_departments vd ...\nLEFT JOIN visits v ... GROUP BY d.department_id",
        "key_ops": "Double $lookup (junction), nested pipeline (correlated subquery), $reduce (DISTINCT)",
        "args": lambda db: (db,),
    },
]


def _get_sample_patient_id(db: DatabaseConnection) -> str:
    """Fetch the first available patient_id for demo queries.

    Args:
        db: Active DatabaseConnection.

    Returns:
        A patient_id string, defaulting to PAT-2024-001 if none found.
    """
    try:
        first = db.get_collection("patients").find_one({}, {"patient_id": 1})
        if first:
            return first["patient_id"]
    except Exception:
        pass
    return "PAT-2024-001"


def _render_queries_section(db: DatabaseConnection) -> None:
    """Render Section 3: Live Query Execution with all 10 aggregation pipelines.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("3. Live Query Execution")
    st.info(
        "All 10 aggregation pipelines are MongoDB equivalents of SQL queries. "
        "Each uses `$lookup` for JOINs, `$group` for GROUP BY, `$sort` for "
        "ORDER BY, and `$match` for WHERE / HAVING clauses."
    )

    # Run All Queries button with timing
    if st.button("Run All 10 Queries", type="primary", use_container_width=True):
        start = time.time()
        try:
            all_results = run_all_queries(db)
            elapsed = time.time() - start
            st.success(f"All 10 queries executed in **{elapsed:.2f}s**")
            st.session_state["all_query_results"] = all_results
            st.session_state["all_query_time"] = elapsed
        except Exception as exc:
            st.error(f"Error running queries: {exc}")

    # Show cached results if available
    if "all_query_results" in st.session_state:
        elapsed = st.session_state.get("all_query_time", 0)
        st.caption(f"Last run: {elapsed:.2f}s total")

    st.divider()

    # Individual query expanders
    for idx, qinfo in enumerate(_QUERY_REGISTRY, 1):
        with st.expander(f"Query {idx}: {qinfo['name']}"):
            # SQL equivalent
            st.markdown("**SQL Equivalent:**")
            st.code(qinfo["sql"], language="sql")

            # Key MongoDB operations used
            st.markdown(f"**MongoDB Operations:** `{qinfo['key_ops']}`")

            # Show the Python function source
            with st.expander("View Python Pipeline Code"):
                try:
                    source = inspect.getsource(qinfo["function"])
                    st.code(source, language="python")
                except Exception:
                    st.caption("Source not available at runtime.")

            # Run individual query
            if st.button(f"Run Query {idx}", key=f"run_q{idx}"):
                try:
                    q_start = time.time()
                    args = qinfo["args"](db)
                    result = qinfo["function"](*args)
                    q_elapsed = time.time() - q_start

                    st.success(f"Returned **{len(result) if isinstance(result, list) else 1}** rows in {q_elapsed:.3f}s")

                    if isinstance(result, dict):
                        st.json(result)
                    elif isinstance(result, list) and result:
                        st.dataframe(result, use_container_width=True, hide_index=True)
                    else:
                        st.info("Query returned no results — seed data may not be loaded.")
                except Exception as exc:
                    st.error(f"Query failed: {exc}")


# ============================================================================
# Section 4 — Trigger Demonstrations
# ============================================================================

_TRIGGER_INFO: list[dict[str, str]] = [
    {
        "name": "audit_log_trigger",
        "fires": "AFTER INSERT / UPDATE / DELETE on all collections",
        "description": "Writes an immutable audit row to audit_logs every time patient data is created, read, updated, or deleted. Captures who did what, when, and the before/after diff for updates.",
        "sql": """CREATE TRIGGER trg_audit_log
AFTER INSERT OR UPDATE OR DELETE ON patients
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (log_id, patient_id, action, collection_name,
                           document_id, performed_by, changes, timestamp)
    VALUES (gen_id(), :patient_id, :action, 'patients',
            :doc_id, :user, :diff, CURRENT_TIMESTAMP);
END;""",
    },
    {
        "name": "age_calculator_trigger",
        "fires": "BEFORE INSERT on patients",
        "description": "Computes the patient's age in whole years from date_of_birth and stamps it into the document before insertion. Recomputes on DOB update.",
        "sql": """CREATE TRIGGER trg_age_calculator
BEFORE INSERT ON patients
FOR EACH ROW
BEGIN
    SET NEW.age = TIMESTAMPDIFF(YEAR, NEW.date_of_birth, CURDATE());
    IF NEW.date_of_birth > CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'date_of_birth cannot be in the future';
    END IF;
END;""",
    },
    {
        "name": "visit_frequency_alert_trigger",
        "fires": "AFTER INSERT on visits",
        "description": "Counts how many visits a patient has had in the last 30 days. If the count exceeds 3, inserts a HIGH severity alert into the alerts collection.",
        "sql": """CREATE TRIGGER trg_visit_frequency
AFTER INSERT ON visits
FOR EACH ROW
BEGIN
    DECLARE visit_count INT;
    SELECT COUNT(*) INTO visit_count FROM visits
    WHERE patient_id = NEW.patient_id
      AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);
    IF visit_count > 3 THEN
        INSERT INTO alerts (alert_id, patient_id, alert_type, severity, message)
        VALUES (gen_id(), NEW.patient_id, 'visit_frequency', 'high',
                CONCAT('Patient has ', visit_count, ' visits in 30 days'));
    END IF;
END;""",
    },
    {
        "name": "abnormal_vitals_trigger",
        "fires": "AFTER INSERT on visits (when vital_signs present)",
        "description": "Inspects each vital sign (BP, heart rate, temperature, respiratory rate, SpO2) against normal clinical ranges. Creates one alert per abnormal reading with appropriate severity.",
        "sql": """CREATE TRIGGER trg_abnormal_vitals
AFTER INSERT ON visits
FOR EACH ROW
BEGIN
    IF NEW.bp_systolic < 90 OR NEW.bp_systolic > 140 THEN
        INSERT INTO alerts (alert_type, severity, message)
        VALUES ('abnormal_vitals', 'high', 'Abnormal systolic BP');
    END IF;
    -- Similar checks for diastolic, heart_rate, temperature,
    -- respiratory_rate, oxygen_saturation...
END;""",
    },
    {
        "name": "appointment_conflict_trigger",
        "fires": "BEFORE INSERT on appointments",
        "description": "Checks if the physician already has a scheduled/confirmed appointment within 30 minutes of the proposed time. Raises a ValueError (equivalent to SIGNAL SQLSTATE) to abort the insert.",
        "sql": """CREATE TRIGGER trg_appointment_conflict
BEFORE INSERT ON appointments
FOR EACH ROW
BEGIN
    DECLARE conflict_count INT;
    SELECT COUNT(*) INTO conflict_count FROM appointments
    WHERE physician_id = NEW.physician_id
      AND status IN ('scheduled', 'confirmed')
      AND appointment_date_and_time BETWEEN
          DATE_SUB(NEW.appointment_date_and_time, INTERVAL 30 MINUTE)
          AND DATE_ADD(NEW.appointment_date_and_time, INTERVAL 30 MINUTE);
    IF conflict_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Scheduling conflict detected';
    END IF;
END;""",
    },
]


def _render_triggers_section(db: DatabaseConnection) -> None:
    """Render Section 4: Trigger Demonstrations with SQL equivalents and live demos.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("4. Trigger Demonstrations")
    st.info(
        "Triggers fire automatically inside CRUD operations — the caller never "
        "invokes them directly, exactly like SQL `CREATE TRIGGER` statements. "
        "Our 5 triggers cover BEFORE INSERT, AFTER INSERT, and AFTER UPDATE events."
    )

    # Overview table
    trigger_overview = [
        {"Trigger": t["name"], "Fires": t["fires"], "Description": t["description"]}
        for t in _TRIGGER_INFO
    ]
    st.dataframe(trigger_overview, use_container_width=True, hide_index=True)

    st.divider()

    # Detailed trigger cards with SQL + live demo
    for tinfo in _TRIGGER_INFO:
        with st.expander(f"Trigger: {tinfo['name']}"):
            st.markdown(f"**When it fires:** {tinfo['fires']}")
            st.markdown(f"**What it does:** {tinfo['description']}")

            st.markdown("**SQL Equivalent:**")
            st.code(tinfo["sql"], language="sql")

            # Show Python source
            with st.expander("View Python Implementation"):
                trigger_fn_map = {
                    "audit_log_trigger": audit_log_trigger,
                    "age_calculator_trigger": age_calculator_trigger,
                    "visit_frequency_alert_trigger": visit_frequency_alert_trigger,
                    "abnormal_vitals_trigger": abnormal_vitals_trigger,
                    "appointment_conflict_trigger": appointment_conflict_trigger,
                }
                fn = trigger_fn_map.get(tinfo["name"])
                if fn:
                    try:
                        st.code(inspect.getsource(fn), language="python")
                    except Exception:
                        st.caption("Source not available.")

            # Live demo buttons
            _render_trigger_demo(db, tinfo["name"])


def _render_trigger_demo(db: DatabaseConnection, trigger_name: str) -> None:
    """Render a live demo button for a specific trigger.

    Args:
        db: Active DatabaseConnection.
        trigger_name: Name of the trigger to demonstrate.
    """
    if trigger_name == "age_calculator_trigger":
        if st.button("Demo: Calculate age from DOB", key="demo_age"):
            try:
                test_dob = date(1995, 6, 15)
                age = age_calculator_trigger(test_dob)
                st.success(f"Input DOB: {test_dob} => Computed age: **{age} years**")

                # Also test future date rejection
                try:
                    age_calculator_trigger(date(2099, 1, 1))
                    st.error("Should have raised ValueError for future date!")
                except ValueError as exc:
                    st.success(f"Future date correctly rejected: {exc}")
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "audit_log_trigger":
        if st.button("Demo: Fire audit log entry", key="demo_audit"):
            try:
                sample_pid = _get_sample_patient_id(db)
                audit_log_trigger(
                    db,
                    patient_id=sample_pid,
                    action=AuditAction.READ,
                    collection_name="patients",
                    document_id=sample_pid,
                    performed_by="dbms_demo_page",
                    performed_by_role="demo",
                )
                # Verify it was written
                latest = db.get_collection("audit_logs").find_one(
                    {"performed_by": "dbms_demo_page"},
                    {"_id": 0},
                    sort=[("timestamp", -1)],
                )
                if latest:
                    st.success("Audit log entry written successfully!")
                    st.json({k: str(v) for k, v in latest.items()})
                else:
                    st.warning("Entry was written but could not be read back immediately.")
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "visit_frequency_alert_trigger":
        if st.button("Demo: Check visit frequency", key="demo_freq"):
            try:
                sample_pid = _get_sample_patient_id(db)
                count_before = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "visit_frequency"}
                )
                visit_frequency_alert_trigger(
                    db, sample_pid, "VIS-DEMO-001", threshold=0, window_days=365
                )
                count_after = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "visit_frequency"}
                )
                if count_after > count_before:
                    st.success(
                        f"Alert raised for {sample_pid}! "
                        f"(alerts before: {count_before}, after: {count_after})"
                    )
                else:
                    st.info(
                        f"No alert raised — patient {sample_pid} does not exceed "
                        f"the threshold in the last 365 days."
                    )
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "abnormal_vitals_trigger":
        if st.button("Demo: Check abnormal vitals", key="demo_vitals"):
            try:
                sample_pid = _get_sample_patient_id(db)
                # Deliberately abnormal values to trigger alerts
                abnormal = VitalSigns(
                    blood_pressure_systolic=180,
                    heart_rate=120,
                    temperature_celsius=39.5,
                    oxygen_saturation=88.0,
                )
                count_before = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "abnormal_vitals"}
                )
                abnormal_vitals_trigger(db, sample_pid, "VIS-DEMO-VITALS", abnormal)
                count_after = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "abnormal_vitals"}
                )
                new_alerts = count_after - count_before
                st.success(
                    f"Trigger fired! **{new_alerts}** abnormal vitals alerts created.\n\n"
                    f"Test values: BP 180 mmHg (HIGH), HR 120 bpm (HIGH), "
                    f"Temp 39.5C (HIGH), SpO2 88% (CRITICAL)"
                )
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "appointment_conflict_trigger":
        if st.button("Demo: Detect scheduling conflict", key="demo_conflict"):
            try:
                # Find any physician with an existing appointment
                sample_appt = db.get_collection("appointments").find_one(
                    {"status": {"$in": ["scheduled", "confirmed"]}},
                    {"physician_id": 1, "appointment_date_and_time": 1, "_id": 0},
                )
                if sample_appt:
                    phy_id = sample_appt["physician_id"]
                    existing_time = sample_appt["appointment_date_and_time"]
                    # Try booking at the exact same time — should conflict
                    try:
                        appointment_conflict_trigger(db, phy_id, existing_time)
                        st.info("No conflict found (appointment may have been cancelled).")
                    except ValueError as exc:
                        st.success(f"Conflict correctly detected: {exc}")
                else:
                    st.info("No active appointments found to test against. Schedule one first.")
            except Exception as exc:
                st.error(f"Demo error: {exc}")


# ============================================================================
# Section 5 — Stored Procedures
# ============================================================================

def generate_patient_summary(db: DatabaseConnection, patient_id: str) -> Optional[dict]:
    """Stored Procedure 1: Generate a comprehensive patient summary report.

    Simulates the SQL stored procedure pattern of encapsulating multi-step
    read logic into a single callable unit. Pulls data from patients, visits,
    appointments, referrals, and alerts in one call.

    SQL equivalent:
        CREATE PROCEDURE sp_patient_summary(IN p_id VARCHAR(20))
        BEGIN
            SELECT * FROM patients WHERE patient_id = p_id;
            SELECT COUNT(*) AS total_visits FROM visits WHERE patient_id = p_id;
            SELECT COUNT(*) AS total_appointments FROM appointments WHERE patient_id = p_id;
            SELECT COUNT(*) AS active_alerts FROM alerts WHERE patient_id = p_id AND NOT is_acknowledged;
            SELECT * FROM visits WHERE patient_id = p_id ORDER BY visit_date DESC LIMIT 5;
        END;

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.

    Returns:
        Dict with patient info, counts, and recent history, or None if not found.
    """
    try:
        patient = db.get_collection("patients").find_one(
            {"patient_id": patient_id}, {"_id": 0}
        )
        if not patient:
            return None

        total_visits = db.get_collection("visits").count_documents(
            {"patient_id": patient_id}
        )
        total_appointments = db.get_collection("appointments").count_documents(
            {"patient_id": patient_id}
        )
        total_referrals = db.get_collection("referrals").count_documents(
            {"patient_id": patient_id}
        )
        active_alerts = db.get_collection("alerts").count_documents(
            {"patient_id": patient_id, "is_acknowledged": False}
        )
        recent_visits = list(
            db.get_collection("visits")
            .find({"patient_id": patient_id}, {"_id": 0})
            .sort("visit_date", -1)
            .limit(5)
        )

        return {
            "patient": patient,
            "total_visits": total_visits,
            "total_appointments": total_appointments,
            "total_referrals": total_referrals,
            "active_alerts": active_alerts,
            "recent_visits": recent_visits,
        }
    except PyMongoError as exc:
        raise RuntimeError(f"sp_patient_summary failed: {exc}") from exc


def get_department_report(db: DatabaseConnection, department_id: str) -> Optional[dict]:
    """Stored Procedure 2: Generate department analytics report.

    Multi-step procedure that collects physicians, visit stats, and top
    diagnoses for a single department.

    SQL equivalent:
        CREATE PROCEDURE sp_department_report(IN d_id VARCHAR(20))
        BEGIN
            SELECT * FROM departments WHERE department_id = d_id;
            SELECT * FROM physicians WHERE department_id = d_id;
            SELECT COUNT(DISTINCT v.patient_id) FROM visit_departments vd
                JOIN visits v ON vd.visit_id = v.visit_id WHERE vd.department_id = d_id;
            SELECT diagnosis, COUNT(*) FROM visits v JOIN visit_departments vd
                ON v.visit_id = vd.visit_id WHERE vd.department_id = d_id
                GROUP BY diagnosis ORDER BY COUNT(*) DESC LIMIT 5;
        END;

    Args:
        db: Active DatabaseConnection.
        department_id: The department identifier.

    Returns:
        Dict with department info, physicians, patient count, and top diagnoses.
    """
    try:
        department = db.get_collection("departments").find_one(
            {"department_id": department_id}, {"_id": 0}
        )
        if not department:
            return None

        physicians = list(
            db.get_collection("physicians")
            .find({"department_id": department_id}, {"_id": 0})
            .sort("last_name", 1)
        )

        # Get visit IDs linked to this department via junction table
        junctions = list(
            db.get_collection("visit_departments")
            .find({"department_id": department_id}, {"visit_id": 1, "_id": 0})
        )
        visit_ids = [j["visit_id"] for j in junctions]

        unique_patients: set[str] = set()
        diagnosis_counts: dict[str, int] = {}

        if visit_ids:
            visits = list(
                db.get_collection("visits")
                .find(
                    {"visit_id": {"$in": visit_ids}},
                    {"patient_id": 1, "diagnosis": 1, "_id": 0},
                )
            )
            for v in visits:
                unique_patients.add(v.get("patient_id", ""))
                diag = v.get("diagnosis")
                if diag:
                    diagnosis_counts[diag] = diagnosis_counts.get(diag, 0) + 1

        top_diagnoses = sorted(
            diagnosis_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "department": department,
            "physicians": physicians,
            "physician_count": len(physicians),
            "total_visits": len(visit_ids),
            "unique_patients": len(unique_patients),
            "top_diagnoses": [
                {"diagnosis": d, "count": c} for d, c in top_diagnoses
            ],
        }
    except PyMongoError as exc:
        raise RuntimeError(f"sp_department_report failed: {exc}") from exc


def process_referral_chain(db: DatabaseConnection, patient_id: str) -> Optional[dict]:
    """Stored Procedure 3: Trace the full referral history for a patient.

    Collects every referral, resolves source and target physician names,
    and builds a chain showing how the patient moved between specialists.

    SQL equivalent:
        CREATE PROCEDURE sp_referral_chain(IN p_id VARCHAR(20))
        BEGIN
            SELECT r.*, sp.first_name || ' ' || sp.last_name AS source_name,
                   sp.speciality AS source_spec,
                   tp.first_name || ' ' || tp.last_name AS target_name,
                   tp.speciality AS target_spec
            FROM referrals r
            JOIN physicians sp ON r.source_physician_id = sp.physician_id
            JOIN physicians tp ON r.target_physician_id = tp.physician_id
            WHERE r.patient_id = p_id
            ORDER BY r.referral_date ASC;
        END;

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.

    Returns:
        Dict with patient info and ordered referral chain with physician details.
    """
    try:
        patient = db.get_collection("patients").find_one(
            {"patient_id": patient_id},
            {"_id": 0, "patient_id": 1, "first_name": 1, "last_name": 1},
        )
        if not patient:
            return None

        referrals = list(
            db.get_collection("referrals")
            .find({"patient_id": patient_id}, {"_id": 0})
            .sort("referral_date", 1)
        )

        chain: list[dict] = []
        for ref in referrals:
            source = db.get_collection("physicians").find_one(
                {"physician_id": ref.get("source_physician_id")},
                {"_id": 0, "first_name": 1, "last_name": 1, "speciality": 1},
            )
            target = db.get_collection("physicians").find_one(
                {"physician_id": ref.get("target_physician_id")},
                {"_id": 0, "first_name": 1, "last_name": 1, "speciality": 1},
            )

            ref_date = ref.get("referral_date")
            date_str = ref_date.strftime("%d %b %Y") if hasattr(ref_date, "strftime") else str(ref_date)

            chain.append({
                "referral_id": ref.get("referral_id", ""),
                "date": date_str,
                "from": f"Dr. {source['first_name']} {source['last_name']} ({source['speciality']})" if source else "Unknown",
                "to": f"Dr. {target['first_name']} {target['last_name']} ({target['speciality']})" if target else "Unknown",
                "reason": ref.get("reason", ""),
                "status": str(ref.get("status", "")).title(),
            })

        return {
            "patient": patient,
            "total_referrals": len(chain),
            "referral_chain": chain,
        }
    except PyMongoError as exc:
        raise RuntimeError(f"sp_referral_chain failed: {exc}") from exc


def _render_procedures_section(db: DatabaseConnection) -> None:
    """Render Section 5: Stored Procedures with SQL equivalents and live execution.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("5. Stored Procedures")
    st.info(
        "Stored procedures in SQL encapsulate multi-step read/write logic on the "
        "server. In MongoDB + Python, we achieve the same pattern with dedicated "
        "functions that perform multiple queries in a single call."
    )

    procedures = [
        {
            "name": "sp_patient_summary",
            "function": generate_patient_summary,
            "description": "Generates a full patient report: demographics, visit count, appointment count, active alerts, and 5 most recent visits.",
            "sql": inspect.getdoc(generate_patient_summary) or "",
        },
        {
            "name": "sp_department_report",
            "function": get_department_report,
            "description": "Department analytics: physician roster, total visits, unique patients, and top 5 diagnoses.",
            "sql": inspect.getdoc(get_department_report) or "",
        },
        {
            "name": "sp_referral_chain",
            "function": process_referral_chain,
            "description": "Traces the full referral chain for a patient — shows how they moved between specialists over time.",
            "sql": inspect.getdoc(process_referral_chain) or "",
        },
    ]

    for proc in procedures:
        with st.expander(f"Procedure: {proc['name']}"):
            st.markdown(f"**Description:** {proc['description']}")

            # Extract just the SQL block from the docstring
            doc = proc["sql"]
            sql_start = doc.find("CREATE PROCEDURE")
            sql_end = doc.find("END;")
            if sql_start >= 0 and sql_end >= 0:
                st.markdown("**SQL Equivalent:**")
                st.code(doc[sql_start : sql_end + 4], language="sql")

            # Show Python source
            with st.expander("View Python Implementation"):
                try:
                    st.code(inspect.getsource(proc["function"]), language="python")
                except Exception:
                    st.caption("Source not available.")

    st.divider()

    # Live execution section
    st.markdown("**Live Execution**")

    # Procedure 1 — Patient Summary
    with st.expander("Execute: sp_patient_summary"):
        sample_pid = _get_sample_patient_id(db)
        pid_input = st.text_input(
            "Patient ID", value=sample_pid, key="proc1_pid"
        )
        if st.button("Run sp_patient_summary", key="run_proc1"):
            try:
                start = time.time()
                result = generate_patient_summary(db, pid_input)
                elapsed = time.time() - start

                if result:
                    st.success(f"Executed in {elapsed:.3f}s")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Visits", result["total_visits"])
                    col2.metric("Appointments", result["total_appointments"])
                    col3.metric("Referrals", result["total_referrals"])
                    col4.metric("Active Alerts", result["active_alerts"])

                    if result["recent_visits"]:
                        st.markdown("**Recent Visits:**")
                        st.dataframe(
                            result["recent_visits"],
                            use_container_width=True,
                            hide_index=True,
                        )
                else:
                    st.warning(f"Patient {pid_input} not found.")
            except Exception as exc:
                st.error(f"Procedure error: {exc}")

    # Procedure 2 — Department Report
    with st.expander("Execute: sp_department_report"):
        try:
            depts = list(
                db.get_collection("departments")
                .find({}, {"_id": 0, "department_id": 1, "department_name": 1})
                .sort("department_name", 1)
            )
            dept_options = {
                d["department_name"]: d["department_id"] for d in depts
            }
        except Exception:
            dept_options = {}

        if dept_options:
            selected_dept = st.selectbox(
                "Select Department",
                options=list(dept_options.keys()),
                key="proc2_dept",
            )
            if st.button("Run sp_department_report", key="run_proc2"):
                try:
                    start = time.time()
                    result = get_department_report(db, dept_options[selected_dept])
                    elapsed = time.time() - start

                    if result:
                        st.success(f"Executed in {elapsed:.3f}s")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Physicians", result["physician_count"])
                        col2.metric("Total Visits", result["total_visits"])
                        col3.metric("Unique Patients", result["unique_patients"])

                        if result["top_diagnoses"]:
                            st.markdown("**Top Diagnoses:**")
                            st.dataframe(
                                result["top_diagnoses"],
                                use_container_width=True,
                                hide_index=True,
                            )

                        if result["physicians"]:
                            st.markdown("**Physician Roster:**")
                            roster = [
                                {
                                    "Name": f"Dr. {p.get('first_name', '')} {p.get('last_name', '')}",
                                    "Speciality": p.get("speciality", ""),
                                }
                                for p in result["physicians"]
                            ]
                            st.dataframe(roster, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Department not found.")
                except Exception as exc:
                    st.error(f"Procedure error: {exc}")
        else:
            st.info("No departments found. Load seed data first.")

    # Procedure 3 — Referral Chain
    with st.expander("Execute: sp_referral_chain"):
        sample_pid2 = _get_sample_patient_id(db)
        pid_input2 = st.text_input(
            "Patient ID", value=sample_pid2, key="proc3_pid"
        )
        if st.button("Run sp_referral_chain", key="run_proc3"):
            try:
                start = time.time()
                result = process_referral_chain(db, pid_input2)
                elapsed = time.time() - start

                if result:
                    st.success(
                        f"Executed in {elapsed:.3f}s — "
                        f"**{result['total_referrals']}** referrals found"
                    )

                    if result["referral_chain"]:
                        st.dataframe(
                            result["referral_chain"],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No referrals found for this patient.")
                else:
                    st.warning(f"Patient {pid_input2} not found.")
            except Exception as exc:
                st.error(f"Procedure error: {exc}")


# ============================================================================
# Section 6 — Audit Log Viewer
# ============================================================================

def _render_audit_section(db: DatabaseConnection) -> None:
    """Render Section 6: Live audit log viewer proving triggers work in real time.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("6. Audit Log Viewer")
    st.info(
        "Every CRUD operation fires the `audit_log_trigger`, which writes to the "
        "`audit_logs` collection. This viewer shows the live audit trail — proof "
        "that the trigger is working in real time."
    )

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        action_filter = st.selectbox(
            "Filter by Action",
            options=["All", "create", "read", "update", "delete"],
            key="audit_action_filter",
        )

    with col2:
        collection_filter = st.selectbox(
            "Filter by Collection",
            options=[
                "All", "patients", "visits", "appointments",
                "referrals", "alerts",
            ],
            key="audit_collection_filter",
        )

    with col3:
        limit = st.number_input(
            "Max rows", min_value=10, max_value=200, value=50, key="audit_limit"
        )

    # Refresh button
    if st.button("Refresh Audit Log", key="refresh_audit", use_container_width=True):
        st.session_state.pop("audit_cache", None)

    try:
        query: dict[str, Any] = {}
        if action_filter != "All":
            query["action"] = action_filter
        if collection_filter != "All":
            query["collection_name"] = collection_filter

        logs = list(
            db.get_collection("audit_logs")
            .find(query, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )

        if not logs:
            st.info("No audit log entries found for the selected filters.")
            return

        st.caption(f"Showing {len(logs)} most recent entries")

        # Format for display
        display_data = []
        for log in logs:
            ts = log.get("timestamp")
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)

            changes = log.get("changes")
            changes_str = ""
            if changes and isinstance(changes, dict):
                parts = []
                for field, diff in changes.items():
                    if isinstance(diff, dict):
                        parts.append(
                            f"{field}: {diff.get('before', '?')} -> {diff.get('after', '?')}"
                        )
                changes_str = "; ".join(parts) if parts else ""

            display_data.append({
                "Timestamp": ts_str,
                "Action": str(log.get("action", "")).upper(),
                "Collection": log.get("collection_name", ""),
                "Document ID": log.get("document_id", ""),
                "Patient ID": log.get("patient_id", ""),
                "Performed By": log.get("performed_by", ""),
                "Role": log.get("performed_by_role", ""),
                "Changes": changes_str,
            })

        st.dataframe(display_data, use_container_width=True, hide_index=True)

        # Summary stats
        total_logs = db.get_collection("audit_logs").count_documents({})
        action_counts: dict[str, int] = {}
        for action_val in ["create", "read", "update", "delete"]:
            action_counts[action_val] = db.get_collection("audit_logs").count_documents(
                {"action": action_val}
            )

        st.divider()
        st.markdown("**Audit Log Summary**")
        summary_cols = st.columns(5)
        summary_cols[0].metric("Total Entries", total_logs)
        summary_cols[1].metric("CREATE", action_counts.get("create", 0))
        summary_cols[2].metric("READ", action_counts.get("read", 0))
        summary_cols[3].metric("UPDATE", action_counts.get("update", 0))
        summary_cols[4].metric("DELETE", action_counts.get("delete", 0))

    except PyMongoError as exc:
        st.error(f"Database error loading audit logs: {exc}")
    except Exception as exc:
        st.error(f"Error loading audit logs: {exc}")


# ============================================================================
# Main render function
# ============================================================================

def render(db: DatabaseConnection) -> None:
    """Render the full DBMS Concepts demonstration page.

    This is the page the professor evaluates directly during the viva.
    Six clearly labeled sections cover every core DBMS concept.

    Args:
        db: Active DatabaseConnection.
    """
    st.header("DBMS Concepts — Module 1 Patient Demographics")
    st.success(
        "This page demonstrates all core DBMS concepts implemented in this module: "
        "**Normalization**, **Indexes**, **Constraints**, **Views** (aggregation pipelines), "
        "**Triggers**, **Stored Procedures**, and **Audit Logging**."
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Schema & Normalization",
        "Indexes & Constraints",
        "Live Query Execution",
        "Trigger Demos",
        "Stored Procedures",
        "Audit Log Viewer",
    ])

    with tab1:
        _render_schema_section()

    with tab2:
        _render_indexes_section(db)

    with tab3:
        _render_queries_section(db)

    with tab4:
        _render_triggers_section(db)

    with tab5:
        _render_procedures_section(db)

    with tab6:
        _render_audit_section(db)
