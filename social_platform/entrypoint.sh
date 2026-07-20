#!/bin/bash
set -e

python -m alembic -c /app/social_platform/alembic.ini upgrade head

exec python -u -m social_platform --host 0.0.0.0 --port 8000
