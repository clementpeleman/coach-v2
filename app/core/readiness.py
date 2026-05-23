"""Canonical readiness (recovery) scoring — v3 legacy + v4 personalized."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.hr_profile import (
    HRProfile,
    hr_intensity_bonus,
    is_hard_session,
    resolve_global_hr_profile,
)


READINESS_VERSION_V3 = "current_readiness_v3"
READINESS_VERSION_V4 = "readiness_v4"

STRENGTH_ACTIVITY_KEYWORDS = ("STRENGTH", "HIIT", "GYM", "WEIGHT", "KRAFT", "CROSSFIT")
FATIGUE_DECAY_HOURS = 72
HARD_SESSION_FLOOR = 1.1
HARD_SESSION_FLOOR_START_H = 36


def _is_strength_activity(activity_type: str) -> bool:
    upper = (activity_type or "").upper()
    return any(keyword in upper for keyword in STRENGTH_ACTIVITY_KEYWORDS)


def _hard_session_floor(hours_ago: float) -> float:
    """Linear decay of hard-session floor from 36h (1.1) to 72h (0)."""
    if hours_ago <= HARD_SESSION_FLOOR_START_H:
        return HARD_SESSION_FLOOR
    if hours_ago >= FATIGUE_DECAY_HOURS:
        return 0.0
    span = FATIGUE_DECAY_HOURS - HARD_SESSION_FLOOR_START_H
    return HARD_SESSION_FLOOR * max(0.0, (FATIGUE_DECAY_HOURS - hours_ago) / span)


@dataclass
class ReadinessResult:
    score: Optional[int]
    score_status: str  # ready | insufficient_data
    version: str
    raw_score: float
    components: Dict[str, float] = field(default_factory=dict)
    caps_applied: List[str] = field(default_factory=list)
    penalty: float = 0.0
    hrv_baseline_ms: Optional[float] = None
    hrv_deviation_pct: Optional[float] = None


def compute_recent_fatigue(activities: list[Any], hr_profile: Optional[HRProfile] = None) -> Dict:
    """Estimate short-term fatigue from recent sessions (typically last 72h)."""
    now = datetime.utcnow()
    profile = hr_profile or resolve_global_hr_profile(activities)
    effective_max = profile.effective_max

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
        is_strength = _is_strength_activity(activity_type)

        intensity = 1.0 + hr_intensity_bonus(int(avg_hr), int(max_hr), effective_max)
        if "RUN" in activity_type:
            intensity += 0.10
        if is_strength:
            # Strength/HIIT often has low average HR but still creates meaningful load.
            intensity = max(intensity, 1.15 + min(duration_min, 90) / 120)

        decay = max(0.35, 1 - (hours_ago / FATIGUE_DECAY_HOURS))
        session_load = duration_min * intensity * decay
        if is_strength:
            strength_floor = duration_min * 0.65 * decay
            session_load = max(session_load, strength_floor)
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
            "hr_profile_max": effective_max,
            "load": round(session_load, 1),
            "strength": is_strength,
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
        if is_hard_session(
            session["average_heart_rate"] or 0,
            session["max_heart_rate"] or 0,
            effective_max,
            session["duration_minutes"],
            session["hours_ago"],
        ):
            penalty = max(penalty, _hard_session_floor(session["hours_ago"]))
        elif session.get("strength") and session["hours_ago"] <= FATIGUE_DECAY_HOURS:
            strength_penalty = min(0.9, 0.35 + session["duration_minutes"] / 90)
            strength_penalty *= max(0.0, 1 - (session["hours_ago"] / FATIGUE_DECAY_HOURS))
            penalty = max(penalty, round(strength_penalty, 2))

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
        "hr_profile": {"effective_max": effective_max, "source": profile.source},
    }


def _hrv_term_v4(hrv_overnight: Optional[int], hrv_history: List[int]) -> tuple[float, Optional[float], Optional[float], bool]:
    """Return (score_delta, baseline_ms, deviation_pct, insufficient)."""
    if hrv_overnight is None:
        return 0.0, None, None, True

    clean = [int(v) for v in hrv_history if isinstance(v, (int, float)) and v > 0]
    if len(clean) < 7:
        # Fallback stabilizer (weaker than old v3)
        return (hrv_overnight - 45) / 50, None, None, True

    baseline = float(statistics.median(clean))
    denom = max(baseline * 0.15, 8.0)
    deviation = (hrv_overnight - baseline) / denom
    delta = max(-1.0, min(1.0, deviation * 0.4))
    pct = ((hrv_overnight - baseline) / baseline * 100) if baseline else None
    return delta, baseline, round(pct, 1) if pct is not None else None, False


def compute_readiness_score(
    *,
    sleep_score: Optional[int] = None,
    sleep_hours: Optional[float] = None,
    avg_stress: Optional[int] = None,
    body_battery: Optional[int] = None,
    hrv: Optional[int] = None,
    hrv_history: Optional[List[int]] = None,
    recent_training_penalty: float = 0.0,
    version: str = READINESS_VERSION_V4,
) -> ReadinessResult:
    """Compute 0–6 readiness; returns null score when insufficient inputs."""
    components: Dict[str, float] = {}
    caps: List[str] = []
    score = 3.0

    if sleep_score is not None:
        term = (sleep_score - 70) / 15
        components["sleep_score"] = term
        score += term
    elif sleep_hours is not None:
        term = (sleep_hours - 7) / 1.5
        components["sleep_hours"] = term
        score += term

    if avg_stress is not None:
        term = (45 - avg_stress) / 20
        components["stress"] = term
        score += term

    if body_battery is not None:
        term = (body_battery - 50) / 25
        components["body_battery"] = term
        score += term

    hrv_baseline = None
    hrv_deviation_pct = None
    if hrv is not None:
        if version == READINESS_VERSION_V4:
            term, hrv_baseline, hrv_deviation_pct, hrv_insufficient = _hrv_term_v4(hrv, hrv_history or [])
            components["hrv"] = term
            if hrv_insufficient and hrv_baseline is None:
                components["hrv_insufficient"] = 1.0
            score += term
        else:
            term = (hrv - 45) / 35
            components["hrv"] = term
            score += term

    components["training_penalty"] = -recent_training_penalty
    score -= recent_training_penalty
    raw = score

    has_signal = any([
        sleep_score is not None,
        sleep_hours is not None,
        avg_stress is not None,
        body_battery is not None,
        hrv is not None,
    ])
    if not has_signal:
        return ReadinessResult(
            score=None,
            score_status="insufficient_data",
            version=version,
            raw_score=raw,
            components=components,
            caps_applied=caps,
            penalty=recent_training_penalty,
            hrv_baseline_ms=hrv_baseline,
            hrv_deviation_pct=hrv_deviation_pct,
        )

    rounded = max(0, min(6, int(round(score))))

    if body_battery is not None:
        if body_battery <= 15:
            rounded = min(rounded, 2)
            caps.append("body_battery_<=15")
        elif body_battery <= 25:
            rounded = min(rounded, 3)
            caps.append("body_battery_<=25")
        elif body_battery <= 35 and recent_training_penalty >= 0.8:
            rounded = min(rounded, 3)
            caps.append("body_battery_<=35_with_load")

    if recent_training_penalty >= 1.1:
        rounded = min(rounded, 3)
        caps.append("recent_hard_training")
    if recent_training_penalty >= 1.1 and body_battery is not None and body_battery <= 25:
        rounded = min(rounded, 2)
        caps.append("hard_training_low_battery")

    # Extra cap when BB missing but meaningful load
    if body_battery is None and recent_training_penalty >= 0.4:
        has_hrv_signal = hrv is not None and (hrv_baseline is not None or version == READINESS_VERSION_V3)
        has_sleep = sleep_score is not None or sleep_hours is not None
        if not (has_hrv_signal and has_sleep):
            rounded = min(rounded, 3)
            caps.append("no_bb_with_load")

    return ReadinessResult(
        score=rounded,
        score_status="ready",
        version=version,
        raw_score=raw,
        components=components,
        caps_applied=caps,
        penalty=recent_training_penalty,
        hrv_baseline_ms=hrv_baseline,
        hrv_deviation_pct=hrv_deviation_pct,
    )


def workout_type_from_readiness(
    score: int,
    metrics: Dict[str, Any],
    *,
    workout_patterns: Optional[Dict[str, Any]] = None,
) -> str:
    """Map readiness score to workout type (SPRINT under strict conditions)."""
    body_battery = metrics.get("bodyBatteryCurrent") or metrics.get("body_battery")
    penalty = metrics.get("recentTrainingPenalty") or metrics.get("recent_training_penalty") or 0
    if body_battery is not None and body_battery <= 25:
        return "HERSTEL"
    if penalty >= 1.1:
        return "HERSTEL"
    if score <= 2:
        return "HERSTEL"
    if score == 3:
        return "DUUR"
    if score == 4:
        return "THRESHOLD"
    if score >= 6 and penalty < 0.4:
        patterns = workout_patterns or {}
        by_type = patterns.get("by_type") or {}
        if by_type.get("SPRINT", {}).get("sessions", 0) > 0:
            return "SPRINT"
    return "VO2MAX"


def format_assessment_text(snapshot: Dict[str, Any]) -> str:
    """Human-readable assessment for agent tools."""
    score = snapshot.get("score")
    metrics = snapshot.get("metrics") or {}
    model = snapshot.get("score_model") or {}
    version = model.get("version", READINESS_VERSION_V4)
    lines = [f"Recovery Assessment ({version}):", ""]

    if score is None:
        lines.append(snapshot.get("message") or "Onvoldoende Garmin-data voor een score.")
        return "\n".join(lines)

    lines.append(f"Recovery Score: {score}/6")
    if metrics.get("sleepScore") is not None:
        lines.append(f"Sleep score: {metrics['sleepScore']}")
    if metrics.get("sleepHours") is not None:
        lines.append(f"Sleep: {metrics['sleepHours']} uur")
    if metrics.get("hrvOvernight") is not None:
        hrv_line = f"HRV overnight: {metrics['hrvOvernight']} ms"
        if metrics.get("hrvBaselineMs") is not None:
            hrv_line += f" (baseline {metrics['hrvBaselineMs']} ms"
            if metrics.get("hrvDeviationPct") is not None:
                hrv_line += f", {metrics['hrvDeviationPct']:+.0f}%"
            hrv_line += ")"
        lines.append(hrv_line)
    if metrics.get("bodyBatteryCurrent") is not None:
        lines.append(f"Body Battery: {metrics['bodyBatteryCurrent']}%")
    if metrics.get("recentTrainingPenalty") is not None:
        lines.append(f"Recent training penalty: {metrics['recentTrainingPenalty']}")

    lines.append("")
    if score >= 5:
        lines.append("Status: goed hersteld — intensieve training mogelijk")
    elif score >= 3:
        lines.append("Status: matig hersteld — gematigde training")
    else:
        lines.append("Status: beperkt hersteld — rust of lichte sessie")
    return "\n".join(lines)
