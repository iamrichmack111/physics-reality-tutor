# Security Policy

## Supported version

The latest tagged release and the current `main` branch receive security fixes.

## Reporting a vulnerability

Do **not** open a public issue containing exploitable details, credentials, tokens, private student information, or production configuration. Report the issue privately to the repository owner through GitHub's private vulnerability reporting feature when enabled.

Include:

- affected version/commit
- reproduction steps
- expected vs. observed behavior
- likely impact
- suggested mitigation, if known

## Security controls

The project uses:

- Werkzeug password hashing
- forced first-login administrator password change
- environment-provided production `SECRET_KEY`
- localhost-only production application binding behind Nginx/TLS
- persistent SQLite data outside disposable container layers
- `.gitignore` / `.dockerignore` exclusions for secrets and runtime state
- CodeQL static analysis
- `pip-audit` dependency vulnerability checks
- committed-secret pattern scanning
- Python compile + Flask smoke tests
- Docker Compose validation
- production image build + `/health` container readiness test
- D2 source validation
- Dependabot update checks

## Never commit

- `.env`
- deployment SSH keys
- AWS credentials
- API tokens
- production SQLite databases
- student/private user data
- generated backups containing private state
