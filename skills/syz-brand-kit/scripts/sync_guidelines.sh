#!/usr/bin/env bash
# Copy the brand kit's visual guidelines into every other skill, so each skill folder stays
# self-contained. Run from the repo root after editing skills/syz-brand-kit/references/visual-guidelines.md.
set -euo pipefail
SRC=skills/syz-brand-kit/references/visual-guidelines.md
n=0
for d in skills/*/; do
  [ "$d" = "skills/syz-brand-kit/" ] && continue
  mkdir -p "$d/references"; cp "$SRC" "$d/references/visual-guidelines.md"; n=$((n+1))
done
echo "Copied to $n skills."
