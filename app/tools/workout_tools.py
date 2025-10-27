import tempfile
import json
from datetime import datetime
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import WorkoutStepDuration, WorkoutStepTarget
from typing import List, Dict, Optional
from app.tools.workout_generator import generate_workout, get_recommended_durations, validate_workout_duration
from app.database.models import WorkoutHistory
from app.database.database import SessionLocal

def create_fit_file(
    user_id: Optional[int] = None,
    workout_steps: Optional[List[Dict]] = None,
    workout_type: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    sport: Optional[str] = None,
    recovery_score: Optional[float] = None
) -> str:
    """
    Creates a .fit file dynamically based on workout type, duration and sport.

    Args:
        user_id: Telegram user ID (for saving to history)
        workout_steps: List of workout steps (optional, for custom workouts)
        workout_type: Type of workout (HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
        duration_minutes: Desired duration in minutes
        sport: Sport type (WALKING, RUNNING, CYCLING, LAP_SWIMMING, etc.) - auto-detect if None (HERSTEL→WALKING, others→CYCLING)
        recovery_score: Recovery score before workout (for history tracking)

    Each step should be a dictionary with keys:
    - wkt_step_name: str
    - duration_type: str (allowed values: 'time', 'distance', etc.)
    - duration_value: int (for 'time' duration, value is in seconds; for 'distance', value is in meters)
    - target_type: str (allowed values: 'speed', 'heart_rate', etc.)
    - target_value: int (e.g., heart rate zone)

    Returns:
        Path to the created .fit file
    """
    try:
        builder = FitFileBuilder(auto_define=True)
    except Exception as e:
        raise ValueError(f"Failed to initialize FIT file builder: {e}")

    workout_name = None

    # Genereer workout dynamisch als type en duur gegeven zijn
    if workout_type and duration_minutes and not workout_steps:
        # Valideer duur
        is_valid, message = validate_workout_duration(workout_type, duration_minutes)
        if not is_valid:
            raise ValueError(message)

        # Genereer workout
        workout_data = generate_workout(workout_type, duration_minutes)
        workout_steps = workout_data["steps"]
        workout_name = workout_data["name"]

    # Fallback: Als workout_type gegeven maar geen duur, gebruik aanbevolen duur
    if workout_type and not duration_minutes and not workout_steps:
        recommended = get_recommended_durations(workout_type)
        duration_minutes = recommended[0]  # Neem eerste aanbevolen duur
        workout_data = generate_workout(workout_type, duration_minutes)
        workout_steps = workout_data["steps"]
        workout_name = workout_data["name"]

    if not workout_steps:
        # Absolute fallback: Genereer standaard DUUR workout van 60 minuten
        workout_type = "DUUR"
        duration_minutes = 60
        workout_data = generate_workout(workout_type, duration_minutes)
        workout_steps = workout_data["steps"]
        workout_name = workout_data["name"]

    duration_type_map = {
        'time': WorkoutStepDuration.TIME,
        'distance': WorkoutStepDuration.DISTANCE,
        # ... (other mappings)
    }

    target_type_map = {
        'speed': WorkoutStepTarget.SPEED,
        'heart_rate': WorkoutStepTarget.HEART_RATE,
        'open': WorkoutStepTarget.OPEN,
        # ... (other mappings)
    }

    try:
        for step in workout_steps:
            step_message = WorkoutStepMessage()
            step_message.wkt_step_name = step.get("wkt_step_name")

            duration_type_str = step.get("duration_type")
            if duration_type_str in duration_type_map:
                step_message.duration_type = duration_type_map[duration_type_str]

            duration_value = step.get("duration_value")
            if duration_value is not None:
                try:
                    duration_in_ms = int(duration_value) * 1000 if duration_type_str == 'time' else int(duration_value)
                    step_message.duration_value = duration_in_ms
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid duration value for step '{step.get('wkt_step_name')}': {e}")

            target_type_str = step.get("target_type")
            if target_type_str in target_type_map:
                step_message.target_type = target_type_map[target_type_str]

            target_value = step.get("target_value")
            if target_value is not None:
                try:
                    step_message.target_value = int(target_value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid target value for step '{step.get('wkt_step_name')}': {e}")

            builder.add(step_message)

        fit_file = builder.build()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as fp:
            fp.write(fit_file.to_bytes())
            fit_file_path = fp.name

        # Sla workout op in history als user_id is gegeven
        if user_id:
            _save_workout_to_history(
                user_id=user_id,
                workout_type=workout_type or "CUSTOM",
                workout_name=workout_name or "Custom Workout",
                workout_steps=workout_steps,
                fit_file_path=fit_file_path,
                recovery_score=recovery_score
            )

        # Return file path for backward compatibility with telegram bot
        return fit_file_path

    except Exception as e:
        raise ValueError(f"Failed to create FIT file: {str(e)}")


def _save_workout_to_history(
    user_id: int,
    workout_type: str,
    workout_name: str,
    workout_steps: List[Dict],
    fit_file_path: str,
    recovery_score: Optional[float] = None
):
    """Slaat workout op in de database history."""
    db = SessionLocal()
    try:
        workout_data = {
            "steps": workout_steps,
            "created_at": datetime.utcnow().isoformat()
        }

        history_entry = WorkoutHistory(
            user_id=user_id,
            workout_type=workout_type,
            workout_name=workout_name,
            created_at=datetime.utcnow(),
            recovery_score_before=recovery_score,
            fit_file_path=fit_file_path,
            workout_data=json.dumps(workout_data)
        )

        db.add(history_entry)
        db.commit()
    finally:
        db.close()


def list_available_workouts() -> str:
    """
    Toont beschikbare workout types en hun mogelijkheden.

    Returns:
        Nederlandse lijst van dynamische workout opties
    """
    from app.tools.workout_generator import WORKOUT_RECIPES

    lines = ["DYNAMISCHE WORKOUT GENERATOR", ""]
    lines.append("Workouts worden dynamisch gegenereerd op basis van jouw wensen.")
    lines.append("Specificeer simpelweg het TYPE en DUUR die je wilt.")
    lines.append("")

    lines.append("BESCHIKBARE WORKOUT TYPES:")
    lines.append("")

    for workout_type, recipe in WORKOUT_RECIPES.items():
        lines.append(f"{workout_type}:")
        lines.append(f"  Beschrijving: {recipe['description']}")
        lines.append(f"  Intensiteit: {recipe['intensity_level']}/5")

        # Toon aanbevolen duren
        recommended = get_recommended_durations(workout_type)
        lines.append(f"  Aanbevolen duren: {', '.join(str(d) for d in recommended)} minuten")

        # Toon structuur info
        structure = recipe['structure']
        if structure['intervals']:
            lines.append(f"  Structuur: Intervaltraining (werk + herstel)")
        else:
            lines.append(f"  Structuur: Continue training")

        lines.append("")

    lines.append("SPORT TYPES:")
    lines.append("Je kunt verschillende sporten specificeren:")
    lines.append("")
    lines.append("  WANDELEN:")
    lines.append("    Keywords: wandelen, wandeling, walking")
    lines.append("    Garmin type: WALKING")
    lines.append("    Voorbeelden:")
    lines.append("      - 'HERSTEL wandeling van 45 minuten'")
    lines.append("      - 'DUUR wandeling van 60 minuten'")
    lines.append("")
    lines.append("  HARDLOPEN:")
    lines.append("    Keywords: lopen, hardlopen, rennen, running, joggen")
    lines.append("    Garmin type: RUNNING")
    lines.append("    Voorbeelden:")
    lines.append("      - 'HERSTEL hardlopen van 30 minuten'")
    lines.append("      - 'DUUR hardloop sessie van 60 minuten'")
    lines.append("")
    lines.append("  FIETSEN:")
    lines.append("    Keywords: fietsen, fietsrit, wielrennen, cycling")
    lines.append("    Garmin type: CYCLING")
    lines.append("    Voorbeelden:")
    lines.append("      - 'DUUR fietsrit van 90 minuten'")
    lines.append("      - 'THRESHOLD fietsen van 60 minuten'")
    lines.append("")
    lines.append("  GRAVEL:")
    lines.append("    Keywords: gravel, gravelrit")
    lines.append("    Voorbeelden:")
    lines.append("      - 'DUUR gravelrit van 120 minuten'")
    lines.append("")
    lines.append("  INDOOR FIETSEN (Zwift):")
    lines.append("    Keywords: indoor, zwift, trainer, rollenbank")
    lines.append("    Voorbeelden:")
    lines.append("      - 'THRESHOLD op zwift van 45 minuten'")
    lines.append("      - 'VO2MAX rollenbank sessie van 30 minuten'")
    lines.append("")
    lines.append("  ZWEMMEN:")
    lines.append("    Keywords: zwemmen, swimming, baantjes")
    lines.append("    Voorbeelden:")
    lines.append("      - 'DUUR zwemmen van 45 minuten'")
    lines.append("")
    lines.append("ALGEMENE VOORBEELDEN:")
    lines.append("  - 'Maak een HERSTEL workout van 45 minuten' → Auto WALKING")
    lines.append("  - 'Maak een DUUR workout van 75 minuten' → Auto CYCLING")
    lines.append("  - 'Ik wil een THRESHOLD sessie van 50 minuten op zwift' → CYCLING")
    lines.append("  - 'Geef me een HERSTEL wandeling van 45 minuten' → WALKING")
    lines.append("  - 'Geef me een HERSTEL hardloop sessie van 30 minuten' → RUNNING")
    lines.append("  - 'Plan een VO2MAX gravelrit van 60 minuten' → CYCLING")
    lines.append("")
    lines.append("AUTO-DETECT:")
    lines.append("  - HERSTEL zonder sport specificatie → WALKING (wandelen)")
    lines.append("  - DUUR/THRESHOLD/VO2MAX/SPRINT zonder sport → CYCLING (fietsen)")
    lines.append("  - Keywords in tekst overschrijven auto-detect")

    return "\n".join(lines)
