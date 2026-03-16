"""Visit history page — search bar with patient profile and visit dataframe.

Centered search, patient profile card, tabbed view for visits/appointments/referrals,
and CSV export.
"""

import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import get_patient_by_id, search_patients
from backend.database import DatabaseConnection
from database.queries.aggregations import get_patient_full_profile




def _render_patient_card(patient: dict) -> None:
    """Display the patient profile card with key stats.

    Args:
        patient: Patient document dict from get_patient_full_profile.
    """
    first = patient.get("first_name", "?")
    last = patient.get("last_name", "?")
    gender = str(patient.get("gender", "")).lower()

    dob = patient.get("date_of_birth")
    dob_str = dob.strftime("%d %b %Y") if hasattr(dob, "strftime") else str(dob) if dob else "--"

    with st.container(border=True):
        st.write(f"### {first} {last}")
        st.write(f"`{patient.get('patient_id', 'N/A')}`")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.write(f"**Age:** {patient.get('age', 'N/A')}")
        with c2:
            st.write(f"**Gender:** {gender.title()}")
        with c3:
            st.write(f"**Phone:** {patient.get('phone', '--')}")
        with c4:
            st.write(f"**Blood:** {str(patient.get('blood_group', '--')).upper()}")

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


def _render_visit_table(visits: list[dict]) -> None:
    """Display visits as a plain dataframe with status text badges.

    Args:
        visits: List of visit dicts from the full profile aggregation.
    """
    if not visits:
        st.info("No visits recorded for this patient.")
        return

    # Build display data
    display_data: list[dict[str, Any]] = []
    for v in visits:
        vd = v.get("visit_date", "")
        vd_str = vd.strftime("%d %b %Y") if hasattr(vd, "strftime") else str(vd)

        departments = v.get("departments", [])
        dept_names = [d.get("department_name", "") for d in departments if d] if departments else []

        display_data.append({
            "Date": vd_str,
            "Reason": v.get("reason", ""),
            "Diagnosis": v.get("diagnosis", "Pending"),
            "Status": str(v.get("status", "unknown")).title(),
            "Physician": v.get("physician_name", "Not assigned"),
            "Department": ", ".join(dept_names) if dept_names else "--",
        })

    # Export button
    df = pd.DataFrame(display_data)
    csv = df.to_csv(index=False)
    st.download_button(
        "Export as CSV",
        data=csv,
        file_name="visit_history.csv",
        mime="text/csv",
    )

    # Display as dataframe
    st.dataframe(display_data, use_container_width=True, hide_index=True)


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
    """Render the visit history page with search and dataframe display.

    Args:
        db: Active DatabaseConnection.
    """
    # Page header
    st.subheader("Visit History")
    st.caption("Search by Patient ID or name to view their complete clinical record")

    # Centered search
    _, search_col, _ = st.columns([1, 3, 1])
    with search_col:
        search_query = st.text_input(
            "Search",
            placeholder="PAT-2024-001 or Rajesh Sharma",
            key="visit_search",
            label_visibility="collapsed",
        )

    if not search_query.strip():
        st.caption("Enter a Patient ID (PAT-YYYY-NNN) or patient name above.")
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
                    f"{len(results)} patient(s) found -- confirm selection:"
                    if len(results) == 1
                    else f"{len(results)} patients found -- select one:"
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
            f"Visits ({len(visits)})",
            f"Appointments ({len(appts)})",
            f"Referrals ({len(refs)})",
        ])

        with tab_visits:
            _render_visit_table(visits)

        with tab_appts:
            _render_appointments_tab(appts)

        with tab_refs:
            _render_referrals_tab(refs)

    except RuntimeError as exc:
        st.error(f"Database error: {exc}")
    except Exception as exc:
        st.error(f"Error loading visit history: {exc}")
