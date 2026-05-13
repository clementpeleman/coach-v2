"""Web app endpoints for auth and chat."""
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import UserProfile

router = APIRouter(prefix="/web", tags=["web"])


class WebLoginRequest(BaseModel):
    email: str
    display_name: Optional[str] = Field(default=None, max_length=120)


class WebLoginResponse(BaseModel):
    user_id: int
    email: str
    display_name: Optional[str] = None
    created: bool


class WebMeResponse(BaseModel):
    user_id: int
    email: Optional[str] = None
    display_name: Optional[str] = None
    garmin_connected: bool


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: int
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


def _create_next_user_id(db: Session) -> int:
    current_max = db.query(func.max(UserProfile.user_id)).scalar()
    if current_max is None:
        return int(datetime.utcnow().timestamp() * 1000)
    return int(current_max) + 1


@router.post("/auth/login", response_model=WebLoginResponse)
async def web_login(payload: WebLoginRequest, db: Session = Depends(get_db)):
    """Login/create a web user by email."""
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid email address")

    user = db.query(UserProfile).filter(UserProfile.garmin_email == email).first()
    created = False

    if not user:
        user = UserProfile(
            user_id=_create_next_user_id(db),
            garmin_email=email,
            phone_number=payload.display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created = True
    elif payload.display_name and payload.display_name != user.phone_number:
        user.phone_number = payload.display_name
        db.commit()
        db.refresh(user)

    return WebLoginResponse(
        user_id=user.user_id,
        email=email,
        display_name=user.phone_number,
        created=created,
    )


@router.get("/auth/me", response_model=WebMeResponse)
async def web_me(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return WebMeResponse(
        user_id=user.user_id,
        email=user.garmin_email,
        display_name=user.phone_number,
        garmin_connected=bool(user.garmin_user_id),
    )


@router.post("/chat", response_model=ChatResponse)
async def web_chat(payload: ChatRequest):
    """Chat with the existing coach agent."""
    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from app.agents.conversational_agent import create_conversational_agent
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Chat dependencies not available: {exc}",
        ) from exc

    try:
        chat_history = []
        for item in payload.history:
            if item.role == "assistant":
                chat_history.append(AIMessage(content=item.content))
            else:
                chat_history.append(HumanMessage(content=item.content))

        agent_executor = create_conversational_agent(
            user_id=payload.user_id, current_date=date.today().isoformat()
        )
        result = agent_executor.invoke({"input": payload.message, "chat_history": chat_history})
        return ChatResponse(reply=result["output"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
