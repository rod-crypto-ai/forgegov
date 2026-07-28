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

# Render services set SERVICE_ROLE and use this image's default CMD.
# Keeping command selection here avoids Docker Command quoting and parsing issues.
case "${SERVICE_ROLE:-}" in
  web)
    exec gunicorn forgegov.wsgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-1}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --access-logfile - \
      --error-logfile -
    ;;
  worker)
    exec celery -A forgegov worker \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
      --concurrency="${CELERY_WORKER_CONCURRENCY:-1}" \
      --max-tasks-per-child="${CELERY_MAX_TASKS_PER_CHILD:-50}"
    ;;
  beat)
    exec celery -A forgegov beat \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
      --pidfile=/tmp/celerybeat.pid \
      --schedule=/tmp/celerybeat-schedule
    ;;
  "")
    # Local Docker Compose and one-off commands continue to work normally.
    exec "$@"
    ;;
  *)
    echo "Unknown SERVICE_ROLE: ${SERVICE_ROLE}" >&2
    exit 64
    ;;
esac
