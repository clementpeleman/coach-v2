"""
Workout templates voor verschillende training types.

Workout types:
- HERSTEL (Recovery): Zeer lage intensiteit voor actief herstel (Zone 1)
- DUUR (Endurance): Langere workouts op lage intensiteit (Zone 2)
- THRESHOLD: Tempo workouts op drempel (Zone 4)
- VO2MAX: Intervalworkouts op hoge intensiteit (Zone 5)
- SPRINT: Zeer korte, zeer intensieve intervalworkouts (Zone 5+)
"""

# ============================================
# HERSTEL WORKOUTS (Recovery - Intensity 1)
# ============================================

HERSTEL_WANDELING_30MIN = {
    "workout_type": "HERSTEL",
    "name": "Rustige Wandeling 30 minuten",
    "description": "Korte herstelwandeling op zeer lage intensiteit",
    "duration_minutes": 30,
    "intensity_level": 1,
    "steps": [
        {
            "wkt_step_name": "Wandeling",
            "duration_type": "time",
            "duration_value": 1800,  # 30 minuten
            "target_type": "heart_rate",
            "target_value": 1,  # Zone 1
        },
    ]
}

HERSTEL_WANDELING_60MIN = {
    "workout_type": "HERSTEL",
    "name": "Rustige Wandeling 60 minuten",
    "description": "Lange herstelwandeling op zeer lage intensiteit voor actief herstel",
    "duration_minutes": 60,
    "intensity_level": 1,
    "steps": [
        {
            "wkt_step_name": "Wandeling",
            "duration_type": "time",
            "duration_value": 3600,  # 60 minuten
            "target_type": "heart_rate",
            "target_value": 1,  # Zone 1
        },
    ]
}

HERSTEL_FIETS_45MIN = {
    "workout_type": "HERSTEL",
    "name": "Herstelrit 45 minuten",
    "description": "Zeer rustige fietsrit voor actief herstel",
    "duration_minutes": 45,
    "intensity_level": 1,
    "steps": [
        {
            "wkt_step_name": "Herstelrit",
            "duration_type": "time",
            "duration_value": 2700,  # 45 minuten
            "target_type": "heart_rate",
            "target_value": 1,  # Zone 1
        },
    ]
}

HERSTEL_HARDLOPEN_30MIN = {
    "workout_type": "HERSTEL",
    "name": "Herstel 30 minuten",
    "description": "Zeer rustige hardloopsessie op lage intensiteit voor actief herstel",
    "duration_minutes": 30,
    "intensity_level": 1,
    "steps": [
        {
            "wkt_step_name": "Herstelrun",
            "duration_type": "time",
            "duration_value": 1800,  # 30 minuten
            "target_type": "heart_rate",
            "target_value": 1,  # Zone 1
        },
    ]
}

# ============================================
# DUUR WORKOUTS (Endurance - Intensity 2)
# ============================================

# Template voor DUUR workout (60 minuten)
DUUR_TEMPLATE_60MIN = {
    "workout_type": "DUUR",
    "name": "Duurtraining 60 minuten",
    "description": "Lange training op lage intensiteit voor het verbeteren van je aerobe basis",
    "duration_minutes": 60,
    "intensity_level": 2,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 2,  # Zone 2
        },
        {
            "wkt_step_name": "Duurinterval",
            "duration_type": "time",
            "duration_value": 2700,  # 45 minuten
            "target_type": "heart_rate",
            "target_value": 2,  # Zone 2
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,  # Zone 1
        },
    ]
}

# Template voor DUUR workout (90 minuten)
DUUR_TEMPLATE_90MIN = {
    "workout_type": "DUUR",
    "name": "Duurtraining 90 minuten",
    "description": "Zeer lange training op lage intensiteit",
    "duration_minutes": 90,
    "intensity_level": 2,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Duurinterval",
            "duration_type": "time",
            "duration_value": 4500,  # 75 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor THRESHOLD workout (45 minuten)
THRESHOLD_TEMPLATE_45MIN = {
    "workout_type": "THRESHOLD",
    "name": "Drempeltraining 45 minuten",
    "description": "Tempo training op drempelvermogen voor het verhogen van je FTP",
    "duration_minutes": 45,
    "intensity_level": 4,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Drempelinterval 1",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 4,  # Zone 4
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Drempelinterval 2",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 4,
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor THRESHOLD workout (60 minuten)
THRESHOLD_TEMPLATE_60MIN = {
    "workout_type": "THRESHOLD",
    "name": "Drempeltraining 60 minuten",
    "description": "Langere tempo training met 3x10 minuten op drempel",
    "duration_minutes": 60,
    "intensity_level": 4,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 900,  # 15 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Drempelinterval 1",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 4,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Drempelinterval 2",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 4,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Drempelinterval 3",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 4,
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor VO2MAX workout (45 minuten)
VO2MAX_TEMPLATE_45MIN = {
    "workout_type": "VO2MAX",
    "name": "VO2max Intervallen 45 minuten",
    "description": "Korte intensieve intervallen voor het verhogen van je maximale zuurstofopname",
    "duration_minutes": 45,
    "intensity_level": 5,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 900,  # 15 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        # 5x4 minuten intervallen
        {
            "wkt_step_name": "VO2max Interval 1",
            "duration_type": "time",
            "duration_value": 240,  # 4 minuten
            "target_type": "heart_rate",
            "target_value": 5,  # Zone 5
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 120,  # 2 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 2",
            "duration_type": "time",
            "duration_value": 240,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 120,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 3",
            "duration_type": "time",
            "duration_value": 240,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 120,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 4",
            "duration_type": "time",
            "duration_value": 240,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 120,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 5",
            "duration_type": "time",
            "duration_value": 240,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor VO2MAX workout (30 minuten - korter)
VO2MAX_TEMPLATE_30MIN = {
    "workout_type": "VO2MAX",
    "name": "VO2max Intervallen 30 minuten",
    "description": "Korte VO2max sessie met 3x3 minuten",
    "duration_minutes": 30,
    "intensity_level": 5,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 1",
            "duration_type": "time",
            "duration_value": 180,  # 3 minuten
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 180,  # 3 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 2",
            "duration_type": "time",
            "duration_value": 180,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 180,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "VO2max Interval 3",
            "duration_type": "time",
            "duration_value": 180,
            "target_type": "heart_rate",
            "target_value": 5,
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor SPRINT workout (30 minuten)
SPRINT_TEMPLATE_30MIN = {
    "workout_type": "SPRINT",
    "name": "Sprint Intervallen 30 minuten",
    "description": "Zeer korte, maximale inspanningen voor anaerobe power",
    "duration_minutes": 30,
    "intensity_level": 5,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 900,  # 15 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        # 6x30 seconden sprints
        {
            "wkt_step_name": "Sprint 1",
            "duration_type": "time",
            "duration_value": 30,  # 30 seconden
            "target_type": "open",  # Max effort
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 90,  # 1.5 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 2",
            "duration_type": "time",
            "duration_value": 30,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 90,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 3",
            "duration_type": "time",
            "duration_value": 30,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 90,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 4",
            "duration_type": "time",
            "duration_value": 30,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 90,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 5",
            "duration_type": "time",
            "duration_value": 30,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 90,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 6",
            "duration_type": "time",
            "duration_value": 30,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Template voor SPRINT workout (20 minuten - korter)
SPRINT_TEMPLATE_20MIN = {
    "workout_type": "SPRINT",
    "name": "Sprint Intervallen 20 minuten",
    "description": "Korte sprint sessie met 4x20 seconden",
    "duration_minutes": 20,
    "intensity_level": 5,
    "steps": [
        {
            "wkt_step_name": "Warming-up",
            "duration_type": "time",
            "duration_value": 600,  # 10 minuten
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 1",
            "duration_type": "time",
            "duration_value": 20,  # 20 seconden
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 100,  # 1:40
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 2",
            "duration_type": "time",
            "duration_value": 20,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 100,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 3",
            "duration_type": "time",
            "duration_value": 20,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Herstel",
            "duration_type": "time",
            "duration_value": 100,
            "target_type": "heart_rate",
            "target_value": 2,
        },
        {
            "wkt_step_name": "Sprint 4",
            "duration_type": "time",
            "duration_value": 20,
            "target_type": "open",
        },
        {
            "wkt_step_name": "Cool-down",
            "duration_type": "time",
            "duration_value": 300,  # 5 minuten
            "target_type": "heart_rate",
            "target_value": 1,
        },
    ]
}

# Collectie van alle templates
ALL_TEMPLATES = [
    # Herstel workouts (intensity 1)
    HERSTEL_WANDELING_30MIN,
    HERSTEL_WANDELING_60MIN,
    HERSTEL_FIETS_45MIN,
    HERSTEL_HARDLOPEN_30MIN,
    # Duur workouts (intensity 2)
    DUUR_TEMPLATE_60MIN,
    DUUR_TEMPLATE_90MIN,
    # Threshold workouts (intensity 4)
    THRESHOLD_TEMPLATE_45MIN,
    THRESHOLD_TEMPLATE_60MIN,
    # VO2Max workouts (intensity 5)
    VO2MAX_TEMPLATE_30MIN,
    VO2MAX_TEMPLATE_45MIN,
    # Sprint workouts (intensity 5)
    SPRINT_TEMPLATE_20MIN,
    SPRINT_TEMPLATE_30MIN,
]

def get_templates_by_type(workout_type: str):
    """Haal alle templates op voor een specifiek workout type."""
    return [t for t in ALL_TEMPLATES if t["workout_type"] == workout_type]

def get_template_by_name(name: str):
    """Haal een specifieke template op bij naam."""
    for template in ALL_TEMPLATES:
        if template["name"] == name:
            return template
    return None

def get_templates_by_duration(min_duration: int, max_duration: int):
    """Haal templates op binnen een bepaalde duur range."""
    return [t for t in ALL_TEMPLATES if min_duration <= t["duration_minutes"] <= max_duration]

def get_templates_by_intensity(max_intensity: int):
    """Haal templates op met een maximale intensiteit."""
    return [t for t in ALL_TEMPLATES if t["intensity_level"] <= max_intensity]
