#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running Django database migrations..."
  attempt=1
  max_attempts="${MIGRATION_MAX_ATTEMPTS:-12}"
  until python manage.py migrate --noinput; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Database migrations failed after $attempt attempts."
      exit 1
    fi
    echo "Migration attempt $attempt failed; retrying in 5 seconds..."
    attempt=$((attempt + 1))
    sleep 5
  done
fi

if [ "${COLLECTSTATIC:-true}" = "true" ]; then
  echo "Collecting Django static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
