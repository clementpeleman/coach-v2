"""Web app endpoints for auth and chat."""
import logging
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database.database import get_db
from app.database.models import OAuthSession, UserProfile
from app.tools.garmin_oauth import GarminOAuthService

router = APIRouter(prefix="/web", tags=["web"])
logger = logging.getLogger(__name__)


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
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str


class WeatherResponse(BaseModel):
    source: str
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    temperature_c: Optional[float] = None
    apparent_temperature_c: Optional[float] = None
    humidity_percent: Optional[int] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_gust_kmh: Optional[float] = None
    weather_code: Optional[int] = None
    condition: str
    training_note: str
    observed_at: Optional[str] = None


class GarminDirectStartRequest(BaseModel):
    user_id: Optional[int] = None
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


def _weather_condition(code: Optional[int]) -> str:
    if code is None:
        return "onbekend"
    if code == 0:
        return "helder"
    if code in {1, 2, 3}:
        return "bewolkt"
    if code in {45, 48}:
        return "mist"
    if code in {51, 53, 55, 56, 57}:
        return "motregen"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "regen"
    if code in {71, 73, 75, 77, 85, 86}:
        return "sneeuw"
    if code in {95, 96, 99}:
        return "onweer"
    return "wisselvallig"


def _weather_training_note(current: dict) -> str:
    temp = current.get("temperature_2m")
    apparent = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m") or 0
    gust = current.get("wind_gusts_10m") or 0
    precip = current.get("precipitation") or 0
    code = current.get("weather_code")
    condition = _weather_condition(code)

    notes = []
    feels_like = apparent if isinstance(apparent, (int, float)) else temp
    if isinstance(feels_like, (int, float)):
        if feels_like >= 26:
            notes.append("warm: kies lagere intensiteit en drink extra")
        elif feels_like <= 3:
            notes.append("koud: neem langere warming-up")
    if wind >= 28 or gust >= 45:
        notes.append("veel wind: kies beschutte route of lagere tempodoelen")
    if precip > 0 or condition in {"regen", "motregen", "onweer"}:
        notes.append("nat weer: let op grip en zichtbaarheid")
    if condition == "onweer":
        notes.append("vermijd buiten trainen tot het onweer voorbij is")

    return "; ".join(notes) if notes else "weer heeft geen grote aanpassing nodig"


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
    try:
        if not settings.garmin_redirect_uri:
            raise HTTPException(
                status_code=500,
                detail="GARMIN_REDIRECT_URI is not configured on the server.",
            )
        if not settings.garmin_consumer_key or not settings.garmin_consumer_secret:
            raise HTTPException(
                status_code=500,
                detail="GARMIN_CONSUMER_KEY and GARMIN_CONSUMER_SECRET must be set in Coolify env.",
            )

        user = None
        if payload.user_id is not None:
            user = db.query(UserProfile).filter(UserProfile.user_id == payload.user_id).first()

        if not user:
            user = _create_or_reuse_user(
                db, email=payload.email, display_name=payload.display_name
            )

        oauth_service = GarminOAuthService()

        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        db.query(OAuthSession).filter(OAuthSession.created_at < ten_minutes_ago).delete()
        db.commit()

        auth_url, code_verifier, state = oauth_service.get_authorization_url(
            settings.garmin_redirect_uri
        )
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Garmin OAuth start failed")
        raise HTTPException(
            status_code=500,
            detail=f"Garmin OAuth start failed: {exc}",
        ) from exc


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


@router.get("/weather", response_model=WeatherResponse)
async def web_weather(lat: float, lon: float):
    """Return current weather for the user's browser-provided location."""
    try:
        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ",".join([
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                ]),
                "timezone": "auto",
            },
            timeout=8,
        )
        forecast.raise_for_status()
        data = forecast.json()
        current = data.get("current") or {}

        location_name = None
        try:
            reverse = requests.get(
                "https://geocoding-api.open-meteo.com/v1/reverse",
                params={"latitude": lat, "longitude": lon, "language": "nl", "count": 1},
                timeout=5,
            )
            if reverse.ok:
                first = (reverse.json().get("results") or [None])[0]
                if first:
                    parts = [first.get("name"), first.get("admin1"), first.get("country_code")]
                    location_name = ", ".join([part for part in parts if part])
        except Exception:
            location_name = None

        condition = _weather_condition(current.get("weather_code"))
        return WeatherResponse(
            source="open-meteo",
            latitude=lat,
            longitude=lon,
            location_name=location_name,
            temperature_c=current.get("temperature_2m"),
            apparent_temperature_c=current.get("apparent_temperature"),
            humidity_percent=current.get("relative_humidity_2m"),
            precipitation_mm=current.get("precipitation"),
            wind_speed_kmh=current.get("wind_speed_10m"),
            wind_gust_kmh=current.get("wind_gusts_10m"),
            weather_code=current.get("weather_code"),
            condition=condition,
            training_note=_weather_training_note(current),
            observed_at=current.get("time"),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weerdata ophalen mislukt: {exc}") from exc


@router.post("/chat", response_model=ChatResponse)
async def web_chat(payload: ChatRequest):
    """Chat with the existing coach agent."""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is niet geconfigureerd op de server.",
        )

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
        message = payload.message
        if payload.context:
            context_lines = []
            recovery = payload.context.get("recovery") if isinstance(payload.context, dict) else None
            if recovery:
                metrics = recovery.get("metrics") if isinstance(recovery.get("metrics"), dict) else {}
                context_lines.append(
                    "Actuele app-herstelscore: "
                    f"{recovery.get('score')}/6"
                    f" ({recovery.get('label') or 'label onbekend'}). "
                    "Gebruik deze score als waarheid als oudere chatgeschiedenis of tools iets anders suggereren."
                )
                context_lines.append(
                    "Actuele herstelmetrics: "
                    f"sleepScore={metrics.get('sleepScore')}, "
                    f"sleepHours={metrics.get('sleepHours')}, "
                    f"bodyBattery={metrics.get('bodyBattery')}, "
                    f"hrvOvernight={metrics.get('hrvOvernight')}, "
                    f"restingHr={metrics.get('restingHr')}, "
                    f"avgStress={metrics.get('avgStress')}."
                )
            weather = payload.context.get("weather") if isinstance(payload.context, dict) else None
            if weather:
                context_lines.append(
                    f"Weer/locatie: {weather.get('location_name') or 'locatie onbekend'}, "
                    f"{weather.get('temperature_c')}°C, {weather.get('condition')}, "
                    f"wind {weather.get('wind_speed_kmh')} km/u, "
                    f"neerslag {weather.get('precipitation_mm')} mm. "
                    f"Trainingsnota: {weather.get('training_note')}."
                )
            if context_lines:
                message = (
                    "CONTEXT VOOR COACH\n"
                    + "\n".join(context_lines)
                    + "\n\n"
                    f"GEBRUIKERSVRAAG\n{payload.message}"
                )

        result = agent_executor.invoke({"input": message, "chat_history": chat_history})
        return ChatResponse(reply=result["output"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
