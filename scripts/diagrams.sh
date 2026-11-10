#!/usr/bin/env bash
# scripts/diagrams.sh — rebuild every diagram export. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/diagrams
MMDC="npx --yes @mermaid-js/mermaid-cli@11.4.2"

# Full class diagram straight from the models: proof the curated one matches the code.
uv run python manage.py graph_models accounts catalog outcomes grading core ingestion reports \
  --group-models --arrow-shape normal --exclude-models "AbstractUser,AbstractBaseUser,PermissionsMixin" \
  --dot -o "$OUT/classes-generated.dot"
dot -Tsvg "$OUT/classes-generated.dot" -o "$OUT/classes-generated.svg"
dot -Tpng -Gdpi=200 "$OUT/classes-generated.dot" -o "$OUT/classes-generated.png"

# Curated class diagram (report/slides), architecture and ER from Mermaid sources
for name in classes architecture er; do
  $MMDC -i "$OUT/$name.mmd" -o "$OUT/$name.svg" -b transparent
  $MMDC -i "$OUT/$name.mmd" -o "$OUT/$name.png" -b white -s 3     # -s 3 = 3x scale, sharp on a projector
done
echo "Diagrams written to $OUT/"
