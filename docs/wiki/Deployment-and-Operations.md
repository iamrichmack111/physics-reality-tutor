# Deployment and Operations

## Published image

The corrected multi-architecture release is:

`ghcr.io/iamrichmack111/physics-reality-tutor:v1.0.2`

## Supported architectures

* `linux/amd64`
* `linux/arm64`

This permits the same release to run on conventional x86-64 servers and Apple Silicon/ARM systems.

## Release flow

Main branch → CI + CodeQL + Playwright → version tag → Docker Buildx → GHCR → production.

## Health verification

Production deployment should not be considered complete merely because a process started. The application health endpoint should respond successfully through the deployed network path.

## Secrets

Production secrets belong in environment configuration and must not be committed to Git.

## Backups

Persistent SQLite data should be backed up independently of the application container. Replacing a container should not destroy learner records.

## Operational troubleshooting

When deployment fails, isolate the layer:

1. DNS
2. TLS
3. reverse proxy
4. container
5. application process
6. database
7. route
8. browser

This avoids changing several layers at once while diagnosing one failure.
