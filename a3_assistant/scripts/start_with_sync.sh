#!/usr/bin/env bash
set -u

echo "[boot] Starting function sync..."
if python /a3_assistant/scripts/sync_functions.py; then
  echo "[boot] Sync complete."
else
  echo "[boot] WARN: function sync failed, continuing startup to avoid crash loop."
fi

echo "[boot] Starting Open WebUI..."
if [ -f /app/backend/start.sh ]; then
  exec bash /app/backend/start.sh
else
  exec bash start.sh
fi
