# Project Specificatie: Agentische AI Sportcoach

Dit document dient als een directe technische specificatie voor de ontwikkeling van een schaalbaar en intelligent sportcoachingssysteem.

---

## 1. Fundamentele Concepten en Systeemarchitectuur

### 1.1. Systeemdefinitie

Het te bouwen systeem is een agentisch AI-systeem. Het is een doelgericht systeem dat autonoom kan plannen, acties in meerdere stappen kan uitvoeren en leert van gebruikersinteracties. De AI fungeert als een "junior partner" die vooruitdenkt en trainingsplannen dynamisch aanpast op basis van nieuwe data.

### 1.2. Architectonisch Overzicht

De architectuur is modulair met een duidelijke scheiding van verantwoordelijkheden.

- Gebruikersinterfacelaag: Handelt de interactie met de gebruiker af via externe berichtendiensten.
- Backend Service-laag: De kern van de applicatie, gebouwd met FastAPI (Python), die API-endpoints en asynchrone taken beheert.
- AI-Kernlaag: De intelligentie van het systeem, waarvoor LangGraph wordt ingezet voor complexe redenering en de orkestratie van tools.
- Datalagen: De persistentielaag, bestaande uit een PostgreSQL database met de TimescaleDB-extensie.
- Externe Diensten: Integraties met de Garmin Connect API en een service voor het genereren van .FIT-bestanden.

### 1.3. Hoofdcomponenten

1.  Conversatie-interface: Beheert de communicatie met de gebruiker.
2.  AI-orkestratie-kern: Het brein dat redeneert en tools uitvoert.
3.  Gegevensopnamepijplijn: Service voor het ophalen van data van Garmin Connect.
4.  Database & Gegevensanalyse: Persistentielaag voor alle gebruikers- en sensordata.
5.  Proactieve "Watcher": Mechanisme dat de agent activeert op basis van nieuwe data.

---

## 2. Gekozen Technologieën & Implementatie

### 2.1. AI-Kern: LangGraph

De AI-kern wordt geïmplementeerd met LangGraph. De stateful, grafiek-gebaseerde architectuur is essentieel voor de cyclische en complexe logica van een adaptieve coach (analyseer > plan > voer uit > pas aan). LangGraph beheert het geheugen en de staat van de agent, wat cruciaal is voor het onthouden van de gebruikerscontext.

### 2.2. Conversatie-interface: Gefaseerde Aanpak

De implementatie volgt een gefaseerde aanpak:

1.  Fase 1 (MVP): De interface wordt gebouwd voor Telegram. Dit platform is gratis en flexibel, ideaal voor snelle ontwikkeling en validatie. Berichten worden ontvangen via Webhooks.
2.  Fase 2 (Commerciële Lancering): Er wordt een interface voor WhatsApp ontwikkeld om een breder publiek te bereiken.

### 2.3. Gegevensbeheer

#### Integratie Garmin Wearable-gegevens

Voor de data-integratie met Garmin wordt de volgende strategie gehanteerd:

- MVP: De Python-bibliotheek `garminconnect` wordt gebruikt. Deze biedt programmatische toegang tot de Garmin Connect API via een veilige OAuth-authenticatiestroom.
- Commerciële fase: Er wordt overgestapt op het officiële Garmin Connect Developer Program voor maximale robuustheid en schaalbaarheid.

#### Databasearchitectuur: PostgreSQL + TimescaleDB

De databaselaag combineert PostgreSQL met de TimescaleDB-extensie.

- Gebruikersgegevens (profielen, etc.) worden opgeslagen in standaard PostgreSQL-tabellen.
- Tijdreeksgegevens van wearables (hartslag, snelheid, etc.) worden opgeslagen in TimescaleDB "hypertables" voor superieure prestaties bij invoer en query's.

Tabelstructuur:

| Tabelnaam               | Type                   | Voorbeeld Velden                                                  |
| :---------------------- | :--------------------- | :---------------------------------------------------------------- |
| `user_profile`          | PostgreSQL-tabel       | `user_id (PK)`, `phone_number`, `garmin_user_id`                  |
| `activities_hypertable` | TimescaleDB-hypertable | `activity_id (PK)`, `user_id (FK)`, `activity_type`, `start_time` |
| `sensor_data`           | TimescaleDB-hypertable | `timestamp`, `user_id (FK)`, `heart_rate`, `speed`, `power`       |

### 2.4. Proactieve "Watcher": Celery

De "watcher"-functionaliteit, die proactief nieuwe Garmin-activiteiten detecteert, wordt geïmplementeerd als een ontkoppelde achtergrondtaak met Celery. Celery is een gedistribueerde takenwachtrij die zorgt voor robuustheid, schaalbaarheid en fouttolerantie, zonder het hoofd-webproces (FastAPI) te blokkeren.

### 2.5. Generatie van Trainingsplannen: fit-tool

Voor het genereren en leveren van trainingsplannen wordt de Python-bibliotheek `fit-tool` gebruikt. Deze bibliotheek ondersteunt expliciet het schrijven van .FIT-bestanden. Het proces omvat het programmatisch opbouwen van het bestand met de `FitFileBuilder`-klasse en het vervolgens via de chat-interface als document naar de gebruiker te sturen.

---

## 3. Projectstructuur en Ontwikkeling

### 3.1. Projectstructuur

```
project-root/
├── app/                  # Kernapplicatielogica
│   ├── api/              # FastAPI-endpoints
│   ├── agents/           # LangGraph agentdefinitie en logica
│   ├── data/             # Gegevensopnamepijplijn en watcher-service
│   ├── database/         # Databasemodellen (ORM)
│   ├── tools/            # Agent-tools (Garmin API-wrapper, FIT-generator)
│   └── __init__.py
├── chat_interface/       # Chatbot-specifieke logica (Telegram handlers)
├── tests/                # Unit- en integratietesten
├── config/               # Configuratie en geheimen (.env)
└── requirements.txt      # Projectafhankelijkheden
```

### 3.2. Initiële Installatie

1.  Installeer Python 3.10+.
2.  Zet een virtuele omgeving op (`python -m venv venv`).
3.  Installeer afhankelijkheden: `fastapi`, `uvicorn`, `langgraph`, `sqlalchemy`, `sqlalchemy-timescaledb`, `psycopg2-binary`, `garminconnect`, `fit-tool`, `celery`.
4.  Zet de PostgreSQL-database op en activeer de TimescaleDB-extensie.

---

## 4. Actiegericht Stappenplan

Fase 1 (MVP):

1.  Database Opzet: Configureer PostgreSQL + TimescaleDB met de gedefinieerde tabellen.
2.  Data-opname: Bouw de pijplijn met `garminconnect` om gebruikers en activiteiten te synchroniseren.
3.  Kernapplicatie: Ontwikkel de Telegram-interface en de basis-agent in LangGraph, ontsloten via FastAPI.
4.  Logica: Implementeer de kernlogica om op basis van Garmin-gegevens een trainingsplan te genereren.
5.  Levering: Creëer de tool voor het genereren van .FIT-bestanden met `fit-tool` en stuur de bestanden naar de gebruiker.

Fase 2 (Uitbreiding):

1.  Proactiviteit: Integreer Celery om de "watcher" te implementeren voor proactieve analyses en berichten.
2.  Algoritme Verfijning: Verbeter het trainingsalgoritme met meer diepgaande fysiologische principes.
3.  Testen: Voer prestatie- en schaalbaarheidstests uit.

Fase 3 (Commercialisering):

1.  API-migratie: Migreer naar de officiële commerciële Garmin API.
2.  WhatsApp Integratie: Ontwikkel de WhatsApp-interface via een provider zoals Twilio.
3.  Naleving: Zorg voor naleving van de WhatsApp Business API-regels.
