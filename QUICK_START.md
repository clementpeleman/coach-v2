# 🚀 Quick Start Guide - AI Sports Coach Bot

## Prerequisites

- ✅ Docker Desktop installed and running
- ✅ Python 3.10+ installed
- ✅ Garmin Developer account (already configured in `.env`)

## 🎯 Start the Bot in 3 Commands

```bash
# 1. Run database migration (creates Garmin tables)
alembic upgrade head

# 2. Start the bot
./scripts/run_local.sh

# 3. Check status
./scripts/bot.sh status
```

That's it! Your bot is now running and ready to accept commands.

---

## 📋 Available Scripts

### Bot Management (`./scripts/bot.sh`)

```bash
./scripts/bot.sh start      # Start the Telegram bot
./scripts/bot.sh stop       # Stop the bot
./scripts/bot.sh restart    # Restart the bot
./scripts/bot.sh status     # Check if bot is running
./scripts/bot.sh logs       # View bot logs in real-time
./scripts/bot.sh help       # Show help
```

### Development Helper (`./scripts/dev.sh`)

```bash
./scripts/dev.sh local      # Switch to local mode (DB on localhost)
./scripts/dev.sh docker     # Switch to Docker mode
./scripts/dev.sh db         # Start only database container
./scripts/dev.sh start      # Start all Docker services
./scripts/dev.sh stop       # Stop all services
./scripts/dev.sh status     # Show environment status
./scripts/dev.sh logs       # Show Docker logs
./scripts/dev.sh shell      # Open shell in app container
```

### Quick Run Scripts

```bash
./scripts/run_local.sh      # All-in-one: DB + Bot (recommended)
./scripts/run_docker.sh     # Run in Docker mode
```

---

## 🤖 Using the Bot

### 1. Open Telegram and Start Bot

```
/start
```

You'll see available commands.

### 2. Connect Garmin Account (OAuth2 - Recommended)

```
/garmin_connect
```

Click the link, log in to Garmin, and you're connected!

### 3. Check Connection

```
/garmin_status
```

Verify your Garmin account is connected.

### 4. Sync Data

```
/garmin_sync
```

This fetches your last 7 days of data from Garmin.

### 5. Ask Questions!

```
Hoe heb ik geslapen deze week?
Wat was mijn gemiddelde hartslag gisteren?
Maak een trainingsplan voor volgende week
```

---

## 🔧 Development Workflow

### Starting Fresh

```bash
# 1. Ensure in local mode
./scripts/dev.sh local

# 2. Start database
./scripts/dev.sh db

# 3. Run migrations (if needed)
alembic upgrade head

# 4. Start bot
./scripts/bot.sh start

# 5. Check everything is running
./scripts/dev.sh status
./scripts/bot.sh status
```

### Making Changes to Bot

```bash
# 1. Stop bot
./scripts/bot.sh stop

# 2. Edit code
vim chat_interface/telegram_bot.py

# 3. Restart bot
./scripts/bot.sh start

# 4. Watch logs
./scripts/bot.sh logs
```

### Database Changes

```bash
# 1. Edit models
vim app/database/models.py

# 2. Create migration
alembic revision --autogenerate -m "description"

# 3. Review migration
vim alembic/versions/<new_file>.py

# 4. Apply migration
alembic upgrade head
```

---

## 📊 Checking Status

### Quick Status Check

```bash
./scripts/dev.sh status
./scripts/bot.sh status
```

### Detailed Checks

```bash
# Check database
docker ps | grep coach_db

# Check bot process
ps aux | grep telegram_bot

# View recent logs
tail -50 bot.log

# Live logs
./scripts/bot.sh logs
```

---

## 🐛 Troubleshooting

### Bot Won't Start

Check database is running:
```bash
docker ps | grep coach_db
```

If not running:
```bash
./scripts/dev.sh db
```

Check for errors:
```bash
cat bot.log
```

### Database Connection Issues

Check .env file:
```bash
grep DB_HOST .env
```

Should be `localhost` for local mode.

Switch to local mode:
```bash
./scripts/dev.sh local
```

### Migration Issues

Check current migration:
```bash
alembic current
```

View migration history:
```bash
alembic history
```

Downgrade and re-apply:
```bash
alembic downgrade -1
alembic upgrade head
```

### OAuth Not Working

Make sure FastAPI is running for callbacks:

You need both services running:

```bash
# Terminal 1: Bot
./scripts/bot.sh start

# Terminal 2: FastAPI (for OAuth callbacks)
uvicorn app.api.main:app --reload --port 8000
```

### "Stale PID file" Error

```bash
./scripts/bot.sh stop
rm -f .bot.pid
./scripts/bot.sh start
```

---

## 📝 Environment Modes

### Local Mode (Default)

- Bot runs on host machine
- Database in Docker
- Fast development iteration
- Direct Python debugging

```bash
./scripts/dev.sh local
./scripts/run_local.sh
```

### Docker Mode

- Everything in containers
- Production-like environment
- Isolated dependencies

```bash
./scripts/dev.sh docker
docker-compose up -d
```

---

## 🔐 Security Notes

### Credentials in .env

Your `.env` file contains:
- Telegram Bot Token
- OpenAI API Key
- Garmin Client ID & Secret
- Database passwords
- Encryption key

Never commit `.env` to git! ✅ Already in `.gitignore`

### Garmin OAuth Tokens

All OAuth tokens are:
- ✅ Encrypted at rest (Fernet)
- ✅ Automatically refreshed
- ✅ Scoped to specific permissions
- ✅ User can disconnect anytime

---

## 📚 Available Documentation

- `README.md` - Project overview
- `GARMIN_INTEGRATION.md` - Technical Garmin integration details
- `GARMIN_QUICKSTART.md` - 5-minute Garmin setup
- `TELEGRAM_GARMIN_INTEGRATION.md` - Bot commands and flow
- `project_specifications.md` - Original project specs

---

## 🚀 Production Deployment Checklist

- [ ] Update OAuth redirect URI to production URL
- [ ] Deploy FastAPI with HTTPS
- [ ] Configure Garmin webhooks to production
- [ ] Request production Garmin API key
- [ ] Set up monitoring and logging
- [ ] Configure error alerts
- [ ] Set up database backups
- [ ] Review and update rate limits
- [ ] Test with multiple users
- [ ] Create user documentation

---

## 💡 Quick Tips

View logs in real-time:
```bash
./scripts/bot.sh logs
```

Check if bot is responding:
```bash
./scripts/bot.sh status
ps aux | grep telegram_bot
```

Restart after code changes:
```bash
./scripts/bot.sh restart
```

Clean start:
```bash
./scripts/bot.sh stop
rm -f bot.log .bot.pid
./scripts/bot.sh start
```

Check database tables:
```bash
docker exec coach_db psql -U myuser -d coach_db -c "\dt"
```

Query Garmin data:
```bash
docker exec coach_db psql -U myuser -d coach_db -c "SELECT * FROM garmin_tokens;"
```

---

## 🎉 You're Ready!

The bot is fully functional with Garmin OAuth2 integration. Users can now:

1. ✅ Connect their Garmin accounts securely
2. ✅ Sync health and activity data automatically
3. ✅ Ask AI questions about their data
4. ✅ Get personalized coaching recommendations

Start the bot:
```bash
./scripts/run_local.sh
```

Test in Telegram:
```
/start
/garmin_connect
/garmin_sync
"Geef me een trainingsplan voor volgende week"
```

Happy coaching! 🏃‍♂️💪
