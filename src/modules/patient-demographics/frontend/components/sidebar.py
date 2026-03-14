"""Sidebar component — dark-themed navigation, connection status, and quick stats.

Renders the module logo, page navigation with icons, live MongoDB connection
indicator with animated pulse, quick stats in a 2x2 grid, and version tag.
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

# Page registry — maps display names to (page_key, icon)
PAGES: dict[str, tuple[str, str]] = {
    "Dashboard": ("home", "📊"),
    "Register Patient": ("register_patient", "📝"),
    "Visit History": ("visit_history", "🕐"),
    "Appointments": ("appointments", "📅"),
    "Referrals": ("referrals", "🔗"),
    "API Explorer": ("api_explorer", "🚀"),
    "DBMS Demo": ("dbms_demo", "🧪"),
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

    Displays module branding, icon-based navigation, live connection
    status with animated pulse, quick stats in a 2x2 grid, and version tag.

    Args:
        db: Active DatabaseConnection.

    Returns:
        The page key string for the selected page, or None if no selection.
    """
    with st.sidebar:
        # Module branding
        st.markdown(
            """
            <div style="text-align:center; padding: 8px 0 4px 0;">
                <span style="font-size:2rem;">🏥</span>
                <h3 style="margin:4px 0 0 0; font-size:1.1rem; font-weight:700;
                    letter-spacing:-0.02em;">Patient Demographics</h3>
                <p style="color:#94A3B8; font-size:0.7rem; margin:2px 0 0 0;
                    text-transform:uppercase; letter-spacing:0.08em;">
                    Module 1 — Visit History
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # Navigation with icons
        page_labels = [f"{icon}  {name}" for name, (_, icon) in PAGES.items()]
        selected_label = st.radio(
            "Navigation",
            options=page_labels,
            label_visibility="collapsed",
        )

        # Map label back to page key
        selected_key = "home"
        for name, (key, icon) in PAGES.items():
            if selected_label == f"{icon}  {name}":
                selected_key = key
                break

        st.divider()

        # Live connection status with pulse animation
        is_connected = _check_connection(db)
        if is_connected:
            st.markdown(
                """<div style="display:flex; align-items:center; gap:8px; padding:4px 0;">
                    <span style="display:inline-block; width:8px; height:8px;
                        border-radius:50%; background:#10B981;
                        box-shadow: 0 0 8px rgba(16,185,129,0.6);
                        animation: pulse 2s ease-in-out infinite;"></span>
                    <span style="font-size:0.8rem; font-weight:600; color:#10B981;">
                        Connected to MongoDB Atlas
                    </span>
                </div>
                <style>
                @keyframes pulse {
                    0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(16,185,129,0.6); }
                    50% { opacity: 0.6; box-shadow: 0 0 4px rgba(16,185,129,0.3); }
                }
                </style>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """<div style="display:flex; align-items:center; gap:8px; padding:4px 0;">
                    <span style="display:inline-block; width:8px; height:8px;
                        border-radius:50%; background:#EF4444;
                        box-shadow: 0 0 8px rgba(239,68,68,0.6);"></span>
                    <span style="font-size:0.8rem; font-weight:600; color:#EF4444;">
                        Disconnected
                    </span>
                </div>""",
                unsafe_allow_html=True,
            )
            db_error = st.session_state.get("db_error")
            if db_error:
                st.caption(f"Error: {db_error}")

        st.divider()

        # Quick stats — 2x2 grid
        st.markdown(
            '<p style="font-size:0.7rem; text-transform:uppercase; '
            'letter-spacing:0.08em; color:#94A3B8; font-weight:600; margin-bottom:8px;">'
            "Quick Stats</p>",
            unsafe_allow_html=True,
        )

        # Use session state to cache stats and support refresh
        if "sidebar_stats" not in st.session_state:
            st.session_state["sidebar_stats"] = _get_quick_stats(db)

        stats = st.session_state["sidebar_stats"]

        stat_col1, stat_col2 = st.columns(2)
        stat_col1.metric("Patients", stats["total_patients"])
        stat_col2.metric("Visits", stats["total_visits"])

        stat_col3, stat_col4 = st.columns(2)
        stat_col3.metric("Appts", stats["upcoming_appointments"])
        stat_col4.metric("Alerts", stats["active_alerts"])

        # Refresh button
        if st.button("↻ Refresh", use_container_width=True):
            st.session_state["sidebar_stats"] = _get_quick_stats(db)
            st.rerun()

        st.divider()

        # API endpoint
        st.markdown(
            '<p style="font-size:0.7rem; text-transform:uppercase; '
            'letter-spacing:0.08em; color:#94A3B8; font-weight:600; margin-bottom:4px;">'
            "REST API</p>",
            unsafe_allow_html=True,
        )
        st.code("http://localhost:8000/api", language=None)

        # Version tag at bottom
        st.markdown(
            """<div style="text-align:center; padding:16px 0 8px 0; margin-top:auto;">
                <span style="font-size:0.65rem; color:#475569; font-weight:500;
                    letter-spacing:0.05em;">
                    v1.0 — IIT(ISM) Dhanbad — DBMS Project 2025
                </span>
            </div>""",
            unsafe_allow_html=True,
        )

    return selected_key
