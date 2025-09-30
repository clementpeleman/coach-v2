import datetime

def get_current_date() -> str:
    """Returns the current date in ISO format (YYYY-MM-DD)."""
    return datetime.date.today().isoformat()
