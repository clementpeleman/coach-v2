"""Web app endpoints for auth and chat."""
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database.database import get_db
from app.database.models import OAuthSession, UserProfile
from app.tools.garmin_oauth import GarminOAuthService

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


class GarminDirectStartRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = Field(default=None, max_length=120)


class GarminDirectStartResponse(BaseModel):
    user_id: int
    authorization_url: str
    state: str


def _create_next_user_id(db: Session) -> int:
    current_max = db.query(func.max(UserProfile.user_id)).scalar()
    if current_max is None:
        return int(datetime.utcnow().timestamp() * 1000)
    return int(current_max) + 1


def _create_or_reuse_user(db: Session, email: Optional[str], display_name: Optional[str]) -> UserProfile:
    normalized_email: Optional[str] = None
    if email:
        normalized_email = email.strip().lower()
        if "@" not in normalized_email:
            raise HTTPException(status_code=422, detail="Invalid email address")

    user = None
    if normalized_email:
        user = db.query(UserProfile).filter(UserProfile.garmin_email == normalized_email).first()

    if not user:
        user = UserProfile(
            user_id=_create_next_user_id(db),
            garmin_email=normalized_email,
            phone_number=display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif display_name and display_name != user.phone_number:
        user.phone_number = display_name
        db.commit()
        db.refresh(user)

    return user


@router.post("/auth/login", response_model=WebLoginResponse)
async def web_login(payload: WebLoginRequest, db: Session = Depends(get_db)):
    """Login/create a web user by email."""
    email = payload.email.strip().lower()
    existing = db.query(UserProfile).filter(UserProfile.garmin_email == email).first()
    user = _create_or_reuse_user(db, email=email, display_name=payload.display_name)
    created = existing is None

    return WebLoginResponse(
        user_id=user.user_id,
        email=email,
        display_name=user.phone_number,
        created=created,
    )


@router.post("/auth/garmin/start", response_model=GarminDirectStartResponse)
async def start_direct_garmin_oauth(
    payload: GarminDirectStartRequest, db: Session = Depends(get_db)
):
    """Create/reuse a user and return Garmin OAuth URL directly."""
    if not settings.garmin_redirect_uri:
        raise HTTPException(status_code=500, detail="GARMIN_REDIRECT_URI not configured")

    user = _create_or_reuse_user(db, email=payload.email, display_name=payload.display_name)
    oauth_service = GarminOAuthService()

    ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
    db.query(OAuthSession).filter(
        OAuthSession.created_at < ten_minutes_ago
    ).delete()
    db.commit()

    auth_url, code_verifier, state = oauth_service.get_authorization_url(settings.garmin_redirect_uri)
    oauth_session = OAuthSession(
        state=state,
        code_verifier=code_verifier,
        user_id=user.user_id,
    )
    db.add(oauth_session)
    db.commit()

    return GarminDirectStartResponse(
        user_id=user.user_id,
        authorization_url=auth_url,
        state=state,
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
