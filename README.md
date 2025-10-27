# 🤖 AI Sports Coach

An intelligent sports coaching system powered by LangGraph that integrates with Garmin wearables to provide personalized training advice via Telegram.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

## ✨ Features

- 🧠 AI-Powered: LangGraph agents with GPT-4o-mini for intelligent conversations
- ⌚ Garmin Integration: Automatic sync of activities, sleep, and stress data
- 📊 Smart Profiling: AI analyzes your training patterns automatically
- 🏋️ Custom Workouts: Generates personalized .FIT training files
- 🔒 Secure: Encrypted password storage + auto-deleting login messages
- 🐳 Flexible Deployment: Run locally or fully containerized

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure (edit with your credentials)
cp .env.example .env

# 3. Start everything
./scripts/run_local.sh
```

That's it! Your bot is now running. Find it on Telegram and send `/start`

## 📱 Using the Bot

### Telegram Commands

- `/start` - Get started with your AI coach
- `/login <email> <password>` - Connect your Garmin account (message auto-deleted)
- `/delete_my_data` - Remove all your data

### Natural Conversations

Just chat naturally:
- "Show me my activities from last week"
- "How did I sleep last night?"
- "Create a 5K training plan for me"
- "Analyze my running progress"

## 🛠️ Management Commands

### Bot Control
```bash
./scripts/bot.sh start      # Start the bot
./scripts/bot.sh stop       # Stop the bot
./scripts/bot.sh status     # Check if running
./scripts/bot.sh logs       # View live logs
./scripts/bot.sh restart    # Restart bot
```

### Environment Management
```bash
./scripts/dev.sh local      # Switch to local mode
./scripts/dev.sh docker     # Switch to Docker mode
./scripts/dev.sh db         # Start database only
./scripts/dev.sh status     # Show current state
./scripts/dev.sh migrate    # Run password migration
```

## 🏗️ Architecture

```
Telegram User
     ↓
[Telegram Bot API]
     ↓
[Python Telegram Bot]
     ↓
[LangGraph Agent] ←→ [GPT-4o-mini]
     ↓
[Tools Layer]
├─ Garmin API
├─ FIT File Generator  
├─ User Profiler
└─ Database CRUD
     ↓
[PostgreSQL + TimescaleDB]
```

## 🔒 Security

All security best practices implemented:
- ✅ Fernet (AES-128) password encryption
- ✅ Auto-delete login messages  
- ✅ Environment validation on startup
- ✅ Comprehensive error handling
- ✅ No plaintext credentials stored

See [SECURITY.md](SECURITY.md) for full details.

## 📚 Documentation

- [QUICK_START.md](QUICK_START.md) - Detailed setup guide
- [SECURITY.md](SECURITY.md) - Security implementation
- [CHANGELOG_SECURITY.md](CHANGELOG_SECURITY.md) - Recent updates  
- [project_specifications.md](project_specifications.md) - Technical specs

## 🐛 Troubleshooting

### Bot Conflict Error
```bash
./scripts/bot.sh stop    # Kill all instances
./scripts/bot.sh start   # Start fresh
```

### Database Connection Issues
```bash
./scripts/dev.sh status  # Check configuration
./scripts/dev.sh local   # Switch to local mode
./scripts/dev.sh db      # Ensure DB is running
```

### Need Help?
Check [QUICK_START.md](QUICK_START.md) troubleshooting section.

## 📊 Tech Stack

| Component | Technology |
|-----------|------------|
| AI Framework | LangChain, LangGraph |
| LLM | OpenAI GPT-4o-mini |
| Backend | FastAPI, Python 3.10+ |
| Database | PostgreSQL 14 + TimescaleDB |
| Chat Interface | python-telegram-bot |
| Wearables | garminconnect (unofficial API) |
| Workouts | fit-tool |
| Security | cryptography (Fernet) |
| Containers | Docker, Docker Compose |

## 🗺️ Roadmap

### ✅ Phase 1 (MVP) - COMPLETE
- Telegram bot interface
- Garmin integration  
- LangGraph conversational agent
- Activity analysis & profiling
- Workout generation
- Security implementation

### 🚧 Phase 2 (In Progress)
- [ ] Celery task queue
- [ ] Proactive coaching features
- [ ] Advanced training algorithms
- [ ] Performance optimization

### 📅 Phase 3 (Planned)
- [ ] Official Garmin Developer API
- [ ] WhatsApp Business integration
- [ ] Multi-user scale testing
- [ ] Analytics dashboard

## 🤝 Contributing

This is a private project. For issues or feature requests, contact the maintainers.

## 📄 License

Proprietary - All rights reserved

---

Made with ❤️ using LangGraph and Claude Code
