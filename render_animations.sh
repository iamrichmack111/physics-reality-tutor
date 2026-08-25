#!/usr/bin/env bash
set -euo pipefail
mkdir -p static/animations
if ! command -v manim >/dev/null 2>&1; then echo 'Manim is not installed. Install it, then rerun this script.'; exit 1; fi
for scene in Definitions Syllogism LimitedRendering Information MathematicalUniverse Simulation; do manim -ql manim_scenes/scenes.py "$scene"; done
find media/videos -type f -name '*.mp4' | while read -r f; do
  b=$(basename "$f")
  case "$b" in
    Definitions.mp4) cp "$f" static/animations/definitions.mp4;;
    Syllogism.mp4) cp "$f" static/animations/syllogism.mp4;;
    LimitedRendering.mp4) cp "$f" static/animations/limited_rendering.mp4;;
    Information.mp4) cp "$f" static/animations/information.mp4;;
    MathematicalUniverse.mp4) cp "$f" static/animations/mathematical_universe.mp4;;
    Simulation.mp4) cp "$f" static/animations/simulation.mp4;;
  esac
done
echo 'Animations copied to static/animations/'
