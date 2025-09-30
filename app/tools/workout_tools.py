import tempfile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import WorkoutStepDuration, WorkoutStepTarget
from typing import List, Dict, Optional

def create_fit_file(workout_steps: Optional[List[Dict]] = None) -> str:
    """
    Creates a .fit file from a list of workout steps.
    Each step should be a dictionary with keys:
    - wkt_step_name: str
    - duration_type: str (allowed values: 'time', 'distance', 'hr_less_than', 'hr_greater_than', 'calories', 'open', 'repeat_until_steps_cmplt', 'repeat_until_time', 'repeat_until_distance', 'repeat_until_calories', 'repeat_until_hr_less_than', 'repeat_until_hr_greater_than', 'repeat_until_power_less_than', 'repeat_until_power_greater_than', 'power_less_than', 'power_greater_than', 'training_peaks_tss', 'repeat_until_training_peaks_tss', 'repetition_time', 'reps')
    - duration_value: int (e.g., seconds, meters)
    - target_type: str (allowed values: 'speed', 'heart_rate', 'open', 'cadence', 'power', 'grade', 'resistance', 'power_3s', 'power_10s', 'power_30s', 'power_lap', 'swim_stroke', 'speed_lap', 'heart_rate_lap')
    - target_value: int (e.g., heart rate zone)
    If workout_steps is not provided, a default workout will be created.
    Returns the path to the created .fit file.
    """
    builder = FitFileBuilder(auto_define=True)

    if not workout_steps:
        # Create a default workout if none is provided
        workout_steps = [
            {
                "wkt_step_name": "Warm-up",
                "duration_type": "time",
                "duration_value": 600,  # 10 minutes
                "target_type": "open",
            },
            {
                "wkt_step_name": "Ride",
                "duration_type": "distance",
                "duration_value": 10000,  # 10 km
                "target_type": "heart_rate",
                "target_value": 3, # Zone 3
            },
            {
                "wkt_step_name": "Cool-down",
                "duration_type": "time",
                "duration_value": 300,  # 5 minutes
                "target_type": "open",
            },
        ]

    duration_type_map = {
        'time': WorkoutStepDuration.TIME,
        'distance': WorkoutStepDuration.DISTANCE,
        'hr_less_than': WorkoutStepDuration.HR_LESS_THAN,
        'hr_greater_than': WorkoutStepDuration.HR_GREATER_THAN,
        'calories': WorkoutStepDuration.CALORIES,
        'open': WorkoutStepDuration.OPEN,
        'repeat_until_steps_cmplt': WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT,
        'repeat_until_time': WorkoutStepDuration.REPEAT_UNTIL_TIME,
        'repeat_until_distance': WorkoutStepDuration.REPEAT_UNTIL_DISTANCE,
        'repeat_until_calories': WorkoutStepDuration.REPEAT_UNTIL_CALORIES,
        'repeat_until_hr_less_than': WorkoutStepDuration.REPEAT_UNTIL_HR_LESS_THAN,
        'repeat_until_hr_greater_than': WorkoutStepDuration.REPEAT_UNTIL_HR_GREATER_THAN,
        'repeat_until_power_less_than': WorkoutStepDuration.REPEAT_UNTIL_POWER_LESS_THAN,
        'repeat_until_power_greater_than': WorkoutStepDuration.REPEAT_UNTIL_POWER_GREATER_THAN,
        'power_less_than': WorkoutStepDuration.POWER_LESS_THAN,
        'power_greater_than': WorkoutStepDuration.POWER_GREATER_THAN,
        'training_peaks_tss': WorkoutStepDuration.TRAINING_PEAKS_TSS,
        'repeat_until_training_peaks_tss': WorkoutStepDuration.REPEAT_UNTIL_TRAINING_PEAKS_TSS,
        'repetition_time': WorkoutStepDuration.REPETITION_TIME,
        'reps': WorkoutStepDuration.REPS,
    }

    target_type_map = {
        'speed': WorkoutStepTarget.SPEED,
        'heart_rate': WorkoutStepTarget.HEART_RATE,
        'open': WorkoutStepTarget.OPEN,
        'cadence': WorkoutStepTarget.CADENCE,
        'power': WorkoutStepTarget.POWER,
        'grade': WorkoutStepTarget.GRADE,
        'resistance': WorkoutStepTarget.RESISTANCE,
        'power_3s': WorkoutStepTarget.POWER_3S,
        'power_10s': WorkoutStepTarget.POWER_10S,
        'power_30s': WorkoutStepTarget.POWER_30S,
        'power_lap': WorkoutStepTarget.POWER_LAP,
        'swim_stroke': WorkoutStepTarget.SWIM_STROKE,
        'speed_lap': WorkoutStepTarget.SPEED_LAP,
        'heart_rate_lap': WorkoutStepTarget.HEART_RATE_LAP,
    }

    for step in workout_steps:
        step_message = WorkoutStepMessage()
        step_message.wkt_step_name = step.get("wkt_step_name")
        
        duration_type_str = step.get("duration_type")
        if duration_type_str in duration_type_map:
            step_message.duration_type = duration_type_map[duration_type_str]
        
        duration_value = step.get("duration_value")
        if duration_value is not None:
            try:
                step_message.duration_value = int(duration_value)
            except (ValueError, TypeError):
                pass

        target_type_str = step.get("target_type")
        if target_type_str in target_type_map:
            step_message.target_type = target_type_map[target_type_str]

        target_value = step.get("target_value")
        if target_value is not None:
            try:
                step_message.target_value = int(target_value)
            except (ValueError, TypeError):
                pass

        builder.add(step_message)

    fit_file = builder.build()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as fp:
        fp.write(fit_file.to_bytes())
        fit_file_path = fp.name

    return fit_file_path
