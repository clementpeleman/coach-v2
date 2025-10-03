#!/bin/bash
# Bot Management Script
# Manages the Telegram bot process

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/.bot.pid"

cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_help() {
    echo "Bot Management Script"
    echo ""
    echo "Usage: ./scripts/bot.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start the bot"
    echo "  stop        - Stop the bot"
    echo "  restart     - Restart the bot"
    echo "  status      - Check if bot is running"
    echo "  logs        - Show bot logs (if running in background)"
    echo "  help        - Show this help message"
    echo ""
}

check_running() {
    if pgrep -f "python.*telegram_bot.py" > /dev/null; then
        return 0
    else
        return 1
    fi
}

start_bot() {
    echo -e "${YELLOW}Starting Telegram bot...${NC}"

    # Check if already running
    if check_running; then
        echo -e "${RED}✗ Bot is already running!${NC}"
        echo "  Use './scripts/bot.sh stop' first"
        exit 1
    fi

    # Check database is running
    if ! docker ps | grep -q coach_db; then
        echo -e "${YELLOW}Database not running. Starting it...${NC}"
        ./scripts/dev.sh db
        sleep 5
    fi

    # Check environment mode
    DB_HOST=$(grep DB_HOST .env | cut -d '=' -f2 | tr -d '"' | tr -d ' ')
    if [ "$DB_HOST" = "db" ]; then
        echo -e "${YELLOW}⚠️  Warning: Running in Docker mode but starting bot locally${NC}"
        echo "  Consider switching: ./scripts/dev.sh local"
        echo ""
    fi

    # Start bot
    nohup python chat_interface/telegram_bot.py > bot.log 2>&1 &
    BOT_PID=$!
    echo $BOT_PID > "$PID_FILE"

    sleep 2

    if check_running; then
        echo -e "${GREEN}✓ Bot started successfully${NC}"
        echo "  PID: $BOT_PID"
        echo "  Logs: tail -f bot.log"
        echo "  Stop: ./scripts/bot.sh stop"
    else
        echo -e "${RED}✗ Bot failed to start${NC}"
        echo "  Check logs: cat bot.log"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_bot() {
    echo -e "${YELLOW}Stopping Telegram bot...${NC}"

    if ! check_running; then
        echo -e "${YELLOW}Bot is not running${NC}"
        rm -f "$PID_FILE"
        return
    fi

    # Kill all instances
    pkill -f "python.*telegram_bot.py" || true
    rm -f "$PID_FILE"

    sleep 2

    if check_running; then
        echo -e "${RED}✗ Failed to stop bot${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Bot stopped${NC}"
    fi
}

restart_bot() {
    echo -e "${YELLOW}Restarting bot...${NC}"
    stop_bot
    sleep 1
    start_bot
}

show_status() {
    echo -e "${GREEN}=== Bot Status ===${NC}"
    echo ""

    if check_running; then
        PID=$(pgrep -f "python.*telegram_bot.py")
        echo -e "Status: ${GREEN}Running${NC}"
        echo "PID: $PID"

        if [ -f "$PID_FILE" ]; then
            STORED_PID=$(cat "$PID_FILE")
            echo "Stored PID: $STORED_PID"
        fi

        echo ""
        echo "Process details:"
        ps aux | grep -E "PID|$PID" | grep -v grep
    else
        echo -e "Status: ${RED}Not running${NC}"

        if [ -f "$PID_FILE" ]; then
            echo -e "${YELLOW}⚠️  Stale PID file found${NC}"
            rm -f "$PID_FILE"
        fi
    fi
}

show_logs() {
    if [ ! -f "bot.log" ]; then
        echo -e "${RED}No log file found${NC}"
        echo "Start the bot first: ./scripts/bot.sh start"
        exit 1
    fi

    echo -e "${GREEN}=== Bot Logs (Ctrl+C to exit) ===${NC}"
    tail -f bot.log
}

# Main command handler
case "${1:-help}" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help)
        print_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        print_help
        exit 1
        ;;
esac
