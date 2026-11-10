# Diagrams

| Diagram | Source | Export | Used in |
|---|---|---|---|
| Scoring chain (the brief's Elif example) | `source/build_figures.py` → `source/chain.pptx` | `chain.png` | report, slides |
| System architecture | `source/build_figures.py` → `source/architecture.pptx` | `architecture.png` | CSE 321 §2, slides |
| Class diagram (15 core classes) | `source/build_figures.py` → `source/classes.pptx` | `classes.png` | CSE 321 §2, slides |
| Velocity chart | `source/build_figures.py` → `source/velocity.pptx` | `../process/velocity.png` | CSE 311 §2, slides |
| Class diagram, generated | `graph_models` straight from the code | `classes-generated.dot/.svg/.png` | proof the hand-placed one matches the models |
| ER diagram | `er.mmd` (spec §5.1) | `er.svg/.png` | CSE 321 §3 |

The first four are hand-placed in PowerPoint so that no label, line or box overlaps. Each `.pptx`
can be opened and nudged by hand. Rebuild all four with `./scripts/figures.sh` (macOS with
PowerPoint; it exports through PowerPoint so the real Avenir Next and DIN Alternate fonts are used).
Rebuild the generated class diagram and the ER diagram with `./scripts/diagrams.sh`.
