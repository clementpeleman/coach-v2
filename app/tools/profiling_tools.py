import datetime
from collections import Counter
from app.database import crud, schemas
from app.database.database import SessionLocal

def analyze_and_summarize_user_activities(user_id: int) -> str:
    """
    Analyzes the user's activities and provides a summary of their profile.
    This includes preferred activity type, activity frequency, and typical duration and distance.
    """
    db = SessionLocal()
    activities = crud.get_activities_by_user(db, user_id=user_id, limit=100) # Analyze last 100 activities
    db.close()

    if not activities or len(activities) < 5: # Require at least 5 activities for a meaningful profile
        return "Not enough activity data to create a profile. Please record more activities."

    # Preferred activity type
    activity_types = [a.activity_type for a in activities]
    preferred_activity_type = Counter(activity_types).most_common(1)[0][0]

    # Activity frequency
    oldest_activity = min(a.start_time for a in activities)
    latest_activity = max(a.start_time for a in activities)
    duration_weeks = (latest_activity - oldest_activity).days / 7
    activity_frequency = len(activities) / duration_weeks if duration_weeks > 0 else len(activities)

    # Typical duration and distance
    total_duration = sum(a.duration for a in activities if a.duration)
    total_distance = sum(a.distance for a in activities if a.distance)
    typical_activity_duration = (total_duration / len(activities)) / 60 if total_duration else 0 # In minutes
    typical_activity_distance = (total_distance / len(activities)) / 1000 if total_distance else 0 # In kilometers

    # Create summary object
    summary = schemas.UserSummaryCreate(
        preferred_activity_type=preferred_activity_type,
        activity_frequency=activity_frequency,
        typical_activity_duration=typical_activity_duration,
        typical_activity_distance=typical_activity_distance,
    )

    # Store summary in the database
    db = SessionLocal()
    crud.create_or_update_user_summary(db, user_id=user_id, summary=summary)
    db.close()

    # Generate summary string
    summary_str = (
        f"Based on your last {len(activities)} activities, here is a summary of your profile:\n\n"
        f"- **Preferred Activity Type:** {preferred_activity_type.replace('_', ' ').title()}\n"
        f"- **Activity Frequency:** {activity_frequency:.1f} activities per week\n"
        f"- **Typical Duration:** {typical_activity_duration:.0f} minutes\n"
        f"- **Typical Distance:** {typical_activity_distance:.2f} km"
    )

    return summary_str
