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

# ER diagram from its Mermaid source (the other figures are hand-placed: scripts/figures.sh)
$MMDC -i "$OUT/er.mmd" -o "$OUT/er.svg" -b transparent
$MMDC -i "$OUT/er.mmd" -o "$OUT/er.png" -b white -s 3
echo "Diagrams written to $OUT/"
