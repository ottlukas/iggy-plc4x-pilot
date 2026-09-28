#!/bin/sh
set -eu

superset db upgrade
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
    --firstname Superset \
    --lastname Admin \
    --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || echo "Superset admin already exists"
superset init
exec gunicorn --bind 0.0.0.0:8088 --workers 2 --worker-class gthread --threads 8 --timeout 120 'superset.app:create_app()'