"""Garmin OAuth2 and webhook API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
import requests
import time
from datetime import datetime, timedelta

from app.config import settings
from app.database.database import get_db
from app.tools.garmin_oauth import GarminOAuthService
from app.tools.garmin_client import GarminAPIClient
from app.database.models import GarminToken, OAuthSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/garmin", tags=["garmin"])


@router.get("/auth/start")
async def start_oauth(
    telegram_user_id: int = Query(..., description="Telegram user ID"),
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

        logger.info(f"[OAuth Start] Generated state: {state} for user: {telegram_user_id}")

        # Store session data in the database
        new_session = OAuthSession(
            state=state,
            code_verifier=code_verifier,
            telegram_user_id=telegram_user_id
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
        telegram_user_id = session.telegram_user_id
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
        garmin_token = oauth_service.store_tokens(db, telegram_user_id, token_data)

        # Get user permissions
        access_token = token_data['access_token']
        permissions = oauth_service.get_user_permissions(access_token)

        # Return a simple HTML page that can be closed
        from fastapi.responses import HTMLResponse
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Garmin Verbonden</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #ffffff;
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 400px;
                }
                .success-icon {
                    font-size: 60px;
                    color: #28a745;
                    margin-bottom: 20px;
                }
                h1 {
                    color: #333;
                    margin-bottom: 10px;
                }
                p {
                    color: #666;
                    line-height: 1.6;
                }
                .close-btn {
                    margin-top: 20px;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                }
                .close-btn:hover {
                    background: #5568d3;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon"></div>
                <h1>Succesvol verbonden!</h1>
                <p>Je Garmin account is succesvol gekoppeld.</p>
                <p>Je kunt dit venster nu sluiten en teruggaan naar de Telegram bot.</p>
                <button class="close-btn" onclick="window.close()">Sluit venster</button>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/status")
async def check_auth_status(
    telegram_user_id: int = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check if user has valid Garmin authentication."""
    try:
        oauth_service = GarminOAuthService()
        access_token = oauth_service.get_valid_access_token(db, telegram_user_id)

        if not access_token:
            return {
                "authenticated": False,
                "message": "No Garmin connection found"
            }

        # Get user permissions
        permissions = oauth_service.get_user_permissions(access_token)

        # Get token info
        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == telegram_user_id
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
    telegram_user_id: int = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Disconnect Garmin account and delete stored tokens."""
    try:
        oauth_service = GarminOAuthService()

        # Get current access token
        access_token = oauth_service.get_valid_access_token(db, telegram_user_id)

        if access_token:
            # Deregister from Garmin API
            try:
                oauth_service.deregister_user(access_token)
            except Exception as e:
                logger.warning(f"Garmin deregistration failed: {e}")

        # Delete local tokens
        oauth_service.delete_tokens(db, telegram_user_id)

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
    telegram_user_id: int = Query(..., description="Telegram user ID"),
    days: int = Query(7, description="Number of days to fetch", ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Fetch recent health and activity data for a user.

    This manually fetches data from Garmin API instead of waiting for webhooks.
    """
    try:
        client = GarminAPIClient(db, telegram_user_id)
        data = client.get_recent_data(days=days)

        return {
            "status": "success",
            "data": data,
            "message": f"Fetched data for the last {days} days"
        }

    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/backfill")
async def request_backfill(
    telegram_user_id: int = Query(..., description="Telegram user ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    data_type: str = Query(..., description="Type of data", regex="^(dailies|activities|both)$"),
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

        client = GarminAPIClient(db, telegram_user_id)

        if data_type in ["dailies", "both"]:
            client.backfill_dailies(start, end)

        if data_type in ["activities", "both"]:
            client.backfill_activities(start, end)

        return {
            "status": "success",
            "message": f"Backfill requested for {data_type} from {start_date} to {end_date}. Data will be sent via webhooks."
        }

    except Exception as e:
        logger.error(f"Backfill request failed: {e}")
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

                # Find the telegram_user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    logger.warning(f"No token found for Garmin user {garmin_user_id}")
                    continue

                telegram_user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH data directly
                    try:
                        client = GarminAPIClient(db, telegram_user_id)
                        client._store_health_data(summary_type, [item])
                        logger.info(f"Stored PUSH {summary_type} for user {telegram_user_id}")
                    except Exception as e:
                        logger.error(f"Failed to store PUSH data: {e}")
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, telegram_user_id)
                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        client._store_health_data(summary_type, summaries)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {telegram_user_id}")
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

                # Find the telegram_user_id from garmin_user_id
                token = db.query(GarminToken).filter(GarminToken.garmin_user_id == garmin_user_id).first()
                if not token:
                    logger.warning(f"No token found for Garmin user {garmin_user_id}")
                    continue

                telegram_user_id = token.user_id

                if not callback_url:
                    # This is a PUSH notification with data included
                    logger.info(f"PUSH notification for {summary_type}, user {garmin_user_id}")
                    # Store PUSH activity data directly
                    try:
                        client = GarminAPIClient(db, telegram_user_id)
                        client._store_activity_data([item])
                        logger.info(f"Stored PUSH {summary_type} for user {telegram_user_id}")
                    except Exception as e:
                        logger.error(f"Failed to store PUSH activity: {e}")
                    continue

                # This is a PING notification, we need to fetch data from callback URL
                logger.info(f"PING notification for {summary_type}, user {garmin_user_id}")

                try:
                    # Fetch data from callback URL using user's access token
                    client = GarminAPIClient(db, telegram_user_id)
                    response = requests.get(
                        callback_url,
                        headers=client._get_headers()
                    )

                    if response.status_code == 200:
                        summaries = response.json()
                        logger.info(f"Fetched {len(summaries)} {summary_type} summaries from PING")

                        # Store in database
                        client._store_activity_data(summaries)
                        logger.info(f"Stored {len(summaries)} {summary_type} summaries for user {telegram_user_id}")
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
