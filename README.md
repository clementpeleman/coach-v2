# 🤖 AI Sports Coach

An intelligent sports coaching system powered by LangGraph that integrates Garmin wearables with a Telegram chatbot. Uses GPT-4o-mini to provide personalized training advice in Dutch via OAuth2-secured webhooks.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![Garmin API](https://img.shields.io/badge/garmin-oauth2-green.svg)](https://developer.garmin.com/)

## ✨ Features

- 🧠 **AI-Powered**: LangGraph agents with GPT-4o-mini for intelligent Dutch conversations
- ⌚ **Garmin OAuth2**: Secure integration with official Garmin Health/Activity APIs
- 📊 **Webhook-Based**: Real-time data sync via PUSH/PING notifications
- 🏋️ **Dynamic Workouts**: Generates personalized .FIT files (5 workout types)
- 💪 **Recovery Assessment**: Sleep/stress-based training recommendations (0-6 scale)
- 🔒 **Secure**: Encrypted tokens (Fernet AES-128) + OAuth2 PKCE flow
- 🐳 **Docker-First**: Fully containerized with Docker Compose

## 🚀 Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your credentials:
# - TELEGRAM_BOT_TOKEN
# - OPENAI_API_KEY
# - GARMIN_CONSUMER_KEY
# - GARMIN_CONSUMER_SECRET

# 2. Start all services (bot, API, database)
docker compose up -d

# 3. Check logs
docker compose logs -f bot
```

That's it! Find your bot on Telegram and send `/start`

## 📱 Using the Bot

### Telegram Commands

**Garmin Connection:**
- `/start` - Show welcome message
- `/garmin_connect` - Connect Garmin account (OAuth2)
- `/garmin_status` - Check connection status
- `/garmin_sync` - Check recent synced data
- `/garmin_backfill <days>` - Fetch historical data (max 90 days)
- `/garmin_disconnect` - Disconnect Garmin account

**Data Management:**
- `/delete_my_data` - Remove all your data

### Natural Conversations (Dutch)

Just chat naturally in Dutch:
- "Wat was mijn gemiddelde hartslag gisteren?"
- "Hoe heb ik geslapen vannacht?"
- "Maak een duurtraining van 2 uur voor me"
- "Wat is mijn herstelstatus?"
- "Toon mijn activiteiten van afgelopen week"

## 🛠️ Management Commands

### Docker Services

```bash
docker compose up -d              # Start all services
docker compose down               # Stop all services
docker compose restart bot        # Restart bot container
docker compose restart api        # Restart API container
docker compose logs -f bot        # Follow bot logs
docker compose logs -f api        # Follow API logs
docker compose logs --tail 50 bot # Show last 50 lines
docker ps                         # Check running containers
```

### Database Migrations

```bash
# Run inside bot container
docker compose exec bot alembic revision --autogenerate -m "description"
docker compose exec bot alembic upgrade head
docker compose exec bot alembic downgrade -1
docker compose exec bot alembic current
```

## 🏗️ Architecture

```
Telegram User → [Telegram Bot] → [LangGraph Agent] ↔ [GPT-4o-mini]
                                         ↓
                                    [Tools Layer]
                                    ├─ Recovery Assessment
                                    ├─ Workout Generator
                                    ├─ Health Data Tools
                                    └─ FIT File Generator
                                         ↓
                              [PostgreSQL + TimescaleDB]
                                         ↑
                              [FastAPI Webhooks] ← Garmin API (OAuth2)
```

### Key Components

**1. Chat Interface** (`chat_interface/telegram_bot.py`)
- Python Telegram Bot with OAuth2 flow handling
- HTML formatting for rich messages (`<b>`, `<i>`, `<code>`)
- Chat history management (20 message limit to prevent context bleeding)
- Workout action buttons (upload to Garmin/download FIT)

**2. AI Agent** (`app/agents/conversational_agent.py`)
- LangGraph conversational agent with 13 tools
- Current date automatically passed to agent
- Dutch language system prompt
- Recovery-aware workout recommendations

**3. API Layer** (`app/api/garmin.py`)
- FastAPI webhook receivers for Garmin PUSH/PING notifications
- OAuth2 PKCE endpoints (start, callback, status, disconnect)
- Backfill support for historical data (max 90 days)

**4. Tools Layer** (`app/tools/`)
- `garmin_oauth.py` - OAuth2 PKCE authentication with token refresh
- `garmin_client.py` - Garmin Health/Activity API client
- `garmin_tools.py` - Database queries for health metrics
- `workout_generator.py` - Dynamic FIT file generation (5 types)
- `garmin_workout_upload.py` - Upload workouts to Garmin Connect
- `recovery_tools.py` - Sleep/stress-based recovery scoring (0-6)

**5. Database** (`app/database/`)
- PostgreSQL 14 + TimescaleDB for time-series data
- SQLAlchemy ORM models
- Encrypted token storage with Fernet (AES-128)
- Tables: `garmin_tokens`, `garmin_health_data`, `garmin_activity_data`, `workout_history`

## 🔒 Security

All security best practices implemented:
- ✅ OAuth2 PKCE flow (no password storage)
- ✅ Fernet (AES-128) token encryption in database
- ✅ Auto-delete sensitive Telegram messages
- ✅ Token auto-refresh with 10-minute buffer
- ✅ Environment validation on startup (pydantic-settings)
- ✅ Webhook signature verification (optional)

## 📊 Garmin Integration

### How Data Flows

**1. Initial Connection:**
```
User: /garmin_connect
  ↓
Bot → Garmin OAuth2 URL
  ↓
User authorizes on Garmin
  ↓
Garmin → Callback with auth code
  ↓
Bot exchanges code for access token
  ↓
Token encrypted and stored in DB
```

**2. Real-Time Data (Webhooks):**
```
User syncs Garmin device
  ↓
Garmin → PUSH webhook to /garmin/webhook/health
  ↓
Webhook handler stores data in database
  ↓
User asks bot: "Hoeveel stappen vandaag?"
  ↓
Agent queries database → Returns answer
```

**3. Historical Data (Backfill):**
```
User: /garmin_backfill 30
  ↓
Bot → Garmin backfill API (HTTP 202 Accepted)
  ↓
[Garmin processes request asynchronously - 5-10 minutes]
  ↓
Garmin → PUSH webhooks with historical data
  ↓
Webhooks store data in database
  ↓
User can now query past 30 days
```

### Supported Data Types

**Health API:**
- Daily summaries (steps, distance, calories, heart rate)
- Sleep data (deep/light/REM sleep, sleep score)
- Stress details (3-min averages, Body Battery)
- HRV (heart rate variability)
- Respiration, Pulse Ox, Body Composition

**Activity API:**
- Activity summaries (running, cycling, swimming, etc.)
- Activity details (GPS tracks, heart rate zones, laps)
- Activity files (FIT/TCX/GPX)
- Move IQ (auto-detected activities)

### Limitations

- **Backfill**: Max 90 days for health data, 30 days for activities
- **Rate Limits**: Evaluation keys: 100 days/minute, Production: 10,000 days/minute
- **Webhooks Required**: Direct API queries not supported (webhook-only architecture)

## 🏋️ Workout Generation

### 5 Workout Types

1. **HERSTEL** (Recovery) - Low intensity, active recovery
2. **DUUR** (Endurance) - Long duration, steady pace
3. **THRESHOLD** (Tempo) - At lactate threshold
4. **VO2MAX** (Intervals) - High-intensity intervals
5. **SPRINT** (Max Effort) - Maximum intensity sprints

### Supported Sports

- 🏃 Running (`RUNNING`)
- 🚴 Cycling (`CYCLING`)
- 🏊 Swimming (`LAP_SWIMMING`)
- 🚶 Walking (`CARDIO_TRAINING`)

### Recovery-Aware Generation

The agent automatically assesses recovery before creating intense workouts:
```python
recovery_score = assess_recovery_status(user_id)
# Score 0-6 based on sleep quality and stress levels
# Low score (0-2) → Suggests recovery workout
# High score (4-6) → Approves intense workouts
```

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) - Developer guidance for Claude Code
- [QUICK_START.md](QUICK_START.md) - Detailed setup guide with troubleshooting
- [project_specifications.md](project_specifications.md) - Technical specifications
- [api-docs/](api-docs/) - Garmin API documentation (Health API, Activity API)

## 🐛 Troubleshooting

### Bot Not Starting

```bash
docker compose ps                # Check container status
docker compose logs bot          # Check for errors
docker compose restart bot       # Restart container
docker compose down && docker compose up -d --build  # Clean rebuild
```

### Garmin Connection Issues

```bash
# Check OAuth status
docker compose exec bot python3 -c "
from app.database.database import get_db
from app.database.models import GarminToken
db = next(get_db())
tokens = db.query(GarminToken).all()
for t in tokens:
    print(f'User {t.user_id}: expires {t.expires_at}')
"
```

### Webhooks Not Working

1. Check webhook URLs are publicly accessible (use ngrok for local dev)
2. Verify `GARMIN_REDIRECT_URI` in `.env` matches registered callback
3. Check API logs: `docker compose logs -f api`
4. Test webhook manually with curl (see Garmin API docs)

### Database Connection Issues

```bash
docker compose ps db             # Check if database is running
docker compose logs db           # Check database logs
docker compose restart db        # Restart database
```

### Backfill Not Receiving Data

1. Wait 5-10 minutes (backfill is asynchronous)
2. Check rate limits (100 days/min for eval keys)
3. Verify user connected within last 1 month (user rate limit)
4. Check webhook logs: `docker compose logs -f api | grep webhook`

## 📊 Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| AI Framework | LangChain, LangGraph | 0.3.27, 0.6.8 |
| LLM | OpenAI GPT-4o-mini | Latest |
| Backend | FastAPI | 0.115.0 |
| Database | PostgreSQL + TimescaleDB | 14 |
| Chat | python-telegram-bot | 22.5 |
| Wearables | Garmin OAuth2 API | Official |
| Workouts | fit-tool | 0.9.13 |
| Security | cryptography (Fernet) | 45.0.5 |
| Containers | Docker Compose | Latest |

## 🗺️ Roadmap

### ✅ Phase 1 (MVP) - COMPLETE
- ✅ Telegram bot interface
- ✅ Garmin OAuth2 integration with webhooks
- ✅ LangGraph conversational agent (Dutch)
- ✅ Activity analysis & health data retrieval
- ✅ Dynamic workout generation (5 types)
- ✅ Recovery assessment system
- ✅ Backfill support for historical data
- ✅ Security implementation (encrypted tokens)

### 🚧 Phase 2 (In Progress)
- [ ] Celery task queue for proactive coaching
- [ ] Advanced training plan generation
- [ ] Performance trend analysis
- [ ] Training load monitoring
- [ ] Automated testing suite

### 📅 Phase 3 (Planned)
- [ ] Production Garmin API key (10K rate limit)
- [ ] WhatsApp Business integration
- [ ] Multi-language support (EN, FR, DE)
- [ ] Web dashboard for analytics
- [ ] Multi-user scale testing

## 🤝 Contributing

This is a private project. For issues or feature requests, contact the maintainers.

## 📄 License

Proprietary - All rights reserved

---

Made with ❤️ using LangGraph, GPT-4o-mini, and Claude Code
