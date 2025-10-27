"""Recovery assessment tools for intelligent workout planning."""
import datetime
from app.tools.garmin_tools import get_health_data


def assess_recovery_status(user_id: int) -> str:
    """
    Assess user's recovery status based on recent sleep and stress data.

    This tool checks yesterday's sleep and stress to determine if the user
    is well-recovered for intensive training.

    Returns a comprehensive recovery assessment with recommendations.
    """
    try:
        # Get yesterday's date (using today's date if no data for yesterday yet)
        today = datetime.date.today()
        yesterday = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # Fetch sleep and stress data
        health_data = get_health_data(user_id, data_types=['sleeps', 'stress'], start_date=yesterday)

        # Build comprehensive assessment
        assessment = f"Recovery Assessment (based on {yesterday}):\n\n"
        assessment += health_data + "\n\n"

        # Parse health data for recovery score
        recovery_score = 0
        notes = []

        # Simple heuristics for recovery assessment
        if "Error" not in health_data:
            # Check sleep duration
            if " 7" in health_data or " 8" in health_data or " 9" in health_data:
                recovery_score += 2
                notes.append("✓ Good sleep duration")
            elif " 6" in health_data:
                recovery_score += 1
                notes.append("⚠ Moderate sleep duration")
            elif "Total sleep:" in health_data:
                notes.append("⚠ Insufficient sleep duration")

            # Check for sleep score if available
            if "sleep score:" in health_data.lower():
                try:
                    score_part = health_data.lower().split("sleep score:")[1].strip()
                    score = int(score_part.split("/")[0].strip())
                    if score >= 80:
                        recovery_score += 2
                        notes.append("✓ Excellent sleep quality")
                    elif score >= 60:
                        recovery_score += 1
                        notes.append("⚠ Moderate sleep quality")
                    else:
                        notes.append("⚠ Poor sleep quality")
                except:
                    pass

            # Check stress data
            if "average stress:" in health_data.lower():
                try:
                    avg_stress_part = health_data.lower().split("average stress:")[1].strip()
                    avg_stress = int(avg_stress_part.split("\n")[0].strip())
                    if avg_stress < 30:
                        recovery_score += 2
                        notes.append("✓ Low average stress")
                    elif avg_stress < 50:
                        recovery_score += 1
                        notes.append("⚠ Moderate average stress")
                    else:
                        notes.append("⚠ High average stress")
                except:
                    pass

        # Generate recommendation
        assessment += "=== Recovery Status ===\n"
        for note in notes:
            assessment += f"{note}\n"

        assessment += f"\nRecovery Score: {recovery_score}/6\n\n"

        if recovery_score >= 5:
            assessment += "✓ WELL RECOVERED - Ready for intensive training\n"
            assessment += "Recommendation: Can proceed with challenging workouts"
        elif recovery_score >= 3:
            assessment += "⚠ MODERATE RECOVERY - Consider moderate intensity\n"
            assessment += "Recommendation: Light to moderate training recommended"
        else:
            assessment += "⚠ POOR RECOVERY - Rest or very light activity advised\n"
            assessment += "Recommendation: Rest day or easy recovery session only"

        return assessment

    except Exception as e:
        return f"Error: Could not assess recovery status: {str(e)}"


def get_recovery_metrics(user_id: int, date: str = None) -> str:
    """
    Get recovery metrics for a specific date.

    Args:
        user_id: User ID
        date: Date in YYYY-MM-DD format. If None, uses yesterday.

    Returns comprehensive recovery data.
    """
    try:
        if not date:
            today = datetime.date.today()
            date = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        health_data = get_health_data(user_id, data_types=['sleeps', 'stress'], start_date=date)

        result = f"Recovery Metrics for {date}:\n\n"
        result += health_data

        return result

    except Exception as e:
        return f"Error: Could not retrieve recovery metrics: {str(e)}"
