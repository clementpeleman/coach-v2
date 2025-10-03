#!/bin/bash
# Quick script to run the bot in Docker

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🤖 Starting AI Sports Coach Bot (Docker Mode)"
echo ""

# Switch to Docker mode if not already
if grep -q "DB_HOST=localhost" .env; then
    echo "Switching to Docker mode..."
    ./scripts/dev.sh docker
fi

echo "Starting all services with Docker Compose..."
docker-compose up -d

echo ""
echo "✓ Services started!"
echo ""
echo "View logs with: docker-compose logs -f"
echo "Stop with: docker-compose down"
