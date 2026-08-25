#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required."
  exit 1
fi

if [ ! -d node_modules ]; then
  npm install
fi

npx playwright install chromium

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt >/dev/null

mkdir -p data
BACKUP=""
if [ -f data/physics_reality.db ]; then
  BACKUP="data/physics_reality.db.playwright-backup"
  cp data/physics_reality.db "$BACKUP"
fi

cleanup() {
  if [ -n "${APP_PID:-}" ]; then
    kill "$APP_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$BACKUP" ] && [ -f "$BACKUP" ]; then
    mv -f "$BACKUP" data/physics_reality.db
  fi
}
trap cleanup EXIT

rm -f data/physics_reality.db
python init_db.py >/dev/null

SECRET_KEY=playwright-only-secret python app.py > /tmp/physics-reality-playwright.log 2>&1 &
APP_PID=$!

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5088/health >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:5088/health >/dev/null
npx playwright test tests/e2e/screenshots.spec.js

echo
echo "Screenshots written to docs/assets/screenshots/"
ls -lh docs/assets/screenshots/
