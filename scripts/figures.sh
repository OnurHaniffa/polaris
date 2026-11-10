#!/usr/bin/env bash
# scripts/figures.sh — rebuild the hand-placed figures (macOS + Microsoft PowerPoint).
# build_figures.py writes one .pptx per figure; PowerPoint exports each to PDF with the real
# Avenir Next and DIN Alternate fonts; pdftoppm turns the PDFs into 300 dpi PNGs.
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="$HOME/Library/Containers/com.microsoft.Powerpoint/Data/Documents/polaris-figs"  # PowerPoint can write here
mkdir -p "$WORK"
uv run --no-project --with python-pptx python docs/diagrams/source/build_figures.py "$WORK"
for f in chain velocity architecture classes; do
  osascript -e "tell application \"Microsoft PowerPoint\"" \
            -e "open POSIX file \"$WORK/$f.pptx\"" \
            -e "set p to active presentation" \
            -e "save p in POSIX file \"$WORK/$f.pdf\" as save as PDF" \
            -e "close p saving no" -e "end tell"
  pdftoppm -r 300 -png -singlefile "$WORK/$f.pdf" "$WORK/$f"
  cp "$WORK/$f.pptx" docs/diagrams/source/
done
cp "$WORK"/{chain,architecture,classes}.png docs/diagrams/
cp "$WORK/velocity.png" docs/process/velocity.png
echo "Figures written to docs/diagrams and docs/process"
