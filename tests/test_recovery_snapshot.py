"""Tests for live recovery snapshot assembly."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.recovery_snapshot import _hrv_history, build_live_recovery_snapshot


def _hrv_record(last_night_avg: int, start_time: datetime):
    return SimpleNamespace(
        data={"lastNightAvg": last_night_avg, "hrvValues": {}},
        start_time=start_time,
    )


def test_hrv_history_returns_last_night_values():
    db = MagicMock()
    now = datetime.utcnow()
    records = [
        _hrv_record(55, now - timedelta(days=1)),
        _hrv_record(52, now - timedelta(days=2)),
        _hrv_record(50, now - timedelta(days=3)),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = records

    values = _hrv_history(db, user_id=1, since=now - timedelta(days=14), limit=14)
    assert values == [55, 52, 50]


def test_metrics_hrv_trend_uses_nightly_history(monkeypatch):
    db = MagicMock()
    now = datetime.utcnow()

    sleep = SimpleNamespace(
        summary_id="sleep-1",
        start_time=now,
        data='{"calendarDate":"2026-03-20","durationInSeconds":28800,"overallSleepScore":{"value":80}}',
    )
    stress = SimpleNamespace(
        summary_id="stress-1",
        start_time=now,
        data='{"calendarDate":"2026-03-20","startTimeInSeconds":1710000000,"timeOffsetStressLevelValues":{"0":40},"timeOffsetBodyBatteryValues":{"0":55}}',
    )
    hrv = SimpleNamespace(
        summary_id="hrv-1",
        start_time=now,
        data='{"calendarDate":"2026-03-20","lastNightAvg":58,"hrvValues":{"0":57,"1":59}}',
    )
    daily = SimpleNamespace(
        summary_id="daily-1",
        start_time=now,
        data='{"calendarDate":"2026-03-20","restingHeartRateInBeatsPerMinute":52}',
    )

    def latest_record(db_session, user_id, summary_type, since):
        return {
            "sleeps": sleep,
            "stressDetails": stress,
            "hrv": hrv,
            "dailies": daily,
        }.get(summary_type)

    hrv_records = [
        _hrv_record(58, now - timedelta(days=1)),
        _hrv_record(54, now - timedelta(days=2)),
        _hrv_record(51, now - timedelta(days=3)),
    ]

    monkeypatch.setattr("app.core.recovery_snapshot._latest_health_record", latest_record)
    monkeypatch.setattr(
        "app.core.recovery_snapshot._hrv_history",
        lambda db_session, user_id, since, limit=14: [58, 54, 51],
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    snapshot = build_live_recovery_snapshot(db, user_id=1, lookback_days=14, readiness_version="readiness_v4")
    assert snapshot["metrics"]["hrvTrend"] == [51, 54, 58]
