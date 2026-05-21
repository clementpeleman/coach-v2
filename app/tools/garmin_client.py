"""Garmin API client for fetching health and activity data."""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import base64
import json

from app.tools.garmin_oauth import GarminOAuthService
from app.database.models import GarminActivityAuxiliaryData, GarminHealthData, GarminActivityData

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
    BACKFILL_ACTIVITY_DETAILS_URL = "https://apis.garmin.com/wellness-api/rest/backfill/activityDetails"
    BACKFILL_MOVE_IQ_URL = "https://apis.garmin.com/wellness-api/rest/backfill/moveiq"
    BACKFILL_SLEEPS_URL = "https://apis.garmin.com/wellness-api/rest/backfill/sleeps"
    BACKFILL_EPOCHS_URL = "https://apis.garmin.com/wellness-api/rest/backfill/epochs"
    BACKFILL_BODY_COMP_URL = "https://apis.garmin.com/wellness-api/rest/backfill/bodyComps"
    BACKFILL_STRESS_URL = "https://apis.garmin.com/wellness-api/rest/backfill/stressDetails"
    BACKFILL_USER_METRICS_URL = "https://apis.garmin.com/wellness-api/rest/backfill/userMetrics"
    BACKFILL_PULSE_OX_URL = "https://apis.garmin.com/wellness-api/rest/backfill/pulseOx"
    BACKFILL_RESPIRATION_URL = "https://apis.garmin.com/wellness-api/rest/backfill/respiration"
    BACKFILL_HEALTH_SNAPSHOT_URL = "https://apis.garmin.com/wellness-api/rest/backfill/healthSnapshot"
    BACKFILL_HRV_URL = "https://apis.garmin.com/wellness-api/rest/backfill/hrv"
    BACKFILL_BLOOD_PRESSURE_URL = "https://apis.garmin.com/wellness-api/rest/backfill/bloodPressures"
    BACKFILL_SKIN_TEMP_URL = "https://apis.garmin.com/wellness-api/rest/backfill/skinTemp"

    def __init__(self, db: Session, user_id: int):
        """
        Initialize Garmin API client.

        Args:
            db: Database session
            user_id: Internal user ID
        """
        self.db = db
        self.user_id = user_id
        self.oauth_service = GarminOAuthService()
        self.access_token = self.oauth_service.get_valid_access_token(db, user_id)

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
            elif isinstance(summary.get('summary'), dict) and summary['summary'].get('startTimeInSeconds'):
                start_time = datetime.utcfromtimestamp(summary['summary']['startTimeInSeconds'])
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
                    user_id=self.user_id,
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
        summaries: List[Dict],
        summary_type: str = "activities",
    ):
        """
        Store activity data summaries in database.

        Args:
            summaries: List of activity summary dicts
            summary_type: Garmin summary type from webhook payload
        """
        if summary_type not in {"activities", "manuallyUpdatedActivities"}:
            self._store_activity_auxiliary_data(summary_type, summaries)
            return

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
                existing.summary_type = summary_type
                existing.data = data_json
                existing.updated_at = datetime.utcnow()
            else:
                # Create new record
                activity_data = GarminActivityData(
                    user_id=self.user_id,
                    summary_id=summary_id,
                    summary_type=summary_type,
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

    def _store_activity_auxiliary_data(
        self,
        summary_type: str,
        summaries: List[Dict],
    ):
        """Store activity details, files, MoveIQ, and other non-list activity payloads."""
        for summary in summaries:
            summary_id = (
                summary.get('summaryId')
                or summary.get('activityId')
                or summary.get('fileId')
                or summary.get('callbackURL')
            )
            if not summary_id:
                logger.warning(f"No stable identifier found in {summary_type} summary")
                continue

            existing = self.db.query(GarminActivityAuxiliaryData).filter(
                GarminActivityAuxiliaryData.summary_type == summary_type,
                GarminActivityAuxiliaryData.summary_id == str(summary_id),
            ).first()

            start_time = None
            if 'startTimeInSeconds' in summary:
                start_time = datetime.utcfromtimestamp(summary['startTimeInSeconds'])

            data_json = json.dumps(summary)

            if existing:
                existing.activity_id = summary.get('activityId')
                existing.start_time = start_time
                existing.start_time_offset = summary.get('startTimeOffsetInSeconds')
                existing.duration = summary.get('durationInSeconds')
                existing.data = data_json
                existing.updated_at = datetime.utcnow()
            else:
                aux_data = GarminActivityAuxiliaryData(
                    user_id=self.user_id,
                    summary_id=str(summary_id),
                    summary_type=summary_type,
                    activity_id=summary.get('activityId'),
                    start_time=start_time,
                    start_time_offset=summary.get('startTimeOffsetInSeconds'),
                    duration=summary.get('durationInSeconds'),
                    data=data_json,
                )
                self.db.add(aux_data)

        self.db.commit()

    def _store_activity_file_content(
        self,
        metadata: Dict,
        content: bytes,
        content_type: Optional[str] = None,
    ):
        """Store activity file metadata plus raw callback content as base64."""
        payload = dict(metadata)
        payload["contentType"] = content_type
        payload["contentLength"] = len(content)
        payload["contentBase64"] = base64.b64encode(content).decode("ascii")
        self._store_activity_auxiliary_data("activityFiles", [payload])

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
            self._store_activity_data(data, "activities")

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
            self._store_activity_auxiliary_data("activityDetails", data)

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

    def backfill_activity_type(
        self,
        data_type: str,
        start_date: datetime,
        end_date: datetime
    ):
        """Request backfill for supported Activity API summary types."""
        urls = {
            "activityDetails": self.BACKFILL_ACTIVITY_DETAILS_URL,
            "moveIQActivities": self.BACKFILL_MOVE_IQ_URL,
        }
        url = urls.get(data_type)
        if not url:
            raise ValueError(f"Unsupported activity backfill type: {data_type}")

        params = {
            "summaryStartTimeInSeconds": int(start_date.timestamp()),
            "summaryEndTimeInSeconds": int(end_date.timestamp())
        }

        response = requests.get(
            url,
            headers=self._get_headers(),
            params=params
        )

        if response.status_code == 202:
            logger.info(f"Backfill requested for {data_type}: {start_date} to {end_date}")
        else:
            raise Exception(f"Backfill request failed for {data_type}: {response.text}")

    def backfill_health_type(
        self,
        data_type: str,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Request backfill for a supported Garmin health summary type.

        Data arrives asynchronously via configured Garmin webhooks.
        """
        urls = {
            "epochs": self.BACKFILL_EPOCHS_URL,
            "sleeps": self.BACKFILL_SLEEPS_URL,
            "bodyComps": self.BACKFILL_BODY_COMP_URL,
            "stressDetails": self.BACKFILL_STRESS_URL,
            "userMetrics": self.BACKFILL_USER_METRICS_URL,
            "pulseOx": self.BACKFILL_PULSE_OX_URL,
            "respiration": self.BACKFILL_RESPIRATION_URL,
            "healthSnapshot": self.BACKFILL_HEALTH_SNAPSHOT_URL,
            "hrv": self.BACKFILL_HRV_URL,
            "bloodPressures": self.BACKFILL_BLOOD_PRESSURE_URL,
            "skinTemp": self.BACKFILL_SKIN_TEMP_URL,
        }
        url = urls.get(data_type)
        if not url:
            raise ValueError(f"Unsupported health backfill type: {data_type}")

        params = {
            "summaryStartTimeInSeconds": int(start_date.timestamp()),
            "summaryEndTimeInSeconds": int(end_date.timestamp())
        }

        response = requests.get(
            url,
            headers=self._get_headers(),
            params=params
        )

        if response.status_code == 202:
            logger.info(f"Backfill requested for {data_type}: {start_date} to {end_date}")
        else:
            raise Exception(f"Backfill request failed for {data_type}: {response.text}")

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
            GarminHealthData.user_id == self.user_id,
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
            GarminActivityData.user_id == self.user_id,
            GarminActivityData.created_at >= cutoff_date
        ).all()

        for record in activity_data:
            data = json.loads(record.data) if isinstance(record.data, str) else record.data
            result["activities"].append(data)

        logger.info(f"Retrieved from database: {len(result['dailies'])} dailies, "
                   f"{len(result['sleeps'])} sleeps, {len(result['activities'])} activities, "
                   f"{len(result['stress'])} stress records")

        return result


def write_health_data(db: Session, user_id: int, summary_type: str, summaries: List[Dict]) -> None:
    """Persist health webhook payloads without a live Garmin API token."""
    writer = GarminAPIClient.__new__(GarminAPIClient)
    writer.db = db
    writer.user_id = user_id
    writer._store_health_data(summary_type, summaries)


def write_activity_data(
    db: Session,
    user_id: int,
    summaries: List[Dict],
    summary_type: str = "activities",
) -> None:
    """Persist activity webhook payloads without a live Garmin API token."""
    writer = GarminAPIClient.__new__(GarminAPIClient)
    writer.db = db
    writer.user_id = user_id
    writer._store_activity_data(summaries, summary_type)


def write_activity_auxiliary_data(
    db: Session,
    user_id: int,
    summary_type: str,
    summaries: List[Dict],
) -> None:
    """Persist auxiliary activity webhook payloads without a live Garmin API token."""
    writer = GarminAPIClient.__new__(GarminAPIClient)
    writer.db = db
    writer.user_id = user_id
    writer._store_activity_auxiliary_data(summary_type, summaries)
