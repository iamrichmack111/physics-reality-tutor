# Architecture

## Application
- Flask/Jinja web application
- SQLite persistent state
- Manim-rendered instructional media
- JavaScript interactive experiments
- Docker + Gunicorn production runtime
- Nginx reverse proxy and TLS in production

## Data durability
Production data is bind-mounted at `./data:/app/data` so container replacement does not erase accounts, grades, reading progress, mastery, or assignments.

## Diagrams
D2 sources live under `docs/diagrams/`.
