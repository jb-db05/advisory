#!/usr/bin/env bash
# Copy the visual guidelines into every skill, so each skill folder stays self-contained.
# Run from the repo root after editing brand/visual-guidelines.md.
set -euo pipefail
for d in skills/*/; do
  mkdir -p "$d/references"
  cp brand/visual-guidelines.md "$d/references/visual-guidelines.md"
done
echo "Copied to $(ls -d skills/*/ | wc -l) skills."
