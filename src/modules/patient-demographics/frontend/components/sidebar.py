"""Sidebar component — navigation, connection status, and quick stats.

Renders the module title, page navigation links, live MongoDB connection
indicator (green/red dot), quick patient/visit/alert counts, and a
refresh button to update stats on demand.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.database import DatabaseConnection

load_dotenv()

# Page registry — maps display names to page module keys
PAGES: dict[str, str] = {
    "Home": "home",
    "Register Patient": "register_patient",
    "Visit History": "visit_history",
    "Appointments": "appointments",
    "Referrals": "referrals",
    "DBMS Demo": "dbms_demo",
}


def _check_connection(db: DatabaseConnection) -> bool:
    """Check if the database connection is alive.

    Args:
        db: DatabaseConnection instance to test.

    Returns:
        True if the connection responds to a ping, False otherwise.
    """
    try:
        db.get_collection("patients").find_one({}, {"_id": 1})
        return True
    except Exception:
        return False


def _get_quick_stats(db: DatabaseConnection) -> dict[str, int]:
    """Fetch quick stats: patients, visits, upcoming appointments, active alerts.

    Args:
        db: Active DatabaseConnection.

    Returns:
        Dict with keys total_patients, total_visits, upcoming_appointments, active_alerts.
    """
    stats: dict[str, int] = {
        "total_patients": 0,
        "total_visits": 0,
        "upcoming_appointments": 0,
        "active_alerts": 0,
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
        stats["upcoming_appointments"] = db.get_collection(
            "appointments"
        ).count_documents(
            {
                "status": {"$in": ["scheduled", "confirmed"]},
                "appointment_date_and_time": {"$gte": datetime.utcnow()},
            }
        )
    except PyMongoError:
        pass

    try:
        stats["active_alerts"] = db.get_collection("alerts").count_documents(
            {"is_acknowledged": False}
        )
    except PyMongoError:
        pass

    return stats


def render(db: DatabaseConnection) -> Optional[str]:
    """Render the sidebar and return the selected page key.

    Displays the module title, navigation radio buttons, live connection
    status, quick stats, and a refresh button.

    Args:
        db: Active DatabaseConnection.

    Returns:
        The page key string for the selected page, or None if no selection.
    """
    with st.sidebar:
        st.title("Module 1")
        st.caption("Patient Demographics & Visit History")
        st.divider()

        # Navigation links
        selected_page = st.radio(
            "Navigation",
            options=list(PAGES.keys()),
            label_visibility="collapsed",
        )

        st.divider()

        # Live connection status
        is_connected = _check_connection(db)
        if is_connected:
            st.markdown(":green_circle: **Connected** to MongoDB Atlas")
        else:
            st.markdown(":red_circle: **Disconnected** from MongoDB Atlas")
            db_error = st.session_state.get("db_error")
            if db_error:
                st.caption(f"Error: {db_error}")

        st.divider()

        # Quick stats
        st.markdown("**Quick Stats**")

        # Use session state to cache stats and support refresh
        if "sidebar_stats" not in st.session_state:
            st.session_state["sidebar_stats"] = _get_quick_stats(db)

        stats = st.session_state["sidebar_stats"]

        stat_col1, stat_col2 = st.columns(2)
        stat_col1.metric("Patients", stats["total_patients"])
        stat_col2.metric("Visits", stats["total_visits"])

        stat_col3, stat_col4 = st.columns(2)
        stat_col3.metric("Appointments", stats["upcoming_appointments"])
        stat_col4.metric("Alerts", stats["active_alerts"])

        # Refresh button
        if st.button("Refresh Stats", use_container_width=True):
            st.session_state["sidebar_stats"] = _get_quick_stats(db)
            st.rerun()

        st.divider()

        # API base URL for cross-module integration
        st.markdown("**REST API**")
        st.code("http://localhost:8000/api", language=None)
        st.caption("Other modules use this URL to query patient data.")

    return PAGES.get(selected_page)
