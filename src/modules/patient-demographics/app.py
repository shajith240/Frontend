"""Main Streamlit entry point for Module 1 — Patient Demographics & Visit History.

Connects to MongoDB Atlas on startup, injects the dark clinical theme,
renders the sidebar for navigation, and routes to the appropriate page.
The home dashboard features live metrics, Plotly charts, activity feed,
and auto-refresh every 30 seconds.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    api_explorer,
)
from frontend.styles import (
    inject_css,
    PLOTLY_LAYOUT,
    PLOTLY_CONFIG,
    CHART_COLORS,
    SUCCESS,
    WARNING,
    DANGER,
    PRIMARY,
    TEXT,
    TEXT_MUTED,
    NAVY_CARD,
)

load_dotenv()


# ── Cached data fetchers (TTL 30s) ─────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _get_dashboard_stats(_db_id: int, db: DatabaseConnection) -> dict[str, Any]:
    """Fetch all dashboard metrics in one pass.

    Args:
        _db_id: Hash key for caching (id of db object).
        db: Active DatabaseConnection.

    Returns:
        Dict with metric values and deltas.
    """
    stats: dict[str, Any] = {
        "total_patients": 0,
        "total_visits": 0,
        "active_alerts": 0,
        "total_referrals": 0,
        "pending_referrals": 0,
        "patients_this_week": 0,
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

    try:
        stats["pending_referrals"] = db.get_collection("referrals").count_documents(
            {"status": "pending"}
        )
    except PyMongoError:
        pass

    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        stats["patients_this_week"] = db.get_collection("patients").count_documents(
            {"created_at": {"$gte": week_ago}}
        )
    except PyMongoError:
        pass

    return stats


@st.cache_data(ttl=30, show_spinner=False)
def _get_visits_by_month(_db_id: int, db: DatabaseConnection) -> list[dict]:
    """Aggregate visit counts grouped by month for the bar chart.

    Args:
        _db_id: Cache key.
        db: Active DatabaseConnection.

    Returns:
        List of dicts with year, month, count.
    """
    try:
        pipeline = [
            {
                "$addFields": {
                    "year": {"$year": "$visit_date"},
                    "month": {"$month": "$visit_date"},
                }
            },
            {"$group": {"_id": {"year": "$year", "month": "$month"}, "count": {"$sum": 1}}},
            {"$sort": {"_id.year": 1, "_id.month": 1}},
            {"$limit": 12},
        ]
        results = list(db.get_collection("visits").aggregate(pipeline))
        return [
            {
                "month": f"{r['_id']['year']}-{r['_id']['month']:02d}",
                "count": r["count"],
            }
            for r in results
        ]
    except PyMongoError:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def _get_diagnosis_distribution(_db_id: int, db: DatabaseConnection) -> list[dict]:
    """Aggregate top diagnoses for the donut chart.

    Args:
        _db_id: Cache key.
        db: Active DatabaseConnection.

    Returns:
        List of dicts with diagnosis name and count.
    """
    try:
        pipeline = [
            {"$match": {"diagnosis": {"$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$diagnosis", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8},
        ]
        results = list(db.get_collection("visits").aggregate(pipeline))
        return [{"diagnosis": r["_id"], "count": r["count"]} for r in results]
    except PyMongoError:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def _get_recent_patients(_db_id: int, db: DatabaseConnection) -> list[dict]:
    """Fetch 8 most recently registered patients.

    Args:
        _db_id: Cache key.
        db: Active DatabaseConnection.

    Returns:
        List of patient dicts.
    """
    try:
        return list(
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
            .limit(8)
        )
    except PyMongoError:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def _get_recent_activity(_db_id: int, db: DatabaseConnection) -> list[dict]:
    """Fetch the 10 most recent audit log entries for the activity feed.

    Args:
        _db_id: Cache key.
        db: Active DatabaseConnection.

    Returns:
        List of audit log dicts.
    """
    try:
        return list(
            db.get_collection("audit_logs")
            .find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(10)
        )
    except PyMongoError:
        return []


# ── Dashboard rendering ─────────────────────────────────────────────────────

def _render_metric_cards(stats: dict[str, Any]) -> None:
    """Render the 4 hero metric cards with trend badges.

    Args:
        stats: Dashboard statistics dict.
    """
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        week_badge = f"+{stats['patients_this_week']}" if stats["patients_this_week"] > 0 else "0"
        st.metric(
            "Total Patients",
            stats["total_patients"],
            delta=f"{week_badge} this week",
        )

    with c2:
        st.metric("Total Visits", stats["total_visits"])

    with c3:
        alert_count = stats["active_alerts"]
        if alert_count > 0:
            st.markdown(
                f"""<div style="position:relative;">
                    <span style="position:absolute; top:8px; right:12px;
                        width:8px; height:8px; border-radius:50%; background:#EF4444;
                        animation: pulse 1.5s ease-in-out infinite;
                        box-shadow: 0 0 10px rgba(239,68,68,0.8);"></span>
                </div>
                <style>
                @keyframes pulse {{
                    0%, 100% {{ opacity:1; box-shadow: 0 0 10px rgba(239,68,68,0.8); }}
                    50% {{ opacity:0.4; box-shadow: 0 0 4px rgba(239,68,68,0.3); }}
                }}
                </style>""",
                unsafe_allow_html=True,
            )
        st.metric("Active Alerts", alert_count)

    with c4:
        pending = stats["pending_referrals"]
        st.metric(
            "Total Referrals",
            stats["total_referrals"],
            delta=f"{pending} pending" if pending > 0 else None,
        )


def _render_charts(db: DatabaseConnection) -> None:
    """Render the two side-by-side Plotly charts.

    Args:
        db: Active DatabaseConnection.
    """
    db_id = id(db)
    left, right = st.columns(2)

    with left:
        st.markdown(
            '<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; '
            'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">'
            "Visits by Month</p>",
            unsafe_allow_html=True,
        )
        monthly = _get_visits_by_month(db_id, db)
        if monthly:
            df = pd.DataFrame(monthly)
            fig = px.bar(
                df, x="month", y="count",
                color_discrete_sequence=[PRIMARY],
            )
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_layout(
                xaxis_title="", yaxis_title="Visits",
                height=320,
                bargap=0.3,
            )
            fig.update_traces(marker_line_width=0, marker_cornerradius=4)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("No visit data available for chart.")

    with right:
        st.markdown(
            '<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; '
            'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">'
            "Diagnosis Distribution</p>",
            unsafe_allow_html=True,
        )
        diagnoses = _get_diagnosis_distribution(db_id, db)
        if diagnoses:
            df = pd.DataFrame(diagnoses)
            fig = px.pie(
                df, names="diagnosis", values="count",
                hole=0.55,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_layout(height=320, showlegend=True)
            fig.update_traces(
                textposition="inside",
                textinfo="percent",
                textfont_size=11,
                marker=dict(line=dict(color="#0A0F1E", width=2)),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("No diagnosis data available for chart.")


def _render_recent_patients(db: DatabaseConnection) -> None:
    """Display recent patients with avatar initials color-coded by gender.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; '
        'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px;">'
        "Recent Patients</p>",
        unsafe_allow_html=True,
    )

    patients = _get_recent_patients(id(db), db)
    if not patients:
        st.info("No patients registered yet.")
        return

    for p in patients:
        first = p.get("first_name", "?")
        last = p.get("last_name", "?")
        initials = f"{first[0]}{last[0]}".upper()
        gender = str(p.get("gender", "")).lower()

        # Color by gender
        if gender == "male":
            avatar_bg = PRIMARY
        elif gender == "female":
            avatar_bg = "#EC4899"
        else:
            avatar_bg = "#8B5CF6"

        created = p.get("created_at")
        date_str = created.strftime("%d %b %Y") if hasattr(created, "strftime") else ""

        st.markdown(
            f"""<div style="display:flex; align-items:center; gap:12px; padding:8px 12px;
                    border-radius:8px; margin-bottom:4px;
                    background:rgba(30,41,59,0.3); transition:background 0.2s;">
                <div style="width:36px; height:36px; border-radius:50%;
                    background:{avatar_bg}; display:flex; align-items:center;
                    justify-content:center; font-size:0.75rem; font-weight:700;
                    color:white; flex-shrink:0;">{initials}</div>
                <div style="flex:1; min-width:0;">
                    <div style="font-weight:600; font-size:0.85rem; color:#F8FAFC;">
                        {first} {last}</div>
                    <div style="font-size:0.7rem; color:#94A3B8;">
                        {p.get('patient_id', '')} &middot; Age {p.get('age', 'N/A')}
                        &middot; {date_str}</div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_activity_feed(db: DatabaseConnection) -> None:
    """Display the last 10 audit log entries as a real-time activity feed.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; '
        'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px;">'
        "Activity Feed</p>",
        unsafe_allow_html=True,
    )

    logs = _get_recent_activity(id(db), db)
    if not logs:
        st.info("No activity recorded yet.")
        return

    action_colors = {
        "create": SUCCESS,
        "read": PRIMARY,
        "update": WARNING,
        "delete": DANGER,
    }

    for log in logs:
        action = str(log.get("action", "")).lower()
        color = action_colors.get(action, TEXT_MUTED)
        ts = log.get("timestamp")
        ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else ""
        collection = log.get("collection_name", "")
        performed_by = log.get("performed_by", "system")
        doc_id = log.get("document_id", "")

        st.markdown(
            f"""<div style="display:flex; align-items:flex-start; gap:10px;
                    padding:6px 10px; border-left:2px solid {color};
                    margin-bottom:4px; border-radius:0 4px 4px 0;
                    background:rgba(30,41,59,0.2);">
                <span style="font-size:0.65rem; color:#64748B; font-family:monospace;
                    white-space:nowrap; padding-top:2px;">{ts_str}</span>
                <div style="flex:1; min-width:0;">
                    <span style="font-size:0.75rem; font-weight:600; color:{color};
                        text-transform:uppercase;">{action}</span>
                    <span style="font-size:0.75rem; color:#94A3B8;">
                        &nbsp;{collection}</span>
                    <div style="font-size:0.65rem; color:#64748B; margin-top:1px;">
                        {doc_id} &middot; {performed_by}</div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_home(db: DatabaseConnection) -> None:
    """Render the Home dashboard page with metrics, charts, and feeds.

    Args:
        db: Active DatabaseConnection.
    """
    # Top navbar
    nav_l, nav_c, nav_r = st.columns([2, 2, 1])
    with nav_l:
        st.markdown(
            '<h2 style="margin:0; font-size:1.4rem;">Dashboard</h2>',
            unsafe_allow_html=True,
        )
    with nav_c:
        pass  # Connection indicator is in sidebar
    with nav_r:
        now = datetime.now().strftime("%d %b %Y, %I:%M %p")
        st.markdown(
            f'<p style="text-align:right; color:#94A3B8; font-size:0.8rem; '
            f'margin:8px 0 0 0;">{now}</p>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Metric cards
    with st.spinner("Loading metrics..."):
        stats = _get_dashboard_stats(id(db), db)
    _render_metric_cards(stats)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Charts
    _render_charts(db)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Bottom section: recent patients + activity feed
    left, right = st.columns([3, 2])
    with left:
        _render_recent_patients(db)
    with right:
        _render_activity_feed(db)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Active alerts section
    alerts_component.render(db)

    # Auto-refresh every 30 seconds
    st.markdown(
        """<script>
        setTimeout(function() {
            window.parent.postMessage({type: 'streamlit:rerun'}, '*');
        }, 30000);
        </script>""",
        unsafe_allow_html=True,
    )


def main() -> None:
    """Application entry point — configure page, connect to DB, and route pages."""
    st.set_page_config(
        page_title="Patient Demographics — Clinical Dashboard",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Inject dark clinical theme
    inject_css()

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
    if not is_connected:
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
        "api_explorer": api_explorer.render,
        "dbms_demo": dbms_demo.render,
    }

    page_fn = page_router.get(selected_page, _render_home)

    try:
        page_fn(db)
    except Exception as exc:
        st.error(f"Page error: {exc}")

    # Footer
    st.divider()
    st.markdown(
        '<p style="text-align:center; font-size:0.7rem; color:#475569; '
        'letter-spacing:0.05em;">'
        "Module 1 — Patient Demographics & Visit History &middot; "
        "IIT(ISM) Dhanbad &middot; DBMS Project 2025</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
