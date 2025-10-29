from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime, Float, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profile'

    user_id = Column(BigInteger, primary_key=True)
    phone_number = Column(String, nullable=True)
    garmin_email = Column(String, nullable=True)  # Made nullable since OAuth doesn't need email
    garmin_password = Column(String, nullable=True)  # Stored encrypted with Fernet, nullable for OAuth
    garmin_user_id = Column(String, unique=True, nullable=True)  # Garmin API User ID from OAuth

class UserSummary(Base):
    __tablename__ = 'user_summary'

    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), primary_key=True)
    preferred_activity_type = Column(String)
    activity_frequency = Column(Float)  # Activities per week
    typical_activity_duration = Column(Float)  # In minutes
    typical_activity_distance = Column(Float)  # In kilometers
    last_updated = Column(DateTime)

# The following tables are intended to be TimescaleDB hypertables.
# The conversion to hypertables will be handled separately.

class ActivitiesHypertable(Base):
    __tablename__ = 'activities_hypertable'

    activity_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'))
    activity_type = Column(String)
    start_time = Column(DateTime)
    duration = Column(Float)  # In seconds
    distance = Column(Float)  # In meters

class SensorData(Base):
    __tablename__ = 'sensor_data'

    timestamp = Column(DateTime, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'))
    heart_rate = Column(Integer)
    speed = Column(Float)
    power = Column(Float)

class GarminToken(Base):
    """Stores OAuth2 tokens for Garmin API integration."""
    __tablename__ = 'garmin_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), unique=True, nullable=False)
    garmin_user_id = Column(String, unique=True, nullable=False)  # Garmin API User ID
    access_token = Column(Text, nullable=False)  # Encrypted OAuth2 access token
    refresh_token = Column(Text, nullable=False)  # Encrypted OAuth2 refresh token
    token_type = Column(String, default='bearer')
    expires_at = Column(DateTime, nullable=False)  # When access token expires
    refresh_expires_at = Column(DateTime, nullable=False)  # When refresh token expires
    scope = Column(Text)  # Space-separated scopes granted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GarminHealthData(Base):
    """Stores Garmin health/wellness data (dailies, epochs, sleep, etc.)."""
    __tablename__ = 'garmin_health_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), nullable=False)
    summary_id = Column(String, unique=True, nullable=False)  # Garmin's unique summary ID
    summary_type = Column(String, nullable=False)  # dailies, epochs, sleeps, stressDetails, etc.
    calendar_date = Column(String, nullable=True)  # Format: yyyy-mm-dd
    start_time = Column(DateTime, nullable=False)  # UTC timestamp
    start_time_offset = Column(Integer, nullable=True)  # Offset in seconds
    duration = Column(Integer, nullable=True)  # Duration in seconds
    data = Column(Text, nullable=False)  # JSON data of the full summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GarminActivityData(Base):
    """Stores Garmin activity data (runs, cycles, swims, etc.)."""
    __tablename__ = 'garmin_activity_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), nullable=False)
    summary_id = Column(String, unique=True, nullable=False)  # Garmin's unique summary ID
    activity_id = Column(String, nullable=True)  # Garmin Connect activity ID
    activity_type = Column(String, nullable=False)  # RUNNING, CYCLING, etc.
    activity_name = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)  # UTC timestamp
    start_time_offset = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    distance = Column(Float, nullable=True)  # Distance in meters
    calories = Column(Integer, nullable=True)  # Active kilocalories
    average_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    device_name = Column(String, nullable=True)
    manual = Column(Boolean, default=False)  # Manually created vs device recorded
    data = Column(Text, nullable=False)  # JSON data of the full summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OAuthSession(Base):
    """Stores temporary OAuth2 state and code verifier."""
    __tablename__ = 'oauth_sessions'

    state = Column(String, primary_key=True)
    code_verifier = Column(String, nullable=False)
    telegram_user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class WorkoutPreferences(Base):
    """Stores user workout preferences."""
    __tablename__ = 'workout_preferences'

    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), primary_key=True)
    preferred_workout_types = Column(Text, nullable=True)  # JSON array: ["DUUR", "THRESHOLD", "VO2MAX", "SPRINT"]
    preferred_duration_minutes = Column(Integer, nullable=True)  # Preferred workout duration
    max_intensity_level = Column(Integer, nullable=True)  # 1-5, max intensity user wants
    weekly_workout_goal = Column(Integer, nullable=True)  # Target number of workouts per week
    ftp = Column(Integer, nullable=True)  # Functional Threshold Power in watts (for power-based cycling workouts)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WorkoutTemplate(Base):
    """Stores workout templates for different training types."""
    __tablename__ = 'workout_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workout_type = Column(String, nullable=False)  # DUUR, THRESHOLD, VO2MAX, SPRINT
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    intensity_level = Column(Integer, nullable=False)  # 1-5
    template_json = Column(Text, nullable=False)  # JSON with workout steps
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkoutHistory(Base):
    """Stores history of created/completed workouts."""
    __tablename__ = 'workout_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'), nullable=False)
    workout_type = Column(String, nullable=False)  # DUUR, THRESHOLD, VO2MAX, SPRINT
    workout_name = Column(String, nullable=False)
    template_id = Column(Integer, ForeignKey('workout_templates.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)  # When workout was actually done
    recovery_score_before = Column(Float, nullable=True)  # Recovery score before workout
    fit_file_path = Column(String, nullable=True)  # Path to generated FIT file
    workout_data = Column(Text, nullable=False)  # JSON with full workout details
