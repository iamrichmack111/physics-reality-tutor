# Security

Controls and validation include:
- hashed account passwords
- forced initial admin password change
- production `SECRET_KEY` via environment
- localhost-only container binding
- Nginx/TLS public edge
- persistent data outside disposable container layers
- dependency audit in CI
- secret scanning
- Python compilation checks
- Docker build validation
- D2 diagram validation
- production health endpoint

Never commit `.env`, production databases, deployment keys, or tokens.
