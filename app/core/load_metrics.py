"""Unified training load ratio (acute vs chronic weekly volume)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional


ACUTE_DAYS = 7
CHRONIC_DAYS = 28
LOAD_LOW_THRESHOLD = 0.75
LOAD_HIGH_THRESHOLD = 1.25


@dataclass
class LoadMetrics:
    acute_hours: float
    chronic_weekly_hours: float
    load_ratio: Optional[float]
    label: str
    acute_days: int = ACUTE_DAYS
    chronic_days: int = CHRONIC_DAYS


def _activity_hours(activity: Any) -> float:
    seconds = getattr(activity, "duration", None) or 0
    return float(seconds) / 3600.0


def compute_load_metrics(
    activities: Iterable[Any],
    *,
    now: Optional[datetime] = None,
    acute_days: int = ACUTE_DAYS,
    chronic_days: int = CHRONIC_DAYS,
) -> LoadMetrics:
    """Acute = last `acute_days`; chronic = prior `chronic_days` averaged per week."""
    now = now or datetime.utcnow()
    current_start = now - timedelta(days=acute_days)
    baseline_start = current_start - timedelta(days=chronic_days)

    acute_hours = 0.0
    chronic_total = 0.0
    for activity in activities:
        start = getattr(activity, "start_time", None)
        if not start:
            continue
        hours = _activity_hours(activity)
        if start >= current_start:
            acute_hours += hours
        elif baseline_start <= start < current_start:
            chronic_total += hours

    chronic_weekly = chronic_total / 4.0 if chronic_total > 0 else 0.0
    ratio = round(acute_hours / chronic_weekly, 2) if chronic_weekly > 0 else None
    label = _load_label(ratio)
    return LoadMetrics(
        acute_hours=round(acute_hours, 2),
        chronic_weekly_hours=round(chronic_weekly, 2),
        load_ratio=ratio,
        label=label,
        acute_days=acute_days,
        chronic_days=chronic_days,
    )


def compute_load_metrics_for_sport(
    activities: Iterable[Any],
    sport: str,
    *,
    now: Optional[datetime] = None,
    sport_normalizer=None,
) -> LoadMetrics:
    """Filter activities to one sport then compute load metrics."""
    normalizer = sport_normalizer or (lambda a: getattr(a, "activity_type", "") or "")
    filtered = [a for a in activities if normalizer(a) == sport]
    return compute_load_metrics(filtered, now=now)


def _load_label(ratio: Optional[float]) -> str:
    if ratio is None:
        return "insufficient_data"
    if ratio < LOAD_LOW_THRESHOLD:
        return "low"
    if ratio > LOAD_HIGH_THRESHOLD:
        return "high"
    return "balanced"


def load_advice_nl(ratio: Optional[float]) -> str:
    if ratio is None:
        return "Nog beperkte historiek: focus op consistente rustige sessies."
    if ratio > LOAD_HIGH_THRESHOLD:
        return "Belasting stijgt sterk; plan extra herstel en beperk intensiteit."
    if ratio < LOAD_LOW_THRESHOLD:
        return "Belasting ligt laag; voeg eventueel 1 rustige sessie toe."
    return "Belasting is goed in balans; huidige structuur aanhouden."
