#!/usr/bin/env bash
set -euo pipefail
OWNER="${GITHUB_OWNER:-iamrichmack111}"
REPO="${1:-physics-reality-tutor}"
FULL="$OWNER/$REPO"

gh repo edit "$FULL" \
  --description "Self-paced Physics, Philosophy, Logic & ELA tutor with Aristotelian debate, Manim experiments, adaptive mastery, and self-grading." \
  --homepage "https://physics.richmackos.com" \
  --enable-issues \
  --enable-wiki

for topic in physics education flask manim philosophy logic homeschool adaptive-learning sqlite docker ela critical-thinking self-paced-learning spaced-repetition argumentation; do
  gh repo edit "$FULL" --add-topic "$topic"
done

echo "✓ Repository description, homepage, issues, wiki, and topics updated."
echo "✓ Push main to trigger CI + CodeQL."
