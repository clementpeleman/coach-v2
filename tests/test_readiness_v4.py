"""Unit tests for readiness_v4 algorithms."""
from types import SimpleNamespace
from datetime import datetime, timedelta

from app.core.readiness import (
    HARD_SESSION_FLOOR,
    _hard_session_floor,
    _is_strength_activity,
    compute_readiness_score,
    compute_recent_fatigue,
    workout_type_from_readiness,
)
from app.core.hr_profile import resolve_hr_profile, hr_intensity_bonus
from app.core.load_metrics import compute_load_metrics, LOAD_LOW_THRESHOLD, LOAD_HIGH_THRESHOLD
from app.tools.training_recommendation_engine import build_recommendation


def _activity(duration_min, avg_hr, max_hr=0, hours_ago=12, activity_type="RUNNING", name="Run"):
    return SimpleNamespace(
        activity_id=1,
        activity_name=name,
        activity_type=activity_type,
        start_time=datetime.utcnow() - timedelta(hours=hours_ago),
        duration=duration_min * 60,
        average_heart_rate=avg_hr,
        max_heart_rate=max_hr or avg_hr + 10,
    )


def test_hrv_baseline_improves_score_when_above_baseline():
    result = compute_readiness_score(
        sleep_score=75,
        avg_stress=40,
        body_battery=70,
        hrv=60,
        hrv_history=[50, 52, 51, 53, 50, 52, 54, 51, 52, 50],
        recent_training_penalty=0,
        version="readiness_v4",
    )
    assert result.score is not None
    assert result.hrv_baseline_ms == 51.5 or result.hrv_baseline_ms == 52


def test_fatigue_uses_percent_max_not_absolute_160():
    profile = resolve_hr_profile([_activity(60, 150, 165)])
    bonus_young = hr_intensity_bonus(150, 165, profile.effective_max)
    profile_old = resolve_hr_profile([_activity(60, 150, 165)], age_years=55)
    bonus_old = hr_intensity_bonus(150, 165, profile_old.effective_max)
    assert bonus_young == bonus_old


def test_hard_session_penalty_with_high_ratio():
    activities = [_activity(50, 170, 190, hours_ago=10)]
    fatigue = compute_recent_fatigue(activities)
    assert fatigue["penalty"] >= 0.4


def test_workout_type_sprint_only_with_pattern():
    assert workout_type_from_readiness(
        6,
        {"recentTrainingPenalty": 0.2},
        workout_patterns={"by_type": {"SPRINT": {"sessions": 2}}},
    ) == "SPRINT"
    assert workout_type_from_readiness(6, {"recentTrainingPenalty": 0.2}, workout_patterns={}) == "VO2MAX"


def test_load_ratio_thresholds():
    now = datetime.utcnow()
    activities = []
    for i in range(4):
        activities.append(SimpleNamespace(
            start_time=now - timedelta(days=i + 1),
            duration=3600,
        ))
    for i in range(4):
        activities.append(SimpleNamespace(
            start_time=now - timedelta(days=10 + i),
            duration=1800,
        ))
    metrics = compute_load_metrics(activities, now=now)
    assert metrics.load_ratio is not None
    assert LOAD_LOW_THRESHOLD == 0.75
    assert LOAD_HIGH_THRESHOLD == 1.25


def test_strength_training_contributes_meaningful_load():
    fatigue = compute_recent_fatigue([_activity(45, 95, 120, hours_ago=8, activity_type="STRENGTH_TRAINING", name="Gym")])
    assert fatigue["load"] >= 20
    assert fatigue["penalty"] >= 0.35
    assert fatigue["sessions"][0]["strength"] is True


def test_hard_session_penalty_decays_after_36h():
    assert _hard_session_floor(12) == HARD_SESSION_FLOOR
    assert _hard_session_floor(36) == HARD_SESSION_FLOOR
    assert _hard_session_floor(54) < HARD_SESSION_FLOOR
    assert _hard_session_floor(72) == 0.0


def test_strength_activity_detection():
    assert _is_strength_activity("STRENGTH_TRAINING")
    assert _is_strength_activity("HIIT")
    assert not _is_strength_activity("RUNNING")


def test_build_recommendation_downshifts_after_strength_yesterday():
    recovery = {
        "score": 4,
        "metrics": {"recentTrainingPenalty": 0.5},
        "recent_training": {
            "sessions": [{
                "activity_name": "Upper body",
                "activity_type": "STRENGTH_TRAINING",
                "hours_ago": 20,
                "load": 30,
            }],
        },
    }
    training_profile = {
        "sport_baselines": {"RUNNING": {"load_ratio": 1.0}},
        "workout_patterns": {"weekly_pattern": {}, "by_type": {}, "classified_activities": []},
        "dominant_sport": "RUNNING",
    }
    draft = build_recommendation(user_id=1, recovery=recovery, training_profile=training_profile)
    assert draft["type"] == "HERSTEL"
    assert any("kracht" in line.lower() or "Gisteren" in line for line in draft["reasoning"])


def test_build_recommendation_respects_high_load_ratio():
    recovery = {"score": 5, "metrics": {"recentTrainingPenalty": 0.0}}
    training_profile = {
        "sport_baselines": {"RUNNING": {"load_ratio": 1.35}},
        "workout_patterns": {"weekly_pattern": {}, "by_type": {"VO2MAX": {"sessions": 3}}, "classified_activities": []},
        "dominant_sport": "RUNNING",
    }
    draft = build_recommendation(user_id=1, recovery=recovery, training_profile=training_profile)
    assert draft["type"] in {"THRESHOLD", "DUUR", "HERSTEL"}
    assert any("Load ratio" in line for line in draft["reasoning"])
