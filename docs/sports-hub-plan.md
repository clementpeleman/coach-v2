# Sports Hub en AI Coach - Plan

## Doel

De app wordt een webgebaseerde sports hub met een AI-coach voor meerdere gebruikers.
Telegram verdwijnt als primaire interface. Garmin wordt in de eerste versie de enige
databron.

De app moet:

- Garmin-data ophalen en analyseren.
- Hardloop- en fietsactiviteiten begrijpen.
- Wekelijks automatisch een statusanalyse maken.
- Korte, duidelijke inzichten geven met relevante gemiddelde waarden.
- Losse trainingen en weekschema's genereren.
- Doelen ondersteunen, maar niet verplicht maken.
- Trainingen eerst ter goedkeuring voorleggen.
- Goedgekeurde trainingen naar Garmin pushen.
- Een coach-chat in de webapp aanbieden.

## Bevestigde keuzes

| Onderwerp | Keuze |
| --- | --- |
| Productrichting | Sports hub met AI-coach |
| Gebruikers | Meerdere gebruikers |
| Databron MVP | Alleen Garmin |
| Frontend | Next.js |
| Analysefrequentie | Wekelijks automatisch |
| Doelen | Optioneel |
| Training upload | Push naar Garmin na goedkeuring |
| Interface | Webapp met dashboard, planner en chat |
| Telegram | Uitfaseren/vervangen |

## Huidige repo-context

De bestaande repo bevat al een aantal bruikbare onderdelen:

- FastAPI backend.
- PostgreSQL/TimescaleDB.
- Garmin OAuth/webhook-code.
- Garmin credentials/config via environment variables.
- Telegram bot als huidige chat-interface.
- LangChain coach-agent.
- Bestaande workout history/templates.

Belangrijke lacunes:

- Nog geen Next.js frontend.
- Nog geen zelfstandige webapp-UX.
- Veel code lijkt nog rond `telegram_user_id` te draaien.
- Nog geen sterk datamodel voor volledige trainingsplannen.
- Garmin-data wordt deels als JSON opgeslagen; voor analyse zijn genormaliseerde kolommen nodig.

## Kernarchitectuur

### Backend

De bestaande FastAPI backend blijft de centrale API-laag.

Nieuwe of aangepaste domeinen:

- Auth en gebruikers.
- Garmin connect/sync.
- Activiteiten.
- Analyse.
- Training planner.
- Garmin workout upload.
- Coach-chat.

Voorbeeld API-routes:

```text
/auth/garmin/start
/auth/garmin/callback
/users/me
/activities
/analysis/current
/analysis/weekly
/training-plans
/planned-sessions
/chat
```

### Frontend

Nieuwe Next.js frontend.

Belangrijke pagina's:

```text
/login
/dashboard
/activities
/analysis
/planner
/chat
/settings/garmin
```

### Database

PostgreSQL blijft de primaire database. TimescaleDB kan worden gebruikt voor tijdreeksdata
zoals hartslag, health metrics en sensorwaarden.

## Identity refactor

De app moet loskomen van Telegram als user identity.

### Nieuw user-model

```text
User
- id
- email optional
- name optional
- created_at
- updated_at
```

### Externe koppelingen

```text
UserConnection
- id
- user_id
- provider: garmin
- external_id
- access_token encrypted
- refresh_token encrypted
- scopes
- status
- connected_at
- updated_at
```

Voor de MVP is Garmin de enige provider. Telegram hoeft niet als nieuw kanaal ondersteund
te worden, behalve eventueel tijdelijk voor legacy gebruikers.

## Garmin integratie

Garmin wordt de eerste en enige databron.

### Te ondersteunen data

Voor hardlopen en fietsen:

```text
Activity
- id
- user_id
- provider: garmin
- provider_activity_id / summary_id
- sport: running / cycling
- start_time
- duration_seconds
- distance_meters
- avg_heart_rate
- max_heart_rate
- avg_speed
- avg_pace
- elevation_gain
- avg_cadence
- avg_power
- max_power
- calories
- training_effect
- aerobic_effect
- anaerobic_effect
- raw_payload
- created_at
```

Voor health/status data:

```text
DailyHealthMetric
- id
- user_id
- date
- resting_heart_rate
- max_heart_rate_estimate
- hrv_avg
- sleep_duration_seconds
- sleep_score
- stress_score
- body_battery_min
- body_battery_max
- steps
- raw_payload
```

Voor hartslagzones:

```text
HeartRateZoneProfile
- id
- user_id
- sport optional
- max_heart_rate
- resting_heart_rate
- zone_1_min
- zone_1_max
- zone_2_min
- zone_2_max
- zone_3_min
- zone_3_max
- zone_4_min
- zone_4_max
- zone_5_min
- zone_5_max
- source: garmin / estimated / manual
- valid_from
```

### Historische sync

De app moet niet alleen nieuwe webhooks verwerken, maar ook historische Garmin-data ophalen.

Aanpak:

1. Na Garmin connect een eerste backfill starten.
2. Activiteiten ophalen voor een configureerbare periode, bijvoorbeeld 6 tot 24 maanden.
3. Alleen hardlopen en fietsen in de MVP normaliseren.
4. Raw payload bewaren voor toekomstige uitbreiding.
5. Sync-status bijhouden per gebruiker.

Voorbeeld model:

```text
GarminSyncState
- id
- user_id
- last_activity_sync_at
- last_health_sync_at
- backfill_started_at
- backfill_completed_at
- status
- error_message
```

## Analyse-engine

De analyse-engine maakt een beeld van de huidige status van de gebruiker.

### Analyseperiodes

Gebruik standaard:

- Laatste 7 dagen.
- Laatste 28 dagen.
- Laatste 42 dagen.
- Historisch gemiddelde waar beschikbaar.

### 1. Activiteitstype-analyse

Voor hardlopen en fietsen:

- Aantal sessies per week.
- Totale duur per week.
- Totale afstand per week.
- Verdeling hardlopen/fietsen.
- Rustige vs intensieve sessies.
- Langste sessie.
- Consistentie.
- Missende weken.
- Plotselinge pieken in volume of intensiteit.

Voorbeeldinzicht:

```text
Je trainde deze week 4 keer: 2 runs en 2 rides. Je totale volume was 5u20,
ongeveer 12% hoger dan je 4-weeks gemiddelde.
```

### 2. Hartslaganalyse

Metrics:

- Gemiddelde hartslag per sport.
- Max hartslag per sport.
- Tijd in hartslagzones.
- Rusthartslagtrend.
- Hartslag bij vergelijkbare pace/snelheid.
- Afwijkend hoge hartslag bij rustige sessies.
- Intensiteitsverdeling over zone 1-5.

Voorbeeldinzicht:

```text
Je gemiddelde hartslag bij rustige runs ligt deze week 6 bpm hoger dan je recente
gemiddelde. Dat kan wijzen op vermoeidheid, warmte, stress of onvoldoende herstel.
```

### 3. Training load

Start simpel en maak dit later geavanceerder.

Metrics:

```text
acute_load: laatste 7 dagen
chronic_load: laatste 28 of 42 dagen
load_ratio: acute_load / chronic_load
intensity_distribution
monotony
strain
```

Voorbeeldinzicht:

```text
Je acute belasting ligt 1.28x boven je 4-weeks gemiddelde. Dat is een stevige
maar nog acceptabele stijging zolang hersteldata normaal blijft.
```

### 4. Performance trends

Voor hardlopen:

- Pace bij lage hartslag.
- Tempo over vergelijkbare afstanden.
- Lange duurloop-progressie.
- Intervalprestaties.
- Geschatte conditietrend.

Voor fietsen:

- Snelheid bij vergelijkbare hartslag.
- Duurvermogen.
- Hoogtemeterbelasting.
- Power-analyse als Garmin power beschikbaar is.

### 5. Herstel en readiness

Maak een wekelijkse score op basis van:

- Rusthartslag.
- HRV.
- Slaap.
- Recente intensiteit.
- Training load.
- Dagen sinds laatste zware training.

Voorbeeld output:

```text
readiness_score: 0-100
fatigue: low / medium / high
injury_risk: low / medium / high
recommended_focus: recovery / endurance / intensity / build
```

## Wekelijkse statusanalyse

De app moet automatisch wekelijks een rapport maken, bijvoorbeeld elke maandag ochtend.

### Model

```text
WeeklyAnalysis
- id
- user_id
- week_start
- week_end
- metrics_json
- ai_summary
- recommendations_json
- created_at
```

### Rapportstructuur

Elke analyse bevat:

1. Korte samenvatting.
2. Belangrijkste cijfers.
3. Wat gaat goed.
4. Risico's of aandachtspunten.
5. Advies voor komende week.
6. Voorgestelde trainingen.

Voorbeeld:

```text
Deze week deed je 4 trainingen: 2 runs en 2 rides. Je totale volume was 5u20,
ongeveer 12% boven je 4-weeks gemiddelde. Je rusthartslag bleef stabiel, maar je
hartslag bij rustige runs lag iets hoger dan normaal. Advies: houd komende week
maximaal 1 zware sessie en bouw vooral rustig duurvolume.
```

## Training planner

De app moet losse trainingen en weekschema's kunnen voorstellen.

### Gebruikersinstellingen

Doelen zijn optioneel. Zonder doel kiest de coach voor gebalanceerde progressie.

Mogelijke instellingen:

```text
goal optional
available_days
max_time_per_day
preferred_sports
sessions_per_week
constraints optional
```

### Training plan model

```text
TrainingPlan
- id
- user_id
- name
- goal optional
- start_date
- end_date
- status: draft / active / completed / archived
- created_at
```

### Planned session model

```text
PlannedSession
- id
- user_id
- training_plan_id optional
- sport: running / cycling
- scheduled_date
- duration_seconds
- intensity: recovery / easy / moderate / hard
- target_hr_zone
- workout_structure_json
- explanation
- status: proposed / approved / rejected / pushed / completed / skipped
- garmin_status: not_pushed / pushed / failed
- garmin_workout_id optional
- created_at
- updated_at
```

## Training generatie

### Losse training

Voorbeeldvraag:

```text
Maak een training voor morgen.
```

De coach gebruikt:

- Recente belasting.
- Laatste trainingen.
- Herstelstatus.
- Beschikbare tijd.
- Voorkeur sport.
- Intensiteitsbalans.

Voorbeeldantwoord:

```text
Rustige duurloop
Duur: 45 min
Zone: 2

Structuur:
- 10 min inlopen
- 30 min zone 2
- 5 min uitlopen

Waarom:
Je had deze week al een intensieve fietstraining. Deze sessie bouwt aerobe basis
zonder veel extra belasting.
```

### Weekschema

Voorbeeld:

```text
Maandag: rust
Dinsdag: rustige run 45 min
Woensdag: fiets herstelrit 60 min
Vrijdag: interval run 6x3 min
Zondag: lange duurtraining fiets 90 min
```

Alle gegenereerde trainingen starten met status `proposed`.

## Goedkeuren en pushen naar Garmin

Flow:

1. De AI genereert een training of schema.
2. De gebruiker bekijkt het voorstel in de planner.
3. De gebruiker kiest goedkeuren, aanpassen of afwijzen.
4. Na goedkeuring wordt de training opgeslagen als `approved`.
5. De backend zet de training om naar Garmin workout format.
6. De backend pusht de training naar Garmin.
7. De status wordt `pushed`, of `failed` met foutmelding.

Advies: push automatisch direct na goedkeuring, maar toon duidelijk de Garmin-status
en eventuele foutmelding.

## Coach-chat in Next.js

De chat komt in de webapp en gebruikt de bestaande coach-intelligentie waar mogelijk.

### Flow

```text
Web chat message
-> backend /chat
-> user context ophalen
-> recente activiteiten en analyses ophalen
-> coach-agent
-> antwoord terug naar frontend
```

### Voorbeeldvragen

- Hoe sta ik ervoor deze week?
- Wat moet ik morgen trainen?
- Maak een schema voor volgende week.
- Waarom was mijn hartslag zo hoog?
- Ben ik te hard aan het opbouwen?

Antwoorden moeten kort, concreet en onderbouwd zijn met cijfers.

Voorbeeld:

```text
Je volume ligt deze week 18% hoger dan je 4-weeks gemiddelde. Omdat je rusthartslag
stabiel is, lijkt dat voorlopig acceptabel. Ik zou morgen wel een rustige zone
2-training doen in plaats van interval.
```

## Telegram uitfaseren

Telegram moet niet de kern van de app blijven.

Aanpak:

1. Nieuwe webapp naast Telegram bouwen.
2. Coach-agent loskoppelen van Telegram-specifieke formatting.
3. `telegram_user_id` vervangen door interne `user_id`.
4. Telegram-bot tijdelijk als legacy laten bestaan als dat nodig is.
5. Telegram-bot verwijderen of uitschakelen zodra webapp volledig werkt.

Gewenste structuur:

```text
coach_core/
  agent.py
  prompts.py
  tools.py

interfaces/
  web_chat.py
  telegram_bot.py  # tijdelijk legacy
```

## MVP-volgorde

### MVP 1 - Next.js dashboard en Garmin koppeling

Doel: eerste bruikbare sports hub.

Scope:

- Interne user identity.
- Garmin OAuth zonder Telegram-afhankelijkheid.
- Next.js basisapp.
- Garmin connect-knop.
- Activiteitenlijst.
- Dashboard met basisstatistieken.
- Recente hardloop- en fietsactiviteiten.

### MVP 2 - Historische Garmin sync en analyse

Scope:

- Historische backfill.
- Genormaliseerde activity data.
- Health metrics waar beschikbaar.
- Weekly analysis model.
- Eerste automatische weekrapporten.

### MVP 3 - Coach-chat

Scope:

- Chatvenster in Next.js.
- Backend `/chat` endpoint.
- Coach-antwoorden op basis van Garmin-data.
- Statusvragen en trainingsadvies.

### MVP 4 - Training planner

Scope:

- Losse training genereren.
- Weekschema genereren.
- Beschikbare dagen/tijd instellen.
- Statussen: proposed, approved, rejected.
- Planner UI.

### MVP 5 - Garmin workout push

Scope:

- Goedgekeurde trainingen naar Garmin pushen.
- Garmin workout format mapping.
- Uploadstatus tonen.
- Fouten netjes afhandelen.

## Concrete eerste technische stappen

1. Voeg een interne user identity toe.
2. Maak Garmin OAuth los van `telegram_user_id`.
3. Scaffold een Next.js frontend.
4. Maak een dashboard met Garmin connect-knop.
5. Toon eerste Garmin activiteiten in de webapp.
6. Normaliseer hardloop- en fietsdata in aparte kolommen.
7. Bouw daarna de weekly analysis service.

## Open technische aandachtspunten

- Bepalen hoeveel historische Garmin-data initieel wordt opgehaald.
- Controleren welke Garmin endpoints beschikbaar zijn met de huidige scopes.
- Beslissen of auth in de webapp start met simpele sessies, magic links of Garmin-only login.
- Bepalen waar scheduled jobs draaien: Celery, cron, APScheduler of externe scheduler.
- Testdekking toevoegen voor OAuth callback, token refresh, sync, analyse en workout push.
