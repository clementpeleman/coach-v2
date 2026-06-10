"""Regression tests for Garmin OAuth token storage."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, GarminToken, UserProfile
from app.tools.garmin_oauth import GarminOAuthService


def test_store_tokens_relinks_existing_garmin_account_to_current_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    session.add_all(
        [
            UserProfile(user_id=200, garmin_user_id="garmin-123"),
            UserProfile(user_id=100),
            GarminToken(
                user_id=200,
                garmin_user_id="garmin-123",
                access_token="old-access",
                refresh_token="old-refresh",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                refresh_expires_at=datetime.utcnow() + timedelta(days=30),
            ),
        ]
    )
    session.commit()

    service = object.__new__(GarminOAuthService)
    service.get_user_id = lambda _access_token: "garmin-123"
    service.encrypt_token = lambda token: f"encrypted:{token}"

    token = service.store_tokens(
        session,
        user_id=100,
        token_data={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "refresh_token_expires_in": 86400,
        },
    )

    assert token.user_id == 100
    assert session.get(UserProfile, 200).garmin_user_id is None
    assert session.get(UserProfile, 100).garmin_user_id == "garmin-123"
