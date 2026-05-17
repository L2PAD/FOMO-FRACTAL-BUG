#!/bin/bash
# Periodic job runner - runs expire_subscriptions every hour

PYTHON_CMD="/root/.venv/bin/python"

while true; do
    echo "[$(date)] Running subscription expiration job..."
    cd /app/backend
    $PYTHON_CMD jobs/expire_subscriptions.py
    echo "[$(date)] Job complete. Sleeping for 1 hour..."
    sleep 3600  # 1 hour
done
