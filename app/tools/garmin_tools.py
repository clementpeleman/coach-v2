"""Garmin tools for fetching health and activity data via OAuth API."""
import datetime
import json
import logging
from typing import List, Optional
from sqlalchemy import and_
from app.database.database import SessionLocal
from app.database.models import GarminHealthData, GarminActivityData, GarminToken

logger = logging.getLogger(__name__)


def get_health_data(
    user_id: int,
    data_types: List[str],
    start_date: str,
    end_date: Optional[str] = None,
    days: Optional[int] = None
) -> str:
    """
    Fetch health and activity data from the database.

    This unified tool can fetch multiple data types at once for efficient querying.
    Data types can include: dailies, sleeps, stress, activities, epochs, hrv, etc.

    Args:
        user_id: Telegram user ID
        data_types: List of data types to fetch. Options:
            - "dailies": Daily summaries (steps, calories, heart rate, etc.)
            - "sleeps": Sleep data (duration, phases, sleep score)
            - "stress": Stress levels throughout the day
            - "activities": Workouts and exercises
            - "epochs": 15-minute granular data
            - "hrv": Heart rate variability
            - "all": Fetch all available data types
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: Optional end date. If not provided, uses start_date + days
        days: Optional number of days to fetch. Defaults to 1 if end_date not provided

    Returns:
        Human-readable summary of the requested data
    """
    try:
        db = SessionLocal()

        # Parse dates
        try:
            start = datetime.datetime.fromisoformat(start_date).date()
            if end_date:
                end = datetime.datetime.fromisoformat(end_date).date()
            elif days:
                end = start + datetime.timedelta(days=days - 1)
            else:
                end = start
        except ValueError as e:
            return f"Error: Invalid date format: {e}. Please use YYYY-MM-DD."

        # Check if user has OAuth token
        token = db.query(GarminToken).filter(GarminToken.user_id == user_id).first()
        if not token:
            db.close()
            return "Error: No Garmin connection found. Please use /garmin_connect to link your account."

        # Map "all" to all available types
        if "all" in data_types:
            data_types = ["dailies", "sleeps", "stress", "activities"]

        # Convert to database field names
        type_mapping = {
            "dailies": "dailies",
            "sleeps": "sleeps",
            "stress": "stressDetails",
            "activities": "activities",
            "epochs": "epochs",
            "hrv": "hrv"
        }

        results = {}

        # Fetch health data (dailies, sleeps, stress, etc.)
        health_types = [t for t in data_types if t in ["dailies", "sleeps", "stress", "epochs", "hrv"]]
        if health_types:
            db_types = [type_mapping[t] for t in health_types]

            # For dailies, filter by calendar_date (more accurate)
            # For others, filter by start_time
            if "dailies" in data_types:
                health_data = db.query(GarminHealthData).filter(
                    and_(
                        GarminHealthData.user_id == user_id,
                        GarminHealthData.summary_type == "dailies",
                        GarminHealthData.calendar_date >= start.isoformat(),
                        GarminHealthData.calendar_date <= end.isoformat()
                    )
                ).order_by(GarminHealthData.calendar_date).all()

                for item in health_data:
                    if item.summary_type not in results:
                        results[item.summary_type] = []
                    results[item.summary_type].append(json.loads(item.data))

            # For other health types (sleep, stress, etc.), use start_time
            other_types = [t for t in health_types if t != "dailies"]
            if other_types:
                db_other_types = [type_mapping[t] for t in other_types]
                health_data = db.query(GarminHealthData).filter(
                    and_(
                        GarminHealthData.user_id == user_id,
                        GarminHealthData.summary_type.in_(db_other_types),
                        GarminHealthData.start_time >= datetime.datetime.combine(start, datetime.time.min),
                        GarminHealthData.start_time <= datetime.datetime.combine(end, datetime.time.max)
                    )
                ).order_by(GarminHealthData.start_time).all()

                for item in health_data:
                    if item.summary_type not in results:
                        results[item.summary_type] = []
                    results[item.summary_type].append(json.loads(item.data))

        # Fetch activity data
        if "activities" in data_types:
            activity_data = db.query(GarminActivityData).filter(
                and_(
                    GarminActivityData.user_id == user_id,
                    GarminActivityData.start_time >= datetime.datetime.combine(start, datetime.time.min),
                    GarminActivityData.start_time <= datetime.datetime.combine(end, datetime.time.max)
                )
            ).order_by(GarminActivityData.start_time).all()

            results["activities"] = [json.loads(item.data) for item in activity_data]

        # Check if any data was found
        if not results or all(len(v) == 0 for v in results.values()):
            # No data in database - try fetching from Garmin API
            logger.info(f"No data in database for user {user_id}, fetching from Garmin API...")

            try:
                from app.tools.garmin_client import GarminAPIClient
                from datetime import datetime as dt

                # Calculate timestamps for API request
                start_timestamp = int(dt.combine(start, dt.min.time()).timestamp())
                end_timestamp = int(dt.combine(end, dt.max.time()).timestamp())

                # Initialize Garmin API client
                client = GarminAPIClient(db, user_id)

                # Fetch data from Garmin API
                if "dailies" in data_types or "all" in data_types:
                    client.get_dailies(start_timestamp, end_timestamp, store=True)

                if "sleeps" in data_types or "all" in data_types:
                    client.get_sleeps(start_timestamp, end_timestamp, store=True)

                if "stress" in data_types or "all" in data_types:
                    client.get_stress_details(start_timestamp, end_timestamp, store=True)

                if "activities" in data_types or "all" in data_types:
                    client.get_activities(start_timestamp, end_timestamp, store=True)

                if "epochs" in data_types or "all" in data_types:
                    client.get_epochs(start_timestamp, end_timestamp, store=True)

                if "hrv" in data_types or "all" in data_types:
                    client.get_hrv(start_timestamp, end_timestamp, store=True)

                logger.info(f"Successfully fetched and stored data from Garmin API for user {user_id}")

                # Now query the database again
                health_types = [t for t in data_types if t in ["dailies", "sleeps", "stress", "epochs", "hrv"]]
                if health_types:
                    # For dailies, filter by calendar_date
                    if "dailies" in data_types:
                        health_data = db.query(GarminHealthData).filter(
                            and_(
                                GarminHealthData.user_id == user_id,
                                GarminHealthData.summary_type == "dailies",
                                GarminHealthData.calendar_date >= start.isoformat(),
                                GarminHealthData.calendar_date <= end.isoformat()
                            )
                        ).order_by(GarminHealthData.calendar_date).all()

                        for item in health_data:
                            if item.summary_type not in results:
                                results[item.summary_type] = []
                            results[item.summary_type].append(json.loads(item.data))

                    # For other health types, use start_time
                    other_types = [t for t in health_types if t != "dailies"]
                    if other_types:
                        db_other_types = [type_mapping[t] for t in other_types]
                        health_data = db.query(GarminHealthData).filter(
                            and_(
                                GarminHealthData.user_id == user_id,
                                GarminHealthData.summary_type.in_(db_other_types),
                                GarminHealthData.start_time >= dt.combine(start, dt.min.time()),
                                GarminHealthData.start_time <= dt.combine(end, dt.max.time())
                            )
                        ).order_by(GarminHealthData.start_time).all()

                        for item in health_data:
                            if item.summary_type not in results:
                                results[item.summary_type] = []
                            results[item.summary_type].append(json.loads(item.data))

                if "activities" in data_types or "all" in data_types:
                    activity_data = db.query(GarminActivityData).filter(
                        and_(
                            GarminActivityData.user_id == user_id,
                            GarminActivityData.start_time >= dt.combine(start, dt.min.time()),
                            GarminActivityData.start_time <= dt.combine(end, dt.max.time())
                        )
                    ).order_by(GarminActivityData.start_time).all()

                    results["activities"] = [json.loads(item.data) for item in activity_data]

                # Check if we got any data after fetching
                if not results or all(len(v) == 0 for v in results.values()):
                    db.close()
                    return f"No data available from Garmin for {start_date} to {end_date or start_date}.\n\nThis could mean:\n- No data was recorded on your Garmin device for these dates\n- Your device hasn't synced with Garmin Connect yet\n- The date range might be too far in the past"

            except Exception as e:
                db.close()
                logger.error(f"Failed to fetch from Garmin API: {e}")
                return f"No data found in database and failed to fetch from Garmin API: {str(e)}\n\nPlease try syncing your Garmin device with Garmin Connect."

        db.close()

        # Build human-readable summary
        return _format_health_summary(results, start_date, end_date or start_date)

    except Exception as e:
        if 'db' in locals():
            db.close()
        return f"Error: Unexpected error fetching health data: {str(e)}"


def _format_health_summary(results: dict, start_date: str, end_date: str) -> str:
    """Format health data into a human-readable summary."""
    summary_lines = []

    date_range = f"{start_date}" if start_date == end_date else f"{start_date} tot {end_date}"
    summary_lines.append(f"Gezondheidsdata voor {date_range}:\n")

    # Format dailies (daily summaries)
    if "dailies" in results and results["dailies"]:
        summary_lines.append("DAGELIJKSE SAMENVATTINGEN")
        for daily in results["dailies"]:
            date = daily.get("calendarDate", "Onbekend")
            steps = daily.get("steps", 0)
            distance_m = daily.get("distanceInMeters", 0)
            distance_km = round(distance_m / 1000, 2) if distance_m else 0
            calories = daily.get("activeKilocalories", 0)
            floors = daily.get("floorsClimbed", 0)
            avg_hr = daily.get("averageHeartRateInBeatsPerMinute")
            resting_hr = daily.get("restingHeartRateInBeatsPerMinute")

            summary_lines.append(f"\n{date}:")
            summary_lines.append(f"  Stappen: {steps:,}")
            if distance_km > 0:
                summary_lines.append(f"  Afstand: {distance_km} km")
            if calories > 0:
                summary_lines.append(f"  Actieve calorieën: {calories} kcal")
            if floors > 0:
                summary_lines.append(f"  Verdiepingen: {floors}")
            if avg_hr:
                summary_lines.append(f"  Gemiddelde hartslag: {avg_hr} bpm")
            if resting_hr:
                summary_lines.append(f"  Rusthartslag: {resting_hr} bpm")
        summary_lines.append("")

    # Format sleep data
    if "sleeps" in results and results["sleeps"]:
        summary_lines.append("SLAAPDATA")
        for sleep in results["sleeps"]:
            date = sleep.get("calendarDate", "Onbekend")
            duration_sec = sleep.get("durationInSeconds", 0)
            duration_hours = round(duration_sec / 3600, 1) if duration_sec else 0

            deep_sec = sleep.get("deepSleepDurationInSeconds", 0)
            deep_min = int(deep_sec / 60) if deep_sec else 0

            light_sec = sleep.get("lightSleepDurationInSeconds", 0)
            light_min = int(light_sec / 60) if light_sec else 0

            rem_sec = sleep.get("remSleepInSeconds", 0)
            rem_min = int(rem_sec / 60) if rem_sec else 0

            awake_sec = sleep.get("awakeDurationInSeconds", 0)
            awake_min = int(awake_sec / 60) if awake_sec else 0

            sleep_score = sleep.get("overallSleepScore", {}).get("value") or sleep.get("sleepScores", {}).get("overall", {}).get("value")

            summary_lines.append(f"\n{date}:")
            summary_lines.append(f"  Totale slaap: {duration_hours} uur")
            summary_lines.append(f"  Diepe slaap: {deep_min} min")
            summary_lines.append(f"  Lichte slaap: {light_min} min")
            summary_lines.append(f"  REM slaap: {rem_min} min")
            summary_lines.append(f"  Wakker: {awake_min} min")
            if sleep_score:
                summary_lines.append(f"  Slaapscore: {sleep_score}/100")
        summary_lines.append("")

    # Format stress data
    if "stressDetails" in results and results["stressDetails"]:
        summary_lines.append("STRESSDATA")
        for stress in results["stressDetails"]:
            date = stress.get("calendarDate", "Onbekend")
            avg_stress = stress.get("avgStressLevel")
            max_stress = stress.get("maxStressLevel")

            rest_sec = stress.get("restStressDurationInSeconds", 0)
            rest_min = int(rest_sec / 60) if rest_sec else 0

            low_sec = stress.get("lowStressDurationInSeconds", 0)
            low_min = int(low_sec / 60) if low_sec else 0

            med_sec = stress.get("mediumStressDurationInSeconds", 0)
            med_min = int(med_sec / 60) if med_sec else 0

            high_sec = stress.get("highStressDurationInSeconds", 0)
            high_min = int(high_sec / 60) if high_sec else 0

            summary_lines.append(f"\n{date}:")
            if avg_stress:
                summary_lines.append(f"  Gemiddelde stress: {avg_stress}")
            if max_stress:
                summary_lines.append(f"  Max stress: {max_stress}")
            summary_lines.append(f"  Rusttijd: {rest_min} min")
            summary_lines.append(f"  Lage stress: {low_min} min")
            summary_lines.append(f"  Gemiddelde stress: {med_min} min")
            summary_lines.append(f"  Hoge stress: {high_min} min")
        summary_lines.append("")

    # Format activities
    if "activities" in results and results["activities"]:
        summary_lines.append("ACTIVITEITEN")
        for activity in results["activities"]:
            activity_type = activity.get("activityType", "Onbekend")
            activity_name = activity.get("activityName", activity_type)
            start_time = activity.get("startTimeInSeconds")
            date = datetime.datetime.utcfromtimestamp(start_time).strftime("%Y-%m-%d %H:%M") if start_time else "Onbekend"

            duration_sec = activity.get("durationInSeconds", 0)
            duration_min = int(duration_sec / 60) if duration_sec else 0

            distance_m = activity.get("distanceInMeters")
            distance_km = round(distance_m / 1000, 2) if distance_m else 0

            calories = activity.get("activeKilocalories")
            avg_hr = activity.get("averageHeartRateInBeatsPerMinute")
            max_hr = activity.get("maxHeartRateInBeatsPerMinute")

            summary_lines.append(f"\n{date} - {activity_name}")
            if duration_min > 0:
                summary_lines.append(f"  Duur: {duration_min} min")
            if distance_km > 0:
                summary_lines.append(f"  Afstand: {distance_km} km")
            if calories:
                summary_lines.append(f"  Calorieën: {calories} kcal")
            if avg_hr:
                summary_lines.append(f"  Gemiddelde HS: {avg_hr} bpm")
            if max_hr:
                summary_lines.append(f"  Max HS: {max_hr} bpm")
        summary_lines.append("")

    return "\n".join(summary_lines)


def get_user_info(user_id: int) -> str:
    """Get basic user info from Garmin OAuth token."""
    try:
        db = SessionLocal()
        token = db.query(GarminToken).filter(GarminToken.user_id == user_id).first()
        db.close()

        if not token:
            return "Error: No Garmin connection found. Please use /garmin_connect to link your account."

        return f"Garmin User ID: {token.garmin_user_id}\nConnected since: {token.created_at.strftime('%Y-%m-%d')}"

    except Exception as e:
        if 'db' in locals():
            db.close()
        return f"Error: {str(e)}"
