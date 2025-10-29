from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from app.tools.garmin_tools import get_health_data, get_user_info
from app.tools.workout_tools import create_fit_file, list_available_workouts
from app.tools.date_tools import get_current_date as get_current_date_tool
from app.tools.profiling_tools import analyze_and_summarize_user_activities
from app.tools.user_tools import delete_user_data
from app.tools.recovery_tools import assess_recovery_status
from app.tools.workout_recommendation import (
    get_workout_recommendations,
    save_workout_preferences,
    get_workout_history_summary
)
from app.tools.garmin_workout_upload import (
    upload_workout_to_garmin,
    check_garmin_workout_permissions
)
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Pydantic models for tool arguments
class GetHealthDataArgs(BaseModel):
    data_types: List[str] = Field(
        description="List of data types to fetch. Options: 'dailies', 'sleeps', 'stress', 'activities', 'epochs', 'hrv', or 'all' for everything."
    )
    start_date: str = Field(description="Start date in ISO format (YYYY-MM-DD).")
    end_date: Optional[str] = Field(default=None, description="Optional end date. If not provided, uses start_date + days.")
    days: Optional[int] = Field(default=None, description="Optional number of days to fetch. Defaults to 1 if end_date not provided.")

class CreateFitFileArgs(BaseModel):
    workout_steps: Optional[List[Dict]] = Field(default=None, description="A list of workout steps for fully custom workouts. Usually not needed.")
    workout_type: Optional[str] = Field(default=None, description="Type of workout: HERSTEL, DUUR, THRESHOLD, VO2MAX, or SPRINT. Required for dynamic generation.")
    duration_minutes: Optional[int] = Field(default=None, description="Desired duration in minutes (e.g., 45, 60, 75). Any duration within reasonable range is possible.")
    sport: Optional[str] = Field(default=None, description="Optional sport type: CARDIO_TRAINING, RUNNING, CYCLING, LAP_SWIMMING. Leave empty for auto-detect (HERSTEL→CARDIO_TRAINING, others→CYCLING) or detect from user keywords.")
    recovery_score: Optional[float] = Field(default=None, description="Recovery score before workout (0-6)")

class SaveWorkoutPreferencesArgs(BaseModel):
    preferred_types: Optional[List[str]] = Field(default=None, description="List of preferred workout types: ['HERSTEL', 'DUUR', 'THRESHOLD', 'VO2MAX', 'SPRINT']")
    preferred_duration: Optional[int] = Field(default=None, description="Preferred workout duration in minutes")
    max_intensity: Optional[int] = Field(default=None, description="Maximum intensity level (1-5)")
    weekly_goal: Optional[int] = Field(default=None, description="Target number of workouts per week")

class GetWorkoutHistoryArgs(BaseModel):
    days: int = Field(default=30, description="Number of days to look back (default: 30)")

class UploadWorkoutToGarminArgs(BaseModel):
    workout_type: str = Field(description="Type of workout to upload: HERSTEL, DUUR, THRESHOLD, VO2MAX, or SPRINT")
    duration_minutes: int = Field(description="Duration in minutes (e.g., 45, 60, 75)")
    sport: Optional[str] = Field(default=None, description="Optional Garmin sport type: CARDIO_TRAINING, RUNNING, CYCLING, LAP_SWIMMING, etc. Auto-detected if not specified (HERSTEL=CARDIO_TRAINING, others=CYCLING)")
    schedule_date: Optional[str] = Field(default=None, description="Optional date to schedule workout (YYYY-MM-DD format)")

def create_conversational_agent(user_id: int, current_date: str = None):
    """
    Creates a conversational agent for a user.

    Args:
        user_id: The Telegram user ID
        current_date: Current date in ISO format (YYYY-MM-DD). If None, will be fetched automatically.
    """
    if current_date is None:
        current_date = get_current_date_tool()

    # Helper functions to pass user_id to the tools
    def get_health_data_for_user(data_types: List[str], start_date: str, end_date: Optional[str] = None, days: Optional[int] = None) -> str:
        return get_health_data(user_id=user_id, data_types=data_types, start_date=start_date, end_date=end_date, days=days)

    def get_user_info_for_user() -> dict:
        return get_user_info(user_id=user_id)

    def analyze_activities_for_user() -> str:
        return analyze_and_summarize_user_activities(user_id=user_id)

    def delete_user_data_for_user() -> str:
        return delete_user_data(user_id=user_id)

    def assess_recovery_for_user() -> str:
        return assess_recovery_status(user_id=user_id)

    def create_fit_file_for_user(
        workout_steps: Optional[List[Dict]] = None,
        workout_type: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        sport: Optional[str] = None,
        recovery_score: Optional[float] = None
    ) -> str:
        return create_fit_file(
            user_id=user_id,
            workout_steps=workout_steps,
            workout_type=workout_type,
            duration_minutes=duration_minutes,
            sport=sport,
            recovery_score=recovery_score
        )

    def get_workout_recommendations_for_user() -> str:
        return get_workout_recommendations(user_id=user_id)

    def save_workout_preferences_for_user(
        preferred_types: Optional[List[str]] = None,
        preferred_duration: Optional[int] = None,
        max_intensity: Optional[int] = None,
        weekly_goal: Optional[int] = None
    ) -> str:
        return save_workout_preferences(
            user_id=user_id,
            preferred_types=preferred_types,
            preferred_duration=preferred_duration,
            max_intensity=max_intensity,
            weekly_goal=weekly_goal
        )

    def get_workout_history_for_user(days: int = 30) -> str:
        return get_workout_history_summary(user_id=user_id, days=days)

    def upload_workout_to_garmin_for_user(
        workout_type: str,
        duration_minutes: int,
        sport: Optional[str] = None,
        schedule_date: Optional[str] = None
    ) -> str:
        return upload_workout_to_garmin(
            user_id=user_id,
            workout_type=workout_type,
            duration_minutes=duration_minutes,
            sport=sport,
            schedule_date=schedule_date
        )

    def check_garmin_permissions_for_user() -> str:
        return check_garmin_workout_permissions(user_id=user_id)

    tools = [
        StructuredTool.from_function(
            name="get_current_date",
            func=get_current_date_tool,
            description="Returns the current date in ISO format (YYYY-MM-DD).",
        ),
        StructuredTool.from_function(
            name="get_health_data",
            func=get_health_data_for_user,
            description="""Fetch health and activity data from Garmin. This unified tool can fetch multiple data types at once.

            Data types available:
            - 'dailies': Daily summaries (steps, calories, distance, heart rate, floors, etc.)
            - 'sleeps': Sleep data (duration, sleep phases, sleep score)
            - 'stress': Stress levels and time in different stress states
            - 'activities': Workouts and exercises
            - 'epochs': 15-minute granular data
            - 'hrv': Heart rate variability
            - 'all': Fetch all available types

            Examples:
            - Get sleep and stress for one day: data_types=['sleeps', 'stress'], start_date='2025-01-15'
            - Get all data for a week: data_types=['all'], start_date='2025-01-10', days=7
            - Get activities for a range: data_types=['activities'], start_date='2025-01-01', end_date='2025-01-15'

            Returns a human-readable summary with all requested data.""",
            args_schema=GetHealthDataArgs,
        ),
        StructuredTool.from_function(
            name="get_user_info",
            func=get_user_info_for_user,
            description="Fetch user's full name from Garmin Connect.",
        ),
        StructuredTool.from_function(
            name="create_fit_file",
            func=create_fit_file_for_user,
            description="""Creëert een .fit workout bestand DYNAMISCH op basis van type, duur en sport.

            DYNAMISCHE GENERATIE:
            - Geef workout_type, duration_minutes en optioneel sport op
            - Workout wordt automatisch gegenereerd met optimale structuur

            WORKOUT TYPES:
            - HERSTEL: Zeer lage intensiteit voor actief herstel
            - DUUR: Lage intensiteit endurance training
            - THRESHOLD: Tempo training op drempel
            - VO2MAX: Intensieve intervallen
            - SPRINT: Maximale korte inspanningen

            SPORT PARAMETER (OPTIONEEL):
            - Laat LEEG voor auto-detect (HERSTEL→CARDIO_TRAINING, anderen→CYCLING)
            - Geef EXPLICIET mee als gebruiker specifieke sport noemt:
              * "wandelen", "wandeling" → sport="CARDIO_TRAINING"
              * "hardlopen", "rennen", "lopen" → sport="RUNNING"
              * "fietsen", "fietsrit" → sport="CYCLING"
              * "zwemmen" → sport="LAP_SWIMMING"

            VOORBEELDEN:
            - workout_type="HERSTEL", duration_minutes=45 → Auto CARDIO_TRAINING (wandelen)
            - workout_type="HERSTEL", duration_minutes=45, sport="RUNNING" → Hardlopen
            - workout_type="HERSTEL", duration_minutes=45, sport="CYCLING" → Fietsen
            - workout_type="DUUR", duration_minutes=60, sport="RUNNING" → Hardlopen
            - workout_type="THRESHOLD", duration_minutes=50 → Auto CYCLING (fietsen)

            BELANGRIJK: Roep ALTIJD assess_recovery_status AAN VOORDAT je een workout creëert!
            """,
            args_schema=CreateFitFileArgs,
        ),
        StructuredTool.from_function(
            name="list_available_workouts",
            func=list_available_workouts,
            description="""Toont informatie over de dynamische workout generator.

            Laat zien welke workout types beschikbaar zijn en hun kenmerken:
            - HERSTEL: Actief herstel, lage intensiteit
            - DUUR: Endurance training
            - THRESHOLD: Tempo training
            - VO2MAX: Intensieve intervallen
            - SPRINT: Maximale inspanningen

            Toont ook aanbevolen duren per type en voorbeelden van gebruik.
            """,
        ),
        StructuredTool.from_function(
            name="get_workout_recommendations",
            func=get_workout_recommendations_for_user,
            description="""Analyseert recovery status, workout history en preferences om een gepersonaliseerde workout aan te raden.

            Deze tool:
            - Bekijkt herstelstatus (slaap, stress)
            - Analyseert recente workout patronen
            - Houdt rekening met user preferences
            - Raadt optimale workout type en intensiteit aan

            Gebruik dit VOORDAT je een workout maakt om de beste keuze te adviseren.
            """,
        ),
        StructuredTool.from_function(
            name="save_workout_preferences",
            func=save_workout_preferences_for_user,
            description="""Slaat workout voorkeuren van de gebruiker op.

            Parameters:
            - preferred_types: Lijst van voorkeur types zoals ["HERSTEL", "DUUR", "THRESHOLD", "VO2MAX", "SPRINT"]
            - preferred_duration: Voorkeur duur in minuten (bijv. 60)
            - max_intensity: Maximale intensiteit 1-5 die gebruiker wil
            - weekly_goal: Aantal workouts per week als doel

            Deze preferences worden gebruikt bij workout aanbevelingen.
            """,
            args_schema=SaveWorkoutPreferencesArgs,
        ),
        StructuredTool.from_function(
            name="get_workout_history",
            func=get_workout_history_for_user,
            description="""Haalt workout geschiedenis op voor de gebruiker.

            Toont:
            - Totaal aantal workouts
            - Verdeling per type (HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
            - Recente workouts
            - Gemiddelde per week

            Gebruik days parameter om tijdsperiode te specificeren (default: 30 dagen).
            """,
            args_schema=GetWorkoutHistoryArgs,
        ),
        StructuredTool.from_function(
            name="analyze_and_summarize_user_activities",
            func=analyze_activities_for_user,
            description="Analyzes the user's activities and provides a summary of their profile.",
        ),
        StructuredTool.from_function(
            name="assess_recovery_status",
            func=assess_recovery_for_user,
            description="IMPORTANT: Use this tool BEFORE creating any workout. Checks yesterday's sleep and stress data to assess if the user is well-recovered. Returns a recovery score and training recommendations. Always call this before creating a .fit file.",
        ),
        StructuredTool.from_function(
            name="delete_user_data",
            func=delete_user_data_for_user,
            description="Deletes all data associated with the user.",
        ),
        StructuredTool.from_function(
            name="upload_workout_to_garmin",
            func=upload_workout_to_garmin_for_user,
            description="""Upload een dynamisch gegenereerde workout direct naar Garmin Connect.

            BELANGRIJK:
            - Vereist WORKOUT_IMPORT permissie (check eerst met check_garmin_workout_permissions)
            - Workout wordt dynamisch gegenereerd en geupload
            - Sync automatisch naar Garmin horloge
            - Geen handmatige download nodig
            - Sport type wordt AUTO-DETECT (HERSTEL=CARDIO_TRAINING/wandelen, anderen=CYCLING/fietsen)

            Parameters:
            - workout_type: TYPE van workout (HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
            - duration_minutes: DUUR in minuten
            - sport: OPTIONEEL - override auto-detect (CARDIO_TRAINING, RUNNING, CYCLING, LAP_SWIMMING, etc.)
            - schedule_date: Optioneel - plan workout op datum (YYYY-MM-DD)

            Voorbeelden:
            - workout_type="HERSTEL", duration_minutes=45 → Auto: CARDIO_TRAINING (wandelen)
            - workout_type="HERSTEL", duration_minutes=30, sport="RUNNING" → Hardlopen
            - workout_type="DUUR", duration_minutes=75 → Auto: CYCLING (fietsen)
            - workout_type="THRESHOLD", duration_minutes=50, sport="RUNNING" → Hardlopen

            Workflow:
            1. Check eerst WORKOUT_IMPORT permissie
            2. Genereer workout dynamisch
            3. Auto-detect sport type (tenzij opgegeven)
            4. Upload naar Garmin Connect
            5. Bevestig beschikbaarheid op horloge
            """,
            args_schema=UploadWorkoutToGarminArgs,
        ),
        StructuredTool.from_function(
            name="check_garmin_workout_permissions",
            func=check_garmin_permissions_for_user,
            description="""Check of gebruiker WORKOUT_IMPORT permissie heeft.

            Deze tool controleert welke Garmin Connect permissies de gebruiker heeft.
            Roep dit ALTIJD aan VOORDAT je upload_workout_to_garmin gebruikt.

            Als WORKOUT_IMPORT ontbreekt, instrueer gebruiker om:
            1. Naar Garmin Connect account settings te gaan
            2. Workout import permissie te geven
            3. Of opnieuw OAuth te doen met /garmin_oauth
            """,
        ),
    ]

    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", f"""Je bent een behulpzame AI sportcoach. Je helpt gebruikers met hun activiteiten, slaap, stress en het maken van trainingsplannen.

HUIDIGE DATUM: {current_date}
Het is nu {current_date}. Gebruik deze datum als referentie voor alle datum-gerelateerde vragen en data requests.

BELANGRIJKE TAALINSTELLINGEN:
- Antwoord ALTIJD in het Nederlands
- Gebruik Nederlands voor alle tekst, uitleg en data-presentatie
- Vertaal Engelse veldnamen naar Nederlands waar mogelijk (bijv. "Steps" → "Stappen")

OPMAAKREGELS:
- GEEN markdown formatting (geen vet, geen *cursief*, geen ### headers)
- GEEN emojis in je antwoorden
- Gebruik simpele, duidelijke tekstopmaak
- Gebruik HOOFDLETTERS voor sectietitels (bijv. "DAGELIJKSE SAMENVATTING" niet "### Dagelijkse Samenvatting")
- Gebruik inspringingen en regelafbrekingen voor duidelijkheid

BELANGRIJKE DATUM CONTEXT:
- De huidige datum kan worden opgehaald met de get_current_date tool
- Wanneer gebruikers datums noemen zonder jaar (bijv. "8 oktober", "October 8"), ga ALTIJD uit van het HUIDIGE jaar (2025)
- Gebruik get_current_date eerst om de huidige datum en jaar te bepalen
- Voor queries zoals "8 oktober" → gebruik "2025-10-08"
- Voor queries zoals "1 tot 13 oktober" → gebruik "2025-10-01" tot "2025-10-13"

Belangrijke richtlijnen:
- Alle tools retourneren vooraf opgemaakte, leesbare samenvattingen (geen ruwe JSON)
- De data die je ontvangt is al gefilterd en compact
- Je kunt deze data direct gebruiken in je antwoorden
- Gebruik de get_current_date tool wanneer gebruikers vragen om data "tot vandaag" of "deze week"

DYNAMISCHE WORKOUT GENERATOR:
Workouts worden DYNAMISCH gegenereerd op basis van TYPE en DUUR.
Geen vaste templates meer - elke duur is mogelijk!

Er zijn 5 workout types beschikbaar:
- HERSTEL (Recovery): Zeer lage intensiteit (Zone 1) - Voor actief herstel (wandelen, rustig fietsen)
- DUUR (Endurance): Lange, lage intensiteit (Zone 2) - Voor aerobe basis
- THRESHOLD: Tempo training op drempel (Zone 4) - Voor FTP verbetering
- VO2MAX: Korte intensieve intervallen (Zone 5) - Voor maximale zuurstofopname
- SPRINT: Zeer korte max inspanningen - Voor anaerobe power

KRITISCHE WORKFLOW VOOR TRAINING CREATIE:
1. Wanneer gebruiker vraagt om workout aanbeveling:
   - Roep get_workout_recommendations aan
   - Dit analyseert recovery, history en preferences automatisch
   - Toont TYPE en DUUR aanbeveling
   - Leg de aanbeveling uit aan de gebruiker

2. Wanneer gebruiker vraagt om specifieke workout te maken:
   - Roep EERST assess_recovery_status aan
   - Controleer of gevraagde intensiteit past bij herstel
   - Waarschuw als het te intensief is voor hun herstelstatus

3. Bij creëren van workout:
   - Gebruik create_fit_file met workout_type en duration_minutes
   - KRITISCH: Detecteer SPORT TYPE uit wat gebruiker vraagt:

     SPORT DETECTIE KEYWORDS:
     * "wandeling", "wandelen", "lopen" → GEEN sport parameter (laat leeg)
     * "fietsen", "fietsrit", "wielrennen", "cycling" → sport="CYCLING"
     * "hardlopen", "rennen", "running" → sport="RUNNING"
     * "zwemmen", "swimming", "baantjes" → sport="LAP_SWIMMING"
     * Niets specifiek genoemd → GEEN sport parameter (auto-detect)

   VOORBEELDEN:
   * "Maak een herstel wandeling van 45 min" → workout_type="HERSTEL", duration_minutes=45 (GEEN sport)
   * "Maak een herstel fietsrit van 45 min" → workout_type="HERSTEL", duration_minutes=45, sport="CYCLING"
   * "Geef me DUUR hardloop sessie van 60 min" → workout_type="DUUR", duration_minutes=60, sport="RUNNING"
   * "Ik wil zwemmen, 30 min DUUR" → workout_type="DUUR", duration_minutes=30, sport="LAP_SWIMMING"
   * "THRESHOLD workout 50 minuten" → workout_type="THRESHOLD", duration_minutes=50 (GEEN sport, auto CYCLING)

   - De workout wordt automatisch gegenereerd met optimale structuur
   - Geef altijd recovery_score mee als je die hebt

4. AUTOMATISCHE UPLOAD NAAR GARMIN CONNECT:
   - Check eerst WORKOUT_IMPORT permissie met check_garmin_workout_permissions
   - Als permissie aanwezig: upload workout automatisch naar Garmin Connect
   - Gebruik upload_workout_to_garmin met gekozen template
   - Workout synct automatisch naar gebruikers horloge
   - GEEN handmatige FIT file download meer nodig!

5. Na workout creatie/upload:
   - Bevestig dat workout op Garmin Connect staat
   - Leg uit dat het automatisch naar horloge synct
   - Workout wordt automatisch opgeslagen in history

HERSTEL RICHTLIJNEN:
- Herstelscore < 2: Alleen HERSTEL (wandelen, zeer rustig fietsen)
- Herstelscore 2-3: HERSTEL of DUUR mogelijk
- Herstelscore 3-4: DUUR of THRESHOLD mogelijk
- Herstelscore 4-5: DUUR, THRESHOLD of VO2MAX mogelijk
- Herstelscore >= 5: Alle types inclusief SPRINT mogelijk

LEREN VAN HISTORY:
- Het systeem leert van eerdere workouts
- Voorkomt te veel van hetzelfde type
- Past aan op basis van trainingsfrequentie
- Houdt rekening met user preferences

- Wees conversationeel, ondersteunend, en geef prioriteit aan veiligheid en herstel
- Moedig variatie aan in trainingstypes voor optimale ontwikkeling"""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm_with_tools = llm.bind_tools(tools)

    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                x["intermediate_steps"]
            ),
            "chat_history": lambda x: x["chat_history"],
        }
        | prompt
        | llm_with_tools
        | OpenAIToolsAgentOutputParser()
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)

    return agent_executor
