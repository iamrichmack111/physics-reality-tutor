#!/usr/bin/env bash
set -euo pipefail

APP_DIR_LOCAL="$(cd "$(dirname "$0")/.." && pwd)"
SUBDOMAIN="${SUBDOMAIN:-physics}"
HOSTNAME="${SUBDOMAIN}.richmackos.com"
PORT="${PORT:-5088}"
SERVER_IP="${SERVER_IP:-3.129.79.249}"
REMOTE_DIR="${REMOTE_DIR:-/home/ubuntu/physics-reality-tutor}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/richmackos_deploy}"
SSH=(ssh -o IdentitiesOnly=yes -i "$SSH_KEY" "ubuntu@$SERVER_IP")
RSYNC_SSH="ssh -o IdentitiesOnly=yes -i $SSH_KEY"
R53SUB="${R53SUB:-/Users/richmack/bin/r53sub}"

echo "=== Physics & Reality Tutor -> https://${HOSTNAME} ==="

test -f "$SSH_KEY" || { echo "ERROR: SSH key not found: $SSH_KEY"; exit 1; }
test -x "$R53SUB" || { echo "ERROR: r53sub not found/executable: $R53SUB"; exit 1; }

# New service safety: if the target directory does not yet exist, require the port to be free.
if ! "${SSH[@]}" "test -d '$REMOTE_DIR'"; then
  if "${SSH[@]}" "sudo ss -ltnH | awk '{print \$4}' | grep -Eq '(^|:)${PORT}$'"; then
    echo "ERROR: Port ${PORT} is already in use on production."
    exit 1
  fi
fi

DNS_NOW="$(dig +short "$HOSTNAME" A | tail -1 || true)"
if [ "$DNS_NOW" != "$SERVER_IP" ]; then
  echo "Creating/updating Route 53 record..."
  "$R53SUB" -s "$SUBDOMAIN" -i "$SERVER_IP" -t 300
fi

for i in $(seq 1 30); do
  DNS_NOW="$(dig +short "$HOSTNAME" A | tail -1 || true)"
  [ "$DNS_NOW" = "$SERVER_IP" ] && break
  echo "Waiting for DNS (${i}/30)... current=${DNS_NOW:-none}"
  sleep 5
done

[ "$(dig +short "$HOSTNAME" A | tail -1 || true)" = "$SERVER_IP" ] || {
  echo "ERROR: DNS did not resolve to $SERVER_IP"
  exit 1
}

"${SSH[@]}" "mkdir -p '$REMOTE_DIR/data' '$REMOTE_DIR/backups'"

# Create a production secret only if one does not already exist.
"${SSH[@]}" "if [ ! -f '$REMOTE_DIR/.env' ]; then umask 077; printf 'SECRET_KEY=%s\n' \"\$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')\" > '$REMOTE_DIR/.env'; fi"

rsync -az --delete \
  -e "$RSYNC_SSH" \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.env' \
  --exclude 'data/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'media/' \
  "$APP_DIR_LOCAL/" \
  "ubuntu@$SERVER_IP:$REMOTE_DIR/"

"${SSH[@]}" "cd '$REMOTE_DIR' && python3 -m py_compile app.py init_db.py reader_migrations.py course_migrations.py && docker compose up -d --build --remove-orphans"

READY=0
for i in $(seq 1 30); do
  if "${SSH[@]}" "curl -fsS 'http://127.0.0.1:${PORT}/health' >/dev/null"; then
    READY=1
    break
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  "${SSH[@]}" "cd '$REMOTE_DIR' && docker compose ps && docker compose logs --tail=120"
  exit 1
fi

# On a fresh database, upgrade starter excerpts to the full public-domain books.
"${SSH[@]}" "cd '$REMOTE_DIR' && docker compose exec -T physics-reality python - <<'PY'
import sqlite3
p='data/physics_reality.db'
c=sqlite3.connect(p)
try:
    full=c.execute('select count(*) from books where coalesce(is_full_text,0)=1').fetchone()[0]
except Exception:
    full=0
c.close()
raise SystemExit(0 if full else 10)
PY" || {
  code=$?
  if [ "$code" -eq 10 ]; then
    echo "Importing full public-domain books..."
    "${SSH[@]}" "cd '$REMOTE_DIR' && docker compose exec -T physics-reality python import_public_domain_books.py" || \
      echo "WARNING: Full-book import failed; starter readings remain available."
  else
    exit "$code"
  fi
}

"${SSH[@]}" "sudo tee '/etc/nginx/sites-available/${HOSTNAME}' >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name ${HOSTNAME};

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF
sudo ln -sf '/etc/nginx/sites-available/${HOSTNAME}' '/etc/nginx/sites-enabled/${HOSTNAME}'
sudo nginx -t
sudo systemctl reload nginx"

curl -fsSI "http://${HOSTNAME}" >/dev/null

if ! "${SSH[@]}" "sudo test -f '/etc/letsencrypt/live/${HOSTNAME}/fullchain.pem'"; then
  "${SSH[@]}" "sudo certbot --nginx --non-interactive --agree-tos --redirect -m admin@richmackos.com -d '${HOSTNAME}'"
fi

"${SSH[@]}" "sudo nginx -t && sudo systemctl reload nginx"

curl -fsS "https://${HOSTNAME}/health"
echo
echo "DEPLOYED: https://${HOSTNAME}"
echo "Initial login on a fresh database: admin / admin (forced password change)."
