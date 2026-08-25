#!/usr/bin/env bash
set -euo pipefail
APP_DIR_LOCAL="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_IP="${SERVER_IP:-3.129.79.249}"
REMOTE_DIR="${REMOTE_DIR:-/home/ubuntu/physics-reality-tutor}"
PORT="${PORT:-5088}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/richmackos_deploy}"
SSH=(ssh -o IdentitiesOnly=yes -i "$SSH_KEY" "ubuntu@$SERVER_IP")
RSYNC_SSH="ssh -o IdentitiesOnly=yes -i $SSH_KEY"

rsync -az --delete -e "$RSYNC_SSH" \
  --exclude '.git/' --exclude '.github/' --exclude '.env' --exclude 'data/' \
  --exclude '.venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude 'media/' \
  "$APP_DIR_LOCAL/" "ubuntu@$SERVER_IP:$REMOTE_DIR/"

"${SSH[@]}" "cd '$REMOTE_DIR' && python3 -m py_compile app.py init_db.py reader_migrations.py course_migrations.py && docker compose up -d --build --remove-orphans"
for i in $(seq 1 30); do
  if "${SSH[@]}" "curl -fsS 'http://127.0.0.1:${PORT}/health' >/dev/null"; then
    curl -fsS https://physics.richmackos.com/health
    echo
    echo "UPDATE DEPLOYED"
    exit 0
  fi
  sleep 2
done
"${SSH[@]}" "cd '$REMOTE_DIR' && docker compose ps && docker compose logs --tail=120"
exit 1
