"""Alerts component — severity cards with acknowledge buttons.

Fetches unacknowledged alerts, color-codes them by severity, provides
type filtering and per-alert acknowledgement.
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

from backend.database import DatabaseConnection
from backend.models import AlertSeverity, AlertType



# Severity to color mapping
_SEVERITY_COLORS: dict[str, str] = {
    AlertSeverity.CRITICAL: "#EF4444",
    AlertSeverity.HIGH: "#F59E0B",
    AlertSeverity.MEDIUM: "#2563EB",
    AlertSeverity.LOW: "#64748B",
}


def _count_active_alerts(db: DatabaseConnection) -> int:
    """Return the total number of unacknowledged alerts.

    Args:
        db: Active DatabaseConnection.

    Returns:
        Count of unacknowledged alerts, or 0 on error.
    """
    try:
        return db.get_collection("alerts").count_documents(
            {"is_acknowledged": False}
        )
    except PyMongoError:
        return 0


def _fetch_alerts(
    db: DatabaseConnection, alert_type: str = "All"
) -> list[dict]:
    """Fetch unacknowledged alerts, optionally filtered by type.

    Args:
        db: Active DatabaseConnection.
        alert_type: Alert type filter string, or "All" for no filter.

    Returns:
        List of alert dicts sorted by severity (critical first) then date.
    """
    try:
        query: dict[str, Any] = {"is_acknowledged": False}
        if alert_type != "All":
            query["alert_type"] = alert_type.lower()

        severity_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
        }

        alerts = list(
            db.get_collection("alerts")
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .limit(100)
        )

        alerts.sort(
            key=lambda a: severity_order.get(a.get("severity", "low"), 4)
        )
        return alerts

    except PyMongoError:
        return []


def _acknowledge_alert(db: DatabaseConnection, alert_id: str) -> bool:
    """Mark an alert as acknowledged.

    Args:
        db: Active DatabaseConnection.
        alert_id: The alert_id to acknowledge.

    Returns:
        True if the alert was successfully acknowledged.
    """
    try:
        result = db.get_collection("alerts").update_one(
            {"alert_id": alert_id},
            {
                "$set": {
                    "is_acknowledged": True,
                    "acknowledged_by": "clinical_staff",
                    "acknowledged_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0
    except PyMongoError:
        return False


def render(db: DatabaseConnection) -> None:
    """Render the alerts panel with severity-colored cards.

    Args:
        db: Active DatabaseConnection.
    """
    total_active = _count_active_alerts(db)

    st.caption(f"ACTIVE ALERTS ({total_active})")

    if total_active == 0:
        st.success("No active alerts. All clear.")
        return

    # Type filter
    type_options = ["All"] + [t.value.replace("_", " ").title() for t in AlertType]
    selected_type = st.selectbox(
        "Filter by Type",
        options=type_options,
        key="alert_type_filter",
    )

    # Map display name back to enum value
    filter_value = "All"
    if selected_type != "All":
        filter_value = selected_type.lower().replace(" ", "_")
        try:
            AlertType(filter_value)
        except ValueError:
            filter_value = "All"

    alerts = _fetch_alerts(db, filter_value)

    if not alerts:
        st.info(
            f"No alerts matching **{selected_type}**. "
            f"{total_active} alert(s) exist under other types."
        )
        return

    st.caption(f"Showing {len(alerts)} unacknowledged alert(s)")

    for idx, alert in enumerate(alerts):
        severity = alert.get("severity", "low")
        alert_id = alert.get("alert_id", f"unknown-{idx}")

        created_at = alert.get("created_at")
        time_str = (
            created_at.strftime("%d %b %Y, %I:%M %p")
            if hasattr(created_at, "strftime")
            else str(created_at)
        )

        with st.container(border=True):
            header_col, action_col = st.columns([5, 1])

            with header_col:
                st.write(
                    f"**[{severity.upper()}]** {alert.get('title', 'Alert')}"
                )
                st.write(alert.get("message", "No details available."))
                st.caption(
                    f"Patient: {alert.get('patient_id', 'N/A')} | "
                    f"Source: {alert.get('source', 'system')} | "
                    f"{time_str}"
                )

            with action_col:
                if st.button(
                    "Acknowledge",
                    key=f"ack_{alert_id}_{idx}",
                    use_container_width=True,
                ):
                    if _acknowledge_alert(db, alert_id):
                        st.success("Acknowledged")
                        st.rerun()
                    else:
                        st.error("Failed")
