#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="iamrichmack111/physics-reality-tutor"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone "git@github.com:${REPO}.wiki.git" "$TMP/wiki"

rsync -a --delete --exclude='.git' "$ROOT/docs/wiki/" "$TMP/wiki/"

mkdir -p "$TMP/wiki/assets/screenshots"
rsync -a "$ROOT/docs/assets/screenshots/" "$TMP/wiki/assets/screenshots/"

# Wiki is a separate repository, so rewrite main-repo relative image paths.
find "$TMP/wiki" -maxdepth 1 -name '*.md' -print0 | while IFS= read -r -d '' f; do
  sed -i.bak 's#../assets/screenshots/#assets/screenshots/#g' "$f"
  rm -f "$f.bak"
done

cd "$TMP/wiki"
git add .
if git diff --cached --quiet; then
  echo "Wiki already up to date."
  exit 0
fi
git commit -m "docs: publish detailed course and engineering wiki"
BRANCH="$(git symbolic-ref --short HEAD)"
git push origin "$BRANCH"
echo "✓ Detailed GitHub Wiki published"
