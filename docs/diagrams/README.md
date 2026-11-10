# Diagrams

| Diagram | Source | Exports | Used in |
|---|---|---|---|
| System architecture | `architecture.dot` (Graphviz; replaces the spec §4.2 Mermaid sketch, updated for Railway) | `architecture.svg/.png` | CSE 321 report §2, checkpoint slides |
| Class diagram (curated) | `classes.mmd`: the 15 core models, key fields, multiplicities | `classes.svg/.png` | CSE 321 report §2, checkpoint slides |
| Class diagram (generated) | `graph_models` straight from the code, every field | `classes-generated.dot/.svg/.png` | Proof the curated diagram matches the models |
| ER diagram | `er.mmd` (master copy of spec §5.1) | `er.svg/.png` | CSE 321 report §3 |

Dashed boxes in the architecture diagram are planned, not built yet (Celery worker, Claude API, SMTP).

Regenerate everything: `./scripts/diagrams.sh` (needs Graphviz and Node).
When models change: rerun the script and commit the exports in the same commit as the migration.
