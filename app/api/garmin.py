"""Garmin OAuth2 and webhook API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
import requests
import time
import json
import re
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
INITIAL_ACTIVITY_BACKFILL_DAYS = 30
INITIAL_HEALTH_BACKFILL_DAYS = 7


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
    token = None
    if garmin_user_id:
        token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()

    event = GarminWebhookEvent(
        user_id=token.user_id if token else None,
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


def _classify_effort(activity: GarminActivityData, sport_max_hr: Optional[int]) -> str:
    name = (activity.activity_name or "").lower()
    if any(word in name for word in ["easy", "herstel", "recovery", "rustig", "walk", "wandel"]):
        return "easy"
    if any(word in name for word in ["tempo", "threshold", "drempel"]):
        return "threshold"
    if any(word in name for word in ["interval", "vo2", "sprint"]):
        return "vo2"

    avg_hr = activity.average_heart_rate
    if avg_hr and sport_max_hr:
        ratio = avg_hr / sport_max_hr
        if ratio < 0.70:
            return "easy"
        if ratio < 0.80:
            return "endurance"
        if ratio < 0.90:
            return "threshold"
        return "vo2"

    return "endurance"


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


def build_personal_training_profile(activities: list[GarminActivityData]) -> Dict:
    """Build phase-1 personalized training targets from activity summaries."""
    sports: dict[str, list[GarminActivityData]] = {}
    for activity in activities:
        sport = normalize_training_sport(activity)
        if sport in {"UNKNOWN", ""}:
            continue
        sports.setdefault(sport, []).append(activity)

    profile: Dict[str, Dict] = {}
    for sport, sport_activities in sports.items():
        sport_max_hr = max(
            [a.max_heart_rate for a in sport_activities if a.max_heart_rate],
            default=None,
        )
        metric_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        hr_values: dict[str, list[float]] = {"easy": [], "endurance": [], "threshold": [], "vo2": []}
        all_metrics = []

        for activity in sport_activities:
            effort = _classify_effort(activity, sport_max_hr)
            metric = _activity_metric(activity, sport)
            if metric:
                metric_values[effort].append(metric)
                all_metrics.append(metric)
            if activity.average_heart_rate:
                hr_values[effort].append(activity.average_heart_rate)

        zones = {}
        for effort in ["easy", "endurance", "threshold", "vo2"]:
            metric_range = _target_range_for_effort(metric_values, all_metrics, sport, effort)
            hr_range = _range_around(hr_values.get(effort, []), [a.average_heart_rate for a in sport_activities if a.average_heart_rate], True)
            zones[effort] = {
                "metric": _format_metric_range(metric_range, sport),
                "hr": _format_hr_range(hr_range),
                "sample_size": len(metric_values.get(effort, [])) or len(hr_values.get(effort, [])),
            }

        session_count = len(sport_activities)
        confidence = "low"
        if session_count >= 10:
            confidence = "high"
        elif session_count >= 4:
            confidence = "medium"

        profile[sport] = {
            "sport": sport,
            "sessions": session_count,
            "confidence": confidence,
            "metric_type": "speed" if sport in {"CYCLING", "INDOOR_CYCLING"} else "pace",
            "metric_unit": "km/u" if sport in {"CYCLING", "INDOOR_CYCLING"} else ("/100m" if sport == "SWIMMING" else "/km"),
            "max_heart_rate_observed": sport_max_hr,
            "zones": zones,
            "notes": [
                "Gebaseerd op activity summaries; interval- en lapniveau volgt in fase 2."
                if confidence != "high"
                else "Gebaseerd op voldoende recente sessies; fase 2 kan dit verfijnen met laps/details."
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


def _valid_stress_values(values: Dict) -> list[int]:
    return [
        int(value)
        for value in values.values()
        if isinstance(value, int) and value > 0
    ]


def _recent_training_fatigue(activities: list[GarminActivityData]) -> Dict:
    """Estimate short-term fatigue from recent sessions until Garmin training load is available."""
    now = datetime.utcnow()
    session_summaries = []
    weighted_load = 0.0
    hardest = None

    for activity in activities:
        duration_min = (activity.duration or 0) / 60
        if duration_min <= 0:
            continue

        hours_ago = max(0.0, (now - activity.start_time).total_seconds() / 3600) if activity.start_time else 0.0
        avg_hr = activity.average_heart_rate or 0
        max_hr = activity.max_heart_rate or 0
        activity_type = (activity.activity_type or "").upper()

        intensity = 1.0
        if avg_hr >= 160:
            intensity += 0.45
        elif avg_hr >= 145:
            intensity += 0.25
        elif avg_hr >= 130:
            intensity += 0.10
        if max_hr >= 185:
            intensity += 0.15
        if "RUN" in activity_type:
            intensity += 0.10

        decay = max(0.35, 1 - (hours_ago / 72))
        session_load = duration_min * intensity * decay
        weighted_load += session_load

        summary = {
            "activity_id": activity.activity_id,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type,
            "start_time": activity.start_time.isoformat() if activity.start_time else None,
            "hours_ago": round(hours_ago, 1),
            "duration_minutes": round(duration_min),
            "average_heart_rate": activity.average_heart_rate,
            "max_heart_rate": activity.max_heart_rate,
            "load": round(session_load, 1),
        }
        session_summaries.append(summary)
        if hardest is None or summary["load"] > hardest["load"]:
            hardest = summary

    penalty = 0.0
    if weighted_load >= 100:
        penalty = 1.6
    elif weighted_load >= 70:
        penalty = 1.2
    elif weighted_load >= 45:
        penalty = 0.8
    elif weighted_load >= 25:
        penalty = 0.4

    for session in session_summaries:
        if (
            session["hours_ago"] <= 36
            and session["duration_minutes"] >= 40
            and (
                (session["average_heart_rate"] or 0) >= 155
                or (session["max_heart_rate"] or 0) >= 185
            )
        ):
            penalty = max(penalty, 1.1)

    label = "laag"
    if penalty >= 1.2:
        label = "hoog"
    elif penalty >= 0.8:
        label = "matig-hoog"
    elif penalty >= 0.4:
        label = "matig"

    return {
        "load": round(weighted_load, 1),
        "penalty": penalty,
        "label": label,
        "recent_activity_count": len(session_summaries),
        "hardest_activity": hardest,
        "sessions": session_summaries[:5],
    }


def _recovery_score(
    sleep_score: Optional[int],
    sleep_hours: Optional[float],
    avg_stress: Optional[int],
    body_battery: Optional[int],
    hrv: Optional[int],
    recent_training_penalty: float = 0.0,
) -> int:
    score = 3.0

    if sleep_score is not None:
        score += (sleep_score - 70) / 15
    elif sleep_hours is not None:
        score += (sleep_hours - 7) / 1.5

    if avg_stress is not None:
        score += (45 - avg_stress) / 20

    if body_battery is not None:
        score += (body_battery - 50) / 25

    if hrv is not None:
        # Without a personal baseline we only apply a small stabilising signal.
        score += (hrv - 45) / 35

    score -= recent_training_penalty

    return max(0, min(6, int(round(score))))


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

        # Clean up old sessions (e.g., older than 10 minutes)
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        deleted_count = db.query(OAuthSession).filter(OAuthSession.created_at < ten_minutes_ago).delete()
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
            raise HTTPException(status_code=400, detail="Invalid state parameter or session expired")

        # Retrieve data and delete session
        code_verifier = session.code_verifier
        user_id = session.user_id
        db.delete(session)
        db.commit()

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

        # Store tokens in database
        garmin_token = oauth_service.store_tokens(db, user_id, token_data)

        # Get user permissions
        access_token = token_data['access_token']
        permissions = oauth_service.get_user_permissions(access_token)

        # Kick off a conservative initial import after connect. Evaluation keys are
        # limited by days requested, so keep this small and prioritize activities.
        try:
            client = GarminAPIClient(db, user_id)
            backfill_result = request_initial_backfill(client, permissions)
            logger.info(f"Initial Garmin backfill requested after OAuth: {backfill_result}")
        except Exception as backfill_exc:
            logger.warning(f"Initial Garmin backfill after OAuth failed: {backfill_exc}")

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

        # Get user permissions
        permissions = oauth_service.get_user_permissions(access_token)
        garmin_access = build_garmin_capabilities(permissions)

        # Get token info
        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == resolved_user_id
        ).first()
        import_status = build_import_status_payload(db, resolved_user_id, 30)

        return {
            "authenticated": True,
            "garmin_user_id": garmin_token.garmin_user_id,
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
            # Deregister from Garmin API
            try:
                oauth_service.deregister_user(access_token)
            except Exception as e:
                logger.warning(f"Garmin deregistration failed: {e}")

        # Delete local tokens
        oauth_service.delete_tokens(db, resolved_user_id)

        return {
            "status": "success",
            "message": "Successfully disconnected from Garmin"
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
    """Return phase-1 personalized training targets and sport-specific load baselines."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        now = datetime.utcnow()
        start_date = now - timedelta(days=max(days, current_days + 28))
        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
            GarminActivityData.start_time >= start_date,
        ).order_by(GarminActivityData.start_time.desc()).all()

        return {
            "period_days": days,
            "current_days": current_days,
            "generated_at": now.isoformat(),
            "personal_targets": build_personal_training_profile(activities),
            "sport_baselines": build_sport_baselines(activities, current_days, now),
            "method": {
                "phase": 1,
                "source": "Garmin activity summaries",
                "notes": [
                    "Targets are learned per sport from recent sessions.",
                    "Four-week load comparison is calculated inside the same sport type.",
                    "Lap/activity-detail parsing is reserved for phase 2.",
                ],
            },
        }
    except Exception as e:
        logger.error(f"Training profile failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery")
async def get_recovery_snapshot(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    lookback_days: int = Query(14, ge=1, le=90, description="How far back to search for latest health data"),
    db: Session = Depends(get_db)
):
    """Return the latest Garmin health metrics needed by the app recovery UI."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        since = datetime.utcnow() - timedelta(days=lookback_days)

        daily_record = _latest_health_record(db, resolved_user_id, "dailies", since)
        sleep_record = _latest_health_record(db, resolved_user_id, "sleeps", since)
        stress_record = _latest_health_record(db, resolved_user_id, "stressDetails", since)
        hrv_record = _latest_health_record(db, resolved_user_id, "hrv", since)
        recent_activities = (
            db.query(GarminActivityData)
            .filter(
                GarminActivityData.user_id == resolved_user_id,
                GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
                GarminActivityData.start_time >= datetime.utcnow() - timedelta(hours=48),
            )
            .order_by(GarminActivityData.start_time.desc())
            .all()
        )

        daily = _load_health_payload(daily_record)
        sleep = _load_health_payload(sleep_record)
        stress = _load_health_payload(stress_record)
        hrv = _load_health_payload(hrv_record)

        if not any([daily, sleep, stress, hrv]):
            return {
                "source": "empty",
                "calendar_date": None,
                "score": None,
                "metrics": None,
                "message": "No Garmin health data found yet. Sync Garmin Connect or request a backfill.",
            }

        stress_values = _valid_stress_values(stress.get("timeOffsetStressLevelValues", {}))
        body_battery_values = _valid_numeric_values(stress.get("timeOffsetBodyBatteryValues", {}))
        hrv_values = _valid_numeric_values(hrv.get("hrvValues", {}))
        heart_rate_values = _valid_numeric_values(daily.get("timeOffsetHeartRateSamples", {}))

        sleep_duration_seconds = sleep.get("durationInSeconds")
        sleep_hours = round(sleep_duration_seconds / 3600, 1) if sleep_duration_seconds else None
        sleep_score = _sleep_score(sleep)
        avg_stress = round(sum(stress_values) / len(stress_values)) if stress_values else None
        body_battery = round(body_battery_values[-1]) if body_battery_values else None
        hrv_overnight = (
            int(hrv.get("lastNightAvg"))
            if isinstance(hrv.get("lastNightAvg"), (int, float))
            else (round(sum(hrv_values) / len(hrv_values)) if hrv_values else None)
        )

        current_hr = round(heart_rate_values[-1]) if heart_rate_values else daily.get("averageHeartRateInBeatsPerMinute")
        hr_trend = [round(value) for value in heart_rate_values[-60:]]

        date_candidates = [
            payload.get("calendarDate")
            for payload in [sleep, daily, stress, hrv]
            if payload.get("calendarDate")
        ]
        calendar_date = date_candidates[0] if date_candidates else None
        training_fatigue = _recent_training_fatigue(recent_activities)

        score = _recovery_score(
            sleep_score=sleep_score,
            sleep_hours=sleep_hours,
            avg_stress=avg_stress,
            body_battery=body_battery,
            hrv=hrv_overnight,
            recent_training_penalty=training_fatigue["penalty"],
        )

        return {
            "source": "live",
            "calendar_date": calendar_date,
            "score": score,
            "score_model": {
                "version": "health_plus_recent_training_v1",
                "scale": "0-6",
                "notes": [
                    "Health signals use sleep, stress, Body Battery and HRV.",
                    "Recent training reduces the score for 48h based on duration and heart-rate intensity.",
                ],
            },
            "metrics": {
                "sleepScore": sleep_score,
                "sleepHours": sleep_hours,
                "deepSleepMin": _minutes(sleep.get("deepSleepDurationInSeconds")),
                "remMin": _minutes(sleep.get("remSleepInSeconds")),
                "lightMin": _minutes(sleep.get("lightSleepDurationInSeconds")),
                "awakeMin": _minutes(sleep.get("awakeDurationInSeconds")),
                "avgStress": avg_stress,
                "bodyBattery": body_battery,
                "hrvOvernight": hrv_overnight,
                "restingHr": daily.get("restingHeartRateInBeatsPerMinute"),
                "currentHeartRate": current_hr,
                "hrvTrend": [round(value) for value in hrv_values[-7:]],
                "stressTrend": stress_values[-24:],
                "hrTrend": hr_trend,
                "steps": daily.get("steps"),
                "activeKilocalories": daily.get("activeKilocalories"),
                "distanceMeters": daily.get("distanceInMeters"),
                "recentTrainingLoad": training_fatigue["load"],
                "recentTrainingPenalty": training_fatigue["penalty"],
                "recentTrainingLabel": training_fatigue["label"],
                "recentActivityCount48h": training_fatigue["recent_activity_count"],
                "hardestRecentActivity": training_fatigue["hardest_activity"],
            },
            "recent_training": training_fatigue,
            "records": {
                "daily": daily_record.summary_id if daily_record else None,
                "sleep": sleep_record.summary_id if sleep_record else None,
                "stress": stress_record.summary_id if stress_record else None,
                "hrv": hrv_record.summary_id if hrv_record else None,
            },
        }
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

                # Resolve internal user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    message = f"No token found for Garmin user {garmin_user_id}"
                    errors.append(message)
                    logger.warning(message)
                    continue

                user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH data directly
                    try:
                        client = GarminAPIClient(db, user_id)
                        client._store_health_data(summary_type, [item])
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
                        client._store_health_data(summary_type, summaries)
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

                # Resolve internal user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    message = f"No token found for Garmin user {garmin_user_id}"
                    errors.append(message)
                    logger.warning(message)
                    continue

                user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH activity data directly
                    try:
                        client = GarminAPIClient(db, user_id)
                        client._store_activity_data([item], summary_type)
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
                        client._store_activity_auxiliary_data(summary_type, [item])
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
                        client._store_activity_data(summaries, summary_type)
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
