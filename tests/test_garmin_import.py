"""Tests for Garmin import helpers."""
from unittest.mock import MagicMock

from app.core.garmin_import import (
    activity_backfill_summary,
    build_import_log,
    build_import_message,
    migrate_garmin_data_between_users,
    pull_activity_history_direct,
    resolve_internal_user_for_garmin,
)


class FakeActivity:
    def __init__(self, user_id):
        self.user_id = user_id


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.committed = False

    def query(self, model):
        return FakeQuery(self.rows)

    def commit(self):
        self.committed = True


def test_migrate_garmin_data_between_users_updates_rows():
    rows = [FakeActivity(10), FakeActivity(10)]
    db = FakeSession(rows)
    result = migrate_garmin_data_between_users(db, 10, 20)
    assert result["activities"] >= 2
    assert all(row.user_id == 20 for row in rows)
    assert db.committed is True


def test_activity_backfill_summary_detects_duplicate():
    summary = activity_backfill_summary(
        {
            "activity": {
                "activities": [
                    {"status": "duplicate", "notes": ["already processed"]},
                ]
            }
        }
    )
    assert summary["all_duplicate"] is True
    assert summary["duplicate_count"] == 1


def test_build_import_message_for_duplicate_backfill():
    message = build_import_message(
        activity_sessions=1,
        backfill_summary={"all_duplicate": True, "requested_count": 0, "skipped_permissions": False},
        direct_pull=None,
        migration=None,
        permissions_assumed=False,
        capabilities={"ready_for_initial_import": True, "missing_required_for_initial_import": []},
    )
    assert "duplicate backfill" in message


def test_pull_activity_history_direct_is_unsupported():
    result = pull_activity_history_direct(MagicMock(), days=30)
    assert result["status"] == "unsupported"
    assert result["activities"] == 0


def test_build_import_log_includes_backfill_and_replay():
    log = build_import_log(
        user_id=42,
        garmin_user_id="garmin-abc",
        permissions=["ACTIVITY_EXPORT", "HISTORICAL_DATA_EXPORT"],
        permissions_assumed=False,
        capabilities={"ready_for_initial_import": True, "missing_required_for_initial_import": []},
        replay_result={"attempted": 4, "replayed": 3, "stored_items": 12, "still_failed": 1, "event_ids": [372, 373]},
        backfill_result={
            "activity": {
                "activities": [{
                    "status": "duplicate",
                    "notes": ["Garmin reported this range was already processed."],
                    "requested_start": "2026-04-21T00:00:00",
                    "end": "2026-05-21T00:00:00",
                }],
            },
            "health": {"dailies": [{"type": "dailies", "status": "rate_limited", "notes": ["rate limit"]}]},
            "skipped": {},
        },
        backfill_summary={"all_duplicate": True, "requested_count": 0, "skipped_permissions": False},
        import_summary={"activity_sessions": 1, "health_records": 228},
        webhook_status_counts={"health:partial": 4, "activity:processed": 8},
    )
    steps = [entry["step"] for entry in log]
    assert "start" in steps
    assert "replay" in steps
    assert "backfill" in steps
    assert "database" in steps
    assert any("duplicate" in entry["message"].lower() for entry in log)
    token = MagicMock(user_id=42)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [token, None]
    assert resolve_internal_user_for_garmin(db, "garmin-123") == 42
