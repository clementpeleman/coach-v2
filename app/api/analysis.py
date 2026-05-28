"""Deep athlete profile analysis from Garmin activity and health data."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import GarminActivityData, GarminHealthData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ActivityAnalysisRequest(BaseModel):
    user_id: int = Field(..., description="Internal user ID")
    message: Optional[str] = Field(default=None, description="Natural language analysis request")
    intent: Optional[str] = Field(default=None, description="Structured analysis intent")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    compare_start_date: Optional[str] = None
    compare_end_date: Optional[str] = None
    sport: Optional[str] = None
    bucket: Optional[str] = None
    data_source: Optional[str] = Field(default=None, description="auto, details, or summary")
    last_context: Optional[dict[str, Any]] = None


def _parse_raw(activity: GarminActivityData) -> dict:
    raw = activity.data
    return json.loads(raw) if isinstance(raw, str) else raw


def _build_sport_profile(activities: List[GarminActivityData], sport: str) -> Optional[Dict]:
    sport_acts = [a for a in activities if (a.activity_type or "").upper() == sport.upper()]
    if not sport_acts:
        return None

    hrs = [a.average_heart_rate for a in sport_acts if a.average_heart_rate]
    max_hrs = [a.max_heart_rate for a in sport_acts if a.max_heart_rate]
    distances = [a.distance for a in sport_acts if a.distance]
    durations = [a.duration for a in sport_acts if a.duration]
    calories = [a.calories for a in sport_acts if a.calories]

    raws = [_parse_raw(a) for a in sport_acts]
    paces = [r.get("averagePaceInMinutesPerKilometer") for r in raws if r.get("averagePaceInMinutesPerKilometer")]
    speeds = [r.get("averageSpeedInMetersPerSecond") for r in raws if r.get("averageSpeedInMetersPerSecond")]
    elevations = [r.get("totalElevationGainInMeters") for r in raws if r.get("totalElevationGainInMeters")]
    cadences = [r.get("averageRunCadenceInStepsPerMinute") for r in raws if r.get("averageRunCadenceInStepsPerMinute")]

    best_distance = max(distances) if distances else None
    best_duration = max(durations) if durations else None
    fastest_pace = min(paces) if paces else None
    max_speed = max(speeds) if speeds else None

    profile: Dict = {
        "total_sessions": len(sport_acts),
        "total_distance_km": round(sum(distances) / 1000, 1) if distances else 0,
        "total_duration_hours": round(sum(durations) / 3600, 1) if durations else 0,
        "total_calories": sum(calories) if calories else 0,
        "total_elevation_m": round(sum(elevations), 0) if elevations else 0,
        "avg_distance_km": round(sum(distances) / len(distances) / 1000, 2) if distances else None,
        "avg_duration_min": round(sum(durations) / len(durations) / 60, 1) if durations else None,
        "avg_heart_rate": round(sum(hrs) / len(hrs)) if hrs else None,
        "max_heart_rate_observed": max(max_hrs) if max_hrs else None,
        "avg_calories_per_session": round(sum(calories) / len(calories)) if calories else None,
    }

    if sport.upper() == "RUNNING":
        profile["avg_pace_min_km"] = round(sum(paces) / len(paces), 2) if paces else None
        profile["best_pace_min_km"] = round(fastest_pace, 2) if fastest_pace else None
        profile["avg_cadence_spm"] = round(sum(cadences) / len(cadences), 1) if cadences else None
        profile["longest_run_km"] = round(best_distance / 1000, 2) if best_distance else None
        profile["longest_run_min"] = round(best_duration / 60, 1) if best_duration else None
    elif sport.upper() == "CYCLING":
        profile["avg_speed_kmh"] = round(sum(speeds) / len(speeds) * 3.6, 1) if speeds else None
        profile["max_speed_kmh"] = round(max_speed * 3.6, 1) if max_speed else None
        profile["avg_elevation_m"] = round(sum(elevations) / len(elevations), 0) if elevations else None
        profile["longest_ride_km"] = round(best_distance / 1000, 2) if best_distance else None
        profile["longest_ride_min"] = round(best_duration / 60, 1) if best_duration else None

    return profile


def _estimate_hr_zones(max_hr: int) -> Dict:
    return {
        "max_hr_observed": max_hr,
        "zone1": {"name": "Herstel", "range": f"< {round(max_hr * 0.6)} bpm", "min": round(max_hr * 0.5), "max": round(max_hr * 0.6)},
        "zone2": {"name": "Aerobe basis", "range": f"{round(max_hr * 0.6)}-{round(max_hr * 0.7)} bpm", "min": round(max_hr * 0.6), "max": round(max_hr * 0.7)},
        "zone3": {"name": "Tempo", "range": f"{round(max_hr * 0.7)}-{round(max_hr * 0.8)} bpm", "min": round(max_hr * 0.7), "max": round(max_hr * 0.8)},
        "zone4": {"name": "Threshold", "range": f"{round(max_hr * 0.8)}-{round(max_hr * 0.9)} bpm", "min": round(max_hr * 0.8), "max": round(max_hr * 0.9)},
        "zone5": {"name": "VO2max", "range": f"{round(max_hr * 0.9)}-{max_hr} bpm", "min": round(max_hr * 0.9), "max": max_hr},
    }


def _training_patterns(activities: List[GarminActivityData]) -> Dict:
    if not activities:
        return {}

    day_counts: Dict[str, int] = defaultdict(int)
    hour_counts: Dict[int, int] = defaultdict(int)

    for a in activities:
        if a.start_time:
            day_counts[a.start_time.strftime("%A")] += 1
            hour_counts[a.start_time.hour] += 1

    sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)

    dates = sorted([a.start_time for a in activities if a.start_time])
    gaps = []
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i - 1]).days
        gaps.append(gap)

    avg_gap = round(sum(gaps) / len(gaps), 1) if gaps else None
    max_gap = max(gaps) if gaps else None

    first_activity = min(dates) if dates else None
    last_activity = max(dates) if dates else None
    span_weeks = ((last_activity - first_activity).days / 7) if first_activity and last_activity else 0
    sessions_per_week = round(len(activities) / max(span_weeks, 1), 1)

    return {
        "favorite_days": [{"day": d, "count": c} for d, c in sorted_days[:3]],
        "favorite_hours": [{"hour": h, "count": c} for h, c in sorted_hours[:3]],
        "avg_days_between_sessions": avg_gap,
        "max_days_between_sessions": max_gap,
        "sessions_per_week": sessions_per_week,
        "first_activity": first_activity.isoformat() if first_activity else None,
        "last_activity": last_activity.isoformat() if last_activity else None,
        "total_active_weeks": round(span_weeks, 1) if span_weeks else 0,
    }


def _personal_records(activities: List[GarminActivityData]) -> Dict:
    records: Dict = {}

    runs = [a for a in activities if (a.activity_type or "").upper() == "RUNNING"]
    rides = [a for a in activities if (a.activity_type or "").upper() == "CYCLING"]

    if runs:
        fastest = min(runs, key=lambda a: _parse_raw(a).get("averagePaceInMinutesPerKilometer", 999))
        longest = max(runs, key=lambda a: a.distance or 0)
        max_hr_run = max(runs, key=lambda a: a.max_heart_rate or 0)
        records["running"] = {
            "fastest_pace": {
                "value": round(_parse_raw(fastest).get("averagePaceInMinutesPerKilometer", 0), 2),
                "unit": "min/km",
                "date": fastest.start_time.isoformat() if fastest.start_time else None,
                "activity": fastest.activity_name,
            },
            "longest_distance": {
                "value": round((longest.distance or 0) / 1000, 2),
                "unit": "km",
                "date": longest.start_time.isoformat() if longest.start_time else None,
                "activity": longest.activity_name,
            },
            "max_heart_rate": {
                "value": max_hr_run.max_heart_rate,
                "unit": "bpm",
                "date": max_hr_run.start_time.isoformat() if max_hr_run.start_time else None,
                "activity": max_hr_run.activity_name,
            },
        }

    if rides:
        fastest = max(rides, key=lambda a: _parse_raw(a).get("averageSpeedInMetersPerSecond", 0))
        longest = max(rides, key=lambda a: a.distance or 0)
        most_elevation = max(rides, key=lambda a: _parse_raw(a).get("totalElevationGainInMeters", 0))
        max_hr_ride = max(rides, key=lambda a: a.max_heart_rate or 0)
        records["cycling"] = {
            "fastest_avg_speed": {
                "value": round(_parse_raw(fastest).get("averageSpeedInMetersPerSecond", 0) * 3.6, 1),
                "unit": "km/h",
                "date": fastest.start_time.isoformat() if fastest.start_time else None,
                "activity": fastest.activity_name,
            },
            "longest_distance": {
                "value": round((longest.distance or 0) / 1000, 2),
                "unit": "km",
                "date": longest.start_time.isoformat() if longest.start_time else None,
                "activity": longest.activity_name,
            },
            "most_elevation": {
                "value": round(_parse_raw(most_elevation).get("totalElevationGainInMeters", 0)),
                "unit": "m",
                "date": most_elevation.start_time.isoformat() if most_elevation.start_time else None,
                "activity": most_elevation.activity_name,
            },
            "max_heart_rate": {
                "value": max_hr_ride.max_heart_rate,
                "unit": "bpm",
                "date": max_hr_ride.start_time.isoformat() if max_hr_ride.start_time else None,
                "activity": max_hr_ride.activity_name,
            },
        }

    return records


def _health_summary(health_data: List[GarminHealthData]) -> Optional[Dict]:
    dailies = [h for h in health_data if h.summary_type == "dailies"]
    if not dailies:
        return None

    resting_hrs = []
    for d in dailies:
        raw = json.loads(d.data) if isinstance(d.data, str) else d.data
        rhr = raw.get("restingHeartRateInBeatsPerMinute")
        if rhr and rhr > 0:
            resting_hrs.append(rhr)

    return {
        "days_with_data": len(dailies),
        "avg_resting_hr": round(sum(resting_hrs) / len(resting_hrs)) if resting_hrs else None,
        "min_resting_hr": min(resting_hrs) if resting_hrs else None,
        "max_resting_hr": max(resting_hrs) if resting_hrs else None,
    }


@router.post("/activity")
async def activity_analysis(
    payload: ActivityAnalysisRequest,
    db: Session = Depends(get_db),
):
    """Return a chart-ready activity analysis from a structured or natural-language request."""
    from app.tools.activity_analysis import (
        build_activity_analysis,
        detect_activity_analysis_request,
    )

    request: Optional[dict[str, Any]] = None
    if payload.message:
        request = detect_activity_analysis_request(payload.message, payload.last_context)
    if request is None and payload.intent:
        request = {
            "intent": payload.intent,
            "message": payload.message,
            "sport": payload.sport,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "compare_start_date": payload.compare_start_date,
            "compare_end_date": payload.compare_end_date,
            "bucket": payload.bucket,
            "data_source": payload.data_source,
        }
    if request is None:
        raise HTTPException(
            status_code=422,
            detail="Geen ondersteunde activiteitenanalyse herkend.",
        )
    return build_activity_analysis(db, payload.user_id, request)


@router.get("/profile")
async def athlete_profile(
    user_id: int = Query(..., description="Internal user ID"),
    db: Session = Depends(get_db),
):
    """Build a comprehensive athlete profile from all stored Garmin data."""
    activities = (
        db.query(GarminActivityData)
        .filter(GarminActivityData.user_id == user_id)
        .order_by(GarminActivityData.start_time.desc())
        .all()
    )

    health_data = (
        db.query(GarminHealthData)
        .filter(GarminHealthData.user_id == user_id)
        .order_by(GarminHealthData.start_time.desc())
        .all()
    )

    all_max_hrs = [a.max_heart_rate for a in activities if a.max_heart_rate]
    overall_max_hr = max(all_max_hrs) if all_max_hrs else None

    total_distance = sum(a.distance or 0 for a in activities)
    total_duration = sum(a.duration or 0 for a in activities)
    total_calories = sum(a.calories or 0 for a in activities)
    total_elevation = sum(_parse_raw(a).get("totalElevationGainInMeters", 0) for a in activities)

    return {
        "overview": {
            "total_activities": len(activities),
            "total_distance_km": round(total_distance / 1000, 1),
            "total_duration_hours": round(total_duration / 3600, 1),
            "total_calories": total_calories,
            "total_elevation_m": round(total_elevation),
        },
        "heart_rate_zones": _estimate_hr_zones(overall_max_hr) if overall_max_hr else None,
        "running": _build_sport_profile(activities, "RUNNING"),
        "cycling": _build_sport_profile(activities, "CYCLING"),
        "personal_records": _personal_records(activities),
        "training_patterns": _training_patterns(activities),
        "health": _health_summary(health_data),
    }
