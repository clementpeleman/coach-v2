"""Build live Garmin recovery snapshot for API and agent tools."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.readiness import (
    READINESS_VERSION_V3,
    READINESS_VERSION_V4,
    compute_readiness_score,
    compute_recent_fatigue,
)
from app.database.models import GarminActivityData, GarminHealthData


def _load_health_payload(record: Optional[GarminHealthData]) -> Dict:
    if not record:
        return {}
    if isinstance(record.data, str):
        try:
            return json.loads(record.data)
        except json.JSONDecodeError:
            return {}
    return record.data or {}


def _latest_health_record(db: Session, user_id: int, summary_type: str, since: datetime) -> Optional[GarminHealthData]:
    return (
        db.query(GarminHealthData)
        .filter(
            GarminHealthData.user_id == user_id,
            GarminHealthData.summary_type == summary_type,
            GarminHealthData.start_time >= since,
        )
        .order_by(GarminHealthData.start_time.desc())
        .first()
    )


def _hrv_history(db: Session, user_id: int, since: datetime, limit: int = 14) -> List[int]:
    records = (
        db.query(GarminHealthData)
        .filter(
            GarminHealthData.user_id == user_id,
            GarminHealthData.summary_type == "hrv",
            GarminHealthData.start_time >= since,
        )
        .order_by(GarminHealthData.start_time.desc())
        .limit(limit)
        .all()
    )
    values: List[int] = []
    for record in records:
        payload = _load_health_payload(record)
        last_night = payload.get("lastNightAvg")
        if isinstance(last_night, (int, float)) and last_night > 0:
            values.append(int(last_night))
        else:
            hrv_vals = [
                int(v)
                for v in (payload.get("hrvValues") or {}).values()
                if isinstance(v, (int, float)) and v > 0
            ]
            if hrv_vals:
                values.append(int(sum(hrv_vals) / len(hrv_vals)))
    return values


def _sleep_score(sleep: Dict) -> Optional[int]:
    score = (
        sleep.get("overallSleepScore", {}).get("value")
        or sleep.get("sleepScores", {}).get("overall", {}).get("value")
    )
    return int(score) if isinstance(score, (int, float)) else None


def _minutes(value_seconds: Optional[int]) -> int:
    return int((value_seconds or 0) / 60)


def _valid_numeric_values(values: Dict) -> list:
    return [float(v) for v in values.values() if isinstance(v, (int, float)) and v >= 0]


def _valid_numeric_offset_series(values: Dict) -> list:
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


def _valid_stress_values(values: Dict) -> list:
    return [int(v) for v in values.values() if isinstance(v, int) and v > 0]


def _body_battery_at_wake(stress: Dict, sleep: Dict) -> Optional[int]:
    stress_start = stress.get("startTimeInSeconds")
    if not isinstance(stress_start, (int, float)):
        return None
    sleep_start = sleep.get("startTimeInSeconds")
    sleep_duration = sleep.get("durationInSeconds")
    wake_timestamp = None
    if isinstance(sleep_start, (int, float)) and isinstance(sleep_duration, (int, float)):
        wake_timestamp = int(sleep_start + sleep_duration)
    if wake_timestamp is None:
        return None
    samples = _valid_numeric_offset_series(stress.get("timeOffsetBodyBatteryValues", {}))
    if not samples:
        return None
    absolute = [(int(stress_start + o), v) for o, v in samples]
    after = [(t, v) for t, v in absolute if wake_timestamp <= t <= wake_timestamp + 3 * 3600]
    if after:
        return round(after[0][1])
    closest = min(absolute, key=lambda row: abs(row[0] - wake_timestamp))
    if abs(closest[0] - wake_timestamp) <= 3 * 3600:
        return round(closest[1])
    return None


def build_live_recovery_snapshot(
    db: Session,
    user_id: int,
    *,
    lookback_days: int = 14,
    readiness_version: str = READINESS_VERSION_V4,
) -> Dict[str, Any]:
    """Assemble recovery payload identical to GET /garmin/recovery."""
    since = datetime.utcnow() - timedelta(days=lookback_days)
    daily_record = _latest_health_record(db, user_id, "dailies", since)
    sleep_record = _latest_health_record(db, user_id, "sleeps", since)
    stress_record = _latest_health_record(db, user_id, "stressDetails", since)
    hrv_record = _latest_health_record(db, user_id, "hrv", since)
    recent_activities = (
        db.query(GarminActivityData)
        .filter(
            GarminActivityData.user_id == user_id,
            GarminActivityData.summary_type.in_(["activities", "manuallyUpdatedActivities"]),
            GarminActivityData.start_time >= datetime.utcnow() - timedelta(hours=72),
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
            "score_status": "insufficient_data",
            "metrics": None,
            "message": "No Garmin health data found yet. Sync Garmin Connect or request a backfill.",
        }

    stress_values = _valid_stress_values(stress.get("timeOffsetStressLevelValues", {}))
    body_battery_series = _valid_numeric_offset_series(stress.get("timeOffsetBodyBatteryValues", {}))
    body_battery_values = [v for _, v in body_battery_series]
    hrv_values = _valid_numeric_values(hrv.get("hrvValues", {}))
    heart_rate_values = _valid_numeric_values(daily.get("timeOffsetHeartRateSamples", {}))

    sleep_duration_seconds = sleep.get("durationInSeconds")
    sleep_hours = round(sleep_duration_seconds / 3600, 1) if sleep_duration_seconds else None
    sleep_score = _sleep_score(sleep)
    avg_stress = round(sum(stress_values) / len(stress_values)) if stress_values else None
    body_battery_at_wake = _body_battery_at_wake(stress, sleep)
    body_battery_current = round(body_battery_values[-1]) if body_battery_values else None
    body_battery_current_at = None
    body_battery_current_age_hours = None
    stress_start = stress.get("startTimeInSeconds")
    if body_battery_series and isinstance(stress_start, (int, float)):
        last_offset, _ = body_battery_series[-1]
        body_battery_current_dt = datetime.utcfromtimestamp(int(stress_start + last_offset))
        body_battery_current_at = body_battery_current_dt.isoformat()
        body_battery_current_age_hours = max(
            0.0, (datetime.utcnow() - body_battery_current_dt).total_seconds() / 3600
        )

    stale_signals = []
    if body_battery_current is None:
        stale_signals.append("bodyBatteryCurrent_missing")
    elif body_battery_current_age_hours is not None and body_battery_current_age_hours > 6:
        stale_signals.append("bodyBatteryCurrent_stale")
    body_battery_for_score = (
        body_battery_current
        if not any(s.startswith("bodyBatteryCurrent_") for s in stale_signals)
        else None
    )

    hrv_overnight = (
        int(hrv.get("lastNightAvg"))
        if isinstance(hrv.get("lastNightAvg"), (int, float))
        else (round(sum(hrv_values) / len(hrv_values)) if hrv_values else None)
    )
    hrv_history = _hrv_history(db, user_id, since) if readiness_version == READINESS_VERSION_V4 else []
    hrv_trend = list(reversed(hrv_history)) if hrv_history else []

    if not stress_values:
        stale_signals.append("stress_missing")
    if not hrv_overnight:
        stale_signals.append("hrv_missing")
    if sleep_score is None and sleep_hours is None:
        stale_signals.append("sleep_missing")

    training_fatigue = compute_recent_fatigue(recent_activities)
    readiness = compute_readiness_score(
        sleep_score=sleep_score,
        sleep_hours=sleep_hours,
        avg_stress=avg_stress,
        body_battery=body_battery_for_score,
        hrv=hrv_overnight,
        hrv_history=hrv_history,
        recent_training_penalty=training_fatigue["penalty"],
        version=readiness_version,
    )
    score = readiness.score

    date_candidates = [p.get("calendarDate") for p in [sleep, daily, stress, hrv] if p.get("calendarDate")]
    calendar_date = date_candidates[0] if date_candidates else None

    score_inputs = {
        "sleepScore": sleep_score,
        "sleepHours": sleep_hours,
        "avgStress": avg_stress,
        "bodyBatteryCurrent": body_battery_for_score,
        "bodyBatteryCurrentAt": body_battery_current_at,
        "bodyBatteryCurrentAgeHours": round(body_battery_current_age_hours, 1) if body_battery_current_age_hours else None,
        "hrvOvernight": hrv_overnight,
        "hrvBaselineMs": readiness.hrv_baseline_ms,
        "hrvDeviationPct": readiness.hrv_deviation_pct,
        "recentTrainingPenalty": training_fatigue["penalty"],
    }
    score_confidence = "high"
    if stale_signals:
        score_confidence = "medium" if body_battery_for_score is not None else "low"
    if len(stale_signals) >= 3:
        score_confidence = "low"

    current_hr = round(heart_rate_values[-1]) if heart_rate_values else daily.get("averageHeartRateInBeatsPerMinute")

    return {
        "source": "live",
        "calendar_date": calendar_date,
        "score": score,
        "score_status": readiness.score_status,
        "recent_training": training_fatigue,
        "records": {
            "daily": daily_record.summary_id if daily_record else None,
            "sleep": sleep_record.summary_id if sleep_record else None,
            "stress": stress_record.summary_id if stress_record else None,
            "hrv": hrv_record.summary_id if hrv_record else None,
        },
        "score_model": {
            "version": readiness.version,
            "scale": "0-6",
            "confidence": score_confidence,
            "stale_signals": stale_signals,
            "inputs": score_inputs,
            "components": readiness.components,
            "caps_applied": readiness.caps_applied,
            "raw_score": readiness.raw_score,
            "notes": [
                "Health signals use sleep, stress, current Body Battery and HRV.",
                "Recent training reduces the score for 72h based on duration, activity type and HR intensity (% of personal max).",
                "HRV v4 uses a 14-night median baseline when enough history exists.",
            ],
        },
        "scoreConfidence": score_confidence,
        "staleSignals": stale_signals,
        "scoreInputs": score_inputs,
        "metrics": {
            "sleepScore": sleep_score,
            "sleepHours": sleep_hours,
            "deepSleepMin": _minutes(sleep.get("deepSleepDurationInSeconds")),
            "remMin": _minutes(sleep.get("remSleepInSeconds")),
            "lightMin": _minutes(sleep.get("lightSleepDurationInSeconds")),
            "awakeMin": _minutes(sleep.get("awakeDurationInSeconds")),
            "avgStress": avg_stress,
            "bodyBattery": body_battery_for_score,
            "bodyBatteryAtWake": body_battery_at_wake,
            "bodyBatteryCurrent": body_battery_current,
            "bodyBatteryCurrentAt": body_battery_current_at,
            "bodyBatteryScoreSource": "current" if body_battery_for_score is not None else None,
            "hrvOvernight": hrv_overnight,
            "hrvBaselineMs": readiness.hrv_baseline_ms,
            "hrvDeviationPct": readiness.hrv_deviation_pct,
            "restingHr": daily.get("restingHeartRateInBeatsPerMinute"),
            "currentHeartRate": current_hr,
            "hrvTrend": hrv_trend,
            "stressTrend": stress_values[-24:],
            "hrTrend": [round(v) for v in heart_rate_values[-60:]],
            "steps": daily.get("steps"),
            "activeKilocalories": daily.get("activeKilocalories"),
            "distanceMeters": daily.get("distanceInMeters"),
            "recentTrainingLoad": training_fatigue["load"],
            "recentTrainingPenalty": training_fatigue["penalty"],
            "recentTrainingLabel": training_fatigue["label"],
            "recentActivityCount48h": training_fatigue["recent_activity_count"],
            "recentTrainingSessions": training_fatigue["sessions"],
            "hardestRecentActivity": training_fatigue["hardest_activity"],
        },
    }
