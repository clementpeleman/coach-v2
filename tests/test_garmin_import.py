"""Tests for Garmin import helpers."""
from unittest.mock import MagicMock

from app.core.garmin_import import (
    activity_backfill_summary,
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


def test_pull_activity_history_direct_counts_rows():
    client = MagicMock()
    client.get_activities.return_value = [{"summaryId": "a1"}, {"summaryId": "a2"}]
    client.get_activity_details.return_value = [{"summaryId": "d1"}]

    result = pull_activity_history_direct(client, days=2)
    assert result["activities"] == 4
    assert result["activity_details"] == 2
    assert client.get_activities.call_count == 2
