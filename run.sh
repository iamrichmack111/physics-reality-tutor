#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

if ! python -c 'import flask, werkzeug' >/dev/null 2>&1; then
  pip install -r requirements.txt
fi

[ -f data/physics_reality.db ] || python init_db.py
python app.py
