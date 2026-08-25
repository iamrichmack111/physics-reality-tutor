#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-physics-reality-tutor}"
OWNER="${GITHUB_OWNER:-iamrichmack111}"
FULL="$OWNER/$REPO"

gh repo create "$FULL" --public --source=. --remote=origin --push \
  --description "Self-paced Physics, Philosophy, Logic & ELA tutor with Aristotelian debate, Manim experiments, adaptive mastery, and public-domain primary sources." || true

gh repo edit "$FULL" \
  --description "Self-paced Physics, Philosophy, Logic & ELA tutor with Aristotelian debate, Manim experiments, adaptive mastery, and public-domain primary sources." \
  --homepage "https://physics.richmackos.com" \
  --enable-issues \
  --enable-wiki

gh repo edit "$FULL" --add-topic physics --add-topic education --add-topic flask --add-topic manim \
  --add-topic philosophy --add-topic logic --add-topic homeschool --add-topic adaptive-learning \
  --add-topic sqlite --add-topic docker --add-topic ela --add-topic critical-thinking

create_closed_issue () {
  local title="$1"; shift
  local body="$1"; shift
  local labels="$1"; shift
  url="$(gh issue create -R "$FULL" --title "$title" --body "$body" --label "$labels")"
  num="${url##*/}"
  gh issue close -R "$FULL" "$num" --comment "Completed in the initial production release."
}

gh label create "completed" -R "$FULL" --color "0E8A16" --description "Implemented and verified" --force
gh label create "curriculum" -R "$FULL" --color "1D76DB" --description "Curriculum and pedagogy" --force
gh label create "security" -R "$FULL" --color "D93F0B" --description "Security and validation" --force
gh label create "deployment" -R "$FULL" --color "5319E7" --description "Production and delivery" --force

create_closed_issue "Implement forced first-login admin password change" "Seed admin access must require an immediate password change and persist hashed credentials." "completed,security"
create_closed_issue "Add self-graded lesson and assignment engine" "Add objective grading, attempts, scores, explanations, and mastery updates." "completed,curriculum"
create_closed_issue "Add public-domain primary-source reader" "Provide chapter navigation, reading progress, checks, and Aristotle/Berkeley/Hume import." "completed,curriculum"
create_closed_issue "Add Aristotelian argument builder and debate lab" "Support definitions, proposition, premises, syllogisms, counterargument, steelman, and side switching." "completed,curriculum"
create_closed_issue "Add adaptive mastery and spaced review" "Track skill-level mastery and schedule review for weak concepts." "completed,curriculum"
create_closed_issue "Add interactive physics experiment lab" "Provide pendulum and wave/interference activities with prediction, observation, and lab notes." "completed,curriculum"
create_closed_issue "Containerize production application" "Run with Docker/Gunicorn, localhost binding, persistent data, and /health." "completed,deployment"
create_closed_issue "Add CI security and validation checks" "Compile Python, audit dependencies, scan for secrets, validate D2, build Docker, and run CodeQL." "completed,security"

# Push wiki pages to GitHub's separate wiki repository.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone "git@github.com:$FULL.wiki.git" "$tmp/wiki" || mkdir -p "$tmp/wiki"
cp docs/wiki/*.md "$tmp/wiki/"
(
  cd "$tmp/wiki"
  git init >/dev/null 2>&1 || true
  git add .
  git -c user.name="${GIT_AUTHOR_NAME:-Richmack OS}" \
      -c user.email="${GIT_AUTHOR_EMAIL:-noreply@richmackos.com}" \
      commit -m "docs: publish project wiki" || true
  git branch -M master
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "git@github.com:$FULL.wiki.git"
  git push -u origin master
)

git tag -a v1.0.0 -m "Physics & Reality Tutor v1.0.0" || true
git push origin v1.0.0
echo "GitHub bootstrap complete: https://github.com/$FULL"
