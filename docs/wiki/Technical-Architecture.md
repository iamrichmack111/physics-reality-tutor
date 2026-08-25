# Technical Architecture

## Application layer

Flask handles routing, sessions, grading operations, administrative functions, and page delivery. Jinja templates render the server-side UI.

## Persistence

SQLite stores application state such as accounts, lessons, grades, reading progress, and mastery information.

## Visualization

Manim produces explanatory MP4 animations. D2 stores architecture diagrams as text-based source. Playwright launches a real browser to validate important routes and capture documentation screenshots.

## Browser validation

The automated Playwright suite signs into a fresh test database and exercises representative student-facing pages including dashboard, lesson, experiment lab, library, reader, argument builder, and mastery dashboard.

## Architecture as code

D2 sources include:

* `learning-loop.d2`
* `deployment.d2`
* `mastery-engine.d2`
* `data-flow.d2`

Because these are text files, architecture changes can be versioned and reviewed.

## Data flow

Browser → Flask/Jinja → SQLite

Manim → lesson presentation

Playwright → browser routes

GitHub Actions → CI / CodeQL / Playwright / container build

Docker Buildx → GHCR → production deployment
