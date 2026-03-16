"""Referrals page — create referrals, view status, and track referral chain.

Features:
- Create referral form with validation
- Referral cards with status badges
- Status filtering
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import create_referral
from backend.database import DatabaseConnection
from backend.models import Referral, ReferralStatus




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


def _render_create_form(db: DatabaseConnection) -> None:
    """Render the referral creation form.

    Args:
        db: Active DatabaseConnection.
    """
    # Success state
    if st.session_state.get("referral_success_id"):
        st.success(f"Referral Created: {st.session_state['referral_success_id']}")
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
            "Select Patient *", options=list(patient_options.keys())
        )

        col1, col2 = st.columns(2)

        with col1:
            source_options = {
                f"Dr. {p['first_name']} {p['last_name']} -- {p['speciality']}": p[
                    "physician_id"
                ]
                for p in physicians
            }
            selected_source = st.selectbox(
                "Source Physician (Referring) *",
                options=list(source_options.keys()),
                key="source_physician",
            )

        with col2:
            target_options = {
                f"Dr. {p['first_name']} {p['last_name']} -- {p['speciality']}": p[
                    "physician_id"
                ]
                for p in physicians
            }
            selected_target = st.selectbox(
                "Target Physician (Specialist) *",
                options=list(target_options.keys()),
                key="target_physician",
            )

        reason = st.text_area(
            "Reason for Referral *",
            placeholder="Patient requires specialist evaluation for cardiac symptoms",
        )

        urgency = st.selectbox(
            "Urgency",
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
    """Display all referrals as larger container cards with clean layout.

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

        for ref in results:
            ref_date = ref.get("referral_date")
            date_str = (
                ref_date.strftime("%d %b %Y") if hasattr(ref_date, "strftime") else str(ref_date)
            )

            reason_text = ref.get("reason", "")
            status = str(ref.get("status", "pending")).lower()

            with st.container(border=True):
                st.write(f"**Patient:** {ref.get('patient_name', 'Unknown')}  ({ref.get('referral_id', '')})")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**From:** {ref.get('source_physician', 'N/A')} ({ref.get('source_speciality', '')})")
                with col2:
                    st.write(f"**To:** {ref.get('target_physician', 'N/A')} ({ref.get('target_speciality', '')})")
                st.write(f"**Reason:** {reason_text}")
                col3, col4 = st.columns(2)
                with col3:
                    st.write(f"**Status:** {status.title()}")
                with col4:
                    st.write(f"**Date:** {date_str}")

    except PyMongoError as exc:
        st.error(f"Database error loading referrals: {exc}")
    except Exception as exc:
        st.error(f"Error loading referrals: {exc}")


def render(db: DatabaseConnection) -> None:
    """Render the referrals page with create form and list.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("Referrals")
    st.caption("Create referrals and track status.")

    tab1, tab2 = st.tabs(["Create Referral", "All Referrals"])

    with tab1:
        _render_create_form(db)

    with tab2:
        _render_referral_list(db)
