#!/bin/bash
set -e

export MANAGEMENT_SERVER_HOST=0.0.0.0

exec python -u -m agents
