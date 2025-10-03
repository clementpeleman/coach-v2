import datetime
from app.tools.garmin_wrapper import GarminWrapper
from app.database import crud, schemas
from app.database.database import SessionLocal
from app.utils.security import decrypt_password

def get_garmin_wrapper(user_id: int) -> GarminWrapper | None:
    db = SessionLocal()
    user = crud.get_user(db, user_id=user_id)
    db.close()
    if not user or not user.garmin_email or not user.garmin_password:
        return None
    # Decrypt password before using it
    decrypted_password = decrypt_password(user.garmin_password)
    return GarminWrapper(user.garmin_email, decrypted_password)

def get_activities(user_id: int, start_date: str, end_date: str) -> str:
    """Fetch activities from Garmin Connect within a date range. Returns a compact summary.

    Dates should be in ISO format (YYYY-MM-DD).
    Returns a human-readable summary instead of raw JSON to reduce token usage.
    """
    try:
        wrapper = get_garmin_wrapper(user_id)
        if not wrapper:
            return "Error: User not found or Garmin credentials not configured."

        if not wrapper.login():
            return "Error: Garmin login failed. Please check your credentials."

        try:
            start = datetime.datetime.fromisoformat(start_date).date()
            end = datetime.datetime.fromisoformat(end_date).date()
        except ValueError as e:
            return f"Error: Invalid date format: {e}. Please use YYYY-MM-DD."

        activities = wrapper.get_activities(start, end)
        wrapper.logout()

        if not activities:
            return f"No activities found between {start_date} and {end_date}."

        # Store activities in database
        db = SessionLocal()
        try:
            for activity in activities:
                try:
                    activity_create = schemas.ActivityCreate(
                        activity_id=activity["activityId"],
                        user_id=user_id,
                        activity_type=activity["activityType"]["typeKey"],
                        start_time=datetime.datetime.fromisoformat(activity["startTimeLocal"]),
                        duration=activity.get("duration"),
                        distance=activity.get("distance"),
                    )
                    crud.create_activity(db, activity=activity_create)
                except Exception as e:
                    print(f"Error storing activity {activity.get('activityId')}: {e}")
        finally:
            db.close()

        # Create compact summary
        summary_lines = [f"Found {len(activities)} activities from {start_date} to {end_date}:\n"]

        for activity in activities:
            activity_type = activity.get("activityType", {}).get("typeKey", "Unknown")
            date = activity.get("startTimeLocal", "")[:10]  # Just date, not time
            duration_sec = activity.get("duration", 0)
            duration_min = int(duration_sec / 60) if duration_sec else 0
            distance_m = activity.get("distance")
            distance_km = round(distance_m / 1000, 2) if distance_m else 0

            # Build compact line
            line = f"- {date}: {activity_type}"
            if distance_km > 0:
                line += f", {distance_km} km"
            if duration_min > 0:
                line += f", {duration_min} min"

            # Add relevant metrics
            avg_hr = activity.get("averageHR")
            if avg_hr:
                line += f", avg HR {int(avg_hr)}"

            avg_speed_mps = activity.get("averageSpeed")
            if avg_speed_mps:
                avg_pace_min_per_km = 1000 / (avg_speed_mps * 60) if avg_speed_mps > 0 else 0
                if avg_pace_min_per_km > 0:
                    pace_min = int(avg_pace_min_per_km)
                    pace_sec = int((avg_pace_min_per_km - pace_min) * 60)
                    line += f", {pace_min}:{pace_sec:02d}/km"

            summary_lines.append(line)

        return "\n".join(summary_lines)

    except Exception as e:
        return f"Error: Unexpected error fetching activities: {str(e)}"

def get_sleep_data(user_id: int, date: str) -> str:
    """Fetch sleep data for a specific date. Returns a compact summary.

    Date should be in ISO format (YYYY-MM-DD).
    Returns only relevant sleep metrics to reduce token usage.
    """
    try:
        wrapper = get_garmin_wrapper(user_id)
        if not wrapper:
            return "Error: User not found or Garmin credentials not configured."

        if not wrapper.login():
            return "Error: Garmin login failed. Please check your credentials."

        try:
            sleep_date = datetime.datetime.fromisoformat(date).date()
        except ValueError as e:
            return f"Error: Invalid date format: {e}. Please use YYYY-MM-DD."

        sleep_data = wrapper.get_sleep_data(sleep_date)
        wrapper.logout()

        if not sleep_data or "dailySleepDTO" not in sleep_data:
            return f"No sleep data found for {date}."

        # Extract only relevant fields
        daily_sleep = sleep_data.get("dailySleepDTO", {})

        total_sleep_sec = daily_sleep.get("sleepTimeSeconds", 0)
        total_sleep_hours = round(total_sleep_sec / 3600, 1) if total_sleep_sec else 0

        deep_sleep_sec = daily_sleep.get("deepSleepSeconds", 0)
        deep_sleep_min = int(deep_sleep_sec / 60) if deep_sleep_sec else 0

        light_sleep_sec = daily_sleep.get("lightSleepSeconds", 0)
        light_sleep_min = int(light_sleep_sec / 60) if light_sleep_sec else 0

        rem_sleep_sec = daily_sleep.get("remSleepSeconds", 0)
        rem_sleep_min = int(rem_sleep_sec / 60) if rem_sleep_sec else 0

        awake_sec = daily_sleep.get("awakeSeconds", 0)
        awake_min = int(awake_sec / 60) if awake_sec else 0

        sleep_score = daily_sleep.get("sleepScores", {}).get("overall", {}).get("value")

        # Build compact summary
        summary = f"Sleep data for {date}:\n"
        summary += f"- Total sleep: {total_sleep_hours} hours\n"
        summary += f"- Deep sleep: {deep_sleep_min} min\n"
        summary += f"- Light sleep: {light_sleep_min} min\n"
        summary += f"- REM sleep: {rem_sleep_min} min\n"
        summary += f"- Awake: {awake_min} min\n"

        if sleep_score:
            summary += f"- Sleep score: {sleep_score}/100"

        return summary

    except Exception as e:
        return f"Error: Unexpected error fetching sleep data: {str(e)}"

def get_stress_data(user_id: int, date: str) -> str:
    """Fetch stress data for a specific date. Returns a compact summary.

    Date should be in ISO format (YYYY-MM-DD).
    Returns only relevant stress metrics to reduce token usage.
    """
    try:
        wrapper = get_garmin_wrapper(user_id)
        if not wrapper:
            return "Error: User not found or Garmin credentials not configured."

        if not wrapper.login():
            return "Error: Garmin login failed. Please check your credentials."

        try:
            stress_date = datetime.datetime.fromisoformat(date).date()
        except ValueError as e:
            return f"Error: Invalid date format: {e}. Please use YYYY-MM-DD."

        stress_data = wrapper.get_stress_data(stress_date)
        wrapper.logout()

        if not stress_data:
            return f"No stress data found for {date}."

        # Extract relevant metrics
        avg_stress = stress_data.get("avgStressLevel")
        max_stress = stress_data.get("maxStressLevel")
        rest_time_sec = stress_data.get("restStressSeconds", 0)
        rest_time_min = int(rest_time_sec / 60) if rest_time_sec else 0

        low_stress_sec = stress_data.get("lowStressSeconds", 0)
        low_stress_min = int(low_stress_sec / 60) if low_stress_sec else 0

        medium_stress_sec = stress_data.get("mediumStressSeconds", 0)
        medium_stress_min = int(medium_stress_sec / 60) if medium_stress_sec else 0

        high_stress_sec = stress_data.get("highStressSeconds", 0)
        high_stress_min = int(high_stress_sec / 60) if high_stress_sec else 0

        # Build compact summary
        summary = f"Stress data for {date}:\n"
        if avg_stress:
            summary += f"- Average stress level: {avg_stress}\n"
        if max_stress:
            summary += f"- Max stress level: {max_stress}\n"
        summary += f"- Rest time: {rest_time_min} min\n"
        summary += f"- Low stress: {low_stress_min} min\n"
        summary += f"- Medium stress: {medium_stress_min} min\n"
        summary += f"- High stress: {high_stress_min} min"

        return summary

    except Exception as e:
        return f"Error: Unexpected error fetching stress data: {str(e)}"

def get_user_info(user_id: int) -> str:
    """Fetch user's full name from Garmin Connect."""
    try:
        wrapper = get_garmin_wrapper(user_id)
        if not wrapper:
            return "Error: User not found or Garmin credentials not configured."

        if not wrapper.login():
            return "Error: Garmin login failed. Please check your credentials."

        full_name = wrapper.get_full_name()
        wrapper.logout()
        return f"User's full name: {full_name}" if full_name else "Error: Could not retrieve user information."

    except Exception as e:
        return f"Error: Unexpected error fetching user info: {str(e)}"
