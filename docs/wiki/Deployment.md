# Deployment

Production target: `https://physics.richmackos.com`

Runtime path:
Browser → Route 53 → Nginx/TLS → Docker → Gunicorn on `127.0.0.1:5088` → SQLite bind mount.

The repository includes Docker configuration and deployment scripts. Persistent `.env` and `data/` must never be overwritten by routine deployment.
