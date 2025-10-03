from app.database import crud
from app.database.database import SessionLocal

def delete_user_data(user_id: int) -> str:
    """Deletes all data associated with the user."""
    try:
        db = SessionLocal()
        crud.delete_user_data(db, user_id=user_id)
        db.close()
        return "All your data has been deleted successfully."
    except Exception as e:
        return f"Error deleting user data: {str(e)}. Please try again or contact support."
