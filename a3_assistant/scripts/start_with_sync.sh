#!/usr/bin/env bash
set -u

APP_PID=""

cleanup() {
  if [ -n "${APP_PID}" ]; then
    kill "${APP_PID}" 2>/dev/null || true
  fi
}

trap cleanup INT TERM

echo "[boot] Restoring global_active.json from persisted ACTIVE_DIR..."
python3 - << 'PYEOF'
import json, pathlib

STATE   = pathlib.Path('/app/backend/data/a3_state')
ACTIVE  = STATE / 'active_users'
PROJECTS= STATE / 'projects'
OUT     = STATE / 'global_active.json'

pid = None

# 1. Most recently written active_user file
if ACTIVE.exists():
    files = sorted(ACTIVE.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            candidate = str(data.get('project_id', '')).strip()
            if candidate:
                pid = candidate
                print(f'[boot-active] found in {f.name}: {pid}')
                break
        except Exception:
            pass

# 2. Most recently modified project file (prefer non-default)
if not pid and PROJECTS.exists():
    files = list(PROJECTS.glob('*.json'))
    real = sorted([f for f in files if f.stem != 'A3-0001'],
                  key=lambda f: f.stat().st_mtime, reverse=True)
    pick = real or sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    if pick:
        pid = pick[0].stem
        print(f'[boot-active] mtime fallback: {pid}')

if pid:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'project_id': pid}), encoding='utf-8')
    print(f'[boot-active] global_active.json written: {pid}')
else:
    print('[boot-active] no projects found, skipping')
PYEOF

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
