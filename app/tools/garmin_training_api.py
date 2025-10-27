"""
Garmin Training API client voor het uploaden van workouts naar Garmin Connect.
"""
import requests
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.tools.garmin_oauth import GarminOAuthService

logger = logging.getLogger(__name__)


class GarminTrainingAPIClient:
    """Client voor Garmin Training API v2."""

    WORKOUT_CREATE_URL = "https://apis.garmin.com/training-api/workout/v2"
    WORKOUT_GET_URL = "https://apis.garmin.com/training-api/workout/v2/{workoutId}"
    WORKOUT_UPDATE_URL = "https://apis.garmin.com/training-api/workout/v2/{workoutId}"
    WORKOUT_DELETE_URL = "https://apis.garmin.com/training-api/workout/v2/{workoutId}"

    SCHEDULE_CREATE_URL = "https://apis.garmin.com/training-api/schedule/"
    SCHEDULE_GET_URL = "https://apis.garmin.com/training-api/schedule/{scheduleId}"

    PERMISSIONS_URL = "https://apis.garmin.com/userPermissions/"

    def __init__(self, db: Session, telegram_user_id: int):
        """
        Initialize Garmin Training API client.

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
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def check_permissions(self) -> list:
        """
        Check user permissions for Training API.

        Returns:
            List of permissions (should include "WORKOUT_IMPORT")
        """
        try:
            response = requests.get(self.PERMISSIONS_URL, headers=self._get_headers())
            response.raise_for_status()
            permissions = response.json()
            logger.info(f"User permissions: {permissions}")
            return permissions
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to check permissions: {e}")
            raise Exception(f"Permission check failed: {e}")

    def create_workout(self, workout_json: Dict) -> Dict:
        """
        Upload een workout naar Garmin Connect.

        Args:
            workout_json: Workout in Garmin Training API JSON format

        Returns:
            Response dict met workoutId

        Raises:
            Exception: Als upload faalt
        """
        try:
            logger.info(f"Uploading workout to Garmin: {workout_json.get('workoutName')}")

            response = requests.post(
                self.WORKOUT_CREATE_URL,
                headers=self._get_headers(),
                json=workout_json
            )

            response.raise_for_status()

            result = response.json()
            workout_id = result.get('workoutId')

            logger.info(f"Workout uploaded successfully. Workout ID: {workout_id}")

            return result

        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to upload workout: {e}"
            if e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error uploading workout: {e}")
            raise Exception(f"Unexpected error: {e}")

    def get_workout(self, workout_id: int) -> Dict:
        """
        Haal workout op van Garmin Connect.

        Args:
            workout_id: Garmin workout ID

        Returns:
            Workout dict
        """
        try:
            url = self.WORKOUT_GET_URL.format(workoutId=workout_id)
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to get workout {workout_id}: {e}")
            raise Exception(f"Failed to get workout: {e}")

    def update_workout(self, workout_id: int, workout_json: Dict) -> Dict:
        """
        Update een workout op Garmin Connect.

        Args:
            workout_id: Garmin workout ID
            workout_json: Volledig updated workout JSON

        Returns:
            Response dict
        """
        try:
            url = self.WORKOUT_UPDATE_URL.format(workoutId=workout_id)
            response = requests.put(
                url,
                headers=self._get_headers(),
                json=workout_json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update workout {workout_id}: {e}")
            raise Exception(f"Failed to update workout: {e}")

    def delete_workout(self, workout_id: int):
        """
        Verwijder een workout van Garmin Connect.

        Args:
            workout_id: Garmin workout ID
        """
        try:
            url = self.WORKOUT_DELETE_URL.format(workoutId=workout_id)
            response = requests.delete(url, headers=self._get_headers())
            response.raise_for_status()
            logger.info(f"Workout {workout_id} deleted successfully")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to delete workout {workout_id}: {e}")
            raise Exception(f"Failed to delete workout: {e}")

    def schedule_workout(self, workout_id: int, date: str) -> Dict:
        """
        Plan een workout op een specifieke datum.

        Args:
            workout_id: Garmin workout ID
            date: Datum in format 'YYYY-MM-DD'

        Returns:
            Schedule dict met scheduleId
        """
        try:
            schedule_json = {
                "workoutId": workout_id,
                "date": date
            }

            response = requests.post(
                self.SCHEDULE_CREATE_URL,
                headers=self._get_headers(),
                json=schedule_json
            )

            response.raise_for_status()

            result = response.json()
            logger.info(f"Workout {workout_id} scheduled for {date}")

            return result

        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to schedule workout: {e}")
            raise Exception(f"Failed to schedule workout: {e}")
