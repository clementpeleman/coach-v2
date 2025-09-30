from app.database import crud
from app.database.database import SessionLocal

def get_user_activities(user_id: int):
    """Get the activities for a user from the database."""
    db = SessionLocal()
    activities = crud.get_activities_by_user(db, user_id=user_id)
    db.close()
    # We need to convert the SQLAlchemy objects to dicts to make them serializable
    return [{"activity_id": a.activity_id, "activity_type": a.activity_type, "start_time": a.start_time.isoformat()} for a in activities]
