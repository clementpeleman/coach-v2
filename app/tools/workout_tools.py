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
    - duration_type: str (allowed values: 'time', 'distance', etc.)
    - duration_value: int (for 'time' duration, value is in seconds; for 'distance', value is in meters)
    - target_type: str (allowed values: 'speed', 'heart_rate', etc.)
    - target_value: int (e.g., heart rate zone)
    If workout_steps is not provided, a default workout will be created.
    Returns the path to the created .fit file.
    """
    try:
        builder = FitFileBuilder(auto_define=True)
    except Exception as e:
        raise ValueError(f"Failed to initialize FIT file builder: {e}")

    if not workout_steps:
        # Create a default workout if none is provided
        workout_steps = [
            {
                "wkt_step_name": "Warm-up",
                "duration_type": "time",
                "duration_value": 600,  # 10 minutes in seconds
                "target_type": "open",
            },
            {
                "wkt_step_name": "Ride",
                "duration_type": "distance",
                "duration_value": 10000,  # 10 km in meters
                "target_type": "heart_rate",
                "target_value": 3, # Zone 3
            },
            {
                "wkt_step_name": "Cool-down",
                "duration_type": "time",
                "duration_value": 300,  # 5 minutes in seconds
                "target_type": "open",
            },
        ]

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

        return fit_file_path

    except Exception as e:
        raise ValueError(f"Failed to create FIT file: {str(e)}")
