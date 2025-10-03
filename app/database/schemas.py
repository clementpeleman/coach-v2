from pydantic import BaseModel
from typing import Optional
import datetime

class UserProfileBase(BaseModel):
    phone_number: Optional[str] = None
    garmin_email: Optional[str] = None
    garmin_password: Optional[str] = None

class UserProfileCreate(UserProfileBase):
    pass

class UserProfile(UserProfileBase):
    user_id: int

    class Config:
        from_attributes = True

class UserSummaryBase(BaseModel):
    preferred_activity_type: Optional[str] = None
    activity_frequency: Optional[float] = None
    typical_activity_duration: Optional[float] = None
    typical_activity_distance: Optional[float] = None

class UserSummaryCreate(UserSummaryBase):
    pass

class UserSummary(UserSummaryBase):
    user_id: int

    class Config:
        from_attributes = True

class ActivityBase(BaseModel):
    activity_id: int
    user_id: int
    activity_type: str
    start_time: datetime.datetime
    duration: Optional[float] = None
    distance: Optional[float] = None

class ActivityCreate(ActivityBase):
    pass

class Activity(ActivityBase):
    class Config:
        from_attributes = True
