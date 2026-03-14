"""API Explorer page — interactive documentation and live testing for the REST API.

Replaces the raw FastAPI /docs with a styled, dark-themed API reference.
Shows endpoint cards with method badges, parameters, example responses,
live test panel, response time indicator, and copy curl button.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.crud import get_patient_by_id, get_patient_visits, search_patients
from backend.database import DatabaseConnection
from database.queries.aggregations import get_patient_full_profile

load_dotenv()

# API base URL
_BASE_URL = "http://localhost:8000"

# Method badge colors
_METHOD_COLORS = {
    "GET": "#2563EB",
    "POST": "#10B981",
    "PUT": "#F59E0B",
    "DELETE": "#EF4444",
}

# Endpoint registry
_ENDPOINTS: list[dict[str, Any]] = [
    {
        "method": "GET",
        "path": "/api/health",
        "description": "Check database connection status and collection document counts.",
        "parameters": [],
        "tags": ["System"],
        "demo_key": "health",
    },
    {
        "method": "GET",
        "path": "/api/stats",
        "description": "Return aggregate counts for all major collections (patients, visits, appointments, referrals, alerts).",
        "parameters": [],
        "tags": ["System"],
        "demo_key": "stats",
    },
    {
        "method": "GET",
        "path": "/api/patients",
        "description": "List/search patients with optional name and gender filters.",
        "parameters": [
            {"name": "name", "type": "string", "required": False, "description": "Substring search on first/last name"},
            {"name": "gender", "type": "string", "required": False, "description": "Filter by gender (male/female/other)"},
            {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 50, max 200)"},
        ],
        "tags": ["Patients"],
        "demo_key": "patients_list",
    },
    {
        "method": "GET",
        "path": "/api/patients/{patient_id}",
        "description": "Return the complete profile for a single patient. Uses the full-profile aggregation pipeline joining visits, appointments, referrals, physicians, and departments.",
        "parameters": [
            {"name": "patient_id", "type": "string", "required": True, "description": "Patient ID in PAT-YYYY-NNN format"},
        ],
        "tags": ["Patients"],
        "demo_key": "patient_profile",
    },
    {
        "method": "GET",
        "path": "/api/patients/{patient_id}/visits",
        "description": "Return all visits for a patient, sorted newest first.",
        "parameters": [
            {"name": "patient_id", "type": "string", "required": True, "description": "Patient ID in PAT-YYYY-NNN format"},
            {"name": "limit", "type": "integer", "required": False, "description": "Max visits to return (default 20)"},
        ],
        "tags": ["Patients"],
        "demo_key": "patient_visits",
    },
    {
        "method": "GET",
        "path": "/api/patients/{patient_id}/summary",
        "description": "Return a lightweight patient summary (name, age, blood group, active alerts). Designed for modules needing minimal context.",
        "parameters": [
            {"name": "patient_id", "type": "string", "required": True, "description": "Patient ID in PAT-YYYY-NNN format"},
        ],
        "tags": ["Patients"],
        "demo_key": "patient_summary",
    },
    {
        "method": "GET",
        "path": "/api/departments",
        "description": "Return all hospital departments.",
        "parameters": [],
        "tags": ["Reference Data"],
        "demo_key": "departments",
    },
    {
        "method": "GET",
        "path": "/api/physicians",
        "description": "Return all physicians with their department information.",
        "parameters": [],
        "tags": ["Reference Data"],
        "demo_key": "physicians",
    },
]


def _get_sample_patient_id(db: DatabaseConnection) -> str:
    """Fetch the first available patient_id for demo queries.

    Args:
        db: Active DatabaseConnection.

    Returns:
        A patient_id string, defaulting to PAT-2024-001 if none found.
    """
    try:
        first = db.get_collection("patients").find_one({}, {"patient_id": 1})
        if first:
            return first["patient_id"]
    except Exception:
        pass
    return "PAT-2024-001"


def _serialize_for_json(obj: Any) -> Any:
    """Recursively serialize a MongoDB result for JSON display.

    Args:
        obj: Object to serialize.

    Returns:
        JSON-safe object.
    """
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif hasattr(obj, "__str__") and not isinstance(obj, (str, int, float, bool, type(None))):
        return str(obj)
    return obj


def _execute_demo(db: DatabaseConnection, demo_key: str, params: dict[str, str]) -> dict[str, Any]:
    """Execute a demo API call against the database directly.

    Simulates the FastAPI endpoint by calling the same backend functions.

    Args:
        db: Active DatabaseConnection.
        demo_key: The endpoint demo identifier.
        params: Query parameters provided by the user.

    Returns:
        Dict with status, data, and timing information.
    """
    start = time.time()
    result: Any = None
    status_code = 200

    try:
        if demo_key == "health":
            collection_names = [
                "patients", "visits", "appointments", "referrals",
                "alerts", "audit_logs", "departments", "physicians",
            ]
            counts = {}
            for name in collection_names:
                try:
                    counts[name] = db.get_collection(name).count_documents({})
                except Exception:
                    counts[name] = -1
            result = {"status": "healthy", "database": "connected", "collections": counts}

        elif demo_key == "stats":
            result = {
                "total_patients": db.get_collection("patients").count_documents({"is_active": True}),
                "total_visits": db.get_collection("visits").count_documents({}),
                "total_appointments": db.get_collection("appointments").count_documents({}),
                "total_referrals": db.get_collection("referrals").count_documents({}),
                "active_alerts": db.get_collection("alerts").count_documents({"is_acknowledged": False}),
                "total_departments": db.get_collection("departments").count_documents({}),
                "total_physicians": db.get_collection("physicians").count_documents({}),
            }

        elif demo_key == "patients_list":
            name = params.get("name") or None
            limit = int(params.get("limit") or "10")
            result = search_patients(db, name=name, limit=limit)
            result = _serialize_for_json(result)

        elif demo_key == "patient_profile":
            pid = params.get("patient_id", "")
            if not pid:
                return {"status": 400, "data": {"detail": "patient_id is required"}, "time_ms": 0}
            profile = get_patient_full_profile(db, pid)
            if profile is None:
                status_code = 404
                result = {"detail": f"Patient '{pid}' not found."}
            else:
                result = _serialize_for_json(profile)

        elif demo_key == "patient_visits":
            pid = params.get("patient_id", "")
            if not pid:
                return {"status": 400, "data": {"detail": "patient_id is required"}, "time_ms": 0}
            limit = int(params.get("limit") or "20")
            visits = get_patient_visits(db, pid, limit=limit)
            result = _serialize_for_json(visits)

        elif demo_key == "patient_summary":
            pid = params.get("patient_id", "")
            if not pid:
                return {"status": 400, "data": {"detail": "patient_id is required"}, "time_ms": 0}
            patient = get_patient_by_id(db, pid, performed_by="api_explorer")
            if patient is None:
                status_code = 404
                result = {"detail": f"Patient '{pid}' not found."}
            else:
                alert_count = db.get_collection("alerts").count_documents(
                    {"patient_id": pid, "is_acknowledged": False}
                )
                result = _serialize_for_json({
                    "patient_id": patient.get("patient_id", ""),
                    "first_name": patient.get("first_name", ""),
                    "last_name": patient.get("last_name", ""),
                    "age": patient.get("age"),
                    "gender": str(patient.get("gender", "")).lower(),
                    "blood_group": str(patient.get("blood_group", "")) if patient.get("blood_group") else None,
                    "phone": patient.get("phone"),
                    "is_active": patient.get("is_active", True),
                    "active_alerts": alert_count,
                })

        elif demo_key == "departments":
            result = _serialize_for_json(
                list(db.get_collection("departments").find({}, {"_id": 0}))
            )

        elif demo_key == "physicians":
            pipeline = [
                {
                    "$lookup": {
                        "from": "departments",
                        "localField": "department_id",
                        "foreignField": "department_id",
                        "as": "department",
                    }
                },
                {"$unwind": {"path": "$department", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        "_id": 0,
                        "physician_id": 1,
                        "first_name": 1,
                        "last_name": 1,
                        "speciality": 1,
                        "department_name": "$department.department_name",
                    }
                },
            ]
            result = _serialize_for_json(
                list(db.get_collection("physicians").aggregate(pipeline))
            )

    except Exception as exc:
        status_code = 500
        result = {"detail": str(exc)}

    elapsed = (time.time() - start) * 1000
    return {"status": status_code, "data": result, "time_ms": elapsed}


def render(db: DatabaseConnection) -> None:
    """Render the API Explorer page with endpoint cards and live testing.

    Args:
        db: Active DatabaseConnection.
    """
    st.markdown(
        '<h2 style="margin-bottom:4px;">API Explorer</h2>'
        '<p style="color:#94A3B8; font-size:0.85rem; margin-bottom:4px;">'
        "Interactive documentation for the Patient Demographics REST API. "
        "Other modules use these endpoints to query patient data.</p>"
        '<p style="font-family:monospace; font-size:0.8rem; color:#2563EB; margin-bottom:20px;">'
        f'Base URL: {_BASE_URL}/api</p>',
        unsafe_allow_html=True,
    )

    sample_pid = _get_sample_patient_id(db)

    for idx, endpoint in enumerate(_ENDPOINTS):
        method = endpoint["method"]
        path = endpoint["path"]
        color = _METHOD_COLORS.get(method, "#64748B")
        tag = endpoint["tags"][0] if endpoint["tags"] else ""

        with st.expander(
            f"{method}  {path}  —  {endpoint['description'][:60]}..."
            if len(endpoint["description"]) > 60
            else f"{method}  {path}  —  {endpoint['description']}"
        ):
            # Method badge + path
            st.markdown(
                f"""<div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
                    <span style="font-size:0.7rem; font-weight:700; color:white;
                        background:{color}; padding:3px 10px; border-radius:4px;
                        font-family:monospace;">{method}</span>
                    <code style="font-size:0.85rem; color:#F8FAFC;">{path}</code>
                    <span style="font-size:0.6rem; color:#64748B; text-transform:uppercase;
                        letter-spacing:0.05em;">{tag}</span>
                </div>""",
                unsafe_allow_html=True,
            )

            st.write(endpoint["description"])

            # Parameters
            if endpoint["parameters"]:
                st.markdown("**Parameters:**")
                for param in endpoint["parameters"]:
                    req = "required" if param["required"] else "optional"
                    st.markdown(
                        f'- `{param["name"]}` ({param["type"]}, {req}): {param["description"]}'
                    )

            # Curl command
            curl_path = path.replace("{patient_id}", sample_pid)
            curl_cmd = f"curl {_BASE_URL}{curl_path}"
            st.markdown("**cURL:**")
            st.code(curl_cmd, language="bash")

            st.divider()

            # Live test panel
            st.markdown(
                '<p style="font-size:0.75rem; font-weight:600; color:#94A3B8; '
                'text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">'
                "Live Test</p>",
                unsafe_allow_html=True,
            )

            params: dict[str, str] = {}
            for param in endpoint["parameters"]:
                default_val = ""
                if param["name"] == "patient_id":
                    default_val = sample_pid
                elif param["name"] == "limit":
                    default_val = "10"

                params[param["name"]] = st.text_input(
                    param["name"],
                    value=default_val,
                    key=f"api_{idx}_{param['name']}",
                    placeholder=param["description"],
                )

            if st.button("Send Request", key=f"api_send_{idx}", type="primary"):
                with st.spinner("Executing..."):
                    response = _execute_demo(db, endpoint["demo_key"], params)

                # Response time indicator
                time_ms = response["time_ms"]
                time_color = "#10B981" if time_ms < 100 else "#F59E0B" if time_ms < 500 else "#EF4444"
                status = response["status"]
                status_color = "#10B981" if status < 400 else "#F59E0B" if status < 500 else "#EF4444"

                st.markdown(
                    f"""<div style="display:flex; gap:16px; align-items:center; margin:8px 0;">
                        <span style="font-size:0.75rem; font-weight:600;
                            color:{status_color};">Status: {status}</span>
                        <span style="font-size:0.75rem; font-weight:600;
                            color:{time_color};">⏱ {time_ms:.1f}ms</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

                # Response body
                try:
                    formatted = json.dumps(response["data"], indent=2, default=str)
                    st.code(formatted, language="json")
                except Exception:
                    st.json(response["data"])
