"""
Tool voor het uploaden van workouts naar Garmin Connect via Training API.
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.tools.workout_generator import generate_workout
from app.tools.garmin_workout_converter import convert_template_to_garmin
from app.tools.garmin_training_api import GarminTrainingAPIClient
from app.database.database import SessionLocal


def upload_workout_to_garmin(
    user_id: int,
    workout_type: str,
    duration_minutes: int,
    sport: str = None,
    schedule_date: Optional[str] = None,
    force_create: bool = False
) -> str:
    """
    Upload een dynamisch gegenereerde workout naar Garmin Connect.

    Args:
        user_id: Telegram user ID
        workout_type: Type workout (HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
        duration_minutes: Gewenste duur in minuten
        sport: Garmin sport type (CARDIO_TRAINING, RUNNING, CYCLING, etc.) - Auto-detect if None (HERSTEL→CARDIO_TRAINING, others→CYCLING)
        schedule_date: Optioneel - plan workout op datum (YYYY-MM-DD format)
        force_create: If True, bypass recovery checks (useful for testing)

    Returns:
        Nederlands bevestigingsbericht
    """
    db = SessionLocal()

    try:
        # 1. Genereer workout dynamisch
        workout_data = generate_workout(workout_type, duration_minutes)

        # 2. Gebruik default sport als niet opgegeven
        if sport is None:
            sport = workout_data.get("default_sport", "CYCLING")

        # 3. Converteer naar Garmin JSON format
        garmin_json = convert_template_to_garmin(workout_data, sport=sport)

        # 3. Upload naar Garmin Connect
        training_client = GarminTrainingAPIClient(db, user_id)

        # Check permissions eerst
        try:
            permissions = training_client.check_permissions()
            if "WORKOUT_IMPORT" not in permissions:
                return ("Fout: Je hebt geen WORKOUT_IMPORT permissie.\n\n"
                        "Ga naar je Garmin Connect account instellingen en geef toestemming "
                        "voor workout import.")
        except Exception as e:
            return f"Fout bij controleren van permissies: {str(e)}\n\nMogelijk is je OAuth token verlopen."

        # Upload workout
        result = training_client.create_workout(garmin_json)
        workout_id = result.get('workoutId')

        # 4. Optioneel: plan workout
        schedule_info = ""
        if schedule_date:
            try:
                training_client.schedule_workout(workout_id, schedule_date)
                schedule_info = f"\nGepland op: {schedule_date}"
            except Exception as e:
                schedule_info = f"\n\nWaarschuwing: Kon workout niet plannen: {str(e)}"

        # 5. Genereer bevestigingsbericht
        message = "WORKOUT SUCCESVOL GEUPLOAD NAAR GARMIN CONNECT\n\n"
        message += f"Workout: {workout_data['name']}\n"
        message += f"Type: {workout_data['workout_type']}\n"
        message += f"Duur: {workout_data['duration_minutes']} minuten\n"
        message += f"Sport: {sport}\n"
        message += f"Garmin Workout ID: {workout_id}"
        message += schedule_info
        message += "\n\nDe workout is nu beschikbaar in je Garmin Connect account "
        message += "en zal automatisch syncen naar je Garmin horloge.\n\n"
        message += "Je kunt de workout vinden in:\n"
        message += "Garmin Connect > Training > Mijn workouts"

        return message

    except Exception as e:
        error_msg = f"Fout bij uploaden naar Garmin Connect:\n{str(e)}\n\n"
        error_msg += "Mogelijke oorzaken:\n"
        error_msg += "- OAuth token is verlopen (vernieuw via /garmin_oauth)\n"
        error_msg += "- Geen WORKOUT_IMPORT permissie\n"
        error_msg += "- Netwerk probleem\n"
        error_msg += "- Ongeldige workout data"
        return error_msg

    finally:
        db.close()


def check_garmin_workout_permissions(user_id: int) -> str:
    """
    Controleer of gebruiker WORKOUT_IMPORT permissie heeft.

    Args:
        user_id: Telegram user ID

    Returns:
        Nederlands bericht met permissions status
    """
    db = SessionLocal()

    try:
        training_client = GarminTrainingAPIClient(db, user_id)
        permissions = training_client.check_permissions()

        message = "GARMIN CONNECT PERMISSIES\n\n"
        message += "Jouw permissies:\n"

        for permission in permissions:
            if permission == "WORKOUT_IMPORT":
                message += f"  ✓ {permission} (Workout import mogelijk)\n"
            elif permission == "HEALTH_EXPORT":
                message += f"  ✓ {permission} (Health data export mogelijk)\n"
            elif permission == "ACTIVITY_EXPORT":
                message += f"  ✓ {permission} (Activity export mogelijk)\n"
            elif permission == "COURSE_IMPORT":
                message += f"  ✓ {permission} (Course import mogelijk)\n"
            else:
                message += f"  ✓ {permission}\n"

        if "WORKOUT_IMPORT" not in permissions:
            message += "\n⚠️ WORKOUT_IMPORT permissie ontbreekt!\n\n"
            message += "Om workouts te uploaden naar Garmin Connect heb je deze permissie nodig.\n"
            message += "Ga naar Garmin Connect account instellingen en geef toestemming."
        else:
            message += "\n✓ Je kunt workouts uploaden naar Garmin Connect!"

        return message

    except Exception as e:
        return f"Fout bij controleren van permissies:\n{str(e)}\n\nMogelijk is je OAuth token verlopen."

    finally:
        db.close()
