#!/usr/bin/env python3

import re
import subprocess
import sys
from pathlib import Path

SKIP_SUFFIXES = {
    ".md", ".txt", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".mp4", ".zip", ".db"
}

SKIP_PATHS = {
    "scripts/secret_scan.py",
}

PLACEHOLDER_WORDS = {
    "example",
    "placeholder",
    "changeme",
    "change-me",
    "change_me",
    "dummy",
    "sample",
    "testing",
    "test-secret",
    "ci-secret",
    "ci-container-secret",
    "dev-secret",
    "dev-change-me-before-production",
}

PATTERNS = [
    (
        "Private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "AWS access key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "Slack token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    ),
]

ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(
        api[_-]?key |
        access[_-]?token |
        auth[_-]?token |
        secret[_-]?key |
        client[_-]?secret |
        password
    )
    \s*[:=]\s*
    ["']
    ([^"']{12,})
    ["']
    """
)


def tracked_files():
    output = subprocess.check_output(
        ["git", "ls-files", "-z"],
        text=False,
    )

    for raw in output.split(b"\0"):
        if raw:
            yield Path(raw.decode("utf-8", errors="replace"))


def looks_like_placeholder(value: str) -> bool:
    value = value.lower()

    return any(word in value for word in PLACEHOLDER_WORDS)


findings = []

for path in tracked_files():

    if str(path) in SKIP_PATHS:
        continue

    if path.suffix.lower() in SKIP_SUFFIXES:
        continue

    try:
        text = path.read_text(errors="ignore")
    except Exception:
        continue

    for line_number, line in enumerate(text.splitlines(), 1):

        for label, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(
                    (str(path), line_number, label)
                )

        match = ASSIGNMENT.search(line)

        if match:
            value = match.group(2)

            if not looks_like_placeholder(value):
                findings.append(
                    (
                        str(path),
                        line_number,
                        f"Possible literal credential: {match.group(1)}",
                    )
                )


if findings:
    print("Potential committed secrets detected:\n")

    for path, line, reason in findings:
        print(f"{path}:{line}: {reason}")

    print(
        "\nReview these findings before committing."
    )

    sys.exit(1)


print("✓ High-confidence secret scan passed")
