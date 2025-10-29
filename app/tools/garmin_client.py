"""Garmin API client for fetching health and activity data."""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json

from app.tools.garmin_oauth import GarminOAuthService
from app.database.models import GarminHealthData, GarminActivityData

logger = logging.getLogger(__name__)


class GarminAPIClient:
    """Client for interacting with Garmin Health and Activity APIs."""

    # Health API endpoints
    DAILIES_URL = "https://apis.garmin.com/wellness-api/rest/dailies"
    EPOCHS_URL = "https://apis.garmin.com/wellness-api/rest/epochs"
    SLEEPS_URL = "https://apis.garmin.com/wellness-api/rest/sleeps"
    BODY_COMP_URL = "https://apis.garmin.com/wellness-api/rest/bodyComps"
    STRESS_URL = "https://apis.garmin.com/wellness-api/rest/stressDetails"
    USER_METRICS_URL = "https://apis.garmin.com/wellness-api/rest/userMetrics"
    PULSE_OX_URL = "https://apis.garmin.com/wellness-api/rest/pulseox"
    RESPIRATION_URL = "https://apis.garmin.com/wellness-api/rest/respiration"
    HEALTH_SNAPSHOT_URL = "https://apis.garmin.com/wellness-api/rest/healthSnapshot"
    HRV_URL = "https://apis.garmin.com/wellness-api/rest/hrv"
    BLOOD_PRESSURE_URL = "https://apis.garmin.com/wellness-api/rest/bloodPressures"
    SKIN_TEMP_URL = "https://apis.garmin.com/wellness-api/rest/skinTemp"

    # Activity API endpoints
    ACTIVITIES_URL = "https://apis.garmin.com/wellness-api/rest/activities"
    ACTIVITY_DETAILS_URL = "https://apis.garmin.com/wellness-api/rest/activityDetails"
    MOVE_IQ_URL = "https://apis.garmin.com/wellness-api/rest/moveiq"

    # Backfill endpoints
    BACKFILL_DAILIES_URL = "https://apis.garmin.com/wellness-api/rest/backfill/dailies"
    BACKFILL_ACTIVITIES_URL = "https://apis.garmin.com/wellness-api/rest/backfill/activities"

    def __init__(self, db: Session, telegram_user_id: int):
        """
        Initialize Garmin API client.

        Args:
            db: Database session
            telegram_user_id: Telegram user ID
        """
        self.db = db
        self.telegram_user_id = telegram_user_id
        self.oauth_service = GarminOAuthService()
        self.access_token = self.oauth_service.get_valid_access_token(db, telegram_user_id)

        if not self.access_token:
            raise Exception("No valid Garmin access token found for user")

    def _get_headers(self) -> Dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        Make authenticated request to Garmin API.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Check if it's a 400/403 error (likely permission/scope issue)
            if e.response.status_code in [400, 403]:
                logger.error(f"Garmin API request failed with status {e.response.status_code}: {e}")
                logger.error(f"This may indicate missing OAuth scopes. Required: HEALTH_EXPORT ACTIVITY_EXPORT")
                logger.error(f"URL: {url}, Params: {params}")
            else:
                logger.error(f"Garmin API request failed: {e}")
            raise Exception(f"Garmin API error: {e}")

    def _store_health_data(
        self,
        summary_type: str,
        summaries: List[Dict]
    ):
        """
        Store health data summaries in database.

        Args:
            summary_type: Type of summary (dailies, sleeps, etc.)
            summaries: List of summary data dicts
        """
        for summary in summaries:
            summary_id = summary.get('summaryId')
            if not summary_id:
                continue

            # Check if already exists
            existing = self.db.query(GarminHealthData).filter(
                GarminHealthData.summary_id == summary_id
            ).first()

            # Parse timestamps
            start_time = None
            if 'startTimeInSeconds' in summary:
                start_time = datetime.utcfromtimestamp(summary['startTimeInSeconds'])
            elif 'measurementTimeInSeconds' in summary:
                start_time = datetime.utcfromtimestamp(summary['measurementTimeInSeconds'])

            if not start_time:
                logger.warning(f"No timestamp found in summary {summary_id}")
                continue

            data_json = json.dumps(summary)

            if existing:
                # Update existing record
                existing.data = data_json
                existing.updated_at = datetime.utcnow()
            else:
                # Create new record
                health_data = GarminHealthData(
                    user_id=self.telegram_user_id,
                    summary_id=summary_id,
                    summary_type=summary_type,
                    calendar_date=summary.get('calendarDate'),
                    start_time=start_time,
                    start_time_offset=summary.get('startTimeOffsetInSeconds') or summary.get('offsetInSeconds'),
                    duration=summary.get('durationInSeconds'),
                    data=data_json
                )
                self.db.add(health_data)

        self.db.commit()

    def _store_activity_data(
        self,
        summaries: List[Dict]
    ):
        """
        Store activity data summaries in database.

        Args:
            summaries: List of activity summary dicts
        """
        for summary in summaries:
            summary_id = summary.get('summaryId')
            if not summary_id:
                continue

            # Check if already exists
            existing = self.db.query(GarminActivityData).filter(
                GarminActivityData.summary_id == summary_id
            ).first()

            # Parse timestamp
            start_time = datetime.utcfromtimestamp(summary['startTimeInSeconds'])

            data_json = json.dumps(summary)

            if existing:
                # Update existing record
                existing.data = data_json
                existing.updated_at = datetime.utcnow()
            else:
                # Create new record
                activity_data = GarminActivityData(
                    user_id=self.telegram_user_id,
                    summary_id=summary_id,
                    activity_id=summary.get('activityId'),
                    activity_type=summary.get('activityType'),
                    activity_name=summary.get('activityName'),
                    start_time=start_time,
                    start_time_offset=summary.get('startTimeOffsetInSeconds'),
                    duration=summary.get('durationInSeconds'),
                    distance=summary.get('distanceInMeters'),
                    calories=summary.get('activeKilocalories'),
                    average_heart_rate=summary.get('averageHeartRateInBeatsPerMinute'),
                    max_heart_rate=summary.get('maxHeartRateInBeatsPerMinute'),
                    device_name=summary.get('deviceName'),
                    manual=summary.get('manual', False),
                    data=data_json
                )
                self.db.add(activity_data)

        self.db.commit()

    # =========================================================================
    # HEALTH DATA METHODS
    # NOTE: These methods are DEPRECATED for ad-hoc use!
    # Garmin APIs do NOT support direct REST API calls without webhook notifications.
    # These methods will return 400 Bad Request when called directly.
    # Only use these internally when processing webhook notifications.
    # =========================================================================

    def get_dailies(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch daily summaries.

        DEPRECATED: Do not call directly! This will fail with 400 Bad Request.
        Only used internally by webhook handlers.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of daily summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.DAILIES_URL, params)

        if store:
            self._store_health_data("dailies", data)

        return data

    def get_epochs(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch 15-minute epoch summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of epoch summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.EPOCHS_URL, params)

        if store:
            self._store_health_data("epochs", data)

        return data

    def get_sleeps(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch sleep summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of sleep summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.SLEEPS_URL, params)

        if store:
            self._store_health_data("sleeps", data)

        return data

    def get_stress_details(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch stress details summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
        Returns:
            List of stress detail summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.STRESS_URL, params)

        if store:
            self._store_health_data("stressDetails", data)

        return data

    def get_hrv(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch heart rate variability summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of HRV summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.HRV_URL, params)

        if store:
            self._store_health_data("hrv", data)

        return data

    # =========================================================================
    # ACTIVITY DATA METHODS
    # =========================================================================

    def get_activities(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch activity summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of activity summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.ACTIVITIES_URL, params)

        if store:
            self._store_activity_data(data)

        return data

    def get_activity_details(
        self,
        start_time: int,
        end_time: int,
        store: bool = True
    ) -> List[Dict]:
        """
        Fetch detailed activity summaries.

        Args:
            start_time: Start time in Unix timestamp (seconds)
            end_time: End time in Unix timestamp (seconds)
            store: Whether to store in database

        Returns:
            List of activity detail summary dicts
        """
        params = {
            "uploadStartTimeInSeconds": start_time,
            "uploadEndTimeInSeconds": end_time
        }

        data = self._make_request(self.ACTIVITY_DETAILS_URL, params)

        if store:
            # Activity details have nested structure
            for item in data:
                if 'summary' in item:
                    # Extract summary and add summaryId from parent
                    summary = item['summary']
                    summary['summaryId'] = item.get('summaryId')
                    self._store_activity_data([summary])

        return data

    # =========================================================================
    # BACKFILL METHODS
    # =========================================================================

    def backfill_dailies(
        self,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Request backfill of daily summaries for a date range.

        Args:
            start_date: Start date (will be converted to Unix timestamp)
            end_date: End date (will be converted to Unix timestamp)

        Note: Backfill works asynchronously. Data will be sent via webhooks.
        """
        params = {
            "summaryStartTimeInSeconds": int(start_date.timestamp()),
            "summaryEndTimeInSeconds": int(end_date.timestamp())
        }

        response = requests.get(
            self.BACKFILL_DAILIES_URL,
            headers=self._get_headers(),
            params=params
        )

        if response.status_code == 202:
            logger.info(f"Backfill requested for dailies: {start_date} to {end_date}")
        else:
            raise Exception(f"Backfill request failed: {response.text}")

    def backfill_activities(
        self,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Request backfill of activity summaries for a date range.

        Args:
            start_date: Start date (will be converted to Unix timestamp)
            end_date: End date (will be converted to Unix timestamp)

        Note: Backfill works asynchronously. Data will be sent via webhooks.
        """
        params = {
            "summaryStartTimeInSeconds": int(start_date.timestamp()),
            "summaryEndTimeInSeconds": int(end_date.timestamp())
        }

        response = requests.get(
            self.BACKFILL_ACTIVITIES_URL,
            headers=self._get_headers(),
            params=params
        )

        if response.status_code == 202:
            logger.info(f"Backfill requested for activities: {start_date} to {end_date}")
        else:
            raise Exception(f"Backfill request failed: {response.text}")

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_recent_data(self, days: int = 7):
        """
        Fetch recent health and activity data for the user from DATABASE.

        NOTE: Garmin APIs do not support ad-hoc REST API calls. Data is delivered
        via webhooks/push notifications only. This method reads from the local database
        which is populated by webhook handlers.

        For historical data that hasn't arrived yet, use backfill endpoints which
        will trigger webhook deliveries.

        Args:
            days: Number of days to look back in database (default: 7)

        Returns:
            Dict with health and activity data from database
        """
        from app.database.models import GarminHealthData, GarminActivityData
        import json

        result = {
            "dailies": [],
            "sleeps": [],
            "activities": [],
            "stress": []
        }

        # Calculate date range
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Fetch health data from database
        health_data = self.db.query(GarminHealthData).filter(
            GarminHealthData.user_id == self.telegram_user_id,
            GarminHealthData.created_at >= cutoff_date
        ).all()

        for record in health_data:
            data = json.loads(record.data) if isinstance(record.data, str) else record.data

            if record.summary_type == 'dailies':
                result["dailies"].append(data)
            elif record.summary_type == 'sleeps':
                result["sleeps"].append(data)
            elif record.summary_type == 'stressDetails':
                result["stress"].append(data)

        # Fetch activity data from database
        activity_data = self.db.query(GarminActivityData).filter(
            GarminActivityData.user_id == self.telegram_user_id,
            GarminActivityData.created_at >= cutoff_date
        ).all()

        for record in activity_data:
            data = json.loads(record.data) if isinstance(record.data, str) else record.data
            result["activities"].append(data)

        logger.info(f"Retrieved from database: {len(result['dailies'])} dailies, "
                   f"{len(result['sleeps'])} sleeps, {len(result['activities'])} activities, "
                   f"{len(result['stress'])} stress records")

        return result
