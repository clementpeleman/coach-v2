#!/bin/bash
# Quick script to run the bot locally

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🤖 Starting AI Sports Coach Bot (Local Mode)"
echo ""

# Check if database is running
if ! docker ps | grep -q coach_db; then
    echo "⚠️  Database not running. Starting it now..."
    ./scripts/dev.sh db
    sleep 5
fi

# Switch to local mode if not already
if grep -q "DB_HOST=db" .env; then
    echo "Switching to local development mode..."
    ./scripts/dev.sh local
fi

echo ""
./scripts/bot.sh start
