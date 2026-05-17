#!/bin/sh
set -e
if [ "${SKIP_DB_MIGRATIONS:-0}" != "1" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi
echo "Starting: $*"
exec "$@"
