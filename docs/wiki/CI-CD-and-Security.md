# CI/CD and Security

The repository treats validation as executable policy.

## CI

The main CI workflow verifies the Python application, dependencies, D2 documentation, Docker configuration, image build, and runtime health.

## Dependency auditing

`pip-audit` checks the Python dependency set for known vulnerabilities. The pipeline intentionally fails when vulnerable versions are detected.

## Secret scanning

A high-confidence repository scanner checks for likely committed credentials while avoiding obvious environment-variable plumbing and known test placeholders.

## CodeQL

CodeQL provides static analysis of the Python codebase.

## Dependabot

Dependabot proposes dependency updates as pull requests. Those updates must pass the same CI and CodeQL gates before merge.

## Playwright

Playwright provides browser-level validation. This catches failures that Python compilation alone cannot detect: broken routes, login flow failures, template problems, or pages that no longer render.

## D2 validation

Architecture documentation is validated in CI. Broken diagram syntax therefore becomes a detectable repository failure.

## Container validation

Docker Compose configuration is checked, the image is built, a container is started, and the health endpoint is exercised.

## Defense in depth

No single check proves an application is secure. The value comes from multiple independent controls covering dependencies, source code, credentials, packaging, runtime behavior, and maintenance.
