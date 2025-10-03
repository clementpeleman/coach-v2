from sqlalchemy.orm import Session
from . import models, schemas
import datetime
from app.utils.security import encrypt_password

def get_user(db: Session, user_id: int):
    return db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()

def create_user(db: Session, user: schemas.UserProfileCreate, user_id: int):
    # Encrypt password before storing
    encrypted_password = encrypt_password(user.garmin_password) if user.garmin_password else None

    db_user = models.UserProfile(
        user_id=user_id,
        phone_number=user.phone_number or "",
        garmin_email=user.garmin_email,
        garmin_password=encrypted_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_garmin_credentials(db: Session, user_id: int, email: str, password: str):
    # Encrypt password before storing
    encrypted_password = encrypt_password(password)

    db_user = get_user(db, user_id)
    if db_user:
        db_user.garmin_email = email
        db_user.garmin_password = encrypted_password
        db.commit()
        db.refresh(db_user)
    else:
        user_profile = schemas.UserProfileCreate(garmin_email=email, garmin_password=password)
        db_user = create_user(db, user=user_profile, user_id=user_id)
    return db_user

def get_user_summary(db: Session, user_id: int):
    return db.query(models.UserSummary).filter(models.UserSummary.user_id == user_id).first()

def create_or_update_user_summary(db: Session, user_id: int, summary: schemas.UserSummaryCreate):
    db_summary = get_user_summary(db, user_id)
    if db_summary:
        for key, value in summary.dict().items():
            setattr(db_summary, key, value)
        db_summary.last_updated = datetime.datetime.utcnow()
    else:
        db_summary = models.UserSummary(**summary.dict(), user_id=user_id, last_updated=datetime.datetime.utcnow())
        db.add(db_summary)
    db.commit()
    db.refresh(db_summary)
    return db_summary

def create_activity(db: Session, activity: schemas.ActivityCreate):
    db_activity = db.query(models.ActivitiesHypertable).filter(models.ActivitiesHypertable.activity_id == activity.activity_id).first()
    if not db_activity:
        db_activity = models.ActivitiesHypertable(**activity.dict())
        db.add(db_activity)
        db.commit()
        db.refresh(db_activity)
    return db_activity


def get_activities_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.ActivitiesHypertable).filter(models.ActivitiesHypertable.user_id == user_id).offset(skip).limit(limit).all()

def delete_user_data(db: Session, user_id: int):
    # Delete summary
    db.query(models.UserSummary).filter(models.UserSummary.user_id == user_id).delete()
    # Delete activities
    db.query(models.ActivitiesHypertable).filter(models.ActivitiesHypertable.user_id == user_id).delete()
    # Delete profile
    db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).delete()
    db.commit()