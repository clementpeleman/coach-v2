"""Deterministic workout recommendation engine for the web coach."""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional


WORKOUT_TYPES = ["HERSTEL", "DUUR", "THRESHOLD", "VO2MAX", "SPRINT"]
SPORT_TYPES = ["WALKING", "RUNNING", "CYCLING", "INDOOR_CYCLING", "SWIMMING"]

TYPE_LABELS = {
    "HERSTEL": "Herstel",
    "DUUR": "Duur",
    "THRESHOLD": "Drempel",
    "VO2MAX": "VO2 max",
    "SPRINT": "Sprints",
}

SPORT_LABELS = {
    "WALKING": "Wandelen",
    "RUNNING": "Hardlopen",
    "CYCLING": "Fietsen",
    "INDOOR_CYCLING": "Indoor fietsen",
    "SWIMMING": "Zwemmen",
}

GARMIN_SPORT_TYPES = {
    "WALKING": "CARDIO_TRAINING",
    "RUNNING": "RUNNING",
    "CYCLING": "CYCLING",
    "INDOOR_CYCLING": "CYCLING",
    "SWIMMING": "LAP_SWIMMING",
}

SPORT_DURATION_MINUTES = {
    "WALKING": {"HERSTEL": 45, "DUUR": 70, "THRESHOLD": 50, "VO2MAX": 42, "SPRINT": 35},
    "RUNNING": {"HERSTEL": 40, "DUUR": 60, "THRESHOLD": 46, "VO2MAX": 54, "SPRINT": 37},
    "CYCLING": {"HERSTEL": 55, "DUUR": 95, "THRESHOLD": 72, "VO2MAX": 62, "SPRINT": 48},
    "INDOOR_CYCLING": {"HERSTEL": 45, "DUUR": 75, "THRESHOLD": 60, "VO2MAX": 52, "SPRINT": 40},
    "SWIMMING": {"HERSTEL": 28, "DUUR": 42, "THRESHOLD": 38, "VO2MAX": 34, "SPRINT": 30},
}

COLORS = {
    "rest": "oklch(48% 0.05 220)",
    "z1": "oklch(55% 0.06 220)",
    "z2": "oklch(62% 0.10 145)",
    "z3": "oklch(72% 0.14 100)",
    "z4": "oklch(75% 0.18 60)",
    "z5": "oklch(68% 0.22 25)",
}

METRIC_TABLE = {
    "WALKING": {
        "rest": {"pace": "9:30-11:00/km"},
        "z1": {"pace": "9:00-10:15/km"},
        "z2": {"pace": "8:15-9:15/km"},
        "z4": {"pace": "7:10-8:00/km"},
        "z5": {"pace": "6:30-7:15/km"},
    },
    "RUNNING": {
        "rest": {"pace": "7:45-8:45/km"},
        "z1": {"pace": "7:05-8:05/km"},
        "z2": {"pace": "6:20-7:05/km"},
        "z4": {"pace": "4:55-5:15/km"},
        "z5": {"pace": "4:25-4:45/km"},
    },
    "CYCLING": {
        "rest": {"speed": "16-20 km/u"},
        "z1": {"speed": "19-23 km/u"},
        "z2": {"speed": "24-28 km/u"},
        "z4": {"speed": "31-35 km/u"},
        "z5": {"speed": "37-43 km/u"},
    },
    "INDOOR_CYCLING": {
        "rest": {"speed": "18-22 km/u"},
        "z1": {"speed": "22-26 km/u"},
        "z2": {"speed": "27-32 km/u"},
        "z4": {"speed": "34-40 km/u"},
        "z5": {"speed": "42-50 km/u"},
    },
    "SWIMMING": {
        "rest": {"pace": "2:45-3:15/100m"},
        "z1": {"pace": "2:25-2:55/100m"},
        "z2": {"pace": "2:05-2:25/100m"},
        "z4": {"pace": "1:45-2:00/100m"},
        "z5": {"pace": "1:30-1:45/100m"},
    },
}


def build_recommendation(
    *,
    user_id: int,
    recovery: Optional[Dict[str, Any]],
    training_profile: Optional[Dict[str, Any]],
    weather: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build the canonical workout draft for a user."""
    now = now or datetime.utcnow()
    recovery_score = _recovery_score(recovery)
    metrics = recovery.get("metrics") if isinstance(recovery, dict) else {}
    workout_type = _type_from_recovery(recovery_score, metrics or {})
    patterns = (training_profile or {}).get("workout_patterns") or {}
    pattern = (patterns.get("by_type") or {}).get(workout_type) or {}
    sport_type = _choose_sport(workout_type, pattern)
    duration_min = _planned_duration(workout_type, sport_type, pattern)
    personal_profile = ((training_profile or {}).get("personal_targets") or {}).get(sport_type)
    blocks = normalize_workout_blocks(
        fit_blocks_to_duration(build_structure(workout_type, sport_type, personal_profile, pattern), duration_min),
        sport_type,
        workout_type,
    )
    target_mode = preferred_target_mode(blocks, sport_type)
    warnings = _collect_warnings(blocks)
    confidence = _confidence(personal_profile, pattern)
    reasoning = _reasoning(workout_type, sport_type, recovery_score, confidence, pattern, weather, warnings)

    draft_id = _stable_id(user_id, now, workout_type, sport_type, recovery_score)
    return {
        "id": draft_id,
        "status": "draft",
        "type": workout_type,
        "sportType": sport_type,
        "garminSportType": GARMIN_SPORT_TYPES.get(sport_type, "RUNNING"),
        "durationMin": duration_min,
        "targetMode": target_mode,
        "preferredTargetMode": target_mode,
        "intensityPct": 100,
        "blocks": blocks,
        "confidence": confidence,
        "source": "backend",
        "reasoning": reasoning,
        "warnings": warnings,
        "recoveryScore": recovery_score,
        "profileApplied": bool(training_profile),
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
        "note": reasoning[0] if reasoning else "Backend coachvoorstel.",
    }


def adjust_recommendation(
    current: Dict[str, Any],
    instruction: str,
    *,
    training_profile: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Apply a deterministic text instruction to a draft workout."""
    now = now or datetime.utcnow()
    text = (instruction or "").lower()
    next_draft = deepcopy(current or {})
    if not next_draft:
        next_draft = build_recommendation(user_id=0, recovery=None, training_profile=training_profile, now=now)

    changed = False
    rebuild = False
    notes = []

    sport = _infer_sport(text)
    if sport and sport != next_draft.get("sportType"):
        next_draft["sportType"] = sport
        next_draft["durationMin"] = SPORT_DURATION_MINUTES.get(sport, {}).get(next_draft.get("type"), next_draft.get("durationMin", 45))
        changed = True
        rebuild = True
        notes.append(f"sport naar {SPORT_LABELS.get(sport, sport).lower()}")

    workout_type = _infer_type(text)
    if workout_type and workout_type != next_draft.get("type"):
        next_draft["type"] = workout_type
        next_draft["durationMin"] = SPORT_DURATION_MINUTES.get(next_draft.get("sportType"), {}).get(workout_type, next_draft.get("durationMin", 45))
        changed = True
        rebuild = True
        notes.append(f"type naar {TYPE_LABELS.get(workout_type, workout_type).lower()}")

    explicit_duration = _infer_duration(text)
    if explicit_duration:
        next_draft["durationMin"] = explicit_duration
        changed = True
        rebuild = True
        notes.append(f"{explicit_duration} minuten")
    elif re.search(r"\b(korter|compact|minder lang|sneller klaar)\b", text):
        next_draft["durationMin"] = max(20, int(next_draft.get("durationMin") or 45) - 10)
        changed = True
        rebuild = True
        notes.append("korter")
    elif re.search(r"\b(langer|meer volume|uitbreiden|extra lang)\b", text):
        next_draft["durationMin"] = min(150, int(next_draft.get("durationMin") or 45) + 10)
        changed = True
        rebuild = True
        notes.append("langer")

    if re.search(r"\b(rustiger|makkelijker|conservatiever|lager|easy)\b", text):
        next_draft["intensityPct"] = max(90, int(next_draft.get("intensityPct") or 100) - 5)
        changed = True
        notes.append("intensiteit omlaag")
    if re.search(r"\b(harder|zwaarder|scherper|intensiever|steviger)\b", text):
        next_draft["intensityPct"] = min(110, int(next_draft.get("intensityPct") or 100) + 5)
        changed = True
        notes.append("intensiteit omhoog")

    interval = re.search(r"\b(\d{1,2})\s*x\s*(\d{1,2})\s*(min|m|')\b", text)
    if interval and next_draft.get("type") in {"THRESHOLD", "VO2MAX"}:
        personal_profile = ((training_profile or {}).get("personal_targets") or {}).get(next_draft.get("sportType"))
        next_draft["blocks"] = normalize_workout_blocks(
            build_custom_intervals(
                next_draft["type"],
                next_draft["sportType"],
                int(interval.group(1)),
                int(interval.group(2)) * 60,
                personal_profile,
            ),
            next_draft["sportType"],
            next_draft["type"],
        )
        next_draft["durationMin"] = round(sum(block["sec"] for block in next_draft["blocks"]) / 60)
        changed = True
        rebuild = False
        notes.append(f"{interval.group(1)}x{interval.group(2)}min")

    if rebuild:
        sport_type = next_draft.get("sportType") or "RUNNING"
        workout_type = next_draft.get("type") or "DUUR"
        pattern = ((training_profile or {}).get("workout_patterns") or {}).get("by_type", {}).get(workout_type) or {}
        personal_profile = ((training_profile or {}).get("personal_targets") or {}).get(sport_type)
        next_draft["blocks"] = normalize_workout_blocks(
            fit_blocks_to_duration(build_structure(workout_type, sport_type, personal_profile, pattern), next_draft.get("durationMin") or 45),
            sport_type,
            workout_type,
        )

    next_draft["targetMode"] = preferred_target_mode(next_draft.get("blocks", []), next_draft.get("sportType"))
    next_draft["preferredTargetMode"] = next_draft["targetMode"]
    next_draft["warnings"] = _collect_warnings(next_draft.get("blocks", []))
    next_draft["changedByInstruction"] = changed
    next_draft["status"] = "draft"
    next_draft["source"] = "coach" if changed else next_draft.get("source", "backend")
    next_draft["updatedAt"] = now.isoformat()
    if changed:
        next_draft["note"] = f"Aangepast door coach: {', '.join(notes)}."
    return next_draft


def build_structure(
    workout_type: str,
    sport_type: str,
    personal_profile: Optional[Dict[str, Any]] = None,
    pattern: Optional[Dict[str, Any]] = None,
) -> list[Dict[str, Any]]:
    pattern_blocks = _build_pattern_intervals(workout_type, sport_type, personal_profile, pattern or {})
    if pattern_blocks:
        return pattern_blocks

    if workout_type == "HERSTEL":
        return [
            _with_target({"label": "Warming-up", "shortLabel": "WU", "zone": "Z1", "sec": 5 * 60, "hr": "105-122", "color": COLORS["z1"]}, sport_type, "rest", personal_profile),
            _with_target({"label": "Rustige wandeling" if sport_type == "WALKING" else "Easy blok", "shortLabel": "Easy", "zone": "Z1", "sec": 30 * 60, "hr": "110-128", "color": COLORS["rest"]}, sport_type, "rest", personal_profile),
            _with_target({"label": "Cooling-down", "shortLabel": "CD", "zone": "Z1", "sec": 5 * 60, "hr": "100-118", "color": COLORS["z1"]}, sport_type, "rest", personal_profile),
        ]
    if workout_type == "DUUR":
        return [
            _with_target({"label": "Warming-up", "shortLabel": "WU", "zone": "Z1", "sec": 8 * 60, "hr": "125-135", "color": COLORS["z1"]}, sport_type, "z1", personal_profile),
            _with_target({"label": "Duurblok zone 2", "shortLabel": "Z2", "zone": "Z2", "sec": 45 * 60, "hr": "138-152", "color": COLORS["z2"]}, sport_type, "z2", personal_profile),
            _with_target({"label": "Cooling-down", "shortLabel": "CD", "zone": "Z1", "sec": 7 * 60, "hr": "120-135", "color": COLORS["z1"]}, sport_type, "z1", personal_profile),
        ]
    if workout_type == "THRESHOLD":
        return build_custom_intervals(workout_type, sport_type, 2, 12 * 60, personal_profile)
    if workout_type == "VO2MAX":
        return build_custom_intervals(workout_type, sport_type, 6, 3 * 60, personal_profile)
    if workout_type == "SPRINT":
        blocks = [_with_target({"label": "Warming-up", "shortLabel": "WU", "zone": "Z1", "sec": 10 * 60, "hr": "125-138", "color": COLORS["z1"]}, sport_type, "z1", personal_profile)]
        for index in range(10):
            blocks.append(_with_target({"label": f"Sprint {index + 1}", "shortLabel": "SP", "zone": "Z5", "sec": 30, "hr": "> 180", "color": COLORS["z5"]}, sport_type, "z5", personal_profile))
            blocks.append(_with_target({"label": "Herstel", "shortLabel": "rust", "zone": "Z1", "sec": 90, "hr": "110-130", "color": COLORS["rest"]}, sport_type, "rest", personal_profile))
        blocks.append(_with_target({"label": "Cooling-down", "shortLabel": "CD", "zone": "Z1", "sec": 7 * 60, "hr": "120-135", "color": COLORS["z1"]}, sport_type, "z1", personal_profile))
        return blocks
    return []


def build_custom_intervals(
    workout_type: str,
    sport_type: str,
    count: int,
    work_sec: int,
    personal_profile: Optional[Dict[str, Any]] = None,
) -> list[Dict[str, Any]]:
    is_threshold = workout_type == "THRESHOLD"
    work_zone = "z4" if is_threshold else "z5"
    blocks = [_with_target({"label": "Warming-up", "shortLabel": "WU", "zone": "Z1", "sec": 10 * 60, "hr": "125-138", "color": COLORS["z1"]}, sport_type, "z1", personal_profile)]
    rest_sec = 4 * 60 if is_threshold else max(90, min(3 * 60, work_sec))
    for index in range(count):
        blocks.append(_with_target({
            "label": f"{'Tempo blok' if is_threshold else 'VO2 interval'} {index + 1}",
            "shortLabel": "Tempo" if is_threshold else "VO2",
            "zone": "Z4" if is_threshold else "Z5",
            "sec": work_sec,
            "hr": "162-170" if is_threshold else "175-185",
            "color": COLORS[work_zone],
        }, sport_type, work_zone, personal_profile))
        if index < count - 1:
            blocks.append(_with_target({"label": "Herstel", "shortLabel": "rust", "zone": "Z1", "sec": rest_sec, "hr": "130-140", "color": COLORS["z1"]}, sport_type, "z1", personal_profile))
    blocks.append(_with_target({"label": "Cooling-down", "shortLabel": "CD", "zone": "Z1", "sec": 8 * 60, "hr": "120-135", "color": COLORS["z1"]}, sport_type, "z1", personal_profile))
    return blocks


def fit_blocks_to_duration(blocks: list[Dict[str, Any]], duration_min: int) -> list[Dict[str, Any]]:
    target_sec = max(5, round(duration_min or 0)) * 60
    current_sec = sum(block.get("sec", 0) for block in blocks)
    diff = target_sec - current_sec
    if not blocks or abs(diff) < 60:
        return blocks
    work = [(index, block) for index, block in enumerate(blocks) if block.get("zone") != "Z1"]
    targets = work or list(enumerate(blocks))
    total = sum(block.get("sec", 0) for _, block in targets) or current_sec
    target_indexes = {index for index, _ in targets}
    fitted = []
    for index, block in enumerate(blocks):
        if index not in target_indexes:
            fitted.append(block)
            continue
        share = block.get("sec", 0) / total
        min_sec = 20 if block.get("zone") == "Z5" else 60
        fitted.append({**block, "sec": max(min_sec, round(block.get("sec", 0) + diff * share))})
    return fitted


def normalize_workout_blocks(blocks: list[Dict[str, Any]], sport_type: str, workout_type: str) -> list[Dict[str, Any]]:
    normalized = [_normalize_block(block, sport_type, block.get("metricZone") or _zone_to_metric_zone(block.get("zone"))) for block in blocks]
    return _enforce_zone_targets(normalized, sport_type, workout_type)


def preferred_target_mode(blocks: list[Dict[str, Any]], sport_type: Optional[str]) -> str:
    if any(block.get("preferredTargetMode") == "hr" for block in blocks or []):
        return "hr"
    return "pace" if sport_type in {"RUNNING", "WALKING", "SWIMMING", "CYCLING", "INDOOR_CYCLING"} else "hr"


def recommendation_to_workout_steps(recommendation: Dict[str, Any]) -> list[Dict[str, Any]]:
    steps = []
    for block in recommendation.get("blocks") or []:
        zone_num = _zone_number(block.get("zone"))
        steps.append({
            "wkt_step_name": block.get("label") or "Workout step",
            "duration_type": "time",
            "duration_value": int(block.get("sec") or 60),
            "target_type": "heart_rate" if zone_num else "open",
            "target_value": zone_num,
        })
    return steps


def garmin_sport_type(sport_type: str) -> str:
    return GARMIN_SPORT_TYPES.get(sport_type, "RUNNING")


def workout_name(recommendation: Dict[str, Any]) -> str:
    label = TYPE_LABELS.get(recommendation.get("type"), recommendation.get("type", "Workout"))
    sport = SPORT_LABELS.get(recommendation.get("sportType"), recommendation.get("sportType", "Sport"))
    duration = recommendation.get("durationMin") or round(sum(block.get("sec", 0) for block in recommendation.get("blocks", [])) / 60)
    return f"Coach {label} {sport} {duration}m"


def _with_target(block: Dict[str, Any], sport_type: str, metric_zone: str, personal_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    defaults = (METRIC_TABLE.get(sport_type) or METRIC_TABLE["RUNNING"]).get(metric_zone, {})
    effort = _effort_for_zone(metric_zone)
    personal_zone = ((personal_profile or {}).get("zones") or {}).get(effort) or {}
    personal_metric = personal_zone.get("metric")
    metric_safe = _metric_plausible(sport_type, metric_zone, personal_metric)
    next_block = {
        **block,
        **defaults,
        "hr": personal_zone.get("hr") or block.get("hr"),
        "metricZone": metric_zone,
        "personalized": bool(metric_safe or personal_zone.get("hr")),
        "source": personal_zone.get("source") if (metric_safe or personal_zone.get("hr")) else "fallback",
        "warnings": [],
    }
    if (personal_profile or {}).get("metric_type") == "speed":
        next_block["speed"] = personal_metric if metric_safe else defaults.get("speed")
    else:
        next_block["pace"] = personal_metric if metric_safe else defaults.get("pace")
    if personal_metric and not metric_safe:
        next_block["warnings"].append(_fallback_warning(sport_type))
        next_block["preferredTargetMode"] = "hr"
    return _normalize_block(next_block, sport_type, metric_zone)


def _normalize_block(block: Dict[str, Any], sport_type: str, metric_zone: str) -> Dict[str, Any]:
    if sport_type != "RUNNING" or not block.get("pace"):
        return block
    pace_range = _parse_pace_range(block.get("pace"))
    if not pace_range:
        return block
    max_allowed = {"rest": 9 * 60, "z1": 8 * 60 + 45, "z2": 7 * 60 + 35, "z4": 6 * 60 + 25, "z5": 5 * 60 + 45}.get(metric_zone, 9 * 60)
    if pace_range["max"] <= max_allowed:
        return block
    fallback = METRIC_TABLE["RUNNING"].get(metric_zone, {}).get("pace")
    warnings = list(block.get("warnings") or [])
    warnings.append("Tempo begrensd zodat hardlopen geen wandeltempo wordt; hartslag is leidend.")
    return {**block, "pace": fallback or block.get("pace"), "source": "guarded", "warnings": warnings, "preferredTargetMode": "hr"}


def _enforce_zone_targets(blocks: list[Dict[str, Any]], sport_type: str, workout_type: str) -> list[Dict[str, Any]]:
    guarded = []
    for block in blocks:
        zone = block.get("metricZone") or _zone_to_metric_zone(block.get("zone"))
        metric = block.get("speed") if sport_type in {"CYCLING", "INDOOR_CYCLING"} else block.get("pace")
        if metric and not _metric_plausible(sport_type, zone, metric):
            fallback = (METRIC_TABLE.get(sport_type) or {}).get(zone, {})
            warnings = list(block.get("warnings") or [])
            warnings.append("Target begrensd naar een logische sportzone.")
            block = {**block, **fallback, "source": "guarded", "warnings": warnings}
            if sport_type == "RUNNING":
                block["preferredTargetMode"] = "hr"
        guarded.append(block)
    return guarded


def _metric_plausible(sport_type: str, zone: str, metric: Optional[str]) -> bool:
    if not metric:
        return False
    if sport_type == "RUNNING":
        pace = _parse_pace_range(metric)
        if not pace:
            return False
        ceilings = {"rest": 9 * 60, "z1": 8 * 60 + 45, "z2": 7 * 60 + 35, "z4": 6 * 60 + 25, "z5": 5 * 60 + 45}
        floors = {"rest": 4 * 60 + 45, "z1": 4 * 60 + 25, "z2": 4 * 60, "z4": 3 * 60 + 20, "z5": 3 * 60}
        return floors.get(zone, 3 * 60) <= pace["min"] and pace["max"] <= ceilings.get(zone, 9 * 60)
    if sport_type == "WALKING":
        pace = _parse_pace_range(metric)
        return bool(pace and pace["min"] >= 7 * 60 and pace["max"] <= 16 * 60)
    if sport_type == "SWIMMING":
        pace = _parse_pace_range(metric)
        return bool(pace and pace["min"] >= 55 and pace["max"] <= 5 * 60)
    if sport_type in {"CYCLING", "INDOOR_CYCLING"}:
        speed = _parse_numeric_range(metric)
        return bool(speed and speed["min"] >= 8 and speed["max"] <= 65)
    return True


def _type_from_recovery(score: int, metrics: Dict[str, Any]) -> str:
    body_battery = metrics.get("bodyBatteryCurrent")
    penalty = metrics.get("recentTrainingPenalty") or 0
    if body_battery is not None and body_battery <= 25:
        return "HERSTEL"
    if penalty >= 1.1:
        return "HERSTEL"
    if score <= 2:
        return "HERSTEL"
    if score == 3:
        return "DUUR"
    if score == 4:
        return "THRESHOLD"
    return "VO2MAX"


def _choose_sport(workout_type: str, pattern: Dict[str, Any]) -> str:
    preferred = pattern.get("preferred_sport")
    if preferred in SPORT_TYPES:
        return preferred
    if workout_type == "HERSTEL":
        return "RUNNING"
    return "RUNNING"


def _planned_duration(workout_type: str, sport_type: str, pattern: Dict[str, Any]) -> int:
    if pattern.get("typical_duration_min") and (not pattern.get("preferred_sport") or pattern.get("preferred_sport") == sport_type):
        return int(round(pattern["typical_duration_min"]))
    return SPORT_DURATION_MINUTES.get(sport_type, {}).get(workout_type, 45)


def _build_pattern_intervals(workout_type: str, sport_type: str, personal_profile: Optional[Dict[str, Any]], pattern: Dict[str, Any]) -> Optional[list[Dict[str, Any]]]:
    parsed = _parse_pattern_structure(pattern.get("typical_structure"))
    if not parsed or workout_type not in {"THRESHOLD", "VO2MAX", "SPRINT"}:
        return None
    return build_custom_intervals(workout_type, sport_type, parsed["count"], parsed["workSec"], personal_profile)


def _parse_pattern_structure(structure: Optional[str]) -> Optional[Dict[str, int]]:
    match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)(min|s)", str(structure or "").lower())
    if not match:
        return None
    count = int(match.group(1))
    value = float(match.group(2))
    return {"count": count, "workSec": int(value if match.group(3) == "s" else value * 60)}


def _effort_for_zone(zone: str) -> str:
    if zone == "z2":
        return "endurance"
    if zone == "z4":
        return "threshold"
    if zone == "z5":
        return "vo2"
    return "easy"


def _zone_to_metric_zone(zone: Optional[str]) -> str:
    key = str(zone or "").upper()
    if key == "Z5":
        return "z5"
    if key == "Z4":
        return "z4"
    if key == "Z2":
        return "z2"
    if key == "REST":
        return "rest"
    return "z1"


def _zone_number(zone: Optional[str]) -> Optional[int]:
    match = re.search(r"Z([1-5])", str(zone or "").upper())
    return int(match.group(1)) if match else None


def _parse_pace_range(value: Optional[str]) -> Optional[Dict[str, int]]:
    parts = str(value or "").replace("/100m", "").replace("/km", "").split("-")
    seconds = [_pace_to_seconds(part.strip()) for part in parts if part.strip()]
    clean = [item for item in seconds if item is not None]
    if not clean:
        return None
    return {"min": min(clean), "max": max(clean)}


def _pace_to_seconds(value: str) -> Optional[int]:
    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def _parse_numeric_range(value: Optional[str]) -> Optional[Dict[str, float]]:
    nums = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", str(value or ""))]
    if not nums:
        return None
    return {"min": min(nums), "max": max(nums)}


def _recovery_score(recovery: Optional[Dict[str, Any]]) -> int:
    score = recovery.get("score") if isinstance(recovery, dict) else None
    try:
        return max(0, min(6, int(round(score if score is not None else 4))))
    except Exception:
        return 4


def _confidence(personal_profile: Optional[Dict[str, Any]], pattern: Dict[str, Any]) -> str:
    values = [str((personal_profile or {}).get("confidence") or "low"), str(pattern.get("confidence") or "low")]
    if "high" in values:
        return "high"
    if "medium" in values:
        return "medium"
    return "low"


def _collect_warnings(blocks: list[Dict[str, Any]]) -> list[str]:
    warnings = []
    for block in blocks:
        for warning in block.get("warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _reasoning(workout_type: str, sport_type: str, score: int, confidence: str, pattern: Dict[str, Any], weather: Optional[Dict[str, Any]], warnings: list[str]) -> list[str]:
    lines = [f"Recovery {score}/6 kiest {TYPE_LABELS.get(workout_type, workout_type).lower()} voor {SPORT_LABELS.get(sport_type, sport_type).lower()}."]
    if pattern.get("typical_structure"):
        lines.append(f"Structuur gebaseerd op je patroon: {pattern.get('typical_structure')}.")
    lines.append(f"Target confidence: {confidence}.")
    if weather and weather.get("training_note"):
        lines.append(f"Weer: {weather.get('training_note')}.")
    lines.extend(warnings[:2])
    return lines


def _fallback_warning(sport_type: str) -> str:
    if sport_type == "RUNNING":
        return "Persoonlijke pace leek wandeltempo of bevatte pauzes; hartslag is leidend."
    return "Persoonlijke target leek onlogisch; fallback target gebruikt."


def _infer_sport(text: str) -> Optional[str]:
    if re.search(r"\b(zwift|indoor fiets|indoor cycling|rollen)\b", text):
        return "INDOOR_CYCLING"
    if re.search(r"\b(fiets|fietsen|cycling|bike|biken|rit)\b", text):
        return "CYCLING"
    if re.search(r"\b(zwem|zwemmen|swim|baantjes)\b", text):
        return "SWIMMING"
    if re.search(r"\b(wandel|wandelen|walk|stappen)\b", text):
        return "WALKING"
    if re.search(r"\b(loop|lopen|run|running|hardlopen)\b", text):
        return "RUNNING"
    return None


def _infer_type(text: str) -> Optional[str]:
    if re.search(r"\b(herstel|recovery|herstelloop|losfietsen)\b", text):
        return "HERSTEL"
    if re.search(r"\b(duur|zone 2|z2|aeroob|endurance)\b", text):
        return "DUUR"
    if re.search(r"\b(drempel|threshold|tempo)\b", text):
        return "THRESHOLD"
    if re.search(r"\b(vo2|vo2max|interval|intervallen|4x4|3x3|6x3)\b", text):
        return "VO2MAX"
    if re.search(r"\b(sprint|sprints|all-out|all out|30s)\b", text):
        return "SPRINT"
    return None


def _infer_duration(text: str) -> Optional[int]:
    hour = re.search(r"\b(\d+(?:[,.]\d+)?)\s*(u|uur|hour|hours)\b", text)
    if hour:
        return int(round(float(hour.group(1).replace(",", ".")) * 60))
    minutes = re.search(r"\b(\d{2,3})\s*(min|m|minuten)\b", text)
    if minutes:
        return int(minutes.group(1))
    return None


def _stable_id(user_id: int, now: datetime, workout_type: str, sport_type: str, score: int) -> str:
    key = f"{user_id}:{now.date().isoformat()}:{workout_type}:{sport_type}:{score}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"rec-{digest}"
