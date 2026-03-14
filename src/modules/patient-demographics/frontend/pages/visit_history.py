"""Visit history page — hero search bar with vertical timeline design.

Centered search, patient profile card with avatar, vertical timeline
with status-colored dots, tabbed view for visits/appointments/referrals,
and CSV export.
"""

import io
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import get_patient_by_id, search_patients
from backend.database import DatabaseConnection
from database.queries.aggregations import get_patient_full_profile

load_dotenv()


def _render_patient_card(patient: dict) -> None:
    """Display the patient profile card with avatar and key stats.

    Args:
        patient: Patient document dict from get_patient_full_profile.
    """
    first = patient.get("first_name", "?")
    last = patient.get("last_name", "?")
    initials = f"{first[0]}{last[0]}".upper()
    gender = str(patient.get("gender", "")).lower()

    if gender == "male":
        avatar_bg = "#2563EB"
    elif gender == "female":
        avatar_bg = "#EC4899"
    else:
        avatar_bg = "#8B5CF6"

    dob = patient.get("date_of_birth")
    dob_str = dob.strftime("%d %b %Y") if hasattr(dob, "strftime") else str(dob) if dob else "—"

    st.markdown(
        f"""<div style="background:rgba(30,41,59,0.6); backdrop-filter:blur(12px);
                border:1px solid #334155; border-radius:16px; padding:24px;
                display:flex; align-items:center; gap:20px; margin-bottom:20px;">
            <div style="width:64px; height:64px; border-radius:50%;
                background:{avatar_bg}; display:flex; align-items:center;
                justify-content:center; font-size:1.4rem; font-weight:800;
                color:white; flex-shrink:0;
                box-shadow:0 4px 15px rgba(0,0,0,0.3);">{initials}</div>
            <div style="flex:1;">
                <h3 style="margin:0; font-size:1.3rem; font-weight:700;">
                    {first} {last}</h3>
                <p style="color:#94A3B8; font-size:0.8rem; margin:4px 0 0 0;
                    font-family:monospace;">{patient.get('patient_id', 'N/A')}</p>
            </div>
            <div style="display:flex; gap:32px;">
                <div style="text-align:center;">
                    <p style="color:#64748B; font-size:0.6rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Age</p>
                    <p style="font-size:1.3rem; font-weight:800; margin:2px 0 0 0;">
                        {patient.get('age', 'N/A')}</p>
                </div>
                <div style="text-align:center;">
                    <p style="color:#64748B; font-size:0.6rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Gender</p>
                    <p style="font-size:1.3rem; font-weight:800; margin:2px 0 0 0;">
                        {gender.title()}</p>
                </div>
                <div style="text-align:center;">
                    <p style="color:#64748B; font-size:0.6rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Phone</p>
                    <p style="font-size:0.9rem; font-weight:600; margin:6px 0 0 0;">
                        {patient.get('phone', '—')}</p>
                </div>
                <div style="text-align:center;">
                    <p style="color:#64748B; font-size:0.6rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Blood</p>
                    <p style="font-size:1.3rem; font-weight:800; margin:2px 0 0 0;">
                        {str(patient.get('blood_group', '—')).upper()}</p>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Demographics expander
    with st.expander("Full Demographics"):
        demo_col1, demo_col2 = st.columns(2)
        with demo_col1:
            st.write(f"**Email:** {patient.get('email', 'Not provided')}")
            st.write(f"**DOB:** {dob_str}")

        with demo_col2:
            address = patient.get("address")
            if address and isinstance(address, dict):
                addr_str = (
                    f"{address.get('street', '')}, {address.get('city', '')}, "
                    f"{address.get('state', '')} - {address.get('postal_code', '')}"
                )
                st.write(f"**Address:** {addr_str}")

            insurance = patient.get("insurance")
            if insurance and isinstance(insurance, dict):
                st.write(f"**Insurance:** {insurance.get('provider', 'N/A')}")
                st.write(f"**Policy:** {insurance.get('policy_number', 'N/A')}")


def _render_visit_timeline(visits: list[dict]) -> None:
    """Display visits as a vertical timeline with status-colored dots.

    Args:
        visits: List of visit dicts from the full profile aggregation.
    """
    status_colors = {
        "active": "#2563EB",
        "completed": "#10B981",
        "discharged": "#F59E0B",
        "cancelled": "#EF4444",
    }

    if not visits:
        st.info("No visits recorded for this patient.")
        return

    # Export button
    if visits:
        export_data = []
        for v in visits:
            vd = v.get("visit_date", "")
            vd_str = vd.strftime("%Y-%m-%d") if hasattr(vd, "strftime") else str(vd)
            export_data.append({
                "Visit ID": v.get("visit_id", ""),
                "Date": vd_str,
                "Reason": v.get("reason", ""),
                "Diagnosis": v.get("diagnosis", ""),
                "Status": v.get("status", ""),
                "Physician": v.get("physician_name", ""),
            })
        df = pd.DataFrame(export_data)
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Export as CSV",
            data=csv,
            file_name="visit_history.csv",
            mime="text/csv",
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for visit in visits:
        visit_date = visit.get("visit_date", "Unknown date")
        if hasattr(visit_date, "strftime"):
            visit_date_str = visit_date.strftime("%d %b %Y")
        else:
            visit_date_str = str(visit_date)

        status = str(visit.get("status", "unknown")).lower()
        color = status_colors.get(status, "#64748B")

        physician_name = visit.get("physician_name", "Not assigned")
        physician_spec = visit.get("physician_speciality", "")
        departments = visit.get("departments", [])
        dept_names = [d.get("department_name", "") for d in departments if d] if departments else []

        st.markdown(
            f"""<div style="display:flex; gap:16px; margin-bottom:4px;">
                <div style="display:flex; flex-direction:column; align-items:center;
                    width:80px; flex-shrink:0; padding-top:4px;">
                    <span style="font-size:0.75rem; font-weight:600; color:#94A3B8;
                        white-space:nowrap;">{visit_date_str}</span>
                    <div style="width:12px; height:12px; border-radius:50%;
                        background:{color}; margin:8px 0;
                        box-shadow:0 0 8px {color}40;"></div>
                    <div style="width:2px; flex:1; background:#334155;"></div>
                </div>
                <div style="flex:1; background:rgba(30,41,59,0.4);
                    border:1px solid #334155; border-radius:12px;
                    padding:16px; margin-bottom:8px;
                    transition:border-color 0.2s ease;">
                    <div style="display:flex; justify-content:space-between;
                        align-items:flex-start; margin-bottom:8px;">
                        <span style="font-weight:600; font-size:0.9rem;">
                            {visit.get('reason', 'No reason recorded')}</span>
                        <span style="font-size:0.7rem; font-weight:600; color:{color};
                            text-transform:uppercase; letter-spacing:0.05em;
                            background:{color}20; padding:2px 8px;
                            border-radius:4px;">{status}</span>
                    </div>
                    <p style="color:#94A3B8; font-size:0.8rem; margin:0;">
                        <strong>Diagnosis:</strong> {visit.get('diagnosis', 'Pending')}</p>
                    <p style="color:#94A3B8; font-size:0.8rem; margin:4px 0 0 0;">
                        <strong>Physician:</strong> {physician_name}
                        {f' — {physician_spec}' if physician_spec else ''}
                        {f' | <strong>Dept:</strong> {", ".join(dept_names)}' if dept_names else ''}
                    </p>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_appointments_tab(appointments: list[dict]) -> None:
    """Display the patient's appointments in a styled table.

    Args:
        appointments: List of appointment dicts from the full profile aggregation.
    """
    if not appointments:
        st.info("No appointments found for this patient.")
        return

    display: list[dict[str, Any]] = []
    for appt in appointments:
        dt = appt.get("appointment_date_and_time")
        dt_str = (
            dt.strftime("%d %b %Y, %I:%M %p")
            if hasattr(dt, "strftime")
            else str(dt)
        )

        physician_name = "Not assigned"
        physician = appt.get("physician")
        if physician and isinstance(physician, dict):
            physician_name = (
                f"Dr. {physician.get('first_name', '')} "
                f"{physician.get('last_name', '')}"
            )
        elif isinstance(physician, list) and physician:
            p = physician[0]
            physician_name = (
                f"Dr. {p.get('first_name', '')} {p.get('last_name', '')}"
            )

        display.append({
            "ID": appt.get("appointment_id", ""),
            "Date & Time": dt_str,
            "Physician": physician_name,
            "Reason": appt.get("reason", ""),
            "Status": str(appt.get("status", "")).title(),
        })

    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_referrals_tab(referrals: list[dict]) -> None:
    """Display the patient's referrals in a styled table.

    Args:
        referrals: List of referral dicts from the full profile aggregation.
    """
    if not referrals:
        st.info("No referrals found for this patient.")
        return

    display: list[dict[str, Any]] = []
    for ref in referrals:
        ref_date = ref.get("referral_date")
        date_str = (
            ref_date.strftime("%d %b %Y")
            if hasattr(ref_date, "strftime")
            else str(ref_date)
        )

        source_name = "N/A"
        source = ref.get("source_physician")
        if source and isinstance(source, dict):
            source_name = f"Dr. {source.get('first_name', '')} {source.get('last_name', '')}"
        elif isinstance(source, list) and source:
            s = source[0]
            source_name = f"Dr. {s.get('first_name', '')} {s.get('last_name', '')}"

        target_name = "N/A"
        target = ref.get("target_physician")
        if target and isinstance(target, dict):
            target_name = f"Dr. {target.get('first_name', '')} {target.get('last_name', '')}"
        elif isinstance(target, list) and target:
            t = target[0]
            target_name = f"Dr. {t.get('first_name', '')} {t.get('last_name', '')}"

        display.append({
            "ID": ref.get("referral_id", ""),
            "Date": date_str,
            "From": source_name,
            "To": target_name,
            "Reason": ref.get("reason", ""),
            "Status": str(ref.get("status", "")).title(),
        })

    st.dataframe(display, use_container_width=True, hide_index=True)


def render(db: DatabaseConnection) -> None:
    """Render the visit history page with hero search and timeline.

    Args:
        db: Active DatabaseConnection.
    """
    # Hero search bar
    st.markdown(
        """<div style="text-align:center; padding:24px 0 8px 0;">
            <h2 style="margin:0; font-size:1.4rem;">Visit History</h2>
            <p style="color:#94A3B8; font-size:0.85rem; margin:4px 0 0 0;">
                Search by Patient ID or name to view their complete clinical record</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # Centered search
    _, search_col, _ = st.columns([1, 3, 1])
    with search_col:
        search_query = st.text_input(
            "Search",
            placeholder="🔍 PAT-2024-001 or Rajesh Sharma",
            key="visit_search",
            label_visibility="collapsed",
        )

    if not search_query.strip():
        st.markdown(
            '<p style="text-align:center; color:#64748B; font-size:0.8rem; '
            'margin-top:40px;">Enter a Patient ID (PAT-YYYY-NNN) or patient name above.</p>',
            unsafe_allow_html=True,
        )
        return

    query = search_query.strip()
    patient_id: Optional[str] = None

    try:
        # Check if the search looks like a patient ID
        if query.upper().startswith("PAT-"):
            with st.spinner("Searching by Patient ID..."):
                patient_doc = get_patient_by_id(
                    db, query.upper(), performed_by="visit_history_page"
                )
            if patient_doc:
                patient_id = patient_doc["patient_id"]
            else:
                st.warning(f"No patient found with ID: {query.upper()}")
                return
        else:
            # Search by name
            with st.spinner("Searching patients..."):
                results = search_patients(db, name=query, is_active=None, limit=10)
            if not results:
                st.warning(f"No patients found matching '{query}'")
                return

            # Always show dropdown for patient confirmation
            _, sel_col, _ = st.columns([1, 3, 1])
            with sel_col:
                options = {
                    f"{r['first_name']} {r['last_name']} ({r['patient_id']})": r["patient_id"]
                    for r in results
                }
                label = (
                    f"{len(results)} patient(s) found — confirm selection:"
                    if len(results) == 1
                    else f"{len(results)} patients found — select one:"
                )
                selected = st.selectbox(label, options=list(options.keys()))
                if selected:
                    patient_id = options[selected]

        if not patient_id:
            return

        # Fetch complete profile
        with st.spinner("Loading patient profile..."):
            profile = get_patient_full_profile(db, patient_id)
        if not profile:
            st.error(f"Could not load full profile for {patient_id}")
            return

        # Patient card
        _render_patient_card(profile)

        # Tabbed view
        visits = profile.get("visits", [])
        appts = profile.get("appointments", [])
        refs = profile.get("referrals", [])

        tab_visits, tab_appts, tab_refs = st.tabs([
            f"🕐 Visits ({len(visits)})",
            f"📅 Appointments ({len(appts)})",
            f"🔗 Referrals ({len(refs)})",
        ])

        with tab_visits:
            _render_visit_timeline(visits)

        with tab_appts:
            _render_appointments_tab(appts)

        with tab_refs:
            _render_referrals_tab(refs)

    except RuntimeError as exc:
        st.error(f"Database error: {exc}")
    except Exception as exc:
        st.error(f"Error loading visit history: {exc}")
