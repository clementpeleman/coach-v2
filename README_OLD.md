# Quick Start Guide

## 🚀 Getting Started

### Prerequisites
- Docker installed and running
- Python 3.10+
- Telegram bot token
- OpenAI API key

### Initial Setup

1. Clone and navigate to project:
   ```bash
   cd coach-v2
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   # Copy example file
   cp .env.example .env

   # Edit .env with your credentials
   nano .env
   ```

4. Generate encryption key (already done if you used setup script):
   ```bash
   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

5. Start database:
   ```bash
   ./scripts/dev.sh db
   ```

6. Run migrations (if upgrading from old version):
   ```bash
   ./scripts/dev.sh migrate
   ```

## 📋 Common Commands

### Development Helper Script

The `dev.sh` script helps manage your environment:

```bash
./scripts/dev.sh [command]
```

Commands:
- `local` - Switch to local development mode
- `docker` - Switch to Docker mode
- `start` - Start all Docker services
- `stop` - Stop all Docker services
- `db` - Start only database
- `migrate` - Run password migration
- `status` - Show current environment
- `help` - Show help message

### Quick Run Scripts

Run locally (database in Docker, bot on host):
```bash
./scripts/run_local.sh
```

Run in Docker (everything containerized):
```bash
./scripts/run_docker.sh
```

## 🎯 Usage Examples

### Switching Between Modes

Local Development (recommended):
```bash
./scripts/dev.sh local    # Switch to local mode
./scripts/dev.sh db       # Start database
python chat_interface/telegram_bot.py
```

Docker Mode:
```bash
./scripts/dev.sh docker   # Switch to Docker mode
docker-compose up -d      # Start all services
```

### Running Migrations

Interactive (asks for confirmation):
```bash
python scripts/migrate_passwords.py
```

Non-interactive (auto-confirms):
```bash
python scripts/migrate_passwords.py --yes
```

Dry run (see what would happen):
```bash
python scripts/migrate_passwords.py --dry-run
```

## 🐛 Troubleshooting

### Database Connection Issues

Error: `password authentication failed for user "user"`
Solution:
```bash
./scripts/dev.sh local  # Switch to local mode
./scripts/dev.sh status # Check current configuration
```

Error: `could not translate host name "db"`
Solution: Make sure database is running:
```bash
./scripts/dev.sh db
```

### Environment Variable Issues

Error: `ENCRYPTION_KEY not found`
Solution: Generate and add to .env:
```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
# Add output to .env as ENCRYPTION_KEY=...
```

Error: `Invalid TELEGRAM_BOT_TOKEN format`
Solution: Check your token format in .env (should be like `123456:ABC-DEF...`)

### Migration Issues

Error: `Already encrypted`
Solution: This is normal - passwords already migrated, skip them

Error: `Migration failed`
Solution:
1. Check database is running: `./scripts/dev.sh status`
2. Verify credentials in .env
3. Try dry run first: `python scripts/migrate_passwords.py --dry-run`

## 📦 Project Structure

```
coach-v2/
├── app/
│   ├── agents/          # LangGraph agents
│   ├── database/        # Models, schemas, CRUD
│   ├── tools/           # Agent tools
│   ├── utils/           # Security utilities
│   └── config.py        # Environment validation
├── chat_interface/
│   └── telegram_bot.py  # Telegram bot
├── scripts/
│   ├── dev.sh           # Development helper
│   ├── run_local.sh     # Run locally
│   ├── run_docker.sh    # Run in Docker
│   └── migrate_passwords.py  # Password migration
├── .env                 # Your config (git ignored)
├── .env.local           # Local dev template
├── .env.example         # Example template
└── docker-compose.yml   # Docker configuration
```

## 🔒 Security

- Passwords are encrypted using Fernet (AES-128)
- Login messages auto-deleted from Telegram
- Environment validation on startup
- Comprehensive error handling

See [SECURITY.md](SECURITY.md) for details.

## 📝 Development Workflow

1. Start database: `./scripts/dev.sh db`
2. Switch to local mode: `./scripts/dev.sh local`
3. Run bot: `python chat_interface/telegram_bot.py`
4. Test via Telegram:
   - `/start` - Start bot
   - `/login email password` - Login to Garmin
   - Chat naturally - "show my activities from last week"

## 🚢 Production Deployment

1. Switch to Docker mode: `./scripts/dev.sh docker`
2. Build and start: `docker-compose up -d --build`
3. Check logs: `docker-compose logs -f`
4. Monitor health: `./scripts/dev.sh status`

## 📚 Additional Resources

- [SECURITY.md](SECURITY.md) - Security documentation
- [CHANGELOG_SECURITY.md](CHANGELOG_SECURITY.md) - Recent changes
- [project_specifications.md](project_specifications.md) - Technical specs

## 💡 Tips

- Use `--dry-run` flag to test migrations safely
- Check `./scripts/dev.sh status` when unsure about configuration
- Keep `.env.local` for local development, `.env` for Docker
- Run migrations after pulling updates with password changes
