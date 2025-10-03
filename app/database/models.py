from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profile'

    user_id = Column(BigInteger, primary_key=True)
    phone_number = Column(String, nullable=True)
    garmin_email = Column(String)
    garmin_password = Column(String)  # Stored encrypted with Fernet

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
