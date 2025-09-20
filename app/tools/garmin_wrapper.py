import logging
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

    def logout(self):
        """Log out from Garmin Connect."""
        try:
            self.client.logout()
            logger.info("Successfully logged out from Garmin Connect.")
        except Exception as e:
            logger.error(f"Failed to log out: {e}")
