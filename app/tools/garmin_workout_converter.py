"""
Converter van onze workout templates naar Garmin Training API JSON format.
"""
from typing import List, Dict, Optional


# Mapping van onze intensity levels naar Garmin intensities
INTENSITY_MAP = {
    "warming-up": "WARMUP",
    "warm-up": "WARMUP",
    "cool-down": "COOLDOWN",
    "cooldown": "COOLDOWN",
    "herstel": "RECOVERY",
    "recovery": "RECOVERY",
    "interval": "INTERVAL",
    "sprint": "INTERVAL",
    "actief": "ACTIVE",
    "active": "ACTIVE",
}

# Mapping van workout types naar Garmin sport types
SPORT_MAP = {
    "HERSTEL": "WALKING",  # Default naar walking (laag-intensiteit herstel)
    "DUUR": "CYCLING",  # Default naar cycling, kan later aangepast worden
    "THRESHOLD": "CYCLING",
    "VO2MAX": "CYCLING",
    "SPRINT": "CYCLING",
}


def convert_workout_to_garmin_json(
    workout_name: str,
    workout_type: str,
    workout_steps: List[Dict],
    description: Optional[str] = None,
    sport: str = "CYCLING"
) -> Dict:
    """
    Converteert onze workout template naar Garmin Training API JSON format.

    Args:
        workout_name: Naam van de workout
        workout_type: Type (DUUR, THRESHOLD, VO2MAX, SPRINT)
        workout_steps: Lijst van onze workout steps
        description: Optionele beschrijving
        sport: Garmin sport type (RUNNING, CYCLING, etc.)

    Returns:
        Dict in Garmin Training API JSON format
    """

    # Bepaal sport type als niet opgegeven
    if not sport or sport == "CYCLING":
        sport = SPORT_MAP.get(workout_type, "CYCLING")

    # Build Garmin workout structure
    garmin_workout = {
        "workoutName": workout_name,
        "description": description or f"{workout_type} workout",
        "sport": sport,
        "workoutProvider": "AI Coach",
        "workoutSourceId": "ai_coach_v1",
        "isSessionTransitionEnabled": False,
        "segments": [
            {
                "segmentOrder": 1,
                "sport": sport,
                "poolLength": None,
                "poolLengthUnit": None,
                "steps": []
            }
        ]
    }

    # Converteer steps
    garmin_steps = []
    for idx, step in enumerate(workout_steps, start=1):
        garmin_step = _convert_step_to_garmin(step, idx)
        garmin_steps.append(garmin_step)

    garmin_workout["segments"][0]["steps"] = garmin_steps

    return garmin_workout


def _convert_step_to_garmin(step: Dict, step_order: int) -> Dict:
    """
    Converteert een enkele workout step naar Garmin format.

    Args:
        step: Onze workout step
        step_order: Volgorde nummer

    Returns:
        Dict in Garmin step format
    """

    # Bepaal intensity
    step_name = step.get("wkt_step_name", "").lower()
    intensity = "ACTIVE"  # Default

    if "warm" in step_name or "warming" in step_name:
        intensity = "WARMUP"
    elif "cool" in step_name:
        intensity = "COOLDOWN"
    elif "herstel" in step_name or "recovery" in step_name:
        intensity = "RECOVERY"
    elif "interval" in step_name or "sprint" in step_name:
        intensity = "INTERVAL"

    # Bepaal duration
    duration_type = step.get("duration_type", "time").upper()
    duration_value = step.get("duration_value", 0)

    # Converteer duration type naar Garmin format
    garmin_duration_type = "TIME"
    if duration_type == "TIME":
        garmin_duration_type = "TIME"
        # Garmin verwacht seconden, wij gebruiken ook seconden
    elif duration_type == "DISTANCE":
        garmin_duration_type = "DISTANCE"
        # Garmin verwacht meters, wij gebruiken ook meters
    else:
        garmin_duration_type = "OPEN"

    # Bepaal target
    target_type = step.get("target_type", "open")
    target_value = step.get("target_value")

    garmin_target_type = None
    garmin_target_value = None

    if target_type == "heart_rate":
        garmin_target_type = "HEART_RATE"
        # Garmin gebruikt HR zones 1-5
        garmin_target_value = target_value if target_value else None
    elif target_type == "power":
        garmin_target_type = "POWER"
        # Garmin gebruikt power zones 1-7
        garmin_target_value = target_value if target_value else None
    elif target_type == "speed":
        garmin_target_type = "SPEED"
        garmin_target_value = target_value if target_value else None
    else:
        garmin_target_type = "OPEN"

    # Build Garmin step
    garmin_step = {
        "type": "WorkoutStep",
        "stepOrder": step_order,
        "intensity": intensity,
        "description": step.get("wkt_step_name", ""),
        "durationType": garmin_duration_type,
        "durationValue": duration_value,
        "durationValueType": None,
        "targetType": garmin_target_type,
        "targetValue": garmin_target_value,
        "targetValueLow": None,
        "targetValueHigh": None,
        "targetValueType": None,
        "secondaryTargetType": None,
        "secondaryTargetValue": None,
        "secondaryTargetValueLow": None,
        "secondaryTargetValueHigh": None,
        "secondaryTargetValueType": None,
        "strokeType": None,
        "drillType": None,
        "equipmentType": None,
        "exerciseCategory": None,
        "exerciseName": None,
        "weightValue": None,
        "weightDisplayUnit": None
    }

    return garmin_step


def convert_template_to_garmin(template: Dict, sport: str = "CYCLING") -> Dict:
    """
    Converteert een complete workout template naar Garmin format.

    Args:
        template: Workout template dict met 'name', 'workout_type', 'description', 'steps'
        sport: Garmin sport type

    Returns:
        Dict in Garmin Training API JSON format
    """
    return convert_workout_to_garmin_json(
        workout_name=template.get("name", "Workout"),
        workout_type=template.get("workout_type", "CUSTOM"),
        workout_steps=template.get("steps", []),
        description=template.get("description"),
        sport=sport
    )
