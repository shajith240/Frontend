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
# Section 1 -- Schema & Normalization
# ============================================================================

def _render_schema_section() -> None:
    """Render Section 1: Schema & Normalization with collection details and ER relationships."""
    st.caption(
        "Our database is normalized into 9 separate collections, "
        "each storing a single entity type. This eliminates redundancy and ensures referential integrity."
    )

    collections_data = [
        {"Collection": "patients", "Primary Key": "patient_id (PAT-YYYY-NNN)", "Key Fields": "first_name, last_name, date_of_birth, gender, phone, email, address, insurance", "Purpose": "Core patient demographics -- central entity", "Normalization": "3NF: all fields depend on patient_id"},
        {"Collection": "physicians", "Primary Key": "physician_id", "Key Fields": "first_name, last_name, speciality, department_id (FK)", "Purpose": "Physician registry with department assignment", "Normalization": "department_id is FK -- details stored separately"},
        {"Collection": "departments", "Primary Key": "department_id", "Key Fields": "department_name, location", "Purpose": "Hospital department master data", "Normalization": "Prevents repeating department info in every physician"},
        {"Collection": "visits", "Primary Key": "visit_id", "Key Fields": "visit_date, reason, diagnosis, status, patient_id (FK), physician_id (FK)", "Purpose": "Clinical visit records", "Normalization": "FKs to patients and physicians"},
        {"Collection": "appointments", "Primary Key": "appointment_id", "Key Fields": "appointment_date_and_time, reason, status, patient_id (FK), physician_id (FK)", "Purpose": "Scheduled appointments with conflict detection", "Normalization": "Same FK pattern as visits"},
        {"Collection": "referrals", "Primary Key": "referral_id", "Key Fields": "referral_date, reason, status, patient_id (FK), source/target_physician_id (FK)", "Purpose": "Inter-physician referral tracking", "Normalization": "Two FK references to physicians"},
        {"Collection": "visit_departments", "Primary Key": "(visit_id, department_id)", "Key Fields": "visit_id (FK), department_id (FK)", "Purpose": "Junction table -- Visit-Department M:N", "Normalization": "Classic junction table pattern"},
        {"Collection": "alerts", "Primary Key": "alert_id", "Key Fields": "patient_id (FK), alert_type, severity, title, message", "Purpose": "System-generated clinical alerts", "Normalization": "Separate to track alert lifecycle independently"},
        {"Collection": "audit_logs", "Primary Key": "log_id", "Key Fields": "patient_id, action, collection_name, document_id, performed_by", "Purpose": "Immutable audit trail", "Normalization": "Append-only -- never updated"},
    ]
    st.dataframe(collections_data, use_container_width=True, hide_index=True)

    with st.expander("VisitDepartment Junction Table -- Resolving M-to-N"):
        left, right = st.columns(2)
        with left:
            st.markdown("**SQL Equivalent:**")
            st.code(
                """CREATE TABLE visit_departments (
    visit_id       VARCHAR(20)  REFERENCES visits(visit_id),
    department_id  VARCHAR(20)  REFERENCES departments(department_id),
    created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (visit_id, department_id)
);""",
                language="sql",
            )
        with right:
            st.markdown("**MongoDB Equivalent:**")
            st.code(
                """db.visit_departments.insertOne({
    visit_id: "VIS-2024-001",
    department_id: "DEP-2024-003",
    created_at: ISODate()
})""",
                language="javascript",
            )

    with st.expander("ER Diagram Relationships"):
        relationships = [
            {"Entity A": "Patient", "Relationship": "1 --< N", "Entity B": "Visit", "FK Location": "visits.patient_id"},
            {"Entity A": "Patient", "Relationship": "1 --< N", "Entity B": "Appointment", "FK Location": "appointments.patient_id"},
            {"Entity A": "Patient", "Relationship": "1 --< N", "Entity B": "Referral", "FK Location": "referrals.patient_id"},
            {"Entity A": "Physician", "Relationship": "1 --< N", "Entity B": "Visit", "FK Location": "visits.physician_id"},
            {"Entity A": "Physician", "Relationship": "1 --< N", "Entity B": "Appointment", "FK Location": "appointments.physician_id"},
            {"Entity A": "Department", "Relationship": "1 --< N", "Entity B": "Physician", "FK Location": "physicians.department_id"},
            {"Entity A": "Visit", "Relationship": "M -->< N", "Entity B": "Department", "FK Location": "visit_departments (junction)"},
            {"Entity A": "Physician (src)", "Relationship": "1 --< N", "Entity B": "Referral", "FK Location": "referrals.source_physician_id"},
            {"Entity A": "Physician (tgt)", "Relationship": "1 --< N", "Entity B": "Referral", "FK Location": "referrals.target_physician_id"},
        ]
        st.dataframe(relationships, use_container_width=True, hide_index=True)


# ============================================================================
# Section 2 -- Indexes & Constraints
# ============================================================================

def _render_indexes_section(db: DatabaseConnection) -> None:
    """Render Section 2: Indexes & Constraints.

    Args:
        db: Active DatabaseConnection.
    """
    st.caption(
        "Indexes speed up queries. Pydantic models enforce constraints equivalent to SQL CHECK/NOT NULL."
    )

    indexes_data = [
        {"Index Name": "patient_id_1", "Field(s)": "patient_id", "Type": "UNIQUE", "SQL": "CREATE UNIQUE INDEX idx_patient_id ON patients(patient_id)"},
        {"Index Name": "name_1", "Field(s)": "name", "Type": "ASCENDING", "SQL": "CREATE INDEX idx_name ON patients(name)"},
        {"Index Name": "date_of_birth_1", "Field(s)": "date_of_birth", "Type": "ASCENDING", "SQL": "CREATE INDEX idx_dob ON patients(date_of_birth)"},
    ]
    st.dataframe(indexes_data, use_container_width=True, hide_index=True)

    with st.expander("Live Index Info from MongoDB"):
        try:
            live_indexes = list(db.get_collection("patients").list_indexes())
            for idx in live_indexes:
                idx_name = idx.get("name", "unknown")
                idx_key = dict(idx.get("key", {}))
                idx_unique = idx.get("unique", False)
                st.code(
                    f"Index: {idx_name}\n  Key:    {idx_key}\n  Unique: {idx_unique}",
                    language="text",
                )
        except Exception as exc:
            st.warning(f"Could not fetch live indexes: {exc}")

    st.divider()

    st.markdown("**Pydantic Validation Constraints (SQL CHECK / NOT NULL equivalents)**")
    constraints_data = [
        {"Model": "Patient", "Field": "patient_id", "Constraint": "Regex: PAT-\\d{4}-\\d{3}", "SQL": "CHECK (patient_id ~ '^PAT-\\d{4}-\\d{3}$')"},
        {"Model": "Patient", "Field": "first_name", "Constraint": "min_length=1, NOT NULL", "SQL": "VARCHAR NOT NULL CHECK (LENGTH >= 1)"},
        {"Model": "Patient", "Field": "date_of_birth", "Constraint": "Cannot be in the future", "SQL": "CHECK (date_of_birth <= CURRENT_DATE)"},
        {"Model": "Patient", "Field": "gender", "Constraint": "Enum: male, female, other, prefer_not_to_say", "SQL": "CHECK (gender IN (...))"},
        {"Model": "Patient", "Field": "age", "Constraint": "0 <= age <= 150", "SQL": "CHECK (age BETWEEN 0 AND 150)"},
        {"Model": "VitalSigns", "Field": "blood_pressure_systolic", "Constraint": "50 <= value <= 300", "SQL": "CHECK (bp_systolic BETWEEN 50 AND 300)"},
        {"Model": "VitalSigns", "Field": "oxygen_saturation", "Constraint": "50.0 <= value <= 100.0", "SQL": "CHECK (spo2 BETWEEN 50.0 AND 100.0)"},
        {"Model": "Appointment", "Field": "status + cancellation_reason", "Constraint": "reason required when cancelled", "SQL": "CHECK (status != 'cancelled' OR reason IS NOT NULL)"},
    ]
    st.dataframe(constraints_data, use_container_width=True, hide_index=True)


# ============================================================================
# Section 3 -- Live Query Execution
# ============================================================================

_QUERY_REGISTRY: list[dict[str, Any]] = [
    {"name": "Patients with Visit Count", "function": get_patients_with_visit_count, "sql": "SELECT p.patient_id, p.first_name, p.last_name, COUNT(v.visit_id) AS visit_count\nFROM patients p LEFT JOIN visits v ON p.patient_id = v.patient_id\nGROUP BY p.patient_id ORDER BY visit_count DESC", "key_ops": "$lookup, $addFields + $size, $sort", "args": lambda db: (db,)},
    {"name": "Visit Frequency by Month", "function": get_visit_frequency_by_month, "sql": "SELECT YEAR(visit_date), MONTH(visit_date), COUNT(*)\nFROM visits GROUP BY YEAR, MONTH ORDER BY year, month", "key_ops": "$addFields, $group, $sort", "args": lambda db: (db,)},
    {"name": "Top Diagnoses", "function": get_top_diagnoses, "sql": "SELECT diagnosis, COUNT(*) AS frequency FROM visits\nWHERE diagnosis IS NOT NULL\nGROUP BY diagnosis ORDER BY frequency DESC LIMIT 10", "key_ops": "$match, $group, $sort, $limit", "args": lambda db: (db,)},
    {"name": "Patients per Department", "function": get_patients_per_department, "sql": "SELECT d.department_name, COUNT(DISTINCT v.patient_id)\nFROM departments d LEFT JOIN visit_departments vd ... LEFT JOIN visits v ...\nGROUP BY d.department_id", "key_ops": "$lookup (double JOIN), $reduce + $setUnion", "args": lambda db: (db,)},
    {"name": "Patients with Pending Appointments", "function": get_patients_with_pending_appointments, "sql": "SELECT p.*, a.*, ph.name AS physician_name\nFROM appointments a JOIN patients p ... JOIN physicians ph ...\nWHERE a.status IN ('scheduled', 'confirmed')", "key_ops": "$match, $lookup x2, $unwind, $concat", "args": lambda db: (db,)},
    {"name": "Referral Network Summary", "function": get_referral_network_summary, "sql": "SELECT sp.name AS source, tp.name AS target, COUNT(*)\nFROM referrals r JOIN physicians sp ... JOIN physicians tp ...\nGROUP BY source_id, target_id", "key_ops": "$group, $lookup x2, $concat", "args": lambda db: (db,)},
    {"name": "High Frequency Visitors", "function": get_high_frequency_visitors, "sql": "SELECT p.patient_id, COUNT(v.visit_id)\nFROM visits v JOIN patients p ... WHERE v.visit_date >= NOW() - 30 DAY\nGROUP BY patient_id HAVING COUNT(*) >= 3", "key_ops": "$match, $group + $match (HAVING), $lookup", "args": lambda db: (db,)},
    {"name": "Patient Full Profile", "function": get_patient_full_profile, "sql": "SELECT p.*, v.*, a.*, r.*, d.department_name\nFROM patients p LEFT JOIN visits v ... LEFT JOIN appointments a ...\nLEFT JOIN referrals r ... WHERE p.patient_id = :id", "key_ops": "Nested pipeline $lookup x5 (6-table JOIN)", "args": lambda db: (db, _get_sample_patient_id(db))},
    {"name": "Physician Workload", "function": get_physician_workload, "sql": "SELECT ph.physician_id, ph.name, COALESCE(v.cnt, 0) + COALESCE(a.cnt, 0)\nFROM physicians ph LEFT JOIN (...) v ... LEFT JOIN (...) a ...", "key_ops": "$lookup with pipeline, $ifNull, $add", "args": lambda db: (db,)},
    {"name": "Department Statistics", "function": get_department_statistics, "sql": "SELECT d.department_name, COUNT(vd.visit_id),\nCOUNT(DISTINCT v.patient_id), (TOP 1 diagnosis)\nFROM departments d LEFT JOIN ...", "key_ops": "Double $lookup, nested pipeline, $reduce", "args": lambda db: (db,)},
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
    """Render Section 3: Live Query Execution.

    Args:
        db: Active DatabaseConnection.
    """
    st.caption(
        "All 10 aggregation pipelines are MongoDB equivalents of SQL queries."
    )

    # Metrics bar
    total_run = st.session_state.get("dbms_queries_run", 0)
    avg_time = st.session_state.get("dbms_avg_time", 0.0)
    last_run = st.session_state.get("dbms_last_run", "--")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Queries Run", total_run)
    m2.metric("Avg Time", f"{avg_time:.3f}s")
    m3.metric("Last Run", last_run)

    with m4:
        if st.button("Run All 10", type="primary", use_container_width=True):
            start = time.time()
            try:
                all_results = run_all_queries(db)
                elapsed = time.time() - start
                st.session_state["dbms_queries_run"] = st.session_state.get("dbms_queries_run", 0) + 10
                st.session_state["dbms_avg_time"] = elapsed / 10
                st.session_state["dbms_last_run"] = datetime.now().strftime("%H:%M:%S")
                st.session_state["all_query_results"] = all_results
                st.success(f"All 10 queries executed in **{elapsed:.2f}s**")
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.divider()

    for idx, qinfo in enumerate(_QUERY_REGISTRY, 1):
        with st.expander(f"Query {idx}: {qinfo['name']}"):
            # Side by side: SQL left, MongoDB ops right
            left, right = st.columns(2)
            with left:
                st.markdown("**SQL Equivalent:**")
                st.code(qinfo["sql"], language="sql")
            with right:
                st.markdown("**MongoDB Operations:**")
                st.code(qinfo["key_ops"], language="text")

                with st.expander("View Python Pipeline"):
                    try:
                        source = inspect.getsource(qinfo["function"])
                        st.code(source, language="python")
                    except Exception:
                        st.caption("Source not available at runtime.")

            if st.button(f"Run Query {idx}", key=f"run_q{idx}"):
                try:
                    q_start = time.time()
                    args = qinfo["args"](db)
                    result = qinfo["function"](*args)
                    q_elapsed = time.time() - q_start

                    st.session_state["dbms_queries_run"] = st.session_state.get("dbms_queries_run", 0) + 1
                    st.session_state["dbms_last_run"] = datetime.now().strftime("%H:%M:%S")

                    rows = len(result) if isinstance(result, list) else 1
                    st.success(f"**{rows}** rows in {q_elapsed:.3f}s")

                    if isinstance(result, dict):
                        st.json(result)
                    elif isinstance(result, list) and result:
                        st.dataframe(result, use_container_width=True, hide_index=True)
                    else:
                        st.info("No results -- seed data may not be loaded.")
                except Exception as exc:
                    st.error(f"Query failed: {exc}")


# ============================================================================
# Section 4 -- Trigger Demonstrations
# ============================================================================

_TRIGGER_INFO: list[dict[str, str]] = [
    {"name": "audit_log_trigger", "fires": "AFTER INSERT / UPDATE / DELETE on all collections", "description": "Writes an immutable audit row to audit_logs for every CRUD operation.", "sql": "CREATE TRIGGER trg_audit_log\nAFTER INSERT OR UPDATE OR DELETE ON patients\nFOR EACH ROW\nBEGIN\n    INSERT INTO audit_logs (log_id, patient_id, action, ...)\n    VALUES (gen_id(), :patient_id, :action, ...);\nEND;"},
    {"name": "age_calculator_trigger", "fires": "BEFORE INSERT on patients", "description": "Computes age from date_of_birth before insertion.", "sql": "CREATE TRIGGER trg_age_calculator\nBEFORE INSERT ON patients\nFOR EACH ROW\nBEGIN\n    SET NEW.age = TIMESTAMPDIFF(YEAR, NEW.date_of_birth, CURDATE());\nEND;"},
    {"name": "visit_frequency_alert_trigger", "fires": "AFTER INSERT on visits", "description": "Raises HIGH alert if patient has >3 visits in 30 days.", "sql": "CREATE TRIGGER trg_visit_frequency\nAFTER INSERT ON visits\nFOR EACH ROW\nBEGIN\n    SELECT COUNT(*) INTO visit_count FROM visits\n    WHERE patient_id = NEW.patient_id\n      AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);\n    IF visit_count > 3 THEN\n        INSERT INTO alerts (...);\n    END IF;\nEND;"},
    {"name": "abnormal_vitals_trigger", "fires": "AFTER INSERT on visits (when vital_signs present)", "description": "Creates alerts for vital signs outside normal clinical ranges.", "sql": "CREATE TRIGGER trg_abnormal_vitals\nAFTER INSERT ON visits\nFOR EACH ROW\nBEGIN\n    IF NEW.bp_systolic < 90 OR NEW.bp_systolic > 140 THEN\n        INSERT INTO alerts (alert_type, severity, message)\n        VALUES ('abnormal_vitals', 'high', 'Abnormal BP');\n    END IF;\n    -- similar for HR, temp, SpO2, RR\nEND;"},
    {"name": "appointment_conflict_trigger", "fires": "BEFORE INSERT on appointments", "description": "Blocks double-booking within 30-minute slots. Raises ValueError to abort insert.", "sql": "CREATE TRIGGER trg_appointment_conflict\nBEFORE INSERT ON appointments\nFOR EACH ROW\nBEGIN\n    SELECT COUNT(*) INTO conflict_count FROM appointments\n    WHERE physician_id = NEW.physician_id\n      AND status IN ('scheduled', 'confirmed')\n      AND appointment_date_and_time BETWEEN\n          DATE_SUB(NEW.time, INTERVAL 30 MINUTE)\n          AND DATE_ADD(NEW.time, INTERVAL 30 MINUTE);\n    IF conflict_count > 0 THEN\n        SIGNAL SQLSTATE '45000';\n    END IF;\nEND;"},
]


def _render_triggers_section(db: DatabaseConnection) -> None:
    """Render Section 4: Trigger Demonstrations.

    Args:
        db: Active DatabaseConnection.
    """
    st.caption(
        "Triggers fire automatically inside CRUD operations -- exactly like SQL CREATE TRIGGER."
    )

    trigger_overview = [
        {"Trigger": t["name"], "Fires": t["fires"], "Description": t["description"]}
        for t in _TRIGGER_INFO
    ]
    st.dataframe(trigger_overview, use_container_width=True, hide_index=True)

    st.divider()

    for tinfo in _TRIGGER_INFO:
        with st.expander(f"Trigger: {tinfo['name']}"):
            st.markdown(f"**When it fires:** {tinfo['fires']}")
            st.markdown(f"**What it does:** {tinfo['description']}")

            # Side by side SQL / Python
            left, right = st.columns(2)
            with left:
                st.markdown("**SQL Equivalent:**")
                st.code(tinfo["sql"], language="sql")
            with right:
                st.markdown("**Python Implementation:**")
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
                    db, patient_id=sample_pid, action=AuditAction.READ,
                    collection_name="patients", document_id=sample_pid,
                    performed_by="dbms_demo_page", performed_by_role="demo",
                )
                latest = db.get_collection("audit_logs").find_one(
                    {"performed_by": "dbms_demo_page"}, {"_id": 0},
                    sort=[("timestamp", -1)],
                )
                if latest:
                    st.success("Audit log entry written!")
                    st.json({k: str(v) for k, v in latest.items()})
                else:
                    st.warning("Entry written but could not be read back immediately.")
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "visit_frequency_alert_trigger":
        if st.button("Demo: Check visit frequency", key="demo_freq"):
            try:
                sample_pid = _get_sample_patient_id(db)
                count_before = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "visit_frequency"}
                )
                visit_frequency_alert_trigger(db, sample_pid, "VIS-DEMO-001", threshold=0, window_days=365)
                count_after = db.get_collection("alerts").count_documents(
                    {"patient_id": sample_pid, "alert_type": "visit_frequency"}
                )
                if count_after > count_before:
                    st.success(f"Alert raised for {sample_pid}! (before: {count_before}, after: {count_after})")
                else:
                    st.info(f"No alert -- {sample_pid} does not exceed threshold.")
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "abnormal_vitals_trigger":
        if st.button("Demo: Check abnormal vitals", key="demo_vitals"):
            try:
                sample_pid = _get_sample_patient_id(db)
                abnormal = VitalSigns(
                    blood_pressure_systolic=180, heart_rate=120,
                    temperature_celsius=39.5, oxygen_saturation=88.0,
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
                    f"**{new_alerts}** abnormal vitals alerts created.\n\n"
                    f"BP 180 (HIGH), HR 120 (HIGH), Temp 39.5C (HIGH), SpO2 88% (CRITICAL)"
                )
            except Exception as exc:
                st.error(f"Demo error: {exc}")

    elif trigger_name == "appointment_conflict_trigger":
        if st.button("Demo: Detect scheduling conflict", key="demo_conflict"):
            try:
                sample_appt = db.get_collection("appointments").find_one(
                    {"status": {"$in": ["scheduled", "confirmed"]}},
                    {"physician_id": 1, "appointment_date_and_time": 1, "_id": 0},
                )
                if sample_appt:
                    phy_id = sample_appt["physician_id"]
                    existing_time = sample_appt["appointment_date_and_time"]
                    try:
                        appointment_conflict_trigger(db, phy_id, existing_time)
                        st.info("No conflict found.")
                    except ValueError as exc:
                        st.success(f"Conflict correctly detected: {exc}")
                else:
                    st.info("No active appointments to test against.")
            except Exception as exc:
                st.error(f"Demo error: {exc}")


# ============================================================================
# Section 5 -- Stored Procedures
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

        total_visits = db.get_collection("visits").count_documents({"patient_id": patient_id})
        total_appointments = db.get_collection("appointments").count_documents({"patient_id": patient_id})
        total_referrals = db.get_collection("referrals").count_documents({"patient_id": patient_id})
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

    SQL equivalent:
        CREATE PROCEDURE sp_department_report(IN d_id VARCHAR(20))
        BEGIN
            SELECT * FROM departments WHERE department_id = d_id;
            SELECT * FROM physicians WHERE department_id = d_id;
            SELECT COUNT(DISTINCT v.patient_id) FROM visit_departments vd
                JOIN visits v ON vd.visit_id = v.visit_id WHERE vd.department_id = d_id;
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
                .find({"visit_id": {"$in": visit_ids}}, {"patient_id": 1, "diagnosis": 1, "_id": 0})
            )
            for v in visits:
                unique_patients.add(v.get("patient_id", ""))
                diag = v.get("diagnosis")
                if diag:
                    diagnosis_counts[diag] = diagnosis_counts.get(diag, 0) + 1

        top_diagnoses = sorted(diagnosis_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "department": department,
            "physicians": physicians,
            "physician_count": len(physicians),
            "total_visits": len(visit_ids),
            "unique_patients": len(unique_patients),
            "top_diagnoses": [{"diagnosis": d, "count": c} for d, c in top_diagnoses],
        }
    except PyMongoError as exc:
        raise RuntimeError(f"sp_department_report failed: {exc}") from exc


def process_referral_chain(db: DatabaseConnection, patient_id: str) -> Optional[dict]:
    """Stored Procedure 3: Trace the full referral history for a patient.

    SQL equivalent:
        CREATE PROCEDURE sp_referral_chain(IN p_id VARCHAR(20))
        BEGIN
            SELECT r.*, sp.name AS source_name, tp.name AS target_name
            FROM referrals r
            JOIN physicians sp ON r.source_physician_id = sp.physician_id
            JOIN physicians tp ON r.target_physician_id = tp.physician_id
            WHERE r.patient_id = p_id ORDER BY r.referral_date ASC;
        END;

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier.

    Returns:
        Dict with patient info and ordered referral chain.
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

        return {"patient": patient, "total_referrals": len(chain), "referral_chain": chain}
    except PyMongoError as exc:
        raise RuntimeError(f"sp_referral_chain failed: {exc}") from exc


def _render_procedures_section(db: DatabaseConnection) -> None:
    """Render Section 5: Stored Procedures.

    Args:
        db: Active DatabaseConnection.
    """
    st.caption(
        "Stored procedures encapsulate multi-step logic into single callable units."
    )

    procedures = [
        {"name": "sp_patient_summary", "function": generate_patient_summary, "description": "Full patient report: demographics, visit count, appointment count, active alerts, recent visits."},
        {"name": "sp_department_report", "function": get_department_report, "description": "Department analytics: physician roster, total visits, unique patients, top diagnoses."},
        {"name": "sp_referral_chain", "function": process_referral_chain, "description": "Traces the full referral chain for a patient."},
    ]

    for proc in procedures:
        with st.expander(f"Procedure: {proc['name']}"):
            st.markdown(f"**Description:** {proc['description']}")

            left, right = st.columns(2)
            with left:
                doc = inspect.getdoc(proc["function"]) or ""
                sql_start = doc.find("CREATE PROCEDURE")
                sql_end = doc.find("END;")
                if sql_start >= 0 and sql_end >= 0:
                    st.markdown("**SQL Equivalent:**")
                    st.code(doc[sql_start : sql_end + 4], language="sql")
            with right:
                st.markdown("**Python Implementation:**")
                try:
                    st.code(inspect.getsource(proc["function"]), language="python")
                except Exception:
                    st.caption("Source not available.")

    st.divider()

    st.markdown("**Live Execution**")

    with st.expander("Execute: sp_patient_summary"):
        sample_pid = _get_sample_patient_id(db)
        pid_input = st.text_input("Patient ID", value=sample_pid, key="proc1_pid")
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
                        st.dataframe(result["recent_visits"], use_container_width=True, hide_index=True)
                else:
                    st.warning(f"Patient {pid_input} not found.")
            except Exception as exc:
                st.error(f"Procedure error: {exc}")

    with st.expander("Execute: sp_department_report"):
        try:
            depts = list(
                db.get_collection("departments")
                .find({}, {"_id": 0, "department_id": 1, "department_name": 1})
                .sort("department_name", 1)
            )
            dept_options = {d["department_name"]: d["department_id"] for d in depts}
        except Exception:
            dept_options = {}

        if dept_options:
            selected_dept = st.selectbox("Select Department", options=list(dept_options.keys()), key="proc2_dept")
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
                            st.dataframe(result["top_diagnoses"], use_container_width=True, hide_index=True)
                        if result["physicians"]:
                            roster = [
                                {"Name": f"Dr. {p.get('first_name', '')} {p.get('last_name', '')}", "Speciality": p.get("speciality", "")}
                                for p in result["physicians"]
                            ]
                            st.dataframe(roster, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Department not found.")
                except Exception as exc:
                    st.error(f"Procedure error: {exc}")
        else:
            st.info("No departments found. Load seed data first.")

    with st.expander("Execute: sp_referral_chain"):
        sample_pid2 = _get_sample_patient_id(db)
        pid_input2 = st.text_input("Patient ID", value=sample_pid2, key="proc3_pid")
        if st.button("Run sp_referral_chain", key="run_proc3"):
            try:
                start = time.time()
                result = process_referral_chain(db, pid_input2)
                elapsed = time.time() - start
                if result:
                    st.success(f"Executed in {elapsed:.3f}s -- **{result['total_referrals']}** referrals")
                    if result["referral_chain"]:
                        st.dataframe(result["referral_chain"], use_container_width=True, hide_index=True)
                    else:
                        st.info("No referrals found for this patient.")
                else:
                    st.warning(f"Patient {pid_input2} not found.")
            except Exception as exc:
                st.error(f"Procedure error: {exc}")


# ============================================================================
# Section 6 -- Audit Log Viewer
# ============================================================================

def _render_audit_section(db: DatabaseConnection) -> None:
    """Render Section 6: Live audit log viewer.

    Args:
        db: Active DatabaseConnection.
    """
    st.caption(
        "Every CRUD operation fires the audit_log_trigger. This viewer shows the live audit trail."
    )

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
            options=["All", "patients", "visits", "appointments", "referrals", "alerts"],
            key="audit_collection_filter",
        )
    with col3:
        limit = st.number_input("Max rows", min_value=10, max_value=200, value=50, key="audit_limit")

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
                        parts.append(f"{field}: {diff.get('before', '?')} -> {diff.get('after', '?')}")
                changes_str = "; ".join(parts) if parts else ""

            display_data.append({
                "Timestamp": ts_str,
                "Action": str(log.get("action", "")).upper(),
                "Collection": log.get("collection_name", ""),
                "Document ID": log.get("document_id", ""),
                "Patient ID": log.get("patient_id", ""),
                "Performed By": log.get("performed_by", ""),
                "Changes": changes_str,
            })

        st.dataframe(display_data, use_container_width=True, hide_index=True)

        # Summary stats
        total_logs = db.get_collection("audit_logs").count_documents({})
        action_counts: dict[str, int] = {}
        for action_val in ["create", "read", "update", "delete"]:
            action_counts[action_val] = db.get_collection("audit_logs").count_documents({"action": action_val})

        st.divider()
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

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("DBMS Concepts")
    st.caption(
        "Normalization, Indexes, Constraints, Views (aggregation pipelines), "
        "Triggers, Stored Procedures, and Audit Logging."
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Schema",
        "Indexes",
        "Queries",
        "Triggers",
        "Procedures",
        "Audit Log",
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
