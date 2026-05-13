# AGENTS.md

## Cursor Cloud specific instructions

### Environment overview

This project is a Docker-first Python application (FastAPI + Telegram bot + PostgreSQL/TimescaleDB). In Cursor Cloud VMs, Docker container execution may fail due to cgroupv2 "domain threaded" restrictions. **Run services directly on the host instead of via `docker compose`.**

### Running services on the host

1. **PostgreSQL**: Start with `sudo pg_ctlcluster 14 main start`. Database user `coach` / DB `coach_db` should already exist.
2. **FastAPI API**: `PYTHONPATH=/workspace uvicorn app.api.main:app --host 0.0.0.0 --port 8000` (from `/workspace`).
3. **Telegram Bot**: `PYTHONPATH=/workspace python3 chat_interface/telegram_bot.py` — requires valid `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` in `.env`.
4. **Next.js webapp** (optional): `cd webapp && npm run dev` — runs on port 3000.

### Key caveats

- The `.env` file must have `DB_HOST=localhost` when running on the host (not `db` which is the Docker network alias).
- The `API_URL` env var is only used by the bot in Docker mode; comment it out or omit it for local development — the pydantic `Settings` class rejects unknown fields.
- `fit-tool==0.9.13` has been removed from PyPI; use `fit-tool==0.9.14` in `requirements.txt`.
- Database migrations: `PYTHONPATH=/workspace alembic upgrade head` (from `/workspace`).
- Python syntax validation: `PYTHONPATH=/workspace python3 -m py_compile <file>`.

### Lint & test commands

- **Python lint**: No dedicated linter configured; use `python3 -m py_compile` for syntax checks.
- **Webapp lint**: `cd webapp && npm run lint` (ESLint).
- **Automated tests**: Not yet implemented (see `CLAUDE.md`).

### Secrets required for full functionality

- `TELEGRAM_BOT_TOKEN` — Telegram bot token (must contain `:`)
- `OPENAI_API_KEY` — OpenAI API key for GPT-4o-mini agent
- `ENCRYPTION_KEY` — 44-char Fernet key (generate with `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`)
