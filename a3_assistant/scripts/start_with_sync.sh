#!/usr/bin/env bash
set -euo pipefail

echo "[boot] Starting function sync..."
python /a3_assistant/scripts/sync_functions.py
echo "[boot] Sync complete. Starting Open WebUI..."

exec bash /app/backend/start.sh
