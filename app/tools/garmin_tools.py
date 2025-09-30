import datetime
from app.tools.garmin_wrapper import GarminWrapper
from app.database import crud
from app.database.database import SessionLocal

def get_garmin_wrapper(user_id: int) -> GarminWrapper | None:
    db = SessionLocal()
    user = crud.get_user(db, user_id=user_id)
    db.close()
    if not user or not user.garmin_email or not user.garmin_password:
        return None
    return GarminWrapper(user.garmin_email, user.garmin_password)

def get_activities(user_id: int, start_date: str, end_date: str) -> list:
    """Fetch activities from Garmin Connect within a date range. Dates should be in ISO format (YYYY-MM-DD)."""
    wrapper = get_garmin_wrapper(user_id)
    if not wrapper or not wrapper.login():
        return [{"error": "Garmin login failed."}]
    
    try:
        start = datetime.datetime.fromisoformat(start_date).date()
        end = datetime.datetime.fromisoformat(end_date).date()
    except ValueError:
        return [{"error": "Invalid date format. Please use YYYY-MM-DD."}]
    
    activities = wrapper.get_activities(start, end)
    wrapper.logout()

    db = SessionLocal()
    for activity in activities:
        activity_create = schemas.ActivityCreate(
            activity_id=activity["activityId"],
            user_id=user_id,
            activity_type=activity["activityType"]["typeKey"],
            start_time=datetime.datetime.fromisoformat(activity["startTimeLocal"]),
            duration=activity.get("duration"),
            distance=activity.get("distance"),
        )
        crud.create_activity(db, activity=activity_create)
    db.close()

    for activity in activities:
        if 'averageSpeed' in activity and activity['averageSpeed'] is not None:
            activity['averageSpeed'] *= 3.6
        if 'maxSpeed' in activity and activity['maxSpeed'] is not None:
            activity['maxSpeed'] *= 3.6

    return activities

def get_sleep_data(user_id: int, date: str) -> dict:
    """Fetch sleep data for a specific date. Date should be in ISO format (YYYY-MM-DD)."""
    wrapper = get_garmin_wrapper(user_id)
    if not wrapper or not wrapper.login():
        return {"error": "Garmin login failed."}
    
    try:
        sleep_date = datetime.datetime.fromisoformat(date).date()
    except ValueError:
        return {"error": "Invalid date format. Please use YYYY-MM-DD."}
    
    sleep_data = wrapper.get_sleep_data(sleep_date)
    wrapper.logout()
    return sleep_data

def get_stress_data(user_id: int, date: str) -> dict:
    """Fetch stress data for a specific date. Date should be in ISO format (YYYY-MM-DD)."""
    wrapper = get_garmin_wrapper(user_id)
    if not wrapper or not wrapper.login():
        return {"error": "Garmin login failed."}
    
    try:
        stress_date = datetime.datetime.fromisoformat(date).date()
    except ValueError:
        return {"error": "Invalid date format. Please use YYYY-MM-DD."}
    
    stress_data = wrapper.get_stress_data(stress_date)
    wrapper.logout()
    return stress_data

def get_user_info(user_id: int) -> dict:
    """Fetch user's full name from Garmin Connect."""
    wrapper = get_garmin_wrapper(user_id)
    if not wrapper or not wrapper.login():
        return {"error": "Garmin login failed."}
    
    full_name = wrapper.get_full_name()
    wrapper.logout()
    return {"full_name": full_name}
