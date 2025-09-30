import logging
import datetime
from garminconnect import Garmin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GarminWrapper:
    """A wrapper class for the garminconnect library."""

    def __init__(self, email, password):
        """Initialize the Garmin client."""
        self.client = Garmin(email, password)

    def login(self):
        """Log in to Garmin Connect."""
        try:
            self.client.login()
            logger.info("Successfully logged in to Garmin Connect.")
            return True
        except Exception as e:
            logger.error(f"Failed to log in to Garmin Connect: {e}")
            return False

    def get_activities(self, start_date, end_date):
        """Fetch activities from Garmin Connect within a date range."""
        try:
            activities = self.client.get_activities_by_date(
                start_date.isoformat(), end_date.isoformat()
            )
            logger.info(f"Fetched {len(activities)} activities.")
            return activities
        except Exception as e:
            logger.error(f"Failed to fetch activities: {e}")
            return []

    def get_sleep_data(self, date):
        """Fetch sleep data for a specific date."""
        try:
            sleep_data = self.client.get_sleep_data(date.isoformat())
            logger.info(f"Fetched sleep data for {date}.")
            return sleep_data
        except Exception as e:
            logger.error(f"Failed to fetch sleep data: {e}")
            return None

    def get_stress_data(self, date):
        """Fetch stress data for a specific date."""
        try:
            stress_data = self.client.get_stress_data(date.isoformat())
            logger.info(f"Fetched stress data for {date}.")
            return stress_data
        except Exception as e:
            logger.error(f"Failed to fetch stress data: {e}")
            return None

    def get_full_name(self):
        """Fetch user's full name."""
        try:
            full_name = self.client.get_full_name()
            logger.info(f"Fetched full name: {full_name}.")
            return full_name
        except Exception as e:
            logger.error(f"Failed to fetch full name: {e}")
            return None

    def logout(self):
        """Log out from Garmin Connect."""
        try:
            self.client.logout()
            logger.info("Successfully logged out from Garmin Connect.")
        except Exception as e:
            logger.error(f"Failed to log out: {e}")
