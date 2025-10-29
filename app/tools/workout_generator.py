"""
Dynamische workout generator - creëert workouts on-the-fly op basis van type en duur.
"""
from typing import List, Dict, Optional
import random


# FTP Zone definities (percentage van FTP)
# Voor cycling workouts gebruiken we power zones in plaats van hartslag zones
FTP_ZONES = {
    1: (0.50, 0.60),    # Zone 1: Active Recovery (50-60% FTP)
    2: (0.60, 0.75),    # Zone 2: Endurance (60-75% FTP)
    3: (0.75, 0.90),    # Zone 3: Tempo (75-90% FTP)
    4: (0.90, 1.05),    # Zone 4: Threshold (90-105% FTP)
    5: (1.05, 1.20),    # Zone 5: VO2max (105-120% FTP)
}

# Default FTP waarde (wordt overschreven door user preferences)
DEFAULT_FTP = 200  # Watts


# Sport type mapping - Maps Nederlandse keywords naar Garmin sport types
SPORT_KEYWORDS = {
    "wandelen": "CARDIO_TRAINING",
    "wandeling": "CARDIO_TRAINING",
    "walking": "CARDIO_TRAINING",
    "lopen": "RUNNING",
    "hardlopen": "RUNNING",
    "rennen": "RUNNING",
    "running": "RUNNING",
    "joggen": "RUNNING",
    "fietsen": "CYCLING",
    "fietsrit": "CYCLING",
    "wielrennen": "CYCLING",
    "cycling": "CYCLING",
    "gravel": "CYCLING",  # Gravel is ook CYCLING in Garmin
    "gravelrit": "CYCLING",
    "indoor": "CYCLING",  # Indoor cycling (Zwift)
    "zwift": "CYCLING",
    "trainer": "CYCLING",
    "rollenbank": "CYCLING",
    "zwemmen": "LAP_SWIMMING",
    "swimming": "LAP_SWIMMING",
    "baantjes": "LAP_SWIMMING",
}

# Workout "recipes" per type - deze definiëren de structuur
WORKOUT_RECIPES = {
    "HERSTEL": {
        "description": "Actief herstel op zeer lage intensiteit",
        "intensity_level": 1,
        "default_sport": "CARDIO_TRAINING",  # Wandelen (laag intensiteit herstel)
        "structure": {
            "warmup_percent": 0,  # Direct starten
            "cooldown_percent": 0,  # Direct stoppen
            "work_zones": [1],  # Zone 1
            "intervals": False,  # Geen intervallen, continu
        }
    },
    "DUUR": {
        "description": "Duurtraining op lage intensiteit voor aerobe basis",
        "intensity_level": 2,
        "default_sport": "CYCLING",  # Fietsen
        "structure": {
            "warmup_percent": 15,  # 15% warming-up
            "cooldown_percent": 10,  # 10% cool-down
            "work_zones": [2],  # Zone 2
            "intervals": False,  # Continu werk
        }
    },
    "THRESHOLD": {
        "description": "Tempo training op drempelvermogen",
        "intensity_level": 4,
        "default_sport": "CYCLING",  # Fietsen
        "structure": {
            "warmup_percent": 20,  # 20% warming-up
            "cooldown_percent": 15,  # 15% cool-down
            "work_zones": [4],  # Zone 4
            "intervals": True,
            "interval_work_duration": [8, 10, 12],  # Interval lengtes in minuten (kies random)
            "interval_rest_duration": [3, 4, 5],  # Herstel tussen intervallen
            "rest_zone": 2,  # Zone 2 tijdens herstel
        }
    },
    "VO2MAX": {
        "description": "Intensieve intervallen voor maximale zuurstofopname",
        "intensity_level": 5,
        "default_sport": "CYCLING",  # Fietsen
        "structure": {
            "warmup_percent": 25,  # 25% warming-up
            "cooldown_percent": 15,  # 15% cool-down
            "work_zones": [5],  # Zone 5
            "intervals": True,
            "interval_work_duration": [3, 4, 5],  # Interval lengtes in minuten
            "interval_rest_duration": [2, 3],  # Herstel tussen intervallen
            "rest_zone": 2,
        }
    },
    "SPRINT": {
        "description": "Zeer korte maximale inspanningen",
        "intensity_level": 5,
        "default_sport": "CYCLING",  # Fietsen
        "structure": {
            "warmup_percent": 30,  # 30% warming-up (belangrijk voor sprints)
            "cooldown_percent": 20,  # 20% cool-down
            "work_zones": [5],  # Max effort
            "intervals": True,
            "interval_work_duration": [0.5, 1],  # 30-60 seconden (in minuten)
            "interval_rest_duration": [2, 3],  # Lange herstel
            "rest_zone": 1,  # Zeer rustig herstel
        }
    }
}


def calculate_power_range(zone: int, ftp: int) -> Dict[str, int]:
    """
    Berekent power range in watts voor een gegeven zone en FTP.

    Args:
        zone: Zone nummer (1-5)
        ftp: Functional Threshold Power in watts

    Returns:
        Dict met 'min' en 'max' power in watts
    """
    if zone not in FTP_ZONES:
        return {"min": 0, "max": 0}

    low_pct, high_pct = FTP_ZONES[zone]
    return {
        "min": int(ftp * low_pct),
        "max": int(ftp * high_pct),
        "mid": int(ftp * ((low_pct + high_pct) / 2))  # Midpoint van zone
    }


def generate_workout(
    workout_type: str,
    duration_minutes: int,
    user_preferences: Optional[Dict] = None,
    sport: Optional[str] = None
) -> Dict:
    """
    Genereert een workout dynamisch op basis van type en duur.

    Args:
        workout_type: Type workout (HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
        duration_minutes: Gewenste totale duur in minuten
        user_preferences: Optionele preferences (bijv. max_intensity, ftp)
        sport: Sport type (CYCLING, RUNNING, etc.) - bepaalt of power of HR gebruikt wordt

    Returns:
        Dict met workout metadata en steps
    """

    if workout_type not in WORKOUT_RECIPES:
        raise ValueError(f"Onbekend workout type: {workout_type}. Kies uit: {', '.join(WORKOUT_RECIPES.keys())}")

    recipe = WORKOUT_RECIPES[workout_type]
    structure = recipe["structure"]

    # Bepaal of we power of heart rate gebruiken
    # Power gebruiken voor CYCLING workouts (als FTP beschikbaar)
    use_power = False
    ftp = DEFAULT_FTP

    if user_preferences:
        ftp = user_preferences.get('ftp', DEFAULT_FTP)

    # Gebruik power voor cycling workouts als FTP > 0
    if sport and 'CYCLING' in sport.upper() and ftp > 0:
        use_power = True
    elif not sport and recipe.get("default_sport") == "CYCLING" and ftp > 0:
        use_power = True

    # Bereken tijden
    total_seconds = duration_minutes * 60
    warmup_seconds = int(total_seconds * structure["warmup_percent"] / 100)
    cooldown_seconds = int(total_seconds * structure["cooldown_percent"] / 100)
    work_seconds = total_seconds - warmup_seconds - cooldown_seconds

    # Genereer workout steps
    steps = []

    # 1. Warming-up (als van toepassing)
    if warmup_seconds > 0:
        if use_power:
            power_range = calculate_power_range(2, ftp)
            steps.append({
                "wkt_step_name": "Warming-up",
                "duration_type": "time",
                "duration_value": warmup_seconds,
                "target_type": "power",
                "target_value": power_range["mid"],  # Midpoint van Zone 2
                "target_low": power_range["min"],
                "target_high": power_range["max"],
            })
        else:
            steps.append({
                "wkt_step_name": "Warming-up",
                "duration_type": "time",
                "duration_value": warmup_seconds,
                "target_type": "heart_rate",
                "target_value": 2,  # Zone 2
            })

    # 2. Werk gedeelte
    if structure["intervals"]:
        # Intervaltraining
        interval_steps = _generate_interval_steps(
            work_seconds=work_seconds,
            work_zones=structure["work_zones"],
            interval_work_options=structure["interval_work_duration"],
            interval_rest_options=structure["interval_rest_duration"],
            rest_zone=structure["rest_zone"],
            use_power=use_power,
            ftp=ftp
        )
        steps.extend(interval_steps)
    else:
        # Continue training
        work_zone = structure["work_zones"][0]

        if use_power:
            power_range = calculate_power_range(work_zone, ftp)
            steps.append({
                "wkt_step_name": f"{workout_type} interval",
                "duration_type": "time",
                "duration_value": work_seconds,
                "target_type": "power",
                "target_value": power_range["mid"],
                "target_low": power_range["min"],
                "target_high": power_range["max"],
            })
        else:
            target_type = "heart_rate" if work_zone > 0 else "open"
            steps.append({
                "wkt_step_name": f"{workout_type} interval",
                "duration_type": "time",
                "duration_value": work_seconds,
                "target_type": target_type,
                "target_value": work_zone if work_zone > 0 else None,
            })

    # 3. Cool-down (als van toepassing)
    if cooldown_seconds > 0:
        if use_power:
            power_range = calculate_power_range(1, ftp)
            steps.append({
                "wkt_step_name": "Cool-down",
                "duration_type": "time",
                "duration_value": cooldown_seconds,
                "target_type": "power",
                "target_value": power_range["mid"],  # Midpoint van Zone 1
                "target_low": power_range["min"],
                "target_high": power_range["max"],
            })
        else:
            steps.append({
                "wkt_step_name": "Cool-down",
                "duration_type": "time",
                "duration_value": cooldown_seconds,
                "target_type": "heart_rate",
                "target_value": 1,  # Zone 1
            })

    # Genereer beschrijvende naam
    workout_name = _generate_workout_name(workout_type, duration_minutes, structure)

    return {
        "workout_type": workout_type,
        "name": workout_name,
        "description": recipe["description"],
        "duration_minutes": duration_minutes,
        "intensity_level": recipe["intensity_level"],
        "default_sport": recipe.get("default_sport", "CYCLING"),  # Default sport voor dit type
        "steps": steps,
    }


def _generate_interval_steps(
    work_seconds: int,
    work_zones: List[int],
    interval_work_options: List[float],
    interval_rest_options: List[float],
    rest_zone: int,
    use_power: bool = False,
    ftp: int = DEFAULT_FTP
) -> List[Dict]:
    """
    Genereert interval steps dynamisch.

    Strategie: Vul beschikbare tijd met afwisselend werk + herstel intervallen.

    Args:
        work_seconds: Totale tijd voor werk intervallen
        work_zones: Zones voor werk intervallen
        interval_work_options: Mogelijke werk interval lengtes (minuten)
        interval_rest_options: Mogelijke rust interval lengtes (minuten)
        rest_zone: Zone voor herstel
        use_power: Of power gebruikt moet worden (vs heart rate)
        ftp: FTP waarde in watts
    """
    steps = []
    remaining_seconds = work_seconds
    interval_count = 1

    while remaining_seconds > 0:
        # Kies random work interval lengte
        work_minutes = random.choice(interval_work_options)
        work_interval_seconds = int(work_minutes * 60)

        # Kies random rest interval lengte
        rest_minutes = random.choice(interval_rest_options)
        rest_interval_seconds = int(rest_minutes * 60)

        # Check of we nog genoeg tijd hebben voor een volledig interval + herstel
        total_needed = work_interval_seconds + rest_interval_seconds

        if remaining_seconds < work_interval_seconds:
            # Niet genoeg tijd voor volledig werk interval, vul resterende tijd
            if remaining_seconds > 60:  # Als meer dan 1 minuut over
                work_interval_seconds = remaining_seconds
            else:
                break  # Te weinig tijd, stop

        # Voeg werk interval toe
        work_zone = random.choice(work_zones)

        if use_power:
            power_range = calculate_power_range(work_zone, ftp)
            steps.append({
                "wkt_step_name": f"Interval {interval_count}",
                "duration_type": "time",
                "duration_value": work_interval_seconds,
                "target_type": "power",
                "target_value": power_range["mid"],
                "target_low": power_range["min"],
                "target_high": power_range["max"],
            })
        else:
            steps.append({
                "wkt_step_name": f"Interval {interval_count}",
                "duration_type": "time",
                "duration_value": work_interval_seconds,
                "target_type": "heart_rate" if work_zone > 0 else "open",
                "target_value": work_zone if work_zone > 0 else None,
            })
        remaining_seconds -= work_interval_seconds

        # Voeg herstel interval toe (als er nog tijd is EN dit niet het laatste interval is)
        if remaining_seconds >= rest_interval_seconds:
            if use_power:
                rest_power_range = calculate_power_range(rest_zone, ftp)
                steps.append({
                    "wkt_step_name": "Herstel",
                    "duration_type": "time",
                    "duration_value": rest_interval_seconds,
                    "target_type": "power",
                    "target_value": rest_power_range["mid"],
                    "target_low": rest_power_range["min"],
                    "target_high": rest_power_range["max"],
                })
            else:
                steps.append({
                    "wkt_step_name": "Herstel",
                    "duration_type": "time",
                    "duration_value": rest_interval_seconds,
                    "target_type": "heart_rate",
                    "target_value": rest_zone,
                })
            remaining_seconds -= rest_interval_seconds
        elif remaining_seconds > 60:
            # Rest tijd gebruiken voor laatste herstel
            if use_power:
                rest_power_range = calculate_power_range(rest_zone, ftp)
                steps.append({
                    "wkt_step_name": "Herstel",
                    "duration_type": "time",
                    "duration_value": remaining_seconds,
                    "target_type": "power",
                    "target_value": rest_power_range["mid"],
                    "target_low": rest_power_range["min"],
                    "target_high": rest_power_range["max"],
                })
            else:
                steps.append({
                    "wkt_step_name": "Herstel",
                    "duration_type": "time",
                    "duration_value": remaining_seconds,
                    "target_type": "heart_rate",
                    "target_value": rest_zone,
                })
            remaining_seconds = 0
        else:
            # Geen tijd meer voor herstel
            break

        interval_count += 1

    return steps


def _generate_workout_name(workout_type: str, duration_minutes: int, structure: Dict) -> str:
    """Genereert een beschrijvende naam voor de workout."""

    type_names = {
        "HERSTEL": "Herstel",
        "DUUR": "Duurtraining",
        "THRESHOLD": "Drempeltraining",
        "VO2MAX": "VO2max Intervallen",
        "SPRINT": "Sprint Intervallen"
    }

    base_name = type_names.get(workout_type, workout_type)

    if structure["intervals"]:
        return f"{base_name} {duration_minutes} min (dynamisch)"
    else:
        return f"{base_name} {duration_minutes} min"


def get_recommended_durations(workout_type: str) -> List[int]:
    """
    Geeft aanbevolen duren voor een workout type.

    Returns:
        List van aanbevolen duren in minuten
    """
    recommendations = {
        "HERSTEL": [30, 45, 60],
        "DUUR": [45, 60, 75, 90, 120],
        "THRESHOLD": [45, 60, 75, 90, 120],  # Ook langere duren toegevoegd
        "VO2MAX": [30, 45, 60],
        "SPRINT": [20, 30, 45]
    }

    return recommendations.get(workout_type, [30, 45, 60])


def validate_workout_duration(workout_type: str, duration_minutes: int) -> tuple[bool, str]:
    """
    Valideert of een duur geschikt is voor een workout type.

    Returns:
        Tuple van (is_valid, message)
    """
    min_durations = {
        "HERSTEL": 15,
        "DUUR": 30,
        "THRESHOLD": 30,
        "VO2MAX": 20,
        "SPRINT": 15
    }

    max_durations = {
        "HERSTEL": 120,
        "DUUR": 180,
        "THRESHOLD": 150,  # Verhoogd voor lange interval trainingen
        "VO2MAX": 90,
        "SPRINT": 60
    }

    min_dur = min_durations.get(workout_type, 15)
    max_dur = max_durations.get(workout_type, 120)

    if duration_minutes < min_dur:
        return False, f"{workout_type} workout moet minimaal {min_dur} minuten zijn"

    if duration_minutes > max_dur:
        return False, f"{workout_type} workout mag maximaal {max_dur} minuten zijn"

    return True, "OK"


def detect_sport_from_text(text: str) -> Optional[str]:
    """
    Detecteert sport type uit Nederlandse tekst op basis van keywords.

    Args:
        text: Nederlandse tekst (bijv. "herstel wandeling", "duur fietsrit")

    Returns:
        Garmin sport type (RUNNING, CYCLING, LAP_SWIMMING) of None als niet gedetecteerd

    Examples:
        >>> detect_sport_from_text("maak een herstel wandeling")
        'RUNNING'
        >>> detect_sport_from_text("duur fietsrit van 60 minuten")
        'CYCLING'
        >>> detect_sport_from_text("threshold op zwift")
        'CYCLING'
    """
    if not text:
        return None

    text_lower = text.lower()

    # Zoek naar keywords in de tekst
    for keyword, sport_type in SPORT_KEYWORDS.items():
        if keyword in text_lower:
            return sport_type

    return None
