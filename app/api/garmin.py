"""Garmin OAuth2 and webhook API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
import logging
import requests
import time
import json
import re
import os
from datetime import datetime, timedelta

from app.config import settings
from app.database.database import get_db
from app.tools.garmin_oauth import GarminOAuthService
from app.tools.garmin_client import GarminAPIClient
from app.database.models import (
    GarminActivityAuxiliaryData,
    GarminActivityData,
    GarminHealthData,
    GarminToken,
    GarminWebhookEvent,
    OAuthSession,
    WorkoutHistory,
)
from app.tools.training_recommendation_engine import (
    adjust_recommendation,
    build_recommendation,
    garmin_sport_type,
    recommendation_to_workout_steps,
    workout_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/garmin", tags=["garmin"])
MIN_START_TIME_PATTERN = re.compile(r"before min start time of ([0-9T:\.\-]+Z)")
ACTIVITY_BACKFILL_WINDOW_DAYS = 30
HEALTH_BACKFILL_WINDOW_DAYS = 90
DEFAULT_ACTIVITY_BACKFILL_TYPES = ["activities", "activityDetails", "moveIQActivities"]
CORE_ACTIVITY_BACKFILL_TYPES = ["activities", "activityDetails"]
DEFAULT_HEALTH_BACKFILL_TYPES = [
    "dailies",
    "epochs",
    "sleeps",
    "bodyComps",
    "stressDetails",
    "userMetrics",
    "pulseOx",
    "respiration",
    "healthSnapshot",
    "hrv",
    "bloodPressures",
    "skinTemp",
]
CORE_HEALTH_BACKFILL_TYPES = ["dailies", "sleeps", "stressDetails", "hrv"]
REQUIRED_EXPORT_PERMISSIONS = {"ACTIVITY_EXPORT", "HISTORICAL_DATA_EXPORT"}
POST_OAUTH_EXPORT_PERMISSIONS = {"ACTIVITY_EXPORT", "HISTORICAL_DATA_EXPORT", "HEALTH_EXPORT"}
INITIAL_ACTIVITY_BACKFILL_DAYS = 30
INITIAL_HEALTH_BACKFILL_DAYS = 30


class RecommendationAdjustRequest(BaseModel):
    user_id: int
    recommendation: Dict[str, Any] = Field(default_factory=dict)
    instruction: str
    training_profile: Optional[Dict[str, Any]] = None


class WorkoutCreateRequest(BaseModel):
    user_id: int
    recommendation: Dict[str, Any]
    status: str = "approved"


def resolve_user_id(user_id: Optional[int], telegram_user_id: Optional[int]) -> int:
    """Resolve internal user id while supporting legacy query parameter names."""
    resolved_user_id = user_id if user_id is not None else telegram_user_id
    if resolved_user_id is None:
        raise HTTPException(status_code=422, detail="user_id is required")
    return resolved_user_id


def extract_permission_names(permissions_response) -> set[str]:
    """Normalize Garmin's permissions response to a set of permission names."""
    if isinstance(permissions_response, dict):
        permissions = permissions_response.get("permissions", [])
    else:
        permissions = permissions_response or []
    return {str(permission) for permission in permissions}


def fetch_permissions_with_retry(
    oauth_service: GarminOAuthService,
    *,
    access_token: Optional[str] = None,
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    max_attempts: int = 10,
) -> list[str]:
    """Garmin permissions can lag seconds after OAuth — retry before deciding to skip backfill."""
    if not access_token:
        if db is None or user_id is None:
            return []
        access_token = oauth_service.get_valid_access_token(db, user_id)
    if not access_token:
        return []

    for attempt in range(max_attempts):
        try:
            raw = oauth_service.get_user_permissions(access_token, retries=3)
            names = sorted(extract_permission_names(raw))
            if names:
                return names
        except Exception as exc:
            logger.warning(f"Permissions fetch attempt {attempt + 1}/{max_attempts}: {exc}")
        time.sleep(1.0 + attempt * 0.8)
    return []


def trigger_initial_import(
    db: Session,
    user_id: int,
    *,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Request Garmin historical backfill after connect.
    Data arrives asynchronously via webhooks — must be configured in Garmin Developer Portal.
    """
    from app.core.garmin_import import (
        activity_backfill_summary,
        build_import_message,
        garmin_user_id_for_internal_user,
        replay_failed_webhooks,
    )

    oauth_service = GarminOAuthService()
    if not access_token:
        access_token = oauth_service.get_valid_access_token(db, user_id)
    if not access_token:
        return {
            "status": "error",
            "message": "Geen geldige Garmin-token. Verbind Garmin opnieuw.",
        }

    perm_names = fetch_permissions_with_retry(
        oauth_service, access_token=access_token, db=db, user_id=user_id
    )
    permissions_assumed = False
    if not perm_names:
        perm_names = sorted(POST_OAUTH_EXPORT_PERMISSIONS)
        permissions_assumed = True
        logger.warning(
            f"No permissions API response for user {user_id}; requesting backfill with default export scopes"
        )

    client = GarminAPIClient(db, user_id)
    replay_result = replay_failed_webhooks(
        db,
        user_id,
        garmin_user_id=garmin_user_id_for_internal_user(db, user_id),
    )
    backfill_result = request_initial_backfill(client, perm_names)
    backfill_summary = activity_backfill_summary(backfill_result)
    import_status = build_import_status_payload(db, user_id, 30)
    activity_sessions = import_status.get("summary", {}).get("activity_sessions", 0) or 0

    caps = build_garmin_capabilities(perm_names)
    base_url = settings.webapp_url.rstrip("/")
    message = build_import_message(
        activity_sessions=activity_sessions,
        backfill_summary=backfill_summary,
        webhook_replay=replay_result,
        migration=None,
        permissions_assumed=permissions_assumed,
        capabilities=caps,
    )

    return {
        "status": "requested",
        "message": message,
        "permissions": perm_names,
        "permissions_assumed": permissions_assumed,
        "capabilities": caps,
        "backfill": backfill_result,
        "backfill_summary": backfill_summary,
        "webhook_replay": replay_result,
        "import_status": import_status.get("summary"),
        "stored_records": import_status.get("stored_records"),
        "webhook_urls": {
            "health": f"{base_url}/garmin/webhook/health",
            "activity": f"{base_url}/garmin/webhook/activity",
        },
        "webhook_setup_hint": (
            "Zet in Garmin Developer → Endpoints de webhook-URL's hierboven. "
            "Zonder webhooks blijft de database leeg na backfill."
        ),
    }


def request_initial_backfill(
    client: GarminAPIClient,
    permissions_response,
) -> Dict[str, Dict[str, list[Dict]]]:
    """Request a conservative first import after OAuth without exhausting eval quotas."""
    permissions = extract_permission_names(permissions_response)
    result: Dict[str, Dict[str, list[Dict]]] = {
        "activity": {},
        "health": {},
        "skipped": {},
    }

    now = datetime.utcnow()

    if REQUIRED_EXPORT_PERMISSIONS.issubset(permissions):
        activity_start = now - timedelta(days=INITIAL_ACTIVITY_BACKFILL_DAYS)
        for activity_type in CORE_ACTIVITY_BACKFILL_TYPES:
            result["activity"][activity_type] = request_activity_backfill_range(
                client, activity_start, now, activity_type
            )
    else:
        result["skipped"]["activity"] = [
            {
                "status": "skipped",
                "notes": [
                    "Missing ACTIVITY_EXPORT or HISTORICAL_DATA_EXPORT permission after OAuth."
                ],
            }
        ]

    if "HEALTH_EXPORT" in permissions:
        health_start = now - timedelta(days=INITIAL_HEALTH_BACKFILL_DAYS)
        for health_type in CORE_HEALTH_BACKFILL_TYPES:
            result["health"][health_type] = request_health_backfill_range(
                client, health_type, health_start, now
            )
    else:
        result["skipped"]["health"] = [
            {
                "status": "skipped",
                "notes": ["Missing HEALTH_EXPORT permission after OAuth."],
            }
        ]

    return result


def build_garmin_capabilities(permissions_response) -> Dict:
    """Expose the Garmin permissions as actionable app capabilities."""
    permissions = extract_permission_names(permissions_response)
    missing_initial = sorted(
        permission for permission in REQUIRED_EXPORT_PERMISSIONS if permission not in permissions
    )
    capabilities = {
        "activity_export": "ACTIVITY_EXPORT" in permissions,
        "historical_data_export": "HISTORICAL_DATA_EXPORT" in permissions,
        "health_export": "HEALTH_EXPORT" in permissions,
        "workout_import": "WORKOUT_IMPORT" in permissions,
        "course_import": "COURSE_IMPORT" in permissions,
    }
    return {
        "permissions": sorted(permissions),
        "capabilities": capabilities,
        "missing_required_for_initial_import": missing_initial,
        "ready_for_initial_import": not missing_initial,
    }


def build_import_status_payload(db: Session, user_id: int, period_days: int) -> Dict:
    """Return stored Garmin import counts and onboarding-friendly readiness signals."""
    start_date = datetime.utcnow() - timedelta(days=period_days)

    activity_counts = dict(
        db.query(GarminActivityData.summary_type, func.count(GarminActivityData.id))
        .filter(
            GarminActivityData.user_id == user_id,
            GarminActivityData.start_time >= start_date,
        )
        .group_by(GarminActivityData.summary_type)
        .all()
    )
    auxiliary_counts = dict(
        db.query(GarminActivityAuxiliaryData.summary_type, func.count(GarminActivityAuxiliaryData.id))
        .filter(
            GarminActivityAuxiliaryData.user_id == user_id,
            GarminActivityAuxiliaryData.start_time >= start_date,
        )
        .group_by(GarminActivityAuxiliaryData.summary_type)
        .all()
    )
    health_counts = dict(
        db.query(GarminHealthData.summary_type, func.count(GarminHealthData.id))
        .filter(
            GarminHealthData.user_id == user_id,
            GarminHealthData.start_time >= start_date,
        )
        .group_by(GarminHealthData.summary_type)
        .all()
    )
    webhook_counts = dict(
        db.query(GarminWebhookEvent.source, func.count(GarminWebhookEvent.id))
        .filter(
            GarminWebhookEvent.user_id == user_id,
            GarminWebhookEvent.created_at >= start_date,
        )
        .group_by(GarminWebhookEvent.source)
        .all()
    )
    webhook_status_counts = {
        f"{source}:{status}": count
        for source, status, count in (
            db.query(
                GarminWebhookEvent.source,
                GarminWebhookEvent.status,
                func.count(GarminWebhookEvent.id),
            )
            .filter(
                GarminWebhookEvent.user_id == user_id,
                GarminWebhookEvent.created_at >= start_date,
            )
            .group_by(GarminWebhookEvent.source, GarminWebhookEvent.status)
            .all()
        )
    }
    recent_webhooks = [
        {
            "id": event.id,
            "source": event.source,
            "summary_types": json.loads(event.summary_types or "[]"),
            "item_count": event.item_count,
            "callback_count": event.callback_count,
            "status": event.status,
            "error": event.error,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in (
            db.query(GarminWebhookEvent)
            .filter(
                or_(
                    GarminWebhookEvent.user_id == user_id,
                    GarminWebhookEvent.user_id.is_(None),
                ),
                GarminWebhookEvent.created_at >= start_date,
            )
            .order_by(GarminWebhookEvent.created_at.desc())
            .limit(20)
            .all()
        )
    ]

    activity_total = sum(activity_counts.values())
    auxiliary_total = sum(auxiliary_counts.values())
    health_total = sum(health_counts.values())
    webhook_total = sum(webhook_counts.values())
    has_activity_webhook = webhook_counts.get("activity", 0) > 0
    has_health_webhook = webhook_counts.get("health", 0) > 0

    return {
        "period_days": period_days,
        "activity": activity_counts,
        "activity_auxiliary": auxiliary_counts,
        "health": health_counts,
        "summary": {
            "activity_records": activity_total,
            "activity_sessions": activity_counts.get("activities", 0)
            + activity_counts.get("manuallyUpdatedActivities", 0),
            "activity_auxiliary_records": auxiliary_total,
            "activity_files": auxiliary_counts.get("activityFiles", 0),
            "health_records": health_total,
            "health_types": sorted(health_counts.keys()),
            "webhook_events": webhook_total,
            "has_activity_webhook": has_activity_webhook,
            "has_health_webhook": has_health_webhook,
            "activity_import_ready": activity_total > 0 and has_activity_webhook,
            "health_import_ready": health_total > 0 and has_health_webhook,
            "onboarding_ready": activity_total > 0 and health_total > 0,
        },
        "webhooks": {
            "counts": webhook_counts,
            "status_counts": webhook_status_counts,
            "recent": recent_webhooks,
        },
    }


def _create_webhook_event(db: Session, source: str, payload: Dict) -> GarminWebhookEvent:
    """Persist the raw Garmin webhook payload before processing it."""
    summary_types = list(payload.keys())
    items = [
        item
        for value in payload.values()
        if isinstance(value, list)
        for item in value
        if isinstance(item, dict)
    ]
    garmin_user_id = next((item.get("userId") for item in items if item.get("userId")), None)
    from app.core.garmin_import import resolve_internal_user_for_garmin

    resolved_user_id = resolve_internal_user_for_garmin(db, garmin_user_id)

    event = GarminWebhookEvent(
        user_id=resolved_user_id,
        garmin_user_id=garmin_user_id,
        source=source,
        summary_types=json.dumps(summary_types),
        item_count=len(items),
        callback_count=sum(1 for item in items if item.get("callbackURL")),
        status="received",
        payload=json.dumps(payload),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _finish_webhook_event(db: Session, event: GarminWebhookEvent, errors: list[str]) -> None:
    """Mark a Garmin webhook audit event as processed, partial, or failed."""
    event.status = "processed" if not errors else "partial"
    event.error = "\n".join(errors) if errors else None
    event.updated_at = datetime.utcnow()
    db.commit()


def summarize_activities(activities: list[GarminActivityData]) -> Dict:
    """Create aggregate metrics from Garmin activity rows."""
    total_distance_m = sum((activity.distance or 0.0) for activity in activities)
    total_duration_s = sum((activity.duration or 0) for activity in activities)
    hr_values = [activity.average_heart_rate for activity in activities if activity.average_heart_rate]
    max_hr_values = [activity.max_heart_rate for activity in activities if activity.max_heart_rate]
    longest_session_seconds = max((activity.duration or 0) for activity in activities) if activities else 0

    running_count = 0
    cycling_count = 0
    running_hr_values = []
    cycling_hr_values = []
    for activity in activities:
        activity_type = (activity.activity_type or "").upper()
        if "RUN" in activity_type:
            running_count += 1
            if activity.average_heart_rate:
                running_hr_values.append(activity.average_heart_rate)
        if "CYCLE" in activity_type or "BIKE" in activity_type:
            cycling_count += 1
            if activity.average_heart_rate:
                cycling_hr_values.append(activity.average_heart_rate)

    return {
        "sessions": len(activities),
        "distance_meters": round(total_distance_m, 2),
        "distance_km": round(total_distance_m / 1000, 2),
        "duration_seconds": int(total_duration_s),
        "duration_hours": round(total_duration_s / 3600, 2),
        "longest_session_minutes": round(longest_session_seconds / 60, 1) if longest_session_seconds else 0.0,
        "average_heart_rate": round(sum(hr_values) / len(hr_values), 1) if hr_values else None,
        "max_heart_rate": max(max_hr_values) if max_hr_values else None,
        "running_sessions": running_count,
        "cycling_sessions": cycling_count,
        "running_average_heart_rate": round(sum(running_hr_values) / len(running_hr_values), 1) if running_hr_values else None,
        "cycling_average_heart_rate": round(sum(cycling_hr_values) / len(cycling_hr_values), 1) if cycling_hr_values else None,
    }


def _activity_raw(activity: GarminActivityData) -> Dict:
    """Parse the stored Garmin raw payload defensively."""
    try:
        return json.loads(activity.data) if isinstance(activity.data, str) else (activity.data or {})
    except Exception:
        return {}


def _auxiliary_raw(record: GarminActivityAuxiliaryData) -> Dict:
    """Parse an auxiliary Garmin payload such as activityDetails."""
    try:
        return json.loads(record.data) if isinstance(record.data, str) else (record.data or {})
    except Exception:
        return {}


def normalize_training_sport(activity: GarminActivityData) -> str:
    """Map Garmin activity types to the sport buckets used by the coach UI."""
    activity_type = (activity.activity_type or "").upper()
    name = (activity.activity_name or "").lower()
    raw = _activity_raw(activity)
    raw_type = str(raw.get("activityType") or "").upper()
    device_name = str(raw.get("deviceName") or "").lower()
    combined = " ".join([activity_type, raw_type, name, device_name])

    if "SWIM" in combined:
        return "SWIMMING"
    if "INDOOR" in combined or "ZWIFT" in combined or "VIRTUAL" in combined:
        if "CYCLE" in combined or "BIKE" in combined or "CYCLING" in combined:
            return "INDOOR_CYCLING"
    if "CYCLE" in combined or "BIKE" in combined or "CYCLING" in combined:
        return "CYCLING"
    if "WALK" in combined or "WANDEL" in combined:
        return "WALKING"
    if "RUN" in combined:
        return "RUNNING"
    if activity_type == "CARDIO_TRAINING":
        return "WALKING"
    return activity_type or "UNKNOWN"


def _normalize_detail_sport(detail: Dict, fallback: str) -> str:
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else detail
    activity_type = str(summary.get("activityType") or detail.get("activityType") or fallback).upper()
    name = str(summary.get("activityName") or detail.get("activityName") or "").lower()
    combined = f"{activity_type} {name}"
    if "SWIM" in combined:
        return "SWIMMING"
    if ("INDOOR" in combined or "ZWIFT" in combined or "VIRTUAL" in combined) and (
        "CYCLE" in combined or "BIKE" in combined or "CYCLING" in combined
    ):
        return "INDOOR_CYCLING"
    if "CYCLE" in combined or "BIKE" in combined or "CYCLING" in combined:
        return "CYCLING"
    if "WALK" in combined or "WANDEL" in combined:
        return "WALKING"
    if "RUN" in combined:
        return "RUNNING"
    return fallback


def _activity_metric(activity: GarminActivityData, sport: str) -> Optional[float]:
    """Return the primary sport metric: pace seconds/unit or speed km/h."""
    distance = activity.distance or 0
    duration = activity.duration or 0
    if distance <= 0 or duration <= 0:
        return None

    if sport in {"CYCLING", "INDOOR_CYCLING"}:
        return (distance / duration) * 3.6
    if sport == "SWIMMING":
        return duration / (distance / 100)
    return duration / (distance / 1000)


def _segment_metric(segment: Dict, sport: str) -> Optional[float]:
    duration = segment.get("duration_seconds") or 0
    distance = segment.get("distance_meters") or 0
    speed = segment.get("speed_mps")
    if sport in {"CYCLING", "INDOOR_CYCLING"}:
        if speed:
            return speed * 3.6
        return (distance / duration) * 3.6 if distance > 0 and duration > 0 else None
    if sport == "SWIMMING":
        return duration / (distance / 100) if distance > 0 and duration > 0 else None
    return duration / (distance / 1000) if distance > 0 and duration > 0 else None


def _percentile(values: list[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _median(values: list[float]) -> Optional[float]:
    return _percentile(values, 0.5)


def _range_around(values: list[float], fallback_values: list[float], higher_is_harder: bool) -> Optional[tuple[float, float]]:
    source = values or fallback_values
    if not source:
        return None
    if len(source) >= 4:
        low = _percentile(source, 0.25)
        high = _percentile(source, 0.75)
    else:
        center = _median(source)
        spread = max(center * 0.06, 2.0) if center else 0
        low = center - spread
        high = center + spread
    if low is None or high is None:
        return None
    if higher_is_harder:
        return (round(max(0, low), 1), round(max(0, high), 1))
    return (round(max(1, low)), round(max(1, high)))


def _format_pace(seconds: float, suffix: str) -> str:
    total = max(1, int(round(seconds)))
    minutes = total // 60
    secs = total % 60
    return f"{minutes}:{secs:02d}{suffix}"


def _format_metric_range(metric_range: Optional[tuple[float, float]], sport: str) -> Optional[str]:
    if not metric_range:
        return None
    low, high = metric_range
    if sport in {"CYCLING", "INDOOR_CYCLING"}:
        return f"{round(low)}-{round(high)} km/u"
    suffix = "/100m" if sport == "SWIMMING" else "/km"
    return f"{_format_pace(low, suffix)}-{_format_pace(high, suffix)}"


def _format_hr_range(hr_range: Optional[tuple[float, float]]) -> Optional[str]:
    if not hr_range:
        return None
    low, high = hr_range
    return f"{round(low)}-{round(high)}"


def _metric_plausible_for_training_target(metric: Optional[float], sport: str, effort: str) -> bool:
    """Keep route pauses/walking from becoming pace targets for structured workouts."""
    if metric is None or metric <= 0:
        return False
    if sport == "RUNNING":
        # seconds per km. Slower than this is usually walking, stops, trail hiking,
        # or run/walk data: useful context, but not a running pace prescription.
        max_by_effort = {
            "easy": 9 * 60,
            "endurance": 8 * 60 + 45,
            "threshold": 7 * 60 + 30,
            "vo2": 6 * 60 + 45,
        }
        min_by_effort = {
            "easy": 4 * 60 + 30,
            "endurance": 4 * 60,
            "threshold": 3 * 60 + 20,
            "vo2": 3 * 60,
        }
        return min_by_effort.get(effort, 3 * 60) <= metric <= max_by_effort.get(effort, 9 * 60)
    if sport == "WALKING":
        return 7 * 60 <= metric <= 16 * 60
    if sport == "SWIMMING":
        return 55 <= metric <= 5 * 60
    if sport in {"CYCLING", "INDOOR_CYCLING"}:
        return 8 <= metric <= 65
    return True


def _build_activity_detail_index(details: list[GarminActivityAuxiliaryData]) -> Dict[str, Dict]:
    """Index activityDetails by all known Garmin identifiers."""
    index: Dict[str, Dict] = {}
    for record in details:
        payload = _auxiliary_raw(record)
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
        keys = [
            record.activity_id,
            record.summary_id,
            payload.get("activityId"),
            payload.get("summaryId"),
            summary.get("activityId") if isinstance(summary, dict) else None,
            summary.get("summaryId") if isinstance(summary, dict) else None,
        ]
        for key in keys:
            if key is not None:
                index[str(key)] = payload
                if str(key).endswith("-detail"):
                    index[str(key).replace("-detail", "")] = payload
    return index


def _activity_detail_for(activity: GarminActivityData, detail_index: Dict[str, Dict]) -> Optional[Dict]:
    keys = [
        activity.activity_id,
        activity.summary_id,
        str(activity.summary_id).replace("-detail", "") if activity.summary_id else None,
    ]
    for key in keys:
        if key is not None and str(key) in detail_index:
            return detail_index[str(key)]
    return None


def _sample_elapsed(sample: Dict, first_start: Optional[int]) -> Optional[float]:
    for key in ["timerDurationInSeconds", "movingDurationInSeconds", "clockDurationInSeconds"]:
        value = sample.get(key)
        if value is not None:
            return float(value)
    start = sample.get("startTimeInSeconds")
    if start is not None and first_start is not None:
        return float(start - first_start)
    return None


def _samples_to_segment(samples: list[Dict], sport: str) -> Optional[Dict]:
    clean = [s for s in samples if isinstance(s, dict)]
    if len(clean) < 2:
        return None
    first = clean[0]
    last = clean[-1]
    first_start = first.get("startTimeInSeconds")
    start_elapsed = _sample_elapsed(first, first_start)
    end_elapsed = _sample_elapsed(last, first_start)
    if start_elapsed is None or end_elapsed is None:
        return None
    duration = max(0, end_elapsed - start_elapsed)
    start_distance = first.get("totalDistanceInMeters")
    end_distance = last.get("totalDistanceInMeters")
    distance = max(0, (end_distance or 0) - (start_distance or 0)) if end_distance is not None and start_distance is not None else 0
    hr_values = [s.get("heartRate") for s in clean if s.get("heartRate")]
    speed_values = [s.get("speedMetersPerSecond") for s in clean if s.get("speedMetersPerSecond")]
    avg_speed = sum(speed_values) / len(speed_values) if speed_values else ((distance / duration) if distance and duration else None)

    if duration < 45:
        return None
    if sport != "SWIMMING" and distance <= 20 and not avg_speed:
        return None

    return {
        "duration_seconds": duration,
        "distance_meters": distance,
        "heart_rate": sum(hr_values) / len(hr_values) if hr_values else None,
        "speed_mps": avg_speed,
        "sample_count": len(clean),
    }


def _segments_from_detail(detail: Dict, sport: str) -> list[Dict]:
    """Extract useful effort segments from activityDetails samples and laps."""
    detail_sport = _normalize_detail_sport(detail, sport)
    samples = sorted(
        [s for s in detail.get("samples", []) if isinstance(s, dict) and s.get("startTimeInSeconds")],
        key=lambda s: s.get("startTimeInSeconds"),
    )
    if len(samples) < 2:
        return []

    laps = sorted(
        [lap.get("startTimeInSeconds") for lap in detail.get("laps", []) if isinstance(lap, dict) and lap.get("startTimeInSeconds")],
    )
    segments: list[Dict] = []
    if len(laps) >= 2:
        boundaries = laps + [samples[-1]["startTimeInSeconds"] + 1]
        for start, end in zip(boundaries, boundaries[1:]):
            lap_samples = [sample for sample in samples if start <= sample.get("startTimeInSeconds", 0) < end]
            segment = _samples_to_segment(lap_samples, detail_sport)
            if segment:
                segment["source"] = "lap"
                segments.append(segment)
    else:
        first_start = samples[0].get("startTimeInSeconds")
        bucket_seconds = 300
        buckets: Dict[int, list[Dict]] = {}
        for sample in samples:
            elapsed = sample.get("startTimeInSeconds", first_start) - first_start
            bucket = int(elapsed // bucket_seconds)
            buckets.setdefault(bucket, []).append(sample)
        for bucket_samples in buckets.values():
            segment = _samples_to_segment(bucket_samples, detail_sport)
            if segment:
                segment["source"] = "sample_window"
                segments.append(segment)

    return segments


def _classify_effort(activity: GarminActivityData, sport_max_hr: Optional[int]) -> str:
    name = (activity.activity_name or "").lower()
    if any(word in name for word in ["easy", "herstel", "recovery", "rustig", "walk", "wandel"]):
        return "easy"
    if any(word in name for word in ["duur", "endurance", "zone 2", "z2", "lsd", "long slow"]):
        return "endurance"
    if any(word in name for word in ["tempo", "threshold", "drempel"]):
        return "threshold"
    if any(word in name for word in ["interval", "vo2", "sprint"]):
        return "vo2"

    from app.core.hr_profile import classify_effort_from_hr

    effort = classify_effort_from_hr(activity.average_heart_rate, sport_max_hr, sport_max_hr)
    if effort:
        return effort

    return "endurance"


def _classify_segment_effort(segment: Dict, sport_max_hr: Optional[int], metric: Optional[float], sport: str) -> str:
    from app.core.hr_profile import classify_effort_from_hr

    effort = classify_effort_from_hr(segment.get("heart_rate"), sport_max_hr, sport_max_hr)
    if effort:
        return effort

    duration = segment.get("duration_seconds") or 0
    if duration >= 1200:
        return "endurance"
    if duration <= 240:
        return "vo2"
    return "threshold" if sport in {"RUNNING", "CYCLING", "INDOOR_CYCLING"} else "endurance"


def _target_range_for_effort(
    metric_values: dict[str, list[float]],
    all_metrics: list[float],
    sport: str,
    effort: str,
) -> Optional[tuple[float, float]]:
    higher_is_harder = sport in {"CYCLING", "INDOOR_CYCLING"}
    source = metric_values.get(effort, [])
    fallback_order = {
        "easy": ["easy", "endurance"],
        "endurance": ["endurance", "easy", "threshold"],
        "threshold": ["threshold", "vo2", "endurance"],
        "vo2": ["vo2", "threshold"],
    }[effort]
    fallback = []
    for key in fallback_order:
        fallback.extend(metric_values.get(key, []))

    metric_range = _range_around(source, fallback or all_metrics, higher_is_harder)
    if not metric_range:
        return None

    low, high = metric_range
    if higher_is_harder:
        if effort == "easy":
            return (low * 0.92, high * 0.98)
        if effort == "vo2":
            return (low * 1.02, high * 1.08)
        return (low, high)

    if effort == "easy":
        return (low * 1.04, high * 1.10)
    if effort == "vo2":
        return (low * 0.92, high * 0.98)
    return (low, high)


def build_personal_training_profile(
    activities: list[GarminActivityData],
    details: Optional[list[GarminActivityAuxiliaryData]] = None,
) -> Dict:
    """Build personalized training targets from details/laps with summary fallback."""
    detail_index = _build_activity_detail_index(details or [])
    sports: dict[str, list[GarminActivityData]] = {}
    for activity in activities:
        sport = normalize_training_sport(activity)
        if sport in {"UNKNOWN", ""}:
            continue
        sports.setdefault(sport, []).append(activity)

    profile: Dict[str, Dict] = {}
    for sport, sport_activities in sports.items():
        from app.core.hr_profile import resolve_hr_profile

        sport_max_hr = resolve_hr_profile(sport_activities).effective_max
        metric_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        hr_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        detail_metric_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        detail_hr_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        all_metrics = []
        detail_segment_count = 0
        detail_activity_count = 0

        for activity in sport_activities:
            detail = _activity_detail_for(activity, detail_index)
            segments = _segments_from_detail(detail, sport) if detail else []
            if segments:
                detail_activity_count += 1
                detail_segment_count += len(segments)
                for segment in segments:
                    metric = _segment_metric(segment, sport)
                    effort = _classify_segment_effort(segment, sport_max_hr, metric, sport)
                    if _metric_plausible_for_training_target(metric, sport, effort):
                        detail_metric_values[effort].append(metric)
                        all_metrics.append(metric)
                    if segment.get("heart_rate"):
                        detail_hr_values[effort].append(segment["heart_rate"])
                continue

            effort = _classify_effort(activity, sport_max_hr)
            metric = _activity_metric(activity, sport)
            if _metric_plausible_for_training_target(metric, sport, effort):
                metric_values[effort].append(metric)
                all_metrics.append(metric)
            if activity.average_heart_rate:
                hr_values[effort].append(activity.average_heart_rate)

        zones = {}
        for effort in ["easy", "endurance", "threshold", "vo2"]:
            merged_metric_values = {
                key: detail_metric_values[key] or metric_values[key]
                for key in ["easy", "endurance", "threshold", "vo2"]
            }
            merged_hr_values = {
                key: detail_hr_values[key] or hr_values[key]
                for key in ["easy", "endurance", "threshold", "vo2"]
            }
            metric_range = _target_range_for_effort(merged_metric_values, all_metrics, sport, effort)
            hr_range = _range_around(
                merged_hr_values.get(effort, []),
                [a.average_heart_rate for a in sport_activities if a.average_heart_rate],
                True,
            )
            zone_sample_size = (
                len(detail_metric_values.get(effort, []))
                or len(metric_values.get(effort, []))
                or len(detail_hr_values.get(effort, []))
                or len(hr_values.get(effort, []))
            )
            zones[effort] = {
                "metric": _format_metric_range(metric_range, sport),
                "hr": _format_hr_range(hr_range),
                "sample_size": zone_sample_size,
                "source": "activityDetails" if detail_metric_values.get(effort) or detail_hr_values.get(effort) else "activitySummaries",
            }

        session_count = len(sport_activities)
        confidence = "low"
        if detail_segment_count >= 8 or session_count >= 10:
            confidence = "high"
        elif detail_segment_count >= 3 or session_count >= 4:
            confidence = "medium"

        profile[sport] = {
            "sport": sport,
            "sessions": session_count,
            "confidence": confidence,
            "metric_type": "speed" if sport in {"CYCLING", "INDOOR_CYCLING"} else "pace",
            "metric_unit": "km/u" if sport in {"CYCLING", "INDOOR_CYCLING"} else ("/100m" if sport == "SWIMMING" else "/km"),
            "max_heart_rate_observed": sport_max_hr,
            "detail_activities": detail_activity_count,
            "detail_segments": detail_segment_count,
            "zones": zones,
            "notes": [
                "Gebaseerd op activityDetails samples/laps waar beschikbaar, met summary fallback."
                if detail_segment_count
                else "Gebaseerd op activity summaries; activityDetails ontbreken nog voor deze sport."
            ],
        }

    return profile


def build_sport_baselines(activities: list[GarminActivityData], days: int, now: datetime) -> Dict:
    """Compare current window with the previous four weekly windows per sport."""
    current_start = now - timedelta(days=days)
    baseline_start = current_start - timedelta(days=28)
    result: Dict[str, Dict] = {}

    for sport in sorted({normalize_training_sport(activity) for activity in activities}):
        if sport in {"UNKNOWN", ""}:
            continue
        sport_activities = [activity for activity in activities if normalize_training_sport(activity) == sport]
        current = [activity for activity in sport_activities if activity.start_time and activity.start_time >= current_start]
        baseline = [
            activity
            for activity in sport_activities
            if activity.start_time and baseline_start <= activity.start_time < current_start
        ]
        current_metrics = summarize_activities(current)
        baseline_totals = summarize_activities(baseline)
        baseline_weekly = {
            "sessions": round(baseline_totals["sessions"] / 4, 2),
            "distance_km": round(baseline_totals["distance_km"] / 4, 2),
            "duration_hours": round(baseline_totals["duration_hours"] / 4, 2),
            "average_heart_rate": baseline_totals["average_heart_rate"],
        }
        baseline_duration = baseline_weekly["duration_hours"]
        load_ratio = round(current_metrics["duration_hours"] / baseline_duration, 2) if baseline_duration else None
        result[sport] = {
            "sport": sport,
            "days": days,
            "current": current_metrics,
            "baseline_weekly": baseline_weekly,
            "load_ratio": load_ratio,
            "deltas": {
                "sessions_percent": compute_percent_change(current_metrics["sessions"], baseline_weekly["sessions"]),
                "distance_percent": compute_percent_change(current_metrics["distance_km"], baseline_weekly["distance_km"]),
                "duration_percent": compute_percent_change(current_metrics["duration_hours"], baseline_weekly["duration_hours"]),
                "avg_heart_rate_delta": (
                    round(current_metrics["average_heart_rate"] - baseline_weekly["average_heart_rate"], 1)
                    if current_metrics["average_heart_rate"] is not None and baseline_weekly["average_heart_rate"] is not None
                    else None
                ),
            },
        }

    return result


def _activity_name_hint(activity: GarminActivityData) -> Optional[str]:
    """Infer a workout type from user/device activity naming conventions."""
    name = (activity.activity_name or "").lower()
    duration_min = (activity.duration or 0) / 60
    if any(word in name for word in ["sprint", "anaeroob", "anaerobic"]):
        return "SPRINT"
    if any(word in name for word in ["vo2", "vo2max", "interval", "intervallen", "800m", "400m"]):
        return "VO2MAX"
    if any(word in name for word in ["tempo", "threshold", "drempel", "sweet spot", "sweetspot"]):
        return "THRESHOLD"
    if any(word in name for word in ["lsd", "long", "duur", "endurance", "basis"]):
        return "DUUR"
    if any(word in name for word in ["easy", "herstel", "recovery", "rustig", "walk", "wandel"]):
        return "DUUR" if duration_min >= 45 else "HERSTEL"
    return None


def _workout_type_from_effort(effort: str, duration_min: float) -> str:
    if effort == "vo2":
        return "VO2MAX"
    if effort == "threshold":
        return "THRESHOLD"
    if duration_min >= 45:
        return "DUUR"
    return "HERSTEL"


def _format_interval_duration(seconds: float) -> str:
    if seconds < 90:
        return f"{max(10, int(round(seconds / 5) * 5))}s"
    minutes = seconds / 60
    if minutes < 10:
        return f"{round(minutes, 1):g}min"
    return f"{round(minutes)}min"


def _activity_interval_structure(segments: list[Dict], sport_max_hr: Optional[int], sport: str) -> Optional[Dict]:
    """Return interval-like structure detected from detail/lap segments."""
    if not segments:
        return None
    hard_segments = []
    for segment in segments:
        metric = _segment_metric(segment, sport)
        effort = _classify_segment_effort(segment, sport_max_hr, metric, sport)
        duration = segment.get("duration_seconds") or 0
        if effort in {"threshold", "vo2"}:
            hard_segments.append({**segment, "effort": effort, "duration_seconds": duration})

    if len(hard_segments) < 2:
        return None

    durations = [s["duration_seconds"] for s in hard_segments if s.get("duration_seconds")]
    median_duration = _median(durations) if durations else None
    if not median_duration:
        return None

    count = len(hard_segments)
    if 10 <= median_duration <= 75:
        workout_type = "SPRINT"
    elif 120 <= median_duration <= 360:
        workout_type = "VO2MAX"
    else:
        workout_type = "THRESHOLD"

    return {
        "type": workout_type,
        "label": f"{count}x{_format_interval_duration(median_duration)}",
        "count": count,
        "median_work_seconds": round(median_duration),
    }


def classify_workout_type(
    activity: GarminActivityData,
    segments: list[Dict],
    sport_max_hr: Optional[int],
    sport: str,
) -> Dict:
    """Classify a historical activity into the app's five workout types."""
    duration_min = (activity.duration or 0) / 60
    detail_structure = _activity_interval_structure(segments, sport_max_hr, sport)
    name_hint = _activity_name_hint(activity)

    if detail_structure:
        workout_type = detail_structure["type"]
        source = "activityDetails"
        structure = detail_structure["label"]
    elif name_hint:
        workout_type = name_hint
        source = "activityName"
        structure = "continu"
    else:
        effort = _classify_effort(activity, sport_max_hr)
        workout_type = _workout_type_from_effort(effort, duration_min)
        source = "activitySummary"
        structure = "continu"

    if name_hint in {"SPRINT", "VO2MAX", "THRESHOLD"} and not detail_structure:
        workout_type = name_hint

    return {
        "type": workout_type,
        "source": source,
        "structure": structure,
        "detail_segments": len(segments),
        "duration_min": round(duration_min),
    }


def _most_common(values: list) -> Optional:
    if not values:
        return None
    counts: Dict = {}
    for value in values:
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]


def _top_days(activities: list[GarminActivityData], limit: int = 3) -> list[str]:
    counts: Dict[str, int] = {}
    for activity in activities:
        if activity.start_time:
            day = activity.start_time.strftime("%A")
            counts[day] = counts.get(day, 0) + 1
    return [day for day, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _confidence(session_count: int, detail_segments: int) -> str:
    if session_count >= 8 or detail_segments >= 8:
        return "high"
    if session_count >= 3 or detail_segments >= 3:
        return "medium"
    return "low"


def _common_sequence(classified: list[Dict]) -> list[str]:
    ordered = [item for item in sorted(classified, key=lambda item: item["start_time"] or datetime.min) if item.get("type")]
    if len(ordered) < 3:
        return [item["type"] for item in ordered[-3:]]
    windows: Dict[tuple[str, str, str], int] = {}
    for index in range(len(ordered) - 2):
        sequence = tuple(item["type"] for item in ordered[index:index + 3])
        windows[sequence] = windows.get(sequence, 0) + 1
    return list(sorted(windows.items(), key=lambda item: (-item[1], item[0]))[0][0])


def build_workout_patterns(
    activities: list[GarminActivityData],
    details: Optional[list[GarminActivityAuxiliaryData]] = None,
) -> Dict:
    """Detect recurring workout types, structures, and weekly rhythm."""
    detail_index = _build_activity_detail_index(details or [])
    sport_max_hr: Dict[str, int] = {}
    for activity in activities:
        sport = normalize_training_sport(activity)
        if activity.max_heart_rate:
            sport_max_hr[sport] = max(sport_max_hr.get(sport, 0), activity.max_heart_rate)

    classified = []
    for activity in activities:
        sport = normalize_training_sport(activity)
        if sport in {"", "UNKNOWN"}:
            continue
        detail = _activity_detail_for(activity, detail_index)
        segments = _segments_from_detail(detail, sport) if detail else []
        workout = classify_workout_type(activity, segments, sport_max_hr.get(sport), sport)
        classified.append({
            **workout,
            "sport": sport,
            "activity_id": activity.activity_id,
            "summary_id": activity.summary_id,
            "activity_name": activity.activity_name,
            "start_time": activity.start_time,
        })

    total = len(classified)
    type_counts: Dict[str, int] = {}
    for item in classified:
        type_counts[item["type"]] = type_counts.get(item["type"], 0) + 1

    dominant_types = [
        {"type": workout_type, "count": count, "share": round(count / total, 2) if total else 0}
        for workout_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    by_type: Dict[str, Dict] = {}
    for workout_type in ["HERSTEL", "DUUR", "THRESHOLD", "VO2MAX", "SPRINT"]:
        items = [item for item in classified if item["type"] == workout_type]
        if not items:
            continue
        item_activities = [
            activity for activity in activities
            if any(item["summary_id"] == activity.summary_id for item in items)
        ]
        durations = [item["duration_min"] for item in items if item.get("duration_min")]
        detail_segments = sum(item.get("detail_segments", 0) for item in items)
        by_type[workout_type] = {
            "sessions": len(items),
            "preferred_sport": _most_common([item["sport"] for item in items]),
            "typical_duration_min": round(_median(durations)) if durations else None,
            "typical_structure": _most_common([item["structure"] for item in items]) or "continu",
            "preferred_days": _top_days(item_activities),
            "confidence": _confidence(len(items), detail_segments),
            "detail_segments": detail_segments,
            "sources": {
                "activityDetails": sum(1 for item in items if item["source"] == "activityDetails"),
                "activityName": sum(1 for item in items if item["source"] == "activityName"),
                "activitySummary": sum(1 for item in items if item["source"] == "activitySummary"),
            },
        }

    dates = [item["start_time"] for item in classified if item.get("start_time")]
    span_weeks = 1
    if len(dates) >= 2:
        span_weeks = max((max(dates) - min(dates)).days / 7, 1)
    easy_count = sum(type_counts.get(t, 0) for t in ["HERSTEL", "DUUR"])
    hard_count = sum(type_counts.get(t, 0) for t in ["THRESHOLD", "VO2MAX", "SPRINT"])

    return {
        "dominant_types": dominant_types,
        "by_type": by_type,
        "weekly_pattern": {
            "easy_share": round(easy_count / total, 2) if total else None,
            "hard_sessions_per_week": round(hard_count / span_weeks, 1) if total else 0,
            "common_sequence": _common_sequence(classified),
        },
        "classified_activities": [
            {
                "summary_id": item["summary_id"],
                "activity_name": item["activity_name"],
                "type": item["type"],
                "sport": item["sport"],
                "structure": item["structure"],
                "source": item["source"],
            }
            for item in classified[:20]
        ],
    }


def parse_min_start_time_from_error(error_message: str) -> Optional[datetime]:
    """Extract Garmin minimum backfill start time from API error text."""
    match = MIN_START_TIME_PATTERN.search(error_message)
    if not match:
        return None

    iso_value = match.group(1).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        return None


def is_duplicate_backfill_error(error_message: str) -> bool:
    """Return true when Garmin rejects a request because that window was already requested."""
    return "duplicate" in error_message.lower() and "backfill" in error_message.lower()


def is_rate_limit_error(error_message: str) -> bool:
    """Return true when Garmin rejects a request due to backfill rate limits."""
    lowered = error_message.lower()
    return "rate limit" in lowered or "too many request" in lowered or "quota" in lowered


def backfill_error_status(error_message: str) -> str:
    if is_duplicate_backfill_error(error_message):
        return "duplicate"
    if is_rate_limit_error(error_message):
        return "rate_limited"
    return "error"


def backfill_error_note(error_message: str) -> str:
    if is_duplicate_backfill_error(error_message):
        return "Garmin reported this range was already processed."
    if is_rate_limit_error(error_message):
        return "Garmin rate limit hit. Wait at least 1 minute before requesting more backfill."
    return error_message


def split_backfill_windows(start: datetime, end: datetime, window_days: int) -> list[tuple[datetime, datetime]]:
    """Split a backfill range into Garmin-compliant windows."""
    if start >= end:
        return []

    windows = []
    cursor = start
    max_delta = timedelta(days=window_days)
    while cursor < end:
        window_end = min(cursor + max_delta, end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(seconds=1)
    return windows


def request_activity_backfill_with_fallback(
    client: GarminAPIClient,
    start: datetime,
    end: datetime,
) -> Dict:
    """Request activity backfill and auto-adjust when Garmin rejects old start date."""
    result = {
        "requested_start": start.isoformat(),
        "effective_start": start.isoformat(),
        "end": end.isoformat(),
        "status": "requested",
        "notes": [],
    }

    try:
        client.backfill_activities(start, end)
        return result
    except Exception as exc:
        error_text = str(exc)

        if is_duplicate_backfill_error(error_text):
            result["status"] = "duplicate"
            result["notes"].append("Garmin reported this range was already processed.")
            return result

        min_start = parse_min_start_time_from_error(error_text)
        if not min_start:
            raise

        adjusted_start = max(start, min_start + timedelta(seconds=1))
        if adjusted_start >= end:
            result["status"] = "skipped"
            result["effective_start"] = adjusted_start.isoformat()
            result["notes"].append("Requested window is older than Garmin's allowed minimum start time.")
            return result

        result["status"] = "requested_with_adjusted_start"
        result["effective_start"] = adjusted_start.isoformat()
        result["notes"].append("Adjusted start date to Garmin minimum allowed backfill timestamp.")

        try:
            client.backfill_activities(adjusted_start, end)
            return result
        except Exception as second_exc:
            second_error_text = str(second_exc)
            if is_duplicate_backfill_error(second_error_text):
                result["status"] = "duplicate"
                result["notes"].append("Garmin reported this adjusted range was already processed.")
                return result
            raise


def request_activity_backfill_range(
    client: GarminAPIClient,
    start: datetime,
    end: datetime,
    data_type: str = "activities",
) -> list[Dict]:
    """Request activity backfill in 30-day Garmin-compliant windows."""
    results = []
    for window_start, window_end in split_backfill_windows(start, end, ACTIVITY_BACKFILL_WINDOW_DAYS):
        try:
            if data_type == "activities":
                results.append(
                    request_activity_backfill_with_fallback(
                        client=client,
                        start=window_start,
                        end=window_end,
                    )
                )
            else:
                client.backfill_activity_type(data_type, window_start, window_end)
                results.append(
                    {
                        "requested_start": window_start.isoformat(),
                        "effective_start": window_start.isoformat(),
                        "end": window_end.isoformat(),
                        "status": "requested",
                        "notes": [],
                    }
                )
        except Exception as exc:
            error_text = str(exc)
            results.append(
                {
                    "requested_start": window_start.isoformat(),
                    "effective_start": window_start.isoformat(),
                    "end": window_end.isoformat(),
                    "status": backfill_error_status(error_text),
                    "notes": [backfill_error_note(error_text)],
                }
            )
    return results


def request_health_backfill_range(
    client: GarminAPIClient,
    data_type: str,
    start: datetime,
    end: datetime,
) -> list[Dict]:
    """Request health backfill in 90-day Garmin-compliant windows."""
    results = []
    for window_start, window_end in split_backfill_windows(start, end, HEALTH_BACKFILL_WINDOW_DAYS):
        result = {
            "type": data_type,
            "requested_start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "status": "requested",
            "notes": [],
        }
        try:
            if data_type == "dailies":
                client.backfill_dailies(window_start, window_end)
            else:
                client.backfill_health_type(data_type, window_start, window_end)
        except Exception as exc:
            error_text = str(exc)
            result["status"] = backfill_error_status(error_text)
            result["notes"].append(backfill_error_note(error_text))
        results.append(result)
    return results


def build_weekly_activity_trend(activities: list[GarminActivityData]) -> list[Dict]:
    """Build weekly aggregated trend data for a list of activities."""
    weekly: Dict[str, Dict] = {}

    for activity in activities:
        if not activity.start_time:
            continue

        week_start_date = (activity.start_time - timedelta(days=activity.start_time.weekday())).date()
        week_key = week_start_date.isoformat()
        if week_key not in weekly:
            weekly[week_key] = {
                "week_start": week_key,
                "sessions": 0,
                "distance_meters": 0.0,
                "duration_seconds": 0,
                "heart_rates": [],
            }

        weekly[week_key]["sessions"] += 1
        weekly[week_key]["distance_meters"] += activity.distance or 0.0
        weekly[week_key]["duration_seconds"] += activity.duration or 0
        if activity.average_heart_rate:
            weekly[week_key]["heart_rates"].append(activity.average_heart_rate)

    trend = []
    for week_key in sorted(weekly.keys()):
        item = weekly[week_key]
        heart_rates = item["heart_rates"]
        trend.append(
            {
                "week_start": week_key,
                "sessions": item["sessions"],
                "distance_km": round(item["distance_meters"] / 1000, 2),
                "duration_hours": round(item["duration_seconds"] / 3600, 2),
                "average_heart_rate": round(sum(heart_rates) / len(heart_rates), 1) if heart_rates else None,
            }
        )

    return trend


def compute_percent_change(current: float, baseline: float) -> Optional[float]:
    """Compute percentage change between current and baseline values."""
    if baseline == 0:
        return None
    return round(((current - baseline) / baseline) * 100, 1)


def _load_health_payload(record: Optional[GarminHealthData]) -> Dict:
    if not record:
        return {}
    if isinstance(record.data, str):
        try:
            return json.loads(record.data)
        except json.JSONDecodeError:
            return {}
    return record.data or {}


def _latest_health_record(
    db: Session,
    user_id: int,
    summary_type: str,
    since: datetime,
) -> Optional[GarminHealthData]:
    return db.query(GarminHealthData).filter(
        GarminHealthData.user_id == user_id,
        GarminHealthData.summary_type == summary_type,
        GarminHealthData.start_time >= since,
    ).order_by(GarminHealthData.start_time.desc()).first()


def _sleep_score(sleep: Dict) -> Optional[int]:
    score = (
        sleep.get("overallSleepScore", {}).get("value")
        or sleep.get("sleepScores", {}).get("overall", {}).get("value")
    )
    return int(score) if isinstance(score, (int, float)) else None


def _minutes(value_seconds: Optional[int]) -> int:
    return int((value_seconds or 0) / 60)


def _valid_numeric_values(values: Dict) -> list[float]:
    return [
        float(value)
        for value in values.values()
        if isinstance(value, (int, float)) and value >= 0
    ]


def _valid_numeric_series(values: Dict) -> list[float]:
    """Return numeric time-offset values sorted by their offset when possible."""
    return [value for _, value in _valid_numeric_offset_series(values)]


def _valid_numeric_offset_series(values: Dict) -> list[tuple[int, float]]:
    """Return numeric time-offset/value pairs sorted by offset."""
    rows = []
    for offset, value in values.items():
        if not isinstance(value, (int, float)) or value < 0:
            continue
        try:
            sort_key = int(offset)
        except (TypeError, ValueError):
            sort_key = len(rows)
        rows.append((sort_key, float(value)))
    rows.sort(key=lambda row: row[0])
    return rows


def _sleep_wake_timestamp(sleep: Dict, stress: Dict) -> Optional[int]:
    """Infer wake time as Unix UTC seconds from sleep summary or stress Body Battery events."""
    sleep_start = sleep.get("startTimeInSeconds")
    sleep_duration = sleep.get("durationInSeconds")
    if isinstance(sleep_start, (int, float)) and isinstance(sleep_duration, (int, float)):
        return int(sleep_start + sleep_duration)

    events = stress.get("bodyBatteryActivityEvents") or []
    sleep_event_ends = []
    for event in events:
        if not isinstance(event, dict) or (event.get("eventType") or "").upper() != "SLEEP":
            continue
        event_start = event.get("eventStartTimeInSeconds")
        event_duration = event.get("duration")
        if isinstance(event_start, (int, float)) and isinstance(event_duration, (int, float)):
            sleep_event_ends.append(int(event_start + event_duration))
    return max(sleep_event_ends) if sleep_event_ends else None


def _body_battery_at_wake(stress: Dict, sleep: Dict) -> Optional[int]:
    """Pick the Body Battery sample closest to wake time instead of the first daily sample."""
    stress_start = stress.get("startTimeInSeconds")
    if not isinstance(stress_start, (int, float)):
        return None

    wake_timestamp = _sleep_wake_timestamp(sleep, stress)
    if wake_timestamp is None:
        return None

    samples = _valid_numeric_offset_series(stress.get("timeOffsetBodyBatteryValues", {}))
    if not samples:
        return None

    absolute_samples = [(int(stress_start + offset), value) for offset, value in samples]
    after_wake = [
        (timestamp, value)
        for timestamp, value in absolute_samples
        if timestamp >= wake_timestamp and timestamp - wake_timestamp <= 3 * 3600
    ]
    if after_wake:
        return round(after_wake[0][1])

    closest_timestamp, closest_value = min(
        absolute_samples,
        key=lambda row: abs(row[0] - wake_timestamp),
    )
    if abs(closest_timestamp - wake_timestamp) <= 3 * 3600:
        return round(closest_value)
    return None


def _valid_stress_values(values: Dict) -> list[int]:
    return [
        int(value)
        for value in values.values()
        if isinstance(value, int) and value > 0
    ]


def _recent_training_fatigue(activities: list[GarminActivityData]) -> Dict:
    """Delegate to canonical fatigue model (% max HR)."""
    from app.core.readiness import compute_recent_fatigue

    return compute_recent_fatigue(activities)


def _recovery_score(
    sleep_score: Optional[int],
    sleep_hours: Optional[float],
    avg_stress: Optional[int],
    body_battery: Optional[int],
    hrv: Optional[int],
    recent_training_penalty: float = 0.0,
    *,
    hrv_history: Optional[list] = None,
) -> int:
    """Delegate to canonical readiness module."""
    from app.config import settings
    from app.core.readiness import compute_readiness_score

    result = compute_readiness_score(
        sleep_score=sleep_score,
        sleep_hours=sleep_hours,
        avg_stress=avg_stress,
        body_battery=body_battery,
        hrv=hrv,
        hrv_history=hrv_history,
        recent_training_penalty=recent_training_penalty,
        version=settings.readiness_version,
    )
    return result.score if result.score is not None else 0


def build_weekly_summary(
    current_week: Dict,
    baseline_weekly: Dict,
    load_ratio: Optional[float],
    hr_delta: Optional[float],
) -> str:
    """Generate a concise Dutch weekly coaching summary."""
    volume_delta = compute_percent_change(current_week["duration_hours"], baseline_weekly["duration_hours"])
    distance_delta = compute_percent_change(current_week["distance_km"], baseline_weekly["distance_km"])

    summary_parts = [
        (
            f"Deze week: {current_week['sessions']} sessies "
            f"({current_week['running_sessions']} run, {current_week['cycling_sessions']} fiets), "
            f"{current_week['duration_hours']}u en {current_week['distance_km']} km."
        )
    ]

    if volume_delta is not None:
        summary_parts.append(f"Volume vs 4-weeks gemiddeld: {volume_delta:+.1f}%.")
    if distance_delta is not None:
        summary_parts.append(f"Afstand vs 4-weeks gemiddeld: {distance_delta:+.1f}%.")
    if hr_delta is not None:
        summary_parts.append(f"Gemiddelde hartslag trend: {hr_delta:+.1f} bpm.")

    if load_ratio is None:
        advice = "Nog beperkte historiek: focus op consistente rustige sessies."
    elif load_ratio > 1.25:
        advice = "Belasting stijgt sterk; plan extra herstel en beperk intensiteit."
    elif load_ratio < 0.75:
        advice = "Belasting ligt laag; voeg eventueel 1 rustige sessie toe."
    else:
        advice = "Belasting is goed in balans; huidige structuur aanhouden."
    summary_parts.append(f"Advies: {advice}")

    return " ".join(summary_parts)


@router.get("/auth/start")
async def start_oauth(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    Start OAuth2 PKCE flow for Garmin authentication.

    Returns the authorization URL that the user should visit.
    """
    logger.info("[OAuth Start] V3 code is running.")
    try:
        oauth_service = GarminOAuthService()

        # Use the configured redirect URI
        redirect_uri = settings.garmin_redirect_uri
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="GARMIN_REDIRECT_URI not configured")

        thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
        deleted_count = db.query(OAuthSession).filter(OAuthSession.created_at < thirty_minutes_ago).delete()
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old OAuth sessions.")
        db.commit()

        # Generate authorization URL
        auth_url, code_verifier, state = oauth_service.get_authorization_url(redirect_uri)

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        logger.info(f"[OAuth Start] Generated state: {state} for user: {resolved_user_id}")

        # Store session data in the database
        new_session = OAuthSession(
            state=state,
            code_verifier=code_verifier,
            user_id=resolved_user_id
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"[OAuth Start] Successfully saved session to DB for state: {state}")

        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "Visit the authorization_url to grant access"
        }

    except Exception as e:
        logger.error(f"OAuth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    db: Session = Depends(get_db)
):
    """
    OAuth2 callback endpoint. Garmin redirects here after user authorization.

    Exchanges authorization code for access token and stores it.
    """
    callback_time = datetime.utcnow()
    logger.info(f"[OAuth Callback] Received at {callback_time.isoformat()} with state: {state}")
    try:
        # Add a small delay to mitigate race conditions
        time.sleep(3)

        # Retrieve session data from database
        logger.info("[OAuth Callback] Querying database for state...")
        session = db.query(OAuthSession).filter(OAuthSession.state == state).first()

        if session:
            logger.info(f"[OAuth Callback] Found session in DB created at {session.created_at.isoformat()} for state: {state}")
        else:
            logger.error(f"[OAuth Callback] Session NOT FOUND in DB for state: {state}")
            all_sessions = db.query(OAuthSession).all()
            logger.error(f"Current sessions in DB: {[s.state for s in all_sessions]}")


        if not session:
            from fastapi.responses import HTMLResponse
            retry_url = settings.webapp_url.rstrip("/")
            return HTMLResponse(
                content=f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px">
                <h1>Koppeling verlopen</h1>
                <p>De Garmin-sessie is niet meer geldig (verlopen tab of opnieuw gestart).</p>
                <p><a href="{retry_url}">Terug naar Floating Coach</a> en klik opnieuw op <b>Verbind Garmin</b>.</p>
                </body></html>""",
                status_code=400,
            )

        code_verifier = session.code_verifier
        user_id = session.user_id

        # Get redirect_uri from settings
        redirect_uri = settings.garmin_redirect_uri
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="GARMIN_REDIRECT_URI not configured")

        # Exchange code for token
        oauth_service = GarminOAuthService()
        token_data = oauth_service.exchange_code_for_token(
            authorization_code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri
        )

        oauth_service.store_tokens(db, user_id, token_data)
        db.delete(session)
        db.commit()

        access_token = token_data["access_token"]
        try:
            backfill_result = trigger_initial_import(db, user_id, access_token=access_token)
            logger.info(f"Initial Garmin import after OAuth for user {user_id}: {backfill_result.get('status')}")
        except Exception as backfill_exc:
            logger.warning(f"Initial Garmin import after OAuth failed: {backfill_exc}")

        # Redirect the user back to the web app after successful OAuth.
        from fastapi.responses import HTMLResponse
        base_webapp_url = settings.webapp_url.rstrip("/")
        redirect_url = f"{base_webapp_url}/?garmin_connected=1&user_id={user_id}"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Garmin verbonden</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="2;url={redirect_url}">
</head>
<body style="font-family: Arial, sans-serif; padding: 24px;">
  <h1>Succesvol verbonden!</h1>
  <p>Je Garmin account is gekoppeld. Je wordt automatisch teruggestuurd naar de app.</p>
  <p><a href="{redirect_url}">Klik hier als je niet automatisch wordt doorgestuurd</a></p>
  <script>
    try {{
      localStorage.setItem("sportsHubUserId", "{user_id}");
    }} catch (err) {{}}
    setTimeout(function () {{
      window.location.href = "{redirect_url}";
    }}, 1200);
  </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/status")
async def check_auth_status(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check if user has valid Garmin authentication."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        oauth_service = GarminOAuthService()

        try:
            access_token = oauth_service.get_valid_access_token(db, resolved_user_id)
        except Exception as decrypt_err:
            logger.warning(f"Token decryption failed for user {resolved_user_id}, tokens may need re-auth: {decrypt_err}")
            return {
                "authenticated": False,
                "message": "Token expired or corrupted. Please reconnect Garmin."
            }

        if not access_token:
            return {
                "authenticated": False,
                "message": "No Garmin connection found"
            }

        permissions = []
        permissions_pending = False
        try:
            permissions = oauth_service.get_user_permissions(access_token)
        except Exception as perm_exc:
            perm_text = str(perm_exc)
            if "partner_registration_not_found" in perm_text or "no user partner found" in perm_text.lower():
                permissions_pending = True
                logger.warning(f"Garmin permissions pending for user {resolved_user_id}: {perm_exc}")
            else:
                raise

        garmin_access = build_garmin_capabilities(permissions)

        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == resolved_user_id
        ).first()
        import_status = build_import_status_payload(db, resolved_user_id, 30)

        return {
            "authenticated": True,
            "garmin_user_id": garmin_token.garmin_user_id,
            "permissions_pending": permissions_pending,
            "permissions": garmin_access["permissions"],
            "permission_response": permissions,
            "capabilities": garmin_access["capabilities"],
            "missing_required_for_initial_import": garmin_access["missing_required_for_initial_import"],
            "ready_for_initial_import": garmin_access["ready_for_initial_import"],
            "initial_import_policy": {
                "activity_days": INITIAL_ACTIVITY_BACKFILL_DAYS,
                "health_days": INITIAL_HEALTH_BACKFILL_DAYS,
                "activity_types": CORE_ACTIVITY_BACKFILL_TYPES,
                "health_types": CORE_HEALTH_BACKFILL_TYPES,
            },
            "import_status": {
                "period_days": import_status["period_days"],
                "summary": import_status["summary"],
            },
            "onboarding": {
                "connected": True,
                "ready": import_status["summary"]["onboarding_ready"],
                "activity_import_ready": import_status["summary"]["activity_import_ready"],
                "health_import_ready": import_status["summary"]["health_import_ready"],
                "message": (
                    "Garmin is gekoppeld en de eerste activity/health data is binnen."
                    if import_status["summary"]["onboarding_ready"]
                    else "Garmin is gekoppeld. Eerste import loopt via webhooks na sync/backfill."
                ),
            },
            "expires_at": garmin_token.expires_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auth/disconnect")
async def disconnect_garmin(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Disconnect Garmin account and delete stored tokens."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        oauth_service = GarminOAuthService()

        # Get current access token
        access_token = oauth_service.get_valid_access_token(db, resolved_user_id)

        if access_token:
            try:
                oauth_service.deregister_user(access_token)
            except Exception as e:
                logger.warning(f"Garmin deregistration failed (local unlink continues): {e}")

        oauth_service.delete_tokens(db, resolved_user_id)

        return {
            "status": "success",
            "message": "Successfully disconnected from Garmin",
            "garmin_connected": False,
        }

    except Exception as e:
        logger.error(f"Disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DATA FETCHING ENDPOINTS
# ============================================================================

@router.get("/data/recent")
async def get_recent_data(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(7, description="Number of days to fetch", ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Fetch recent health and activity data for a user.

    This manually fetches data from Garmin API instead of waiting for webhooks.
    """
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)
        data = client.get_recent_data(days=days)

        return {
            "status": "success",
            "data": data,
            "message": f"Fetched data for the last {days} days"
        }

    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities")
async def list_activities(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum activities to return"),
    period_days: int = Query(30, ge=7, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """List recent Garmin activities stored for a user."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        start_date = datetime.utcnow() - timedelta(days=period_days)
        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
            GarminActivityData.start_time >= start_date
        ).order_by(GarminActivityData.start_time.desc()).limit(limit).all()

        summary = summarize_activities(activities)
        type_distribution: Dict[str, int] = {}
        for activity in activities:
            activity_type = (activity.activity_type or "UNKNOWN").upper()
            type_distribution[activity_type] = type_distribution.get(activity_type, 0) + 1

        weekly_trend = build_weekly_activity_trend(activities)

        return {
            "activities": [
                {
                    "id": activity.id,
                    "summary_id": activity.summary_id,
                    "summary_type": activity.summary_type,
                    "activity_id": activity.activity_id,
                    "activity_type": activity.activity_type,
                    "activity_name": activity.activity_name,
                    "start_time": activity.start_time.isoformat() if activity.start_time else None,
                    "duration_seconds": activity.duration,
                    "distance_meters": activity.distance,
                    "average_heart_rate": activity.average_heart_rate,
                    "max_heart_rate": activity.max_heart_rate,
                    "calories": activity.calories,
                    "manual": activity.manual,
                    "raw_data": json.loads(activity.data) if isinstance(activity.data, str) else activity.data,
                }
                for activity in activities
            ],
            "count": len(activities),
            "period_days": period_days,
            "summary": summary,
            "type_distribution": type_distribution,
            "weekly_trend": weekly_trend,
        }
    except Exception as e:
        logger.error(f"List activities failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/import-status")
async def garmin_import_status(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    period_days: int = Query(30, ge=1, le=365, description="Number of days to inspect"),
    db: Session = Depends(get_db),
):
    """Return stored Garmin record counts by summary type for import diagnostics."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        return build_import_status_payload(db, resolved_user_id, period_days)
    except Exception as e:
        logger.error(f"Import status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/weekly")
async def weekly_analysis(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(7, ge=1, le=90, description="Window size in days"),
    db: Session = Depends(get_db)
):
    """Return training summary for a given window and baseline comparison."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        now = datetime.utcnow()
        current_start = now - timedelta(days=days)
        baseline_start = current_start - timedelta(days=28)

        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
            GarminActivityData.start_time >= baseline_start
        ).order_by(GarminActivityData.start_time.desc()).all()

        current_week = [activity for activity in activities if activity.start_time >= current_start]
        baseline_window = [activity for activity in activities if baseline_start <= activity.start_time < current_start]

        current_metrics = summarize_activities(current_week)
        baseline_totals = summarize_activities(baseline_window)
        baseline_weekly = {
            "sessions": round(baseline_totals["sessions"] / 4, 2),
            "distance_km": round(baseline_totals["distance_km"] / 4, 2),
            "duration_hours": round(baseline_totals["duration_hours"] / 4, 2),
            "average_heart_rate": baseline_totals["average_heart_rate"],
            "running_sessions": round(baseline_totals["running_sessions"] / 4, 2),
            "cycling_sessions": round(baseline_totals["cycling_sessions"] / 4, 2),
        }

        baseline_duration = baseline_weekly["duration_hours"]
        load_ratio = round(
            (current_metrics["duration_hours"] / baseline_duration), 2
        ) if baseline_duration and baseline_duration > 0 else None

        hr_delta = None
        if current_metrics["average_heart_rate"] is not None and baseline_weekly["average_heart_rate"] is not None:
            hr_delta = round(current_metrics["average_heart_rate"] - baseline_weekly["average_heart_rate"], 1)

        metrics_delta = {
            "sessions_percent": compute_percent_change(current_metrics["sessions"], baseline_weekly["sessions"]),
            "distance_percent": compute_percent_change(current_metrics["distance_km"], baseline_weekly["distance_km"]),
            "duration_percent": compute_percent_change(current_metrics["duration_hours"], baseline_weekly["duration_hours"]),
            "avg_heart_rate_delta": hr_delta,
        }

        if load_ratio is None:
            recommendation = "Not enough historical data yet. Keep building consistent easy sessions."
        elif load_ratio > 1.25:
            recommendation = "High load increase this week. Keep next sessions easy and prioritize recovery."
        elif load_ratio < 0.75:
            recommendation = "Training load is below baseline. Add one extra easy session if recovery is good."
        else:
            recommendation = "Load looks balanced versus your baseline. Keep the current structure."

        weekly_summary = build_weekly_summary(
            current_week=current_metrics,
            baseline_weekly=baseline_weekly,
            load_ratio=load_ratio,
            hr_delta=hr_delta,
        )

        highlights = []
        if load_ratio is not None:
            if load_ratio > 1.25:
                highlights.append({"type": "warning", "label": "Hoge belasting", "text": f"Load ratio {load_ratio}x — plan extra herstel"})
            elif load_ratio < 0.75:
                highlights.append({"type": "info", "label": "Lage belasting", "text": f"Load ratio {load_ratio}x — ruimte om op te bouwen"})
            else:
                highlights.append({"type": "success", "label": "Gebalanceerd", "text": f"Load ratio {load_ratio}x — goed bezig"})

        if hr_delta is not None:
            if hr_delta > 3:
                highlights.append({"type": "warning", "label": "Hartslag stijgt", "text": f"+{hr_delta} bpm vs baseline"})
            elif hr_delta < -3:
                highlights.append({"type": "success", "label": "Hartslag daalt", "text": f"{hr_delta} bpm vs baseline"})

        if current_metrics["running_sessions"] > 0 or current_metrics["cycling_sessions"] > 0:
            highlights.append({
                "type": "info",
                "label": "Verdeling",
                "text": f"{current_metrics['running_sessions']} run · {current_metrics['cycling_sessions']} fiets",
            })

        return {
            "days": days,
            "window": {
                "current_start": current_start.isoformat(),
                "current_end": now.isoformat(),
                "baseline_start": baseline_start.isoformat(),
                "baseline_end": current_start.isoformat(),
            },
            "current_week": current_metrics,
            "baseline_weekly": baseline_weekly,
            "deltas": metrics_delta,
            "load_ratio": load_ratio,
            "insight": recommendation,
            "summary": weekly_summary,
            "highlights": highlights,
        }
    except Exception as e:
        logger.error(f"Weekly analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/profile")
async def training_profile(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(120, ge=30, le=365, description="Days used to learn personal targets"),
    current_days: int = Query(7, ge=1, le=30, description="Current load window for sport baselines"),
    db: Session = Depends(get_db),
):
    """Return personalized targets, sport-specific load baselines, and workout patterns."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        now = datetime.utcnow()
        start_date = now - timedelta(days=max(days, current_days + 28))
        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
            GarminActivityData.start_time >= start_date,
        ).order_by(GarminActivityData.start_time.desc()).all()
        activity_details = db.query(GarminActivityAuxiliaryData).filter(
            GarminActivityAuxiliaryData.user_id == resolved_user_id,
            GarminActivityAuxiliaryData.summary_type == "activityDetails",
            or_(
                GarminActivityAuxiliaryData.start_time >= start_date,
                GarminActivityAuxiliaryData.start_time.is_(None),
            ),
        ).order_by(GarminActivityAuxiliaryData.start_time.desc()).all()

        return {
            "period_days": days,
            "current_days": current_days,
            "generated_at": now.isoformat(),
            "personal_targets": build_personal_training_profile(activities, activity_details),
            "sport_baselines": build_sport_baselines(activities, current_days, now),
            "workout_patterns": build_workout_patterns(activities, activity_details),
            "method": {
                "phase": 2,
                "source": "Garmin activityDetails samples/laps with activity summary fallback",
                "activity_details": len(activity_details),
                "notes": [
                    "Targets are learned per sport from detail segments where available.",
                    "Workout patterns are inferred on demand from details, activity names, and summaries.",
                    "Four-week load comparison is calculated inside the same sport type.",
                    "Activity summaries remain the fallback when details are missing.",
                ],
            },
        }
    except Exception as e:
        logger.error(f"Training profile failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _training_context(db: Session, user_id: int, days: int = 120, current_days: int = 7) -> Dict[str, Any]:
    now = datetime.utcnow()
    start_date = now - timedelta(days=max(days, current_days + 28))
    activities = db.query(GarminActivityData).filter(
        GarminActivityData.user_id == user_id,
        GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
        GarminActivityData.start_time >= start_date,
    ).order_by(GarminActivityData.start_time.desc()).all()
    activity_details = db.query(GarminActivityAuxiliaryData).filter(
        GarminActivityAuxiliaryData.user_id == user_id,
        GarminActivityAuxiliaryData.summary_type == "activityDetails",
        or_(
            GarminActivityAuxiliaryData.start_time >= start_date,
            GarminActivityAuxiliaryData.start_time.is_(None),
        ),
    ).order_by(GarminActivityAuxiliaryData.start_time.desc()).all()
    return {
        "period_days": days,
        "current_days": current_days,
        "generated_at": now.isoformat(),
        "personal_targets": build_personal_training_profile(activities, activity_details),
        "sport_baselines": build_sport_baselines(activities, current_days, now),
        "workout_patterns": build_workout_patterns(activities, activity_details),
    }


@router.get("/training/recommendation")
async def training_recommendation(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(120, ge=30, le=365),
    current_days: int = Query(7, ge=1, le=30),
    temperature_c: Optional[float] = Query(None),
    wind_speed_kmh: Optional[float] = Query(None),
    condition: Optional[str] = Query(None),
    training_note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return the canonical backend-owned workout recommendation for the app."""
    try:
        from app.core.recovery_snapshot import build_live_recovery_snapshot

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        training = _training_context(db, resolved_user_id, days, current_days)
        recovery = build_live_recovery_snapshot(
            db,
            resolved_user_id,
            lookback_days=14,
            readiness_version=settings.readiness_version,
        )
        weather = {
            "temperature_c": temperature_c,
            "wind_speed_kmh": wind_speed_kmh,
            "condition": condition,
            "training_note": training_note,
        } if any(value is not None for value in [temperature_c, wind_speed_kmh, condition, training_note]) else None
        return build_recommendation(
            user_id=resolved_user_id,
            recovery=recovery,
            training_profile=training,
            weather=weather,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/recommendation/adjust")
async def adjust_training_recommendation(
    payload: RecommendationAdjustRequest,
    db: Session = Depends(get_db),
):
    """Apply a deterministic coach/user instruction to a recommendation draft."""
    try:
        training = payload.training_profile or _training_context(db, payload.user_id)
        return adjust_recommendation(
            payload.recommendation,
            payload.instruction,
            training_profile=training,
        )
    except Exception as e:
        logger.error(f"Training recommendation adjustment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/workouts")
async def create_training_workout(
    payload: WorkoutCreateRequest,
    db: Session = Depends(get_db),
):
    """Persist an approved workout recommendation in existing workout history."""
    try:
        recommendation = payload.recommendation
        if not recommendation.get("blocks"):
            raise HTTPException(status_code=422, detail="recommendation.blocks is required")
        name = workout_name(recommendation)
        data = {
            "recommendation": recommendation,
            "delivery": {
                "status": payload.status,
                "fit_file_path": None,
                "garmin": None,
            },
            "created_at": datetime.utcnow().isoformat(),
        }
        entry = WorkoutHistory(
            user_id=payload.user_id,
            workout_type=recommendation.get("type") or "CUSTOM",
            workout_name=name,
            created_at=datetime.utcnow(),
            recovery_score_before=recommendation.get("recoveryScore"),
            fit_file_path=None,
            workout_data=json.dumps(data),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {
            "status": "saved",
            "workout_id": entry.id,
            "workout_name": entry.workout_name,
            "fit_url": f"/garmin/training/workouts/{entry.id}/fit",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create training workout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_workout_history(db: Session, workout_id: int) -> WorkoutHistory:
    entry = db.query(WorkoutHistory).filter(WorkoutHistory.id == workout_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Workout not found")
    return entry


def _history_payload(entry: WorkoutHistory) -> Dict[str, Any]:
    try:
        return json.loads(entry.workout_data or "{}")
    except Exception:
        return {}


def _set_history_payload(db: Session, entry: WorkoutHistory, payload: Dict[str, Any]) -> None:
    entry.workout_data = json.dumps(payload)
    db.commit()
    db.refresh(entry)


@router.get("/training/workouts/{workout_id}/fit")
async def download_training_workout_fit(
    workout_id: int,
    db: Session = Depends(get_db),
):
    """Create or return a FIT file for a stored workout recommendation."""
    try:
        entry = _get_workout_history(db, workout_id)
        payload = _history_payload(entry)
        recommendation = payload.get("recommendation") or {}
        if not recommendation.get("blocks"):
            raise HTTPException(status_code=422, detail="Stored workout has no recommendation blocks")
        if not entry.fit_file_path or not os.path.exists(entry.fit_file_path):
            from app.tools.workout_tools import create_fit_file

            fit_path = create_fit_file(
                user_id=None,
                workout_steps=recommendation_to_workout_steps(recommendation),
                workout_type=recommendation.get("type") or entry.workout_type,
                sport=garmin_sport_type(recommendation.get("sportType")),
                recovery_score=entry.recovery_score_before,
            )
            entry.fit_file_path = fit_path
            payload.setdefault("delivery", {})["status"] = "fit_ready"
            payload["delivery"]["fit_file_path"] = fit_path
            _set_history_payload(db, entry, payload)
        filename = f"{entry.workout_name.lower().replace(' ', '_')}.fit"
        return FileResponse(
            entry.fit_file_path,
            media_type="application/octet-stream",
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FIT generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"fit_error: {e}")


@router.post("/training/workouts/{workout_id}/garmin")
async def upload_training_workout_to_garmin(
    workout_id: int,
    db: Session = Depends(get_db),
):
    """Upload a stored workout to Garmin Connect when WORKOUT_IMPORT is granted."""
    try:
        entry = _get_workout_history(db, workout_id)
        payload = _history_payload(entry)
        recommendation = payload.get("recommendation") or {}
        if not recommendation.get("blocks"):
            raise HTTPException(status_code=422, detail="invalid_workout")

        from app.tools.garmin_training_api import GarminTrainingAPIClient
        from app.tools.garmin_workout_converter import convert_workout_to_garmin_json

        try:
            training_client = GarminTrainingAPIClient(db, entry.user_id)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"token_expired: {exc}") from exc

        try:
            permissions = extract_permission_names(training_client.check_permissions())
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"garmin_error: permission check failed: {exc}") from exc
        if "WORKOUT_IMPORT" not in permissions:
            raise HTTPException(status_code=403, detail="permission_missing: WORKOUT_IMPORT")

        workout_json = convert_workout_to_garmin_json(
            workout_name=entry.workout_name,
            workout_type=recommendation.get("type") or entry.workout_type,
            workout_steps=recommendation_to_workout_steps(recommendation),
            description="Floating Coach workout",
            sport=garmin_sport_type(recommendation.get("sportType")),
        )
        try:
            result = training_client.create_workout(workout_json)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"garmin_error: {exc}") from exc

        payload.setdefault("delivery", {})["status"] = "uploaded"
        payload["delivery"]["garmin"] = result
        _set_history_payload(db, entry, payload)
        return {
            "status": "uploaded",
            "workout_id": entry.id,
            "garmin": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Garmin workout upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"garmin_error: {e}")


@router.get("/recovery")
async def get_recovery_snapshot(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    lookback_days: int = Query(14, ge=1, le=90, description="How far back to search for latest health data"),
    db: Session = Depends(get_db)
):
    """Return the latest Garmin health metrics needed by the app recovery UI."""
    try:
        from app.core.recovery_snapshot import build_live_recovery_snapshot

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        # lookback_days is resolved by FastAPI only on HTTP requests — never call this
        # handler from other endpoints; use build_live_recovery_snapshot() instead.
        return build_live_recovery_snapshot(
            db,
            resolved_user_id,
            lookback_days=int(lookback_days),
            readiness_version=settings.readiness_version,
        )
    except Exception as e:
        logger.error(f"Recovery snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/backfill")
async def request_backfill(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    data_type: str = Query(..., description="Type of data to backfill, e.g. core, activities, health, full"),
    db: Session = Depends(get_db)
):
    """
    Request backfill of historical data from Garmin.

    Data will be sent asynchronously via webhooks.
    """
    try:
        from datetime import datetime

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)
        normalized_type = {
            "stress": "stressDetails",
            "bodyCompositions": "bodyComps",
            "bodyComposition": "bodyComps",
            "pulseox": "pulseOx",
            "bloodPressure": "bloodPressures",
            "skinTemperature": "skinTemp",
            "moveiq": "moveIQActivities",
            "moveIQ": "moveIQActivities",
        }.get(data_type, data_type)

        health_backfill: Dict[str, list[Dict]] = {}
        health_types = []
        if normalized_type in ["core", "both", "all"]:
            health_types = CORE_HEALTH_BACKFILL_TYPES.copy()
        elif normalized_type in ["health", "full-health", "full"]:
            health_types = DEFAULT_HEALTH_BACKFILL_TYPES.copy()
        elif normalized_type in DEFAULT_HEALTH_BACKFILL_TYPES:
            health_types = [normalized_type]

        activity_backfill: Dict[str, list[Dict]] = {}
        activity_types = []
        if normalized_type in ["core", "both", "all"]:
            activity_types = CORE_ACTIVITY_BACKFILL_TYPES.copy()
        elif normalized_type in ["activity", "full-activity", "full"]:
            activity_types = DEFAULT_ACTIVITY_BACKFILL_TYPES.copy()
        elif normalized_type in DEFAULT_ACTIVITY_BACKFILL_TYPES:
            activity_types = [normalized_type]

        for health_type in health_types:
            health_backfill[health_type] = request_health_backfill_range(client, health_type, start, end)
        for activity_type in activity_types:
            activity_backfill[activity_type] = request_activity_backfill_range(
                client, start, end, activity_type
            )

        if not health_backfill and not activity_backfill:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Unsupported data_type. Use all, both, health, activity, activities, "
                    "activityDetails, moveIQActivities, full, or a Health API type such as hrv."
                ),
            )

        return {
            "status": "success",
            "message": f"Backfill requested for {data_type} from {start_date} to {end_date}. Data will be sent via webhooks.",
            "rate_limit_note": "Garmin evaluation keys allow about 100 days of backfill per minute. Use core/all first; wait before full imports.",
            "activity_backfill": activity_backfill,
            "health_backfill": health_backfill,
        }

    except Exception as e:
        logger.error(f"Backfill request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/replay-webhooks")
async def replay_webhooks(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    hours: int = Query(168, ge=1, le=720, description="How far back to scan failed webhook events"),
    db: Session = Depends(get_db),
):
    """Re-process stored partial/failed Garmin webhook payloads for this account."""
    try:
        from app.core.garmin_import import garmin_user_id_for_internal_user, replay_failed_webhooks

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        replay = replay_failed_webhooks(
            db,
            resolved_user_id,
            garmin_user_id=garmin_user_id_for_internal_user(db, resolved_user_id),
            hours=hours,
            limit=100,
        )
        import_status = build_import_status_payload(db, resolved_user_id, 30)
        return {
            "status": "success",
            "webhook_replay": replay,
            "import_status": import_status.get("summary"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook replay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/sync-initial")
async def sync_initial_garmin_data(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db),
):
    """Trigger initial activity + health backfill (e.g. after connect or if import stayed empty)."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        return trigger_initial_import(db, resolved_user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync initial import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/backfill/smart")
async def request_smart_activity_backfill(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(120, ge=7, le=180, description="How many days of activity history to request"),
    db: Session = Depends(get_db),
):
    """Request activity backfill with automatic Garmin minimum-date fallback."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)

        end = datetime.utcnow()
        start = end - timedelta(days=days)
        activity_backfill = {
            activity_type: request_activity_backfill_range(client, start, end, activity_type)
            for activity_type in CORE_ACTIVITY_BACKFILL_TYPES
        }

        return {
            "status": "success",
            "message": "Smart activity backfill requested. Data will arrive via activity webhooks.",
            "activity_backfill": activity_backfill,
        }
    except Exception as e:
        logger.error(f"Smart backfill request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBHOOK ENDPOINTS - Garmin pushes/pings data to these endpoints
# ============================================================================

@router.post("/webhook/health")
async def receive_health_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive health/wellness data webhooks from Garmin.

    This endpoint receives PING notifications for:
    - dailies, epochs, sleeps, bodyComps, stressDetails, userMetrics,
    - pulseox, allDayRespiration, healthSnapshot, hrv, bloodPressures, skinTemp
    """
    try:
        data = await request.json()
        logger.info(f"Received health webhook: {data}")
        event = _create_webhook_event(db, "health", data)
        errors = []

        # Process each summary type
        for summary_type, items in data.items():
            if summary_type == "deregistrations":
                continue  # Handle in separate endpoint

            for item in items:
                garmin_user_id = item.get('userId')
                callback_url = item.get('callbackURL')

                from app.core.garmin_import import resolve_internal_user_for_garmin
                from app.tools.garmin_client import write_health_data

                user_id = resolve_internal_user_for_garmin(db, garmin_user_id)
                if not user_id:
                    message = f"No token found for Garmin user {garmin_user_id}"
                    errors.append(message)
                    logger.warning(message)
                    continue

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH data directly
                    try:
                        write_health_data(db, user_id, summary_type, [item])
                        logger.info(f"Stored PUSH {summary_type} for user {user_id}")
                    except Exception as e:
                        message = f"Failed to store PUSH {summary_type}: {e}"
                        errors.append(message)
                        logger.error(message)
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, user_id)
                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        write_health_data(db, user_id, summary_type, summaries)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {user_id}")
                    else:
                        message = f"{summary_type} callback returned {response.status_code}: {response.text}"
                        errors.append(message)
                        logger.error(message)
                except Exception as e:
                    message = f"Failed to fetch/store {summary_type} from callback URL: {e}"
                    errors.append(message)
                    logger.error(message)

        _finish_webhook_event(db, event, errors)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Health webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/activity")
async def receive_activity_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive activity data webhooks from Garmin.

    This endpoint receives PING notifications for:
    - activities, activityDetails, activityFiles, moveIQActivities, manuallyUpdatedActivities
    """
    try:
        data = await request.json()
        logger.info(f"Received activity webhook: {data}")
        event = _create_webhook_event(db, "activity", data)
        errors = []

        # Process each summary type
        for summary_type, items in data.items():
            for item in items:
                garmin_user_id = item.get('userId')
                callback_url = item.get('callbackURL')

                from app.core.garmin_import import resolve_internal_user_for_garmin
                from app.tools.garmin_client import (
                    write_activity_auxiliary_data,
                    write_activity_data,
                )

                user_id = resolve_internal_user_for_garmin(db, garmin_user_id)
                if not user_id:
                    message = f"No token found for Garmin user {garmin_user_id}"
                    errors.append(message)
                    logger.warning(message)
                    continue

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH activity data directly
                    try:
                        write_activity_data(db, user_id, [item], summary_type)
                        logger.info(f"Stored PUSH {summary_type} for user {user_id}")
                    except Exception as e:
                        message = f"Failed to store PUSH {summary_type}: {e}"
                        errors.append(message)
                        logger.error(message)
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, user_id)
                    if summary_type == "activityFiles":
                        # File pings contain useful metadata in the ping itself, then binary content at callbackURL.
                        write_activity_auxiliary_data(db, user_id, summary_type, [item])
                        file_response = requests.get(
                            callback_url,
                            headers=client._get_headers()
                        )
                        if file_response.status_code == 200:
                            client._store_activity_file_content(
                                metadata=item,
                                content=file_response.content,
                                content_type=file_response.headers.get("content-type"),
                            )
                            logger.info(f"Stored activity file {item.get('summaryId')} for user {user_id}")
                        else:
                            message = f"Activity file callback returned {file_response.status_code}: {file_response.text}"
                            errors.append(message)
                            logger.error(message)
                        continue

                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        write_activity_data(db, user_id, summaries, summary_type)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {user_id}")
                    else:
                        message = f"{summary_type} callback returned {response.status_code}: {response.text}"
                        errors.append(message)
                        logger.error(message)
                except Exception as e:
                    message = f"Failed to fetch/store {summary_type} from callback URL: {e}"
                    errors.append(message)
                    logger.error(message)

        _finish_webhook_event(db, event, errors)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Activity webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/deregistration")
async def receive_deregistration_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive deregistration notifications from Garmin.

    Called when a user disconnects their Garmin account.
    """
    try:
        data = await request.json()
        logger.info(f"Received deregistration webhook: {data}")
        event = _create_webhook_event(db, "deregistration", data)
        errors = []

        # Extract user ID from webhook
        deregistrations = data.get('deregistrations', [])

        for dereg in deregistrations:
            garmin_user_id = dereg.get('userId')
            if garmin_user_id:
                # Find and delete tokens
                garmin_token = db.query(GarminToken).filter(
                    GarminToken.garmin_user_id == garmin_user_id
                ).first()

                if garmin_token:
                    db.delete(garmin_token)
                    logger.info(f"Deleted tokens for Garmin user {garmin_user_id}")
                else:
                    errors.append(f"No token found for Garmin user {garmin_user_id}")

        db.commit()
        _finish_webhook_event(db, event, errors)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Deregistration webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/permissions")
async def receive_permissions_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive user permission change notifications from Garmin.

    Called when a user changes their data sharing permissions.
    """
    try:
        data = await request.json()
        logger.info(f"Received permissions webhook: {data}")
        event = _create_webhook_event(db, "permissions", data)

        # TODO: Update user permissions in database
        # For now, just log it

        _finish_webhook_event(db, event, [])
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Permissions webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
