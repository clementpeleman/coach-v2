"""Structured activity analyses for coach chat and UI chart cards."""
from __future__ import annotations

import json
import math
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from html import escape
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.models import GarminActivityAuxiliaryData, GarminActivityData

MAX_ANALYSIS_DAYS = 365
DEFAULT_TREND_DAYS = 84
DEFAULT_RECENT_DAYS = 30
DEFAULT_PATTERN_DAYS = 120

SPORT_ALIASES = {
    "RUNNING": ("run", "running", "hardloop", "hardlopen", "lopen", "loop", "jog"),
    "CYCLING": ("fiets", "fietsen", "cycling", "ride", "rit", "wielren", "bike"),
    "INDOOR_CYCLING": ("zwift", "indoor fiets", "indoor cycling", "trainer"),
    "SWIMMING": ("zwem", "zwemmen", "swim", "swimming", "baantjes"),
    "WALKING": ("wandel", "wandelen", "walk", "walking"),
}

SPORT_LABELS = {
    "RUNNING": "Hardlopen",
    "CYCLING": "Fietsen",
    "INDOOR_CYCLING": "Indoor fietsen",
    "SWIMMING": "Zwemmen",
    "WALKING": "Wandelen",
    "OTHER": "Overig",
}


def detect_activity_analysis_request(
    message: str,
    last_context: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Return a bounded structured analysis request for activity-analysis questions."""
    text = (message or "").strip().lower()
    if not text:
        return None

    sport = _detect_sport(text)
    data_source = _detect_data_source(text)
    today = date.today()

    follow_up = _looks_like_analysis_follow_up(text)
    if follow_up and last_context:
        request = dict(last_context)
        request["message"] = message
        if sport:
            request["sport"] = sport
        if data_source:
            request["data_source"] = data_source
        if "grafiek" in text or "chart" in text:
            request["wants_chart"] = True
        coerced = _coerce_request(request, today=today)
        coerced["needs_coach_answer"] = analysis_request_needs_coach_answer(message, coerced)
        coerced["attach_card"] = _should_attach_analysis_card(text, coerced, follow_up=True)
        return coerced

    intent = _detect_intent(text)
    if not intent:
        return None
    if intent == "sport_breakdown":
        sport = None

    period = _detect_period(text, intent, today)
    request = _coerce_request(
        {
            "intent": intent,
            "message": message,
            "sport": sport,
            "start_date": period["start_date"].isoformat(),
            "end_date": period["end_date"].isoformat(),
            "bucket": period.get("bucket"),
            "data_source": data_source or "auto",
            "compare_start_date": period.get("compare_start_date").isoformat()
            if period.get("compare_start_date")
            else None,
            "compare_end_date": period.get("compare_end_date").isoformat()
            if period.get("compare_end_date")
            else None,
        },
        today=today,
    )
    request["needs_coach_answer"] = analysis_request_needs_coach_answer(message, request)
    request["attach_card"] = _should_attach_analysis_card(text, request, follow_up=False)
    return request


def build_activity_analysis(
    db: Session,
    user_id: int,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Build a chart-ready, read-only activity analysis for one user."""
    normalized = _coerce_request(request, today=date.today())
    start_dt = _date_start(normalized["start_date"])
    end_dt = _date_end(normalized["end_date"])
    compare_start = _date_start(normalized["compare_start_date"]) if normalized.get("compare_start_date") else None
    compare_end = _date_end(normalized["compare_end_date"]) if normalized.get("compare_end_date") else None

    query_start = compare_start or start_dt
    activities = _load_activities(db, user_id, query_start, end_dt, normalized.get("sport"))
    details = _load_activity_details(
        db,
        user_id,
        query_start,
        end_dt,
        normalized.get("sport"),
        summary_ids=[activity.summary_id for activity in activities if activity.summary_id],
    )
    summary_rows = [_activity_row(activity) for activity in activities]
    rows, detail_stats = _analysis_rows(activities, details, normalized.get("data_source", "auto"))
    current_rows = [row for row in rows if start_dt <= row["start_time"] <= end_dt]
    current_summary_rows = [row for row in summary_rows if start_dt <= row["start_time"] <= end_dt]
    compare_rows = [
        row for row in rows if compare_start and compare_end and compare_start <= row["start_time"] <= compare_end
    ]

    intent = normalized["intent"]
    if intent == "compare_periods":
        result = _compare_periods(current_rows, compare_rows, normalized)
    elif intent == "sport_breakdown":
        result = _sport_breakdown(current_rows, normalized)
    elif intent == "pace_hr_correlation":
        result = _pace_hr_correlation(current_rows, normalized)
    elif intent == "hr_response_kinetics":
        result = _hr_response_kinetics(activities, details, normalized)
    elif intent == "personal_records":
        result = _personal_records(current_summary_rows, normalized)
    elif intent == "workout_pattern_analysis":
        result = _workout_patterns(activities, details, normalized)
    else:
        result = _activity_trend(current_rows, normalized)

    result["analysis_id"] = result.get("analysis_id") or f"ana-{uuid.uuid4().hex[:10]}"
    result["context"] = normalized
    coverage = _coverage(rows, current_rows, normalized, compare_rows=compare_rows, detail_stats=detail_stats)
    coverage.update(result.pop("_coverage_overrides", {}) or {})
    result["coverage"] = coverage
    result["confidence"] = _confidence(result["coverage"], intent)
    result["follow_up_suggestions"] = _follow_up_suggestions(intent, normalized)
    return result


def build_activity_analysis_reply(result: dict[str, Any]) -> str:
    """Make a compact HTML reply that points at the structured card."""
    title = escape(str(result.get("title") or "Activiteitenanalyse"))
    summary = escape(str(result.get("summary") or "Ik heb je activiteiten geanalyseerd."))
    confidence = result.get("confidence") or {}
    level = escape(str(confidence.get("level") or "low"))
    coverage = result.get("coverage") or {}
    sessions = coverage.get("sessions", 0)
    source_label = escape(str(_data_source_label(coverage.get("effective_data_source"))))
    period = result.get("context") or {}
    start = escape(str(period.get("start_date") or "?"))
    end = escape(str(period.get("end_date") or "?"))
    message = str(period.get("message") or "").lower()
    coach_answer = _deterministic_analysis_answer(result, message)
    if coach_answer:
        return coach_answer
    return (
        f"<b>{title}</b><br/>"
        f"{summary}<br/><br/>"
        f"<i>Ik heb er een grafiekkaart bij gezet. Datadekking: {sessions} sessies, "
        f"{start} tot {end}, bron {source_label}, vertrouwen {level}.</i>"
    )


def analysis_request_needs_coach_answer(message: str, request: Optional[dict[str, Any]] = None) -> bool:
    """Return true when the user asks for interpretation, not only a chart."""
    text = (message or "").lower()
    if not text:
        return False
    explanatory = (
        "waarom", "hoezo", "hoe komt", "waardoor", "verklaar", "betekent",
        "interpreteer", "duid", "moet ik", "wat zegt", "wat betekent",
        "is dit normaal", "kan deze", "kan dat", "advies",
    )
    ranking = ("welke", "top", "beste", "slechtste", "effici")
    if any(word in text for word in explanatory):
        return True
    if "effici" in text and any(word in text for word in ranking):
        return True
    if request and request.get("intent") == "pace_hr_correlation" and "hartslag" in text and len(text) > 70:
        return True
    return False


def summarize_activity_analysis_for_prompt(result: dict[str, Any]) -> str:
    """Compact analysis context for the conversational agent."""
    coverage = result.get("coverage") or {}
    confidence = result.get("confidence") or {}
    metrics = result.get("metrics") or []
    chart = result.get("chart") or {}
    table = result.get("table") or {}
    rows = table.get("rows") or []
    points = chart.get("points") or []
    efficiency = result.get("efficiency_rank") or {}
    findings = result.get("coach_findings") or []

    lines = [
        f"Titel: {result.get('title')}",
        f"Samenvatting: {result.get('summary')}",
        f"Databron: {coverage.get('effective_data_source')} "
        f"({coverage.get('detail_segments', 0)} detailsegmenten, "
        f"{coverage.get('fallback_summary_activities', 0)} summary fallback activiteiten)",
        f"Dekking: {coverage.get('sessions')} sessies, {coverage.get('points')} punten, "
        f"HR-dekking {coverage.get('hr_coverage')}, confidence {confidence.get('level')}.",
        "Metrics: "
        + "; ".join(
            f"{item.get('label')}={item.get('value')}{item.get('unit') or ''}"
            for item in metrics
            if isinstance(item, dict)
        ),
    ]
    if points:
        lines.append(
            "Grafiekpunten: "
            + "; ".join(
                f"{point.get('label')} ({point.get('date')}): x={point.get('x')} {chart.get('xLabel')}, "
                f"HR={point.get('y')} bpm"
                for point in points[:12]
                if isinstance(point, dict)
            )
        )
    if efficiency.get("best"):
        lines.append(
            "Meest efficiente punten: "
            + "; ".join(
                f"{item.get('label')} {item.get('date')}: score {item.get('score')}, "
                f"pace {item.get('pace')}, HR {item.get('heart_rate')}"
                for item in efficiency.get("best", [])[:5]
            )
        )
    if rows:
        lines.append(
            "Tabelrijen: "
            + "; ".join(" | ".join(str(cell) for cell in row) for row in rows[:8] if isinstance(row, list))
        )
    if findings:
        lines.append("Coach findings: " + "; ".join(str(item) for item in findings[:8]))
    lines.append(
        "Antwoord als coach in het Nederlands. Geef eerst de interpretatie op de vraag. "
        "Herhaal niet alleen dat er een grafiekkaart is. Wees voorzichtig met medische conclusies."
    )
    return "\n".join(lines)


def _deterministic_analysis_answer(result: dict[str, Any], message: str) -> Optional[str]:
    intent = result.get("intent")
    if intent == "hr_response_kinetics":
        metrics = {item.get("label"): item.get("value") for item in result.get("metrics", []) if isinstance(item, dict)}
        findings = result.get("coach_findings") or []
        findings_html = "".join(f"<li>{escape(str(item))}</li>" for item in findings[:4])
        if not findings_html:
            findings_html = "<li>Er zijn nog te weinig ActivityDetails-samples om blokrespons betrouwbaar te meten.</li>"
        return (
            "<b>HR-respons binnen je training</b><br/>"
            "Ik kijk hier niet naar de sessiesummary, maar naar samples/laps binnen de activiteit: "
            "hoe snel je hartslag stijgt na versnellen, en hoe goed ze zakt na een rustiger blok.<br/><br/>"
            f"<ul>{findings_html}</ul>"
            f"<i>Gemiddelde lag: {escape(str(metrics.get('Gem. lag') or 'n.v.t.'))} sec. "
            f"Snelste stijging: {escape(str(metrics.get('Snelste stijging') or 'n.v.t.'))} bpm/min.</i>"
        )
    if intent != "pace_hr_correlation":
        return None

    efficiency = result.get("efficiency_rank") or {}
    if "effici" in message and efficiency.get("best"):
        best = efficiency["best"][:3]
        rows = "".join(
            "<li>"
            f"{escape(str(item.get('label') or 'Sessie'))} ({escape(str(item.get('date') or '?'))}): "
            f"{escape(str(item.get('pace') or item.get('speed_kmh') or '?'))}, "
            f"{escape(str(item.get('heart_rate') or '?'))} bpm"
            "</li>"
            for item in best
        )
        return (
            "<b>Meest efficiënte sessies in deze set</b><br/>"
            "Ik rangschik hier pragmatisch: bij lopen is een lagere combinatie van tempo en hartslag beter. "
            "Dat is geen labtest, maar wel bruikbaar om trends te zien.<br/><br/>"
            f"<ol>{rows}</ol>"
            "<i>Tip: vergelijk dit liefst binnen hetzelfde type sessie, bijvoorbeeld easy met easy of tempo met tempo.</i>"
        )

    explanatory_words = (
        "waarom", "hoezo", "hoe komt", "waardoor", "verklaar", "betekent",
        "is dit normaal", "kan deze", "kan dat",
    )
    if not any(word in message for word in explanatory_words):
        return None

    metrics = {item.get("label"): item.get("value") for item in result.get("metrics", []) if isinstance(item, dict)}
    corr = metrics.get("Correlatie")
    avg_hr = metrics.get("Gem. HR")
    coverage = result.get("coverage") or {}
    source_label = _data_source_label(coverage.get("effective_data_source"))
    return (
        "<b>Kort antwoord: je hartslag lijkt in deze data vrij snel mee te stijgen met inspanning, "
        "maar deze grafiek bewijst niet één oorzaak.</b><br/><br/>"
        f"De correlatie is <b>{escape(str(corr))}</b>. Omdat pace in min/km werkt, betekent een negatieve correlatie meestal: "
        "lager getal = sneller tempo = hogere hartslag. Dat is op zich logisch. "
        f"Je gemiddelde HR in de gebruikte punten is <b>{escape(str(avg_hr))} bpm</b> "
        f"op basis van <b>{coverage.get('sessions', 0)} sessies</b> ({escape(source_label)}).<br/><br/>"
        "Dat je bij wandelen richting 135 bpm kan gaan, kan komen door helling/wind, warmte, vermoeidheid, stress, "
        "cafeïne/dehydratie, weinig warming-up, of soms sensorruis/cadence lock. "
        "Als dit nieuw is, ook in rust hoog blijft, of gepaard gaat met duizeligheid, pijn op de borst of benauwdheid: "
        "laat dat medisch checken.<br/><br/>"
        "<i>Beste volgende analyse: toon dezelfde vraag specifiek voor wandelen met activityDetails, "
        "dan vergelijken we wandeltempo, helling/segmenten en HR apart van je looptrainingen.</i>"
    )


def _detect_intent(text: str) -> Optional[str]:
    analysis_words = (
        "analyse", "analyseer", "grafiek", "chart", "toon", "bekijk", "hoe was",
        "activiteiten", "activiteit", "trainingen", "trainingsweek", "week",
        "trend", "evolutie", "vergelijk", "record", "records", "patroon", "patronen",
        "correlatie", "effici", "hartslag", "tempo", "pace", "snelheid",
        "afstand", "volume", "belasting", "progressie", "blok", "blokken",
        "interval", "intervallen", "respons", "response", "vertraging", "lag",
        "stijgt", "stijgen", "zakt", "daalt",
    )
    if not any(word in text for word in analysis_words):
        return None
    if _looks_like_hr_response_question(text):
        return "hr_response_kinetics"
    if any(word in text for word in ("sportverdeling", "verdeling", "per sport", "loop vs fiets", "fietsen vs lopen")):
        return "sport_breakdown"
    if any(word in text for word in ("correlatie", "effici", "hartslag", "bpm", "pace", "tempo", "snelheid")):
        return "pace_hr_correlation"
    if any(word in text for word in ("vergelijk", "versus", " vs ", "tegenover", "verschil")):
        if ("loop" in text or "lopen" in text or "hardloop" in text) and ("fiets" in text or "fietsen" in text):
            return "sport_breakdown"
        return "compare_periods"
    if any(word in text for word in ("record", "records", "langste", "snelste", "beste", "zwaarste", "top")):
        return "personal_records"
    if any(word in text for word in ("patroon", "patronen", "vaak", "typisch", "type workout", "workouttype")):
        return "workout_pattern_analysis"
    if any(word in text for word in ("trend", "evolutie", "per week", "per maand", "volume", "afstand")):
        return "activity_trend"
    if any(word in text for word in ("analyse", "analyseer", "trainingsweek", "week", "activiteiten", "trainingen")):
        return "activity_trend"
    return None


def _looks_like_hr_response_question(text: str) -> bool:
    has_hr = any(word in text for word in ("hartslag", "bpm", "hr", "heart rate"))
    has_response = any(
        word in text
        for word in (
            "stijgt", "stijgen", "zakt", "zakken", "daalt", "dalen",
            "respons", "response", "vertraging", "lag", "reageert", "reactie",
            "snel", "hoe snel", "herstel na", "recovery drop",
        )
    )
    has_block_context = any(
        word in text
        for word in (
            "blok", "blokken", "interval", "intervallen", "tempo verandering",
            "tempoverandering", "snelheidsverandering", "verschillende blokken",
            "doorheen training", "binnen training",
        )
    )
    return has_hr and has_response and has_block_context


def _should_attach_analysis_card(text: str, request: dict[str, Any], follow_up: bool) -> bool:
    explicit_visual = any(
        word in text
        for word in (
            "grafiek", "chart", "kaart", "toon", "laat zien", "visualiseer",
            "plot", "zelfde analyse", "activitydetails", "activity details",
            "summary", "samenvatting", "beste bron",
        )
    )
    if explicit_visual:
        return True
    if follow_up:
        return False
    if not request.get("needs_coach_answer"):
        return True
    interpretation_only = any(
        word in text
        for word in (
            "waarom", "hoezo", "hoe komt", "waardoor", "verklaar", "betekent",
            "wat zegt", "welke", "advies", "is dit normaal",
        )
    )
    return not interpretation_only


def _looks_like_analysis_follow_up(text: str) -> bool:
    phrases = (
        "ook", "zelfde", "daarvan", "maak", "toon", "filter",
        "alleen", "zonder", "meer detail", "details", "summary", "samenvatting",
        "activitydetails", "laps", "samples", "per week", "per maand", "grafiek",
    )
    if len(text) >= 80:
        return False
    if "effici" in text or "welke sessies" in text:
        return True
    if re.search(r"\b(en|die)\b", text):
        return True
    return any(phrase in text for phrase in phrases)


def _detect_sport(text: str) -> Optional[str]:
    for sport, aliases in SPORT_ALIASES.items():
        if any(alias in text for alias in aliases):
            return sport
    return None


def _detect_data_source(text: str) -> Optional[str]:
    if any(word in text for word in ("summary", "summaries", "samenvatting", "alleen activities")):
        return "summary"
    if any(
        word in text
        for word in (
            "details", "detail", "activitydetails", "activity details", "laps",
            "samples", "segmenten", "segment", "punten", "uit de activiteit zelf",
            "niet summary", "niet enkel summary",
        )
    ):
        return "details"
    if "auto" in text or "beste bron" in text:
        return "auto"
    return None


def _detect_period(text: str, intent: str, today: date) -> dict[str, Any]:
    if intent == "personal_records":
        days = MAX_ANALYSIS_DAYS
    elif intent == "workout_pattern_analysis":
        days = DEFAULT_PATTERN_DAYS
    elif intent == "activity_trend":
        days = DEFAULT_TREND_DAYS
    else:
        days = DEFAULT_RECENT_DAYS

    number_days = _parse_days(text)
    if number_days:
        days = number_days

    if "deze week" in text or "huidige week" in text or "mijn week" in text or "trainingsweek" in text:
        start = today - timedelta(days=today.weekday())
        end = today
        if intent == "compare_periods":
            prev_end = start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=6)
            return {
                "start_date": start,
                "end_date": end,
                "compare_start_date": prev_start,
                "compare_end_date": prev_end,
                "bucket": "day",
            }
        return {"start_date": start, "end_date": end, "bucket": "day"}

    if "vorige week" in text:
        current_start = today - timedelta(days=today.weekday())
        start = current_start - timedelta(days=7)
        end = current_start - timedelta(days=1)
        return {"start_date": start, "end_date": end, "bucket": "day"}

    if "deze maand" in text or "huidige maand" in text:
        start = today.replace(day=1)
        end = today
        if intent == "compare_periods":
            prev_end = start - timedelta(days=1)
            prev_start = prev_end.replace(day=1)
            return {
                "start_date": start,
                "end_date": end,
                "compare_start_date": prev_start,
                "compare_end_date": prev_end,
                "bucket": "week",
            }
        return {"start_date": start, "end_date": end, "bucket": "week"}

    if "vorige maand" in text:
        first_this_month = today.replace(day=1)
        prev_end = first_this_month - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return {"start_date": prev_start, "end_date": prev_end, "bucket": "week"}

    days = min(max(days, 1), MAX_ANALYSIS_DAYS)
    start = today - timedelta(days=days - 1)
    end = today
    bucket = "week" if days > 21 else "day"
    period = {"start_date": start, "end_date": end, "bucket": bucket}
    if intent == "compare_periods":
        period["compare_end_date"] = start - timedelta(days=1)
        period["compare_start_date"] = period["compare_end_date"] - timedelta(days=days - 1)
    return period


def _parse_days(text: str) -> Optional[int]:
    import re

    match = re.search(r"\b(\d{1,3})\s*(dagen|days|d)\b", text)
    if match:
        return int(match.group(1))
    if "30d" in text or "30 d" in text:
        return 30
    if "7d" in text or "7 d" in text:
        return 7
    if "90d" in text or "90 d" in text:
        return 90
    return None


def _coerce_request(request: dict[str, Any], today: date) -> dict[str, Any]:
    intent = request.get("intent") or "activity_trend"
    start = _parse_date(request.get("start_date")) or (today - timedelta(days=DEFAULT_RECENT_DAYS - 1))
    end = _parse_date(request.get("end_date")) or today
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > MAX_ANALYSIS_DAYS:
        start = end - timedelta(days=MAX_ANALYSIS_DAYS - 1)
    if intent == "compare_periods" and ((end - start).days + 1) * 2 > MAX_ANALYSIS_DAYS:
        start = end - timedelta(days=(MAX_ANALYSIS_DAYS // 2) - 1)

    compare_start = _parse_date(request.get("compare_start_date"))
    compare_end = _parse_date(request.get("compare_end_date"))
    if intent == "compare_periods" and (not compare_start or not compare_end):
        days = (end - start).days + 1
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - timedelta(days=days - 1)
    if intent == "compare_periods" and compare_start and (end - compare_start).days + 1 > MAX_ANALYSIS_DAYS:
        days = (end - start).days + 1
        compare_end = start - timedelta(days=1)
        compare_start = max(compare_end - timedelta(days=days - 1), end - timedelta(days=MAX_ANALYSIS_DAYS - 1))

    return {
        "intent": intent,
        "message": request.get("message"),
        "sport": request.get("sport"),
        "data_source": request.get("data_source") if request.get("data_source") in {"auto", "details", "summary"} else "auto",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "compare_start_date": compare_start.isoformat() if compare_start else None,
        "compare_end_date": compare_end.isoformat() if compare_end else None,
        "bucket": request.get("bucket") or ("week" if (end - start).days > 21 else "day"),
        "needs_coach_answer": bool(request.get("needs_coach_answer")),
        "attach_card": bool(request.get("attach_card", True)),
    }


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None


def _date_start(value: str) -> datetime:
    return datetime.combine(_parse_date(value) or date.today(), time.min)


def _date_end(value: str) -> datetime:
    return datetime.combine(_parse_date(value) or date.today(), time.max)


def _load_activities(
    db: Session,
    user_id: int,
    start: datetime,
    end: datetime,
    sport: Optional[str],
) -> list[GarminActivityData]:
    query = (
        db.query(GarminActivityData)
        .filter(GarminActivityData.user_id == user_id)
        .filter(GarminActivityData.start_time >= start)
        .filter(GarminActivityData.start_time <= end)
        .order_by(GarminActivityData.start_time.asc())
    )
    activities = query.all()
    if not sport:
        return activities
    return [activity for activity in activities if _normalize_sport(activity) == sport]


def _load_activity_details(
    db: Session,
    user_id: int,
    start: datetime,
    end: datetime,
    _sport: Optional[str],
    summary_ids: Optional[list[str]] = None,
) -> list[GarminActivityAuxiliaryData]:
    range_filter = GarminActivityAuxiliaryData.start_time >= start
    range_filter = range_filter & (GarminActivityAuxiliaryData.start_time <= end)
    if summary_ids:
        range_filter = or_(range_filter, GarminActivityAuxiliaryData.summary_id.in_(summary_ids))
    query = (
        db.query(GarminActivityAuxiliaryData)
        .filter(GarminActivityAuxiliaryData.user_id == user_id)
        .filter(GarminActivityAuxiliaryData.summary_type == "activityDetails")
        .filter(range_filter)
        .order_by(GarminActivityAuxiliaryData.start_time.asc())
    )
    return query.all()


def _analysis_rows(
    activities: list[GarminActivityData],
    details: list[GarminActivityAuxiliaryData],
    requested_source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_rows = [_activity_row(activity) for activity in activities]
    if requested_source == "summary":
        return summary_rows, {
            "requested_data_source": "summary",
            "effective_data_source": "summary",
            "detail_activities": 0,
            "detail_segments": 0,
            "fallback_summary_activities": len(summary_rows),
        }

    detail_rows: list[dict[str, Any]] = []
    detail_activity_keys: set[str] = set()
    detail_index = _build_detail_index(details)
    for activity in activities:
        sport = _normalize_sport(activity)
        segments = _detail_segments_for_activity(activity, detail_index, sport)
        if not segments:
            detail_rows.append(_activity_row(activity, source="summary_fallback"))
            continue
        activity_key = _activity_key(activity)
        detail_activity_keys.add(activity_key)
        for index, segment in enumerate(segments):
            detail_rows.append(_segment_row(activity, segment, index, sport))

    detail_segments = sum(1 for row in detail_rows if row.get("source") == "activityDetails")
    if detail_segments == 0:
        return summary_rows, {
            "requested_data_source": requested_source,
            "effective_data_source": "summary",
            "detail_activities": 0,
            "detail_segments": 0,
            "fallback_summary_activities": len(summary_rows),
        }

    return detail_rows, {
        "requested_data_source": requested_source,
        "effective_data_source": "activityDetails" if len(detail_activity_keys) == len(activities) else "mixed",
        "detail_activities": len(detail_activity_keys),
        "detail_segments": detail_segments,
        "fallback_summary_activities": max(0, len(activities) - len(detail_activity_keys)),
    }


def _build_detail_index(details: list[GarminActivityAuxiliaryData]) -> dict[str, dict[str, Any]]:
    try:
        from app.api.garmin import _build_activity_detail_index

        return _build_activity_detail_index(details)
    except Exception:
        index: dict[str, dict[str, Any]] = {}
        for detail in details:
            payload = _raw_payload(detail)
            for key in [detail.summary_id, detail.activity_id, str(payload.get("summaryId") or ""), str(payload.get("activityId") or "")]:
                if key:
                    index[key] = payload
        return index


def _detail_segments_for_activity(
    activity: GarminActivityData,
    detail_index: dict[str, dict[str, Any]],
    sport: str,
) -> list[dict[str, Any]]:
    try:
        from app.api.garmin import _activity_detail_for, _segments_from_detail

        detail = _activity_detail_for(activity, detail_index)
        return _segments_from_detail(detail, sport) if detail else []
    except Exception:
        return []


def _activity_row(activity: GarminActivityData, source: str = "summary") -> dict[str, Any]:
    return _activity_row_from_values(activity, source=source)


def _activity_row_from_values(activity: GarminActivityData, source: str = "summary") -> dict[str, Any]:
    duration_seconds = int(activity.duration or 0)
    distance_meters = float(activity.distance or 0)
    distance_km = distance_meters / 1000 if distance_meters else 0
    duration_hours = duration_seconds / 3600 if duration_seconds else 0
    avg_hr = activity.average_heart_rate
    speed_kmh = (distance_km / duration_hours) if duration_hours and distance_km else None
    pace_min_km = (duration_seconds / 60 / distance_km) if distance_km else None
    return {
        "id": activity.id,
        "activity_key": _activity_key(activity),
        "summary_id": activity.summary_id,
        "activity_id": activity.activity_id,
        "name": activity.activity_name or _sport_label(_normalize_sport(activity)),
        "activity_name": activity.activity_name or _sport_label(_normalize_sport(activity)),
        "segment_label": "Hele sessie",
        "sport": _normalize_sport(activity),
        "start_time": activity.start_time,
        "date": activity.start_time.date().isoformat() if activity.start_time else None,
        "duration_seconds": duration_seconds,
        "duration_hours": duration_hours,
        "duration_min": duration_seconds / 60 if duration_seconds else 0,
        "distance_km": distance_km,
        "calories": activity.calories or 0,
        "avg_hr": avg_hr,
        "max_hr": activity.max_heart_rate,
        "speed_kmh": speed_kmh,
        "pace_min_km": pace_min_km,
        "load": _rough_load(duration_seconds, avg_hr, activity.max_heart_rate),
        "source": source,
        "sample_count": None,
    }


def _segment_row(
    activity: GarminActivityData,
    segment: dict[str, Any],
    index: int,
    sport: str,
) -> dict[str, Any]:
    duration_seconds = int(segment.get("duration_seconds") or 0)
    distance_meters = float(segment.get("distance_meters") or 0)
    distance_km = distance_meters / 1000 if distance_meters else 0
    duration_hours = duration_seconds / 3600 if duration_seconds else 0
    avg_hr = round(segment["heart_rate"]) if segment.get("heart_rate") else None
    speed_mps = segment.get("speed_mps")
    speed_kmh = float(speed_mps) * 3.6 if speed_mps else ((distance_km / duration_hours) if duration_hours and distance_km else None)
    pace_min_km = (duration_seconds / 60 / distance_km) if distance_km else None
    activity_name = activity.activity_name or _sport_label(sport)
    segment_label = f"Segment {index + 1}"
    start_time = activity.start_time + timedelta(seconds=index) if activity.start_time else datetime.min
    return {
        "id": activity.id,
        "activity_key": _activity_key(activity),
        "summary_id": activity.summary_id,
        "activity_id": activity.activity_id,
        "name": f"{activity_name} · {segment_label}",
        "activity_name": activity_name,
        "segment_label": segment_label,
        "sport": sport,
        "start_time": start_time,
        "date": activity.start_time.date().isoformat() if activity.start_time else None,
        "duration_seconds": duration_seconds,
        "duration_hours": duration_hours,
        "duration_min": duration_seconds / 60 if duration_seconds else 0,
        "distance_km": distance_km,
        "calories": None,
        "avg_hr": avg_hr,
        "max_hr": activity.max_heart_rate,
        "speed_kmh": speed_kmh,
        "pace_min_km": pace_min_km,
        "load": _rough_load(duration_seconds, avg_hr, activity.max_heart_rate),
        "source": "activityDetails",
        "sample_count": segment.get("sample_count"),
    }


def _activity_key(activity: GarminActivityData) -> str:
    return str(activity.summary_id or activity.activity_id or activity.id)


def _raw_payload(row: Any) -> dict[str, Any]:
    raw = getattr(row, "data", None)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _normalize_sport(activity: GarminActivityData) -> str:
    try:
        from app.api.garmin import normalize_training_sport

        return normalize_training_sport(activity)
    except Exception:
        return _normalize_raw_sport(_raw_payload(activity), fallback=activity.activity_type)


def _normalize_raw_sport(raw: dict[str, Any], fallback: Optional[str] = None) -> str:
    value = str(raw.get("activityType") or raw.get("summaryType") or fallback or "").upper()
    if "RUN" in value:
        return "RUNNING"
    if "INDOOR" in value and ("CYCL" in value or "BIK" in value):
        return "INDOOR_CYCLING"
    if "CYCL" in value or "BIK" in value:
        return "CYCLING"
    if "SWIM" in value:
        return "SWIMMING"
    if "WALK" in value or "HIKE" in value:
        return "WALKING"
    return "OTHER"


def _rough_load(duration_seconds: int, avg_hr: Optional[int], max_hr: Optional[int]) -> float:
    minutes = duration_seconds / 60
    if not minutes:
        return 0
    if avg_hr and max_hr:
        intensity = max(0.45, min(1.15, avg_hr / max(max_hr, 1)))
    elif avg_hr:
        intensity = max(0.45, min(1.05, avg_hr / 190))
    else:
        intensity = 0.65
    return round(minutes * (intensity ** 2), 1)


def _activity_trend(rows: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    bucket = request.get("bucket") or "week"
    grouped = _group_rows(rows, bucket)
    labels = list(grouped.keys())
    sessions = [item["sessions"] for item in grouped.values()]
    distance = [round(item["distance_km"], 1) for item in grouped.values()]
    duration = [round(item["duration_hours"], 1) for item in grouped.values()]
    totals = _totals(rows)
    sport_part = f" voor {_sport_label(request.get('sport'))}" if request.get("sport") else ""
    return {
        "intent": "activity_trend",
        "title": f"Activiteitstrend{sport_part}",
        "summary": (
            f"{totals['sessions']} sessies, {totals['distance_km']:.1f} km en "
            f"{totals['duration_hours']:.1f} uur in deze periode."
        ),
        "metrics": _metric_tiles(totals),
        "chart": {
            "type": "line",
            "title": "Volume per " + ("week" if bucket == "week" else "dag"),
            "x": labels,
            "series": [
                {"label": "Afstand km", "unit": "km", "values": distance},
                {"label": "Duur uren", "unit": "u", "values": duration},
                {"label": "Sessies", "unit": "", "values": sessions},
            ],
        },
        "table": _activity_table(rows[-8:]),
    }


def _compare_periods(
    current_rows: list[dict[str, Any]],
    compare_rows: list[dict[str, Any]],
    request: dict[str, Any],
) -> dict[str, Any]:
    current = _totals(current_rows)
    previous = _totals(compare_rows)
    deltas = {
        "sessions": _pct_delta(current["sessions"], previous["sessions"]),
        "distance_km": _pct_delta(current["distance_km"], previous["distance_km"]),
        "duration_hours": _pct_delta(current["duration_hours"], previous["duration_hours"]),
        "load": _pct_delta(current["load"], previous["load"]),
    }
    distance_delta = deltas["distance_km"]
    direction = _delta_word(distance_delta)
    return {
        "intent": "compare_periods",
        "title": "Periodevergelijking",
        "summary": (
            f"Deze periode is je afstand {direction} "
            f"({current['distance_km']:.1f} km vs {previous['distance_km']:.1f} km)."
        ),
        "metrics": [
            {"label": "Sessies", "value": current["sessions"], "compare": previous["sessions"], "delta_percent": deltas["sessions"]},
            {"label": "Afstand", "value": round(current["distance_km"], 1), "unit": "km", "compare": round(previous["distance_km"], 1), "delta_percent": deltas["distance_km"]},
            {"label": "Duur", "value": round(current["duration_hours"], 1), "unit": "u", "compare": round(previous["duration_hours"], 1), "delta_percent": deltas["duration_hours"]},
            {"label": "Load", "value": round(current["load"], 1), "compare": round(previous["load"], 1), "delta_percent": deltas["load"]},
        ],
        "chart": {
            "type": "bar",
            "title": "Huidig vs vorige periode",
            "x": ["Vorige", "Huidige"],
            "series": [
                {"label": "Afstand km", "unit": "km", "values": [round(previous["distance_km"], 1), round(current["distance_km"], 1)]},
                {"label": "Duur uren", "unit": "u", "values": [round(previous["duration_hours"], 1), round(current["duration_hours"], 1)]},
                {"label": "Load", "unit": "", "values": [round(previous["load"], 1), round(current["load"], 1)]},
            ],
        },
        "table": {
            "columns": ["Metric", "Vorige", "Huidige", "Delta"],
            "rows": [
                ["Sessies", previous["sessions"], current["sessions"], _format_delta(deltas["sessions"])],
                ["Afstand", f"{previous['distance_km']:.1f} km", f"{current['distance_km']:.1f} km", _format_delta(deltas["distance_km"])],
                ["Duur", f"{previous['duration_hours']:.1f} u", f"{current['duration_hours']:.1f} u", _format_delta(deltas["duration_hours"])],
                ["Load", f"{previous['load']:.1f}", f"{current['load']:.1f}", _format_delta(deltas["load"])],
            ],
        },
    }


def _sport_breakdown(rows: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"sessions": 0, "distance_km": 0, "duration_hours": 0})
    for row in rows:
        item = grouped[row["sport"]]
        item["sessions"] += 1
        item["distance_km"] += row["distance_km"]
        item["duration_hours"] += row["duration_hours"]
    items = sorted(grouped.items(), key=lambda item: item[1]["duration_hours"], reverse=True)
    labels = [_sport_label(sport) for sport, _ in items]
    totals = _totals(rows)
    top = labels[0] if labels else "geen sport"
    return {
        "intent": "sport_breakdown",
        "title": "Sportverdeling",
        "summary": f"Je meeste trainingstijd ging naar {top}. Totaal: {totals['duration_hours']:.1f} uur.",
        "metrics": _metric_tiles(totals),
        "chart": {
            "type": "bar",
            "title": "Duur per sport",
            "x": labels,
            "series": [
                {"label": "Duur uren", "unit": "u", "values": [round(data["duration_hours"], 1) for _, data in items]},
                {"label": "Afstand km", "unit": "km", "values": [round(data["distance_km"], 1) for _, data in items]},
                {"label": "Sessies", "unit": "", "values": [data["sessions"] for _, data in items]},
            ],
        },
        "table": {
            "columns": ["Sport", "Sessies", "Km", "Uren"],
            "rows": [[_sport_label(sport), int(data["sessions"]), round(data["distance_km"], 1), round(data["duration_hours"], 1)] for sport, data in items],
        },
    }


def _pace_hr_correlation(rows: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    sport = request.get("sport") or "RUNNING"
    relevant = [row for row in rows if row["avg_hr"] and row["distance_km"] > 0 and row["duration_min"] > 5]
    if sport:
        relevant = [row for row in relevant if row["sport"] == sport]

    pace_sport = sport in {"RUNNING", "WALKING", "SWIMMING"}
    points = []
    for row in relevant:
        x_value = row["pace_min_km"] if pace_sport else row["speed_kmh"]
        if not x_value or not math.isfinite(x_value):
            continue
        points.append({
            "x": round(x_value, 2),
            "y": row["avg_hr"],
            "label": row["name"],
            "date": row["date"],
            "distance_km": round(row["distance_km"], 1),
            "duration_min": round(row["duration_min"], 1),
            "source": row.get("source"),
        })
    corr = _correlation([p["x"] for p in points], [p["y"] for p in points])
    summary = "Te weinig sessies met hartslag en tempo om betrouwbaar te interpreteren."
    if corr is not None:
        relation = "sterk" if abs(corr) >= 0.65 else "matig" if abs(corr) >= 0.35 else "zwak"
        summary = f"De relatie tussen {'tempo' if pace_sport else 'snelheid'} en hartslag is {relation} (r={corr:.2f})."
    efficiency_rank = _efficiency_rank(points, pace_sport)
    return {
        "intent": "pace_hr_correlation",
        "title": f"{_sport_label(sport)}: tempo vs hartslag",
        "summary": summary,
        "metrics": [
            {"label": "Sessies", "value": len({str(row.get("activity_key") or row.get("id")) for row in relevant})},
            {"label": "Datapunten", "value": len(points)},
            {"label": "Gem. HR", "value": _avg([p["y"] for p in points]), "unit": "bpm"},
            {"label": "Correlatie", "value": round(corr, 2) if corr is not None else "n.v.t."},
        ],
        "chart": {
            "type": "scatter",
            "title": ("Pace min/km vs HR" if pace_sport else "Snelheid km/u vs HR"),
            "xLabel": "min/km" if pace_sport else "km/u",
            "yLabel": "bpm",
            "points": points,
        },
        "efficiency_rank": efficiency_rank,
        "table": _activity_table(sorted(relevant, key=lambda row: row["start_time"], reverse=True)[:8]),
    }


def _hr_response_kinetics(
    activities: list[GarminActivityData],
    details: list[GarminActivityAuxiliaryData],
    request: dict[str, Any],
) -> dict[str, Any]:
    sport = request.get("sport")
    detail_index = _build_detail_index(details)
    candidates: list[dict[str, Any]] = []
    for activity in sorted(activities, key=lambda item: item.start_time or datetime.min, reverse=True):
        normalized_sport = _normalize_sport(activity)
        if sport and normalized_sport != sport:
            continue
        detail = _detail_payload_for_activity(activity, detail_index)
        series = _sample_series(activity, detail, normalized_sport) if detail else []
        if len(series) >= 24:
            candidates.append({
                "activity": activity,
                "sport": normalized_sport,
                "detail": detail,
                "series": series,
            })

    if not candidates:
        return {
            "intent": "hr_response_kinetics",
            "title": "HR-respons binnen training",
            "summary": "Ik heb hiervoor ActivityDetails-samples nodig; die ontbreken nog voor de gekozen periode/sport.",
            "metrics": [
                {"label": "Sessies", "value": 0},
                {"label": "Samples", "value": 0},
                {"label": "Blokken", "value": 0},
                {"label": "Gem. lag", "value": "n.v.t.", "unit": "sec"},
            ],
            "chart": None,
            "table": {"columns": ["Blok", "Duur", "Tempo/snelheid", "HR", "Stijging", "Lag", "Herstel 60s"], "rows": []},
            "coach_findings": [
                "Zet Activity Details-webhook aan en importeer activityDetails; summaries zijn te grof voor HR-respons per blok.",
            ],
            "_coverage_overrides": {
                "sessions": 0,
                "points": 0,
                "sample_points": 0,
                "blocks": 0,
                "effective_data_source": "summary",
            },
        }

    # Prefer the latest activity that actually has multiple meaningful blocks.
    analysed = None
    for candidate in candidates:
        blocks = _response_blocks(candidate["series"], candidate["detail"])
        block_stats = _block_response_stats(blocks, candidate["series"], candidate["sport"])
        meaningful = [block for block in block_stats if block.get("duration_seconds", 0) >= 45]
        if len(meaningful) >= 3:
            analysed = {**candidate, "blocks": blocks, "block_stats": meaningful}
            break
    if analysed is None:
        candidate = candidates[0]
        blocks = _response_blocks(candidate["series"], candidate["detail"])
        analysed = {
            **candidate,
            "blocks": blocks,
            "block_stats": _block_response_stats(blocks, candidate["series"], candidate["sport"]),
        }

    activity = analysed["activity"]
    sport = analysed["sport"]
    series = analysed["series"]
    block_stats = analysed["block_stats"]
    pace_sport = sport in {"RUNNING", "WALKING", "SWIMMING"}
    lag_values = [item["lag_seconds"] for item in block_stats if item.get("lag_seconds") is not None]
    rise_values = [item["rise_bpm_per_min"] for item in block_stats if item.get("rise_bpm_per_min") is not None]
    recovery_values = [item["recovery_drop_60s"] for item in block_stats if item.get("recovery_drop_60s") is not None]
    drift_values = [item["drift_bpm"] for item in block_stats if item.get("drift_bpm") is not None]
    fastest = max(rise_values) if rise_values else None
    avg_lag = _avg(lag_values)
    avg_recovery = _avg(recovery_values)
    max_drift = max(drift_values) if drift_values else None
    title = f"{_sport_label(sport)}: HR-respons per blok"
    activity_name = activity.activity_name or _sport_label(sport)
    summary = (
        f"Ik analyseer {activity_name}: {len(block_stats)} blokken met samples. "
        "Dit toont hoe HR reageert op tempo/snelheidswissels binnen de training."
    )
    findings = _response_findings(block_stats, pace_sport)
    chart_points = _thin_series(series, max_points=120)
    metric_values = [
        item["pace_min_km"] if pace_sport else item["speed_kmh"]
        for item in chart_points
    ]
    metric_unit = "min/km" if pace_sport else "km/u"
    chart = {
        "type": "dual_line",
        "title": "Hartslag vs tempo doorheen sessie",
        "xLabel": "min",
        "x": [round(item["elapsed_s"] / 60, 1) for item in chart_points],
        "series": [
            {"label": "Hartslag", "unit": "bpm", "values": [item["hr"] for item in chart_points]},
            {
                "label": "Tempo" if pace_sport else "Snelheid",
                "unit": metric_unit,
                "values": [round(value, 2) if value is not None else None for value in metric_values],
                "invert": pace_sport,
            },
        ],
        "blocks": [
            {
                "start": round(item["start_s"] / 60, 1),
                "end": round(item["end_s"] / 60, 1),
                "label": item["label"],
                "kind": item.get("kind") or "steady",
            }
            for item in block_stats[:18]
        ],
    }
    return {
        "intent": "hr_response_kinetics",
        "title": title,
        "summary": summary,
        "metrics": [
            {"label": "Blokken", "value": len(block_stats)},
            {"label": "Samples", "value": len(series)},
            {"label": "Gem. lag", "value": avg_lag if avg_lag is not None else "n.v.t.", "unit": "sec"},
            {"label": "Snelste stijging", "value": round(fastest, 1) if fastest is not None else "n.v.t.", "unit": "bpm/min"},
            {"label": "Herstel 60s", "value": avg_recovery if avg_recovery is not None else "n.v.t.", "unit": "bpm"},
            {"label": "Max drift", "value": round(max_drift, 1) if max_drift is not None else "n.v.t.", "unit": "bpm"},
        ],
        "chart": chart,
        "table": {
            "columns": ["Blok", "Duur", "Tempo/snelheid", "HR", "Stijging", "Lag", "Herstel 60s"],
            "rows": [_response_table_row(item, pace_sport) for item in block_stats[:12]],
        },
        "coach_findings": findings,
        "_coverage_overrides": {
            "sessions": 1,
            "points": len(block_stats),
            "sample_points": len(series),
            "blocks": len(block_stats),
            "effective_data_source": "activityDetails",
            "detail_segments": len(block_stats),
            "hr_coverage": round(
                len([item for item in series if item.get("hr") is not None]) / max(1, len(series)),
                2,
            ),
            "distance_coverage": round(
                len([item for item in series if item.get("distance_m") is not None]) / max(1, len(series)),
                2,
            ),
        },
    }


def _personal_records(rows: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    candidates = [row for row in rows if row["duration_seconds"] > 0]
    longest = sorted(candidates, key=lambda row: row["distance_km"], reverse=True)[:5]
    fastest_running = [
        row for row in candidates
        if row["sport"] in {"RUNNING", "WALKING"} and row.get("pace_min_km") and row["distance_km"] >= 1
    ]
    fastest_running = sorted(fastest_running, key=lambda row: row["pace_min_km"])[:5]
    highest_load = sorted(candidates, key=lambda row: row["load"], reverse=True)[:5]
    rows_out = []
    if longest:
        top = longest[0]
        rows_out.append(["Langste afstand", top["name"], top["date"], f"{top['distance_km']:.1f} km"])
    if fastest_running:
        top = fastest_running[0]
        rows_out.append(["Snelste looptempo", top["name"], top["date"], _format_pace(top["pace_min_km"])])
    if highest_load:
        top = highest_load[0]
        rows_out.append(["Hoogste load", top["name"], top["date"], f"{top['load']:.1f}"])
    return {
        "intent": "personal_records",
        "title": "Persoonlijke uitschieters",
        "summary": f"Ik vond {len(rows_out)} duidelijke uitschieters in de gekozen periode.",
        "metrics": [
            {"label": "Gecheckt", "value": len(candidates), "unit": "sessies"},
            {"label": "Langste", "value": round(longest[0]["distance_km"], 1) if longest else 0, "unit": "km"},
            {"label": "Zwaarste load", "value": round(highest_load[0]["load"], 1) if highest_load else 0},
        ],
        "chart": {
            "type": "bar",
            "title": "Top afstanden",
            "x": [row["date"] or "?" for row in longest],
            "series": [{"label": "Afstand km", "unit": "km", "values": [round(row["distance_km"], 1) for row in longest]}],
        },
        "table": {"columns": ["Record", "Activiteit", "Datum", "Waarde"], "rows": rows_out},
    }


def _efficiency_rank(points: list[dict[str, Any]], pace_sport: bool) -> dict[str, list[dict[str, Any]]]:
    ranked = []
    for point in points:
        x_value = point.get("x")
        hr = point.get("y")
        if not isinstance(x_value, (int, float)) or not isinstance(hr, (int, float)) or hr <= 0:
            continue
        if pace_sport:
            score = x_value * hr
            sort_value = score
        else:
            score = x_value / hr
            sort_value = -score
        ranked.append({
            "label": point.get("label"),
            "date": point.get("date"),
            "score": round(score, 2),
            "pace": _format_pace(x_value) if pace_sport else None,
            "speed_kmh": round(x_value, 1) if not pace_sport else None,
            "heart_rate": hr,
            "distance_km": point.get("distance_km"),
            "duration_min": point.get("duration_min"),
            "_sort": sort_value,
        })
    ranked.sort(key=lambda item: item["_sort"])
    for item in ranked:
        item.pop("_sort", None)
    return {
        "best": ranked[:5],
        "worst": ranked[-5:][::-1],
        "method": "pace_x_hr_lower_is_better" if pace_sport else "speed_per_hr_higher_is_better",
    }


def _workout_patterns(
    activities: list[GarminActivityData],
    details: list[GarminActivityAuxiliaryData],
    request: dict[str, Any],
) -> dict[str, Any]:
    try:
        from app.api.garmin import build_workout_patterns

        patterns = build_workout_patterns(activities, details)
    except Exception:
        patterns = {"dominant_types": [], "by_type": {}, "weekly_pattern": {}}
    dominant = patterns.get("dominant_types") or []
    by_type = patterns.get("by_type") or {}
    top = dominant[0]["type"] if dominant else "onbekend"
    return {
        "intent": "workout_pattern_analysis",
        "title": "Workoutpatronen",
        "summary": f"Je meest terugkerende type is {top}. Ik gebruik dit ook als context voor trainingsvoorstellen.",
        "metrics": [
            {"label": "Types", "value": len(dominant)},
            {"label": "Easy share", "value": patterns.get("weekly_pattern", {}).get("easy_share"), "unit": ""},
            {"label": "Hard/week", "value": patterns.get("weekly_pattern", {}).get("hard_sessions_per_week"), "unit": ""},
        ],
        "chart": {
            "type": "bar",
            "title": "Workouttypes",
            "x": [item["type"] for item in dominant],
            "series": [{"label": "Sessies", "unit": "", "values": [item["count"] for item in dominant]}],
        },
        "table": {
            "columns": ["Type", "Sessies", "Sport", "Duur", "Structuur", "Confidence"],
            "rows": [
                [
                    workout_type,
                    data.get("sessions"),
                    _sport_label(data.get("preferred_sport")),
                    f"{data.get('typical_duration_min') or '?'} min",
                    data.get("typical_structure") or "continu",
                    data.get("confidence") or "low",
                ]
                for workout_type, data in by_type.items()
            ],
        },
        "patterns": patterns,
    }


def _detail_payload_for_activity(
    activity: GarminActivityData,
    detail_index: dict[str, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    try:
        from app.api.garmin import _activity_detail_for

        return _activity_detail_for(activity, detail_index)
    except Exception:
        for key in [activity.activity_id, activity.summary_id, str(activity.summary_id).replace("-detail", "") if activity.summary_id else None]:
            if key is not None and str(key) in detail_index:
                return detail_index[str(key)]
    return None


def _sample_series(
    activity: GarminActivityData,
    detail: dict[str, Any],
    sport: str,
) -> list[dict[str, Any]]:
    samples = sorted(
        [sample for sample in detail.get("samples", []) if isinstance(sample, dict) and sample.get("startTimeInSeconds")],
        key=lambda sample: sample.get("startTimeInSeconds"),
    )
    if len(samples) < 2:
        return []
    first_start = samples[0].get("startTimeInSeconds")
    rows: list[dict[str, Any]] = []
    previous: Optional[dict[str, Any]] = None
    for sample in samples:
        elapsed = _sample_elapsed_seconds(sample, first_start)
        if elapsed is None:
            continue
        hr = _number(sample.get("heartRate") or sample.get("heartRateInBeatsPerMinute"))
        distance_m = _first_number(sample, "totalDistanceInMeters", "distanceInMeters")
        speed_mps = _first_number(
            sample,
            "speedMetersPerSecond",
            "enhancedSpeedMetersPerSecond",
            "averageSpeedInMetersPerSecond",
        )
        if not speed_mps and previous and distance_m is not None and previous.get("distance_m") is not None:
            delta_t = elapsed - previous["elapsed_s"]
            delta_d = distance_m - previous["distance_m"]
            if delta_t > 0 and delta_d >= 0:
                speed_mps = delta_d / delta_t
        speed_kmh = speed_mps * 3.6 if speed_mps is not None else None
        pace_min_km = (1000 / speed_mps / 60) if speed_mps and speed_mps > 0 else None
        if sport == "SWIMMING" and speed_mps and speed_mps > 0:
            pace_min_km = (100 / speed_mps / 60)
        row = {
            "elapsed_s": float(elapsed),
            "hr": int(round(hr)) if hr is not None else None,
            "distance_m": distance_m,
            "speed_mps": speed_mps,
            "speed_kmh": speed_kmh,
            "pace_min_km": pace_min_km,
        }
        rows.append(row)
        previous = row
    return _smooth_sample_series(rows)


def _smooth_sample_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) < 5:
        return rows
    smoothed = []
    for index, row in enumerate(rows):
        window = rows[max(0, index - 2): min(len(rows), index + 3)]
        speed_values = [item["speed_mps"] for item in window if item.get("speed_mps") is not None]
        hr_values = [item["hr"] for item in window if item.get("hr") is not None]
        next_row = dict(row)
        if speed_values:
            speed_mps = sum(speed_values) / len(speed_values)
            next_row["speed_mps"] = speed_mps
            next_row["speed_kmh"] = speed_mps * 3.6
            next_row["pace_min_km"] = (1000 / speed_mps / 60) if speed_mps > 0 else None
        if hr_values:
            next_row["hr"] = int(round(sum(hr_values) / len(hr_values)))
        smoothed.append(next_row)
    return smoothed


def _sample_elapsed_seconds(sample: dict[str, Any], first_start: Optional[int]) -> Optional[float]:
    for key in ("timerDurationInSeconds", "movingDurationInSeconds", "clockDurationInSeconds"):
        value = _number(sample.get(key))
        if value is not None:
            return float(value)
    start = _number(sample.get("startTimeInSeconds"))
    if start is not None and first_start is not None:
        return float(start - first_start)
    return None


def _response_blocks(series: list[dict[str, Any]], detail: dict[str, Any]) -> list[list[dict[str, Any]]]:
    laps = sorted(
        [
            _number(lap.get("startTimeInSeconds"))
            for lap in detail.get("laps", [])
            if isinstance(lap, dict) and lap.get("startTimeInSeconds") is not None
        ]
    )
    first_abs = None
    raw_samples = sorted(
        [sample for sample in detail.get("samples", []) if isinstance(sample, dict) and sample.get("startTimeInSeconds")],
        key=lambda sample: sample.get("startTimeInSeconds"),
    )
    if raw_samples:
        first_abs = _number(raw_samples[0].get("startTimeInSeconds"))
    if first_abs is not None and len(laps) >= 2:
        boundaries = [float(lap - first_abs) for lap in laps if lap >= first_abs]
        boundaries = sorted(set([0.0, *boundaries, series[-1]["elapsed_s"] + 1]))
        blocks = []
        for start, end in zip(boundaries, boundaries[1:]):
            block = [item for item in series if start <= item["elapsed_s"] < end]
            if len(block) >= 2:
                blocks.append(block)
        if len(blocks) >= 2:
            return blocks

    # Fallback: infer coarse blocks from speed shifts. This is deliberately conservative;
    # it avoids pretending we know exact workout steps when Garmin laps are missing.
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_speed: Optional[float] = None
    for item in series:
        speed = item.get("speed_mps")
        if not current:
            current = [item]
            current_speed = speed
            continue
        duration = item["elapsed_s"] - current[0]["elapsed_s"]
        speed_changed = (
            speed is not None
            and current_speed is not None
            and duration >= 75
            and abs(speed - current_speed) / max(current_speed, 0.2) >= 0.22
        )
        long_block = duration >= 5 * 60
        if speed_changed or long_block:
            if len(current) >= 2:
                blocks.append(current)
            current = [item]
            current_speed = speed
        else:
            current.append(item)
            speeds = [row["speed_mps"] for row in current if row.get("speed_mps") is not None]
            if speeds:
                current_speed = sum(speeds) / len(speeds)
    if len(current) >= 2:
        blocks.append(current)
    return blocks


def _block_response_stats(
    blocks: list[list[dict[str, Any]]],
    series: list[dict[str, Any]],
    sport: str,
) -> list[dict[str, Any]]:
    speed_values = [item["speed_mps"] for item in series if item.get("speed_mps") is not None]
    median_speed = _median(speed_values) or 0
    stats: list[dict[str, Any]] = []
    previous_speed: Optional[float] = None
    for index, block in enumerate(blocks):
        if len(block) < 2:
            continue
        start_s = block[0]["elapsed_s"]
        end_s = block[-1]["elapsed_s"]
        duration = max(0.0, end_s - start_s)
        if duration < 30:
            continue
        hr_values = [item["hr"] for item in block if item.get("hr") is not None]
        speed_block = [item["speed_mps"] for item in block if item.get("speed_mps") is not None]
        if not hr_values or not speed_block:
            continue
        avg_speed = sum(speed_block) / len(speed_block)
        start_hr = _median([item["hr"] for item in block[:max(2, min(5, len(block)))] if item.get("hr") is not None])
        end_hr = _median([item["hr"] for item in block[-max(2, min(5, len(block))):] if item.get("hr") is not None])
        first_half = [item["hr"] for item in block[: max(1, len(block) // 2)] if item.get("hr") is not None]
        second_half = [item["hr"] for item in block[max(1, len(block) // 2):] if item.get("hr") is not None]
        rise = (end_hr - start_hr) if start_hr is not None and end_hr is not None else None
        rise_per_min = (rise / (duration / 60)) if rise is not None and rise > 0 and duration > 0 else None
        tempo_change = None
        lag = None
        if previous_speed is not None and previous_speed > 0:
            tempo_change = ((avg_speed - previous_speed) / previous_speed) * 100
            if tempo_change >= 8 and rise is not None and rise >= 4 and start_hr is not None:
                threshold = start_hr + max(4, rise * 0.5)
                reached = next((item for item in block if item.get("hr") is not None and item["hr"] >= threshold), None)
                if reached:
                    lag = max(0, round(reached["elapsed_s"] - start_s))
        next_60 = [
            item for item in series
            if end_s < item["elapsed_s"] <= end_s + 60 and item.get("hr") is not None
        ]
        recovery_drop = None
        next_speeds = [item["speed_mps"] for item in next_60 if item.get("speed_mps") is not None]
        next_is_easier = bool(next_speeds) and (sum(next_speeds) / len(next_speeds)) <= avg_speed * 0.9
        if next_60 and end_hr is not None and next_is_easier:
            recovery_drop = round(end_hr - next_60[-1]["hr"], 1)
        drift = None
        if duration >= 6 * 60 and first_half and second_half:
            drift = round((sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half)), 1)
        kind = "work" if avg_speed >= median_speed * 1.07 else "recovery" if avg_speed <= median_speed * 0.88 else "steady"
        stats.append({
            "label": f"Blok {len(stats) + 1}",
            "start_s": start_s,
            "end_s": end_s,
            "duration_seconds": duration,
            "avg_hr": round(sum(hr_values) / len(hr_values), 1),
            "start_hr": round(start_hr, 1) if start_hr is not None else None,
            "end_hr": round(end_hr, 1) if end_hr is not None else None,
            "peak_hr": max(hr_values),
            "rise_bpm": round(rise, 1) if rise is not None else None,
            "rise_bpm_per_min": round(rise_per_min, 1) if rise_per_min is not None else None,
            "lag_seconds": lag,
            "recovery_drop_60s": recovery_drop,
            "drift_bpm": drift,
            "tempo_change_pct": round(tempo_change, 1) if tempo_change is not None else None,
            "speed_kmh": round(avg_speed * 3.6, 1),
            "pace_min_km": round((1000 / avg_speed / 60), 2) if avg_speed > 0 and sport != "SWIMMING" else (
                round((100 / avg_speed / 60), 2) if avg_speed > 0 and sport == "SWIMMING" else None
            ),
            "kind": kind,
        })
        previous_speed = avg_speed
    return stats


def _response_findings(blocks: list[dict[str, Any]], pace_sport: bool) -> list[str]:
    findings = []
    rising = [block for block in blocks if block.get("rise_bpm_per_min") is not None]
    lagged = [block for block in blocks if block.get("lag_seconds") is not None]
    recovery = [block for block in blocks if block.get("recovery_drop_60s") is not None]
    drift = [block for block in blocks if block.get("drift_bpm") is not None]
    if rising:
        fastest = max(rising, key=lambda item: item["rise_bpm_per_min"])
        target = _format_response_metric(fastest, pace_sport)
        findings.append(
            f"{fastest['label']} heeft de snelste HR-stijging: {fastest['rise_bpm_per_min']} bpm/min bij {target}."
        )
    if lagged:
        avg_lag = _avg([block["lag_seconds"] for block in lagged])
        findings.append(
            f"Na duidelijke tempoverhogingen duurt het gemiddeld ongeveer {avg_lag} sec voor je HR half mee is."
        )
    if recovery:
        best = max(recovery, key=lambda item: item["recovery_drop_60s"])
        worst = min(recovery, key=lambda item: item["recovery_drop_60s"])
        findings.append(
            f"Beste 60s-HR-daling na een blok: {best['recovery_drop_60s']} bpm; traagste: {worst['recovery_drop_60s']} bpm."
        )
    if drift:
        max_drift = max(drift, key=lambda item: item["drift_bpm"])
        if max_drift["drift_bpm"] > 5:
            findings.append(
                f"{max_drift['label']} toont cardiac drift: +{max_drift['drift_bpm']} bpm in de tweede helft."
            )
    if not findings:
        findings.append("Er zijn samples gevonden, maar weinig duidelijke tempo/HR-wissels; beschouw dit als verkennend.")
    return findings


def _response_table_row(block: dict[str, Any], pace_sport: bool) -> list[Any]:
    hr_text = "-"
    if block.get("start_hr") is not None and block.get("end_hr") is not None:
        hr_text = f"{block['start_hr']:.0f}->{block['end_hr']:.0f} ({block.get('peak_hr', '-')} max)"
    rise = f"{block['rise_bpm_per_min']} bpm/min" if block.get("rise_bpm_per_min") is not None else "-"
    lag = f"{block['lag_seconds']}s" if block.get("lag_seconds") is not None else "-"
    recovery = f"{block['recovery_drop_60s']} bpm" if block.get("recovery_drop_60s") is not None else "-"
    return [
        block.get("label"),
        _format_duration(int(block.get("duration_seconds") or 0)),
        _format_response_metric(block, pace_sport),
        hr_text,
        rise,
        lag,
        recovery,
    ]


def _format_response_metric(block: dict[str, Any], pace_sport: bool) -> str:
    if pace_sport:
        return _format_pace(block.get("pace_min_km"))
    speed = block.get("speed_kmh")
    return f"{speed:.1f} km/u" if isinstance(speed, (int, float)) else "-"


def _thin_series(series: list[dict[str, Any]], max_points: int = 120) -> list[dict[str, Any]]:
    if len(series) <= max_points:
        return series
    step = max(1, math.ceil(len(series) / max_points))
    thinned = series[::step]
    if thinned[-1] is not series[-1]:
        thinned.append(series[-1])
    return thinned


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_number(source: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in source:
            value = _number(source.get(key))
            if value is not None:
                return value
    return None


def _median(values: list[float]) -> Optional[float]:
    clean = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2


def _group_rows(rows: list[dict[str, Any]], bucket: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    activity_sets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if not row.get("start_time"):
            continue
        if bucket == "day":
            key = row["start_time"].date().isoformat()
        else:
            week_start = row["start_time"].date() - timedelta(days=row["start_time"].weekday())
            key = week_start.isoformat()
        item = grouped.setdefault(key, {"sessions": 0, "distance_km": 0, "duration_hours": 0, "load": 0})
        activity_sets[key].add(str(row.get("activity_key") or row.get("id")))
        item["distance_km"] += row["distance_km"]
        item["duration_hours"] += row["duration_hours"]
        item["load"] += row["load"]
    for key, activity_keys in activity_sets.items():
        grouped[key]["sessions"] = len(activity_keys)
    return dict(sorted(grouped.items()))


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hrs = [row["avg_hr"] for row in rows if row.get("avg_hr")]
    session_count = len({str(row.get("activity_key") or row.get("id")) for row in rows})
    return {
        "sessions": session_count,
        "points": len(rows),
        "distance_km": sum(row["distance_km"] for row in rows),
        "duration_hours": sum(row["duration_hours"] for row in rows),
        "load": sum(row["load"] for row in rows),
        "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
    }


def _metric_tiles(totals: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = [
        {"label": "Sessies", "value": totals["sessions"]},
        {"label": "Afstand", "value": round(totals["distance_km"], 1), "unit": "km"},
        {"label": "Duur", "value": round(totals["duration_hours"], 1), "unit": "u"},
        {"label": "Load", "value": round(totals["load"], 1)},
    ]
    if totals.get("points", totals["sessions"]) > totals["sessions"]:
        metrics[-1] = {"label": "Punten", "value": totals["points"]}
    return metrics


def _coverage(
    rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    request: dict[str, Any],
    compare_rows: Optional[list[dict[str, Any]]] = None,
    detail_stats: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    hr_rows = [row for row in current_rows if row.get("avg_hr")]
    distance_rows = [row for row in current_rows if row.get("distance_km", 0) > 0]
    start = _parse_date(request["start_date"])
    end = _parse_date(request["end_date"])
    days = ((end - start).days + 1) if start and end else None
    session_count = len({str(row.get("activity_key") or row.get("id")) for row in current_rows})
    compare_session_count = len({str(row.get("activity_key") or row.get("id")) for row in compare_rows or []})
    detail_stats = detail_stats or {}
    return {
        "sessions": session_count,
        "points": len(current_rows),
        "query_sessions": len(rows),
        "compare_sessions": compare_session_count,
        "days": days,
        "hr_coverage": round(len(hr_rows) / len(current_rows), 2) if current_rows else 0,
        "distance_coverage": round(len(distance_rows) / len(current_rows), 2) if current_rows else 0,
        "sport": request.get("sport"),
        "requested_data_source": detail_stats.get("requested_data_source") or request.get("data_source") or "auto",
        "effective_data_source": detail_stats.get("effective_data_source") or "summary",
        "detail_activities": detail_stats.get("detail_activities", 0),
        "detail_segments": detail_stats.get("detail_segments", 0),
        "fallback_summary_activities": detail_stats.get("fallback_summary_activities", 0),
    }


def _confidence(coverage: dict[str, Any], intent: str) -> dict[str, Any]:
    sessions = coverage.get("sessions", 0)
    hr_coverage = coverage.get("hr_coverage", 0)
    level = "low"
    if intent == "hr_response_kinetics":
        sample_points = coverage.get("sample_points", 0)
        blocks = coverage.get("blocks", 0)
        if sample_points >= 180 and blocks >= 4 and hr_coverage >= 0.75:
            level = "high"
        elif sample_points >= 60 and blocks >= 3 and hr_coverage >= 0.55:
            level = "medium"
    elif sessions >= 18 and (intent not in {"pace_hr_correlation"} or hr_coverage >= 0.7):
        level = "high"
    elif sessions >= 6 and (intent not in {"pace_hr_correlation"} or hr_coverage >= 0.45):
        level = "medium"
    notes = []
    if sessions < 6:
        notes.append("Weinig sessies in deze periode; interpretatie is voorzichtig.")
    if intent == "pace_hr_correlation" and hr_coverage < 0.7:
        notes.append("Niet elke sessie heeft hartslagdata, dus correlatie is indicatief.")
    if intent == "hr_response_kinetics" and coverage.get("sample_points", 0) < 60:
        notes.append("Te weinig ActivityDetails-samples om HR-respons stevig te beoordelen.")
    if coverage.get("distance_coverage", 0) < 0.7:
        notes.append("Afstandsdata ontbreken bij een deel van de sessies.")
    return {
        "level": level,
        "label": {"low": "voorzichtig", "medium": "redelijk", "high": "sterk"}[level],
        "notes": notes,
    }


def _follow_up_suggestions(intent: str, request: dict[str, Any]) -> list[str]:
    sport_text = " bij hardlopen" if request.get("sport") == "RUNNING" else ""
    base = {
        "activity_trend": [f"Vergelijk dit met de vorige 30 dagen{sport_text}", "Toon sportverdeling", "Welke sessie was het zwaarst?"],
        "compare_periods": ["Waarom is dit veranderd?", "Toon dit per week", "Welke sport verklaart het verschil?"],
        "sport_breakdown": ["Toon alleen hardlopen", "Vergelijk lopen met fietsen", "Welke sport levert meeste load?"],
        "pace_hr_correlation": ["Toon alleen de laatste 90 dagen", "Welke sessies waren efficiënter?", "Vergelijk tempo met vorige maand"],
        "hr_response_kinetics": ["Welke blokken hadden traag HR-herstel?", "Toon dezelfde analyse met activityDetails", "Vergelijk dit met wandelen"],
        "personal_records": ["Toon top 5 zwaarste sessies", "Welke records bij lopen?", "Vergelijk mijn beste weken"],
        "workout_pattern_analysis": ["Welke workouts doe ik te vaak?", "Maak voorstel volgens dit patroon", "Vergelijk harde sessies per week"],
    }
    return base.get(intent, base["activity_trend"])


def _activity_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: row["start_time"], reverse=True)
    return {
        "columns": ["Datum", "Sport", "Activiteit", "Km", "Duur", "HR"],
        "rows": [
            [
                row["date"],
                _sport_label(row["sport"]),
                row["name"],
                round(row["distance_km"], 1),
                _format_duration(row["duration_seconds"]),
                row["avg_hr"] or "-",
            ]
            for row in ordered
        ],
    }


def _sport_label(sport: Optional[str]) -> str:
    return SPORT_LABELS.get(str(sport or "OTHER").upper(), str(sport or "Overig"))


def _data_source_label(source: Optional[str]) -> str:
    return {
        "summary": "summary",
        "activityDetails": "activityDetails",
        "mixed": "activityDetails + summary fallback",
        "auto": "auto",
        "details": "activityDetails",
    }.get(str(source or "summary"), str(source or "summary"))


def _format_duration(seconds: int) -> str:
    minutes = int(round((seconds or 0) / 60))
    hours, mins = divmod(minutes, 60)
    return f"{hours}u{mins:02d}" if hours else f"{mins}m"


def _format_pace(value: Optional[float]) -> str:
    if not value:
        return "-"
    minutes = int(value)
    seconds = int(round((value - minutes) * 60))
    return f"{minutes}:{seconds:02d}/km"


def _pct_delta(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _format_delta(value: Optional[float]) -> str:
    if value is None:
        return "n.v.t."
    return f"{value:+.1f}%"


def _delta_word(value: Optional[float]) -> str:
    if value is None:
        return "niet goed vergelijkbaar"
    if value > 5:
        return "hoger"
    if value < -5:
        return "lager"
    return "ongeveer gelijk"


def _avg(values: list[float]) -> Optional[float]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return round(sum(clean) / len(clean), 1) if clean else None


def _correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) < 4 or len(xs) != len(ys):
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if not var_x or not var_y:
        return None
    return cov / math.sqrt(var_x * var_y)
