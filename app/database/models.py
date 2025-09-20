from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profile'

    user_id = Column(BigInteger, primary_key=True)
    phone_number = Column(String, nullable=False)
    garmin_user_id = Column(String)

# The following tables are intended to be TimescaleDB hypertables.
# The conversion to hypertables will be handled separately.

class ActivitiesHypertable(Base):
    __tablename__ = 'activities_hypertable'

    activity_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'))
    activity_type = Column(String)
    start_time = Column(DateTime)

class SensorData(Base):
    __tablename__ = 'sensor_data'

    timestamp = Column(DateTime, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user_profile.user_id'))
    heart_rate = Column(Integer)
    speed = Column(Float)
    power = Column(Float)
