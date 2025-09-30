from app.agents.state import AgentState
from app.database import crud
from app.database.database import SessionLocal

def handle_garmin_credentials(state: AgentState):
    print("---HANDLE GARMIN CREDENTIALS---")
    try:
        email, password = state["messages"][-1].split()
        db = SessionLocal()
        crud.update_user_garmin_credentials(db, user_id=state["user_id"], email=email, password=password)
        db.close()
        return {"messages": ["Bedankt! Je bent nu ingelogd op je Garmin-account. Hoe kan ik je helpen?"]}
    except ValueError:
        return {"messages": ["Ik kon je gegevens niet verwerken. Gebruik het formaat: /login <email> <wachtwoord>"]}
