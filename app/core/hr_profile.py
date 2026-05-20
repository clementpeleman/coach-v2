"""Heart-rate profile resolution for fatigue and effort classification."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass
class HRProfile:
    effective_max: int
    source: str  # observed_p95 | garmin | age_estimate
    confidence: str  # high | medium | low


def _winsorize_max(values: list[int], cap: int = 210) -> Optional[int]:
    clean = sorted(v for v in values if v and 80 <= v <= cap)
    if not clean:
        return None
    if len(clean) >= 5:
        idx = int(round((len(clean) - 1) * 0.95))
        return int(clean[idx])
    return int(max(clean))


def resolve_hr_profile(
    activities: Iterable[Any],
    *,
    resting_hr: Optional[int] = None,
    age_years: Optional[int] = None,
) -> HRProfile:
    """Resolve effective max HR from recent activities and optional metadata."""
    max_hrs = [int(a.max_heart_rate) for a in activities if getattr(a, "max_heart_rate", None)]
    observed = _winsorize_max(max_hrs)
    if observed:
        return HRProfile(effective_max=observed, source="observed_p95", confidence="high" if len(max_hrs) >= 8 else "medium")

    if resting_hr and resting_hr > 0:
        estimate = min(210, resting_hr + 95)
        return HRProfile(effective_max=estimate, source="resting_offset", confidence="low")

    if age_years and 10 <= age_years <= 90:
        estimate = max(140, min(210, 220 - age_years))
        return HRProfile(effective_max=estimate, source="age_estimate", confidence="low")

    return HRProfile(effective_max=185, source="default", confidence="low")


def resolve_global_hr_profile(activities: Iterable[Any], *, resting_hr: Optional[int] = None) -> HRProfile:
    """Single profile across all sports for short-term fatigue."""
    return resolve_hr_profile(activities, resting_hr=resting_hr)


def hr_intensity_bonus(avg_hr: int, max_hr: int, effective_max: int) -> float:
    """Map session HR to additive intensity factor (replaces absolute 130/145/160 bpm)."""
    if effective_max <= 0:
        return 0.0
    avg_ratio = avg_hr / effective_max if avg_hr else 0.0
    max_ratio = max_hr / effective_max if max_hr else 0.0
    bonus = 0.0
    if avg_ratio >= 0.85:
        bonus += 0.45
    elif avg_ratio >= 0.78:
        bonus += 0.25
    elif avg_ratio >= 0.68:
        bonus += 0.10
    if max_ratio >= 0.92:
        bonus += 0.15
    return bonus


def is_hard_session(avg_hr: int, max_hr: int, effective_max: int, duration_min: float, hours_ago: float) -> bool:
    if hours_ago > 36 or duration_min < 40:
        return False
    if effective_max <= 0:
        return avg_hr >= 155 or max_hr >= 185
    return (avg_hr / effective_max) >= 0.78 or (max_hr / effective_max) >= 0.92


def hr_ratio(hr: int, effective_max: int) -> float:
    if not hr or effective_max <= 0:
        return 0.0
    return hr / effective_max


def classify_effort_from_hr(avg_hr: Optional[int], sport_max_hr: Optional[int], effective_max: Optional[int] = None) -> Optional[str]:
    """Return easy | endurance | threshold | vo2 from HR ratio."""
    emax = effective_max or sport_max_hr
    if not avg_hr or not emax:
        return None
    ratio = avg_hr / emax
    if ratio < 0.70:
        return "easy"
    if ratio < 0.80:
        return "endurance"
    if ratio < 0.90:
        return "threshold"
    return "vo2"
