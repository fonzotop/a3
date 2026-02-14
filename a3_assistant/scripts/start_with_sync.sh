#!/usr/bin/env bash
set -u

APP_PID=""

cleanup() {
  if [ -n "${APP_PID}" ]; then
    kill "${APP_PID}" 2>/dev/null || true
  fi
}

trap cleanup INT TERM

echo "[boot] Starting function sync..."
if python /a3_assistant/scripts/sync_functions.py; then
  echo "[boot] Sync complete."
else
  echo "[boot] WARN: function sync failed, continuing startup to avoid crash loop."
fi

echo "[boot] Starting Open WebUI..."
if [ -f /app/backend/start.sh ]; then
  bash /app/backend/start.sh &
else
  bash start.sh &
fi

APP_PID=$!
echo "[boot] Open WebUI PID: ${APP_PID}"

for i in 1 2 3; do
  sleep 5
  echo "[boot] Post-start sync attempt ${i}..."
  if python /a3_assistant/scripts/sync_functions.py; then
    echo "[boot] Post-start sync successful."
    break
  fi
  echo "[boot] WARN: post-start sync attempt ${i} failed."
done

wait "${APP_PID}"
