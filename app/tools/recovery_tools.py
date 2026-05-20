"""Recovery assessment tools — delegates to canonical readiness_v4 snapshot."""
from __future__ import annotations

from app.core.readiness import format_assessment_text
from app.core.recovery_snapshot import build_live_recovery_snapshot
from app.config import settings
from app.database.database import SessionLocal


def assess_recovery_status(user_id: int) -> str:
    """
    Assess user's recovery status using the same algorithm as GET /garmin/recovery.

    The score in the web app context is authoritative when chatting via /web/chat.
    """
    try:
        with SessionLocal() as db:
            snapshot = build_live_recovery_snapshot(
                db,
                user_id,
                lookback_days=14,
                readiness_version=settings.readiness_version,
            )
        return format_assessment_text(snapshot)
    except Exception as e:
        return f"Error: Could not assess recovery status: {str(e)}"


def get_recovery_metrics(user_id: int, date: str = None) -> str:
    """Get recovery metrics (same canonical snapshot as the web UI)."""
    try:
        with SessionLocal() as db:
            snapshot = build_live_recovery_snapshot(
                db,
                user_id,
                lookback_days=14,
                readiness_version=settings.readiness_version,
            )
        header = f"Recovery Metrics ({snapshot.get('calendar_date') or 'latest'}):\n\n"
        return header + format_assessment_text(snapshot)
    except Exception as e:
        return f"Error: Could not retrieve recovery metrics: {str(e)}"
