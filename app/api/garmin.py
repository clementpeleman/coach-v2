"""Garmin OAuth2 and webhook API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
import requests
import time
import json
import re
from datetime import datetime, timedelta

from app.config import settings
from app.database.database import get_db
from app.tools.garmin_oauth import GarminOAuthService
from app.tools.garmin_client import GarminAPIClient
from app.database.models import GarminActivityData, GarminHealthData, GarminToken, OAuthSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/garmin", tags=["garmin"])
MIN_START_TIME_PATTERN = re.compile(r"before min start time of ([0-9T:\.\-]+Z)")


def resolve_user_id(user_id: Optional[int], telegram_user_id: Optional[int]) -> int:
    """Resolve internal user id while supporting legacy query parameter names."""
    resolved_user_id = user_id if user_id is not None else telegram_user_id
    if resolved_user_id is None:
        raise HTTPException(status_code=422, detail="user_id is required")
    return resolved_user_id


def summarize_activities(activities: list[GarminActivityData]) -> Dict:
    """Create aggregate metrics from Garmin activity rows."""
    total_distance_m = sum((activity.distance or 0.0) for activity in activities)
    total_duration_s = sum((activity.duration or 0) for activity in activities)
    hr_values = [activity.average_heart_rate for activity in activities if activity.average_heart_rate]
    max_hr_values = [activity.max_heart_rate for activity in activities if activity.max_heart_rate]
    longest_session_seconds = max((activity.duration or 0) for activity in activities) if activities else 0

    running_count = 0
    cycling_count = 0
    running_hr_values = []
    cycling_hr_values = []
    for activity in activities:
        activity_type = (activity.activity_type or "").upper()
        if "RUN" in activity_type:
            running_count += 1
            if activity.average_heart_rate:
                running_hr_values.append(activity.average_heart_rate)
        if "CYCLE" in activity_type or "BIKE" in activity_type:
            cycling_count += 1
            if activity.average_heart_rate:
                cycling_hr_values.append(activity.average_heart_rate)

    return {
        "sessions": len(activities),
        "distance_meters": round(total_distance_m, 2),
        "distance_km": round(total_distance_m / 1000, 2),
        "duration_seconds": int(total_duration_s),
        "duration_hours": round(total_duration_s / 3600, 2),
        "longest_session_minutes": round(longest_session_seconds / 60, 1) if longest_session_seconds else 0.0,
        "average_heart_rate": round(sum(hr_values) / len(hr_values), 1) if hr_values else None,
        "max_heart_rate": max(max_hr_values) if max_hr_values else None,
        "running_sessions": running_count,
        "cycling_sessions": cycling_count,
        "running_average_heart_rate": round(sum(running_hr_values) / len(running_hr_values), 1) if running_hr_values else None,
        "cycling_average_heart_rate": round(sum(cycling_hr_values) / len(cycling_hr_values), 1) if cycling_hr_values else None,
    }


def parse_min_start_time_from_error(error_message: str) -> Optional[datetime]:
    """Extract Garmin minimum backfill start time from API error text."""
    match = MIN_START_TIME_PATTERN.search(error_message)
    if not match:
        return None

    iso_value = match.group(1).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        return None


def request_activity_backfill_with_fallback(
    client: GarminAPIClient,
    start: datetime,
    end: datetime,
) -> Dict:
    """Request activity backfill and auto-adjust when Garmin rejects old start date."""
    result = {
        "requested_start": start.isoformat(),
        "effective_start": start.isoformat(),
        "end": end.isoformat(),
        "status": "requested",
        "notes": [],
    }

    try:
        client.backfill_activities(start, end)
        return result
    except Exception as exc:
        error_text = str(exc)

        if "duplicate backfill processed" in error_text:
            result["status"] = "duplicate"
            result["notes"].append("Garmin reported this range was already processed.")
            return result

        min_start = parse_min_start_time_from_error(error_text)
        if not min_start:
            raise

        adjusted_start = max(start, min_start + timedelta(seconds=1))
        if adjusted_start >= end:
            result["status"] = "skipped"
            result["effective_start"] = adjusted_start.isoformat()
            result["notes"].append("Requested window is older than Garmin's allowed minimum start time.")
            return result

        result["status"] = "requested_with_adjusted_start"
        result["effective_start"] = adjusted_start.isoformat()
        result["notes"].append("Adjusted start date to Garmin minimum allowed backfill timestamp.")

        try:
            client.backfill_activities(adjusted_start, end)
            return result
        except Exception as second_exc:
            second_error_text = str(second_exc)
            if "duplicate backfill processed" in second_error_text:
                result["status"] = "duplicate"
                result["notes"].append("Garmin reported this adjusted range was already processed.")
                return result
            raise


def build_weekly_activity_trend(activities: list[GarminActivityData]) -> list[Dict]:
    """Build weekly aggregated trend data for a list of activities."""
    weekly: Dict[str, Dict] = {}

    for activity in activities:
        if not activity.start_time:
            continue

        week_start_date = (activity.start_time - timedelta(days=activity.start_time.weekday())).date()
        week_key = week_start_date.isoformat()
        if week_key not in weekly:
            weekly[week_key] = {
                "week_start": week_key,
                "sessions": 0,
                "distance_meters": 0.0,
                "duration_seconds": 0,
                "heart_rates": [],
            }

        weekly[week_key]["sessions"] += 1
        weekly[week_key]["distance_meters"] += activity.distance or 0.0
        weekly[week_key]["duration_seconds"] += activity.duration or 0
        if activity.average_heart_rate:
            weekly[week_key]["heart_rates"].append(activity.average_heart_rate)

    trend = []
    for week_key in sorted(weekly.keys()):
        item = weekly[week_key]
        heart_rates = item["heart_rates"]
        trend.append(
            {
                "week_start": week_key,
                "sessions": item["sessions"],
                "distance_km": round(item["distance_meters"] / 1000, 2),
                "duration_hours": round(item["duration_seconds"] / 3600, 2),
                "average_heart_rate": round(sum(heart_rates) / len(heart_rates), 1) if heart_rates else None,
            }
        )

    return trend


def compute_percent_change(current: float, baseline: float) -> Optional[float]:
    """Compute percentage change between current and baseline values."""
    if baseline == 0:
        return None
    return round(((current - baseline) / baseline) * 100, 1)


def _load_health_payload(record: Optional[GarminHealthData]) -> Dict:
    if not record:
        return {}
    if isinstance(record.data, str):
        try:
            return json.loads(record.data)
        except json.JSONDecodeError:
            return {}
    return record.data or {}


def _latest_health_record(
    db: Session,
    user_id: int,
    summary_type: str,
    since: datetime,
) -> Optional[GarminHealthData]:
    return db.query(GarminHealthData).filter(
        GarminHealthData.user_id == user_id,
        GarminHealthData.summary_type == summary_type,
        GarminHealthData.start_time >= since,
    ).order_by(GarminHealthData.start_time.desc()).first()


def _sleep_score(sleep: Dict) -> Optional[int]:
    score = (
        sleep.get("overallSleepScore", {}).get("value")
        or sleep.get("sleepScores", {}).get("overall", {}).get("value")
    )
    return int(score) if isinstance(score, (int, float)) else None


def _minutes(value_seconds: Optional[int]) -> int:
    return int((value_seconds or 0) / 60)


def _valid_numeric_values(values: Dict) -> list[float]:
    return [
        float(value)
        for value in values.values()
        if isinstance(value, (int, float)) and value >= 0
    ]


def _valid_stress_values(values: Dict) -> list[int]:
    return [
        int(value)
        for value in values.values()
        if isinstance(value, int) and value > 0
    ]


def _recovery_score(
    sleep_score: Optional[int],
    sleep_hours: Optional[float],
    avg_stress: Optional[int],
    body_battery: Optional[int],
    hrv: Optional[int],
) -> int:
    score = 3.0

    if sleep_score is not None:
        score += (sleep_score - 70) / 15
    elif sleep_hours is not None:
        score += (sleep_hours - 7) / 1.5

    if avg_stress is not None:
        score += (45 - avg_stress) / 20

    if body_battery is not None:
        score += (body_battery - 50) / 25

    if hrv is not None:
        # Without a personal baseline we only apply a small stabilising signal.
        score += (hrv - 45) / 35

    return max(0, min(6, int(round(score))))


def build_weekly_summary(
    current_week: Dict,
    baseline_weekly: Dict,
    load_ratio: Optional[float],
    hr_delta: Optional[float],
) -> str:
    """Generate a concise Dutch weekly coaching summary."""
    volume_delta = compute_percent_change(current_week["duration_hours"], baseline_weekly["duration_hours"])
    distance_delta = compute_percent_change(current_week["distance_km"], baseline_weekly["distance_km"])

    summary_parts = [
        (
            f"Deze week: {current_week['sessions']} sessies "
            f"({current_week['running_sessions']} run, {current_week['cycling_sessions']} fiets), "
            f"{current_week['duration_hours']}u en {current_week['distance_km']} km."
        )
    ]

    if volume_delta is not None:
        summary_parts.append(f"Volume vs 4-weeks gemiddeld: {volume_delta:+.1f}%.")
    if distance_delta is not None:
        summary_parts.append(f"Afstand vs 4-weeks gemiddeld: {distance_delta:+.1f}%.")
    if hr_delta is not None:
        summary_parts.append(f"Gemiddelde hartslag trend: {hr_delta:+.1f} bpm.")

    if load_ratio is None:
        advice = "Nog beperkte historiek: focus op consistente rustige sessies."
    elif load_ratio > 1.25:
        advice = "Belasting stijgt sterk; plan extra herstel en beperk intensiteit."
    elif load_ratio < 0.75:
        advice = "Belasting ligt laag; voeg eventueel 1 rustige sessie toe."
    else:
        advice = "Belasting is goed in balans; huidige structuur aanhouden."
    summary_parts.append(f"Advies: {advice}")

    return " ".join(summary_parts)


@router.get("/auth/start")
async def start_oauth(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    Start OAuth2 PKCE flow for Garmin authentication.

    Returns the authorization URL that the user should visit.
    """
    logger.info("[OAuth Start] V3 code is running.")
    try:
        oauth_service = GarminOAuthService()

        # Use the configured redirect URI
        redirect_uri = settings.garmin_redirect_uri
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="GARMIN_REDIRECT_URI not configured")

        # Clean up old sessions (e.g., older than 10 minutes)
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        deleted_count = db.query(OAuthSession).filter(OAuthSession.created_at < ten_minutes_ago).delete()
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old OAuth sessions.")
        db.commit()

        # Generate authorization URL
        auth_url, code_verifier, state = oauth_service.get_authorization_url(redirect_uri)

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        logger.info(f"[OAuth Start] Generated state: {state} for user: {resolved_user_id}")

        # Store session data in the database
        new_session = OAuthSession(
            state=state,
            code_verifier=code_verifier,
            user_id=resolved_user_id
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"[OAuth Start] Successfully saved session to DB for state: {state}")

        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "Visit the authorization_url to grant access"
        }

    except Exception as e:
        logger.error(f"OAuth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    db: Session = Depends(get_db)
):
    """
    OAuth2 callback endpoint. Garmin redirects here after user authorization.

    Exchanges authorization code for access token and stores it.
    """
    callback_time = datetime.utcnow()
    logger.info(f"[OAuth Callback] Received at {callback_time.isoformat()} with state: {state}")
    try:
        # Add a small delay to mitigate race conditions
        time.sleep(3)

        # Retrieve session data from database
        logger.info("[OAuth Callback] Querying database for state...")
        session = db.query(OAuthSession).filter(OAuthSession.state == state).first()

        if session:
            logger.info(f"[OAuth Callback] Found session in DB created at {session.created_at.isoformat()} for state: {state}")
        else:
            logger.error(f"[OAuth Callback] Session NOT FOUND in DB for state: {state}")
            all_sessions = db.query(OAuthSession).all()
            logger.error(f"Current sessions in DB: {[s.state for s in all_sessions]}")


        if not session:
            raise HTTPException(status_code=400, detail="Invalid state parameter or session expired")

        # Retrieve data and delete session
        code_verifier = session.code_verifier
        user_id = session.user_id
        db.delete(session)
        db.commit()

        # Get redirect_uri from settings
        redirect_uri = settings.garmin_redirect_uri
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="GARMIN_REDIRECT_URI not configured")

        # Exchange code for token
        oauth_service = GarminOAuthService()
        token_data = oauth_service.exchange_code_for_token(
            authorization_code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri
        )

        # Store tokens in database
        garmin_token = oauth_service.store_tokens(db, user_id, token_data)

        # Get user permissions
        access_token = token_data['access_token']
        permissions = oauth_service.get_user_permissions(access_token)

        # Kick off an initial historical backfill attempt after connect.
        try:
            client = GarminAPIClient(db, user_id)
            backfill_end = datetime.utcnow()
            backfill_start = backfill_end - timedelta(days=120)
            client.backfill_dailies(backfill_start, backfill_end)
            backfill_result = request_activity_backfill_with_fallback(
                client=client,
                start=backfill_start,
                end=backfill_end,
            )
            for health_type in ["sleeps", "stressDetails", "hrv"]:
                client.backfill_health_type(health_type, backfill_start, backfill_end)
            logger.info(f"Initial activity backfill requested after OAuth: {backfill_result}")
        except Exception as backfill_exc:
            logger.warning(f"Initial activity backfill after OAuth failed: {backfill_exc}")

        # Redirect the user back to the web app after successful OAuth.
        from fastapi.responses import HTMLResponse
        base_webapp_url = settings.webapp_url.rstrip("/")
        redirect_url = f"{base_webapp_url}/?garmin_connected=1&user_id={user_id}"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Garmin verbonden</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="2;url={redirect_url}">
</head>
<body style="font-family: Arial, sans-serif; padding: 24px;">
  <h1>Succesvol verbonden!</h1>
  <p>Je Garmin account is gekoppeld. Je wordt automatisch teruggestuurd naar de app.</p>
  <p><a href="{redirect_url}">Klik hier als je niet automatisch wordt doorgestuurd</a></p>
  <script>
    try {{
      localStorage.setItem("sportsHubUserId", "{user_id}");
    }} catch (err) {{}}
    setTimeout(function () {{
      window.location.href = "{redirect_url}";
    }}, 1200);
  </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/status")
async def check_auth_status(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check if user has valid Garmin authentication."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        oauth_service = GarminOAuthService()

        try:
            access_token = oauth_service.get_valid_access_token(db, resolved_user_id)
        except Exception as decrypt_err:
            logger.warning(f"Token decryption failed for user {resolved_user_id}, tokens may need re-auth: {decrypt_err}")
            return {
                "authenticated": False,
                "message": "Token expired or corrupted. Please reconnect Garmin."
            }

        if not access_token:
            return {
                "authenticated": False,
                "message": "No Garmin connection found"
            }

        # Get user permissions
        permissions = oauth_service.get_user_permissions(access_token)

        # Get token info
        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == resolved_user_id
        ).first()

        return {
            "authenticated": True,
            "garmin_user_id": garmin_token.garmin_user_id,
            "permissions": permissions,
            "expires_at": garmin_token.expires_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auth/disconnect")
async def disconnect_garmin(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Disconnect Garmin account and delete stored tokens."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        oauth_service = GarminOAuthService()

        # Get current access token
        access_token = oauth_service.get_valid_access_token(db, resolved_user_id)

        if access_token:
            # Deregister from Garmin API
            try:
                oauth_service.deregister_user(access_token)
            except Exception as e:
                logger.warning(f"Garmin deregistration failed: {e}")

        # Delete local tokens
        oauth_service.delete_tokens(db, resolved_user_id)

        return {
            "status": "success",
            "message": "Successfully disconnected from Garmin"
        }

    except Exception as e:
        logger.error(f"Disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DATA FETCHING ENDPOINTS
# ============================================================================

@router.get("/data/recent")
async def get_recent_data(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(7, description="Number of days to fetch", ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Fetch recent health and activity data for a user.

    This manually fetches data from Garmin API instead of waiting for webhooks.
    """
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)
        data = client.get_recent_data(days=days)

        return {
            "status": "success",
            "data": data,
            "message": f"Fetched data for the last {days} days"
        }

    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities")
async def list_activities(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum activities to return"),
    period_days: int = Query(30, ge=7, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """List recent Garmin activities stored for a user."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        start_date = datetime.utcnow() - timedelta(days=period_days)
        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.start_time >= start_date
        ).order_by(GarminActivityData.start_time.desc()).limit(limit).all()

        summary = summarize_activities(activities)
        type_distribution: Dict[str, int] = {}
        for activity in activities:
            activity_type = (activity.activity_type or "UNKNOWN").upper()
            type_distribution[activity_type] = type_distribution.get(activity_type, 0) + 1

        weekly_trend = build_weekly_activity_trend(activities)

        return {
            "activities": [
                {
                    "id": activity.id,
                    "summary_id": activity.summary_id,
                    "activity_id": activity.activity_id,
                    "activity_type": activity.activity_type,
                    "activity_name": activity.activity_name,
                    "start_time": activity.start_time.isoformat() if activity.start_time else None,
                    "duration_seconds": activity.duration,
                    "distance_meters": activity.distance,
                    "average_heart_rate": activity.average_heart_rate,
                    "max_heart_rate": activity.max_heart_rate,
                    "calories": activity.calories,
                    "manual": activity.manual,
                    "raw_data": json.loads(activity.data) if isinstance(activity.data, str) else activity.data,
                }
                for activity in activities
            ],
            "count": len(activities),
            "period_days": period_days,
            "summary": summary,
            "type_distribution": type_distribution,
            "weekly_trend": weekly_trend,
        }
    except Exception as e:
        logger.error(f"List activities failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/weekly")
async def weekly_analysis(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(7, ge=1, le=90, description="Window size in days"),
    db: Session = Depends(get_db)
):
    """Return training summary for a given window and baseline comparison."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        now = datetime.utcnow()
        current_start = now - timedelta(days=days)
        baseline_start = current_start - timedelta(days=28)

        activities = db.query(GarminActivityData).filter(
            GarminActivityData.user_id == resolved_user_id,
            GarminActivityData.start_time >= baseline_start
        ).order_by(GarminActivityData.start_time.desc()).all()

        current_week = [activity for activity in activities if activity.start_time >= current_start]
        baseline_window = [activity for activity in activities if baseline_start <= activity.start_time < current_start]

        current_metrics = summarize_activities(current_week)
        baseline_totals = summarize_activities(baseline_window)
        baseline_weekly = {
            "sessions": round(baseline_totals["sessions"] / 4, 2),
            "distance_km": round(baseline_totals["distance_km"] / 4, 2),
            "duration_hours": round(baseline_totals["duration_hours"] / 4, 2),
            "average_heart_rate": baseline_totals["average_heart_rate"],
            "running_sessions": round(baseline_totals["running_sessions"] / 4, 2),
            "cycling_sessions": round(baseline_totals["cycling_sessions"] / 4, 2),
        }

        baseline_duration = baseline_weekly["duration_hours"]
        load_ratio = round(
            (current_metrics["duration_hours"] / baseline_duration), 2
        ) if baseline_duration and baseline_duration > 0 else None

        hr_delta = None
        if current_metrics["average_heart_rate"] is not None and baseline_weekly["average_heart_rate"] is not None:
            hr_delta = round(current_metrics["average_heart_rate"] - baseline_weekly["average_heart_rate"], 1)

        metrics_delta = {
            "sessions_percent": compute_percent_change(current_metrics["sessions"], baseline_weekly["sessions"]),
            "distance_percent": compute_percent_change(current_metrics["distance_km"], baseline_weekly["distance_km"]),
            "duration_percent": compute_percent_change(current_metrics["duration_hours"], baseline_weekly["duration_hours"]),
            "avg_heart_rate_delta": hr_delta,
        }

        if load_ratio is None:
            recommendation = "Not enough historical data yet. Keep building consistent easy sessions."
        elif load_ratio > 1.25:
            recommendation = "High load increase this week. Keep next sessions easy and prioritize recovery."
        elif load_ratio < 0.75:
            recommendation = "Training load is below baseline. Add one extra easy session if recovery is good."
        else:
            recommendation = "Load looks balanced versus your baseline. Keep the current structure."

        weekly_summary = build_weekly_summary(
            current_week=current_metrics,
            baseline_weekly=baseline_weekly,
            load_ratio=load_ratio,
            hr_delta=hr_delta,
        )

        highlights = []
        if load_ratio is not None:
            if load_ratio > 1.25:
                highlights.append({"type": "warning", "label": "Hoge belasting", "text": f"Load ratio {load_ratio}x — plan extra herstel"})
            elif load_ratio < 0.75:
                highlights.append({"type": "info", "label": "Lage belasting", "text": f"Load ratio {load_ratio}x — ruimte om op te bouwen"})
            else:
                highlights.append({"type": "success", "label": "Gebalanceerd", "text": f"Load ratio {load_ratio}x — goed bezig"})

        if hr_delta is not None:
            if hr_delta > 3:
                highlights.append({"type": "warning", "label": "Hartslag stijgt", "text": f"+{hr_delta} bpm vs baseline"})
            elif hr_delta < -3:
                highlights.append({"type": "success", "label": "Hartslag daalt", "text": f"{hr_delta} bpm vs baseline"})

        if current_metrics["running_sessions"] > 0 or current_metrics["cycling_sessions"] > 0:
            highlights.append({
                "type": "info",
                "label": "Verdeling",
                "text": f"{current_metrics['running_sessions']} run · {current_metrics['cycling_sessions']} fiets",
            })

        return {
            "days": days,
            "window": {
                "current_start": current_start.isoformat(),
                "current_end": now.isoformat(),
                "baseline_start": baseline_start.isoformat(),
                "baseline_end": current_start.isoformat(),
            },
            "current_week": current_metrics,
            "baseline_weekly": baseline_weekly,
            "deltas": metrics_delta,
            "load_ratio": load_ratio,
            "insight": recommendation,
            "summary": weekly_summary,
            "highlights": highlights,
        }
    except Exception as e:
        logger.error(f"Weekly analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery")
async def get_recovery_snapshot(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    lookback_days: int = Query(14, ge=1, le=90, description="How far back to search for latest health data"),
    db: Session = Depends(get_db)
):
    """Return the latest Garmin health metrics needed by the app recovery UI."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        since = datetime.utcnow() - timedelta(days=lookback_days)

        daily_record = _latest_health_record(db, resolved_user_id, "dailies", since)
        sleep_record = _latest_health_record(db, resolved_user_id, "sleeps", since)
        stress_record = _latest_health_record(db, resolved_user_id, "stressDetails", since)
        hrv_record = _latest_health_record(db, resolved_user_id, "hrv", since)

        daily = _load_health_payload(daily_record)
        sleep = _load_health_payload(sleep_record)
        stress = _load_health_payload(stress_record)
        hrv = _load_health_payload(hrv_record)

        if not any([daily, sleep, stress, hrv]):
            return {
                "source": "empty",
                "calendar_date": None,
                "score": None,
                "metrics": None,
                "message": "No Garmin health data found yet. Sync Garmin Connect or request a backfill.",
            }

        stress_values = _valid_stress_values(stress.get("timeOffsetStressLevelValues", {}))
        body_battery_values = _valid_numeric_values(stress.get("timeOffsetBodyBatteryValues", {}))
        hrv_values = _valid_numeric_values(hrv.get("hrvValues", {}))
        heart_rate_values = _valid_numeric_values(daily.get("timeOffsetHeartRateSamples", {}))

        sleep_duration_seconds = sleep.get("durationInSeconds")
        sleep_hours = round(sleep_duration_seconds / 3600, 1) if sleep_duration_seconds else None
        sleep_score = _sleep_score(sleep)
        avg_stress = round(sum(stress_values) / len(stress_values)) if stress_values else None
        body_battery = round(body_battery_values[-1]) if body_battery_values else None
        hrv_overnight = (
            int(hrv.get("lastNightAvg"))
            if isinstance(hrv.get("lastNightAvg"), (int, float))
            else (round(sum(hrv_values) / len(hrv_values)) if hrv_values else None)
        )

        current_hr = round(heart_rate_values[-1]) if heart_rate_values else daily.get("averageHeartRateInBeatsPerMinute")
        hr_trend = [round(value) for value in heart_rate_values[-60:]]

        date_candidates = [
            payload.get("calendarDate")
            for payload in [sleep, daily, stress, hrv]
            if payload.get("calendarDate")
        ]
        calendar_date = date_candidates[0] if date_candidates else None

        score = _recovery_score(
            sleep_score=sleep_score,
            sleep_hours=sleep_hours,
            avg_stress=avg_stress,
            body_battery=body_battery,
            hrv=hrv_overnight,
        )

        return {
            "source": "live",
            "calendar_date": calendar_date,
            "score": score,
            "metrics": {
                "sleepScore": sleep_score,
                "sleepHours": sleep_hours,
                "deepSleepMin": _minutes(sleep.get("deepSleepDurationInSeconds")),
                "remMin": _minutes(sleep.get("remSleepInSeconds")),
                "lightMin": _minutes(sleep.get("lightSleepDurationInSeconds")),
                "awakeMin": _minutes(sleep.get("awakeDurationInSeconds")),
                "avgStress": avg_stress,
                "bodyBattery": body_battery,
                "hrvOvernight": hrv_overnight,
                "restingHr": daily.get("restingHeartRateInBeatsPerMinute"),
                "currentHeartRate": current_hr,
                "hrvTrend": [round(value) for value in hrv_values[-7:]],
                "stressTrend": stress_values[-24:],
                "hrTrend": hr_trend,
                "steps": daily.get("steps"),
                "activeKilocalories": daily.get("activeKilocalories"),
                "distanceMeters": daily.get("distanceInMeters"),
            },
            "records": {
                "daily": daily_record.summary_id if daily_record else None,
                "sleep": sleep_record.summary_id if sleep_record else None,
                "stress": stress_record.summary_id if stress_record else None,
                "hrv": hrv_record.summary_id if hrv_record else None,
            },
        }
    except Exception as e:
        logger.error(f"Recovery snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/backfill")
async def request_backfill(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    data_type: str = Query(..., description="Type of data", regex="^(dailies|activities|sleeps|stress|hrv|health|both|all)$"),
    db: Session = Depends(get_db)
):
    """
    Request backfill of historical data from Garmin.

    Data will be sent asynchronously via webhooks.
    """
    try:
        from datetime import datetime

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)

        if data_type in ["dailies", "health", "both", "all"]:
            client.backfill_dailies(start, end)

        activity_backfill = None
        if data_type in ["activities", "both", "all"]:
            activity_backfill = request_activity_backfill_with_fallback(
                client=client,
                start=start,
                end=end,
            )

        health_types = []
        if data_type in ["sleeps", "health", "both", "all"]:
            health_types.append("sleeps")
        if data_type in ["stress", "health", "both", "all"]:
            health_types.append("stressDetails")
        if data_type in ["hrv", "health", "both", "all"]:
            health_types.append("hrv")

        for health_type in health_types:
            client.backfill_health_type(health_type, start, end)

        return {
            "status": "success",
            "message": f"Backfill requested for {data_type} from {start_date} to {end_date}. Data will be sent via webhooks.",
            "activity_backfill": activity_backfill,
        }

    except Exception as e:
        logger.error(f"Backfill request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/backfill/smart")
async def request_smart_activity_backfill(
    user_id: Optional[int] = Query(None, description="Internal user ID"),
    telegram_user_id: Optional[int] = Query(None, description="Legacy Telegram user ID"),
    days: int = Query(120, ge=7, le=180, description="How many days of activity history to request"),
    db: Session = Depends(get_db),
):
    """Request activity backfill with automatic Garmin minimum-date fallback."""
    try:
        resolved_user_id = resolve_user_id(user_id, telegram_user_id)
        client = GarminAPIClient(db, resolved_user_id)

        end = datetime.utcnow()
        start = end - timedelta(days=days)
        activity_backfill = request_activity_backfill_with_fallback(
            client=client,
            start=start,
            end=end,
        )

        return {
            "status": "success",
            "message": "Smart activity backfill requested. Data will arrive via activity webhooks.",
            "activity_backfill": activity_backfill,
        }
    except Exception as e:
        logger.error(f"Smart backfill request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBHOOK ENDPOINTS - Garmin pushes/pings data to these endpoints
# ============================================================================

@router.post("/webhook/health")
async def receive_health_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive health/wellness data webhooks from Garmin.

    This endpoint receives PING notifications for:
    - dailies, epochs, sleeps, bodyComps, stressDetails, userMetrics,
    - pulseox, allDayRespiration, healthSnapshot, hrv, bloodPressures, skinTemp
    """
    try:
        data = await request.json()
        logger.info(f"Received health webhook: {data}")

        # Process each summary type
        for summary_type, items in data.items():
            if summary_type == "deregistrations":
                continue  # Handle in separate endpoint

            for item in items:
                garmin_user_id = item.get('userId')
                callback_url = item.get('callbackURL')

                # Resolve internal user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    logger.warning(f"No token found for Garmin user {garmin_user_id}")
                    continue

                user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH data directly
                    try:
                        client = GarminAPIClient(db, user_id)
                        client._store_health_data(summary_type, [item])
                        logger.info(f"Stored PUSH {summary_type} for user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to store PUSH data: {e}")
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, user_id)
                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        client._store_health_data(summary_type, summaries)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {user_id}")
                    else:
                        logger.error(f"Callback URL returned {response.status_code}: {response.text}")
                except Exception as e:
                    logger.error(f"Failed to fetch/store from callback URL: {e}")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Health webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/activity")
async def receive_activity_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive activity data webhooks from Garmin.

    This endpoint receives PING notifications for:
    - activities, activityDetails, activityFiles, moveIQActivities, manuallyUpdatedActivities
    """
    try:
        data = await request.json()
        logger.info(f"Received activity webhook: {data}")

        # Process each summary type
        for summary_type, items in data.items():
            for item in items:
                garmin_user_id = item.get('userId')
                callback_url = item.get('callbackURL')

                # Resolve internal user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    logger.warning(f"No token found for Garmin user {garmin_user_id}")
                    continue

                user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH activity data directly
                    try:
                        client = GarminAPIClient(db, user_id)
                        client._store_activity_data([item])
                        logger.info(f"Stored PUSH {summary_type} for user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to store PUSH activity: {e}")
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, user_id)
                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        client._store_activity_data(summaries)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {user_id}")
                    else:
                        logger.error(f"Callback URL returned {response.status_code}: {response.text}")
                except Exception as e:
                    logger.error(f"Failed to fetch/store from callback URL: {e}")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Activity webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/deregistration")
async def receive_deregistration_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive deregistration notifications from Garmin.

    Called when a user disconnects their Garmin account.
    """
    try:
        data = await request.json()
        logger.info(f"Received deregistration webhook: {data}")

        # Extract user ID from webhook
        deregistrations = data.get('deregistrations', [])

        for dereg in deregistrations:
            garmin_user_id = dereg.get('userId')
            if garmin_user_id:
                # Find and delete tokens
                garmin_token = db.query(GarminToken).filter(
                    GarminToken.garmin_user_id == garmin_user_id
                ).first()

                if garmin_token:
                    db.delete(garmin_token)
                    logger.info(f"Deleted tokens for Garmin user {garmin_user_id}")

        db.commit()
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Deregistration webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/permissions")
async def receive_permissions_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive user permission change notifications from Garmin.

    Called when a user changes their data sharing permissions.
    """
    try:
        data = await request.json()
        logger.info(f"Received permissions webhook: {data}")

        # TODO: Update user permissions in database
        # For now, just log it

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Permissions webhook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
