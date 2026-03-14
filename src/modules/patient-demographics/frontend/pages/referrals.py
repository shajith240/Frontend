"""Referrals page — network graph, urgency cards, and status pipeline.

Features:
- Plotly network graph: physicians as nodes, referrals as edges
- Referral cards with urgency color coding
- Status pipeline: Pending -> Active -> Completed progress steps
- Create referral form with validation
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import create_referral
from backend.database import DatabaseConnection
from backend.models import Referral, ReferralStatus
from database.queries.aggregations import get_referral_network_summary
from frontend.styles import PLOTLY_LAYOUT, PLOTLY_CONFIG, CHART_COLORS

load_dotenv()


def _make_referral_id(db: DatabaseConnection) -> str:
    """Generate the next available REF-YYYY-NNN identifier.

    Args:
        db: Active DatabaseConnection.

    Returns:
        A new referral_id string.
    """
    year = datetime.utcnow().year
    prefix = f"REF-{year}-"

    try:
        latest = (
            db.get_collection("referrals")
            .find({"referral_id": {"$regex": f"^{prefix}"}}, {"referral_id": 1})
            .sort("referral_id", -1)
            .limit(1)
        )
        latest_list = list(latest)
        if latest_list:
            last_num = int(latest_list[0]["referral_id"].split("-")[-1])
            return f"{prefix}{last_num + 1:03d}"
    except Exception:
        pass

    return f"{prefix}001"


def _fetch_patients(db: DatabaseConnection) -> list[dict]:
    """Fetch all active patients for the dropdown.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of patient dicts.
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


def _fetch_physicians(db: DatabaseConnection) -> list[dict]:
    """Fetch all active physicians for source/target dropdowns.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of physician dicts.
    """
    try:
        return list(
            db.get_collection("physicians")
            .find(
                {"is_active": True},
                {
                    "_id": 0,
                    "physician_id": 1,
                    "first_name": 1,
                    "last_name": 1,
                    "speciality": 1,
                },
            )
            .sort("last_name", 1)
        )
    except PyMongoError:
        return []


def _render_network_graph(db: DatabaseConnection) -> None:
    """Render the referral network as a Plotly node-edge graph.

    Physicians are nodes, referrals are edges, edge thickness = referral count.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; '
        'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px;">'
        "Referral Network</p>",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Loading referral network..."):
            network = get_referral_network_summary(db)

        if not network:
            st.info("No referral patterns found yet. Create referrals to build the network.")
            return

        # Build node and edge data
        physicians: dict[str, dict] = {}
        edges: list[dict] = []

        for entry in network:
            src_name = entry.get("source_physician_name", "Unknown")
            src_spec = entry.get("source_speciality", "")
            tgt_name = entry.get("target_physician_name", "Unknown")
            tgt_spec = entry.get("target_speciality", "")
            count = entry.get("referral_count", 1)

            if src_name not in physicians:
                physicians[src_name] = {"speciality": src_spec}
            if tgt_name not in physicians:
                physicians[tgt_name] = {"speciality": tgt_spec}

            edges.append({"from": src_name, "to": tgt_name, "count": count})

        # Position nodes in a circle
        import math

        node_names = list(physicians.keys())
        n = len(node_names)
        positions: dict[str, tuple[float, float]] = {}

        for i, name in enumerate(node_names):
            angle = 2 * math.pi * i / n
            positions[name] = (math.cos(angle), math.sin(angle))

        # Build edge traces
        fig = go.Figure()

        for edge in edges:
            x0, y0 = positions[edge["from"]]
            x1, y1 = positions[edge["to"]]
            width = min(edge["count"] * 2, 8)

            fig.add_trace(go.Scatter(
                x=[x0, x1, None], y=[y0, y1, None],
                mode="lines",
                line=dict(width=width, color="rgba(37,99,235,0.4)"),
                hoverinfo="text",
                text=f"{edge['from']} → {edge['to']}: {edge['count']} referrals",
                showlegend=False,
            ))

        # Build node trace
        node_x = [positions[n][0] for n in node_names]
        node_y = [positions[n][1] for n in node_names]
        node_text = [
            f"{n}<br>{physicians[n]['speciality']}" for n in node_names
        ]

        fig.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(
                size=30,
                color=CHART_COLORS[:n],
                line=dict(width=2, color="#0A0F1E"),
            ),
            text=[n.replace("Dr. ", "") for n in node_names],
            textposition="top center",
            textfont=dict(size=10, color="#F8FAFC"),
            hovertext=node_text,
            hoverinfo="text",
            showlegend=False,
        ))

        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_layout(
            height=400,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )

        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Summary stats
        total_referrals = sum(e["count"] for e in edges)
        st.markdown(
            f'<p style="text-align:center; color:#64748B; font-size:0.75rem;">'
            f"{total_referrals} referrals across {len(edges)} physician pairs</p>",
            unsafe_allow_html=True,
        )

    except RuntimeError as exc:
        st.error(f"Database error: {exc}")
    except Exception as exc:
        st.error(f"Error loading network: {exc}")


def _render_create_form(db: DatabaseConnection) -> None:
    """Render the referral creation form.

    Args:
        db: Active DatabaseConnection.
    """
    # Success state
    if st.session_state.get("referral_success_id"):
        st.markdown(
            f"""<div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3);
                    border-radius:12px; padding:24px; text-align:center; margin-bottom:16px;">
                <span style="font-size:2rem;">✅</span>
                <h3 style="margin:8px 0 4px 0; color:#10B981;">Referral Created</h3>
                <p style="font-family:monospace; font-size:1rem; font-weight:700;">
                    {st.session_state['referral_success_id']}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("Create Another Referral", type="primary"):
            st.session_state.pop("referral_success_id", None)
            st.rerun()
        return

    with st.spinner("Loading patients and physicians..."):
        patients = _fetch_patients(db)
        physicians = _fetch_physicians(db)

    if not patients:
        st.warning("No active patients found. Register a patient first.")
        return

    if len(physicians) < 2:
        st.warning("At least two physicians are needed to create a referral.")
        return

    with st.form("create_referral_form", clear_on_submit=False):
        # Patient selection
        patient_options = {
            f"{p['first_name']} {p['last_name']} ({p['patient_id']})": p["patient_id"]
            for p in patients
        }
        selected_patient = st.selectbox(
            "👤 Select Patient *", options=list(patient_options.keys())
        )

        col1, col2 = st.columns(2)

        with col1:
            source_options = {
                f"Dr. {p['first_name']} {p['last_name']} — {p['speciality']}": p[
                    "physician_id"
                ]
                for p in physicians
            }
            selected_source = st.selectbox(
                "📤 Source Physician (Referring) *",
                options=list(source_options.keys()),
                key="source_physician",
            )

        with col2:
            target_options = {
                f"Dr. {p['first_name']} {p['last_name']} — {p['speciality']}": p[
                    "physician_id"
                ]
                for p in physicians
            }
            selected_target = st.selectbox(
                "📥 Target Physician (Specialist) *",
                options=list(target_options.keys()),
                key="target_physician",
            )

        reason = st.text_area(
            "📋 Reason for Referral *",
            placeholder="Patient requires specialist evaluation for cardiac symptoms",
        )

        urgency = st.selectbox(
            "⚡ Urgency",
            options=["Routine", "Urgent", "Emergency"],
        )

        submitted = st.form_submit_button(
            "Create Referral", type="primary", use_container_width=True
        )

    if submitted:
        errors: list[str] = []

        if not selected_patient or selected_patient not in patient_options:
            errors.append("Please select a patient")
        if not selected_source or selected_source not in source_options:
            errors.append("Please select a source physician")
        if not selected_target or selected_target not in target_options:
            errors.append("Please select a target physician")
        if not reason.strip():
            errors.append("Reason is required")

        # Prevent referring to the same physician
        if (
            selected_source in source_options
            and selected_target in target_options
            and source_options[selected_source] == target_options[selected_target]
        ):
            errors.append("Source and target physician cannot be the same")

        if errors:
            for error in errors:
                st.error(error)
            return

        with st.spinner("Creating referral..."):
            try:
                referral_reason = f"[{urgency.upper()}] {reason.strip()}"

                referral = Referral(
                    referral_id=_make_referral_id(db),
                    patient_id=patient_options[selected_patient],
                    source_physician_id=source_options[selected_source],
                    target_physician_id=target_options[selected_target],
                    reason=referral_reason,
                )

                created_id = create_referral(
                    db, referral, performed_by="clinical_staff"
                )
                st.session_state["referral_success_id"] = created_id
                st.rerun()

            except ValueError as exc:
                st.error(f"Referral failed: {exc}")
            except RuntimeError as exc:
                st.error(f"Database error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")


def _render_referral_list(db: DatabaseConnection) -> None:
    """Display all referrals with urgency colors and status pipeline.

    Args:
        db: Active DatabaseConnection.
    """
    status_filter = st.selectbox(
        "Filter by Status",
        options=["All"] + [s.value.title() for s in ReferralStatus],
        key="referral_status_filter",
    )

    try:
        with st.spinner("Loading referrals..."):
            pipeline: list[dict[str, Any]] = []

            if status_filter != "All":
                pipeline.append({"$match": {"status": status_filter.lower()}})

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
                        "localField": "source_physician_id",
                        "foreignField": "physician_id",
                        "as": "source_doc",
                    }
                },
                {"$unwind": {"path": "$source_doc", "preserveNullAndEmptyArrays": True}},
                {
                    "$lookup": {
                        "from": "physicians",
                        "localField": "target_physician_id",
                        "foreignField": "physician_id",
                        "as": "target_doc",
                    }
                },
                {"$unwind": {"path": "$target_doc", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        "_id": 0,
                        "referral_id": 1,
                        "patient_name": {
                            "$concat": ["$patient.first_name", " ", "$patient.last_name"]
                        },
                        "patient_id": 1,
                        "source_physician": {
                            "$concat": [
                                "Dr. ",
                                "$source_doc.first_name",
                                " ",
                                "$source_doc.last_name",
                            ]
                        },
                        "source_speciality": "$source_doc.speciality",
                        "target_physician": {
                            "$concat": [
                                "Dr. ",
                                "$target_doc.first_name",
                                " ",
                                "$target_doc.last_name",
                            ]
                        },
                        "target_speciality": "$target_doc.speciality",
                        "reason": 1,
                        "status": 1,
                        "referral_date": 1,
                    }
                },
                {"$sort": {"referral_date": -1}},
            ])

            results = list(db.get_collection("referrals").aggregate(pipeline))

        if not results:
            st.info("No referrals found matching the selected filter.")
            return

        # Urgency color mapping
        urgency_colors = {
            "emergency": "#EF4444",
            "urgent": "#F59E0B",
            "routine": "#2563EB",
        }

        # Status pipeline colors
        status_pipeline = {
            "pending": 0,
            "accepted": 1,
            "completed": 2,
            "rejected": -1,
        }

        for ref in results:
            ref_date = ref.get("referral_date")
            date_str = (
                ref_date.strftime("%d %b %Y") if hasattr(ref_date, "strftime") else str(ref_date)
            )

            reason_text = ref.get("reason", "")
            urgency = "routine"
            for u in ["emergency", "urgent", "routine"]:
                if f"[{u.upper()}]" in reason_text:
                    urgency = u
                    break
            urgency_color = urgency_colors.get(urgency, "#2563EB")

            status = str(ref.get("status", "pending")).lower()
            step = status_pipeline.get(status, 0)

            # Build status pipeline visual
            pipeline_html = '<div style="display:flex; gap:4px; align-items:center; margin-top:8px;">'
            steps = ["Pending", "Accepted", "Completed"]
            for i, s in enumerate(steps):
                if status == "rejected":
                    bg = "#EF444430" if i == 0 else "#33415530"
                    text_color = "#EF4444" if i == 0 else "#64748B"
                elif i <= step:
                    bg = "#10B98130"
                    text_color = "#10B981"
                else:
                    bg = "#33415530"
                    text_color = "#64748B"
                pipeline_html += (
                    f'<span style="font-size:0.6rem; padding:2px 8px; border-radius:4px; '
                    f'background:{bg}; color:{text_color}; font-weight:600;">{s}</span>'
                )
                if i < len(steps) - 1:
                    pipeline_html += '<span style="color:#475569;">→</span>'
            if status == "rejected":
                pipeline_html += (
                    '<span style="color:#475569;">→</span>'
                    '<span style="font-size:0.6rem; padding:2px 8px; border-radius:4px; '
                    'background:#EF444430; color:#EF4444; font-weight:600;">Rejected</span>'
                )
            pipeline_html += "</div>"

            st.markdown(
                f"""<div style="background:rgba(30,41,59,0.3); border:1px solid #334155;
                        border-left:3px solid {urgency_color};
                        border-radius:10px; padding:14px 16px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between;
                        align-items:flex-start;">
                        <div>
                            <span style="font-weight:600; font-size:0.85rem;">
                                {ref.get('patient_name', 'Unknown')}</span>
                            <span style="font-size:0.7rem; color:#64748B; margin-left:6px;">
                                {ref.get('referral_id', '')}</span>
                        </div>
                        <span style="font-size:0.65rem; font-weight:700; color:{urgency_color};
                            text-transform:uppercase; background:{urgency_color}20;
                            padding:2px 8px; border-radius:4px;">{urgency}</span>
                    </div>
                    <p style="color:#94A3B8; font-size:0.78rem; margin:6px 0 0 0;">
                        📤 {ref.get('source_physician', 'N/A')} ({ref.get('source_speciality', '')})
                        → 📥 {ref.get('target_physician', 'N/A')} ({ref.get('target_speciality', '')})</p>
                    <p style="color:#64748B; font-size:0.72rem; margin:4px 0 0 0;">
                        {date_str} &middot; {reason_text}</p>
                    {pipeline_html}
                </div>""",
                unsafe_allow_html=True,
            )

    except PyMongoError as exc:
        st.error(f"Database error loading referrals: {exc}")
    except Exception as exc:
        st.error(f"Error loading referrals: {exc}")


def render(db: DatabaseConnection) -> None:
    """Render the referrals page with network graph, create form, and list.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<h2 style="margin-bottom:4px;">Referrals</h2>'
        '<p style="color:#94A3B8; font-size:0.85rem; margin-bottom:16px;">'
        "Create referrals, view the network, and track status.</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs([
        "🔗 Network Graph",
        "📝 Create Referral",
        "📋 All Referrals",
    ])

    with tab1:
        _render_network_graph(db)

    with tab2:
        _render_create_form(db)

    with tab3:
        _render_referral_list(db)
