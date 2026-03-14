"""Main Streamlit entry point for Module 1 — Patient Demographics & Visit History.

Connects to MongoDB Atlas on startup, renders the sidebar for navigation,
and routes to the appropriate page based on user selection.
"""

import sys
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

# Ensure the module root is on sys.path so all relative imports resolve
_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.database import DatabaseConnection
from frontend.components import sidebar
from frontend.components import alerts as alerts_component
from frontend.pages import (
    register_patient,
    visit_history,
    appointments,
    referrals,
    dbms_demo,
)

load_dotenv()


def _get_dashboard_stats(db: DatabaseConnection) -> dict[str, int]:
    """Fetch the four dashboard metric values.

    Args:
        db: Active DatabaseConnection.

    Returns:
        Dict with total_patients, total_visits, active_alerts, total_referrals.
    """
    stats: dict[str, int] = {
        "total_patients": 0,
        "total_visits": 0,
        "active_alerts": 0,
        "total_referrals": 0,
    }

    try:
        stats["total_patients"] = db.get_collection("patients").count_documents(
            {"is_active": True}
        )
    except PyMongoError:
        pass

    try:
        stats["total_visits"] = db.get_collection("visits").count_documents({})
    except PyMongoError:
        pass

    try:
        stats["active_alerts"] = db.get_collection("alerts").count_documents(
            {"is_acknowledged": False}
        )
    except PyMongoError:
        pass

    try:
        stats["total_referrals"] = db.get_collection("referrals").count_documents({})
    except PyMongoError:
        pass

    return stats


def _render_recent_patients(db: DatabaseConnection) -> None:
    """Display a table of the 5 most recently registered patients.

    Args:
        db: Active DatabaseConnection.
    """
    try:
        patients = list(
            db.get_collection("patients")
            .find(
                {},
                {
                    "_id": 0,
                    "patient_id": 1,
                    "first_name": 1,
                    "last_name": 1,
                    "age": 1,
                    "gender": 1,
                    "phone": 1,
                    "created_at": 1,
                },
            )
            .sort("created_at", -1)
            .limit(5)
        )

        if not patients:
            st.info("No patients registered yet. Use the Register Patient page to add one.")
            return

        display: list[dict[str, Any]] = []
        for p in patients:
            created = p.get("created_at")
            date_str = (
                created.strftime("%d %b %Y")
                if hasattr(created, "strftime")
                else str(created)
            )
            display.append({
                "Patient ID": p.get("patient_id", ""),
                "Name": f"{p.get('first_name', '')} {p.get('last_name', '')}",
                "Age": p.get("age", "N/A"),
                "Gender": str(p.get("gender", "")).title(),
                "Phone": p.get("phone", ""),
                "Registered": date_str,
            })

        st.dataframe(display, use_container_width=True, hide_index=True)
    except PyMongoError as exc:
        st.error(f"Could not load recent patients: {exc}")


def _render_recent_visits(db: DatabaseConnection) -> None:
    """Display a table of the 5 most recent clinical visits.

    Args:
        db: Active DatabaseConnection.
    """
    try:
        pipeline: list[dict[str, Any]] = [
            {"$sort": {"visit_date": -1}},
            {"$limit": 5},
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
                    "visit_id": 1,
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
                    "visit_date": 1,
                    "reason": 1,
                    "diagnosis": 1,
                    "status": 1,
                }
            },
        ]

        visits = list(db.get_collection("visits").aggregate(pipeline))

        if not visits:
            st.info("No visits recorded yet.")
            return

        display: list[dict[str, Any]] = []
        for v in visits:
            vd = v.get("visit_date")
            date_str = (
                vd.strftime("%d %b %Y") if hasattr(vd, "strftime") else str(vd)
            )
            display.append({
                "Visit ID": v.get("visit_id", ""),
                "Patient": v.get("patient_name", "Unknown"),
                "Physician": v.get("physician_name", "N/A"),
                "Date": date_str,
                "Reason": v.get("reason", ""),
                "Diagnosis": v.get("diagnosis", "Pending"),
                "Status": str(v.get("status", "")).title(),
            })

        st.dataframe(display, use_container_width=True, hide_index=True)
    except PyMongoError as exc:
        st.error(f"Could not load recent visits: {exc}")


def _render_home(db: DatabaseConnection) -> None:
    """Render the Home dashboard page.

    Shows 4 metric cards, recent patients table, and recent visits table.

    Args:
        db: Active DatabaseConnection.
    """
    st.header("Dashboard")

    # Metric cards
    with st.spinner("Loading dashboard metrics..."):
        stats = _get_dashboard_stats(db)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Patients", stats["total_patients"])
    col2.metric("Total Visits", stats["total_visits"])
    col3.metric("Active Alerts", stats["active_alerts"])
    col4.metric("Total Referrals", stats["total_referrals"])

    st.divider()

    # Recent patients
    st.subheader("Recent Patients")
    _render_recent_patients(db)

    st.divider()

    # Recent visits
    st.subheader("Recent Visits")
    _render_recent_visits(db)

    # Active alerts section
    st.divider()
    alerts_component.render(db)


def main() -> None:
    """Application entry point — configure page, connect to DB, and route pages."""
    st.set_page_config(
        page_title="Module 1 — Patient Demographics & Visit History",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Connect to MongoDB Atlas on startup — cache in session state
    if "db" not in st.session_state:
        db = DatabaseConnection()
        try:
            db.connect()
            st.session_state["db"] = db
            st.session_state["db_connected"] = True
        except (ConnectionError, ValueError) as exc:
            st.session_state["db"] = db
            st.session_state["db_connected"] = False
            st.session_state["db_error"] = str(exc)

    db: DatabaseConnection = st.session_state["db"]
    is_connected: bool = st.session_state.get("db_connected", False)

    # Connection status banner
    if is_connected:
        st.success("Connected to MongoDB Atlas")
    else:
        error_msg = st.session_state.get("db_error", "Unknown connection error")
        st.error(
            f"Could not connect to MongoDB Atlas: {error_msg}\n\n"
            "Please check your `.env` file has a valid `MONGODB_URI` and that "
            "your IP is whitelisted in the Atlas dashboard."
        )
        st.stop()

    # Render sidebar navigation and get selected page
    selected_page = sidebar.render(db)

    # Route to the selected page
    page_router: dict[str, Any] = {
        "home": _render_home,
        "register_patient": register_patient.render,
        "visit_history": visit_history.render,
        "appointments": appointments.render,
        "referrals": referrals.render,
        "dbms_demo": dbms_demo.render,
    }

    page_fn = page_router.get(selected_page, _render_home)

    try:
        page_fn(db)
    except Exception as exc:
        st.error(f"Page error: {exc}")

    # Footer
    st.divider()
    st.caption(
        "Module 1 — Patient Demographics & Visit History | "
        "IIT(ISM) Dhanbad | DBMS Project 2025"
    )


if __name__ == "__main__":
    main()
