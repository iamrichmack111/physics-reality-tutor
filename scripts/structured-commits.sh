#!/usr/bin/env bash
set -euo pipefail
echo "This helper creates truthful commits from the current working tree; it does not falsify historical dates."
git add app.py templates static course_migrations.py reader_migrations.py import_public_domain_books.py 2>/dev/null || true
git commit -m "feat: add adaptive physics and reasoning tutor" || true
git add docs README.md 2>/dev/null || true
git commit -m "docs: add architecture diagrams screenshots and wiki source" || true
git add Dockerfile docker-compose.yml .dockerignore scripts 2>/dev/null || true
git commit -m "build: add Docker production and deployment automation" || true
git add .github SECURITY.md .gitignore 2>/dev/null || true
git commit -m "ci: add validation security scanning and container publishing" || true
