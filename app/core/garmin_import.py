"""Garmin import helpers: migrate orphaned rows and direct activity pull fallback."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.database.models import (
    GarminActivityAuxiliaryData,
    GarminActivityData,
    GarminHealthData,
    GarminWebhookEvent,
)

if TYPE_CHECKING:
    from app.tools.garmin_client import GarminAPIClient

logger = logging.getLogger(__name__)

REQUESTED_BACKFILL_STATUSES = {"requested", "requested_with_adjusted_start"}


def migrate_garmin_data_between_users(db: Session, source_user_id: int, target_user_id: int) -> Dict[str, int]:
    """Re-assign stored Garmin rows from a previous internal user to the current account."""
    if source_user_id == target_user_id:
        return {"activities": 0, "activity_auxiliary": 0, "health": 0}

    counts = {"activities": 0, "activity_auxiliary": 0, "health": 0}
    for row in db.query(GarminActivityData).filter(GarminActivityData.user_id == source_user_id).all():
        row.user_id = target_user_id
        counts["activities"] += 1
    for row in db.query(GarminActivityAuxiliaryData).filter(
        GarminActivityAuxiliaryData.user_id == source_user_id
    ).all():
        row.user_id = target_user_id
        counts["activity_auxiliary"] += 1
    for row in db.query(GarminHealthData).filter(GarminHealthData.user_id == source_user_id).all():
        row.user_id = target_user_id
        counts["health"] += 1

    if any(counts.values()):
        db.commit()
        logger.info(
            "Migrated Garmin data user %s -> %s: %s",
            source_user_id,
            target_user_id,
            counts,
        )
    return counts


def find_previous_user_ids_for_garmin(db: Session, garmin_user_id: str, current_user_id: int) -> List[int]:
    """Find internal users that previously received webhooks for this Garmin account."""
    rows = (
        db.query(GarminWebhookEvent.user_id)
        .filter(
            GarminWebhookEvent.garmin_user_id == garmin_user_id,
            GarminWebhookEvent.user_id.isnot(None),
            GarminWebhookEvent.user_id != current_user_id,
        )
        .distinct()
        .all()
    )
    return sorted({int(row[0]) for row in rows if row[0] is not None})


def migrate_garmin_account_data(
    db: Session,
    *,
    garmin_user_id: str,
    target_user_id: int,
    previous_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Move orphaned Garmin rows onto the active account after reconnect."""
    source_ids: List[int] = []
    if previous_user_id and previous_user_id != target_user_id:
        source_ids.append(previous_user_id)
    source_ids.extend(find_previous_user_ids_for_garmin(db, garmin_user_id, target_user_id))

    merged = {"activities": 0, "activity_auxiliary": 0, "health": 0, "source_user_ids": []}
    seen = set()
    for source_user_id in source_ids:
        if source_user_id in seen or source_user_id == target_user_id:
            continue
        seen.add(source_user_id)
        moved = migrate_garmin_data_between_users(db, source_user_id, target_user_id)
        if any(moved.values()):
            merged["source_user_ids"].append(source_user_id)
        for key in ("activities", "activity_auxiliary", "health"):
            merged[key] += moved[key]
    return merged


def activity_backfill_summary(backfill_result: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize activity backfill windows for diagnostics."""
    activity = backfill_result.get("activity") or {}
    windows: List[Dict[str, Any]] = []
    for data_type, entries in activity.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                windows.append({"type": data_type, **entry})

    statuses = [str(window.get("status") or "") for window in windows]
    return {
        "windows": windows,
        "requested_count": sum(1 for status in statuses if status in REQUESTED_BACKFILL_STATUSES),
        "duplicate_count": sum(1 for status in statuses if status == "duplicate"),
        "error_count": sum(
            1 for status in statuses if status not in REQUESTED_BACKFILL_STATUSES.union({"duplicate", "skipped"})
        ),
        "all_duplicate": bool(windows) and all(status == "duplicate" for status in statuses),
        "skipped_permissions": bool(backfill_result.get("skipped", {}).get("activity")),
    }


def split_upload_windows(start: datetime, end: datetime, window_days: int = 1) -> Iterable[tuple[datetime, datetime]]:
    """Split a range into upload-time windows for Garmin REST activity pulls."""
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=window_days) - timedelta(seconds=1), end)
        yield cursor, window_end
        cursor = window_end + timedelta(seconds=1)


def pull_activity_history_direct(client: "GarminAPIClient", days: int = 30) -> Dict[str, Any]:
    """
    Pull activity summaries directly from Garmin when webhook backfill won't replay history.

    Activity REST pulls are supported; health pulls are webhook/backfill-only in production.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    result: Dict[str, Any] = {
        "days": days,
        "activities": 0,
        "activity_details": 0,
        "windows": 0,
        "errors": [],
        "status": "ok",
    }

    for window_start, window_end in split_upload_windows(start, end, window_days=1):
        upload_start = int(window_start.timestamp())
        upload_end = int(window_end.timestamp())
        result["windows"] += 1
        try:
            activities = client.get_activities(upload_start, upload_end, store=True)
            if isinstance(activities, list):
                result["activities"] += len(activities)
        except Exception as exc:
            message = f"activities {window_start.date()}..{window_end.date()}: {exc}"
            result["errors"].append(message)
            logger.warning("Direct activity pull failed: %s", message)

        try:
            details = client.get_activity_details(upload_start, upload_end, store=True)
            if isinstance(details, list):
                result["activity_details"] += len(details)
        except Exception as exc:
            message = f"activityDetails {window_start.date()}..{window_end.date()}: {exc}"
            result["errors"].append(message)
            logger.warning("Direct activity detail pull failed: %s", message)

    if result["activities"] == 0 and result["errors"]:
        result["status"] = "failed"
    elif result["errors"]:
        result["status"] = "partial"
    return result


def build_import_message(
    *,
    activity_sessions: int,
    backfill_summary: Dict[str, Any],
    direct_pull: Optional[Dict[str, Any]],
    migration: Optional[Dict[str, Any]],
    permissions_assumed: bool,
    capabilities: Dict[str, Any],
) -> str:
    """Human-readable import result for the profile UI."""
    parts: List[str] = []

    if migration and migration.get("source_user_ids"):
        moved = migration.get("activities", 0)
        parts.append(
            f"{moved} oudere activiteiten gekoppeld aan dit account na opnieuw verbinden."
        )

    if direct_pull and direct_pull.get("activities", 0) > 0:
        parts.append(
            f"{direct_pull['activities']} activiteiten direct opgehaald bij Garmin "
            f"(laatste {direct_pull.get('days', 30)} dagen)."
        )

    if activity_sessions > 0 and not parts:
        parts.append(
            f"{activity_sessions} activiteiten staan in de app voor de laatste 30 dagen."
        )

    if backfill_summary.get("skipped_permissions"):
        parts.append(
            "Historische activiteiten-import overgeslagen: ACTIVITY_EXPORT of "
            "HISTORICAL_DATA_EXPORT ontbreekt in Garmin-permissions."
        )
    elif backfill_summary.get("all_duplicate") and activity_sessions <= 1 and not (
        direct_pull and direct_pull.get("activities", 0) > 0
    ):
        parts.append(
            "Garmin stuurde geen historiek opnieuw (duplicate backfill). "
            "Alleen activiteiten na je (her)koppeling komen automatisch binnen tenzij direct ophalen lukt."
        )

    if backfill_summary.get("requested_count", 0) > 0 and activity_sessions <= 1 and not (
        direct_pull and direct_pull.get("activities", 0) > 0
    ):
        parts.append(
            "Historiek is aangevraagd en komt meestal binnen 2–15 minuten via webhooks."
        )

    if permissions_assumed:
        parts.append(
            "Garmin-permissions waren nog niet zichtbaar; import liep met standaard scopes."
        )

    if not capabilities.get("ready_for_initial_import"):
        missing = capabilities.get("missing_required_for_initial_import") or []
        if missing:
            parts.append(f"Ontbrekende permissions: {', '.join(missing)}.")

    if not parts:
        return (
            "Import gestart. Nieuwe activiteiten komen automatisch binnen; "
            "historiek via webhook kan enkele minuten duren."
        )
    return " ".join(parts)
