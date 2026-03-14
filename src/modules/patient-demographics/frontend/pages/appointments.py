"""Appointments page — physician cards, booking form, and status-badged list.

Features:
- Physician cards with speciality, available slots placeholder
- Department filter outside form for reactive physician filtering
- Status badges: scheduled=blue, completed=green, cancelled=gray
- Today's appointments highlighted
- Conflict detection via appointment_conflict_trigger
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import create_appointment
from backend.database import DatabaseConnection
from backend.models import Appointment, AppointmentStatus

load_dotenv()


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


def _render_physician_cards(physicians: list[dict]) -> None:
    """Render physician cards in a grid layout.

    Args:
        physicians: List of physician dicts.
    """
    if not physicians:
        return

    cols = st.columns(min(len(physicians), 3))
    for i, phy in enumerate(physicians):
        with cols[i % 3]:
            name = f"Dr. {phy.get('first_name', '')} {phy.get('last_name', '')}"
            spec = phy.get("speciality", "General")
            initials = f"{phy.get('first_name', '?')[0]}{phy.get('last_name', '?')[0]}".upper()

            st.markdown(
                f"""<div style="background:rgba(30,41,59,0.5); border:1px solid #334155;
                        border-radius:12px; padding:16px; text-align:center;
                        margin-bottom:8px; transition:border-color 0.2s;">
                    <div style="width:48px; height:48px; border-radius:50%;
                        background:#2563EB; display:flex; align-items:center;
                        justify-content:center; font-size:0.9rem; font-weight:700;
                        color:white; margin:0 auto 8px auto;">{initials}</div>
                    <p style="font-weight:600; font-size:0.85rem; margin:0;">{name}</p>
                    <p style="color:#94A3B8; font-size:0.75rem; margin:2px 0 0 0;">{spec}</p>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_schedule_form(db: DatabaseConnection) -> None:
    """Render the appointment scheduling form.

    Department filter lives OUTSIDE the form so it triggers a page rerun
    immediately, updating the physician dropdown in real time.

    Args:
        db: Active DatabaseConnection.
    """
    # Success state
    if st.session_state.get("appt_success_id"):
        st.markdown(
            f"""<div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3);
                    border-radius:12px; padding:24px; text-align:center; margin-bottom:16px;">
                <span style="font-size:2rem;">✅</span>
                <h3 style="margin:8px 0 4px 0; color:#10B981;">Appointment Scheduled</h3>
                <p style="font-family:monospace; font-size:1rem; font-weight:700;">
                    {st.session_state['appt_success_id']}</p>
            </div>""",
            unsafe_allow_html=True,
        )
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

    # Physician cards
    _render_physician_cards(physicians[:6])

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Build option maps
    patient_options = {
        f"{p['first_name']} {p['last_name']} ({p['patient_id']})": p["patient_id"]
        for p in patients
    }
    physician_options = {
        f"Dr. {p['first_name']} {p['last_name']} — {p['speciality']}": p[
            "physician_id"
        ]
        for p in physicians
    }

    # Booking form
    with st.form("schedule_appointment_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            selected_patient = st.selectbox(
                "👤 Select Patient *",
                options=list(patient_options.keys()),
            )

            tomorrow = datetime.now() + timedelta(days=1)
            appt_date = st.date_input(
                "📅 Appointment Date *", value=tomorrow.date()
            )

        with col2:
            selected_physician = st.selectbox(
                "🩺 Select Physician *",
                options=list(physician_options.keys()),
            )
            appt_time = st.time_input(
                "🕐 Appointment Time *",
                value=tomorrow.replace(hour=10, minute=0).time(),
            )

        reason = st.text_area(
            "📋 Reason for Appointment *", placeholder="Routine checkup"
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
    """Display existing appointments with status badges.

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

        # Render as styled cards
        today = datetime.now().date()
        status_colors = {
            "scheduled": "#2563EB",
            "confirmed": "#2563EB",
            "completed": "#10B981",
            "cancelled": "#64748B",
            "no_show": "#F59E0B",
        }

        for appt in results:
            dt = appt.get("appointment_date_and_time")
            dt_str = dt.strftime("%d %b %Y, %I:%M %p") if hasattr(dt, "strftime") else str(dt)
            is_today = hasattr(dt, "date") and dt.date() == today
            status = str(appt.get("status", "")).lower()
            color = status_colors.get(status, "#64748B")

            today_badge = (
                '<span style="font-size:0.6rem; background:#F59E0B; color:#0A0F1E; '
                'padding:1px 6px; border-radius:3px; font-weight:700; margin-left:8px;">'
                "TODAY</span>"
                if is_today
                else ""
            )

            st.markdown(
                f"""<div style="display:flex; align-items:center; gap:12px; padding:12px 16px;
                        background:rgba(30,41,59,0.3); border:1px solid #334155;
                        border-radius:10px; margin-bottom:6px;
                        {'border-left:3px solid #F59E0B;' if is_today else ''}">
                    <div style="flex:1;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span style="font-weight:600; font-size:0.85rem;">
                                {appt.get('patient_name', 'Unknown')}</span>
                            {today_badge}
                        </div>
                        <span style="font-size:0.75rem; color:#94A3B8;">
                            {appt.get('physician_name', 'N/A')} &middot;
                            {appt.get('speciality', '')} &middot; {dt_str}</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.7rem; font-weight:600; color:{color};
                            text-transform:uppercase; background:{color}20;
                            padding:2px 8px; border-radius:4px;">{status}</span>
                        <div style="font-size:0.7rem; color:#64748B; margin-top:2px;">
                            {appt.get('appointment_id', '')}</div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

    except PyMongoError as exc:
        st.error(f"Database error loading appointments: {exc}")
    except Exception as exc:
        st.error(f"Error loading appointments: {exc}")


def render(db: DatabaseConnection) -> None:
    """Render the appointments page with scheduling form and list view.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<h2 style="margin-bottom:4px;">Appointments</h2>'
        '<p style="color:#94A3B8; font-size:0.85rem; margin-bottom:16px;">'
        "Schedule new appointments and manage existing ones.</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📅 Schedule New", "📋 View Existing"])

    with tab1:
        _render_schedule_form(db)

    with tab2:
        _render_existing_appointments(db)
