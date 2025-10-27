#!/bin/bash
# Start FastAPI server for Garmin OAuth callbacks and webhooks

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🚀 Starting FastAPI server...${NC}"
echo ""

# Check if database is running
if ! docker ps | grep -q coach_db; then
    echo -e "${YELLOW}Database not running. Starting it...${NC}"
    ./scripts/dev.sh db
    sleep 5
fi

echo -e "${GREEN}Starting FastAPI on http://localhost:8000${NC}"
echo ""
echo "Available endpoints:"
echo "  - http://localhost:8000/docs (API documentation)"
echo "  - http://localhost:8000/garmin/auth/callback (OAuth callback)"
echo "  - http://localhost:8000/garmin/webhook/* (Webhooks)"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

uvicorn app.api.main:app --port 8000
