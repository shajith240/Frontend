"""Visit history page — search patients and display their full visit timeline.

Uses get_patient_full_profile() from the aggregation pipelines to fetch a
complete patient record with visits, appointments, referrals, and physician
details in a single aggregation pass.
"""

import sys
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import get_patient_by_id, search_patients
from backend.database import DatabaseConnection
from database.queries.aggregations import get_patient_full_profile

load_dotenv()


def _render_patient_summary(patient: dict) -> None:
    """Display the demographic summary card at the top of the page.

    Args:
        patient: Patient document dict from get_patient_full_profile.
    """
    st.subheader(f"{patient.get('first_name', '')} {patient.get('last_name', '')}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Patient ID", patient.get("patient_id", "N/A"))
    col2.metric("Age", patient.get("age", "N/A"))
    col3.metric("Gender", str(patient.get("gender", "N/A")).title())
    col4.metric("Phone", patient.get("phone", "N/A"))

    # Additional demographics in an expander
    with st.expander("Full Demographics"):
        demo_col1, demo_col2 = st.columns(2)
        with demo_col1:
            st.write(f"**Email:** {patient.get('email', 'Not provided')}")
            st.write(
                f"**Blood Group:** "
                f"{str(patient.get('blood_group', 'Unknown')).upper()}"
            )
            dob = patient.get("date_of_birth")
            if dob:
                dob_str = dob.strftime("%d %b %Y") if hasattr(dob, "strftime") else str(dob)
                st.write(f"**Date of Birth:** {dob_str}")

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
    """Display the visit timeline sorted by date descending.

    Each visit card shows VisitDate, Reason, Diagnosis, Status, Physician name,
    and Department as required by the ER diagram.

    Args:
        visits: List of visit dicts from the full profile aggregation.
    """
    st.metric("Total Visits", len(visits))

    if not visits:
        st.info("No visits recorded for this patient.")
        return

    for visit in visits:
        visit_date = visit.get("visit_date", "Unknown date")
        if hasattr(visit_date, "strftime"):
            visit_date = visit_date.strftime("%d %b %Y")

        status = str(visit.get("status", "unknown")).upper()
        status_colors = {
            "ACTIVE": "blue",
            "COMPLETED": "green",
            "DISCHARGED": "orange",
            "CANCELLED": "red",
        }
        status_color = status_colors.get(status, "gray")

        with st.container(border=True):
            header_col, status_col = st.columns([4, 1])
            with header_col:
                st.markdown(
                    f"**{visit_date}** — {visit.get('reason', 'No reason recorded')}"
                )
            with status_col:
                st.markdown(
                    f":{status_color}[**{status}**]"
                )

            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                diagnosis = visit.get("diagnosis", "Pending")
                st.write(f"**Diagnosis:** {diagnosis}")
                st.write(
                    f"**Physician:** {visit.get('physician_name', 'Not assigned')}"
                )

            with detail_col2:
                speciality = visit.get("physician_speciality", "")
                if speciality:
                    st.write(f"**Speciality:** {speciality}")

                departments = visit.get("departments", [])
                if departments:
                    dept_names = [
                        d.get("department_name", "") for d in departments if d
                    ]
                    st.write(f"**Department:** {', '.join(dept_names)}")


def render(db: DatabaseConnection) -> None:
    """Render the visit history page with search and timeline display.

    Args:
        db: Active DatabaseConnection.
    """
    st.header("Visit History")

    # Search bar — accepts PatientID or name
    search_query = st.text_input(
        "Search by Patient ID or Name",
        placeholder="PAT-2024-001 or Rajesh",
        key="visit_search",
    )

    if not search_query.strip():
        st.info("Enter a Patient ID (PAT-YYYY-NNN) or patient name to search.")
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

            # Always show dropdown so the user can confirm the right patient,
            # even when there is only one match (handles same-name patients).
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

        # Fetch complete profile using the aggregation pipeline
        with st.spinner("Loading patient profile..."):
            profile = get_patient_full_profile(db, patient_id)
        if not profile:
            st.error(f"Could not load full profile for {patient_id}")
            return

        # Render patient summary at the top
        _render_patient_summary(profile)

        st.divider()

        # Render visit timeline
        visits = profile.get("visits", [])
        _render_visit_timeline(visits)

    except RuntimeError as exc:
        st.error(f"Database error: {exc}")
    except Exception as exc:
        st.error(f"Error loading visit history: {exc}")
