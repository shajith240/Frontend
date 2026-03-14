"""Aggregation pipeline queries for the patient-demographics module.

Import directly from this package:

    from database.queries.aggregations import (
        get_patients_with_visit_count,
        get_top_diagnoses,
        run_all_queries,
        ...
    )
"""

from database.queries.aggregations import (
    get_patients_with_visit_count,
    get_visit_frequency_by_month,
    get_top_diagnoses,
    get_patients_per_department,
    get_patients_with_pending_appointments,
    get_referral_network_summary,
    get_high_frequency_visitors,
    get_patient_full_profile,
    get_physician_workload,
    get_department_statistics,
    run_all_queries,
)

__all__ = [
    "get_patients_with_visit_count",
    "get_visit_frequency_by_month",
    "get_top_diagnoses",
    "get_patients_per_department",
    "get_patients_with_pending_appointments",
    "get_referral_network_summary",
    "get_high_frequency_visitors",
    "get_patient_full_profile",
    "get_physician_workload",
    "get_department_statistics",
    "run_all_queries",
]
