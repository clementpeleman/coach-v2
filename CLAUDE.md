# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI-powered sports coaching system that integrates Garmin wearables with a Telegram chatbot. Uses LangGraph agents (GPT-4o-mini) to provide personalized training advice in Dutch.

## Architecture

### High-Level Flow
```
Telegram User → [Telegram Bot] → [LangGraph Agent] ↔ [GPT-4o-mini]
                                         ↓
                                    [Tools Layer]
                                         ↓
                              [PostgreSQL + TimescaleDB]
                                         ↑
                              [FastAPI Webhooks] ← Garmin API
```

### Key Components

**1. Chat Interface** (`chat_interface/telegram_bot.py`)
- Telegram bot using python-telegram-bot library
- Handles OAuth2 flow for Garmin authentication
- Routes messages to conversational agent
- **Important**: Uses `parse_mode=ParseMode.HTML` for all replies - agent must use HTML tags (`<b>`, `<i>`, `<code>`)

**2. AI Agent** (`app/agents/conversational_agent.py`)
- LangGraph-based conversational agent with OpenAI GPT-4o-mini
- **Critical**: Current date is passed to agent on EVERY message via `current_date` parameter - never needs `get_current_date` tool
- Dutch language interface with HTML formatting for Telegram
- 13 structured tools available (health data, workout generation, recovery assessment)
- System prompt specifies HTML formatting rules for Telegram display

**3. Tools Layer** (`app/tools/`)
- `garmin_oauth.py`: OAuth2 PKCE authentication
- `garmin_client.py`: Garmin API client for data fetching
- `garmin_tools.py`: Health data retrieval from database
- `workout_generator.py`: Dynamic workout generation (5 types: HERSTEL, DUUR, THRESHOLD, VO2MAX, SPRINT)
- `garmin_workout_upload.py`: Direct upload to Garmin Connect
- `recovery_tools.py`: Sleep/stress-based recovery assessment (0-6 scale)

**4. API Layer** (`app/api/main.py`, `app/api/garmin.py`)
- FastAPI application with webhook receivers
- Garmin OAuth2 endpoints (start, callback, status, disconnect)
- Webhook handlers for health/activity data (PING/PUSH notifications)
- Backfill support for historical data

**5. Database** (`app/database/`)
- PostgreSQL 14 + TimescaleDB
- SQLAlchemy ORM models
- Key tables: `user_profile`, `garmin_tokens` (encrypted), `garmin_health_data`, `garmin_activity_data`, `workout_history`

## Development Workflow

### Environment Setup

**This project uses Docker exclusively for all services.**

Start all services:
```bash
docker compose up -d        # Start all services (bot, API, database)
```

### Common Commands

**Docker Services:**
```bash
docker compose up -d              # Start all services
docker compose down               # Stop all services
docker compose restart bot        # Restart bot container
docker compose restart api        # Restart API container
docker compose logs -f bot        # Follow bot logs
docker compose logs -f api        # Follow API logs
docker compose logs --tail 50 bot # Show last 50 lines of bot logs
docker ps                         # Check running containers
```

**Database Migrations:**
```bash
# Run migrations inside the bot container
docker compose exec bot alembic revision --autogenerate -m "description"
docker compose exec bot alembic upgrade head
docker compose exec bot alembic downgrade -1
docker compose exec bot alembic current
```

### Making Code Changes

**Bot changes:**
```bash
# Edit code in chat_interface/telegram_bot.py or app/agents/
docker compose restart bot
docker compose logs -f bot  # Monitor for errors
```

**API changes:**
```bash
# Edit code in app/api/
docker compose restart api
docker compose logs -f api  # Monitor for errors
```

**Agent/tool changes:**
```bash
# Edit code in app/agents/ or app/tools/
docker compose restart bot
docker compose logs -f bot  # Check for import errors
```

**Database schema changes:**
```bash
# 1. Edit app/database/models.py
# 2. Create migration inside container
docker compose exec bot alembic revision --autogenerate -m "add new column"
# 3. Review generated migration in alembic/versions/
# 4. Apply migration
docker compose exec bot alembic upgrade head
```

## Critical Implementation Details

### Date Handling
- **Current date is ALWAYS passed to agent on every message** in `telegram_bot.py:452`
- Agent receives `current_date` parameter in system prompt
- Agent should use this date for context, not call `get_current_date` tool
- When users mention dates without year (e.g., "8 oktober"), assume current year (2025)

### Telegram Formatting
- **Agent MUST use HTML tags** for formatting (not markdown)
- Bold: `<b>text</b>` (not `**text**`)
- Italic: `<i>text</i>` (not `*text*`)
- Code: `<code>text</code>` (not `` `text` ``)
- All replies use `parse_mode=ParseMode.HTML` in `telegram_bot.py:471-473`
- System prompt explicitly instructs agent to use HTML formatting

### Workout Generation
- **5 workout types**: HERSTEL (recovery), DUUR (endurance), THRESHOLD (tempo), VO2MAX (intervals), SPRINT (max effort)
- Dynamic generation - any duration possible (no fixed templates)
- Sport detection from Dutch keywords:
  - "wandelen" → CARDIO_TRAINING
  - "fietsen", "wielrennen" → CYCLING
  - "hardlopen", "rennen" → RUNNING
  - "zwemmen" → LAP_SWIMMING
- **Critical workflow**: Always call `assess_recovery_status()` before creating workout
- Recovery score (0-6) determines recommended workout intensity

### Garmin Integration
- **OAuth2 PKCE flow** (no legacy password login in production)
- Webhooks are primary data source (not polling)
- Data stored in `garmin_health_data` and `garmin_activity_data` tables
- Token refresh automatic with 10-minute buffer
- All tokens encrypted with Fernet (AES-128)

### Security
- All Garmin tokens encrypted in database (`garmin_tokens` table)
- Login messages auto-deleted in Telegram
- Encryption key must be 44 characters (Fernet requirement)
- Environment validation on startup (pydantic-settings)

## Important Files

**Entry Points:**
- `chat_interface/telegram_bot.py` - Bot entry point
- `app/api/main.py` - FastAPI entry point
- `app/agents/conversational_agent.py` - Agent definition

**Configuration:**
- `.env` - Environment variables (gitignored)
- `.env.example` - Template
- `app/config.py` - Validated settings with pydantic
- `docker-compose.yml` - Service orchestration

**Database:**
- `app/database/models.py` - ORM schema
- `alembic/versions/*.py` - Migration history

**Documentation:**
- `README.md` - Project overview
- `QUICK_START.md` - Setup guide with troubleshooting
- `project_specifications.md` - Technical specifications

## Testing Changes

### Bot Testing
```bash
# 1. Restart bot to apply changes
docker compose restart bot

# 2. Monitor logs
docker compose logs -f bot

# 3. Test in Telegram
/start
/garmin_connect
/garmin_status
```

### Agent Testing
```bash
# Test import in container
docker compose exec bot python3 -c "from app.agents.conversational_agent import create_conversational_agent; agent = create_conversational_agent(123456); print('Success')"
```

### Syntax Validation
```bash
# Validate syntax inside container
docker compose exec bot python3 -m py_compile chat_interface/telegram_bot.py
docker compose exec bot python3 -m py_compile app/agents/conversational_agent.py
```

## Common Issues & Solutions

**Bot won't start:**
```bash
docker compose ps           # Check container status
docker compose logs bot     # Check for errors
docker compose restart bot  # Try restarting
```

**Date issues:**
- Verify `current_date` parameter is passed in `telegram_bot.py` (around line 679)
- Check system prompt includes `HUIDIGE DATUM: {current_date}`

**Formatting not showing in Telegram:**
- Ensure `parse_mode=ParseMode.HTML` in reply_text calls
- Verify agent uses HTML tags (not markdown)

**Import errors after code changes:**
```bash
# Rebuild and restart containers
docker compose down
docker compose up -d --build
```

**Database connection issues:**
```bash
docker compose ps           # Check if database is running
docker compose logs db      # Check database logs
docker compose restart db   # Restart database
```

**Container build issues:**
```bash
# Clean rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Telegram Commands

**User commands:**
- `/start` - Show welcome message
- `/garmin_connect` - Start OAuth2 flow
- `/garmin_status` - Check connection status
- `/garmin_sync` - Check recent data
- `/garmin_backfill <days>` - Fetch historical data
- `/garmin_disconnect` - Disconnect Garmin account
- `/delete_my_data` - Delete all user data

## Tech Stack

- **AI**: LangChain 0.3.27, LangGraph 0.6.8, OpenAI GPT-4o-mini
- **Backend**: FastAPI 0.115.0, Python 3.10+
- **Database**: PostgreSQL 14 + TimescaleDB
- **Chat**: python-telegram-bot 22.5
- **Wearables**: Garmin OAuth2 API
- **Workouts**: fit-tool 0.9.13
- **Security**: cryptography 45.0.5 (Fernet)
- **Containers**: Docker + Docker Compose

## Project State

**Modified files (git status):**
- `app/agents/conversational_agent.py` - Date handling, HTML formatting
- `app/tools/garmin_*.py` - Workout generation and upload
- `chat_interface/telegram_bot.py` - Date passing, HTML parse mode

**Current phase:** MVP complete, OAuth2 integrated, dynamic workouts working

**Known limitations:**
- No automated tests
- Celery proactive features not yet implemented
- WhatsApp integration planned for Phase 3
