"""Patient registration page — split layout with live preview card.

Form on left, real-time patient card preview on right. Progress bar shows
completion percentage. Fires age_calculator_trigger and audit_log_trigger
automatically through create_patient in crud.py.
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


def _compute_completion(
    first_name: str,
    last_name: str,
    phone: str,
    email: str,
    street: str,
    city: str,
    insurance_provider: str,
    policy_number: str,
) -> int:
    """Compute form completion percentage.

    Args:
        first_name: First name value.
        last_name: Last name value.
        phone: Phone value.
        email: Email value.
        street: Street address value.
        city: City value.
        insurance_provider: Insurance provider value.
        policy_number: Policy number value.

    Returns:
        Integer percentage 0-100.
    """
    fields = [first_name, last_name, phone]  # required = 3
    optional = [email, street, city, insurance_provider, policy_number]
    filled_required = sum(1 for f in fields if f.strip())
    filled_optional = sum(1 for f in optional if f.strip())
    total = len(fields) + len(optional)
    filled = filled_required + filled_optional
    return int((filled / total) * 100) if total > 0 else 0


def _render_live_preview(
    first_name: str,
    last_name: str,
    date_of_birth: date,
    gender: str,
    phone: str,
    email: str,
    street: str,
    city: str,
    state: str,
    insurance_provider: str,
    patient_id: str = "",
) -> None:
    """Render the live preview patient card on the right.

    Args:
        first_name: Current first name value.
        last_name: Current last name value.
        date_of_birth: Current DOB value.
        gender: Current gender value.
        phone: Current phone value.
        email: Current email value.
        street: Current street value.
        city: Current city value.
        state: Current state value.
        insurance_provider: Current insurance provider.
        patient_id: Generated patient ID (shown only on success).
    """
    fn = first_name.strip() or "First"
    ln = last_name.strip() or "Last"
    initials = f"{fn[0]}{ln[0]}".upper()

    gender_lower = gender.lower()
    if gender_lower == "male":
        avatar_bg = "#2563EB"
    elif gender_lower == "female":
        avatar_bg = "#EC4899"
    else:
        avatar_bg = "#8B5CF6"

    # Compute age from DOB
    today = date.today()
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    pid_display = patient_id if patient_id else "PAT-YYYY-NNN"
    pid_color = "#10B981" if patient_id else "#64748B"

    st.markdown(
        f"""<div style="background:rgba(30,41,59,0.6); backdrop-filter:blur(12px);
                border:1px solid #334155; border-radius:16px; padding:28px;
                text-align:center;">
            <div style="width:72px; height:72px; border-radius:50%;
                background:{avatar_bg}; display:flex; align-items:center;
                justify-content:center; font-size:1.5rem; font-weight:800;
                color:white; margin:0 auto 16px auto;
                box-shadow:0 4px 15px rgba(0,0,0,0.3);">{initials}</div>
            <h3 style="margin:0; font-size:1.2rem; font-weight:700;">{fn} {ln}</h3>
            <p style="color:{pid_color}; font-size:0.8rem; font-family:monospace;
                margin:4px 0 16px 0; font-weight:600;">{pid_display}</p>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;
                text-align:left;">
                <div>
                    <p style="color:#64748B; font-size:0.65rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Age</p>
                    <p style="font-size:0.9rem; font-weight:600; margin:2px 0 0 0;">
                        {age} yrs</p>
                </div>
                <div>
                    <p style="color:#64748B; font-size:0.65rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Gender</p>
                    <p style="font-size:0.9rem; font-weight:600; margin:2px 0 0 0;">
                        {gender.replace('_', ' ').title()}</p>
                </div>
                <div>
                    <p style="color:#64748B; font-size:0.65rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Phone</p>
                    <p style="font-size:0.9rem; font-weight:600; margin:2px 0 0 0;">
                        {phone.strip() or '—'}</p>
                </div>
                <div>
                    <p style="color:#64748B; font-size:0.65rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin:0;">Email</p>
                    <p style="font-size:0.85rem; font-weight:600; margin:2px 0 0 0;
                        word-break:break-all;">
                        {email.strip() or '—'}</p>
                </div>
            </div>
            {"<div style='margin-top:16px; padding-top:12px; border-top:1px solid #334155;'>"
             "<div style='display:flex; justify-content:space-between;'>"
             f"<span style='color:#64748B; font-size:0.7rem;'>📍 {city.strip() or '—'}, {state.strip() or '—'}</span>"
             f"<span style='color:#64748B; font-size:0.7rem;'>🏥 {insurance_provider.strip() or 'No insurance'}</span>"
             "</div></div>"
            }
        </div>""",
        unsafe_allow_html=True,
    )


def render(db: DatabaseConnection) -> None:
    """Render the patient registration form with live preview card.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<h2 style="margin-bottom:4px;">Register New Patient</h2>'
        '<p style="color:#94A3B8; font-size:0.85rem; margin-bottom:20px;">'
        "Fill in patient demographics to register them in the system.</p>",
        unsafe_allow_html=True,
    )

    # Success state — show confirmation
    if st.session_state.get("reg_success_id"):
        pid = st.session_state["reg_success_id"]
        st.markdown(
            f"""<div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3);
                    border-radius:12px; padding:24px; text-align:center; margin-bottom:20px;">
                <span style="font-size:2.5rem;">🎉</span>
                <h3 style="margin:8px 0 4px 0; color:#10B981;">Patient Registered Successfully</h3>
                <p style="font-family:monospace; font-size:1.1rem; font-weight:700;
                    color:#F8FAFC;">{pid}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("Register Another Patient", type="primary"):
            st.session_state.pop("reg_success_id", None)
            st.session_state.pop("reg_errors", None)
            st.rerun()
        return

    # Previous validation errors from session state
    field_errors: dict[str, str] = st.session_state.get("reg_errors", {})

    # Split layout: form left, preview right
    form_col, preview_col = st.columns([3, 2])

    with form_col:
        with st.form("patient_registration_form", clear_on_submit=False):
            # Personal Information
            st.markdown(
                '<p style="font-size:0.75rem; font-weight:600; color:#94A3B8; '
                'text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">'
                "Personal Information</p>",
                unsafe_allow_html=True,
            )
            col1, col2 = st.columns(2)

            with col1:
                first_name = st.text_input("👤 First Name *", placeholder="Rajesh")
                if field_errors.get("first_name"):
                    st.error(field_errors["first_name"])

                date_of_birth = st.date_input(
                    "📅 Date of Birth *",
                    value=date(1990, 1, 1),
                    min_value=date(1900, 1, 1),
                    max_value=date.today(),
                )
                if field_errors.get("date_of_birth"):
                    st.error(field_errors["date_of_birth"])

                phone = st.text_input("📱 Phone *", placeholder="+919876543210")
                if field_errors.get("phone"):
                    st.error(field_errors["phone"])

            with col2:
                last_name = st.text_input("👤 Last Name *", placeholder="Sharma")
                if field_errors.get("last_name"):
                    st.error(field_errors["last_name"])

                gender = st.selectbox(
                    "⚥ Gender *",
                    options=[g.value for g in Gender],
                    format_func=lambda x: x.replace("_", " ").title(),
                )

                email = st.text_input("✉ Email", placeholder="rajesh.sharma@email.com")
                if field_errors.get("email"):
                    st.error(field_errors["email"])

            # Address section
            st.markdown(
                '<p style="font-size:0.75rem; font-weight:600; color:#94A3B8; '
                'text-transform:uppercase; letter-spacing:0.08em; margin:16px 0 8px 0;">'
                "Address</p>",
                unsafe_allow_html=True,
            )
            addr_col1, addr_col2 = st.columns(2)

            with addr_col1:
                street = st.text_input("📍 Street Address", placeholder="42, MG Road")
                state = st.text_input("🗺 State", placeholder="Jharkhand")

            with addr_col2:
                city = st.text_input("🏙 City", placeholder="Dhanbad")
                postal_code = st.text_input("📮 Postal Code", placeholder="826001")

            # Insurance section
            st.markdown(
                '<p style="font-size:0.75rem; font-weight:600; color:#94A3B8; '
                'text-transform:uppercase; letter-spacing:0.08em; margin:16px 0 8px 0;">'
                "Insurance Details</p>",
                unsafe_allow_html=True,
            )
            ins_col1, ins_col2 = st.columns(2)

            with ins_col1:
                insurance_provider = st.text_input(
                    "🏥 Insurance Provider", placeholder="Star Health"
                )
                group_number = st.text_input("🔢 Group Number", placeholder="GRP-001")

            with ins_col2:
                policy_number = st.text_input("📋 Policy Number", placeholder="POL-12345")
                valid_until = st.date_input("📅 Valid Until", value=None)

            submitted = st.form_submit_button(
                "Register Patient", type="primary", use_container_width=True
            )

    with preview_col:
        # Progress bar
        completion = _compute_completion(
            first_name or "", last_name or "", phone or "",
            email or "", street or "", city or "",
            insurance_provider or "", policy_number or "",
        )
        st.markdown(
            f'<p style="font-size:0.7rem; color:#94A3B8; margin-bottom:4px;">'
            f"Form Completion: {completion}%</p>",
            unsafe_allow_html=True,
        )
        st.progress(completion / 100)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # Live preview card
        _render_live_preview(
            first_name=first_name or "",
            last_name=last_name or "",
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone or "",
            email=email or "",
            street=street or "",
            city=city or "",
            state=state or "",
            insurance_provider=insurance_provider or "",
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
