"""Appointments page — booking form and status-badged list.

Features:
- Two-column booking form with department filter
- Clean st.dataframe view for existing appointments
- Conflict detection via appointment_conflict_trigger
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import create_appointment
from backend.database import DatabaseConnection
from backend.models import Appointment, AppointmentStatus




def _make_appointment_id(db: DatabaseConnection) -> str:
    """Generate the next available APT-YYYY-NNN identifier.

    Args:
        db: Active DatabaseConnection.

    Returns:
        A new appointment_id string.
    """
    year = datetime.utcnow().year
    prefix = f"APT-{year}-"

    try:
        latest = (
            db.get_collection("appointments")
            .find({"appointment_id": {"$regex": f"^{prefix}"}}, {"appointment_id": 1})
            .sort("appointment_id", -1)
            .limit(1)
        )
        latest_list = list(latest)
        if latest_list:
            last_num = int(latest_list[0]["appointment_id"].split("-")[-1])
            return f"{prefix}{last_num + 1:03d}"
    except Exception:
        pass

    return f"{prefix}001"


def _fetch_patients(db: DatabaseConnection) -> list[dict]:
    """Fetch all active patients for the dropdown selector.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of patient dicts with patient_id, first_name, last_name.
    """
    try:
        return list(
            db.get_collection("patients")
            .find(
                {"is_active": True},
                {"_id": 0, "patient_id": 1, "first_name": 1, "last_name": 1},
            )
            .sort("last_name", 1)
        )
    except PyMongoError:
        return []


def _fetch_departments(db: DatabaseConnection) -> list[dict]:
    """Fetch all departments for the filter dropdown.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of department dicts with department_id and department_name.
    """
    try:
        return list(
            db.get_collection("departments")
            .find({}, {"_id": 0, "department_id": 1, "department_name": 1})
            .sort("department_name", 1)
        )
    except PyMongoError:
        return []


def _fetch_physicians(
    db: DatabaseConnection, department_id: str = ""
) -> list[dict]:
    """Fetch physicians, optionally filtered by department.

    Args:
        db: Active DatabaseConnection.
        department_id: If provided, only return physicians in this department.

    Returns:
        List of physician dicts.
    """
    try:
        query: dict[str, Any] = {"is_active": True}
        if department_id:
            query["department_id"] = department_id

        return list(
            db.get_collection("physicians")
            .find(
                query,
                {
                    "_id": 0,
                    "physician_id": 1,
                    "first_name": 1,
                    "last_name": 1,
                    "speciality": 1,
                    "department_id": 1,
                },
            )
            .sort("last_name", 1)
        )
    except PyMongoError:
        return []


def _render_schedule_form(db: DatabaseConnection) -> None:
    """Render the appointment scheduling form in a two-column grid.

    Department filter lives OUTSIDE the form so it triggers a page rerun
    immediately, updating the physician dropdown in real time.

    Args:
        db: Active DatabaseConnection.
    """
    # Success state
    if st.session_state.get("appt_success_id"):
        st.success(f"Appointment Scheduled: {st.session_state['appt_success_id']}")
        if st.button("Schedule Another", type="primary"):
            st.session_state.pop("appt_success_id", None)
            st.rerun()
        return

    with st.spinner("Loading patients and departments..."):
        patients = _fetch_patients(db)
        departments = _fetch_departments(db)

    if not patients:
        st.warning("No active patients found. Register a patient first.")
        return

    # Department filter OUTSIDE the form for reactivity
    dept_options: dict[str, str] = {"All Departments": ""}
    dept_options.update(
        {d["department_name"]: d["department_id"] for d in departments}
    )
    selected_dept = st.selectbox(
        "Filter Physicians by Department",
        options=list(dept_options.keys()),
        key="appt_dept_filter",
        help="Changing this updates the physician list instantly.",
    )

    dept_id = dept_options.get(selected_dept, "")
    physicians = _fetch_physicians(db, dept_id)

    if not physicians:
        st.warning("No physicians found in the selected department.")
        return

    # Build option maps
    patient_options = {
        f"{p['first_name']} {p['last_name']} ({p['patient_id']})": p["patient_id"]
        for p in patients
    }
    physician_options = {
        f"Dr. {p['first_name']} {p['last_name']} -- {p['speciality']}": p[
            "physician_id"
        ]
        for p in physicians
    }

    # Booking form -- two column grid
    with st.form("schedule_appointment_form", clear_on_submit=False):
        col_left, col_right = st.columns(2)

        with col_left:
            selected_patient = st.selectbox(
                "Select Patient *",
                options=list(patient_options.keys()),
            )
            selected_physician = st.selectbox(
                "Select Physician *",
                options=list(physician_options.keys()),
            )

        with col_right:
            tomorrow = datetime.now() + timedelta(days=1)
            appt_date = st.date_input(
                "Appointment Date *", value=tomorrow.date()
            )
            appt_time = st.time_input(
                "Appointment Time *",
                value=tomorrow.replace(hour=10, minute=0).time(),
            )

        reason = st.text_area(
            "Reason for Appointment *", placeholder="Routine checkup"
        )

        submitted = st.form_submit_button(
            "Schedule Appointment", type="primary", use_container_width=True
        )

    if submitted:
        errors: list[str] = []

        if not selected_patient or selected_patient not in patient_options:
            errors.append("Please select a patient")
        if not selected_physician or selected_physician not in physician_options:
            errors.append("Please select a physician")
        if not reason.strip():
            errors.append("Reason is required")

        appt_datetime = datetime.combine(appt_date, appt_time)
        if appt_datetime <= datetime.now():
            errors.append("Appointment must be scheduled in the future")

        if errors:
            for error in errors:
                st.error(error)
            return

        with st.spinner("Scheduling appointment..."):
            try:
                appointment = Appointment(
                    appointment_id=_make_appointment_id(db),
                    patient_id=patient_options[selected_patient],
                    physician_id=physician_options[selected_physician],
                    appointment_date_and_time=appt_datetime,
                    reason=reason.strip(),
                )

                created_id = create_appointment(
                    db, appointment, performed_by="reception_desk"
                )
                st.session_state["appt_success_id"] = created_id
                st.rerun()

            except ValueError as exc:
                st.error(f"Scheduling conflict: {exc}")
            except RuntimeError as exc:
                st.error(f"Database error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")


def _render_existing_appointments(db: DatabaseConnection) -> None:
    """Display existing appointments as a clean st.dataframe.

    Args:
        db: Active DatabaseConnection.
    """
    status_filter = st.selectbox(
        "Filter by Status",
        options=["All"] + [s.value.title() for s in AppointmentStatus],
        key="appt_status_filter",
    )

    try:
        with st.spinner("Loading appointments..."):
            query: dict[str, Any] = {}
            if status_filter != "All":
                query["status"] = status_filter.lower()

            pipeline: list[dict[str, Any]] = []
            if query:
                pipeline.append({"$match": query})

            pipeline.extend([
                {
                    "$lookup": {
                        "from": "patients",
                        "localField": "patient_id",
                        "foreignField": "patient_id",
                        "as": "patient",
                    }
                },
                {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
                {
                    "$lookup": {
                        "from": "physicians",
                        "localField": "physician_id",
                        "foreignField": "physician_id",
                        "as": "physician",
                    }
                },
                {"$unwind": {"path": "$physician", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        "_id": 0,
                        "appointment_id": 1,
                        "patient_name": {
                            "$concat": ["$patient.first_name", " ", "$patient.last_name"]
                        },
                        "patient_id": 1,
                        "physician_name": {
                            "$concat": [
                                "Dr. ",
                                "$physician.first_name",
                                " ",
                                "$physician.last_name",
                            ]
                        },
                        "speciality": "$physician.speciality",
                        "appointment_date_and_time": 1,
                        "reason": 1,
                        "status": 1,
                    }
                },
                {"$sort": {"appointment_date_and_time": -1}},
            ])

            results = list(db.get_collection("appointments").aggregate(pipeline))

        if not results:
            st.info("No appointments found matching the selected filter.")
            return

        # Build dataframe rows
        rows: list[dict[str, Any]] = []
        for appt in results:
            dt = appt.get("appointment_date_and_time")
            dt_str = dt.strftime("%d %b %Y, %I:%M %p") if hasattr(dt, "strftime") else str(dt)

            rows.append({
                "ID": appt.get("appointment_id", ""),
                "Patient": appt.get("patient_name", "Unknown"),
                "Physician": appt.get("physician_name", "N/A"),
                "Speciality": appt.get("speciality", ""),
                "Date & Time": dt_str,
                "Reason": appt.get("reason", ""),
                "Status": str(appt.get("status", "")).title(),
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

    except PyMongoError as exc:
        st.error(f"Database error loading appointments: {exc}")
    except Exception as exc:
        st.error(f"Error loading appointments: {exc}")


def render(db: DatabaseConnection) -> None:
    """Render the appointments page with scheduling form and list view.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("Appointments")
    st.caption("Schedule new appointments and manage existing ones.")

    tab1, tab2 = st.tabs(["Schedule New", "View Existing"])

    with tab1:
        _render_schedule_form(db)

    with tab2:
        _render_existing_appointments(db)
