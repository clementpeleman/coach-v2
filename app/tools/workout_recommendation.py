"""
Workout aanbevelingen tool - leert van history en recovery status.
"""
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.database.models import WorkoutHistory, WorkoutPreferences, GarminHealthData
from app.tools.workout_generator import WORKOUT_RECIPES, get_recommended_durations
from app.tools.recovery_tools import assess_recovery_status
from app.database.database import SessionLocal


def get_workout_recommendations(user_id: int) -> str:
    """
    Analyseert workout history, recovery status en preferences om een workout aan te raden.

    Returns:
        Nederlandse tekstuele aanbeveling met workout type en reden.
    """
    db = SessionLocal()

    try:
        # 1. Haal recovery status op
        recovery_status = assess_recovery_status(user_id)
        recovery_score = _extract_recovery_score(recovery_status)

        # 2. Haal workout preferences op
        preferences = db.query(WorkoutPreferences).filter(
            WorkoutPreferences.user_id == user_id
        ).first()

        # 3. Analyseer recente workout history (laatste 2 weken)
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        recent_workouts = db.query(WorkoutHistory).filter(
            WorkoutHistory.user_id == user_id,
            WorkoutHistory.created_at >= two_weeks_ago
        ).order_by(WorkoutHistory.created_at.desc()).all()

        # 4. Analyseer workout patronen
        workout_analysis = _analyze_workout_patterns(recent_workouts)

        # 5. Bepaal aanbevolen workout type en duur
        workout_type, duration_minutes = _determine_workout_recommendation(
            recovery_score=recovery_score,
            preferences=preferences,
            workout_analysis=workout_analysis
        )

        # 6. Genereer Nederlandse aanbeveling
        recommendation = _format_recommendation(
            workout_type=workout_type,
            duration_minutes=duration_minutes,
            recovery_score=recovery_score,
            workout_analysis=workout_analysis,
            recovery_status=recovery_status
        )

        return recommendation

    finally:
        db.close()


def _extract_recovery_score(recovery_status: str) -> float:
    """Extract recovery score uit de recovery status string."""
    try:
        # Zoek naar "Herstelscore: X/6" in de string
        if "Herstelscore:" in recovery_status:
            score_part = recovery_status.split("Herstelscore:")[1].split("\n")[0].strip()
            score = float(score_part.split("/")[0])
            return score
        return 3.0  # Default middelmatige score
    except:
        return 3.0


def _analyze_workout_patterns(recent_workouts) -> Dict:
    """
    Analyseert recente workout patronen.

    Returns:
        Dict met statistieken over recente workouts.
    """
    if not recent_workouts:
        return {
            "total_workouts": 0,
            "workouts_this_week": 0,
            "type_counts": {},
            "last_workout_type": None,
            "days_since_last_workout": None,
            "needs_variety": False,
        }

    type_counts = {}
    for workout in recent_workouts:
        workout_type = workout.workout_type
        type_counts[workout_type] = type_counts.get(workout_type, 0) + 1

    # Bereken dagen sinds laatste workout
    last_workout_date = recent_workouts[0].created_at
    days_since = (datetime.utcnow() - last_workout_date).days

    # Tel workouts deze week
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    workouts_this_week = sum(1 for w in recent_workouts if w.created_at >= one_week_ago)

    # Check of er variatie nodig is (>50% van workouts is hetzelfde type)
    most_common_type = max(type_counts, key=type_counts.get) if type_counts else None
    needs_variety = False
    if most_common_type and type_counts[most_common_type] > len(recent_workouts) * 0.5:
        needs_variety = True

    return {
        "total_workouts": len(recent_workouts),
        "workouts_this_week": workouts_this_week,
        "type_counts": type_counts,
        "last_workout_type": recent_workouts[0].workout_type if recent_workouts else None,
        "days_since_last_workout": days_since,
        "needs_variety": needs_variety,
        "most_common_type": most_common_type,
    }


def _determine_workout_recommendation(
    recovery_score: float,
    preferences: Optional[WorkoutPreferences],
    workout_analysis: Dict
) -> tuple[str, int]:
    """
    Bepaalt welke workout type en duur aanbevolen wordt.

    Logica:
    - Recovery score < 2: Alleen HERSTEL (wandelen, zeer rustig fietsen)
    - Recovery score 2-3: HERSTEL of DUUR
    - Recovery score 3-4: DUUR of THRESHOLD
    - Recovery score 4-5: DUUR, THRESHOLD, of VO2MAX
    - Recovery score >= 5: Alle types mogelijk
    - Houdt rekening met variatie (niet altijd hetzelfde type)
    - Respecteert user preferences

    Returns:
        Tuple van (workout_type, duration_minutes)
    """

    # Bepaal maximale intensiteit op basis van recovery
    if recovery_score < 2:
        allowed_types = ["HERSTEL"]
    elif recovery_score < 3:
        allowed_types = ["HERSTEL", "DUUR"]
    elif recovery_score < 4:
        allowed_types = ["DUUR", "THRESHOLD"]
    elif recovery_score < 5:
        allowed_types = ["DUUR", "THRESHOLD", "VO2MAX"]
    else:
        allowed_types = ["DUUR", "THRESHOLD", "VO2MAX", "SPRINT"]

    # Filter op basis van user preferences (als beschikbaar)
    if preferences:
        # Filter op voorkeur types
        if preferences.preferred_workout_types:
            try:
                preferred_types = json.loads(preferences.preferred_workout_types)
                # Neem intersectie van allowed en preferred
                allowed_types = [t for t in allowed_types if t in preferred_types]
            except:
                pass

        # Respecteer max intensity preference
        if preferences.max_intensity_level:
            # Filter types op basis van max intensity
            allowed_types = [
                t for t in allowed_types
                if WORKOUT_RECIPES[t]["intensity_level"] <= preferences.max_intensity_level
            ]

    # Als geen types meer beschikbaar, fallback naar HERSTEL
    if not allowed_types:
        allowed_types = ["HERSTEL"]

    # Kies type op basis van variatie behoefte
    if workout_analysis["needs_variety"] and workout_analysis["most_common_type"]:
        # Vermijd het meest gedane type
        most_common = workout_analysis["most_common_type"]
        varied_types = [t for t in allowed_types if t != most_common]
        if varied_types:
            allowed_types = varied_types

    # Kies type op basis van training cyclus
    # Als laatste workout high intensity was, kies low intensity
    last_type = workout_analysis.get("last_workout_type")
    if last_type in ["VO2MAX", "SPRINT"] and workout_analysis["days_since_last_workout"] <= 2:
        # Doe een recovery workout (HERSTEL of DUUR)
        recovery_types = [t for t in allowed_types if t in ["HERSTEL", "DUUR"]]
        if recovery_types:
            allowed_types = recovery_types

    # Als veel workouts deze week, kies lichtere optie
    if workout_analysis["workouts_this_week"] >= 4:
        lighter_types = [t for t in allowed_types if WORKOUT_RECIPES[t]["intensity_level"] <= 3]
        if lighter_types:
            allowed_types = lighter_types

    # Kies random type uit allowed types (voor variatie)
    chosen_type = random.choice(allowed_types)

    # Bepaal duur
    if preferences and preferences.preferred_duration_minutes:
        # Gebruik user preference
        duration = preferences.preferred_duration_minutes
    else:
        # Kies uit aanbevolen duren voor dit type
        recommended_durations = get_recommended_durations(chosen_type)
        duration = random.choice(recommended_durations)

    return chosen_type, duration


def _format_recommendation(
    workout_type: str,
    duration_minutes: int,
    recovery_score: float,
    workout_analysis: Dict,
    recovery_status: str
) -> str:
    """Formatteert de aanbeveling in het Nederlands."""

    lines = []
    lines.append("WORKOUT AANBEVELING")
    lines.append("")

    # Recovery samenvatting
    lines.append(f"Herstelscore: {recovery_score}/6")
    if recovery_score < 2:
        lines.append("Status: Zeer slecht hersteld - Alleen herstel activiteiten aanbevolen")
    elif recovery_score < 3:
        lines.append("Status: Slecht hersteld - Herstel of lichte training aanbevolen")
    elif recovery_score < 4:
        lines.append("Status: Matig hersteld - Lichte tot matige training mogelijk")
    elif recovery_score < 5:
        lines.append("Status: Goed hersteld - Training mogelijk, vermijd zeer hoge intensiteit")
    else:
        lines.append("Status: Uitstekend hersteld - Alle types training mogelijk")
    lines.append("")

    # Workout history samenvatting
    lines.append("RECENTE ACTIVITEIT")
    lines.append(f"Workouts afgelopen 2 weken: {workout_analysis['total_workouts']}")
    lines.append(f"Workouts deze week: {workout_analysis['workouts_this_week']}")
    if workout_analysis["last_workout_type"]:
        lines.append(f"Laatste workout type: {workout_analysis['last_workout_type']}")
        lines.append(f"Dagen geleden: {workout_analysis['days_since_last_workout']}")
    lines.append("")

    # Type verdeling
    if workout_analysis["type_counts"]:
        lines.append("Type verdeling:")
        for wtype, count in workout_analysis["type_counts"].items():
            lines.append(f"  {wtype}: {count}x")
        lines.append("")

    # Aanbevolen workout
    recipe = WORKOUT_RECIPES[workout_type]
    lines.append("AANBEVOLEN WORKOUT")
    lines.append(f"Type: {workout_type}")
    lines.append(f"Duur: {duration_minutes} minuten")
    lines.append(f"Beschrijving: {recipe['description']}")
    lines.append(f"Intensiteit: {recipe['intensity_level']}/5")
    if recipe['structure']['intervals']:
        lines.append(f"Structuur: Intervaltraining (dynamisch gegenereerd)")
    else:
        lines.append(f"Structuur: Continue training")
    lines.append("")

    # Motivatie voor keuze
    lines.append("WAAROM DEZE WORKOUT?")

    if recovery_score < 2:
        lines.append("- Je herstel is momenteel zeer slecht, een herstel activiteit is essentieel")
    elif recovery_score < 3:
        lines.append("- Je herstel is momenteel niet optimaal, een herstel workout of lichte training is het beste")
    elif recovery_score >= 5:
        lines.append("- Je bent uitstekend hersteld en kunt een uitdagende training doen")

    if workout_analysis["needs_variety"]:
        lines.append(f"- Je hebt recent veel {workout_analysis['most_common_type']} workouts gedaan, variatie is goed")

    if workout_analysis["workouts_this_week"] >= 4:
        lines.append("- Je hebt al veel getraind deze week, een lichtere sessie helpt overtraining voorkomen")

    if workout_analysis["last_workout_type"] in ["VO2MAX", "SPRINT"] and workout_analysis["days_since_last_workout"] <= 2:
        lines.append("- Je laatste workout was zeer intensief, je lichaam heeft herstel nodig")

    lines.append("")
    lines.append(f"Vraag me: 'Maak een {workout_type} workout van {duration_minutes} minuten'")

    return "\n".join(lines)


def save_workout_preferences(
    user_id: int,
    preferred_types: Optional[list] = None,
    preferred_duration: Optional[int] = None,
    max_intensity: Optional[int] = None,
    weekly_goal: Optional[int] = None,
    ftp: Optional[int] = None
) -> str:
    """
    Slaat workout preferences op voor een gebruiker.

    Args:
        user_id: Telegram user ID
        preferred_types: Lijst van voorkeur types ["DUUR", "THRESHOLD", etc.]
        preferred_duration: Voorkeur duur in minuten
        max_intensity: Maximale intensiteit (1-5)
        weekly_goal: Doel aantal workouts per week
        ftp: Functional Threshold Power in watts (voor power-based cycling workouts)

    Returns:
        Bevestigingsbericht in het Nederlands
    """
    db = SessionLocal()

    try:
        # Haal bestaande preferences op of maak nieuwe aan
        prefs = db.query(WorkoutPreferences).filter(
            WorkoutPreferences.user_id == user_id
        ).first()

        if not prefs:
            prefs = WorkoutPreferences(user_id=user_id)
            db.add(prefs)

        # Update fields
        if preferred_types is not None:
            prefs.preferred_workout_types = json.dumps(preferred_types)
        if preferred_duration is not None:
            prefs.preferred_duration_minutes = preferred_duration
        if max_intensity is not None:
            prefs.max_intensity_level = max_intensity
        if weekly_goal is not None:
            prefs.weekly_workout_goal = weekly_goal
        if ftp is not None:
            prefs.ftp = ftp

        prefs.updated_at = datetime.utcnow()

        db.commit()

        # Genereer bevestigingsbericht
        lines = ["WORKOUT VOORKEUREN OPGESLAGEN", ""]
        if preferred_types:
            lines.append(f"Voorkeur types: {', '.join(preferred_types)}")
        if preferred_duration:
            lines.append(f"Voorkeur duur: {preferred_duration} minuten")
        if max_intensity:
            lines.append(f"Maximale intensiteit: {max_intensity}/5")
        if weekly_goal:
            lines.append(f"Wekelijks doel: {weekly_goal} workouts")
        if ftp:
            lines.append(f"FTP (Functional Threshold Power): {ftp} watts")

        lines.append("")
        lines.append("Deze voorkeuren worden gebruikt bij het aanbevelen van workouts.")
        if ftp:
            lines.append("Je FTP wordt gebruikt voor power-based cycling workouts.")

        return "\n".join(lines)

    finally:
        db.close()


def get_workout_history_summary(user_id: int, days: int = 30) -> str:
    """
    Haalt workout history op en geeft een samenvatting.

    Args:
        user_id: Telegram user ID
        days: Aantal dagen terug te kijken

    Returns:
        Nederlandse samenvatting van workout history
    """
    db = SessionLocal()

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        workouts = db.query(WorkoutHistory).filter(
            WorkoutHistory.user_id == user_id,
            WorkoutHistory.created_at >= cutoff_date
        ).order_by(WorkoutHistory.created_at.desc()).all()

        if not workouts:
            return f"Geen workouts gevonden in de afgelopen {days} dagen."

        # Analyseer
        type_counts = {}
        for workout in workouts:
            workout_type = workout.workout_type
            type_counts[workout_type] = type_counts.get(workout_type, 0) + 1

        lines = [f"WORKOUT GESCHIEDENIS ({days} dagen)", ""]
        lines.append(f"Totaal aantal workouts: {len(workouts)}")
        lines.append(f"Gemiddeld per week: {len(workouts) / (days / 7):.1f}")
        lines.append("")

        lines.append("VERDELING PER TYPE")
        for workout_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(workouts)) * 100
            lines.append(f"  {workout_type}: {count}x ({percentage:.0f}%)")
        lines.append("")

        lines.append("RECENTE WORKOUTS")
        for workout in workouts[:10]:  # Laatste 10
            date_str = workout.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"  {date_str} - {workout.workout_type}: {workout.workout_name}")

        if len(workouts) > 10:
            lines.append(f"  ... en nog {len(workouts) - 10} workouts")

        return "\n".join(lines)

    finally:
        db.close()
