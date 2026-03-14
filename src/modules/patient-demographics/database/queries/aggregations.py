"""MongoDB aggregation pipeline queries for the patient-demographics module.

Each function is a direct MongoDB equivalent of a named SQL query and is
documented with the SQL statement it mirrors. These pipelines demonstrate
the core DBMS concepts required by the project specification:
  $lookup   → JOIN
  $group    → GROUP BY / HAVING
  $sort     → ORDER BY
  $limit    → LIMIT / TOP N
  $match    → WHERE / HAVING
  $project  → SELECT (column projection)
  $unwind   → lateral join / normalise arrays
  $facet    → parallel sub-pipelines (multi-table SELECT in one pass)

Collections used: patients, physicians, departments, visits,
                  visit_departments, appointments, referrals.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo.errors import PyMongoError

# Allow running this file directly from the repo root.
_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from backend.database import DatabaseConnection

load_dotenv()


# ---------------------------------------------------------------------------
# Query 1 — patients with visit count
# ---------------------------------------------------------------------------

def get_patients_with_visit_count(db: DatabaseConnection) -> list[dict]:
    """Return every patient together with the total number of visits they have made.

    SQL equivalent:
        SELECT
            p.patient_id,
            p.first_name,
            p.last_name,
            p.age,
            p.gender,
            COUNT(v.visit_id) AS visit_count
        FROM patients p
        LEFT JOIN visits v ON p.patient_id = v.patient_id
        GROUP BY p.patient_id
        ORDER BY visit_count DESC;

    The LEFT JOIN semantics are reproduced with $lookup +
    $size so patients with zero visits still appear (visit_count = 0).

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts, each containing patient_id, first_name, last_name,
        age, gender, and visit_count. Sorted by visit_count descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # LEFT JOIN patients → visits
        {
            "$lookup": {
                "from": "visits",
                "localField": "patient_id",
                "foreignField": "patient_id",
                "as": "visits",
            }
        },
        # COUNT(visit_id) — equivalent to SELECT COUNT(v.visit_id)
        {
            "$addFields": {
                "visit_count": {"$size": "$visits"},
            }
        },
        # SELECT specific columns
        {
            "$project": {
                "_id": 0,
                "patient_id": 1,
                "first_name": 1,
                "last_name": 1,
                "age": 1,
                "gender": 1,
                "phone": 1,
                "visit_count": 1,
            }
        },
        # ORDER BY visit_count DESC
        {"$sort": {"visit_count": -1}},
    ]
    try:
        return list(db.get_collection("patients").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_patients_with_visit_count failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 2 — visit frequency by month
# ---------------------------------------------------------------------------

def get_visit_frequency_by_month(db: DatabaseConnection) -> list[dict]:
    """Return the number of visits recorded for each calendar month and year.

    SQL equivalent:
        SELECT
            YEAR(visit_date)  AS year,
            MONTH(visit_date) AS month,
            COUNT(*)          AS visit_count
        FROM visits
        GROUP BY YEAR(visit_date), MONTH(visit_date)
        ORDER BY year ASC, month ASC;

    Useful for plotting visit-frequency trends over time on the dashboard.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts with year, month (integer), month_name, and visit_count.
        Ordered chronologically oldest-first.

    Raises:
        RuntimeError: On unexpected database error.
    """
    # Month name lookup array — index 0 is unused; $month returns 1-based integer.
    _MONTH_NAMES = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    pipeline: list[dict[str, Any]] = [
        # Extract YEAR() and MONTH() from the stored datetime field
        {
            "$addFields": {
                "_year": {"$year": "$visit_date"},
                "_month": {"$month": "$visit_date"},
            }
        },
        # GROUP BY YEAR, MONTH  — COUNT(*)
        {
            "$group": {
                "_id": {"year": "$_year", "month": "$_month"},
                "visit_count": {"$sum": 1},
            }
        },
        # Promote _id fields and add human-readable month name
        {
            "$addFields": {
                "year": "$_id.year",
                "month": "$_id.month",
                "month_name": {
                    "$arrayElemAt": [_MONTH_NAMES, "$_id.month"]
                },
            }
        },
        # SELECT — drop internal _id
        {"$project": {"_id": 0, "year": 1, "month": 1, "month_name": 1, "visit_count": 1}},
        # ORDER BY year ASC, month ASC
        {"$sort": {"year": 1, "month": 1}},
    ]
    try:
        return list(db.get_collection("visits").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_visit_frequency_by_month failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 3 — top diagnoses
# ---------------------------------------------------------------------------

def get_top_diagnoses(db: DatabaseConnection, limit: int = 10) -> list[dict]:
    """Return the most frequently recorded diagnoses across all visits.

    SQL equivalent:
        SELECT
            diagnosis,
            COUNT(*) AS frequency
        FROM visits
        WHERE diagnosis IS NOT NULL
        GROUP BY diagnosis
        ORDER BY frequency DESC
        LIMIT :limit;

    Args:
        db: Active DatabaseConnection.
        limit: Maximum number of diagnoses to return (default 10).

    Returns:
        List of dicts with diagnosis and frequency. Sorted by frequency descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # WHERE diagnosis IS NOT NULL
        {"$match": {"diagnosis": {"$ne": None, "$exists": True}}},
        # GROUP BY diagnosis  COUNT(*)
        {
            "$group": {
                "_id": "$diagnosis",
                "frequency": {"$sum": 1},
            }
        },
        # SELECT diagnosis, frequency
        {
            "$project": {
                "_id": 0,
                "diagnosis": "$_id",
                "frequency": 1,
            }
        },
        # ORDER BY frequency DESC
        {"$sort": {"frequency": -1}},
        # LIMIT N
        {"$limit": max(1, limit)},
    ]
    try:
        return list(db.get_collection("visits").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_top_diagnoses failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 4 — unique patients per department (via junction table)
# ---------------------------------------------------------------------------

def get_patients_per_department(db: DatabaseConnection) -> list[dict]:
    """Return the number of distinct patients who have visited each department.

    SQL equivalent:
        SELECT
            d.department_name,
            d.location,
            COUNT(DISTINCT v.patient_id) AS unique_patients,
            COUNT(vd.visit_id)           AS total_visit_links
        FROM departments d
        LEFT JOIN visit_departments vd ON d.department_id = vd.department_id
        LEFT JOIN visits            v  ON vd.visit_id      = v.visit_id
        GROUP BY d.department_id
        ORDER BY unique_patients DESC;

    Uses the VisitDepartment junction table to resolve the M-to-N relationship
    between Visit and Department, then counts distinct patients.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts with department_id, department_name, location,
        unique_patients, and total_visit_links.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # Start from departments so that departments with zero visits appear.
        # LEFT JOIN visit_departments ON department_id
        {
            "$lookup": {
                "from": "visit_departments",
                "localField": "department_id",
                "foreignField": "department_id",
                "as": "junctions",
            }
        },
        # LEFT JOIN visits (via junction) to get patient_id and physician_id
        {
            "$lookup": {
                "from": "visits",
                "let": {"visit_ids": "$junctions.visit_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$in": ["$visit_id", {"$ifNull": ["$$visit_ids", []]}]}
                        }
                    },
                    {"$project": {"_id": 0, "visit_id": 1, "patient_id": 1}},
                ],
                "as": "dept_visits",
            }
        },
        # COUNT(DISTINCT patient_id) using $reduce to build a set
        {
            "$addFields": {
                "unique_patients": {
                    "$size": {
                        "$reduce": {
                            "input": "$dept_visits",
                            "initialValue": [],
                            "in": {
                                "$setUnion": ["$$value", ["$$this.patient_id"]]
                            },
                        }
                    }
                },
                "total_visit_links": {"$size": "$junctions"},
            }
        },
        # SELECT
        {
            "$project": {
                "_id": 0,
                "department_id": 1,
                "department_name": 1,
                "location": 1,
                "unique_patients": 1,
                "total_visit_links": 1,
            }
        },
        # ORDER BY unique_patients DESC
        {"$sort": {"unique_patients": -1}},
    ]
    try:
        return list(db.get_collection("departments").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_patients_per_department failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 5 — patients with pending / confirmed appointments
# ---------------------------------------------------------------------------

def get_patients_with_pending_appointments(db: DatabaseConnection) -> list[dict]:
    """Return all patients who have at least one upcoming (scheduled/confirmed) appointment.

    SQL equivalent:
        SELECT
            p.patient_id,
            p.first_name,
            p.last_name,
            p.phone,
            a.appointment_id,
            a.appointment_date_and_time,
            a.reason                     AS appointment_reason,
            a.status,
            ph.first_name || ' ' || ph.last_name AS physician_name,
            ph.speciality
        FROM appointments a
        JOIN patients   p  ON a.patient_id  = p.patient_id
        JOIN physicians ph ON a.physician_id = ph.physician_id
        WHERE a.status IN ('scheduled', 'confirmed')
        ORDER BY a.appointment_date_and_time ASC;

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts, one row per appointment, with patient and physician info
        embedded. Ordered by appointment_date_and_time ascending (soonest first).

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # WHERE status IN ('scheduled', 'confirmed')
        {"$match": {"status": {"$in": ["scheduled", "confirmed"]}}},
        # JOIN patients
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "patient_id",
                "as": "patient",
            }
        },
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        # JOIN physicians
        {
            "$lookup": {
                "from": "physicians",
                "localField": "physician_id",
                "foreignField": "physician_id",
                "as": "physician",
            }
        },
        {"$unwind": {"path": "$physician", "preserveNullAndEmptyArrays": True}},
        # SELECT — flatten into a single readable row
        {
            "$project": {
                "_id": 0,
                "appointment_id": 1,
                "appointment_date_and_time": 1,
                "appointment_reason": "$reason",
                "status": 1,
                "patient_id": 1,
                "patient_first_name": "$patient.first_name",
                "patient_last_name": "$patient.last_name",
                "patient_phone": "$patient.phone",
                "patient_age": "$patient.age",
                "physician_id": 1,
                "physician_name": {
                    "$concat": ["$physician.first_name", " ", "$physician.last_name"]
                },
                "speciality": "$physician.speciality",
            }
        },
        # ORDER BY appointment_date_and_time ASC
        {"$sort": {"appointment_date_and_time": 1}},
    ]
    try:
        return list(db.get_collection("appointments").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(
            f"get_patients_with_pending_appointments failed: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Query 6 — referral network summary
# ---------------------------------------------------------------------------

def get_referral_network_summary(db: DatabaseConnection) -> list[dict]:
    """Return referral counts grouped by (source physician, target physician) pairs.

    SQL equivalent:
        SELECT
            sp.physician_id               AS source_physician_id,
            sp.first_name || ' ' || sp.last_name AS source_physician_name,
            sp.speciality                 AS source_speciality,
            tp.physician_id               AS target_physician_id,
            tp.first_name || ' ' || tp.last_name AS target_physician_name,
            tp.speciality                 AS target_speciality,
            COUNT(*)                      AS referral_count
        FROM referrals r
        JOIN physicians sp ON r.source_physician_id = sp.physician_id
        JOIN physicians tp ON r.target_physician_id = tp.physician_id
        GROUP BY r.source_physician_id, r.target_physician_id
        ORDER BY referral_count DESC;

    Visualises the inter-physician referral network used in the module dashboard.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts with source physician, target physician, and referral_count.
        Sorted by referral_count descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # GROUP BY source_physician_id, target_physician_id  — COUNT(*)
        {
            "$group": {
                "_id": {
                    "source_physician_id": "$source_physician_id",
                    "target_physician_id": "$target_physician_id",
                },
                "referral_count": {"$sum": 1},
                # Collect one status sample to show most common status for this pair
                "statuses": {"$push": "$status"},
            }
        },
        # JOIN physicians (source) — first $lookup
        {
            "$lookup": {
                "from": "physicians",
                "localField": "_id.source_physician_id",
                "foreignField": "physician_id",
                "as": "source_physician",
            }
        },
        {"$unwind": {"path": "$source_physician", "preserveNullAndEmptyArrays": True}},
        # JOIN physicians (target) — second $lookup on same collection
        {
            "$lookup": {
                "from": "physicians",
                "localField": "_id.target_physician_id",
                "foreignField": "physician_id",
                "as": "target_physician",
            }
        },
        {"$unwind": {"path": "$target_physician", "preserveNullAndEmptyArrays": True}},
        # SELECT
        {
            "$project": {
                "_id": 0,
                "source_physician_id": "$_id.source_physician_id",
                "source_physician_name": {
                    "$concat": [
                        "$source_physician.first_name",
                        " ",
                        "$source_physician.last_name",
                    ]
                },
                "source_speciality": "$source_physician.speciality",
                "target_physician_id": "$_id.target_physician_id",
                "target_physician_name": {
                    "$concat": [
                        "$target_physician.first_name",
                        " ",
                        "$target_physician.last_name",
                    ]
                },
                "target_speciality": "$target_physician.speciality",
                "referral_count": 1,
            }
        },
        # ORDER BY referral_count DESC
        {"$sort": {"referral_count": -1}},
    ]
    try:
        return list(db.get_collection("referrals").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_referral_network_summary failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 7 — high-frequency visitors (alert trigger support)
# ---------------------------------------------------------------------------

def get_high_frequency_visitors(
    db: DatabaseConnection,
    min_visits: int = 3,
    days: int = 30,
) -> list[dict]:
    """Return patients who have visited more than min_visits times in the last N days.

    SQL equivalent:
        SELECT
            p.patient_id,
            p.first_name,
            p.last_name,
            p.phone,
            COUNT(v.visit_id) AS visit_count
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE v.visit_date >= NOW() - INTERVAL :days DAY
        GROUP BY v.patient_id
        HAVING COUNT(v.visit_id) >= :min_visits
        ORDER BY visit_count DESC;

    This query powers the visit_frequency_alert_trigger — the same logic that
    raises a HIGH alert when a patient is visiting unusually often.

    Args:
        db: Active DatabaseConnection.
        min_visits: Minimum number of visits to qualify (default 3).
        days: Rolling window in days to count visits within (default 30).

    Returns:
        List of dicts with patient_id, first_name, last_name, phone, visit_count,
        and the list of matching visit_ids. Sorted by visit_count descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    cutoff: datetime = datetime.utcnow() - timedelta(days=days)

    pipeline: list[dict[str, Any]] = [
        # WHERE visit_date >= cutoff
        {"$match": {"visit_date": {"$gte": cutoff}}},
        # GROUP BY patient_id  — COUNT(*) and collect visit IDs
        {
            "$group": {
                "_id": "$patient_id",
                "visit_count": {"$sum": 1},
                "visit_ids": {"$push": "$visit_id"},
                "latest_visit": {"$max": "$visit_date"},
            }
        },
        # HAVING COUNT(*) >= min_visits
        {"$match": {"visit_count": {"$gte": min_visits}}},
        # JOIN patients
        {
            "$lookup": {
                "from": "patients",
                "localField": "_id",
                "foreignField": "patient_id",
                "as": "patient",
            }
        },
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        # SELECT
        {
            "$project": {
                "_id": 0,
                "patient_id": "$_id",
                "first_name": "$patient.first_name",
                "last_name": "$patient.last_name",
                "phone": "$patient.phone",
                "age": "$patient.age",
                "visit_count": 1,
                "latest_visit": 1,
                "visit_ids": 1,
            }
        },
        # ORDER BY visit_count DESC
        {"$sort": {"visit_count": -1}},
    ]
    try:
        return list(db.get_collection("visits").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_high_frequency_visitors failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 8 — full patient profile (complex multi-table join)
# ---------------------------------------------------------------------------

def get_patient_full_profile(
    db: DatabaseConnection,
    patient_id: str,
) -> Optional[dict]:
    """Return a complete profile for one patient joining all six ER tables.

    SQL equivalent (simplified):
        SELECT p.*,
               v.visit_id, v.visit_date, v.reason, v.diagnosis, v.status,
               pv.first_name AS visit_physician_name,
               a.appointment_id, a.appointment_date_and_time, a.status,
               pa.first_name AS appt_physician_name,
               r.referral_id, r.referral_date, r.reason, r.status,
               d.department_name
        FROM patients p
        LEFT JOIN visits       v  ON p.patient_id = v.patient_id
        LEFT JOIN physicians  pv  ON v.physician_id = pv.physician_id
        LEFT JOIN appointments a  ON p.patient_id = a.patient_id
        LEFT JOIN physicians  pa  ON a.physician_id = pa.physician_id
        LEFT JOIN referrals    r  ON p.patient_id = r.patient_id
        LEFT JOIN visit_departments vd ON v.visit_id = vd.visit_id
        LEFT JOIN departments  d  ON vd.department_id = d.department_id
        WHERE p.patient_id = :patient_id;

    Uses nested pipeline $lookup calls so all sub-queries run server-side in
    a single aggregation pass rather than multiple round-trips.

    Args:
        db: Active DatabaseConnection.
        patient_id: The PAT-YYYY-NNN identifier to profile.

    Returns:
        A single dict containing the patient document with embedded visits
        (each with physician and departments), appointments (with physician),
        and referrals. Returns None if the patient is not found.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # WHERE p.patient_id = :patient_id
        {"$match": {"patient_id": patient_id}},

        # LEFT JOIN visits + their physicians + their departments
        {
            "$lookup": {
                "from": "visits",
                "let": {"pid": "$patient_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$patient_id", "$$pid"]}}},
                    # nested: join physician onto each visit
                    {
                        "$lookup": {
                            "from": "physicians",
                            "localField": "physician_id",
                            "foreignField": "physician_id",
                            "as": "physician",
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$physician",
                            "preserveNullAndEmptyArrays": True,
                        }
                    },
                    # nested: join visit_departments + departments
                    {
                        "$lookup": {
                            "from": "visit_departments",
                            "localField": "visit_id",
                            "foreignField": "visit_id",
                            "as": "dept_links",
                        }
                    },
                    {
                        "$lookup": {
                            "from": "departments",
                            "let": {"dept_ids": "$dept_links.department_id"},
                            "pipeline": [
                                {
                                    "$match": {
                                        "$expr": {
                                            "$in": [
                                                "$department_id",
                                                {"$ifNull": ["$$dept_ids", []]},
                                            ]
                                        }
                                    }
                                },
                                {
                                    "$project": {
                                        "_id": 0,
                                        "department_id": 1,
                                        "department_name": 1,
                                    }
                                },
                            ],
                            "as": "departments",
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "visit_id": 1,
                            "visit_date": 1,
                            "reason": 1,
                            "diagnosis": 1,
                            "status": 1,
                            "physician_name": {
                                "$concat": [
                                    "$physician.first_name",
                                    " ",
                                    "$physician.last_name",
                                ]
                            },
                            "physician_speciality": "$physician.speciality",
                            "departments": 1,
                        }
                    },
                    {"$sort": {"visit_date": -1}},
                ],
                "as": "visits",
            }
        },

        # LEFT JOIN appointments + their physicians
        {
            "$lookup": {
                "from": "appointments",
                "let": {"pid": "$patient_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$patient_id", "$$pid"]}}},
                    {
                        "$lookup": {
                            "from": "physicians",
                            "localField": "physician_id",
                            "foreignField": "physician_id",
                            "as": "physician",
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$physician",
                            "preserveNullAndEmptyArrays": True,
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "appointment_id": 1,
                            "appointment_date_and_time": 1,
                            "reason": 1,
                            "status": 1,
                            "physician_name": {
                                "$concat": [
                                    "$physician.first_name",
                                    " ",
                                    "$physician.last_name",
                                ]
                            },
                            "speciality": "$physician.speciality",
                        }
                    },
                    {"$sort": {"appointment_date_and_time": -1}},
                ],
                "as": "appointments",
            }
        },

        # LEFT JOIN referrals + source and target physician names
        {
            "$lookup": {
                "from": "referrals",
                "let": {"pid": "$patient_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$patient_id", "$$pid"]}}},
                    {
                        "$lookup": {
                            "from": "physicians",
                            "localField": "source_physician_id",
                            "foreignField": "physician_id",
                            "as": "source_physician",
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$source_physician",
                            "preserveNullAndEmptyArrays": True,
                        }
                    },
                    {
                        "$lookup": {
                            "from": "physicians",
                            "localField": "target_physician_id",
                            "foreignField": "physician_id",
                            "as": "target_physician",
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$target_physician",
                            "preserveNullAndEmptyArrays": True,
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "referral_id": 1,
                            "referral_date": 1,
                            "reason": 1,
                            "status": 1,
                            "source_physician_name": {
                                "$concat": [
                                    "$source_physician.first_name",
                                    " ",
                                    "$source_physician.last_name",
                                ]
                            },
                            "source_speciality": "$source_physician.speciality",
                            "target_physician_name": {
                                "$concat": [
                                    "$target_physician.first_name",
                                    " ",
                                    "$target_physician.last_name",
                                ]
                            },
                            "target_speciality": "$target_physician.speciality",
                        }
                    },
                    {"$sort": {"referral_date": -1}},
                ],
                "as": "referrals",
            }
        },

        # Drop MongoDB internal _id before returning
        {"$project": {"_id": 0}},
    ]
    try:
        results = list(db.get_collection("patients").aggregate(pipeline))
        return results[0] if results else None
    except PyMongoError as exc:
        raise RuntimeError(f"get_patient_full_profile failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 9 — physician workload
# ---------------------------------------------------------------------------

def get_physician_workload(db: DatabaseConnection) -> list[dict]:
    """Return the total number of visits and appointments handled by each physician.

    SQL equivalent:
        SELECT
            ph.physician_id,
            ph.first_name || ' ' || ph.last_name AS physician_name,
            ph.speciality,
            d.department_name,
            COALESCE(v.visit_count, 0)       AS total_visits,
            COALESCE(a.appt_count, 0)        AS total_appointments,
            COALESCE(v.visit_count, 0)
            + COALESCE(a.appt_count, 0)      AS total_workload
        FROM physicians ph
        LEFT JOIN departments d ON ph.department_id = d.department_id
        LEFT JOIN (SELECT physician_id, COUNT(*) AS visit_count
                   FROM visits GROUP BY physician_id) v
               ON ph.physician_id = v.physician_id
        LEFT JOIN (SELECT physician_id, COUNT(*) AS appt_count
                   FROM appointments GROUP BY physician_id) a
               ON ph.physician_id = a.physician_id
        ORDER BY total_workload DESC;

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts with physician_id, physician_name, speciality,
        department_name, total_visits, total_appointments, total_workload.
        Sorted by total_workload descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # LEFT JOIN departments ON department_id
        {
            "$lookup": {
                "from": "departments",
                "localField": "department_id",
                "foreignField": "department_id",
                "as": "department",
            }
        },
        {"$unwind": {"path": "$department", "preserveNullAndEmptyArrays": True}},

        # Subquery: COUNT visits per physician (pipeline-based lookup → single count doc)
        {
            "$lookup": {
                "from": "visits",
                "let": {"pid": "$physician_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$physician_id", "$$pid"]}}},
                    {"$count": "count"},
                ],
                "as": "_visit_stats",
            }
        },
        # Subquery: COUNT appointments per physician
        {
            "$lookup": {
                "from": "appointments",
                "let": {"pid": "$physician_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$physician_id", "$$pid"]}}},
                    {"$count": "count"},
                ],
                "as": "_appt_stats",
            }
        },

        # COALESCE(..., 0) — use $ifNull so physicians with no records get 0
        {
            "$addFields": {
                "total_visits": {
                    "$ifNull": [{"$arrayElemAt": ["$_visit_stats.count", 0]}, 0]
                },
                "total_appointments": {
                    "$ifNull": [{"$arrayElemAt": ["$_appt_stats.count", 0]}, 0]
                },
            }
        },
        {
            "$addFields": {
                "total_workload": {"$add": ["$total_visits", "$total_appointments"]}
            }
        },

        # SELECT
        {
            "$project": {
                "_id": 0,
                "physician_id": 1,
                "physician_name": {
                    "$concat": ["$first_name", " ", "$last_name"]
                },
                "first_name": 1,
                "last_name": 1,
                "speciality": 1,
                "department_name": "$department.department_name",
                "total_visits": 1,
                "total_appointments": 1,
                "total_workload": 1,
            }
        },

        # ORDER BY total_workload DESC
        {"$sort": {"total_workload": -1}},
    ]
    try:
        return list(db.get_collection("physicians").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_physician_workload failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query 10 — department statistics
# ---------------------------------------------------------------------------

def get_department_statistics(db: DatabaseConnection) -> list[dict]:
    """Return full analytics for each department: visit counts, unique patients,
    active physicians, and top diagnosis.

    SQL equivalent:
        SELECT
            d.department_id,
            d.department_name,
            d.location,
            COUNT(vd.visit_id)                AS total_visits,
            COUNT(DISTINCT v.patient_id)      AS unique_patients,
            COUNT(DISTINCT v.physician_id)    AS active_physicians,
            (SELECT TOP 1 diagnosis
             FROM visits v2
             JOIN visit_departments vd2 ON v2.visit_id = vd2.visit_id
             WHERE vd2.department_id = d.department_id
               AND v2.diagnosis IS NOT NULL
             GROUP BY v2.diagnosis
             ORDER BY COUNT(*) DESC)          AS top_diagnosis
        FROM departments d
        LEFT JOIN visit_departments vd ON d.department_id = vd.department_id
        LEFT JOIN visits            v  ON vd.visit_id      = v.visit_id
        GROUP BY d.department_id
        ORDER BY total_visits DESC;

    The top_diagnosis sub-query is implemented as a nested pipeline $lookup
    with $group + $sort + $limit: 1 to find the most frequent diagnosis per dept.

    Args:
        db: Active DatabaseConnection.

    Returns:
        List of dicts with department_id, department_name, location,
        total_visits, unique_patients, active_physicians, top_diagnosis.
        Sorted by total_visits descending.

    Raises:
        RuntimeError: On unexpected database error.
    """
    pipeline: list[dict[str, Any]] = [
        # LEFT JOIN visit_departments ON department_id
        {
            "$lookup": {
                "from": "visit_departments",
                "localField": "department_id",
                "foreignField": "department_id",
                "as": "junctions",
            }
        },

        # LEFT JOIN visits (via junction) — bring in patient_id, physician_id, diagnosis
        {
            "$lookup": {
                "from": "visits",
                "let": {"visit_ids": "$junctions.visit_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$in": [
                                    "$visit_id",
                                    {"$ifNull": ["$$visit_ids", []]},
                                ]
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "visit_id": 1,
                            "patient_id": 1,
                            "physician_id": 1,
                            "diagnosis": 1,
                        }
                    },
                ],
                "as": "dept_visits",
            }
        },

        # Nested pipeline: find top diagnosis for this department
        # Equivalent to the correlated sub-select in the SQL above
        {
            "$lookup": {
                "from": "visits",
                "let": {"visit_ids": "$junctions.visit_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {
                                        "$in": [
                                            "$visit_id",
                                            {"$ifNull": ["$$visit_ids", []]},
                                        ]
                                    },
                                    {"$ne": ["$diagnosis", None]},
                                ]
                            }
                        }
                    },
                    {"$group": {"_id": "$diagnosis", "cnt": {"$sum": 1}}},
                    {"$sort": {"cnt": -1}},
                    {"$limit": 1},
                    {"$project": {"_id": 0, "diagnosis": "$_id"}},
                ],
                "as": "_top_diag_result",
            }
        },

        # COUNT(DISTINCT patient_id) and COUNT(DISTINCT physician_id) via $reduce
        {
            "$addFields": {
                "total_visits": {"$size": "$dept_visits"},
                "unique_patients": {
                    "$size": {
                        "$reduce": {
                            "input": "$dept_visits",
                            "initialValue": [],
                            "in": {
                                "$setUnion": ["$$value", ["$$this.patient_id"]]
                            },
                        }
                    }
                },
                "active_physicians": {
                    "$size": {
                        "$reduce": {
                            "input": "$dept_visits",
                            "initialValue": [],
                            "in": {
                                "$setUnion": ["$$value", ["$$this.physician_id"]]
                            },
                        }
                    }
                },
                "top_diagnosis": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$_top_diag_result.diagnosis", 0]},
                        "No diagnosis recorded",
                    ]
                },
            }
        },

        # SELECT
        {
            "$project": {
                "_id": 0,
                "department_id": 1,
                "department_name": 1,
                "location": 1,
                "total_visits": 1,
                "unique_patients": 1,
                "active_physicians": 1,
                "top_diagnosis": 1,
            }
        },

        # ORDER BY total_visits DESC
        {"$sort": {"total_visits": -1}},
    ]
    try:
        return list(db.get_collection("departments").aggregate(pipeline))
    except PyMongoError as exc:
        raise RuntimeError(f"get_department_statistics failed: {exc}") from exc


# ---------------------------------------------------------------------------
# run_all_queries — convenience runner
# ---------------------------------------------------------------------------

def run_all_queries(
    db: DatabaseConnection,
    sample_patient_id: Optional[str] = None,
) -> dict[str, Any]:
    """Execute all 10 aggregation queries and return their results as a dict.

    Designed for use in the Streamlit dashboard and for demonstration during
    the project viva. Each key in the returned dict matches the query name.

    If sample_patient_id is not provided, the function picks the first patient
    in the collection to populate the get_patient_full_profile result.

    Args:
        db: Active DatabaseConnection.
        sample_patient_id: Optional PAT-YYYY-NNN to use for the full-profile query.

    Returns:
        Dict mapping query name → list[dict] result. The full_profile entry is
        a single dict (or None) rather than a list.

    Raises:
        RuntimeError: If any individual query fails unexpectedly.
    """
    # Resolve a sample patient_id if none was provided
    if sample_patient_id is None:
        try:
            first = db.get_collection("patients").find_one({}, {"patient_id": 1})
            sample_patient_id = first["patient_id"] if first else "PAT-2024-001"
        except Exception:
            sample_patient_id = "PAT-2024-001"

    results: dict[str, Any] = {}

    queries: list[tuple[str, Any]] = [
        ("patients_with_visit_count",          lambda: get_patients_with_visit_count(db)),
        ("visit_frequency_by_month",           lambda: get_visit_frequency_by_month(db)),
        ("top_diagnoses",                      lambda: get_top_diagnoses(db)),
        ("patients_per_department",            lambda: get_patients_per_department(db)),
        ("patients_with_pending_appointments", lambda: get_patients_with_pending_appointments(db)),
        ("referral_network_summary",           lambda: get_referral_network_summary(db)),
        ("high_frequency_visitors",            lambda: get_high_frequency_visitors(db)),
        ("patient_full_profile",               lambda: get_patient_full_profile(db, sample_patient_id)),
        ("physician_workload",                 lambda: get_physician_workload(db)),
        ("department_statistics",              lambda: get_department_statistics(db)),
    ]

    for name, fn in queries:
        try:
            results[name] = fn()
        except RuntimeError as exc:
            # Store the error message so the dashboard can display it
            # without crashing the whole run.
            results[name] = {"error": str(exc)}

    return results
