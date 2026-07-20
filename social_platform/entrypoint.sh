#!/bin/bash
set -e

python -m social_platform.migrate

exec python -u -m social_platform --host 0.0.0.0 --port 8000
