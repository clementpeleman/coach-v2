import datetime
from collections import Counter
from app.database import crud, schemas
from app.database.database import SessionLocal

SPORT_ACTIVITY_TYPES = [
    'running', 'cycling', 'swimming', 'walking', 'hiking', 'strength_training', 'cardio', 'yoga', 'pilates'
]

def analyze_and_summarize_user_activities(user_id: int) -> str:
    """
    Analyzes the user's activities and provides a summary of their profile.
    This includes preferred activity type, activity frequency, and typical duration and distance.
    """
    try:
        db = SessionLocal()
        all_activities = crud.get_activities_by_user(db, user_id=user_id, limit=100) # Analyze last 100 activities
        db.close()
    except Exception as e:
        return f"Error fetching activities from database: {str(e)}"

    # Filter for sports activities with a minimum duration
    activities = [
        a for a in all_activities 
        if a.activity_type in SPORT_ACTIVITY_TYPES and a.duration and a.duration > 300 # More than 5 minutes
    ]

    if not activities or len(activities) < 3: # Require at least 3 sport activities for a meaningful profile
        return "Not enough sport activity data to create a profile. Please record more sport activities."

    # Get top 2 activity types
    activity_types = [a.activity_type for a in activities]
    top_activity_types = [item[0] for item in Counter(activity_types).most_common(2)]

    summary_str = f"Based on your last {len(activities)} sport activities, here is a summary of your profile:\n"

    for activity_type in top_activity_types:
        activities_of_type = [a for a in activities if a.activity_type == activity_type]
        
        # Activity frequency
        oldest_activity = min(a.start_time for a in activities_of_type)
        latest_activity = max(a.start_time for a in activities_of_type)
        duration_weeks = (latest_activity - oldest_activity).days / 7
        activity_frequency = len(activities_of_type) / duration_weeks if duration_weeks > 0 else len(activities_of_type)

        # Typical duration and distance
        activities_with_duration = [a for a in activities_of_type if a.duration]
        activities_with_distance = [a for a in activities_of_type if a.distance]

        total_duration = sum(a.duration for a in activities_with_duration)
        total_distance = sum(a.distance for a in activities_with_distance)

        typical_activity_duration = (total_duration / len(activities_with_duration)) / 60 if activities_with_duration else 0 # In minutes
        typical_activity_distance = (total_distance / len(activities_with_distance)) / 1000 if activities_with_distance else 0 # In kilometers

        summary_str += (
            f"\n**{activity_type.replace('_', ' ').title()}**\n"
            f"- Frequency: {activity_frequency:.1f} activities per week\n"
            f"- Typical Duration: {typical_activity_duration:.0f} minutes\n"
            f"- Typical Distance: {typical_activity_distance:.2f} km\n"
        )

        # Store summary for the most preferred activity type
        if activity_type == top_activity_types[0]:
            try:
                summary = schemas.UserSummaryCreate(
                    preferred_activity_type=activity_type,
                    activity_frequency=activity_frequency,
                    typical_activity_duration=typical_activity_duration,
                    typical_activity_distance=typical_activity_distance,
                )
                db = SessionLocal()
                crud.create_or_update_user_summary(db, user_id=user_id, summary=summary)
                db.close()
            except Exception as e:
                # Log error but don't fail the entire analysis
                summary_str += f"\n⚠️ Warning: Could not save summary to database: {str(e)}\n"

    # Generate activities list for debugging
    activities_list_str = "\n\nAnalyzed Activities:\n"
    for act in activities:
        activities_list_str += f"- {act.activity_type} on {act.start_time.strftime('%Y-%m-%d')}, distance: {act.distance/1000:.2f} km, duration: {act.duration/60:.0f} min\n"

    # return activities_list_str + "\n" + summary_str
    return summary_str
