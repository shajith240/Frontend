"""FastAPI integration layer for cross-module patient data sharing.

Exposes patient demographics data via REST endpoints so other modules
(Lab Results, Radiology, Billing, Pharmacy, etc.) can query patient
information using the universal patient_id (PAT-YYYY-NNN) foreign key.

Run standalone:
    uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

Or via the project's run.sh script which starts both FastAPI and Streamlit.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure module root is on sys.path for relative imports
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.database import DatabaseConnection
from backend.crud import (
    get_patient_by_id,
    get_patient_visits,
    search_patients,
)
from database.queries.aggregations import get_patient_full_profile

load_dotenv()

# ---------------------------------------------------------------------------
# Shared database connection
# ---------------------------------------------------------------------------

_db: Optional[DatabaseConnection] = None


def _get_db() -> DatabaseConnection:
    """Return the active database connection.

    Raises:
        RuntimeError: If the database is not connected.
    """
    if _db is None or _db._db is None:
        raise RuntimeError("Database not connected.")
    return _db


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response model for the /api/health endpoint."""

    status: str
    database: str
    collections: dict[str, int]


class StatsResponse(BaseModel):
    """Response model for the /api/stats endpoint."""

    total_patients: int
    total_visits: int
    total_appointments: int
    total_referrals: int
    active_alerts: int
    total_departments: int
    total_physicians: int


class PatientSummary(BaseModel):
    """Lightweight patient summary for quick lookups by other modules."""

    patient_id: str
    first_name: str
    last_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    active_alerts: int = 0


class MessageResponse(BaseModel):
    """Generic message response."""

    detail: str


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle.

    Opens the MongoDB Atlas connection on startup and closes it on shutdown.
    """
    global _db
    _db = DatabaseConnection()
    try:
        _db.connect()
        print("FastAPI: MongoDB Atlas connection established.")
    except (ConnectionError, ValueError) as exc:
        print(f"FastAPI: Failed to connect to MongoDB Atlas: {exc}")
        _db = None

    yield

    if _db is not None:
        _db.disconnect()
        print("FastAPI: MongoDB Atlas connection closed.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Module 1 — Patient Demographics API",
    description=(
        "REST API for the Patient Demographics & Visit History module. "
        "Provides patient data to all 50 modules in the Clinical Decision "
        "Support System via the universal patient_id (PAT-YYYY-NNN) key."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so any module on any port can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check() -> dict[str, Any]:
    """Return database connection status and collection document counts.

    Used by other modules and monitoring dashboards to verify that
    Module 1's data layer is online and responsive.
    """
    try:
        db = _get_db()
        collection_names = [
            "patients", "visits", "appointments", "referrals",
            "alerts", "audit_logs", "departments", "physicians",
            "visit_departments",
        ]
        counts: dict[str, int] = {}
        for name in collection_names:
            try:
                counts[name] = db.get_collection(name).count_documents({})
            except Exception:
                counts[name] = -1

        return {
            "status": "healthy",
            "database": "connected",
            "collections": counts,
        }
    except RuntimeError:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "collections": {},
        }


@app.get("/api/stats", response_model=StatsResponse, tags=["System"])
def get_stats() -> dict[str, int]:
    """Return aggregate counts for all major collections.

    Lightweight endpoint for dashboards and status pages across the system.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        return {
            "total_patients": db.get_collection("patients").count_documents(
                {"is_active": True}
            ),
            "total_visits": db.get_collection("visits").count_documents({}),
            "total_appointments": db.get_collection("appointments").count_documents({}),
            "total_referrals": db.get_collection("referrals").count_documents({}),
            "active_alerts": db.get_collection("alerts").count_documents(
                {"is_acknowledged": False}
            ),
            "total_departments": db.get_collection("departments").count_documents({}),
            "total_physicians": db.get_collection("physicians").count_documents({}),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {exc}")


@app.get("/api/patients", tags=["Patients"])
def list_patients(
    name: Optional[str] = Query(None, description="Substring search on first/last name"),
    gender: Optional[str] = Query(None, description="Filter by gender (male/female/other)"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
) -> list[dict[str, Any]]:
    """List patients with optional name and gender filters.

    Other modules use this to search for patients by name when they don't
    have the patient_id handy (e.g. front-desk lookup in Billing module).
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        results = search_patients(db, name=name, limit=limit)

        if gender:
            results = [
                p for p in results
                if str(p.get("gender", "")).lower() == gender.lower()
            ]

        return results
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error searching patients: {exc}")


@app.get("/api/patients/{patient_id}", tags=["Patients"])
def get_patient(patient_id: str) -> dict[str, Any]:
    """Return the complete profile for a single patient.

    Uses the full-profile aggregation pipeline that joins across visits,
    appointments, referrals, physicians, and departments in one pass.
    This is the primary endpoint other modules call to resolve a patient_id.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        profile = get_patient_full_profile(db, patient_id)
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"Patient '{patient_id}' not found.",
            )
        return profile
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching patient profile: {exc}",
        )


@app.get("/api/patients/{patient_id}/visits", tags=["Patients"])
def get_visits_for_patient(
    patient_id: str,
    limit: int = Query(20, ge=1, le=100, description="Max visits to return"),
) -> list[dict[str, Any]]:
    """Return all visits for a patient, sorted newest first.

    Used by modules like Nursing (Module 7) and Pharmacy (Module 14) to
    pull a patient's clinical visit history for context.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        # Verify patient exists
        patient = get_patient_by_id(db, patient_id, performed_by="api", performed_by_role="system")
        if patient is None:
            raise HTTPException(
                status_code=404,
                detail=f"Patient '{patient_id}' not found.",
            )

        visits = get_patient_visits(db, patient_id, limit=limit)
        return visits
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching visits: {exc}",
        )


@app.get(
    "/api/patients/{patient_id}/summary",
    response_model=PatientSummary,
    tags=["Patients"],
)
def get_patient_summary(patient_id: str) -> dict[str, Any]:
    """Return a lightweight patient summary (name, age, blood group, active alerts).

    Designed for modules that need minimal patient context without pulling
    the full profile — e.g. a pharmacy label or a lab report header.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        patient = get_patient_by_id(db, patient_id, performed_by="api", performed_by_role="system")
        if patient is None:
            raise HTTPException(
                status_code=404,
                detail=f"Patient '{patient_id}' not found.",
            )

        # Count active (unacknowledged) alerts for this patient
        active_alerts = db.get_collection("alerts").count_documents(
            {"patient_id": patient_id, "is_acknowledged": False}
        )

        return {
            "patient_id": patient.get("patient_id", ""),
            "first_name": patient.get("first_name", ""),
            "last_name": patient.get("last_name", ""),
            "age": patient.get("age"),
            "gender": str(patient.get("gender", "")).lower(),
            "blood_group": str(patient.get("blood_group", "")) if patient.get("blood_group") else None,
            "phone": patient.get("phone"),
            "is_active": patient.get("is_active", True),
            "active_alerts": active_alerts,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching patient summary: {exc}",
        )


@app.get("/api/departments", tags=["Reference Data"])
def list_departments() -> list[dict[str, Any]]:
    """Return all hospital departments.

    Used by modules that need to display department dropdowns or validate
    department references in their own records.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        departments = list(
            db.get_collection("departments").find({}, {"_id": 0})
        )
        return departments
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching departments: {exc}",
        )


@app.get("/api/physicians", tags=["Reference Data"])
def list_physicians() -> list[dict[str, Any]]:
    """Return all physicians with their department information.

    Used by modules like Appointments and Referrals in other modules
    to populate physician selection dropdowns.
    """
    try:
        db = _get_db()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not connected.")

    try:
        pipeline: list[dict[str, Any]] = [
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
                    "department_id": 1,
                    "department_name": "$department.department_name",
                    "phone": 1,
                    "email": 1,
                }
            },
        ]
        physicians = list(db.get_collection("physicians").aggregate(pipeline))
        return physicians
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching physicians: {exc}",
        )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
