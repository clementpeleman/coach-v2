"""Recovery assessment tools for intelligent workout planning."""
import datetime
from app.tools.garmin_tools import get_sleep_data, get_stress_data


def assess_recovery_status(user_id: int) -> str:
    """
    Assess user's recovery status based on recent sleep and stress data.

    This tool checks yesterday's sleep and stress to determine if the user
    is well-recovered for intensive training.

    Returns a comprehensive recovery assessment with recommendations.
    """
    try:
        # Get yesterday's date
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # Fetch sleep and stress data
        sleep_summary = get_sleep_data(user_id, yesterday)
        stress_summary = get_stress_data(user_id, yesterday)

        # Build comprehensive assessment
        assessment = f"Recovery Assessment (based on {yesterday}):\n\n"
        assessment += "=== Sleep Analysis ===\n"
        assessment += sleep_summary + "\n\n"
        assessment += "=== Stress Analysis ===\n"
        assessment += stress_summary + "\n\n"

        # Parse sleep data for basic assessment
        recovery_score = 0
        notes = []

        # Simple heuristics for recovery assessment
        if "Error" not in sleep_summary:
            if "7" in sleep_summary or "8" in sleep_summary or "9" in sleep_summary:
                recovery_score += 2
                notes.append("✓ Good sleep duration")
            elif "6" in sleep_summary:
                recovery_score += 1
                notes.append("⚠ Moderate sleep duration")
            else:
                notes.append("⚠ Insufficient sleep duration")

            # Check for sleep score if available
            if "sleep score:" in sleep_summary.lower():
                score_part = sleep_summary.lower().split("sleep score:")[1].strip()
                try:
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

        # Parse stress data
        if "Error" not in stress_summary:
            if "average stress level:" in stress_summary.lower():
                try:
                    avg_stress_part = stress_summary.lower().split("average stress level:")[1].strip()
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
            date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        sleep_summary = get_sleep_data(user_id, date)
        stress_summary = get_stress_data(user_id, date)

        result = f"Recovery Metrics for {date}:\n\n"
        result += sleep_summary + "\n\n"
        result += stress_summary

        return result

    except Exception as e:
        return f"Error: Could not retrieve recovery metrics: {str(e)}"
