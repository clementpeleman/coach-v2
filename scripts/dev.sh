#!/bin/bash
# Development Helper Script
# Manages local vs Docker environments

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_help() {
    echo "Development Helper Script for AI Sports Coach"
    echo ""
    echo "Usage: ./scripts/dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  local       - Switch to local development mode (localhost DB)"
    echo "  docker      - Switch to Docker mode (db container)"
    echo "  start       - Start all Docker services"
    echo "  stop        - Stop all Docker services"
    echo "  restart     - Restart all Docker services"
    echo "  logs        - Show Docker logs"
    echo "  db          - Start only the database container"
    echo "  shell       - Open a shell in the app container"
    echo "  migrate     - Run password migration script"
    echo "  status      - Show current environment status"
    echo "  help        - Show this help message"
    echo ""
}

switch_to_local() {
    echo -e "${YELLOW}Switching to local development mode...${NC}"

    if [ ! -f .env.local ]; then
        echo -e "${RED}Error: .env.local not found${NC}"
        exit 1
    fi

    cp .env .env.docker.backup 2>/dev/null || true
    cp .env.local .env

    echo -e "${GREEN}✓ Switched to local mode${NC}"
    echo "  Database: localhost:5432"
    echo "  Remember to start the database: ./scripts/dev.sh db"
}

switch_to_docker() {
    echo -e "${YELLOW}Switching to Docker mode...${NC}"

    if [ -f .env.docker.backup ]; then
        cp .env.docker.backup .env
    else
        # Update DB_HOST to 'db'
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's/DB_HOST=localhost/DB_HOST=db/g' .env
        else
            sed -i 's/DB_HOST=localhost/DB_HOST=db/g' .env
        fi
    fi

    echo -e "${GREEN}✓ Switched to Docker mode${NC}"
    echo "  Database: db:5432 (Docker network)"
}

start_services() {
    echo -e "${YELLOW}Starting Docker services...${NC}"
    docker-compose up -d
    echo -e "${GREEN}✓ Services started${NC}"
    docker-compose ps
}

stop_services() {
    echo -e "${YELLOW}Stopping Docker services...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ Services stopped${NC}"
}

restart_services() {
    echo -e "${YELLOW}Restarting Docker services...${NC}"
    docker-compose restart
    echo -e "${GREEN}✓ Services restarted${NC}"
}

show_logs() {
    docker-compose logs -f
}

start_db_only() {
    echo -e "${YELLOW}Starting database container...${NC}"
    docker-compose up -d db
    sleep 5

    if docker ps | grep -q coach_db; then
        echo -e "${GREEN}✓ Database started${NC}"
        docker ps --filter "name=coach_db"
    else
        echo -e "${RED}✗ Database failed to start${NC}"
        docker-compose logs db
    fi
}

open_shell() {
    echo -e "${YELLOW}Opening shell in app container...${NC}"
    docker-compose run --rm app /bin/bash
}

run_migration() {
    echo -e "${YELLOW}Running password migration...${NC}"

    DB_HOST=$(grep DB_HOST .env | cut -d '=' -f2)

    if [ "$DB_HOST" = "db" ]; then
        echo "Running in Docker mode..."
        docker-compose run --rm app python scripts/migrate_passwords.py
    else
        echo "Running in local mode..."
        python scripts/migrate_passwords.py
    fi
}

show_status() {
    echo -e "${GREEN}=== Environment Status ===${NC}"
    echo ""

    DB_HOST=$(grep DB_HOST .env | cut -d '=' -f2 | tr -d '"')

    if [ "$DB_HOST" = "localhost" ]; then
        echo "Mode: ${GREEN}Local Development${NC}"
    else
        echo "Mode: ${YELLOW}Docker${NC}"
    fi

    echo "Database Host: $DB_HOST"
    echo ""

    echo -e "${GREEN}=== Docker Containers ===${NC}"
    if docker ps --filter "name=coach" | grep -q coach; then
        docker ps --filter "name=coach"
    else
        echo "No containers running"
    fi
}

# Main command handler
case "${1:-help}" in
    local)
        switch_to_local
        ;;
    docker)
        switch_to_docker
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    db)
        start_db_only
        ;;
    shell)
        open_shell
        ;;
    migrate)
        run_migration
        ;;
    status)
        show_status
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
