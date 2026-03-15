"""Patient registration page — clean form layout.

Registration form with validation. Fires age_calculator_trigger and
audit_log_trigger automatically through create_patient in crud.py.
"""

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import create_patient
from backend.database import DatabaseConnection
from backend.models import Address, Gender, InsuranceInfo, Patient

load_dotenv()

# Pre-compiled validation patterns
_PHONE_PATTERN = re.compile(r"^\+91\d{10}$")
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _generate_patient_id(db: DatabaseConnection) -> str:
    """Generate the next available PAT-YYYY-NNN identifier.

    Args:
        db: Active DatabaseConnection.

    Returns:
        A new patient_id string in PAT-YYYY-NNN format.
    """
    year = datetime.utcnow().year
    prefix = f"PAT-{year}-"

    try:
        latest = (
            db.get_collection("patients")
            .find({"patient_id": {"$regex": f"^{prefix}"}}, {"patient_id": 1})
            .sort("patient_id", -1)
            .limit(1)
        )
        latest_list = list(latest)
        if latest_list:
            last_num = int(latest_list[0]["patient_id"].split("-")[-1])
            return f"{prefix}{last_num + 1:03d}"
    except Exception:
        pass

    return f"{prefix}001"


def render(db: DatabaseConnection) -> None:
    """Render the patient registration form.

    Args:
        db: Active DatabaseConnection.
    """
    st.subheader("Register New Patient")
    st.caption("Fill in patient demographics to register them in the system.")

    # Success state -- show confirmation
    if st.session_state.get("reg_success_id"):
        pid = st.session_state["reg_success_id"]
        st.success(f"Patient Registered Successfully: {pid}")
        if st.button("Register Another Patient", type="primary"):
            st.session_state.pop("reg_success_id", None)
            st.session_state.pop("reg_errors", None)
            st.rerun()
        return

    # Previous validation errors from session state
    field_errors: dict[str, str] = st.session_state.get("reg_errors", {})

    with st.form("patient_registration_form", clear_on_submit=False):
        # Personal Information
        st.caption("PERSONAL INFORMATION")
        col1, col2 = st.columns(2)

        with col1:
            first_name = st.text_input("First Name *", placeholder="Enter first name")
            if field_errors.get("first_name"):
                st.error(field_errors["first_name"])

            date_of_birth = st.date_input(
                "Date of Birth *",
                value=date(1990, 1, 1),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )
            if field_errors.get("date_of_birth"):
                st.error(field_errors["date_of_birth"])

            phone = st.text_input("Phone *", placeholder="+919876543210")
            if field_errors.get("phone"):
                st.error(field_errors["phone"])

        with col2:
            last_name = st.text_input("Last Name *", placeholder="Enter last name")
            if field_errors.get("last_name"):
                st.error(field_errors["last_name"])

            gender = st.selectbox(
                "Gender *",
                options=[g.value for g in Gender],
                format_func=lambda x: x.replace("_", " ").title(),
            )

            email = st.text_input("Email", placeholder="name@example.com")
            if field_errors.get("email"):
                st.error(field_errors["email"])

        # Address section
        st.caption("ADDRESS")
        addr_col1, addr_col2 = st.columns(2)

        with addr_col1:
            street = st.text_input("Street Address", placeholder="Street address")
            state = st.text_input("State", placeholder="State name")

        with addr_col2:
            city = st.text_input("City", placeholder="City name")
            postal_code = st.text_input("Postal Code", placeholder="Postal code")

        # Insurance section
        st.caption("INSURANCE DETAILS")
        ins_col1, ins_col2 = st.columns(2)

        with ins_col1:
            insurance_provider = st.text_input(
                "Insurance Provider", placeholder="Provider name"
            )
            group_number = st.text_input("Group Number", placeholder="Group number")

        with ins_col2:
            policy_number = st.text_input("Policy Number", placeholder="Policy number")
            valid_until = st.date_input("Valid Until", value=None)

        submitted = st.form_submit_button(
            "Register Patient", type="primary", use_container_width=True
        )

    # Form submission handling
    if submitted:
        # Clear previous errors before re-validating
        st.session_state.pop("reg_errors", None)
        errors: dict[str, str] = {}

        if not first_name.strip():
            errors["first_name"] = "First name is required"
        if not last_name.strip():
            errors["last_name"] = "Last name is required"

        if date_of_birth > date.today():
            errors["date_of_birth"] = "Date of birth cannot be in the future"

        if not phone.strip():
            errors["phone"] = "Phone number is required"
        elif not _PHONE_PATTERN.match(phone.strip()):
            errors["phone"] = (
                "Phone must start with +91 followed by 10 digits "
                "(e.g. +919876543210)"
            )

        if email.strip() and not _EMAIL_PATTERN.match(email.strip()):
            errors["email"] = (
                "Please enter a valid email address (e.g. name@example.com)"
            )

        if errors:
            st.session_state["reg_errors"] = errors
            st.rerun()

        # Build Address if any field is filled
        address: Optional[Address] = None
        if any([street.strip(), city.strip(), state.strip(), postal_code.strip()]):
            try:
                address = Address(
                    street=street.strip() or "N/A",
                    city=city.strip() or "N/A",
                    state=state.strip() or "N/A",
                    postal_code=postal_code.strip() or "000000",
                )
            except Exception as exc:
                st.error(f"Address validation error: {exc}")
                return

        # Build InsuranceInfo if provider and policy are filled
        insurance: Optional[InsuranceInfo] = None
        if insurance_provider.strip() and policy_number.strip():
            try:
                insurance = InsuranceInfo(
                    provider=insurance_provider.strip(),
                    policy_number=policy_number.strip(),
                    group_number=group_number.strip() or None,
                    valid_until=valid_until,
                )
            except Exception as exc:
                st.error(f"Insurance validation error: {exc}")
                return

        # Generate ID and insert into MongoDB
        with st.spinner("Registering patient..."):
            try:
                patient_id = _generate_patient_id(db)
                patient = Patient(
                    patient_id=patient_id,
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    date_of_birth=date_of_birth,
                    gender=Gender(gender),
                    phone=phone.strip(),
                    email=email.strip() or None,
                    address=address,
                    insurance=insurance,
                )

                created_id = create_patient(
                    db, patient, performed_by="registration_desk"
                )
                st.session_state["reg_success_id"] = created_id
                st.rerun()

            except ValueError as exc:
                st.error(f"Registration failed: {exc}")
            except RuntimeError as exc:
                st.error(f"Database error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error during registration: {exc}")
