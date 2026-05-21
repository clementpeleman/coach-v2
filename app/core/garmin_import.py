"""Garmin import helpers: migrate orphaned rows and direct activity pull fallback."""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

import requests
from sqlalchemy.orm import Session

from app.database.models import (
    GarminActivityAuxiliaryData,
    GarminActivityData,
    GarminHealthData,
    GarminToken,
    GarminWebhookEvent,
    UserProfile,
)
from app.tools.garmin_client import (
    write_activity_auxiliary_data,
    write_activity_data,
    write_health_data,
)

if TYPE_CHECKING:
    from app.tools.garmin_client import GarminAPIClient

logger = logging.getLogger(__name__)

REQUESTED_BACKFILL_STATUSES = {"requested", "requested_with_adjusted_start"}


def resolve_internal_user_for_garmin(db: Session, garmin_user_id: Optional[str]) -> Optional[int]:
    """Map a Garmin user id to our internal user id via token or profile."""
    if not garmin_user_id:
        return None
    token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
    if token:
        return int(token.user_id)
    profile = db.query(UserProfile).filter(UserProfile.garmin_user_id == garmin_user_id).first()
    if profile:
        return int(profile.user_id)
    return None


def garmin_user_id_for_internal_user(db: Session, user_id: int) -> Optional[str]:
    token = db.query(GarminToken).filter(GarminToken.user_id == user_id).first()
    if token and token.garmin_user_id:
        return str(token.garmin_user_id)
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile and profile.garmin_user_id:
        return str(profile.garmin_user_id)
    return None


def replay_failed_webhooks(
    db: Session,
    user_id: int,
    *,
    garmin_user_id: Optional[str] = None,
    hours: int = 72,
    limit: int = 40,
) -> Dict[str, Any]:
    """Re-process stored partial/failed webhook payloads once a token is available again."""
    resolved_garmin_user_id = garmin_user_id or garmin_user_id_for_internal_user(db, user_id)
    query = db.query(GarminWebhookEvent).filter(
        GarminWebhookEvent.status.in_(["partial", "failed"]),
        GarminWebhookEvent.created_at >= datetime.utcnow() - timedelta(hours=hours),
    )
    if resolved_garmin_user_id:
        query = query.filter(GarminWebhookEvent.garmin_user_id == resolved_garmin_user_id)
    else:
        query = query.filter(GarminWebhookEvent.user_id == user_id)

    events = query.order_by(GarminWebhookEvent.created_at.asc()).limit(limit).all()
    result: Dict[str, Any] = {
        "attempted": len(events),
        "replayed": 0,
        "stored_items": 0,
        "still_failed": 0,
        "errors": [],
    }

    for event in events:
        try:
            payload = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
        except json.JSONDecodeError:
            result["still_failed"] += 1
            result["errors"].append(f"event {event.id}: invalid payload JSON")
            continue

        if event.source == "health":
            stats = _replay_health_payload(db, user_id, payload)
        elif event.source == "activity":
            stats = _replay_activity_payload(db, user_id, payload)
        else:
            continue

        result["stored_items"] += stats.get("stored_items", 0)
        if stats.get("errors"):
            result["still_failed"] += 1
            result["errors"].extend(stats["errors"][:3])
            event.status = "partial"
            event.error = "\n".join(stats["errors"][:10])
        else:
            result["replayed"] += 1
            event.status = "processed"
            event.error = None
        event.user_id = user_id
        event.updated_at = datetime.utcnow()

    if events:
        db.commit()
    return result


def _replay_health_payload(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    stats = {"stored_items": 0, "errors": []}
    client = None
    for summary_type, items in payload.items():
        if summary_type == "deregistrations" or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            callback_url = item.get("callbackURL")
            if not callback_url:
                try:
                    write_health_data(db, user_id, summary_type, [item])
                    stats["stored_items"] += 1
                except Exception as exc:
                    stats["errors"].append(f"PUSH {summary_type}: {exc}")
                continue
            try:
                if client is None:
                    from app.tools.garmin_client import GarminAPIClient

                    client = GarminAPIClient(db, user_id)
                response = requests.get(callback_url, headers=client._get_headers(), timeout=30)
                if response.status_code == 200:
                    summaries = response.json()
                    write_health_data(db, user_id, summary_type, summaries)
                    stats["stored_items"] += len(summaries) if isinstance(summaries, list) else 1
                else:
                    stats["errors"].append(
                        f"PING {summary_type}: callback {response.status_code}"
                    )
            except Exception as exc:
                stats["errors"].append(f"PING {summary_type}: {exc}")
    return stats


def _replay_activity_payload(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    stats = {"stored_items": 0, "errors": []}
    client = None
    for summary_type, items in payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            callback_url = item.get("callbackURL")
            if not callback_url:
                try:
                    write_activity_data(db, user_id, [item], summary_type)
                    stats["stored_items"] += 1
                except Exception as exc:
                    stats["errors"].append(f"PUSH {summary_type}: {exc}")
                continue
            try:
                if client is None:
                    from app.tools.garmin_client import GarminAPIClient

                    client = GarminAPIClient(db, user_id)
                if summary_type == "activityFiles":
                    write_activity_auxiliary_data(db, user_id, summary_type, [item])
                    file_response = requests.get(callback_url, headers=client._get_headers(), timeout=60)
                    if file_response.status_code == 200:
                        payload_item = dict(item)
                        payload_item["contentType"] = file_response.headers.get("content-type")
                        payload_item["contentLength"] = len(file_response.content)
                        payload_item["contentBase64"] = base64.b64encode(file_response.content).decode("ascii")
                        write_activity_auxiliary_data(db, user_id, "activityFiles", [payload_item])
                        stats["stored_items"] += 1
                    else:
                        stats["errors"].append(
                            f"activityFiles callback {file_response.status_code}"
                        )
                    continue
                response = requests.get(callback_url, headers=client._get_headers(), timeout=30)
                if response.status_code == 200:
                    summaries = response.json()
                    write_activity_data(db, user_id, summaries, summary_type)
                    stats["stored_items"] += len(summaries) if isinstance(summaries, list) else 1
                else:
                    stats["errors"].append(
                        f"PING {summary_type}: callback {response.status_code}"
                    )
            except Exception as exc:
                stats["errors"].append(f"PING {summary_type}: {exc}")
    return stats


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
    Deprecated: Garmin Wellness API rejects ad-hoc REST pulls with HTTP 400.

    Historical activity data must arrive via backfill + webhook callbacks only.
    Kept for diagnostics; do not call in production import flows.
    """
    return {
        "days": days,
        "activities": 0,
        "activity_details": 0,
        "windows": 0,
        "errors": ["Garmin staat geen directe REST-pull toe; gebruik backfill + webhooks."],
        "status": "unsupported",
    }


def build_import_message(
    *,
    activity_sessions: int,
    backfill_summary: Dict[str, Any],
    webhook_replay: Optional[Dict[str, Any]] = None,
    direct_pull: Optional[Dict[str, Any]] = None,
    migration: Optional[Dict[str, Any]] = None,
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

    replay_stored = (webhook_replay or {}).get("stored_items", 0) or 0
    replay_count = (webhook_replay or {}).get("replayed", 0) or 0
    if replay_stored > 0:
        parts.append(
            f"{replay_stored} records hersteld uit eerder mislukte Garmin-webhooks."
        )
    elif replay_count > 0:
        parts.append("Eerder mislukte webhooks opnieuw verwerkt.")

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
    elif backfill_summary.get("all_duplicate") and activity_sessions <= 1:
        parts.append(
            "Garmin stuurde geen historiek opnieuw (duplicate backfill). "
            "Alleen activiteiten na je (her)koppeling komen automatisch binnen via webhooks."
        )

    if backfill_summary.get("requested_count", 0) > 0 and activity_sessions <= 1:
        parts.append(
            "Historiek is aangevraagd en komt meestal binnen 2–15 minuten via webhooks. "
            "Laat Garmin verbonden tot alles binnen is."
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
