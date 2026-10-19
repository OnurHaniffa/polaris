# Build guide · Sprints 4 and 5

**Sprint 4:** Mon 9 – Sun 15 Nov · light sprint (CSE 311 midterm Tue 10 Nov, **CSE 321 checkpoint Thu 12 Nov**)
**Sprint 5:** Mon 16 – Sun 22 Nov · light sprint (**CSE 311 checkpoint Tue 17 Nov**, CSE 321 midterm Thu 19 Nov)

These two weeks hold both checkpoints and two midterms, so they're planned at half velocity. Each sprint has one real feature story, and the rest is checkpoint work:

- **Sprint 4** finishes bulk grade upload (T1.1).
- **Sprint 5** lays the whole back half of the AI wizard: the background worker, the Claude call, validation and the eval set. Sprint 6 only has to build screens on top of it.

Spec sections this chapter implements: §5.6 (diagrams, transactions), §6 T1.1, Part 7 (§7.2–7.10), §9.5 (evidence), §13.1, §13.2.

---

# Sprint 4 — Light: CSE 321 checkpoint (Mon 9 – Sun 15 Nov)

**Sprint goal:** present our data and system architecture on Thursday, and let instructors upload a whole gradebook file with a dry run before anything is saved.

| ID | Story | Pts | Owner | Merge order |
|---|---|---|---|---|
| S4-01 | Diagrams exported to `docs/diagrams/` | 3 | A | 1 (needed by S4-02 on Wednesday) |
| S4-02 | CSE 321 checkpoint report + slides | 3 | A + all | Slides frozen Wed 11 Nov 20:00 |
| S4-03 | Bulk upload: dry run + confirm + golden-file tests | 5 | B | 3 (any time; builds on the S3-08 spike) |
| S4-04 | Baseline bug fixes from the Sprint 3 review | 2 | C | 2 (before Wednesday, so the live demo runs on fixed code) |
| S4-05 | CSE 311 checkpoint evidence | 2 | C | Sunday |

**By Sunday:**
1. The checkpoint was presented, and the report PDF is in `docs/reports/cse321-checkpoint.pdf`.
2. On staging, an instructor uploads `seed/grades/messy.xlsx`, sees every problem listed, ticks "skip invalid rows", confirms, and finds 6 new and 1 changed **draft** grades in the sheet.
3. `docs/process/` has everything S5-01 needs.

**Midterm week rule.** Nobody opens a PR between Monday 18:00 and Tuesday's exam. Reviews wait until Tuesday evening. Put this in the sprint planning notes so the velocity dip has a written reason.

---

## S4-01 · Diagrams: architecture, class, ER

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S4-01-diagrams` · **Depends on:** Sprint 3 models merged

### Goal

Three diagrams the CSE 321 checkpoint needs (slides 4, 6, 7 in §13.1). Each is kept as an editable **source file** next to its **export**, so it can be regenerated in one command when the models change. The final report in December reuses the same files.

Generated diagrams beat hand-drawn ones for one reason: they can't drift away from the code. The class diagram is produced from the real models, and the ER and architecture diagrams are the Mermaid sources already in the spec (§4.2, §5.1), so the spec and the slides show the same picture.

### Files

| Path | Create/modify | What |
|---|---|---|
| `docs/diagrams/architecture.mmd` | create | Mermaid source, copied from spec §4.2 |
| `docs/diagrams/er.mmd` | create | Mermaid source, copied from spec §5.1 |
| `docs/diagrams/classes.dot` | generated | Graphviz source from `graph_models` |
| `docs/diagrams/{architecture,er,classes}.svg` and `.png` | generated | Exports for slides (PNG) and the report (SVG scales cleanly when printed at 125%) |
| `docs/diagrams/README.md` | create | How to regenerate |
| `scripts/diagrams.sh` | create | One command that rebuilds every export |
| `pyproject.toml` | modify | `django-extensions` as a dev dependency |
| `config/settings/dev.py` | modify | Add `django_extensions` to `INSTALLED_APPS` (dev only) |

### Steps

**1. Install the tools.** `django-extensions` provides `graph_models`. We ask it for a `.dot` file and run Graphviz's `dot` ourselves. That route needs no Python Graphviz bindings, and those bindings (`pygraphviz`) are painful to install on macOS. Mermaid diagrams are exported with the official CLI through `npx`, so nobody has to install Node packages globally.

```bash
uv add --dev "django-extensions~=4.1"
brew install graphviz            # Linux: sudo apt install graphviz
node --version                   # any Node ≥ 20; npx downloads mermaid-cli on first use
```

```python
# config/settings/dev.py  (add below the debug_toolbar lines)
INSTALLED_APPS += ["django_extensions"]  # noqa: F405  graph_models for docs/diagrams (S4-01)
```

**2. Copy the Mermaid sources out of the spec.** Copy the fenced block under §4.2 into `docs/diagrams/architecture.mmd`, and the one under §5.1 into `docs/diagrams/er.mmd`. Copy only the inside of the fence, without the ```` ```mermaid ```` lines. From now on these files are the master copies. If you change one, paste it back into the spec in the same PR. The spec is a living document that changes with the code, and this keeps the diagrams in step with it.

**3. The regeneration script.**

```bash
#!/usr/bin/env bash
# scripts/diagrams.sh — rebuild every diagram export. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/diagrams
MMDC="npx --yes @mermaid-js/mermaid-cli@12.0.0"

# Class diagram straight from the models. Leave out Django's own apps; group by app.
uv run python manage.py graph_models accounts catalog outcomes grading core ingestion reports \
  --group-models --arrow-shape normal --exclude-models "AbstractUser,AbstractBaseUser,PermissionsMixin" \
  --dot -o "$OUT/classes.dot"
dot -Tsvg "$OUT/classes.dot" -o "$OUT/classes.svg"
dot -Tpng -Gdpi=200 "$OUT/classes.dot" -o "$OUT/classes.png"

for name in architecture er; do
  $MMDC -i "$OUT/$name.mmd" -o "$OUT/$name.svg" -b transparent
  $MMDC -i "$OUT/$name.mmd" -o "$OUT/$name.png" -b white -s 3     # -s 3 = 3x scale, sharp on a projector
done
echo "Diagrams written to $OUT/"
```

```bash
chmod +x scripts/diagrams.sh && ./scripts/diagrams.sh
```

**4. Tidy the class diagram if needed.** With 15+ models, Graphviz can put `User` in the middle with arrows everywhere. If the slide is unreadable, open `classes.svg` in draw.io (File → Import), move the boxes, and save the result as `docs/diagrams/classes.drawio` plus a `classes-tidy.png` export. Keep the generated version as well, because it's the one that proves the diagram matches the code.

**5. `docs/diagrams/README.md`.**

```markdown
# Diagrams

| Diagram | Source | Exports | Used in |
|---|---|---|---|
| System architecture | `architecture.mmd` (master copy of spec §4.2) | `architecture.svg/.png` | CSE 321 slide 4, report §2 |
| Class diagram | generated from models | `classes.dot/.svg/.png` | CSE 321 slide 6, report §2 |
| ER diagram | `er.mmd` (master copy of spec §5.1) | `er.svg/.png` | CSE 321 slide 7, report §3 |

Regenerate everything: `./scripts/diagrams.sh` (needs Graphviz and Node).
When models change: rerun the script and commit the exports in the same PR as the migration.
```

### Tests

There's no automated test for pictures. Add one review checklist item to the PR template instead, under "Checklist": `- [ ] Models changed? Ran ./scripts/diagrams.sh and committed the exports.`

### Check it works

1. Run `./scripts/diagrams.sh`. It finishes with "Diagrams written to docs/diagrams/" and six image files exist.
2. Open `classes.svg`. Every model from spec §5.2 is there, including `IngestionJob` and `ExportJob`, and so is the M2M `CourseOffering.instructors`.
3. Open `er.png` at full screen and read it from 3 metres away, as a projector audience would. If the text is too small, raise `-s 3` to `-s 4`.

### Done when

- [ ] Three diagrams, each with an editable source and SVG + PNG exports, committed
- [ ] `scripts/diagrams.sh` reproduces them from scratch on a second laptop
- [ ] README explains how to regenerate

### Commits and PR

```
Add django-extensions for model graphs (#S4-01)
Add Mermaid sources for architecture and ER diagrams
Add diagrams.sh to regenerate every diagram export
Export architecture, class and ER diagrams
```

PR title: **Diagrams for the CSE 321 checkpoint (S4-01)**

---

## S4-02 · CSE 321 checkpoint report and slides

**Points:** 3 · **Owner:** Person A, everyone presents · **Branch:** `docs/S4-02-cse321-checkpoint` · **Depends on:** S4-01

### Goal

Deliver spec §13.1: about 10 minutes, 10–12 slides, and a 4–6 page report on Thursday 12 Nov. The *content* is already decided in §13.1. This story is the **runbook**: who does what on which day, so a midterm on Tuesday doesn't push the slides to Wednesday night.

### Files

| Path | Create/modify | What |
|---|---|---|
| `docs/reports/cse321-checkpoint/report.md` | create | Report source (Markdown, exported to PDF) |
| `docs/reports/cse321-checkpoint/slides.pdf` | create | Exported slides (built in Google Slides, the team's shared tool) |
| `docs/reports/cse321-checkpoint/explain/*.txt` | create | `EXPLAIN ANALYZE` outputs pasted into the report |
| `docs/reports/cse321-checkpoint.pdf` | create | Final report PDF |

### Steps

**1. Timeline.** Paste it into the sprint's planning notes.

| When | What | Who |
|---|---|---|
| Mon 9 Nov | Slide skeleton: 12 empty slides with titles from §13.1, speakers assigned | A |
| Mon 9 Nov | `EXPLAIN ANALYZE` runs on staging (step 3) | A |
| Tue 10 Nov | Midterm. No project work | — |
| Wed 11 Nov 12:00 | Each speaker fills in their slides | all |
| Wed 11 Nov 18:00 | Report draft complete (step 4) | A writes, B + C review |
| Wed 11 Nov 20:00 | **Slides frozen.** Rehearsal 1, timed (step 5) | all |
| Thu 12 Nov morning | Rehearsal 2 (10 min), then print the report | all |
| Thu 12 Nov 22:00 | Commit slides + report PDF; S4-02 → Done | A |

**2. Who presents what.** Three speakers of roughly 3 minutes each:

| Slides | Speaker | Why them |
|---|---|---|
| 1–3 (problem, scoring chain, design questions) | C | Owns the student and department pages that show the chain |
| 4–5 (architecture, why each component) | C | Owns Docker, CI/CD, hosting |
| 6–9 (classes, ER, constraints, transactions) | A | Owns the data model |
| 10–11 (planned reporting tables, live demo) | B | Drives the live demo from the instructor side |

**3. Collect the database evidence.** Slides 8–9 are stronger when they show that the indexes and locks really exist. Run these on **staging**, where the seeded data is (spec Appendix B: 120 students, 12 courses). Use `psql` inside the db container:

```bash
ssh deploy@<host>
cd ~/polaris-staging && docker compose -f compose.prod.yml exec db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

```sql
-- 1. The partial unique index exists and is partial
SELECT indexname, indexdef FROM pg_indexes WHERE indexname = 'one_active_po_set_per_program';

-- 2. Grade sheet load uses uniq_grade (assessment, enrollment)
EXPLAIN ANALYZE
SELECT g.* FROM grading_grade g
JOIN outcomes_assessment a ON a.id = g.assessment_id
WHERE a.offering_id = (SELECT id FROM catalog_courseoffering ORDER BY id LIMIT 1);

-- 3. "All grades of one student" uses grade_enrollment_idx
EXPLAIN ANALYZE
SELECT * FROM grading_grade
WHERE enrollment_id IN (SELECT id FROM catalog_enrollment
                        WHERE student_id = (SELECT id FROM accounts_user WHERE student_number = '2023-0001'));

-- 4. The CHECK constraints are really in the database, not only in Django
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname IN ('lo_po_weight_range', 'a_lo_weight_range', 'score_non_negative', 'term_dates_ordered');

-- 5. A violated constraint, live (good for the slide): this must fail
INSERT INTO outcomes_lopoweight (learning_outcome_id, program_outcome_id, weight, source, rationale)
SELECT lo.id, po.id, 6, 'manual', '' FROM outcomes_learningoutcome lo, catalog_programoutcome po LIMIT 1;
```

Save each output into `docs/reports/cse321-checkpoint/explain/0N-<name>.txt`. **How to read a plan in one sentence:** "Index Scan using uniq_grade" means Postgres jumped straight to the rows through the index, while "Seq Scan" means it read the whole table. On tables this small, Postgres sometimes prefers a Seq Scan because it really is cheaper. If that happens, run `SET enable_seqscan = off;` before the `EXPLAIN` to show the index *can* be used, and say exactly that on the slide. Hiding it would be worse.

**4. Report.** The 4–6 pages, in Markdown, exported to PDF with the same pipeline as the final report: `brew install pandoc` once, then `uv run pandoc report.md -o ../cse321-checkpoint.pdf --pdf-engine=weasyprint` from the report folder. WeasyPrint is already a project dependency, so `uv run` puts it on the PATH. Headings follow §13.1:

```markdown
# POlaris — CSE 321 Checkpoint: Data & System Architecture
Team: <names> · Repo: https://github.com/OnurHaniffa/polaris · 12 Nov 2026

## 1 Introduction
<punchline from spec §1.2; the scoring chain in three sentences; Elif's example with numbers>

## 2 System design
<architecture.png> <one paragraph per component from spec §4.1: why Postgres, why Redis, why a worker>
<classes.png> <two paragraphs: the five apps and what each owns (spec §4.3)>

## 3 Data model
<er.png>
- Tables and keys (from spec §5.2), normalisation argument: every non-key column depends on the key,
  the whole key and nothing but the key; the two weight tables are the associative entities of two M:N relationships.
- Integrity: the constraint list from step 3 query 4, plus the partial unique index.
- Rules the database can't express (spec §5.3) and where they are enforced.

## 4 Transactions (planned in detail, partly built)
<spec §5.6 table, 3 sentences on why READ COMMITTED + row locks is enough for writes>

## 5 Reporting and scale (planned)
<star schema sentence from spec §5.5; partitioning arithmetic from §5.6>

## 6 Fault tolerance (planned)
<retries, idempotent tasks, health checks, nightly pg_dump — two or three sentences>
```

**5. Rehearsal runbook.** Rehearsals are the cheapest quality you can buy for a presentation.

| Step | Check |
|---|---|
| Timer on a phone, visible to everyone | Total ≤ 10:00. Over 10:30? Cut slide 3 to one line per question |
| Live demo on **production**, not staging | Log in as the instructor persona beforehand in a private window; second window logged in as Elif |
| Fallback | The Sprint 3 baseline video is open in a background tab, muted, at 0:00 |
| Each speaker ends with a handover sentence | "…and that's why we need row locks. B will show you it running." |
| Likely questions, one answer each | Why not SQLite? (D7: concurrency + partial indexes + the course is about Postgres.) Why our own audit table? (D10.) Why no partitioning? (the §5.6 arithmetic) |

### Tests

None (document story). Definition of Done for this story is: presented, both PDFs committed, retro note written.

### Check it works

Open `docs/reports/cse321-checkpoint.pdf`. It is 4–6 pages, has no title page (same rule as the final report), every figure is readable when printed, and every claim about an index has the matching `explain/*.txt` file.

### Done when

- [ ] Presented on Thu 12 Nov, everyone spoke
- [ ] `slides.pdf`, `report.md`, `explain/*.txt` and `cse321-checkpoint.pdf` committed
- [ ] Two questions the audience asked, and our answers, written into `docs/process/sprint-04/retro.md`

### Commits and PR

```
Add CSE 321 checkpoint report source and EXPLAIN outputs
Add checkpoint slides and final PDF
```

PR title: **CSE 321 checkpoint deliverables (S4-02)**

---

## S4-03 · Bulk grade upload: dry run, confirm, golden-file tests

**Points:** 5 · **Owner:** Person B · **Branch:** `feature/S4-03-bulk-upload` · **Depends on:** S2-06 (grade sheet, `parse_score_input`), S3-08 (spike), S1-04 (`Grade`, audit)

### Goal

An instructor uploads the gradebook they already keep in Excel and gets four steps: **upload → match columns → check → confirm**. Nothing is written before Confirm, and nothing is ever *published* by an upload: uploaded grades are drafts, exactly as if typed into the sheet. This delivers spec T1.1 and its four acceptance criteria:

1. Golden-file reports for one clean and one messy sample.
2. No writes before Confirm and no publishing.
3. Re-uploading the same file is a no-op.
4. 200 rows in under 2 seconds.

The S3-08 spike tried out parsing. This story turns it into `apps/grading/upload.py` (below, in full; replace the spike version), adds the three screens, and pins the behaviour with golden files.

### How the pieces fit

```
upload view ──► services.start_grade_upload ──► upload.read_table + upload.guess_mapping
                     │ IngestionJob(kind=GRADES, status=PENDING, result={rows, mapping})
map view ─────► services.set_upload_mapping ──► upload.dry_run ──► plan()  (pure)
                     │ status=READY, result.report
preview view ─► shows result.report (nothing written yet)
confirm view ─► services.apply_grade_upload ──► dry_run again (fresh) ──► one transaction:
                     bulk_create / bulk_update drafts + one audit event per changed grade ──► APPLIED
```

**Why `plan()` is a pure function.** `dry_run` does three reads (assessments, enrolled students, existing grades), turns them into plain dataclasses (`UploadContext`), and hands them to `plan`. All the judgment lives in `plan`: duplicates, unknown students, bad values, create vs update vs unchanged. Because `plan` never touches the database, the same rows and the same context always give the same report, byte for byte. That's what makes a **golden-file test** possible: we store the expected report as JSON next to the sample file, and any change in behaviour shows up as a readable diff in the PR.

**Why confirm runs the dry run again.** The preview might be minutes old. If the instructor typed a grade into the sheet meanwhile, replaying the old plan would overwrite it with a stale "old → new". Re-planning inside the transaction, with the grade rows locked, means we write exactly what is different *now*.

**Why the job table.** We need the rows somewhere between steps, and session storage is a bad home for 5,000 rows. `IngestionJob(kind=GRADES)` already exists (§5.2) and gives traceability for free (T1.1 step 5): the file, who uploaded it, the report, and what was applied.

| Job status | Meaning for a grade upload |
|---|---|
| `pending` | File read, mapping guessed, not confirmed yet |
| `ready` | Mapping confirmed, dry-run report stored |
| `applied` | Confirmed; `result.applied` has the counts |

### Files

| Path | Create/modify | What |
|---|---|---|
| `apps/grading/upload.py` | create (replaces spike) | Reading, matching, parsing, `plan`, `dry_run`, report dataclasses |
| `apps/grading/services.py` | modify | `start_grade_upload`, `set_upload_mapping`, `apply_grade_upload`, `UploadResult` |
| `apps/grading/forms.py` | modify | `GradeUploadForm`, `ColumnMappingForm` |
| `apps/grading/views.py` | modify | `upload`, `upload_map`, `upload_preview`, `upload_confirm` |
| `apps/grading/urls.py` | modify | Four paths |
| `apps/grading/templates/grading/upload.html`, `upload_map.html`, `upload_preview.html` | create | The screens |
| `apps/grading/templates/grading/sheet.html` | modify | "Upload grades" button |
| `seed/grades/clean.csv` | create | Clean sample |
| `seed/grades/make_messy.py` → `messy.csv`, `messy.xlsx` | create | Messy samples in real Turkish-Excel encoding |
| `seed/grades/expected/clean.json`, `messy.json` | create | Golden reports |
| `apps/grading/tests/conftest.py`, `golden.py`, `test_upload_unit.py`, `test_upload_golden.py`, `test_upload_service.py`, `test_upload_views.py` | create | Tests |
| `apps/accounts/tests/test_permission_matrix.py` | modify | Four new URLs |

### Steps

**1. The sample files.** Write them first: they're the specification in miniature. The clean file is what a tidy instructor exports:

```csv
Student No,Name,Midterm I,Project,Quiz 1
2026-0001,Elif Yıldız,90,80,18
2026-0002,Ahmet Kaya,75.5,88,15
2026-0003,Zeynep Arslan,62,70,EX
2026-0004,Mert Çelik,48,55,9.5
2026-0005,Selin Koç,100,92,20
2026-0006,Burak Öztürk,81,,12
```

The messy file contains **every** problem from T1.1 step 3, plus the things that should *not* be problems:

| Row | Student | What it tests |
|---|---|---|
| 2 | 2026-0001 | Midterm 90 = existing draft 90 → **unchanged**; Project 80 vs existing 75 → **update**; Quiz → **create** |
| 3 | 2026-0002 | `85,5` Turkish decimal comma → 85.5; Quiz 15 = existing → **unchanged**; a note in an unmapped column (ignored) |
| 4 | 2026-0003 | `M` (muaf) → **excused**; `-5` → **negative**; `abc` → **not a number** |
| 5 | 2026-0004 | `105` above max 100 → **above_max**; `9,5` on a quiz out of 20 → fine |
| 6, 7 | 2026-0005 | Same student twice → **duplicate**, both rows blocked |
| 8 | (blank) | Fully empty row → ignored silently |
| 9 | 2026-9999 | Not enrolled → **warning**, row skipped |
| — | 2026-0006 | Enrolled but not in the file → listed as **missing**, grades left alone |

Headers are deliberately sloppy: `Öğrenci No`, `MIDTERM 1`, `Proje`, `quiz-1`, plus a `Notlar` column that matches nothing. The file must be **Windows-1254 with semicolons**, because that's what Excel on a Turkish-locale Windows machine writes. A text editor would quietly save it as UTF-8, so a script writes it, along with the `.xlsx` twin:

```python
"""Writes seed/grades/messy.csv (Windows-1254, semicolons) and messy.xlsx from the same rows.

Run once with `uv run python seed/grades/make_messy.py` and commit the outputs. The rows are
written here instead of by hand because a text editor would silently save the CSV as UTF-8,
and the point of this file is to be what Turkish Excel actually produces."""
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

ROWS = [
    ["Öğrenci No", "Ad Soyad", "MIDTERM 1", "Proje", "quiz-1", "Notlar"],
    ["2026-0001", "Elif Yıldız", "90", "80", "18", ""],
    ["2026-0002", "Ahmet Kaya", "85,5", "88", "15", "geç teslim"],
    ["2026-0003", "Zeynep Arslan", "M", "-5", "abc", ""],
    ["2026-0004", "Mert Çelik", "105", "55", "9,5", ""],
    ["2026-0005", "Selin Koç", "100", "92", "20", ""],
    ["2026-0005", "Selin Koç", "100", "92", "20", "tekrar"],
    ["", "", "", "", "", ""],
    ["2026-9999", "Hayalet Öğrenci", "70", "70", "10", ""],
]


def as_excel_value(text: str):
    """What Excel would store: numbers as numbers (85,5 typed in Turkish Excel is the number 85.5)."""
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text or None
    return int(number) if number.is_integer() else number


def main() -> None:
    lines = [";".join(row) for row in ROWS]
    (HERE / "messy.csv").write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1254"))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Notlar"
    for row in ROWS:
        values = [row[0], row[1], *(as_excel_value(v) for v in row[2:5]), row[5] or None]
        sheet.append(values)
    workbook.save(HERE / "messy.xlsx")


if __name__ == "__main__":
    main()
```

```bash
uv run python seed/grades/make_messy.py
file seed/grades/messy.csv      # → "ISO-8859 text, with CRLF line terminators"  (cp1254 looks like this to `file`)
```

**2. `apps/grading/upload.py`.** Read the docstrings: each one says *why*, not just what. Three decisions worth defending at the demo:

- **Encoding detection** tries UTF-8 first (with or without the BOM Excel adds), then Windows-1254. The order matters. Windows-1254 can decode *any* byte sequence, so trying it first would turn every UTF-8 "ö" into "Ã¶" without an error.
- **The separator** is whichever of `;`, `,` or tab appears most in the header line. `csv.Sniffer` exists, but it guesses wrong on short files with decimal commas.
- **Matching columns**: an exact match after normalising (case, Turkish letters, punctuation), then `difflib` similarity ≥ 0.75 for the rest. Fuzzy matches get a "Best guess, please check" badge. `MIDTERM 1` vs `Midterm I` scores 0.89 and `Proje` vs `Project` 0.83, while `Notlar` scores far below any assessment name. The student-number column is found from header words *and* from values that look like `2026-0001`. "No" is checked as a whole word, so a column called "Notes" doesn't match.

```python
"""Read gradebook files and work out what an upload would change (T1.1).

Nothing in this module writes to the database. `dry_run` reads the offering once, then
hands plain data to `plan`, which is a pure function: same rows + same mapping + same
context always give the same report. That's what makes the golden-file tests possible.
"""
from __future__ import annotations

import csv
import difflib
import io
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence

from django.core.exceptions import ValidationError

from .models import Grade

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
EXCUSED_TOKENS = {"ex", "m", "muaf", "excused", "mazeretli"}
STUDENT_HEADER_TOKENS = {"student", "ogrenci", "no", "number", "numara", "numarasi", "id", "sid"}
STUDENT_NUMBER_RE = re.compile(r"^\d{4}-\d{4}$|^\d{6,12}$")
FUZZY_CUTOFF = 0.75
TWO_PLACES = Decimal("0.01")


# ---------- reading files ----------

def read_table(file) -> list[list[str]]:
    """Return the file as rows of stripped strings, header first, all rows the same width.

    Accepts CSV (UTF-8, UTF-8 with BOM, or Windows-1254 as written by Turkish Excel; comma,
    semicolon or tab separated) and XLSX (first sheet only). Raises ValidationError with a
    message the instructor can act on."""
    file.seek(0)
    data = file.read()
    if isinstance(data, str):
        data = data.encode("utf-8")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError("The file is larger than 5 MB. Remove extra sheets or columns and try again.")
    if data[:4] == b"PK\x03\x04":
        rows = _read_xlsx(data)
    elif b"\x00" in data[:4096]:
        raise ValidationError("This file isn't a CSV or Excel (.xlsx) file.")
    else:
        rows = _read_csv(_decode(data))

    rows = [[_clean(cell) for cell in row] for row in rows]
    while rows and not any(rows[-1]):
        rows.pop()
    if len(rows) < 2:
        raise ValidationError("The file needs a header row and at least one student row.")
    if len(rows) - 1 > MAX_ROWS:
        raise ValidationError(f"The file has more than {MAX_ROWS} rows.")
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def _decode(data: bytes) -> str:
    # utf-8-sig also reads plain UTF-8; it just drops a BOM if Excel wrote one.
    # cp1254 (Turkish Windows) can decode any byte, so it must be the last resort.
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("We couldn't read the text in this file. Save it as CSV UTF-8 and try again.")


def _read_csv(text: str) -> list[list[str]]:
    first_line = text.split("\n", 1)[0]
    # Turkish Excel writes ";" because "," is the decimal separator. Pick whichever
    # separator appears most often in the header line.
    delimiter = max((";", ",", "\t"), key=first_line.count)
    if first_line.count(delimiter) == 0:
        delimiter = ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _read_xlsx(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
        raise ValidationError("This Excel file couldn't be opened. Save it again as .xlsx.") from exc
    try:
        sheet = workbook.worksheets[0]
        return [[_cell_to_str(value) for value in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))           # Excel stores 90 as 90.0
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean(cell: str) -> str:
    return cell.replace(" ", " ").strip()


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA. Used for cell references like C14."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


# ---------- matching columns ----------

def normalise(text: str) -> str:
    """'  Öğrenci  No.' -> 'ogrenci no'. Case-, accent- and punctuation-insensitive."""
    text = text.replace("İ", "i").replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^0-9a-z]+", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class ColumnMapping:
    student_col: int | None
    assessment_cols: dict[int, int] = field(default_factory=dict)   # column index -> assessment id
    fuzzy_cols: frozenset[int] = frozenset()                         # matched by similarity, not exactly

    def to_dict(self) -> dict:
        return {
            "student_col": self.student_col,
            "assessment_cols": {str(col): aid for col, aid in sorted(self.assessment_cols.items())},
            "fuzzy_cols": sorted(self.fuzzy_cols),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ColumnMapping:
        return cls(
            student_col=data["student_col"],
            assessment_cols={int(col): aid for col, aid in data["assessment_cols"].items()},
            fuzzy_cols=frozenset(data.get("fuzzy_cols", [])),
        )


def guess_mapping(header: Sequence[str], assessments: Iterable, sample_rows: Sequence[Sequence[str]] = ()) -> ColumnMapping:
    """First guess at which column is which. The instructor confirms it on the next screen.

    Student-number column: header words like "no", "öğrenci", "student" (+1 point) plus the share
    of sample values that look like student numbers (up to +1). Best column scoring ≥ 0.8 wins.
    Assessment columns: exact match after `normalise`, then the closest name with difflib
    (similarity ≥ 0.75). Each assessment is used at most once."""
    scores = []
    for col, title in enumerate(header):
        header_hit = 1.0 if set(normalise(title).split()) & STUDENT_HEADER_TOKENS else 0.0
        values = [row[col] for row in sample_rows if col < len(row) and row[col]]
        value_hit = sum(bool(STUDENT_NUMBER_RE.match(v)) for v in values) / len(values) if values else 0.0
        scores.append((header_hit + value_hit, col))
    best_score, best_col = max(scores, default=(0.0, None))
    student_col = best_col if best_score >= 0.8 else None

    by_name = {normalise(a.name): a.id for a in assessments}
    assessment_cols: dict[int, int] = {}
    fuzzy: set[int] = set()
    free_names = dict(by_name)
    candidates = [col for col in range(len(header)) if col != student_col and header[col]]

    for col in candidates:                                   # pass 1: exact
        name = normalise(header[col])
        if name in free_names:
            assessment_cols[col] = free_names.pop(name)
    for col in candidates:                                   # pass 2: closest remaining
        if col in assessment_cols:
            continue
        match = difflib.get_close_matches(normalise(header[col]), list(free_names), n=1, cutoff=FUZZY_CUTOFF)
        if match:
            assessment_cols[col] = free_names.pop(match[0])
            fuzzy.add(col)
    return ColumnMapping(student_col, assessment_cols, frozenset(fuzzy))


# ---------- parsing one cell ----------

class CellProblem(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def fmt(value: Decimal | None) -> str:
    """Decimal -> shortest plain string: 90.00 -> '90', 85.50 -> '85.5'. None -> ''."""
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    return text


def parse_cell(raw: str, max_score: Decimal, assessment_name: str) -> tuple[Decimal | None, bool]:
    """'85,5' -> (85.5, False); 'EX' / 'M' / 'muaf' / 'excused' -> (None, True).
    Raises CellProblem with a code: not_a_number, negative, above_max, too_precise."""
    if normalise(raw) in EXCUSED_TOKENS:
        return None, True
    text = raw.replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")                      # Turkish decimal comma
    try:
        value = Decimal(text)
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite():
        raise CellProblem("not_a_number",
                          f"“{raw}” is not a number. Use a number, EX for excused, or leave the cell empty.")
    if value < 0:
        raise CellProblem("negative", "Scores can't be negative.")
    if value > max_score:
        raise CellProblem("above_max", f"Max for {assessment_name} is {fmt(max_score)}.")
    if value != value.quantize(TWO_PLACES):
        raise CellProblem("too_precise", "Use at most two decimal places.")
    return value, False


# ---------- the dry-run report ----------

@dataclass(frozen=True)
class AssessmentInfo:
    id: int
    name: str
    max_score: Decimal


@dataclass(frozen=True)
class EnrollmentInfo:
    id: int
    student_number: str
    name: str


@dataclass(frozen=True)
class UploadContext:
    """Everything `plan` needs from the database, as plain data."""
    assessments: dict[int, AssessmentInfo]                          # id -> info
    enrollments: dict[str, EnrollmentInfo]                          # student number -> info
    grades: dict[tuple[int, int], tuple[Decimal | None, bool]]      # (assessment id, enrollment id) -> (score, excused)


@dataclass(frozen=True)
class GradeChange:
    cell: str
    student_number: str
    enrollment_id: int
    assessment_id: int
    assessment_name: str
    kind: str                     # "create" | "update" | "unchanged"
    old_score: Decimal | None
    old_excused: bool
    new_score: Decimal | None
    new_excused: bool


@dataclass(frozen=True)
class CellError:
    cell: str
    student_number: str
    assessment_name: str
    raw: str
    code: str
    message: str


@dataclass(frozen=True)
class RowIssue:
    rows: tuple[int, ...]
    student_number: str
    code: str                     # "duplicate" | "missing_student_number" (errors), "not_enrolled" (warning)
    message: str

    @property
    def is_error(self) -> bool:
        return self.code != "not_enrolled"


@dataclass(frozen=True)
class DryRunReport:
    changes: tuple[GradeChange, ...]
    cell_errors: tuple[CellError, ...]
    row_issues: tuple[RowIssue, ...]
    missing_students: tuple[str, ...]          # enrolled, but not in the file
    empty_cells: int

    @property
    def creates(self) -> list[GradeChange]:
        return [c for c in self.changes if c.kind == "create"]

    @property
    def updates(self) -> list[GradeChange]:
        return [c for c in self.changes if c.kind == "update"]

    @property
    def unchanged(self) -> list[GradeChange]:
        return [c for c in self.changes if c.kind == "unchanged"]

    @property
    def errors(self) -> list[RowIssue]:
        return [i for i in self.row_issues if i.is_error]

    @property
    def warnings(self) -> list[RowIssue]:
        return [i for i in self.row_issues if not i.is_error]

    @property
    def has_blocking_errors(self) -> bool:
        return bool(self.cell_errors or self.errors)

    def summary(self) -> dict[str, int]:
        return {
            "create": len(self.creates),
            "update": len(self.updates),
            "unchanged": len(self.unchanged),
            "excused": sum(c.new_excused for c in self.changes if c.kind != "unchanged"),
            "empty": self.empty_cells,
            "cell_errors": len(self.cell_errors),
            "row_errors": len(self.errors),
            "not_enrolled": len(self.warnings),
            "missing": len(self.missing_students),
        }

    def to_dict(self, *, include_ids: bool = True) -> dict:
        def change(c: GradeChange) -> dict:
            data = {
                "cell": c.cell, "student_number": c.student_number, "assessment": c.assessment_name,
                "kind": c.kind, "old": fmt(c.old_score), "old_excused": c.old_excused,
                "new": fmt(c.new_score), "new_excused": c.new_excused,
            }
            if include_ids:
                data |= {"enrollment_id": c.enrollment_id, "assessment_id": c.assessment_id}
            return data

        return {
            "summary": self.summary(),
            "changes": [change(c) for c in self.changes],
            "cell_errors": [asdict(e) for e in self.cell_errors],
            "row_issues": [{"rows": list(i.rows), "student_number": i.student_number,
                            "code": i.code, "message": i.message} for i in self.row_issues],
            "missing_students": list(self.missing_students),
            "empty_cells": self.empty_cells,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DryRunReport:
        """Rebuild a stored report (needs include_ids=True)."""
        def dec(text: str) -> Decimal | None:
            return Decimal(text) if text else None

        return cls(
            changes=tuple(GradeChange(
                cell=c["cell"], student_number=c["student_number"], enrollment_id=c["enrollment_id"],
                assessment_id=c["assessment_id"], assessment_name=c["assessment"], kind=c["kind"],
                old_score=dec(c["old"]), old_excused=c["old_excused"],
                new_score=dec(c["new"]), new_excused=c["new_excused"]) for c in data["changes"]),
            cell_errors=tuple(CellError(**e) for e in data["cell_errors"]),
            row_issues=tuple(RowIssue(rows=tuple(i["rows"]), student_number=i["student_number"],
                                      code=i["code"], message=i["message"]) for i in data["row_issues"]),
            missing_students=tuple(data["missing_students"]),
            empty_cells=data["empty_cells"],
        )


def load_context(offering) -> UploadContext:
    """Three queries: assessments, enrolled students, existing grades."""
    assessments = {a.id: AssessmentInfo(a.id, a.name, a.max_score) for a in offering.assessments.all()}
    enrollments = {
        e.student.student_number: EnrollmentInfo(e.id, e.student.student_number, e.student.get_full_name())
        for e in offering.enrollments.filter(status="enrolled").select_related("student")
        if e.student.student_number
    }
    grades = {
        (g.assessment_id, g.enrollment_id): (g.score, g.is_excused)
        for g in Grade.objects.filter(assessment__offering=offering).only(
            "assessment_id", "enrollment_id", "score", "is_excused")
    }
    return UploadContext(assessments, enrollments, grades)


def dry_run(rows: Sequence[Sequence[str]], mapping: ColumnMapping, offering) -> DryRunReport:
    """What would happen if this file were confirmed now. Reads, never writes."""
    return plan(rows, mapping, load_context(offering))


def plan(rows: Sequence[Sequence[str]], mapping: ColumnMapping, ctx: UploadContext) -> DryRunReport:
    if mapping.student_col is None:
        raise ValidationError("Choose the column that holds student numbers.")
    col = mapping.student_col
    body = list(enumerate(rows[1:], start=2))                    # spreadsheet row numbers: header is row 1

    # Pass 1: who appears where. Duplicates block both rows: we can't know which one is right.
    appearances: dict[str, list[int]] = {}
    issues: list[RowIssue] = []
    for number, row in body:
        if not any(row):
            continue
        student_number = row[col]
        if not student_number:
            issues.append(RowIssue((number,), "", "missing_student_number",
                                   f"Row {number} has values but no student number."))
            continue
        appearances.setdefault(student_number, []).append(number)
    duplicates = {sn for sn, where in appearances.items() if len(where) > 1}
    for sn in duplicates:
        where = appearances[sn]
        issues.append(RowIssue(tuple(where), sn, "duplicate",
                               f"Student {sn} appears on rows {', '.join(map(str, where))}. "
                               "Keep one row per student."))

    # Pass 2: every mapped cell of every usable row.
    changes: list[GradeChange] = []
    cell_errors: list[CellError] = []
    empty = 0
    columns = sorted(mapping.assessment_cols.items())
    for number, row in body:
        if not any(row):
            continue
        student_number = row[col]
        if not student_number or student_number in duplicates:
            continue
        enrollment = ctx.enrollments.get(student_number)
        if enrollment is None:
            issues.append(RowIssue((number,), student_number, "not_enrolled",
                                   f"{student_number} (row {number}) is not enrolled in this course. Row skipped."))
            continue
        for column, assessment_id in columns:
            assessment = ctx.assessments[assessment_id]
            raw = row[column]
            cell = f"{column_letter(column)}{number}"
            if not raw:
                empty += 1
                continue
            try:
                score, excused = parse_cell(raw, assessment.max_score, assessment.name)
            except CellProblem as problem:
                cell_errors.append(CellError(cell, student_number, assessment.name, raw,
                                             problem.code, problem.message))
                continue
            old_score, old_excused = ctx.grades.get((assessment_id, enrollment.id), (None, False))
            if old_score is None and not old_excused:
                kind = "create"
            elif (old_score, old_excused) == (score, excused):
                kind = "unchanged"
            else:
                kind = "update"
            changes.append(GradeChange(cell, student_number, enrollment.id, assessment_id, assessment.name,
                                       kind, old_score, old_excused, score, excused))

    missing = sorted(set(ctx.enrollments) - set(appearances))
    issues.sort(key=lambda issue: issue.rows[0])
    return DryRunReport(tuple(changes), tuple(cell_errors), tuple(issues), tuple(missing), empty)
```

> **Why not reuse `parse_score_input` from the grade sheet?** The sheet parses one value a person just typed, and its error goes into a cell tooltip. The uploader needs an error *code* for every cell (the golden files compare codes) and accepts more excused spellings (`M`, `muaf`). The rules are the same ones (decimal comma, never negative, never above max), and `test_upload_unit.py` pins them. If the two ever drift apart, make `parse_score_input` call `parse_cell` rather than the other way round.

**3. Services.** Three functions in `apps/grading/services.py`. All writes are in `apply_grade_upload`, inside one `transaction.atomic()`. Points to notice:

- `select_for_update()` on the **job** row: two clicks on Confirm (or two tabs) can't apply the same file twice. The second waits for the first, then sees `APPLIED` and stops.
- `select_for_update(of=("self",))` on the grade rows locks only `grading_grade` rows, not the joined assessments. Without `of=`, PostgreSQL would also lock the assessment rows, and a concurrent publish would wait for no reason.
- `bulk_update` doesn't run `auto_now`, so `updated_at` is set by hand. This is a classic Django trap (Part 15).
- One audit event per changed grade (spec §5.3) plus one summary event for the whole upload.

```python
# apps/grading/services.py  — add these imports at the top of the file
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.catalog.services import ensure_term_open
from apps.core.audit import record, snapshot
from apps.ingestion.models import IngestionJob

from . import upload
from .models import Grade


# … existing functions (parse_score_input, save_grade, publish_assessment, unpublish_assessment) stay as they are …


@dataclass(frozen=True)
class UploadResult:
    created: int
    updated: int
    unchanged: int
    skipped_cells: int
    skipped_rows: int


def start_grade_upload(user, offering, uploaded_file) -> IngestionJob:
    """Read the file, guess the column mapping, and store both on a new job. No grades touched."""
    ensure_term_open(offering)
    rows = upload.read_table(uploaded_file)                      # raises ValidationError on bad files
    mapping = upload.guess_mapping(rows[0], list(offering.assessments.all()), sample_rows=rows[1:51])

    original_name = Path(uploaded_file.name).name[:255]
    uploaded_file.seek(0)
    uploaded_file.name = f"{uuid4().hex}{Path(original_name).suffix.lower()}"   # random name on disk (§7.8)
    job = IngestionJob.objects.create(
        offering=offering, kind=IngestionJob.Kind.GRADES, file=uploaded_file,
        original_filename=original_name, status=IngestionJob.Status.PENDING, created_by=user,
        result={"rows": rows, "mapping": mapping.to_dict()},
    )
    record(user, "grade_upload.start", job, after={"file": original_name, "rows": len(rows) - 1},
           offering=offering)
    return job


def set_upload_mapping(user, job, mapping: upload.ColumnMapping) -> upload.DryRunReport:
    """Store the instructor's confirmed mapping and the dry-run report it produces."""
    if job.status == IngestionJob.Status.APPLIED:
        raise ValidationError("This upload was already applied.")
    ensure_term_open(job.offering)
    report = upload.dry_run(job.result["rows"], mapping, job.offering)
    job.result = {**job.result, "mapping": mapping.to_dict(), "report": report.to_dict()}
    job.status = IngestionJob.Status.READY
    job.save(update_fields=["result", "status", "updated_at"])
    return report


@transaction.atomic
def apply_grade_upload(user, job, *, skip_invalid: bool = False) -> UploadResult:
    """Write every valid cell as a DRAFT grade, in one transaction. Never publishes (T1.1 AC 2)."""
    job = IngestionJob.objects.select_for_update().select_related("offering__term").get(pk=job.pk)
    if job.kind != IngestionJob.Kind.GRADES:
        raise ValueError(f"Job {job.pk} is not a grade upload")
    if job.status == IngestionJob.Status.APPLIED:
        raise ValidationError("This upload was already applied.")
    if job.status != IngestionJob.Status.READY:
        raise ValidationError("Check the column mapping before confirming.")
    offering = job.offering
    ensure_term_open(offering)

    # Re-plan against the database as it is *now*. Someone may have typed grades in the sheet
    # between the preview and this click; the fresh plan never overwrites their change blindly.
    mapping = upload.ColumnMapping.from_dict(job.result["mapping"])
    report = upload.dry_run(job.result["rows"], mapping, offering)
    if report.has_blocking_errors and not skip_invalid:
        raise ValidationError("The file still has errors. Fix them, or tick “skip invalid rows”.")

    to_write = [change for change in report.changes if change.kind != "unchanged"]
    existing = {
        (g.assessment_id, g.enrollment_id): g
        for g in Grade.objects.select_for_update(of=("self",)).filter(
            assessment__offering=offering,
            enrollment_id__in={c.enrollment_id for c in to_write},
        )
    }
    now = timezone.now()
    new_grades: list[Grade] = []
    changed: list[tuple[Grade, dict | None]] = []
    for change in to_write:
        grade = existing.get((change.assessment_id, change.enrollment_id))
        if grade is None:
            grade = Grade(assessment_id=change.assessment_id, enrollment_id=change.enrollment_id,
                          score=change.new_score, is_excused=change.new_excused, updated_by=user)
            new_grades.append(grade)
            changed.append((grade, None))
        else:
            before = snapshot(grade, ["score", "is_excused"])
            grade.score, grade.is_excused = change.new_score, change.new_excused
            grade.updated_by, grade.updated_at = user, now       # bulk_update skips auto_now: set it by hand
            changed.append((grade, before))

    Grade.objects.bulk_create(new_grades)                        # PostgreSQL returns the new primary keys
    Grade.objects.bulk_update([g for g, before in changed if before is not None],
                              ["score", "is_excused", "updated_by", "updated_at"])
    for grade, before in changed:
        record(user, "grade.update" if before else "grade.create", grade, before=before,
               after=snapshot(grade, ["score", "is_excused"]) | {"via": "upload", "job": job.pk},
               offering=offering)

    result = UploadResult(
        created=sum(1 for _, before in changed if before is None),
        updated=sum(1 for _, before in changed if before is not None),
        unchanged=len(report.unchanged),
        skipped_cells=len(report.cell_errors),
        skipped_rows=sum(len(issue.rows) for issue in report.row_issues),
    )
    job.status = IngestionJob.Status.APPLIED
    job.applied_at = now
    job.result = {**job.result, "report": report.to_dict(), "applied": vars(result)}
    job.save(update_fields=["status", "applied_at", "result", "updated_at"])
    record(user, "grade_upload.apply", job, after=vars(result), offering=offering)
    return result
```

**4. Forms.** `ColumnMappingForm` builds one dropdown per column of *this* file at runtime, which is why it's a plain `Form` with fields added in `__init__`.

```python
# apps/grading/forms.py  — add below the existing forms
from pathlib import Path

from django import forms

from .upload import MAX_UPLOAD_BYTES, ColumnMapping, column_letter

STUDENT = "student"


class GradeUploadForm(forms.Form):
    file = forms.FileField(
        label="Gradebook file",
        help_text="CSV or Excel (.xlsx), up to 5 MB. First row = column names, one row per student.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,.xlsx"}),
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if Path(file.name).suffix.lower() not in {".csv", ".xlsx"}:
            raise forms.ValidationError("Upload a .csv or .xlsx file. Old .xls files: open and “Save as” .xlsx.")
        if file.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file is larger than 5 MB.")
        return file                   # content is checked properly by upload.read_table


class ColumnMappingForm(forms.Form):
    """One dropdown per file column: ignore it, it's the student number, or it's assessment X."""

    def __init__(self, *args, header, assessments, mapping: ColumnMapping | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.header = list(header)
        self.assessment_ids = {a.id for a in assessments}
        choices = [("", "— ignore this column —"), (STUDENT, "Student number")]
        choices += [(str(a.id), f"{a.name} (max {a.max_score.normalize():f})") for a in assessments]
        for index, title in enumerate(self.header):
            initial = ""
            if mapping is not None:
                if mapping.student_col == index:
                    initial = STUDENT
                elif index in mapping.assessment_cols:
                    initial = str(mapping.assessment_cols[index])
            self.fields[f"col_{index}"] = forms.ChoiceField(
                label=title or f"Column {column_letter(index)}", choices=choices,
                required=False, initial=initial,
            )

    def clean(self):
        cleaned = super().clean()
        values = [cleaned.get(f"col_{i}", "") for i in range(len(self.header))]
        if values.count(STUDENT) != 1:
            raise forms.ValidationError("Choose exactly one column as “Student number”.")
        chosen = [v for v in values if v not in ("", STUDENT)]
        if len(chosen) != len(set(chosen)):
            raise forms.ValidationError("Each assessment can be matched to one column only.")
        if not chosen:
            raise forms.ValidationError("Match at least one column to an assessment.")
        if any(int(v) not in self.assessment_ids for v in chosen):
            raise forms.ValidationError("That assessment no longer exists. Reload the page.")
        return cleaned

    def to_mapping(self, previous: ColumnMapping | None = None) -> ColumnMapping:
        student_col = None
        assessment_cols: dict[int, int] = {}
        for index in range(len(self.header)):
            value = self.cleaned_data.get(f"col_{index}", "")
            if value == STUDENT:
                student_col = index
            elif value:
                assessment_cols[index] = int(value)
        fuzzy = frozenset()
        if previous is not None:       # keep the "guessed" marker only where the instructor kept our guess
            fuzzy = frozenset(c for c in previous.fuzzy_cols
                              if previous.assessment_cols.get(c) == assessment_cols.get(c))
        return ColumnMapping(student_col, assessment_cols, fuzzy)

    def columns(self, rows):
        """(bound field, letter, first three non-empty values) per column, for the template."""
        for index in range(len(self.header)):
            samples = [row[index] for row in rows[1:] if row[index]][:3]
            yield self[f"col_{index}"], column_letter(index), samples
```

**5. Views.** Thin, as §4.4 requires. Each loads the job **through the offering** (`_grade_job`), so a job id from another course gives 404 even for an instructor who teaches both. `@require_POST` sits innermost so the permission check runs first: a student sending GET to confirm gets 404, not 405, and doesn't learn the URL exists.

```python
# apps/grading/views.py  — add these imports and views
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access
from apps.ingestion.models import IngestionJob

from . import services
from .forms import ColumnMappingForm, GradeUploadForm
from .upload import ColumnMapping, DryRunReport


def _grade_job(offering, job_id):
    """A grade-upload job of THIS offering, or 404 (never another course's job)."""
    return get_object_or_404(IngestionJob, pk=job_id, offering=offering, kind=IngestionJob.Kind.GRADES)


@login_required
@require_offering_access(edit=True)
def upload(request, offering, perms_for, **kwargs):
    form = GradeUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            job = services.start_grade_upload(request.user, offering, form.cleaned_data["file"])
        except ValidationError as exc:
            form.add_error("file", exc)
        else:
            return redirect("grading:upload_map", offering_id=offering.pk, job_id=job.pk)
    recent = offering.ingestion_jobs.filter(kind=IngestionJob.Kind.GRADES).select_related("created_by")[:5]
    return render(request, "grading/upload.html",
                  {"offering": offering, "perms_for": perms_for, "form": form, "recent": recent})


@login_required
@require_offering_access(edit=True)
def upload_map(request, offering, perms_for, job_id, **kwargs):
    job = _grade_job(offering, job_id)
    if job.status == IngestionJob.Status.APPLIED:
        return redirect("grading:upload_preview", offering_id=offering.pk, job_id=job.pk)
    rows = job.result["rows"]
    guessed = ColumnMapping.from_dict(job.result["mapping"])
    form = ColumnMappingForm(request.POST or None, header=rows[0],
                             assessments=list(offering.assessments.all()), mapping=guessed)
    if request.method == "POST" and form.is_valid():
        try:
            services.set_upload_mapping(request.user, job, form.to_mapping(previous=guessed))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("grading:upload_preview", offering_id=offering.pk, job_id=job.pk)
    return render(request, "grading/upload_map.html", {
        "offering": offering, "perms_for": perms_for, "job": job, "form": form,
        "columns": list(form.columns(rows)), "fuzzy_cols": guessed.fuzzy_cols, "row_count": len(rows) - 1,
    })


@login_required
@require_offering_access(edit=True)
def upload_preview(request, offering, perms_for, job_id, **kwargs):
    job = _grade_job(offering, job_id)
    if "report" not in (job.result or {}):
        return redirect("grading:upload_map", offering_id=offering.pk, job_id=job.pk)
    report = DryRunReport.from_dict(job.result["report"])
    return render(request, "grading/upload_preview.html", {
        "offering": offering, "perms_for": perms_for, "job": job, "report": report,
        "summary": report.summary(), "applied": job.result.get("applied"),
        "visible_changes": [c for c in report.changes if c.kind != "unchanged"][:300],
    })


@login_required
@require_offering_access(edit=True)
@require_POST
def upload_confirm(request, offering, perms_for, job_id, **kwargs):
    job = _grade_job(offering, job_id)
    try:
        result = services.apply_grade_upload(request.user, job,
                                             skip_invalid=request.POST.get("skip_invalid") == "on")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("grading:upload_preview", offering_id=offering.pk, job_id=job.pk)
    messages.success(request, (
        f"Saved {result.created} new and {result.updated} changed draft grades from "
        f"{job.original_filename}. Nothing is published yet: publish each assessment when you're ready."))
    return redirect("grading:sheet", offering_id=offering.pk)
```

```python
# apps/grading/urls.py  — add to urlpatterns (app_name = "grading" is already set)
path("offerings/<int:offering_id>/grades/upload/", views.upload, name="upload"),
path("offerings/<int:offering_id>/grades/upload/<int:job_id>/map/", views.upload_map, name="upload_map"),
path("offerings/<int:offering_id>/grades/upload/<int:job_id>/preview/", views.upload_preview, name="upload_preview"),
path("offerings/<int:offering_id>/grades/upload/<int:job_id>/confirm/", views.upload_confirm, name="upload_confirm"),
```

Use the same prefix style as the existing paths in the file. If `config/urls.py` includes `apps.grading.urls` under `offerings/<int:offering_id>/`, drop that prefix here.

**6. Templates.** Plain Bootstrap with no HTMX: each step is a normal page and a normal form, so the back button and a page refresh both behave as the instructor expects. Every coloured state also has an icon and text (§8.2, accessibility).

`apps/grading/templates/grading/upload.html`:

```django
{% extends "base.html" %}
{% block title %}Upload grades · {{ offering.course.code }}{% endblock %}
{% block content %}
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'catalog:offering' offering_id=offering.pk %}">{{ offering.course.code }}</a></li>
    <li class="breadcrumb-item"><a href="{% url 'grading:sheet' offering_id=offering.pk %}">Grades</a></li>
    <li class="breadcrumb-item active" aria-current="page">Upload</li>
  </ol>
</nav>

<h1 class="h3">Upload a gradebook</h1>
<ol class="list-inline text-body-secondary small mb-4" aria-label="Steps">
  <li class="list-inline-item fw-semibold text-body">1. Upload</li>
  <li class="list-inline-item">→ 2. Match columns</li>
  <li class="list-inline-item">→ 3. Check</li>
  <li class="list-inline-item">→ 4. Confirm</li>
</ol>

<div class="row g-4">
  <div class="col-lg-6">
    <form method="post" enctype="multipart/form-data" class="card card-body">
      {% csrf_token %}
      <div class="mb-3">
        <label for="{{ form.file.id_for_label }}" class="form-label">{{ form.file.label }}</label>
        <input type="file" name="{{ form.file.html_name }}" id="{{ form.file.id_for_label }}"
               class="form-control{% if form.file.errors %} is-invalid{% endif %}" accept=".csv,.xlsx" required>
        <div class="form-text">{{ form.file.help_text }}</div>
        {% for error in form.file.errors %}<div class="invalid-feedback">{{ error }}</div>{% endfor %}
      </div>
      <button class="btn btn-primary">Upload and continue</button>
      <p class="small text-body-secondary mt-3 mb-0">
        Nothing is saved until you confirm on step 4, and nothing is ever published by an upload.
      </p>
    </form>
  </div>
  <div class="col-lg-6">
    <div class="card card-body">
      <h2 class="h6">What the file should look like</h2>
      <table class="table table-sm small mb-2">
        <thead><tr><th>Student No</th><th>Name</th><th>Midterm I</th><th>Project</th></tr></thead>
        <tbody>
          <tr><td>2026-0001</td><td>Elif Yıldız</td><td>90</td><td>80</td></tr>
          <tr><td>2026-0002</td><td>Ahmet Kaya</td><td>85,5</td><td>EX</td></tr>
        </tbody>
      </table>
      <ul class="small mb-0">
        <li>Column names don't have to match exactly. You'll confirm the matches next.</li>
        <li>Decimal commas (<code>85,5</code>) are fine. <code>EX</code>, <code>M</code> or <code>muaf</code> = excused.</li>
        <li>An empty cell leaves that grade as it is.</li>
      </ul>
    </div>
    {% if recent %}
    <h2 class="h6 mt-4">Recent uploads</h2>
    <ul class="list-group list-group-flush small">
      {% for job in recent %}
      <li class="list-group-item d-flex justify-content-between">
        <a href="{% url 'grading:upload_preview' offering_id=offering.pk job_id=job.pk %}">{{ job.original_filename }}</a>
        <span>{{ job.get_status_display }} · {{ job.created_at|date:"j M H:i" }} · {{ job.created_by.get_full_name }}</span>
      </li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
</div>
{% endblock %}
```

`apps/grading/templates/grading/upload_map.html`:

```django
{% extends "base.html" %}
{% block title %}Match columns · {{ offering.course.code }}{% endblock %}
{% block content %}
<h1 class="h3">Match the columns</h1>
<p class="text-body-secondary">
  <strong>{{ job.original_filename }}</strong> has {{ row_count }} row{{ row_count|pluralize }}.
  We guessed what each column holds. Check every dropdown, then continue. Still nothing is saved.
</p>

<form method="post">
  {% csrf_token %}
  {% if form.non_field_errors %}
    <div class="alert alert-danger" role="alert">{% for e in form.non_field_errors %}{{ e }} {% endfor %}</div>
  {% endif %}
  <div class="table-responsive">
    <table class="table align-middle">
      <thead>
        <tr><th scope="col">Column</th><th scope="col">Name in the file</th><th scope="col">First values</th><th scope="col">Means</th></tr>
      </thead>
      <tbody>
        {% for field, letter, samples in columns %}
        <tr>
          <td class="font-monospace">{{ letter }}</td>
          <td><label for="{{ field.id_for_label }}">{{ field.label }}</label></td>
          <td class="small text-body-secondary">{{ samples|join:", "|default:"(empty)" }}</td>
          <td>
            <select name="{{ field.html_name }}" id="{{ field.id_for_label }}" class="form-select form-select-sm">
              {% for value, text in field.field.choices %}
                <option value="{{ value }}"{% if field.value|stringformat:"s" == value|stringformat:"s" %} selected{% endif %}>{{ text }}</option>
              {% endfor %}
            </select>
            {% if forloop.counter0 in fuzzy_cols %}
              <span class="badge text-bg-warning mt-1">Best guess, please check</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="d-flex gap-2">
    <button class="btn btn-primary">Check the file</button>
    <a class="btn btn-outline-secondary" href="{% url 'grading:upload' offering_id=offering.pk %}">Upload a different file</a>
  </div>
</form>
{% endblock %}
```

`apps/grading/templates/grading/upload_preview.html`:

```django
{% extends "base.html" %}
{% load polaris %}
{% block title %}Check upload · {{ offering.course.code }}{% endblock %}
{% block content %}
<h1 class="h3">Check before saving</h1>
<p class="text-body-secondary">{{ job.original_filename }} · nothing has been saved yet.</p>

{% if applied %}
  <div class="alert alert-success" role="status">
    Applied {{ job.applied_at|date:"j M Y H:i" }}: {{ applied.created }} created, {{ applied.updated }} changed.
  </div>
{% endif %}

<div class="row row-cols-2 row-cols-md-4 g-3 mb-4">
  <div class="col"><div class="card card-body text-center">
    <div class="fs-3">✅ {{ summary.create }}</div><div class="small">grade{{ summary.create|pluralize }} will be created</div></div></div>
  <div class="col"><div class="card card-body text-center">
    <div class="fs-3">✏️ {{ summary.update }}</div><div class="small">grade{{ summary.update|pluralize }} will change</div></div></div>
  <div class="col"><div class="card card-body text-center">
    <div class="fs-3">＝ {{ summary.unchanged }}</div><div class="small">already up to date</div></div></div>
  <div class="col"><div class="card card-body text-center">
    <div class="fs-3">❌ {{ summary.cell_errors|add:summary.row_errors }}</div><div class="small">problem{{ summary.cell_errors|add:summary.row_errors|pluralize }} to fix</div></div></div>
</div>

{% if report.cell_errors or report.errors %}
<section class="mb-4" aria-labelledby="errors-h">
  <h2 id="errors-h" class="h5">❌ Problems: these cells and rows will not be saved</h2>
  <table class="table table-sm">
    <thead><tr><th>Where</th><th>Student</th><th>Value</th><th>Problem</th></tr></thead>
    <tbody>
      {% for e in report.errors %}
        <tr><td>Row{{ e.rows|length|pluralize }} {{ e.rows|join:", " }}</td><td>{{ e.student_number|default:"—" }}</td><td></td><td>{{ e.message }}</td></tr>
      {% endfor %}
      {% for e in report.cell_errors %}
        <tr><td class="font-monospace">{{ e.cell }}</td><td>{{ e.student_number }}</td><td><code>{{ e.raw }}</code></td><td>{{ e.message }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if report.warnings or report.missing_students %}
<section class="mb-4" aria-labelledby="warnings-h">
  <h2 id="warnings-h" class="h5">⚠️ Worth a look</h2>
  <ul>
    {% for w in report.warnings %}<li>{{ w.message }}</li>{% endfor %}
    {% if report.missing_students %}
      <li>Enrolled but not in the file ({{ report.missing_students|length }}): {{ report.missing_students|join:", " }}. Their grades stay as they are.</li>
    {% endif %}
    {% if summary.empty %}<li>{{ summary.empty }} empty cell{{ summary.empty|pluralize }} left as they are.</li>{% endif %}
  </ul>
</section>
{% endif %}

{% if visible_changes %}
<section class="mb-4" aria-labelledby="changes-h">
  <h2 id="changes-h" class="h5">What will be saved (as drafts)</h2>
  <div class="table-responsive" style="max-height: 28rem">
    <table class="table table-sm table-striped tabular-nums">
      <thead class="sticky-top"><tr><th>Cell</th><th>Student</th><th>Assessment</th><th>Now</th><th>After</th></tr></thead>
      <tbody>
        {% for c in visible_changes %}
        <tr>
          <td class="font-monospace">{{ c.cell }}</td><td>{{ c.student_number }}</td><td>{{ c.assessment_name }}</td>
          <td>{% if c.old_excused %}excused{% elif c.old_score is None %}—{% else %}{{ c.old_score|weight }}{% endif %}</td>
          <td class="fw-semibold">{% if c.new_excused %}excused{% else %}{{ c.new_score|weight }}{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
{% endif %}

{% if not applied %}
<form method="post" action="{% url 'grading:upload_confirm' offering_id=offering.pk job_id=job.pk %}" class="card card-body">
  {% csrf_token %}
  {% if report.has_blocking_errors %}
    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" name="skip_invalid" id="skip_invalid">
      <label class="form-check-label" for="skip_invalid">Skip the problem cells and rows, save everything else</label>
    </div>
  {% endif %}
  <div class="d-flex gap-2">
    <button class="btn btn-primary"{% if not summary.create and not summary.update %} disabled{% endif %}>
      Save {{ summary.create|add:summary.update }} draft grade{{ summary.create|add:summary.update|pluralize }}
    </button>
    <a class="btn btn-outline-secondary" href="{% url 'grading:upload_map' offering_id=offering.pk job_id=job.pk %}">Back to columns</a>
  </div>
  <p class="small text-body-secondary mt-2 mb-0">Students see nothing until you publish each assessment on the grade sheet.</p>
</form>
{% endif %}
{% endblock %}
```

Add the entry point to the grade sheet header in `grading/sheet.html`, next to the title:

```django
{% if perms_for.can_edit %}
  <a class="btn btn-outline-primary btn-sm" href="{% url 'grading:upload' offering_id=offering.pk %}">
    Upload grades (CSV / Excel)
  </a>
{% endif %}
```

**7. Generate the golden files once, then read them.** Run the golden tests with `UPDATE_GOLDEN=1` the first time. Then **read both JSON files line by line** against the table in step 1 before committing. A golden file you haven't checked by hand only proves the code does what it does. Expected contents:

`seed/grades/expected/clean.json`:

```json
{
  "summary": {"create": 17, "update": 0, "unchanged": 0, "excused": 1, "empty": 1, "cell_errors": 0, "row_errors": 0, "not_enrolled": 0, "missing": 0},
  "changes": [
    {"cell": "C2", "student_number": "2026-0001", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "90", "new_excused": false},
    {"cell": "D2", "student_number": "2026-0001", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "80", "new_excused": false},
    {"cell": "E2", "student_number": "2026-0001", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "18", "new_excused": false},
    {"cell": "C3", "student_number": "2026-0002", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "75.5", "new_excused": false},
    {"cell": "D3", "student_number": "2026-0002", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "88", "new_excused": false},
    {"cell": "E3", "student_number": "2026-0002", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "15", "new_excused": false},
    {"cell": "C4", "student_number": "2026-0003", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "62", "new_excused": false},
    {"cell": "D4", "student_number": "2026-0003", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "70", "new_excused": false},
    {"cell": "E4", "student_number": "2026-0003", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "", "new_excused": true},
    {"cell": "C5", "student_number": "2026-0004", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "48", "new_excused": false},
    {"cell": "D5", "student_number": "2026-0004", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "55", "new_excused": false},
    {"cell": "E5", "student_number": "2026-0004", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "9.5", "new_excused": false},
    {"cell": "C6", "student_number": "2026-0005", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "100", "new_excused": false},
    {"cell": "D6", "student_number": "2026-0005", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "92", "new_excused": false},
    {"cell": "E6", "student_number": "2026-0005", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "20", "new_excused": false},
    {"cell": "C7", "student_number": "2026-0006", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "81", "new_excused": false},
    {"cell": "E7", "student_number": "2026-0006", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "12", "new_excused": false}
  ],
  "cell_errors": [],
  "row_issues": [],
  "missing_students": [],
  "empty_cells": 1
}
```

`seed/grades/expected/messy.json`:

```json
{
  "summary": {"create": 6, "update": 1, "unchanged": 2, "excused": 1, "empty": 0, "cell_errors": 3, "row_errors": 1, "not_enrolled": 1, "missing": 1},
  "changes": [
    {"cell": "C2", "student_number": "2026-0001", "assessment": "Midterm I", "kind": "unchanged", "old": "90", "old_excused": false, "new": "90", "new_excused": false},
    {"cell": "D2", "student_number": "2026-0001", "assessment": "Project", "kind": "update", "old": "75", "old_excused": false, "new": "80", "new_excused": false},
    {"cell": "E2", "student_number": "2026-0001", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "18", "new_excused": false},
    {"cell": "C3", "student_number": "2026-0002", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "85.5", "new_excused": false},
    {"cell": "D3", "student_number": "2026-0002", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "88", "new_excused": false},
    {"cell": "E3", "student_number": "2026-0002", "assessment": "Quiz 1", "kind": "unchanged", "old": "15", "old_excused": false, "new": "15", "new_excused": false},
    {"cell": "C4", "student_number": "2026-0003", "assessment": "Midterm I", "kind": "create", "old": "", "old_excused": false, "new": "", "new_excused": true},
    {"cell": "D5", "student_number": "2026-0004", "assessment": "Project", "kind": "create", "old": "", "old_excused": false, "new": "55", "new_excused": false},
    {"cell": "E5", "student_number": "2026-0004", "assessment": "Quiz 1", "kind": "create", "old": "", "old_excused": false, "new": "9.5", "new_excused": false}
  ],
  "cell_errors": [
    {"cell": "D4", "student_number": "2026-0003", "assessment_name": "Project", "raw": "-5", "code": "negative", "message": "Scores can't be negative."},
    {"cell": "E4", "student_number": "2026-0003", "assessment_name": "Quiz 1", "raw": "abc", "code": "not_a_number", "message": "“abc” is not a number. Use a number, EX for excused, or leave the cell empty."},
    {"cell": "C5", "student_number": "2026-0004", "assessment_name": "Midterm I", "raw": "105", "code": "above_max", "message": "Max for Midterm I is 100."}
  ],
  "row_issues": [
    {"rows": [6, 7], "student_number": "2026-0005", "code": "duplicate", "message": "Student 2026-0005 appears on rows 6, 7. Keep one row per student."},
    {"rows": [9], "student_number": "2026-9999", "code": "not_enrolled", "message": "2026-9999 (row 9) is not enrolled in this course. Row skipped."}
  ],
  "missing_students": [
    "2026-0006"
  ],
  "empty_cells": 0
}
```

### Tests

`apps/grading/tests/conftest.py` sets up the course every upload test uses: 3 assessments and 6 enrolled students, matching the sample files:

```python
# apps/grading/tests/conftest.py  (pytest finds these fixtures automatically)
"""The offering every upload test uses. It matches seed/grades/*.csv exactly."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory,
    EnrollmentFactory,
    GradeFactory,
    MembershipFactory,
    OfferingFactory,
    UserFactory,
)

STUDENTS = [("Elif", "Yıldız"), ("Ahmet", "Kaya"), ("Zeynep", "Arslan"),
            ("Mert", "Çelik"), ("Selin", "Koç"), ("Burak", "Öztürk")]


@pytest.fixture
def upload_course(db):
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    instructor = UserFactory(email="instructor@example.com")
    MembershipFactory(user=instructor, program=offering.course.program, role="instructor")
    offering.instructors.add(instructor)
    midterm = AssessmentFactory(offering=offering, name="Midterm I", kind="midterm",
                                max_score=Decimal("100"), position=1)
    project = AssessmentFactory(offering=offering, name="Project", kind="project",
                                max_score=Decimal("100"), position=2)
    quiz = AssessmentFactory(offering=offering, name="Quiz 1", kind="quiz",
                             max_score=Decimal("20"), position=3)
    enrollments = {}
    for number, (first, last) in enumerate(STUDENTS, start=1):
        student = UserFactory(first_name=first, last_name=last, student_number=f"2026-{number:04d}")
        enrollments[student.student_number] = EnrollmentFactory(offering=offering, student=student)
    return SimpleNamespace(offering=offering, instructor=instructor, midterm=midterm, project=project,
                           quiz=quiz, enrollments=enrollments)


@pytest.fixture
def messy_existing(upload_course):
    """Draft grades that exist before messy.csv is uploaded (to exercise update / unchanged)."""
    c = upload_course
    GradeFactory(assessment=c.midterm, enrollment=c.enrollments["2026-0001"], score=Decimal("90"))
    GradeFactory(assessment=c.project, enrollment=c.enrollments["2026-0001"], score=Decimal("75"))
    GradeFactory(assessment=c.quiz, enrollment=c.enrollments["2026-0002"], score=Decimal("15"))
    return c
```

`apps/grading/tests/golden.py`:

```python
# apps/grading/tests/golden.py
import json
import os
from pathlib import Path

from django.conf import settings

GRADES_DIR = Path(settings.BASE_DIR) / "seed" / "grades"


def dump_golden(report: dict) -> str:
    """One JSON object per line inside each list, so a diff shows exactly which cell changed."""
    parts = []
    for key, value in report.items():
        if isinstance(value, list) and value:
            items = ",\n".join("    " + json.dumps(v, ensure_ascii=False) for v in value)
            parts.append(f'  "{key}": [\n{items}\n  ]')
        else:
            parts.append(f'  "{key}": {json.dumps(value, ensure_ascii=False)}')
    return "{\n" + ",\n".join(parts) + "\n}\n"


def assert_matches_golden(report: dict, name: str) -> None:
    """Compare with seed/grades/expected/<name>.json. UPDATE_GOLDEN=1 rewrites the file instead:
    do that only on purpose, and read the diff in the PR before committing it."""
    path = GRADES_DIR / "expected" / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(dump_golden(report), encoding="utf-8")
    assert report == json.loads(path.read_text(encoding="utf-8"))
```

`apps/grading/tests/test_upload_unit.py` (no database, under 0.2 s):

```python
# apps/grading/tests/test_upload_unit.py — no database
import io
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from openpyxl import Workbook

from apps.grading.upload import (
    CellProblem,
    column_letter,
    guess_mapping,
    normalise,
    parse_cell,
    read_table,
)

ASSESSMENTS = [SimpleNamespace(id=11, name="Midterm I"), SimpleNamespace(id=12, name="Project"),
               SimpleNamespace(id=13, name="Quiz 1")]


def as_file(data: bytes):
    return io.BytesIO(data)


# ---------- read_table ----------

def test_reads_utf8_comma_csv():
    rows = read_table(as_file("No,Ad\n2026-0001,Elif Yıldız\n".encode()))
    assert rows == [["No", "Ad"], ["2026-0001", "Elif Yıldız"]]


def test_reads_utf8_with_bom():
    rows = read_table(as_file("﻿No,Ad\n1,Ö\n".encode("utf-8")))
    assert rows[0] == ["No", "Ad"]                       # no invisible BOM glued to "No"


def test_reads_turkish_excel_csv():
    data = "Öğrenci No;Ad Soyad;Vize\r\n2026-0001;Şule Ağaç;85,5\r\n".encode("cp1254")
    assert read_table(as_file(data)) == [["Öğrenci No", "Ad Soyad", "Vize"], ["2026-0001", "Şule Ağaç", "85,5"]]


def test_reads_tab_separated():
    assert read_table(as_file(b"No\tMidterm\n1\t50\n"))[1] == ["1", "50"]


def test_pads_short_rows_and_drops_trailing_blank_rows():
    rows = read_table(as_file(b"a,b,c\n1\n\n,,\n"))
    assert rows == [["a", "b", "c"], ["1", "", ""]]


def test_reads_first_sheet_of_xlsx():
    book = Workbook()
    book.active.append(["No", "Midterm I"])
    book.active.append(["2026-0001", 90.0])               # Excel stores numbers as floats
    book.active.append(["2026-0002", 85.5])
    book.create_sheet("Ignored").append(["x"])
    buffer = io.BytesIO()
    book.save(buffer)
    assert read_table(as_file(buffer.getvalue())) == [["No", "Midterm I"], ["2026-0001", "90"], ["2026-0002", "85.5"]]


@pytest.mark.parametrize("data", [b"", b"only,a,header\n", b"PK\x03\x04garbage", b"\x00\x01\x02binary"])
def test_unreadable_files_raise_a_friendly_error(data):
    with pytest.raises(ValidationError):
        read_table(as_file(data))


def test_too_large_file_is_refused():
    with pytest.raises(ValidationError, match="5 MB"):
        read_table(as_file(b"a\n" + b"1\n" * (3 * 1024 * 1024)))


# ---------- matching ----------

@pytest.mark.parametrize(("text", "expected"), [
    ("  Öğrenci  No.", "ogrenci no"), ("MIDTERM I", "midterm i"), ("İSİM", "isim"), ("quiz-1", "quiz 1"),
])
def test_normalise(text, expected):
    assert normalise(text) == expected


def test_guess_mapping_exact_names():
    mapping = guess_mapping(["Student No", "Name", "Midterm I", "Project", "Quiz 1"], ASSESSMENTS,
                            [["2026-0001", "Elif", "90", "80", "18"]])
    assert mapping.student_col == 0
    assert mapping.assessment_cols == {2: 11, 3: 12, 4: 13}
    assert mapping.fuzzy_cols == frozenset()


def test_guess_mapping_fuzzy_names_are_flagged():
    mapping = guess_mapping(["Öğrenci No", "Ad Soyad", "MIDTERM 1", "Proje", "quiz-1", "Notlar"], ASSESSMENTS,
                            [["2026-0001", "Elif", "90", "80", "18", "geç"]])
    assert mapping.assessment_cols == {2: 11, 3: 12, 4: 13}
    assert mapping.fuzzy_cols == frozenset({2, 3})       # "Notlar" stays unmatched


def test_student_column_found_from_values_when_header_is_unhelpful():
    mapping = guess_mapping(["Name", "Code", "Midterm I"], ASSESSMENTS,
                            [["Elif", "2026-0001", "90"], ["Ahmet", "2026-0002", "70"]])
    assert mapping.student_col == 1


def test_no_student_column_means_none():
    assert guess_mapping(["Name", "Midterm I"], ASSESSMENTS, [["Elif", "90"]]).student_col is None


def test_each_assessment_used_once():
    mapping = guess_mapping(["No", "Midterm I", "Midterm 1"], ASSESSMENTS, [["2026-0001", "1", "2"]])
    assert list(mapping.assessment_cols.values()).count(11) == 1


def test_column_letters():
    assert [column_letter(i) for i in (0, 2, 25, 26, 27, 701)] == ["A", "C", "Z", "AA", "AB", "ZZ"]


# ---------- parse_cell ----------

@pytest.mark.parametrize(("raw", "expected"), [
    ("90", (Decimal("90"), False)), ("85,5", (Decimal("85.5"), False)), ("85.25", (Decimal("85.25"), False)),
    ("0", (Decimal("0"), False)), ("100", (Decimal("100"), False)),
    ("EX", (None, True)), ("ex", (None, True)), ("M", (None, True)), ("muaf", (None, True)),
    ("Excused", (None, True)),
])
def test_parse_cell_accepts(raw, expected):
    assert parse_cell(raw, Decimal("100"), "Midterm I") == expected


@pytest.mark.parametrize(("raw", "code"), [
    ("abc", "not_a_number"), ("NaN", "not_a_number"), ("Infinity", "not_a_number"), ("1.234,5", "not_a_number"),
    ("-1", "negative"), ("100.5", "above_max"), ("85.555", "too_precise"),
])
def test_parse_cell_rejects(raw, code):
    with pytest.raises(CellProblem) as info:
        parse_cell(raw, Decimal("100"), "Midterm I")
    assert info.value.code == code


def test_above_max_message_names_the_assessment():
    with pytest.raises(CellProblem, match="Max for Midterm I is 100."):
        parse_cell("105", Decimal("100.00"), "Midterm I")
```

`apps/grading/tests/test_upload_golden.py`:

```python
# apps/grading/tests/test_upload_golden.py
import io
import time

import pytest

from apps.core.tests.factories import EnrollmentFactory, UserFactory
from apps.grading.models import Grade
from apps.grading.tests.golden import GRADES_DIR, assert_matches_golden
from apps.grading.upload import dry_run, guess_mapping, read_table


def plan_for(course, filename):
    with (GRADES_DIR / filename).open("rb") as handle:
        rows = read_table(handle)
    mapping = guess_mapping(rows[0], list(course.offering.assessments.all()), rows[1:51])
    return dry_run(rows, mapping, course.offering)


@pytest.mark.django_db
def test_clean_file_golden(upload_course):
    report = plan_for(upload_course, "clean.csv")
    assert_matches_golden(report.to_dict(include_ids=False), "clean")
    assert not report.has_blocking_errors


@pytest.mark.django_db
def test_messy_csv_golden(messy_existing):
    report = plan_for(messy_existing, "messy.csv")
    assert_matches_golden(report.to_dict(include_ids=False), "messy")
    assert report.has_blocking_errors


@pytest.mark.django_db
def test_messy_xlsx_gives_the_same_report_as_the_csv(messy_existing):
    assert plan_for(messy_existing, "messy.xlsx").to_dict() == plan_for(messy_existing, "messy.csv").to_dict()


@pytest.mark.django_db
def test_dry_run_writes_nothing(messy_existing):
    before = list(Grade.objects.order_by("pk").values_list("pk", "score", "is_excused"))
    plan_for(messy_existing, "messy.csv")
    assert list(Grade.objects.order_by("pk").values_list("pk", "score", "is_excused")) == before


@pytest.mark.django_db
def test_200_rows_in_three_queries_and_under_two_seconds(upload_course, django_assert_max_num_queries):
    lines = ["Student No,Midterm I,Project,Quiz 1"]
    for n in range(7, 207):
        student = UserFactory(student_number=f"2026-{n:04d}")
        EnrollmentFactory(offering=upload_course.offering, student=student)
        lines.append(f"2026-{n:04d},{n % 100},{(n * 7) % 100},{n % 20}")
    rows = read_table(io.BytesIO("\n".join(lines).encode()))
    mapping = guess_mapping(rows[0], list(upload_course.offering.assessments.all()), rows[1:51])
    started = time.perf_counter()
    with django_assert_max_num_queries(3):
        report = dry_run(rows, mapping, upload_course.offering)
    assert time.perf_counter() - started < 2
    assert report.summary()["create"] == 600
```

`apps/grading/tests/test_upload_service.py`:

```python
# apps/grading/tests/test_upload_service.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.grading import services
from apps.grading.models import Grade
from apps.grading.tests.golden import GRADES_DIR
from apps.ingestion.models import IngestionJob

pytestmark = pytest.mark.django_db


def upload(course, filename, *, confirm_mapping=True):
    file = SimpleUploadedFile(filename, (GRADES_DIR / filename).read_bytes())
    job = services.start_grade_upload(course.instructor, course.offering, file)
    if confirm_mapping:
        from apps.grading.upload import ColumnMapping
        services.set_upload_mapping(course.instructor, job, ColumnMapping.from_dict(job.result["mapping"]))
        job.refresh_from_db()
    return job


def test_start_stores_rows_and_a_random_file_name(upload_course):
    job = upload(upload_course, "clean.csv", confirm_mapping=False)
    assert job.kind == IngestionJob.Kind.GRADES
    assert job.status == IngestionJob.Status.PENDING
    assert job.original_filename == "clean.csv"
    assert "clean" not in job.file.name                        # stored under a random name
    assert len(job.result["rows"]) == 7
    assert Grade.objects.count() == 0


def test_apply_clean_file_creates_drafts_only(upload_course):
    job = upload(upload_course, "clean.csv")
    result = services.apply_grade_upload(upload_course.instructor, job)
    assert (result.created, result.updated, result.unchanged) == (17, 0, 0)
    assert Grade.objects.count() == 17
    assert not Grade.objects.filter(published_score__isnull=False).exists()   # AC 2: nothing published
    assert Grade.objects.filter(is_excused=True).count() == 1
    elif_mid = Grade.objects.get(assessment=upload_course.midterm,
                                 enrollment=upload_course.enrollments["2026-0001"])
    assert elif_mid.score == Decimal("90") and elif_mid.updated_by == upload_course.instructor
    assert AuditEvent.objects.filter(action="grade.create").count() == 17
    assert AuditEvent.objects.filter(action="grade_upload.apply").count() == 1
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.APPLIED and job.applied_at is not None


def test_reuploading_the_same_file_changes_nothing(upload_course):
    services.apply_grade_upload(upload_course.instructor, upload(upload_course, "clean.csv"))
    events = AuditEvent.objects.count()
    result = services.apply_grade_upload(upload_course.instructor, upload(upload_course, "clean.csv"))
    assert (result.created, result.updated, result.unchanged) == (0, 0, 17)        # AC 3
    grade_events = AuditEvent.objects.filter(action__startswith="grade.").count()
    assert grade_events == 17                                                      # no new grade events
    assert AuditEvent.objects.count() == events + 2                                # start + apply only


def test_blocking_errors_stop_confirm_and_write_nothing(messy_existing):
    job = upload(messy_existing, "messy.csv")
    with pytest.raises(ValidationError, match="skip invalid rows"):
        services.apply_grade_upload(messy_existing.instructor, job)
    assert Grade.objects.count() == 3


def test_skip_invalid_saves_the_rest(messy_existing):
    result = services.apply_grade_upload(messy_existing.instructor, upload(messy_existing, "messy.csv"),
                                         skip_invalid=True)
    assert (result.created, result.updated, result.unchanged) == (6, 1, 2)
    assert (result.skipped_cells, result.skipped_rows) == (3, 3)      # rows 6, 7 (duplicate) and 9 (not enrolled)
    elif_project = Grade.objects.get(assessment=messy_existing.project,
                                     enrollment=messy_existing.enrollments["2026-0001"])
    assert elif_project.score == Decimal("80")
    event = AuditEvent.objects.get(action="grade.update", entity_id=elif_project.pk)
    assert event.before == {"score": "75.00", "is_excused": False}
    assert event.after["score"] == "80" and event.after["via"] == "upload"


def test_confirm_uses_the_database_as_it_is_now(messy_existing):
    job = upload(messy_existing, "messy.csv")
    Grade.objects.filter(assessment=messy_existing.project,
                         enrollment=messy_existing.enrollments["2026-0001"]).update(score=Decimal("80"))
    result = services.apply_grade_upload(messy_existing.instructor, job, skip_invalid=True)
    assert result.updated == 0 and result.unchanged == 3


def test_cannot_apply_twice(upload_course):
    job = upload(upload_course, "clean.csv")
    services.apply_grade_upload(upload_course.instructor, job)
    with pytest.raises(ValidationError, match="already applied"):
        services.apply_grade_upload(upload_course.instructor, job)


def test_cannot_apply_before_mapping_is_confirmed(upload_course):
    job = upload(upload_course, "clean.csv", confirm_mapping=False)
    with pytest.raises(ValidationError, match="column mapping"):
        services.apply_grade_upload(upload_course.instructor, job)


def test_closed_term_blocks_upload(upload_course):
    job = upload(upload_course, "clean.csv")
    Term.objects.filter(pk=upload_course.offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.apply_grade_upload(upload_course.instructor, job)
    assert Grade.objects.count() == 0


def test_failure_midway_rolls_everything_back(upload_course, monkeypatch):
    job = upload(upload_course, "clean.csv")

    def explode(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(services, "record", explode)        # first audit write fails after the grade writes
    with pytest.raises(RuntimeError):
        services.apply_grade_upload(upload_course.instructor, job)
    assert Grade.objects.count() == 0
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.READY
```

`apps/grading/tests/test_upload_views.py`:

```python
# apps/grading/tests/test_upload_views.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.tests.factories import UserFactory
from apps.grading.models import Grade
from apps.grading.tests.golden import GRADES_DIR
from apps.ingestion.models import IngestionJob

pytestmark = pytest.mark.django_db


def test_full_flow_as_the_instructor(client, upload_course):
    c = upload_course
    client.force_login(c.instructor)
    url = reverse("grading:upload", kwargs={"offering_id": c.offering.pk})
    assert client.get(url).status_code == 200

    file = SimpleUploadedFile("clean.csv", (GRADES_DIR / "clean.csv").read_bytes(), content_type="text/csv")
    response = client.post(url, {"file": file})
    job = IngestionJob.objects.get()
    map_url = reverse("grading:upload_map", kwargs={"offering_id": c.offering.pk, "job_id": job.pk})
    assert response.status_code == 302 and response.url == map_url

    page = client.get(map_url)
    assert page.status_code == 200 and "Student number" in page.content.decode()

    response = client.post(map_url, {"col_0": "student", "col_1": "", "col_2": str(c.midterm.pk),
                                     "col_3": str(c.project.pk), "col_4": str(c.quiz.pk)})
    preview_url = reverse("grading:upload_preview", kwargs={"offering_id": c.offering.pk, "job_id": job.pk})
    assert response.url == preview_url
    preview = client.get(preview_url)
    assert preview.context["summary"]["create"] == 17
    assert "grades will be created" in preview.content.decode()
    assert Grade.objects.count() == 0                                     # still nothing saved

    response = client.post(reverse("grading:upload_confirm",
                                   kwargs={"offering_id": c.offering.pk, "job_id": job.pk}))
    assert response.url == reverse("grading:sheet", kwargs={"offering_id": c.offering.pk})
    assert Grade.objects.count() == 17


def test_mapping_needs_exactly_one_student_column(client, upload_course):
    c = upload_course
    client.force_login(c.instructor)
    client.post(reverse("grading:upload", kwargs={"offering_id": c.offering.pk}),
                {"file": SimpleUploadedFile("clean.csv", (GRADES_DIR / "clean.csv").read_bytes())})
    job = IngestionJob.objects.get()
    response = client.post(reverse("grading:upload_map", kwargs={"offering_id": c.offering.pk, "job_id": job.pk}),
                           {"col_0": "", "col_2": str(c.midterm.pk)})
    assert response.status_code == 200
    assert "exactly one column" in response.content.decode()


def test_wrong_file_type_is_refused(client, upload_course):
    client.force_login(upload_course.instructor)
    response = client.post(reverse("grading:upload", kwargs={"offering_id": upload_course.offering.pk}),
                           {"file": SimpleUploadedFile("grades.xls", b"\xd0\xcf\x11\xe0old excel")})
    assert response.status_code == 200
    assert "Save as" in response.content.decode()
    assert not IngestionJob.objects.exists()


def test_a_student_gets_404(client, upload_course):
    client.force_login(UserFactory())
    response = client.get(reverse("grading:upload", kwargs={"offering_id": upload_course.offering.pk}))
    assert response.status_code == 404


def test_another_course_cannot_open_this_job(client, upload_course):
    from apps.core.tests.factories import OfferingFactory

    c = upload_course
    client.force_login(c.instructor)
    client.post(reverse("grading:upload", kwargs={"offering_id": c.offering.pk}),
                {"file": SimpleUploadedFile("clean.csv", (GRADES_DIR / "clean.csv").read_bytes())})
    job = IngestionJob.objects.get()
    other = OfferingFactory()
    other.instructors.add(c.instructor)                                   # same instructor, other course
    url = reverse("grading:upload_preview", kwargs={"offering_id": other.pk, "job_id": job.pk})
    assert client.get(url).status_code == 404


def test_confirm_rejects_get(client, upload_course):
    client.force_login(upload_course.instructor)
    url = reverse("grading:upload_confirm", kwargs={"offering_id": upload_course.offering.pk, "job_id": 1})
    assert client.get(url).status_code == 405
```

**Permission matrix.** Each of the four URLs already has a row in `ROUTES` (`apps/accounts/tests/routes.py`, written in S2-02). A row switches on by itself once its URL resolves, so there is nothing to add; run the matrix test and check it gives these results (the matrix sends `upload_confirm` as a POST, so the allowed roles get a redirect rather than 405):

| URL | Anonymous | Student | Instructor (other course) | Instructor (own) | Head | Admin |
|---|---|---|---|---|---|---|
| `grading:upload` | 302 → login | 404 | 404 | 200 | 200 | 200 |
| `grading:upload_map` (job of this offering) | 302 | 404 | 404 | 200 | 200 | 200 |
| `grading:upload_preview` (READY job) | 302 | 404 | 404 | 200 | 200 | 200 |
| `grading:upload_confirm` | 302 | 404 | 404 | 405 (POST only) | 405 | 405 |

### Check it works

```bash
uv run pytest apps/grading -q                                  # all green
uv run python manage.py runserver
```

1. Log in as an instructor of a 2026F offering in the seed data, open **Grades → Upload grades (CSV / Excel)**.
2. Upload `seed/grades/messy.xlsx`. The mapping page shows `MIDTERM 1 → Midterm I` and `Proje → Project` with the yellow "Best guess" badge, and `Notlar` is set to ignore. (The seeded offering has its own students, so most rows will show as "not enrolled". For the full picture, run this against a test offering built like the conftest fixture.)
3. Continue. The preview lists the problems with cell references (`D4`, `E4`, `C5`), the duplicate rows 6 and 7, and the unknown student. Click Save without ticking the box: the page comes back with the red message "The file still has errors…" and nothing is saved. Tick "Skip the problem cells and rows" and save again.
4. The grade sheet shows the new values with the amber "unpublished" dot. Log in as one of those students in another window: nothing has changed for them.
5. Upload the same file again. The preview says 0 created, 0 changed.

### Done when

- [ ] AC 1: `test_clean_file_golden`, `test_messy_csv_golden`, `test_messy_xlsx_gives_the_same_report_as_the_csv`
- [ ] AC 2: `test_dry_run_writes_nothing`, `test_apply_clean_file_creates_drafts_only` (no `published_score`)
- [ ] AC 3: `test_reuploading_the_same_file_changes_nothing`
- [ ] AC 4: `test_200_rows_in_three_queries_and_under_two_seconds`
- [ ] Transaction safety: `test_failure_midway_rolls_everything_back`, `test_cannot_apply_twice`
- [ ] Permission matrix updated; manual check above done on staging

### Commits and PR

```
Add clean and messy sample gradebooks with golden reports (#S4-03)
Rewrite upload parsing as a pure plan() over plain data
Add upload services with re-planning on confirm
Add upload, column mapping and preview screens
Add upload URLs to the permission matrix
```

PR title: **Bulk grade upload with dry run and golden tests (S4-03)**. This PR is over 400 lines. Split it into two: (1) `upload.py` + samples + unit and golden tests, (2) services + views + templates.

---

## S4-04 · Baseline bug fixes from the Sprint 3 review

**Points:** 2 · **Owner:** Person C · **Branch:** one `fix/<issue#>-<slug>` per bug · **Depends on:** Sprint 3 review notes

### Goal

The Sprint 3 review (Sunday 8 Nov) will produce a list of small bugs. This story is a **timebox** of 2 points (about 4 hours) to fix the ones that matter for Thursday's live demo. Everything else goes back on the backlog with an estimate. The aim isn't "zero bugs", it's that the demo path works and nothing is forgotten.

### Steps

**1. Triage on Monday morning, 20 minutes, all three of you.** Each bug from the review becomes a GitHub issue built from the `bug.yml` template, then gets one label:

| Label | Rule | Goes where |
|---|---|---|
| `demo-path` | Breaks or embarrasses the path head → instructor → publish → student profile | S4-04, fixed by Wednesday 12:00 |
| `data-wrong` | Any number on screen that disagrees with the engine, or a permission leak | S4-04, **top priority**, regardless of demo |
| `polish` | Cosmetic, wording, alignment | Backlog, Sprint 7 (S7-07) |
| `later` | Real but rare | Backlog with an estimate |

**2. Fix test-first.** For every `demo-path` or `data-wrong` bug: write a failing test that reproduces it, commit it, then fix it. The red commit is the proof the bug existed, and the test stops it coming back. Commit messages: `Reproduce empty-state crash on course with no LOs (#57)` then `Fix empty state when an offering has no LOs (#57)`.

**3. Small PRs.** One bug per PR, so a reviewer can approve it in five minutes.

**4. Write down what was cut.** In `docs/process/sprint-04/review.md`, list the bugs found, the ones fixed, and the ones moved, each with its issue number. That's evidence for "how we handle defects" in the CSE 311 report.

### Check it works

Run the baseline demo path from the Sprint 3 checkpoint end to end on staging after the last fix merges. Every step works without a console error. Check this with the browser DevTools console open.

### Done when

- [ ] Every `data-wrong` bug fixed with a regression test
- [ ] Every `demo-path` bug fixed or consciously accepted (written down, with the reason)
- [ ] `review.md` lists all bugs and where each went

### Commits and PR

One PR per bug: **Fix <thing> (#NN)**.

---

## S4-05 · CSE 311 checkpoint evidence

**Points:** 2 · **Owner:** Person C (Scrum Master) · **Branch:** `docs/S4-05-evidence` · **Depends on:** Sprints 0–4 evidence folders

### Goal

On Sunday 15 Nov, everything S5-01 needs for Tuesday's slides and report is already in `docs/process/`. Section 2 of the CSE 311 report is graded on *evidence* (who did what, velocity, sprints). Evidence collected weekly is cheap. Evidence reconstructed the night before is weak, and graders can tell.

### Files

| Path | Create/modify | What |
|---|---|---|
| `docs/process/velocity.md` | modify | Rows for Sprints 0–4 complete |
| `docs/process/velocity.png` | create | Bar chart of completed points + forecast line |
| `scripts/velocity_chart.py` | create | Draws the chart from `velocity.md` |
| `docs/process/sprint-0N/` | check | The §9.5 checklist for every sprint so far |
| `docs/process/ci-runs.md` | create | Table of CI/CD run summaries with links |
| `docs/process/contributors-2026-11-15.png` | create | GitHub Insights screenshots |

### Steps

**1. Audit every sprint folder against the §9.5 checklist.** Fill the gaps *now* while memory is fresh. If something is truly missing, such as a board screenshot that was never taken, write "not captured" rather than inventing it.

| Item | S0 | S1 | S2 | S3 | S4 |
|---|---|---|---|---|---|
| Board screenshot, Monday | | | | | |
| Board screenshot, Sunday | | | | | |
| Insights burn-up screenshot | | | | | |
| Review recording link | | | | | |
| `retro.md` with action item | | | | | |
| Row in `velocity.md` | | | | | |
| Release PR + tag + green CD run link | | | | | |

Copy this table into `docs/process/evidence-audit.md` and tick it.

**2. The velocity chart from `velocity.md`.** A script, so the final report can regenerate it in December with one command. It reads the Markdown table and needs no spreadsheet. matplotlib is a dev-only dependency: `uv add --dev matplotlib`.

```python
#!/usr/bin/env python3
"""scripts/velocity_chart.py — draw docs/process/velocity.png from docs/process/velocity.md.

Usage: uv run python scripts/velocity_chart.py
Bars = completed points per sprint. Dashed line = forecast. Committed shown as an outline."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # no window; we only write a file
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "process" / "velocity.md"
TARGET = ROOT / "docs" / "process" / "velocity.png"


def number(cell: str) -> float | None:
    cell = cell.strip()
    try:
        return float(cell)
    except ValueError:
        return None                       # "–" or empty


def read_rows() -> list[dict]:
    lines = [line for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    header = [cell.strip().lower() for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:                # skip header and the |---| separator
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        row = dict(zip(header, cells, strict=False))
        if number(row.get("completed", "")) is not None:
            rows.append(row)
    return rows


def main() -> None:
    rows = read_rows()
    labels = [f"S{row['sprint']}" for row in rows]
    completed = [number(row["completed"]) for row in rows]
    committed = [number(row["committed"]) or 0 for row in rows]
    forecast = [number(row["forecast"]) for row in rows]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
    positions = range(len(rows))
    ax.bar(positions, committed, width=0.6, fill=False, edgecolor="#9aa5b1", label="Committed")
    bars = ax.bar(positions, completed, width=0.6, color="#1f3a5f", label="Completed")
    ax.bar_label(bars, labels=[f"{c:g}" for c in completed], padding=2, fontsize=9)
    points = [(i, f) for i, f in zip(positions, forecast, strict=True) if f is not None]
    if points:
        ax.plot([p[0] for p in points], [p[1] for p in points], linestyle="--", marker="o",
                color="#d98e04", label="Forecast")
    ax.set_xticks(list(positions), labels)
    ax.set_ylabel("Story points")
    ax.set_title("POlaris velocity per sprint")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(TARGET)
    print(f"Wrote {TARGET.relative_to(ROOT)} ({len(rows)} sprints)")


if __name__ == "__main__":
    main()
```

**3. CI/CD run summaries** for report Section 5. GitHub keeps run history, but a table is what goes in the report:

```bash
gh run list --branch develop --limit 30 \
  --json displayTitle,workflowName,conclusion,createdAt,url \
  --jq '.[] | "| \(.createdAt[:10]) | \(.workflowName) | \(.displayTitle) | \(.conclusion) | [run](\(.url)) |"' \
  > /tmp/runs.md
{ echo "| Date | Workflow | Commit | Result | Link |"; echo "|---|---|---|---|---|"; cat /tmp/runs.md; } \
  > docs/process/ci-runs.md
```

Pick one red run that was later fixed and write two sentences about it under the table. "CI caught X before it reached staging" is the strongest sentence in Section 5.

**4. Contributor charts.** Section 3 of the report needs GitHub's *Contributors* and *Code frequency* graphs. They count only the **default branch** (`develop`, spec §9.6). Screenshot both at full width: Insights → Contributors, Insights → Code frequency. Save them as `docs/process/contributors-2026-11-15.png` and `code-frequency-2026-11-15.png`. If someone's commits are missing, their git email doesn't match their GitHub account. Fix it now (spec §9.6, "the contribution chart trap"), because the chart only fixes itself for commits made after the fix.

**5. Who did what.** Export the issue list per assignee for Section 2:

```bash
for user in OnurHaniffa Fatmaaa-Demir ZeynepUygun05; do
  echo "## $user"
  gh issue list --state closed --assignee "$user" --limit 100 \
    --json number,title,closedAt --jq '.[] | "- #\(.number) \(.title) (closed \(.closedAt[:10]))"'
done > docs/process/work-split-2026-11-15.md
```

### Check it works

`uv run python scripts/velocity_chart.py` prints "Wrote docs/process/velocity.png (5 sprints)", and the PNG shows five bars with a dashed forecast line. `evidence-audit.md` has no blank cells: every cell is ✓ or "not captured".

### Done when

- [ ] Evidence audit table complete
- [ ] `velocity.png`, `ci-runs.md`, contributor screenshots and `work-split-*.md` committed
- [ ] Every member appears in the Contributors chart

### Commits and PR

```
Add velocity chart script and chart for Sprints 0–4
Add CI run summary and contributor screenshots
Add work split export for the CSE 311 checkpoint
```

PR title: **Process evidence for the CSE 311 checkpoint (S4-05)**

---

# Sprint 5 — Light: CSE 311 checkpoint (Mon 16 – Sun 22 Nov)

**Sprint goal:** present our tooling and tasking on Tuesday. Then build everything behind the AI wizard except its screens: a real background worker, a tested Claude call, validation that turns the model's answer into a reviewable draft, and an eval that measures it. Sprint 6 (the wizard UI) starts on solid ground.

| ID | Story | Pts | Owner | Merge order |
|---|---|---|---|---|
| S5-01 | CSE 311 checkpoint report + slides | 3 | C + all | Slides frozen Mon 16 Nov 20:00 |
| S5-02 | Celery worker in prod, eager mode in tests, `on_commit` helper | 2 | C | 1 (S5-03's task needs it) |
| S5-03 | Extraction: `files.py`, `prompts.py`, task, cost recording | 5 | A | 2 |
| S5-04 | `validation.py`: `validate_and_derive` + fixture tests | 3 | B | Any time (pure; only needs `schemas.py` from S5-03's first commit) |
| S5-05 | Eval set + `eval_extraction` command | 2 | A | 3 (needs S5-03 merged) |

**Unblocking S5-04 on Monday.** S5-04 needs only `apps/ingestion/schemas.py` (spec §7.4, copy it verbatim). Person A opens a tiny PR with just that file on Monday morning and merges it after review. From then on, A and B work in parallel without waiting on each other.

**Before Monday:** create the team's Anthropic API key (Console → Settings → Workspaces → new workspace "polaris" → set a **monthly spend limit of $50** → API key). Store it in three places only: each developer's `.env`, the staging/production server `.env`, and nowhere else. CI never needs it, because tests never call the API.

**By Sunday:**
1. On staging, a syllabus job created from the Django shell goes PENDING → PROCESSING → READY *in the worker*, not in the web process. The worker log shows it.
2. The job row shows tokens, cost and the request id.
3. `eval_extraction` has run once on all six eval files, and its table is in `docs/process/sprint-05/eval.md`.

---

## S5-01 · CSE 311 checkpoint report and slides

**Points:** 3 · **Owner:** Person C, everyone presents · **Branch:** `docs/S5-01-cse311-checkpoint` · **Depends on:** S4-05

### Goal

Spec §13.2: about 10 slides and 10 minutes on Tuesday 17 Nov, theme *Tooling & Tasking*, plus a report using the final CSE 311 headings. S4-05 already collected the evidence. This story turns it into slides and a report, and rehearses them. The timeline is tight because the checkpoint falls on the sprint's second day.

### Steps

**1. Timeline.**

| When | What | Who |
|---|---|---|
| Sun 15 Nov (end of S4) | Evidence complete (S4-05). Slide skeleton with §13.2 titles; speakers assigned | C |
| Mon 16 Nov 14:00 | Every speaker's slides filled in | all |
| Mon 16 Nov 18:00 | Report complete; A and B review it within 2 hours | C |
| Mon 16 Nov 20:00 | **Slides frozen.** Rehearsal 1, timed | all |
| Tue 17 Nov | Rehearsal 2 before class. Present. Print the report if required | all |
| Tue 17 Nov evening | Commit slides + PDF; note the questions in `docs/process/sprint-05/retro.md` | C |

**2. Speakers.**

| Slides (§13.2) | Speaker |
|---|---|
| 1–2 (punchline, how the backlog was formed) | A, the Product Owner, who owns the backlog |
| 3–5 (GitHub Projects board, meetings, who does what) | C, the Scrum Master |
| 6–7 (planning poker example, sprint length) | B |
| 8–9 (velocity chart, retro lesson) | C |
| 10 (teaser: CI/CD and AI wizard) | A |

**3. Slide 6 needs one real planning-poker example.** Pick the story with the widest first-round spread from the planning notes (S2-05 or S2-06 are likely). Show the first-round cards, the conversation that closed the gap, and the final estimate. Then show what it *actually* took. A story estimated at 5 that took 8, with the reason why, is a stronger slide than a perfect estimate.

**4. Slide 8: the velocity chart.** Use `docs/process/velocity.png` from S4-05. Say in one sentence why Sprint 4 is lower: it was planned light because of the midterm and the CSE 321 checkpoint. A planned dip is a sign of a team that forecasts, not a weakness.

**5. Report.** Same Markdown → PDF pipeline as S4-02, in `docs/reports/cse311-checkpoint/`. Use the six final-report headings (spec §13.4). Sections 1–2 are written in full. Section 3 gets the contributor and code-frequency screenshots from S4-05. Sections 4–5 are short but real: the branching diagram (spec §9.6) and `ci-runs.md`. Section 6 lists the Getting Real chapters we follow, with one sentence each, marked "planned in full for the final report".

**6. Rehearsal checklist.** Same as S4-02, step 5. Prepare one more likely question: *"Why is a three-person team's velocity comparable to a four-person team's?"* Answer: we don't compare. Velocity is only meaningful against our own previous sprints, which is how we use it to forecast.

### Done when

- [ ] Presented on Tue 17 Nov
- [ ] `docs/reports/cse311-checkpoint/` (source + slides PDF) and `docs/reports/cse311-checkpoint.pdf` committed
- [ ] Questions and answers in the Sprint 5 retro notes

### Commits and PR

```
Add CSE 311 checkpoint report source
Add CSE 311 checkpoint slides and PDF
```

PR title: **CSE 311 checkpoint deliverables (S5-01)**

---

## S5-02 · Celery worker: production, eager mode in tests, `on_commit` helper

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S5-02-celery-worker` · **Depends on:** S0-03 (`config/celery.py`), S2-08 (staging deploy)

### Goal

Until now, `CELERY_TASK_ALWAYS_EAGER=True` in dev meant every "background" task ran inside the web request. A syllabus extraction takes 20–60 seconds, longer than a browser and Caddy will wait comfortably. This story makes the worker real:

- Production runs a separate `worker` container.
- Developers can run one locally.
- Tests stay synchronous and fast.
- A single helper makes sure a task is only queued once the database change it depends on has been committed.

### Background: three ideas, in plain language

**Broker and worker.** The web process doesn't do slow work. It writes a small message ("run `run_syllabus_extraction` with job 42") into Redis, the *broker*, and answers the browser immediately. A separate process, the *worker*, takes messages off Redis and runs them. If the worker is busy or down, messages wait in Redis.

**Why `on_commit`.** A view creates `IngestionJob(42)` inside a transaction and queues the task. If the message is sent *before* the transaction commits, a fast worker can pick it up and run `IngestionJob.objects.get(pk=42)` before row 42 is visible, and the task crashes with `DoesNotExist`. If the transaction then rolls back, the task runs for a job that never existed. `transaction.on_commit(...)` sends the message only after a successful commit, and never after a rollback. We wrap it in one helper so nobody has to remember this.

**Eager mode.** With `CELERY_TASK_ALWAYS_EAGER=True`, `task.delay()` runs the task immediately, in-process. That's ideal for tests: no Redis, no worker, deterministic. There's a trap, though. pytest-django wraps every test in a transaction that is **rolled back** at the end, so `on_commit` callbacks never fire in tests. Use pytest-django's `django_capture_on_commit_callbacks` fixture to run them (see Tests).

### Files

| Path | Create/modify | What |
|---|---|---|
| `apps/core/jobs.py` | create | `enqueue_on_commit(task, *args, **kwargs)` |
| `apps/core/tasks.py` | create | `ping` task for smoke tests |
| `config/settings/base.py` | modify | Celery settings for long tasks |
| `compose.prod.yml` | modify | Worker health check |
| `.env.example` | modify | `CELERY_EAGER` documented |
| `apps/core/tests/test_jobs.py` | create | Tests |

### Steps

**1. Settings.** Add these below the existing `CELERY_*` lines in `config/settings/base.py`:

```python
CELERY_WORKER_PREFETCH_MULTIPLIER = 1        # a worker holds one task at a time: a 60 s Claude call
                                             # must not keep a second job waiting behind it
CELERY_TASK_REJECT_ON_WORKER_LOST = True     # with ACKS_LATE: a killed worker's task goes back to the queue
CELERY_TASK_IGNORE_RESULT = True             # no result backend; job state lives in our own tables
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True   # worker waits for Redis instead of crashing at boot
CELERY_TIMEZONE = TIME_ZONE
```

`ACKS_LATE` (already set) means a message is removed from Redis only *after* the task finishes, so a crash mid-task leads to a re-run. That's only safe because our tasks are **idempotent**: `run_syllabus_extraction` checks the job status first and does nothing for a finished job (S5-03).

**2. The helper.** It's one function, so it's easy to find with grep and easy to review:

```python
# apps/core/jobs.py
"""Queue background work safely. Always use this instead of calling task.delay() in a service."""
from functools import partial

from django.db import transaction


def enqueue_on_commit(task, *args, **kwargs) -> None:
    """Send `task` to the worker after the current transaction commits, never before and never
    after a rollback. Outside a transaction (autocommit) it sends immediately."""
    transaction.on_commit(partial(task.delay, *args, **kwargs))
```

Usage in any service (S6-01 will do exactly this):

```python
from apps.core.jobs import enqueue_on_commit
from apps.ingestion.tasks import run_syllabus_extraction

with transaction.atomic():
    job = IngestionJob.objects.create(...)
    enqueue_on_commit(run_syllabus_extraction, job.pk)
```

**3. A smoke-test task.**

```python
# apps/core/tasks.py
import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task
def ping(message: str = "") -> str:
    """Proves the worker is alive and can import Django. Look for 'pong' in the worker log."""
    log.info("pong %s", message)
    return f"pong {message}".strip()
```

**4. Running a real worker locally.** Developers keep eager mode by default, because it's simpler. To try the real thing, set `CELERY_EAGER=false` in `.env` and run a second terminal:

```bash
docker compose up -d                                   # Redis is already in compose.yml
uv run celery -A config worker -l info --pool solo     # terminal 2; --pool solo = one process, macOS-friendly
uv run celery -A config call apps.core.tasks.ping --args='["from my laptop"]'   # terminal 3
# terminal 2 prints: ... pong from my laptop
```

`--pool solo` avoids the macOS `fork()` crash (`objc[...] +[__NSCFConstantString initialize] may have been in progress`) that the default prefork pool can trigger. Production runs on Linux and keeps prefork with `--concurrency 2`.

Document it in `.env.example`:

```bash
# Run Celery tasks inside the web process (true) or send them to a worker (false).
# Leave true unless you're testing the worker: then run `uv run celery -A config worker -l info --pool solo`.
CELERY_EAGER=true
```

**5. Production: a health check for the worker.** The `worker` service already exists in `compose.prod.yml` (spec §10.5). Without a health check, Docker restarts it if it *exits*, but not if it hangs (for example, after losing its Redis connection). Add this to the `worker` service:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "celery -A config inspect ping -d celery@$$HOSTNAME --timeout 10 | grep -q pong"]
      interval: 60s
      timeout: 20s
      retries: 3
      start_period: 30s
```

`$$HOSTNAME` is how Compose writes a literal `$HOSTNAME`. Celery names a worker `celery@<container hostname>`, so this pings only this container's worker.

The CD workflow's `docker compose up -d` already restarts the worker with the new image on every deploy, because the image tag changes. Check this after the first deploy: `docker compose -f compose.prod.yml ps` shows `worker` as `Up … (healthy)` with a fresh "Created" time.

**6. Prove it on staging.** Set `CELERY_EAGER=false` in the staging `.env` (prod settings never set eager mode, but be explicit). Deploy, then:

```bash
docker compose -f compose.prod.yml exec web python manage.py shell -c \
  "from apps.core.tasks import ping; ping.delay('staging')"
docker compose -f compose.prod.yml logs worker --tail 20 | grep pong
```

### Tests

```python
# apps/core/tests/test_jobs.py
from unittest import mock

import pytest
from django.db import transaction

from apps.core.jobs import enqueue_on_commit
from apps.core.tasks import ping


@pytest.mark.django_db
def test_task_is_sent_only_after_commit(django_capture_on_commit_callbacks):
    with mock.patch.object(ping, "delay") as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            enqueue_on_commit(ping, "hello")
        delay.assert_not_called()                 # still inside the transaction: nothing sent
        assert len(callbacks) == 1
        callbacks[0]()                            # what Django does at COMMIT
        delay.assert_called_once_with("hello")


@pytest.mark.django_db(transaction=True)          # real transactions, so a rollback really happens
def test_rollback_sends_nothing():
    with mock.patch.object(ping, "delay") as delay:
        with pytest.raises(RuntimeError), transaction.atomic():
            enqueue_on_commit(ping, "never")
            raise RuntimeError("something failed after queueing")
        delay.assert_not_called()


def test_eager_mode_runs_tasks_inline():
    # config.settings.test sets CELERY_TASK_ALWAYS_EAGER = True
    assert ping.delay("x").get() == "pong x"
```

**The pattern for every later test of a service that queues work** (S6-01, T2.2, T2.3):

```python
def test_upload_starts_extraction(django_capture_on_commit_callbacks, user, offering, file):
    with django_capture_on_commit_callbacks(execute=True):
        job = services.create_syllabus_job(user, offering, file)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.READY        # the eager task already ran
```

### Check it works

The local steps in step 4 print `pong`. On staging, step 6 shows `pong staging` in the worker log, and `docker compose ps` shows the worker healthy.

### Done when

- [ ] `enqueue_on_commit` exists, tested for commit and rollback
- [ ] Worker health check in `compose.prod.yml`; staging shows `(healthy)`
- [ ] README "Running locally" mentions the worker command

### Commits and PR

```
Add enqueue_on_commit helper and ping task (#S5-02)
Tune Celery for long tasks: prefetch 1, reject on worker loss
Add worker health check to the production stack
```

PR title: **Real Celery worker with on-commit enqueueing (S5-02)**

---

## S5-03 · Extraction service: files, prompt, task, cost

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S5-03-extraction` · **Depends on:** S5-02, S1-05 (POs seeded)

### Goal

Wire spec §7.3–7.5 into working code. Sniff the uploaded file, convert it, call Claude with structured output, and turn every possible outcome into a job that ends READY or FAILED with a human message. Record model, tokens, cost and request id on every job (T1.2 AC 6). The Claude call itself (`extract_syllabus`, `_content_blocks`, the schemas, the system prompt) is **already written in the spec. Copy it, don't rewrite it.** This story adds what surrounds it.

### Files

| Path | Create/modify | What |
|---|---|---|
| `apps/ingestion/schemas.py` | create | Verbatim from spec §7.4 (the Monday mini-PR) |
| `apps/ingestion/prompts.py` | create | `SYSTEM_PROMPT` (spec §7.5 text), `PROMPT_VERSION`, `format_po_list`, `build_instruction` |
| `apps/ingestion/extraction.py` | create | Spec §7.5 code verbatim + `cost_usd` |
| `apps/ingestion/files.py` | create | Magic-byte sniffing, size limit, DOCX → text, photo downscaling |
| `apps/ingestion/tasks.py` | create | `run_syllabus_extraction` with full error handling (replaces the spec's sketch) |
| `apps/ingestion/tests/fixtures.py` | create | Realistic `SyllabusExtraction` builders (shared with S5-04) |
| `apps/ingestion/tests/test_files.py`, `test_tasks.py`, `test_cost.py` | create | Tests, no network |

### Steps

**1. The one-hour spike first (spec §7.5).** Before writing any of the code below, copy `schemas.py`, `prompts.py` and the spec's `extraction.py` and call Claude once from the shell with our real CSE 311 syllabus:

```bash
cp "../CSE 311 - Syllabus - Fall 2026.docx.pdf" apps/ingestion/evals/syllabi/cse311.pdf   # path to your copy
uv run python manage.py shell
```

```python
from pathlib import Path
from apps.catalog.models import Program
from apps.catalog.selectors import active_po_set
from apps.ingestion.extraction import extract_syllabus

pos = "\n".join(f"PO {p.number}: {p.description}" for p in active_po_set(Program.objects.get(code="CSE")).outcomes.order_by("number"))
extraction, response = extract_syllabus(Path("apps/ingestion/evals/syllabi/cse311.pdf"), "application/pdf", pos)
print(response.stop_reason, response.model, response.usage, response._request_id)
print(extraction.model_dump_json(indent=2))
```

Record in the PR description:

1. Does `output_config={"effort": "high"}` work together with `output_format=`?
2. Is the fallback parameter accepted on our key?
3. Do we get 4 LOs and 4 assessments at 25/25/10/40?

> **SDK note found while writing this guide.** In `anthropic` 1.15, `client.beta.messages.parse` has `fallbacks` as a **named parameter**, so `fallbacks="default"` works directly. The spec's `extra_body={"fallbacks": "default"}` sends the same thing and also works. Keep the spec's form unless the spike shows a problem. Also check that `response.usage` reports the fallback model's tokens when a fallback happened.

**2. `extraction.py`.** Paste the spec §7.5 block unchanged, then add the cost function below it. Cost is computed from the model that **actually answered** (`response.model`). With refusal fallback on, that can be a different model from the one we asked for.

```python
# apps/ingestion/extraction.py — add below extract_syllabus (the spec's code above it stays unchanged)
from decimal import Decimal

MILLION = Decimal(1_000_000)
# USD per million tokens (input, output), from spec §7.7. Thinking tokens are billed as output.
PRICES_PER_MILLION = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10")),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """What one call cost. `model` is the model that actually answered (with refusal fallback on,
    that can differ from the one we asked for). Unknown model → 0, and the eval report shows it."""
    for name, (per_input, per_output) in PRICES_PER_MILLION.items():
        if model.startswith(name):
            total = (per_input * input_tokens + per_output * output_tokens) / MILLION
            return total.quantize(Decimal("0.0001"))
    return Decimal("0")
```

**3. `prompts.py`.** The system prompt text is exactly spec §7.5's. `PROMPT_VERSION` is stored on every job (inside `result`), so when accuracy changes we can tell which prompt produced which result.

```python
# apps/ingestion/prompts.py
"""The words we send to Claude. Bump PROMPT_VERSION on every edit and re-run the eval (S5-05):
a prompt change is a behaviour change."""
from apps.catalog.selectors import active_po_set

PROMPT_VERSION = "2026-11-18.1"   # date + counter; stored on every job

SYSTEM_PROMPT = """\
You extract structured course information from a university course syllabus so that a
department can track Program Outcome scores. The syllabus may be in English or Turkish;
always answer in the syllabus's own language for descriptions and quotes.

Rules:
- Only report learning outcomes and assessments that the document actually contains.
  Never invent them. Every learning outcome and assessment must have a verbatim
  source_quote from the document.
- If the document is not a course syllabus, set is_course_syllabus to false and leave
  the lists empty.
- Number learning outcomes in the order the document lists them, starting at 1.
- course_weight_percent is the assessment's share of the final course grade as printed.
- measures_lo_numbers: fill it only from an explicit statement or table in the document,
  and set measures_stated_in_document to true. If the document is silent, propose the
  learning outcomes each assessment most plausibly measures and set it to false.
- course_po_contributions: copy the "contribution of the course to program outcomes"
  table if the document has one (levels 0-5). Otherwise return an empty list.
- lo_po_links: if the document maps learning outcomes to program outcomes, copy that
  mapping with stated_in_document true. Otherwise suggest links with
  stated_in_document false, using weights 1-5 where 5 means the learning outcome is a
  central, directly assessed part of the program outcome. Suggest only clear links,
  usually 1-3 per learning outcome. Never exceed the course-level contribution level
  for that program outcome when one is given. Give a one-sentence rationale per link.
- Put anything ambiguous or contradictory in warnings, in plain English."""


def format_po_list(offering) -> str:
    """'PO 1: <official description>' lines for the offering's program, from the active PO set."""
    po_set = active_po_set(offering.course.program)
    return "\n".join(f"PO {po.number}: {po.description}" for po in po_set.outcomes.order_by("number"))


def build_instruction(po_list_text: str) -> str:
    return (
        "The document above is the syllabus to read.\n\n"
        "These are the department's program outcomes. Use only these PO numbers:\n"
        f"<program_outcomes>\n{po_list_text}\n</program_outcomes>\n\n"
        "Extract the course information following your rules."
    )
```

**4. `files.py`: what may go to Claude, and in what shape.** Three rules from spec §7.3:

- **Type by content, not name.** The first bytes decide. `%PDF-` is a PDF, and a zip that contains `word/document.xml` is a DOCX. A renamed `.exe` called `syllabus.pdf` is rejected, and a phone photo with a strange extension still works.
- **DOCX becomes text**, with table rows written as `cell | cell | cell`. Assessment weights usually live in a table, and a paragraph-only conversion would lose them. `iter_inner_content()` (python-docx ≥ 1.1) walks paragraphs and tables in reading order.
- **Photos are rotated upright and shrunk** to 2000 px on the long side. Phones store "this photo is sideways" in EXIF rather than rotating the pixels, and `exif_transpose` applies it. A smaller image costs fewer tokens and reads just as well.

```python
"""Turn an uploaded syllabus into something Claude can read (spec §7.3).

The file type is decided by the first bytes of the file, never by its extension: a renamed
.exe called syllabus.pdf must be rejected, and a phone photo saved as .JPG.jpeg must work."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_SYLLABUS_BYTES = 20 * 1024 * 1024
MAX_IMAGE_SIDE = 2000

PDF = "application/pdf"
PNG = "image/png"
JPEG = "image/jpeg"
WEBP = "image/webp"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT = "text/plain"            # what a DOCX becomes before it is sent

UNSUPPORTED = "Please upload a PDF, Word (.docx), PNG, JPG or WEBP file. Other formats: export as PDF or JPG first."


class UnsupportedFile(ValueError):
    """Shown to the instructor as-is."""


def sniff_media_type(head: bytes, *, path: Path | None = None) -> str:
    """Media type from magic bytes. `head` = the first 16+ bytes. DOCX needs `path` to look inside the zip."""
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head.startswith(b"PK\x03\x04") and path is not None:
        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" in archive.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            pass
    raise UnsupportedFile(UNSUPPORTED)


def check_upload(uploaded_file) -> str:
    """Used by SyllabusUploadForm: size and type check on the uploaded file object."""
    if uploaded_file.size > MAX_SYLLABUS_BYTES:
        raise UnsupportedFile("The file is larger than 20 MB. Upload only the syllabus pages.")
    uploaded_file.seek(0)
    head = uploaded_file.read(16)
    uploaded_file.seek(0)
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(uploaded_file) as archive:
                is_docx = "word/document.xml" in archive.namelist()
        except zipfile.BadZipFile:
            is_docx = False
        finally:
            uploaded_file.seek(0)
        if is_docx:
            return DOCX
        raise UnsupportedFile(UNSUPPORTED)
    return sniff_media_type(head)


def docx_to_text(path: Path) -> str:
    """Paragraphs and tables in reading order. Table rows become 'cell | cell | cell' lines,
    which is how assessment-weight tables survive the conversion."""
    from docx import Document
    from docx.table import Table

    lines: list[str] = []
    for block in Document(str(path)).iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    text = " ".join(cell.text.split())
                    if not cells or cells[-1] != text:   # merged cells repeat their text
                        cells.append(text)
                lines.append(" | ".join(cells))
            lines.append("")
        else:
            text = block.text.strip()
            if text:
                lines.append(text)
    return "\n".join(lines).strip()


def downscale_image(data: bytes, media_type: str) -> bytes:
    """Phone photos: fix EXIF rotation and shrink to 2000 px on the long side. Same accuracy, fewer tokens."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        out = io.BytesIO()
        fmt = {PNG: "PNG", JPEG: "JPEG", WEBP: "WEBP"}[media_type]
        if fmt == "JPEG" and image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(out, format=fmt, **({"quality": 90} if fmt != "PNG" else {}))
        return out.getvalue()


@dataclass(frozen=True)
class PreparedDocument:
    path: Path
    media_type: str


def prepare_document(source: Path, workdir: Path) -> PreparedDocument:
    """Return a file `extract_syllabus` can send as-is. DOCX → UTF-8 text file; images → downscaled copy."""
    if source.stat().st_size > MAX_SYLLABUS_BYTES:
        raise UnsupportedFile("The file is larger than 20 MB. Upload only the syllabus pages.")
    with source.open("rb") as handle:
        head = handle.read(16)
    media_type = sniff_media_type(head, path=source)
    if media_type == DOCX:
        text = docx_to_text(source)
        if not text:
            raise UnsupportedFile("This Word file has no text in it.")
        target = workdir / "syllabus.txt"
        target.write_text(text, encoding="utf-8")
        return PreparedDocument(target, TEXT)
    if media_type in {PNG, JPEG, WEBP}:
        target = workdir / f"syllabus.{media_type.split('/')[1]}"
        target.write_bytes(downscale_image(source.read_bytes(), media_type))
        return PreparedDocument(target, media_type)
    return PreparedDocument(source, media_type)
```

`check_upload` is for S6-01's `SyllabusUploadForm.clean_file`: it rejects bad files at upload time, before a job is even created. `prepare_document` repeats the check in the worker, because files can arrive by other routes (admin, the eval command).

**5. `tasks.py`: every way the job can end.** The spec's sketch (§7.5) uses `autoretry_for=…`. We handle retries by hand instead, for two reasons found while writing this guide:

- **After the last retry**, `autoretry_for` re-raises the error and the job would stay PROCESSING forever. The spec wants FAILED with "The AI service is unavailable right now…". Handling it by hand lets us mark the job failed on the final attempt.
- **The SDK has more retryable errors than the sketch lists.** 529 `OverloadedError` and 503 `ServiceUnavailableError` are *not* subclasses of `InternalServerError` in SDK 1.15, so the sketch would treat "Claude is overloaded" as a permanent failure.

| What happened | Job ends as | Message the instructor sees |
|---|---|---|
| Valid extraction | READY | — (review screen) |
| `ExtractionError` (refusal, max_tokens) | FAILED | The message from `extract_syllabus` |
| Not a syllabus / no LOs (from validation, S5-04) | FAILED | "This doesn't look like a course syllabus…" |
| Unsupported file type or > 20 MB | FAILED | "Please upload a PDF, Word (.docx)…" |
| 400 Bad request (corrupt PDF, too many pages) | FAILED | `BAD_FILE` |
| 413 Request too large | FAILED | `TOO_LARGE` |
| 401/403 (key missing or revoked) | FAILED | `MISCONFIGURED` |
| 429 / 500 / 503 / 529 / network / timeout | retried 30 s, 60 s, 120 s, 240 s, then FAILED | `UNAVAILABLE` |
| Anything else (a bug) | FAILED, error re-raised so it's logged | `UNEXPECTED` |
| Job discarded while Claude was reading | stays DISCARDED | — |

The last row is why every write goes through `_update_if_active`, a conditional `UPDATE … WHERE status IN ('pending','processing')`. If the instructor discarded the job during the 40-second call, the late result is silently dropped instead of bringing the job back.

```python
# apps/ingestion/tasks.py
"""The syllabus extraction job (spec §7.2, §7.5). Runs in the Celery
worker. Every way it can end leaves the job in READY or FAILED with a message a person can act on."""
import logging
import tempfile
from pathlib import Path

import anthropic
from celery import shared_task
from django.utils import timezone

from .extraction import ExtractionError, cost_usd, extract_syllabus
from .files import UnsupportedFile, prepare_document
from .models import IngestionJob
from .prompts import PROMPT_VERSION, format_po_list
from .validation import validate_and_derive

log = logging.getLogger(__name__)

# Worth waiting for: rate limits, server errors, overload, network trouble. (APITimeoutError is a
# subclass of APIConnectionError, so it's included.) Everything else is final on the first try.
RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,
    anthropic.ServiceUnavailableError,
    anthropic.APIConnectionError,
)
MAX_RETRIES = 4

UNAVAILABLE = "The AI service is unavailable right now. Try again later or set up the course manually."
BAD_FILE = "The file could not be read. Is it a valid PDF, Word file or image?"
TOO_LARGE = "This document is too large to read in one go. Upload only the syllabus pages."
MISCONFIGURED = "Syllabus reading isn't configured on this server. Set up the course manually and tell the team."
UNEXPECTED = "Something went wrong while reading the file. Set up the course manually, or try again later."

ACTIVE = (IngestionJob.Status.PENDING, IngestionJob.Status.PROCESSING)


def backoff_seconds(retries: int) -> int:
    """30 s, 60 s, 120 s, 240 s… capped at 10 minutes."""
    return min(30 * 2**retries, 600)


def _update_if_active(job: IngestionJob, **fields) -> bool:
    """Write only if the job is still pending/processing. If the instructor pressed Discard while
    Claude was reading, the late result must not resurrect the job. Returns True if written."""
    fields["updated_at"] = timezone.now()
    written = IngestionJob.objects.filter(pk=job.pk, status__in=ACTIVE).update(**fields)
    return bool(written)


def mark_failed(job: IngestionJob, message: str, *, detail: str = "") -> None:
    if detail:
        log.warning("Ingestion job %s failed: %s | %s", job.pk, message, detail)
    _update_if_active(job, status=IngestionJob.Status.FAILED, error=message,
                      result={"prompt_version": PROMPT_VERSION, "detail": detail[:4000]})


def record_usage(job: IngestionJob, response) -> None:
    usage = response.usage
    model = response.model or ""
    _update_if_active(
        job,
        model=model[:40],
        request_id=(getattr(response, "_request_id", None) or "")[:64],
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=cost_usd(model, usage.input_tokens, usage.output_tokens),
    )


def save_ready(job: IngestionJob, extraction, draft) -> None:
    _update_if_active(
        job,
        status=IngestionJob.Status.READY,
        error="",
        warnings=draft.warnings,
        result={
            "prompt_version": PROMPT_VERSION,
            "extraction": extraction.model_dump(mode="json"),    # raw model output, kept for debugging and evals
            "draft": draft.to_json(),                            # what the review screen edits (S6-02)
        },
    )


@shared_task(bind=True, max_retries=MAX_RETRIES)
def run_syllabus_extraction(self, job_id: int) -> None:
    job = IngestionJob.objects.select_related("offering__course__program").get(pk=job_id)
    if job.status not in ACTIVE:
        return                                     # idempotent: done, failed or discarded already
    _update_if_active(job, status=IngestionJob.Status.PROCESSING)

    try:
        with tempfile.TemporaryDirectory() as workdir:
            document = prepare_document(Path(job.file.path), Path(workdir))
            extraction, response = extract_syllabus(document.path, document.media_type,
                                                    format_po_list(job.offering))
        record_usage(job, response)                # before validation: a rejected file still cost tokens
        draft = validate_and_derive(extraction, job.offering)
    except (ExtractionError, UnsupportedFile) as exc:
        mark_failed(job, str(exc))
        return
    except anthropic.RequestTooLargeError as exc:
        mark_failed(job, TOO_LARGE, detail=str(exc))
        return
    except anthropic.BadRequestError as exc:
        mark_failed(job, BAD_FILE, detail=str(exc))
        return
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        mark_failed(job, MISCONFIGURED, detail=str(exc))
        return
    except RETRYABLE as exc:
        if self.request.retries >= self.max_retries:
            mark_failed(job, UNAVAILABLE, detail=repr(exc))
            return
        log.info("Ingestion job %s: %r, retry %s in %ss", job.pk, exc, self.request.retries + 1,
                 backoff_seconds(self.request.retries))
        raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries)) from exc
    except Exception as exc:
        mark_failed(job, UNEXPECTED, detail=repr(exc))
        raise                                       # still logged by Celery (and Sentry, T2.10)
    save_ready(job, extraction, draft)
```

**6. Settings and secrets.** `ANTHROPIC_API_KEY` goes in `.env` (developers) and the server `.env`. `django-environ`'s `read_env` copies `.env` into the process environment, which is where the SDK looks. Never put the key in `settings` or in code. Confirm `.env` is in `.gitignore` (spec §10.3) before the first commit of this branch.

### Tests

The tests never call the network. `extract_syllabus` is replaced with a fake that returns a fixture, or raises the exact SDK error class. SDK 1.x is built on `httpx2`, not `httpx`, so the error objects are built from `httpx2.Request` / `httpx2.Response`.

`apps/ingestion/tests/fixtures.py` (shared with S5-04 and S5-05; shaped like the real extraction of our CSE 311 syllabus):

```python
"""Recorded-style extractions for tests. Shaped like what Claude returned for the real
CSE 311 Fall 2026 syllabus during the S5-03 spike, so tests exercise realistic data."""
from apps.ingestion.schemas import (
    CoursePOContribution,
    ExtractedAssessment,
    ExtractedLO,
    ExtractedLOPOLink,
    SyllabusExtraction,
)

ALL_POS = set(range(1, 12))


def lo(number, description, quote=None):
    return ExtractedLO(number=number, description=description, source_quote=quote or description)


def assessment(name, kind, weight, measures=(), stated=False, max_score=None):
    return ExtractedAssessment(
        name=name, kind=kind, course_weight_percent=weight, max_score=max_score,
        measures_lo_numbers=list(measures), measures_stated_in_document=stated,
        source_quote=f"{name} {weight}%",
    )


def link(lo_number, po_number, weight, stated=False, rationale="Plausible link."):
    return ExtractedLOPOLink(lo_number=lo_number, po_number=po_number, weight=weight,
                             stated_in_document=stated, rationale=rationale)


def cse311(**overrides) -> SyllabusExtraction:
    """The CSE 311 syllabus: 4 LOs, 4 assessments summing to 100, no PO table, suggested links."""
    data = dict(
        is_course_syllabus=True,
        course_code="CSE 311", course_title="Software", credits=3.0, ects=6.0, language="English",
        learning_outcomes=[
            lo(1, "Learn design choices & philosophy behind widely popular SD practices."),
            lo(2, "Learn agile-SD methodology & best practices & the soft skill-set."),
            lo(3, "Apply the skill-set on a team project."),
            lo(4, "Write a term report detailing your experience and exposure."),
        ],
        assessments=[
            assessment("Midterm I", "midterm", 25.0, measures=[1, 2]),
            assessment("Midterm II", "midterm", 25.0, measures=[1, 2]),
            assessment("Attendance & Participation & Preparation", "participation", 10.0, measures=[2]),
            assessment("Project (Presentations, Demo) – Final", "project", 40.0, measures=[3, 4]),
        ],
        course_po_contributions=[],
        lo_po_links=[
            link(1, 1, 3), link(2, 5, 4), link(3, 5, 5), link(3, 6, 4), link(4, 7, 4),
        ],
        warnings=[],
    )
    data.update(overrides)
    return SyllabusExtraction(**data)
```

`apps/ingestion/tests/test_files.py`:

```python
# apps/ingestion/tests/test_files.py — no database, no network
import io

import pytest
from docx import Document
from PIL import Image

from apps.ingestion.files import (
    DOCX,
    JPEG,
    MAX_SYLLABUS_BYTES,
    PDF,
    PNG,
    TEXT,
    WEBP,
    UnsupportedFile,
    check_upload,
    docx_to_text,
    prepare_document,
    sniff_media_type,
)


def image_bytes(fmt: str, size=(100, 50)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize(("head", "expected"), [
    (b"%PDF-1.7\n", PDF),
    (image_bytes("PNG")[:16], PNG),
    (image_bytes("JPEG")[:16], JPEG),
    (image_bytes("WEBP")[:16], WEBP),
])
def test_sniff_by_magic_bytes(head, expected):
    assert sniff_media_type(head) == expected


@pytest.mark.parametrize("head", [b"MZ\x90\x00", b"\x00\x00\x00\x18ftypheic", b"Hello, plain text", b""])
def test_unsupported_types_are_rejected(head):
    with pytest.raises(UnsupportedFile, match="PDF, Word"):
        sniff_media_type(head)


def make_docx(path):
    doc = Document()
    doc.add_paragraph("Learning Outcomes")
    doc.add_paragraph("1. Apply the skill-set on a team project.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Midterm I", "25%"
    merged = table.cell(1, 0).merge(table.cell(1, 1))
    merged.text = "Total 100%"
    doc.add_paragraph("Weekly topics follow.")
    doc.save(path)


def test_docx_text_keeps_reading_order_and_tables(tmp_path):
    make_docx(tmp_path / "s.docx")
    assert docx_to_text(tmp_path / "s.docx") == (
        "Learning Outcomes\n1. Apply the skill-set on a team project.\n"
        "Midterm I | 25%\nTotal 100%\n\nWeekly topics follow."
    )


def test_prepare_docx_becomes_utf8_text(tmp_path):
    make_docx(tmp_path / "s.docx")
    prepared = prepare_document(tmp_path / "s.docx", tmp_path)
    assert prepared.media_type == TEXT
    assert "Midterm I | 25%" in prepared.path.read_text(encoding="utf-8")


def test_sniff_recognises_docx_inside_the_zip(tmp_path):
    make_docx(tmp_path / "s.docx")
    assert sniff_media_type((tmp_path / "s.docx").read_bytes()[:16], path=tmp_path / "s.docx") == DOCX


def test_large_photo_is_downscaled_and_rotated(tmp_path):
    image = Image.new("RGB", (4000, 3000), "white")
    exif = image.getexif()
    exif[0x0112] = 6                                     # EXIF orientation: rotate 90° (portrait phone photo)
    image.save(tmp_path / "photo.jpg", exif=exif)
    prepared = prepare_document(tmp_path / "photo.jpg", tmp_path)
    assert prepared.media_type == JPEG
    with Image.open(prepared.path) as result:
        assert result.size == (1500, 2000)               # rotated upright, long side 2000


def test_pdf_is_passed_through_untouched(tmp_path):
    (tmp_path / "s.pdf").write_bytes(b"%PDF-1.7\nbody")
    prepared = prepare_document(tmp_path / "s.pdf", tmp_path)
    assert (prepared.path, prepared.media_type) == (tmp_path / "s.pdf", PDF)


def test_oversized_file_is_refused(tmp_path):
    big = tmp_path / "big.pdf"
    with big.open("wb") as handle:
        handle.write(b"%PDF-1.7\n")
        handle.truncate(MAX_SYLLABUS_BYTES + 1)
    with pytest.raises(UnsupportedFile, match="20 MB"):
        prepare_document(big, tmp_path)


class FakeUpload(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.size = len(data)


def test_check_upload_accepts_docx_and_rejects_other_zips(tmp_path):
    make_docx(tmp_path / "s.docx")
    assert check_upload(FakeUpload((tmp_path / "s.docx").read_bytes())) == DOCX
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ppt/presentation.xml", "<x/>")
    with pytest.raises(UnsupportedFile):
        check_upload(FakeUpload(buffer.getvalue()))
```

`apps/ingestion/tests/test_tasks.py`:

```python
# apps/ingestion/tests/test_tasks.py — the task end to end, with Claude replaced by a fake
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx2                      # the HTTP library the Anthropic SDK 1.x is built on
import pytest
from celery.exceptions import Retry
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import ProgramOutcome, ProgramOutcomeSet
from apps.core.tests.factories import OfferingFactory, ProgramOutcomeSetFactory, UserFactory
from apps.ingestion import tasks
from apps.ingestion.extraction import ExtractionError
from apps.ingestion.models import IngestionJob
from apps.ingestion.tests.fixtures import cse311
from apps.ingestion.validation import NOT_A_SYLLABUS

PDF = b"%PDF-1.7\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n"


@pytest.fixture
def job(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    offering = OfferingFactory()
    program = offering.course.program
    po_set = (ProgramOutcomeSet.objects.filter(program=program, is_active=True).first()
              or ProgramOutcomeSetFactory(program=program, is_active=True))
    for number in range(1, 12):
        ProgramOutcome.objects.get_or_create(
            po_set=po_set, number=number,
            defaults={"short_name": f"Outcome {number}", "description": f"Official wording of PO {number}."})
    return IngestionJob.objects.create(
        offering=offering, kind=IngestionJob.Kind.SYLLABUS, original_filename="syllabus.pdf",
        file=SimpleUploadedFile("syllabus.pdf", PDF), created_by=UserFactory(),
    )


def fake_response(model="claude-opus-5-5"):
    return SimpleNamespace(model=model, _request_id="req_011CTest",
                           usage=SimpleNamespace(input_tokens=12_000, output_tokens=6_000))


def api_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


def run(job, **kwargs):
    tasks.run_syllabus_extraction.apply(args=[job.pk], **kwargs)
    job.refresh_from_db()
    return job


def test_success_stores_draft_usage_and_cost(job, monkeypatch):
    seen = {}

    def fake_extract(path, media_type, po_list_text):
        seen.update(media_type=media_type, po_list=po_list_text)
        return cse311(), fake_response()

    monkeypatch.setattr(tasks, "extract_syllabus", fake_extract)
    job = run(job)
    assert job.status == IngestionJob.Status.READY
    assert seen["media_type"] == "application/pdf"
    assert seen["po_list"].splitlines()[10] == "PO 11: Official wording of PO 11."
    assert (job.input_tokens, job.output_tokens) == (12_000, 6_000)
    assert job.cost_usd == Decimal("0.1680")              # 12k × $4/M + 6k × $20/M
    assert job.request_id == "req_011CTest" and job.model == "claude-opus-5-5"
    assert job.result["prompt_version"] == tasks.PROMPT_VERSION
    assert len(job.result["draft"]["los"]) == 4
    assert job.warnings == []


def test_extraction_error_fails_with_its_message(job, monkeypatch):
    def refuse(*args):
        raise ExtractionError("The document could not be processed. Please set up the course manually.")

    monkeypatch.setattr(tasks, "extract_syllabus", refuse)
    job = run(job)
    assert job.status == IngestionJob.Status.FAILED
    assert job.error.startswith("The document could not be processed")


def test_not_a_syllabus_fails_but_usage_is_kept(job, monkeypatch):
    menu = cse311(is_course_syllabus=False, learning_outcomes=[], assessments=[], lo_po_links=[])
    monkeypatch.setattr(tasks, "extract_syllabus", lambda *a: (menu, fake_response()))
    job = run(job)
    assert (job.status, job.error) == (IngestionJob.Status.FAILED, NOT_A_SYLLABUS)
    assert job.input_tokens == 12_000                      # we still paid for the call


def test_rate_limit_schedules_a_retry(job, monkeypatch):
    def limited(*args):
        raise api_error(anthropic.RateLimitError, 429)

    monkeypatch.setattr(tasks, "extract_syllabus", limited)
    with pytest.raises(Retry):                             # eager mode raises the retry instead of sleeping
        tasks.run_syllabus_extraction.apply(args=[job.pk])
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.PROCESSING


@pytest.mark.parametrize("error", [
    api_error(anthropic.OverloadedError, 529),
    api_error(anthropic.InternalServerError, 500),
    anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")),
])
def test_last_retry_fails_with_a_friendly_message(job, monkeypatch, error):
    def broken(*args):
        raise error

    monkeypatch.setattr(tasks, "extract_syllabus", broken)
    job = run(job, retries=tasks.MAX_RETRIES)              # pretend this is the 5th attempt
    assert (job.status, job.error) == (IngestionJob.Status.FAILED, tasks.UNAVAILABLE)


def test_bad_request_is_not_retried(job, monkeypatch):
    calls = []

    def bad(*args):
        calls.append(1)
        raise api_error(anthropic.BadRequestError, 400)

    monkeypatch.setattr(tasks, "extract_syllabus", bad)
    job = run(job)
    assert (job.status, job.error, len(calls)) == (IngestionJob.Status.FAILED, tasks.BAD_FILE, 1)


def test_unsupported_file_never_calls_claude(job, monkeypatch):
    job.file.save("photo.heic", SimpleUploadedFile("photo.heic", b"\x00\x00\x00\x18ftypheic"), save=True)
    monkeypatch.setattr(tasks, "extract_syllabus", lambda *a: pytest.fail("Claude must not be called"))
    job = run(job)
    assert job.status == IngestionJob.Status.FAILED and "PDF, Word" in job.error


@pytest.mark.parametrize("status", [IngestionJob.Status.READY, IngestionJob.Status.APPLIED,
                                    IngestionJob.Status.DISCARDED, IngestionJob.Status.FAILED])
def test_finished_jobs_are_left_alone(job, monkeypatch, status):
    IngestionJob.objects.filter(pk=job.pk).update(status=status)
    monkeypatch.setattr(tasks, "extract_syllabus", lambda *a: pytest.fail("must not run"))
    assert run(job).status == status


def test_discard_during_extraction_wins(job, monkeypatch):
    def slow_extract(*args):
        IngestionJob.objects.filter(pk=job.pk).update(status=IngestionJob.Status.DISCARDED)
        return cse311(), fake_response()

    monkeypatch.setattr(tasks, "extract_syllabus", slow_extract)
    assert run(job).status == IngestionJob.Status.DISCARDED


def test_unexpected_error_fails_the_job_and_is_raised(job, monkeypatch):
    def crash(*args):
        raise KeyError("surprise")

    monkeypatch.setattr(tasks, "extract_syllabus", crash)
    with pytest.raises(KeyError):
        tasks.run_syllabus_extraction.apply(args=[job.pk])
    job.refresh_from_db()
    assert (job.status, job.error) == (IngestionJob.Status.FAILED, tasks.UNEXPECTED)


def test_backoff_doubles_and_caps():
    assert [tasks.backoff_seconds(n) for n in range(6)] == [30, 60, 120, 240, 480, 600]
```

`apps/ingestion/tests/test_cost.py`:

```python
from decimal import Decimal

from apps.ingestion.extraction import cost_usd


def test_opus_pricing():
    assert cost_usd("claude-opus-5-5", 1_000_000, 0) == Decimal("4.0000")
    assert cost_usd("claude-opus-5-5", 15_000, 8_000) == Decimal("0.2200")     # a typical syllabus


def test_sonnet_pricing_for_the_cheaper_fallback_plan():
    assert cost_usd("claude-sonnet-5-5", 15_000, 8_000) == Decimal("0.1100")


def test_unknown_model_costs_zero_rather_than_crashing():
    assert cost_usd("some-future-model", 10, 10) == Decimal("0")
```

### Check it works

```bash
uv run pytest apps/ingestion -q
```

Then the real thing, on your laptop with the worker running (S5-02, step 4) and `ANTHROPIC_API_KEY` set:

```python
# uv run python manage.py shell
from django.core.files import File
from apps.catalog.models import CourseOffering
from apps.core.jobs import enqueue_on_commit
from apps.ingestion.models import IngestionJob
from apps.ingestion.tasks import run_syllabus_extraction
from apps.accounts.models import User

offering = CourseOffering.objects.get(course__code="CSE 311", term__code="2026F")
with open("apps/ingestion/evals/syllabi/cse311.pdf", "rb") as f:
    job = IngestionJob.objects.create(offering=offering, kind="syllabus", file=File(f, "s.pdf"),
                                      original_filename="cse311.pdf", created_by=User.objects.filter(is_superuser=True).first())
enqueue_on_commit(run_syllabus_extraction, job.pk)
```

The worker log shows the task. About 30–60 s later, `IngestionJob.objects.get(pk=job.pk)` has `status='ready'`, `cost_usd` around 0.2, a `request_id` beginning `req_`, and `result['draft']['los']` holds the four CSE 311 LOs. Look at the job in Django admin too: that's where you'll debug real failures.

### Done when

- [ ] Spike findings recorded in the PR description
- [ ] T1.2 AC 3 (failures end FAILED with a human message, never a 500): `test_tasks.py` covers every row of the table in step 5
- [ ] T1.2 AC 6 (model, tokens, cost, request id): `test_success_stores_draft_usage_and_cost`
- [ ] Unsupported files never reach Claude: `test_unsupported_file_never_calls_claude`
- [ ] A real job reaches READY in the worker on staging

### Commits and PR

```
Add syllabus schemas from the spec (#S5-03)
Add file sniffing, DOCX conversion and photo downscaling
Add extraction prompt and cost calculation
Add extraction task with retries and friendly failures
```

PR title: **Syllabus extraction service and task (S5-03)**

---

## S5-04 · Validation and derivation: `validate_and_derive`

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S5-04-validation` · **Depends on:** `schemas.py` (Monday mini-PR of S5-03)

### Goal

Claude's answer is a proposal, not data we trust. This story writes the pure functions that check it against our rules (spec §7.6), repair what can be repaired, explain every repair in a warning, and fill in the assessment→LO weights that syllabi almost never state. The output is a `ReviewDraft`: the exact structure the Sprint 6 review screen shows and edits, and the Apply step turns into rows. Person B owns the wizard screens, so B designs the draft they will render.

### Design

**Why a separate `ReviewDraft` instead of editing the Pydantic model.** `SyllabusExtraction` describes what *the model* said, including its mistakes. `ReviewDraft` describes what *we propose to save*. It's renumbered, clamped and derived, and every cell carries an **origin** (`document`, `derived` or `ai_suggested`; the review screen adds `manual` when a human edits a cell), which the review screen turns into the three colours of T1.2. Rows are identified by stable **keys** (`l1`, `a2`) rather than numbers or names, because the instructor can add, delete and rename rows on the review screen before anything exists in the database. Keeping both means we can always show "the document said X, we changed it to Y because Z".

**Why pure.** `derive_draft(extraction, valid_po_numbers)` takes plain data and returns plain data. The tests cover every row of the §7.6 table in milliseconds without a database or the API, which is what spec §7.10 asks for. `validate_and_derive(extraction, offering)` is a three-line wrapper that looks up the PO numbers.

**The derived-weight rule (spec §7.6), in one sentence.** The arrow from an assessment to each LO it measures gets the assessment's **course weight**. So each LO's score is an average of the assessments that measure it, weighted the way the course grade weights them. If any assessment has no course weight, every arrow gets 100, meaning equal weight, because mixing real percentages with a made-up default would make the missing one count arbitrarily.

**Edge rules this guide had to decide** (the spec's table doesn't cover them; each is tested):

| Situation | Rule | Why |
|---|---|---|
| LO numbers have a gap (1, 2, 4) | Renumber 1..n; references to 4 now point to 3 | References follow the LO, not the old number |
| LO number used twice | Renumber; references to the repeated number go to its **first** occurrence; extra warning | Ambiguous: we can't know, so we flag it for the human |
| Course weight 0% (e.g. bonus) | No arrows from it; warning | The database requires arrow weights > 0 (`a_lo_weight_range`) |
| Course weight < 0 or > 100 | Cleared to "unknown"; warning | Impossible values; the human re-enters it |
| Two assessments with the same name | Second becomes "Name (2)" | `uniq_assessment_name` would reject the Apply |
| Same LO→PO pair twice | Keep the first | `uniq_lo_po` would reject the Apply |
| Suggested link with no course-level row for that PO | Kept as is | Only an explicit level caps a suggestion |
| Stated (document) link above the course level | **Not** lowered | We never overrule the document, only the model's guesses |

### Files

| Path | Create/modify | What |
|---|---|---|
| `apps/ingestion/validation.py` | create | `ReviewDraft` and parts, `Origin`, `derive_draft`, `validate_and_derive` |
| `apps/ingestion/tests/fixtures.py` | create or share | Same file as S5-03. Whoever merges first adds it |
| `apps/ingestion/tests/test_validation.py` | create | One test per rule |

### Steps

**1. Write the tests first** (below), one per row of the §7.6 table plus the edge rules above. Commit them failing: `Add validation tests for every §7.6 rule (red)`.

**2. Then `validation.py`.**

```python
"""Check and complete what Claude extracted, before any human sees it (spec §7.6).

`derive_draft` is pure: an extraction and the set of valid PO numbers in, a ReviewDraft out.
`validate_and_derive` is the thin wrapper the Celery task calls; it only looks up the PO numbers.
Nothing here writes to the database. The draft is stored as JSON on the IngestionJob and edited
on the review screen (S6-02) before Apply (S6-03) creates real rows."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from .extraction import ExtractionError
from .schemas import SyllabusExtraction

HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")
WEIGHT_SUM_TOLERANCE = Decimal("1")

NOT_A_SYLLABUS = "This doesn't look like a course syllabus. Upload the course's syllabus, or set the course up manually."
NO_LEARNING_OUTCOMES = ("We couldn't find learning outcomes in this document. Set the course up manually, "
                        "or upload the page that lists them.")


class Origin:
    """Where a value in the review draft came from. Drives the cell colours (spec §8.2).
    The strings match GridCell.origin in apps/outcomes/matrix.py (S2-05)."""
    DOCUMENT = "document"          # read from a table or statement in the syllabus (blue)
    DERIVED = "derived"            # link stated in the document, weight computed by the §7.6 rule (teal)
    AI_SUGGESTED = "ai_suggested"  # proposed by Claude, not in the document (violet)
    MANUAL = "manual"              # typed or changed by a human on the review screen (no colour)


@dataclass
class DraftCourse:
    code: str | None = None
    title: str | None = None
    credits: Decimal | None = None
    ects: Decimal | None = None
    language: str | None = None


@dataclass
class DraftLO:
    key: str                 # stable id inside the draft, e.g. "l1". Never shown to the user
    number: int              # 1..n, contiguous
    description: str
    source_quote: str = ""


@dataclass
class DraftAssessment:
    key: str                 # stable id inside the draft, e.g. "a1" (names can be edited)
    name: str
    kind: str                # one of Assessment.Kind values
    max_score: Decimal
    course_weight: Decimal | None
    source_quote: str = ""


@dataclass
class DraftALO:
    assessment_key: str
    lo_key: str
    weight: Decimal          # 0 < w <= 100
    origin: str              # DERIVED or AI_SUGGESTED from the extraction; MANUAL after a human edit


@dataclass
class DraftLOPO:
    lo_key: str
    po_number: int           # number inside the offering program's active PO set
    weight: int              # 1..5
    origin: str              # DOCUMENT or AI_SUGGESTED from the extraction; MANUAL after a human edit
    rationale: str = ""


def _dec(v):
    return None if v is None else Decimal(str(v))


@dataclass
class ReviewDraft:
    course: DraftCourse
    los: list[DraftLO]
    assessments: list[DraftAssessment]
    a_lo: list[DraftALO]
    lo_po: list[DraftLOPO]
    course_po_levels: dict[int, int] = field(default_factory=dict)   # PO number -> 0..5
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        """JSON-safe dict for IngestionJob.result: Decimal -> str, dict keys -> str."""
        def conv(v):
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, dict):
                return {str(k): conv(x) for k, x in v.items()}
            if isinstance(v, list):
                return [conv(x) for x in v]
            return v
        return conv(asdict(self))

    @classmethod
    def from_json(cls, data: dict) -> ReviewDraft:
        c = data.get("course") or {}
        return cls(
            course=DraftCourse(code=c.get("code"), title=c.get("title"), credits=_dec(c.get("credits")),
                               ects=_dec(c.get("ects")), language=c.get("language")),
            los=[DraftLO(**lo) for lo in data["los"]],
            assessments=[DraftAssessment(key=a["key"], name=a["name"], kind=a["kind"],
                                         max_score=Decimal(a["max_score"]),
                                         course_weight=_dec(a["course_weight"]),
                                         source_quote=a.get("source_quote", ""))
                         for a in data["assessments"]],
            a_lo=[DraftALO(x["assessment_key"], x["lo_key"], Decimal(x["weight"]), x["origin"])
                  for x in data["a_lo"]],
            lo_po=[DraftLOPO(x["lo_key"], int(x["po_number"]), int(x["weight"]), x["origin"],
                             x.get("rationale", "")) for x in data["lo_po"]],
            course_po_levels={int(k): int(v) for k, v in (data.get("course_po_levels") or {}).items()},
            warnings=list(data.get("warnings") or []),
        )


def to_decimal(value: float | None) -> Decimal | None:
    """Floats from JSON -> Decimal via str, so 25.0 stays 25.0 and never 25.000000000000001."""
    return None if value is None else Decimal(str(value)).quantize(TWO_PLACES)


def derive_draft(extraction: SyllabusExtraction, valid_po_numbers: set[int]) -> ReviewDraft:
    """Apply every row of the §7.6 table. Raises ExtractionError for the two fatal cases."""
    if not extraction.is_course_syllabus:
        raise ExtractionError(NOT_A_SYLLABUS)
    if not extraction.learning_outcomes:
        raise ExtractionError(NO_LEARNING_OUTCOMES)

    warnings: list[str] = []

    # 1. Learning outcomes: renumber 1..n in document order if the numbers are odd.
    original_numbers = [lo.number for lo in extraction.learning_outcomes]
    expected = list(range(1, len(original_numbers) + 1))
    renumber: dict[int, int] = {}
    for new_number, old_number in enumerate(original_numbers, start=1):
        renumber.setdefault(old_number, new_number)          # a duplicated number keeps its first position
    if original_numbers != expected:
        warnings.append(
            f"Learning outcome numbers in the document were {', '.join(map(str, original_numbers))}; "
            f"we renumbered them 1–{len(expected)} in the order they appear.")
        if len(set(original_numbers)) != len(original_numbers):
            warnings.append("Some learning outcome numbers were used twice. References to a repeated "
                            "number were linked to its first occurrence: check the mapping grids.")
    los = [DraftLO(f"l{n}", n, lo.description.strip(), lo.source_quote.strip())
           for n, lo in enumerate(extraction.learning_outcomes, start=1)]
    key_of = {lo.number: lo.key for lo in los}                 # new LO number -> draft key

    # 2. Assessments: defaults, ranges, unique names.
    assessments: list[DraftAssessment] = []
    used_names: set[str] = set()
    for index, a in enumerate(extraction.assessments, start=1):
        name = a.name.strip() or f"Assessment {index}"
        if name.casefold() in used_names:
            new_name = f"{name} ({index})"
            warnings.append(f"Two assessments were called “{name}”; the second is now “{new_name}”.")
            name = new_name
        used_names.add(name.casefold())

        max_score = to_decimal(a.max_score)
        if max_score is None or max_score <= 0:
            if max_score is not None:
                warnings.append(f"{name}: the maximum score {a.max_score} is not positive; we used 100.")
            max_score = HUNDRED

        weight = to_decimal(a.course_weight_percent)
        if weight is not None and not (0 <= weight <= HUNDRED):
            warnings.append(f"{name}: a course weight of {a.course_weight_percent}% is impossible; we cleared it.")
            weight = None
        assessments.append(DraftAssessment(key=f"a{index}", name=name, kind=a.kind, max_score=max_score,
                                           course_weight=weight, source_quote=a.source_quote.strip()))

    weights = [a.course_weight for a in assessments]
    if assessments and all(w is not None for w in weights):
        total = sum(weights, Decimal("0"))
        if abs(total - HUNDRED) > WEIGHT_SUM_TOLERANCE:
            warnings.append(f"Course weights add up to {total.normalize():f}%, not 100%.")
    elif any(w is None for w in weights):
        missing = [a.name for a in assessments if a.course_weight is None]
        warnings.append(f"No course weight found for: {', '.join(missing)}. "
                        "Every assessment counts equally towards its learning outcomes until you set one.")

    # 3. Assessment → LO arrows, with the derived weight rule.
    all_weights_known = bool(assessments) and all(w is not None for w in weights)
    a_lo: list[DraftALO] = []
    for source, draft in zip(extraction.assessments, assessments, strict=True):
        if all_weights_known and draft.course_weight == 0:
            if source.measures_lo_numbers:
                warnings.append(f"{draft.name} is worth 0% of the grade, so it feeds no learning outcome.")
            continue
        arrow_weight = draft.course_weight if all_weights_known else HUNDRED
        origin = Origin.DERIVED if source.measures_stated_in_document else Origin.AI_SUGGESTED
        seen: set[int] = set()
        for old_number in source.measures_lo_numbers:
            lo_number = renumber.get(old_number)
            if lo_number is None:
                warnings.append(f"{draft.name} refers to learning outcome {old_number}, which doesn't exist. "
                                "We removed that link.")
                continue
            if lo_number in seen:
                continue
            seen.add(lo_number)
            a_lo.append(DraftALO(draft.key, key_of[lo_number], arrow_weight, origin))

    # 4. Course-level PO contribution table (Bologna syllabi).
    course_po_levels: dict[int, int] = {}
    for row in extraction.course_po_contributions:
        if row.po_number not in valid_po_numbers:
            warnings.append(f"The course contribution table mentions PO {row.po_number}, "
                            "which is not one of the program's outcomes. Ignored.")
            continue
        course_po_levels[row.po_number] = min(max(row.level, 0), 5)

    # 5. LO → PO links.
    lo_po: list[DraftLOPO] = []
    seen_pairs: set[tuple[int, int]] = set()
    for link in extraction.lo_po_links:
        lo_number = renumber.get(link.lo_number)
        if lo_number is None:
            warnings.append(f"A program outcome link refers to learning outcome {link.lo_number}, "
                            "which doesn't exist. Removed.")
            continue
        if link.po_number not in valid_po_numbers:
            warnings.append(f"LO {lo_number} was linked to PO {link.po_number}, which is not one of "
                            "the program's outcomes. Removed.")
            continue
        if (lo_number, link.po_number) in seen_pairs:
            warnings.append(f"LO {lo_number} → PO {link.po_number} appeared twice; we kept the first.")
            continue
        weight = link.weight
        if not 1 <= weight <= 5:
            clamped = min(max(weight, 1), 5)
            warnings.append(f"LO {lo_number} → PO {link.po_number} had weight {weight}; weights are 1–5, "
                            f"so we used {clamped}.")
            weight = clamped
        origin = Origin.DOCUMENT if link.stated_in_document else Origin.AI_SUGGESTED
        level = course_po_levels.get(link.po_number)
        if origin == Origin.AI_SUGGESTED and level is not None and weight > level:
            if level == 0:
                warnings.append(f"Suggested link LO {lo_number} → PO {link.po_number} removed: the syllabus "
                                f"says the course does not contribute to PO {link.po_number}.")
                continue
            warnings.append(f"Suggested link LO {lo_number} → PO {link.po_number} lowered from {weight} to "
                            f"{level}, the course's stated contribution level.")
            weight = level
        seen_pairs.add((lo_number, link.po_number))
        lo_po.append(DraftLOPO(key_of[lo_number], link.po_number, weight, origin, link.rationale.strip()))

    # 6. Coverage hints, the same ideas as mapping lint L001 and L003.
    fed = {cell.lo_key for cell in a_lo}
    for lo in los:
        if lo.key not in fed:
            warnings.append(f"LO {lo.number} is not assessed by anything yet.")
    feeding = {cell.assessment_key for cell in a_lo}
    for a in assessments:
        if a.key not in feeding and not (all_weights_known and a.course_weight == 0):
            warnings.append(f"{a.name} doesn't measure any learning outcome yet, so its grades won't count.")

    warnings.extend(f"From the document reader: {w}" for w in extraction.warnings)

    return ReviewDraft(
        course=DraftCourse(code=extraction.course_code, title=extraction.course_title,
                           credits=to_decimal(extraction.credits), ects=to_decimal(extraction.ects),
                           language=extraction.language),
        los=los, assessments=assessments, a_lo=a_lo, lo_po=lo_po,
        course_po_levels=course_po_levels, warnings=warnings,
    )


def validate_and_derive(extraction: SyllabusExtraction, offering) -> ReviewDraft:
    """The task's entry point: looks up the active PO numbers of the offering's program."""
    from apps.catalog.selectors import active_po_set

    po_set = active_po_set(offering.course.program)
    valid = set(po_set.outcomes.values_list("number", flat=True))
    return derive_draft(extraction, valid)
```

> `validation.py` imports `ExtractionError` from `extraction.py`. If S5-03 hasn't merged yet, add a two-line `extraction.py` containing only `class ExtractionError(Exception): ...`. S5-03 then replaces it with the full file.

**3. Hand-off to Sprint 6.** The job stores `result["draft"] = draft.to_json()`. S6-02 rebuilds it with `ReviewDraft.from_json(job.result["draft"])`, edits it, and saves it back with `ingestion.services.save_review`. S6-03's `apply_syllabus_job` reads it to create rows. The mapping from draft to models is direct:

| Draft | Model row |
|---|---|
| `DraftLO` | `LearningOutcome(number, description, source="syllabus")` |
| `DraftAssessment` | `Assessment(name, kind, max_score, course_weight, position=index)` |
| `DraftALO` | `AssessmentLOWeight(weight)`; assessment found by `assessment_key`, LO by `lo_key` |
| `DraftLOPO` | `LOPOWeight(weight, source=..., rationale)`; LO found by `lo_key`. `source` is `syllabus` for `document`, `ai_suggested` for `ai_suggested`, `manual` for `manual` (S6-03) |

### Tests

`apps/ingestion/tests/test_validation.py`:

```python
import json
from decimal import Decimal

import pytest

from apps.ingestion.extraction import ExtractionError
from apps.ingestion.tests.fixtures import ALL_POS, assessment, cse311, link, lo
from apps.ingestion.schemas import CoursePOContribution
from apps.ingestion.validation import (
    NO_LEARNING_OUTCOMES,
    NOT_A_SYLLABUS,
    Origin,
    ReviewDraft,
    derive_draft,
)


def _number(draft):
    return {lo.key: lo.number for lo in draft.los}


def cells(draft):
    """{(assessment key, LO number): (weight, origin)}: LO numbers read better in assertions than keys."""
    n = _number(draft)
    return {(c.assessment_key, n[c.lo_key]): (c.weight, c.origin) for c in draft.a_lo}


def links(draft):
    n = _number(draft)
    return {(n[c.lo_key], c.po_number): (c.weight, c.origin) for c in draft.lo_po}


def test_clean_extraction_has_no_warnings():
    draft = derive_draft(cse311(), ALL_POS)
    assert draft.warnings == []
    assert [lo.number for lo in draft.los] == [1, 2, 3, 4]
    assert [a.key for a in draft.assessments] == ["a1", "a2", "a3", "a4"]
    assert draft.assessments[0].max_score == Decimal("100")


def test_not_a_syllabus_fails():
    with pytest.raises(ExtractionError, match="doesn't look like a course syllabus") as info:
        derive_draft(cse311(is_course_syllabus=False, learning_outcomes=[], assessments=[], lo_po_links=[]), ALL_POS)
    assert str(info.value) == NOT_A_SYLLABUS


def test_no_learning_outcomes_fails():
    with pytest.raises(ExtractionError) as info:
        derive_draft(cse311(learning_outcomes=[], lo_po_links=[]), ALL_POS)
    assert str(info.value) == NO_LEARNING_OUTCOMES


def test_gapped_lo_numbers_are_renumbered_and_references_follow():
    extraction = cse311(
        learning_outcomes=[lo(1, "One"), lo(2, "Two"), lo(4, "Four")],
        assessments=[assessment("Final", "final", 100.0, measures=[4], stated=True)],
        lo_po_links=[link(4, 3, 5, stated=True)],
    )
    draft = derive_draft(extraction, ALL_POS)
    assert [lo.number for lo in draft.los] == [1, 2, 3]
    assert cells(draft) == {("a1", 3): (Decimal("100.00"), Origin.DERIVED)}
    assert links(draft) == {(3, 3): (5, Origin.DOCUMENT)}
    assert any("renumbered" in w for w in draft.warnings)


def test_duplicate_lo_numbers_warn_twice():
    extraction = cse311(learning_outcomes=[lo(1, "A"), lo(1, "B"), lo(2, "C")], lo_po_links=[],
                        assessments=[assessment("Final", "final", 100.0, measures=[1, 2])])
    draft = derive_draft(extraction, ALL_POS)
    assert [lo.description for lo in draft.los] == ["A", "B", "C"]
    assert any("used twice" in w for w in draft.warnings)


def test_reference_to_missing_lo_is_dropped():
    extraction = cse311(assessments=[assessment("Final", "final", 100.0, measures=[1, 9])])
    draft = derive_draft(extraction, ALL_POS)
    assert ("a1", 1) in cells(draft)
    assert all(lo_number != 9 for _, lo_number in cells(draft))
    assert any("learning outcome 9, which doesn't exist" in w for w in draft.warnings)


def test_po_outside_active_set_is_dropped():
    draft = derive_draft(cse311(lo_po_links=[link(1, 12, 3), link(1, 2, 3)]), ALL_POS)
    assert links(draft) == {(1, 2): (3, Origin.AI_SUGGESTED)}
    assert any("PO 12" in w for w in draft.warnings)


@pytest.mark.parametrize(("given", "expected"), [(0, 1), (-2, 1), (6, 5), (9, 5)])
def test_lo_po_weight_is_clamped(given, expected):
    draft = derive_draft(cse311(lo_po_links=[link(1, 2, given, stated=True)]), ALL_POS)
    assert links(draft)[(1, 2)] == (expected, Origin.DOCUMENT)
    assert any("weights are 1–5" in w for w in draft.warnings)


def test_suggestion_lowered_to_course_level():
    extraction = cse311(
        course_po_contributions=[CoursePOContribution(po_number=5, level=3),
                                 CoursePOContribution(po_number=6, level=0)],
        lo_po_links=[link(3, 5, 5), link(3, 6, 4), link(2, 5, 5, stated=True)],
    )
    draft = derive_draft(extraction, ALL_POS)
    assert links(draft)[(3, 5)] == (3, Origin.AI_SUGGESTED)            # lowered 5 → 3
    assert (3, 6) not in links(draft)                               # level 0 → removed
    assert links(draft)[(2, 5)] == (5, Origin.DOCUMENT)             # stated links are never lowered
    assert draft.course_po_levels == {5: 3, 6: 0}


def test_course_weights_not_summing_to_100_warn_but_keep():
    extraction = cse311(assessments=[assessment("Midterm", "midterm", 30.0, [1]),
                                     assessment("Final", "final", 60.0, [2, 3, 4])])
    draft = derive_draft(extraction, ALL_POS)
    assert [a.course_weight for a in draft.assessments] == [Decimal("30.00"), Decimal("60.00")]
    assert "Course weights add up to 90%, not 100%." in draft.warnings


def test_course_weights_within_one_percent_do_not_warn():
    extraction = cse311(assessments=[assessment("Midterm", "midterm", 33.3, [1, 2]),
                                     assessment("Final", "final", 66.6, [3, 4])])
    draft = derive_draft(extraction, ALL_POS)
    assert not any("add up to" in w for w in draft.warnings)


def test_missing_max_score_defaults_to_100():
    extraction = cse311(assessments=[assessment("Quiz", "quiz", 100.0, [1, 2, 3, 4], max_score=None),
                                     ])
    assert derive_draft(extraction, ALL_POS).assessments[0].max_score == Decimal("100")


def test_explicit_max_score_is_kept():
    extraction = cse311(assessments=[assessment("Quiz", "quiz", 100.0, [1, 2, 3, 4], max_score=20.0)])
    assert derive_draft(extraction, ALL_POS).assessments[0].max_score == Decimal("20.00")


def test_derived_weight_is_the_course_weight():
    draft = derive_draft(cse311(), ALL_POS)
    assert cells(draft) == {
        ("a1", 1): (Decimal("25.00"), Origin.AI_SUGGESTED), ("a1", 2): (Decimal("25.00"), Origin.AI_SUGGESTED),
        ("a2", 1): (Decimal("25.00"), Origin.AI_SUGGESTED), ("a2", 2): (Decimal("25.00"), Origin.AI_SUGGESTED),
        ("a3", 2): (Decimal("10.00"), Origin.AI_SUGGESTED),
        ("a4", 3): (Decimal("40.00"), Origin.AI_SUGGESTED), ("a4", 4): (Decimal("40.00"), Origin.AI_SUGGESTED),
    }


def test_stated_measures_are_marked_derived():
    extraction = cse311(assessments=[assessment("Final", "final", 100.0, [1, 2, 3, 4], stated=True)])
    assert {origin for _, origin in cells(derive_draft(extraction, ALL_POS)).values()} == {Origin.DERIVED}


def test_missing_course_weights_mean_equal_arrows():
    extraction = cse311(assessments=[assessment("Midterm", "midterm", 40.0, [1, 2]),
                                     assessment("Project", "project", None, [3, 4])])
    draft = derive_draft(extraction, ALL_POS)
    assert {w for w, _ in cells(draft).values()} == {Decimal("100")}
    assert any("No course weight found for: Project" in w for w in draft.warnings)


def test_zero_weight_assessment_feeds_nothing():
    extraction = cse311(assessments=[assessment("Bonus", "other", 0.0, [1]),
                                     assessment("Final", "final", 100.0, [1, 2, 3, 4])])
    draft = derive_draft(extraction, ALL_POS)
    assert all(key != "a1" for key, _ in cells(draft))
    assert any("worth 0%" in w for w in draft.warnings)


def test_unassessed_lo_and_unused_assessment_are_flagged():
    extraction = cse311(assessments=[assessment("Midterm", "midterm", 50.0, [1, 2]),
                                     assessment("Quiz", "quiz", 50.0, [])])
    draft = derive_draft(extraction, ALL_POS)
    assert "LO 3 is not assessed by anything yet." in draft.warnings
    assert "Quiz doesn't measure any learning outcome yet, so its grades won't count." in draft.warnings


def test_duplicate_assessment_names_are_made_unique():
    extraction = cse311(assessments=[assessment("Quiz", "quiz", 50.0, [1, 2]),
                                     assessment("quiz", "quiz", 50.0, [3, 4])])
    draft = derive_draft(extraction, ALL_POS)
    assert [a.name for a in draft.assessments] == ["Quiz", "quiz (2)"]


def test_model_warnings_are_passed_through():
    draft = derive_draft(cse311(warnings=["The weights table is blurry."]), ALL_POS)
    assert draft.warnings[-1] == "From the document reader: The weights table is blurry."


def test_draft_survives_a_json_round_trip():
    draft = derive_draft(cse311(), ALL_POS)
    assert ReviewDraft.from_json(json.loads(json.dumps(draft.to_json()))) == draft
```

### Check it works

```bash
uv run pytest apps/ingestion/tests/test_validation.py -q      # 24 passed, well under a second
```

Then feed it the real spike output from S5-03:

```python
# uv run python manage.py shell   (after a job reached READY)
from apps.ingestion.models import IngestionJob
from apps.ingestion.validation import ReviewDraft
draft = ReviewDraft.from_json(IngestionJob.objects.latest("created_at").result["draft"])
for cell in draft.a_lo: print(cell)               # CSE 311: a1 → l1, l2 at 25.00 …
print(draft.warnings)
```

### Done when

- [ ] Every row of the §7.6 table has a test: renumbering, missing LO reference, PO outside the set, clamp 1–5, suggestion over the course level (lowered and level-0 removal), weights ≠ 100, missing max score, not a syllabus, no LOs
- [ ] Derivation tests: course weight → arrow weight; missing weights → 100
- [ ] `ReviewDraft` survives a JSON round trip
- [ ] The red test commit comes before the green code commit in the history

### Commits and PR

```
Add validation tests for every §7.6 rule (red)
Add ReviewDraft and derive_draft (green)
Handle zero-weight and duplicate assessments
```

PR title: **Validate and derive syllabus extractions (S5-04)**

---

## S5-05 · Eval set and `eval_extraction`

**Points:** 2 · **Owner:** Person A (+ one other person for labelling) · **Branch:** `feature/S5-05-eval` · **Depends on:** S5-03

### Goal

Measure the extraction instead of eyeballing it (spec §7.9). That means six documents with hand-labelled correct answers, and a command that runs each one *N* times against the live API and prints accuracy against the targets. It's run when the prompt or model changes, before each checkpoint, and before the demo. **Never in CI**: it costs money and needs the key.

### The eval set

| File in `apps/ingestion/evals/syllabi/` | Why it's in the set |
|---|---|
| `cse311.pdf` | Our own syllabus: 4 LOs, assessment table, no PO mapping (pure suggestion case) |
| `bologna_table.pdf` | An Acıbadem OBS course page printed to PDF that has the "contribution to program outcomes" table (tests the course-level cap) |
| `turkish.pdf` | A Turkish-language syllabus (answers must stay in Turkish) |
| `photo.jpg` | A phone photo of a printed syllabus page, taken at a slight angle (image path, EXIF rotation) |
| `word.docx` | A syllabus in Word with the weights in a table (DOCX path) |
| `menu.pdf` | A restaurant menu: **must be rejected** (T1.2 AC 4) |

Public course pages and our own syllabus only. No document with student data goes in this folder, and it is committed to a public repository.

### Gold-file format

One JSON file per document in `apps/ingestion/evals/expected/`, written **by hand by two people who agree on it** (spec §7.9). The gold file is the claim "this is what a careful human reads in the document". Disagreements between the two labellers are themselves a finding: write them in `notes`.

| Key | Required | Meaning |
|---|---|---|
| `file` | yes | Name in `syllabi/` |
| `is_course_syllabus` | yes | `false` only for negative examples; then nothing else is needed |
| `course_code` | no | For a human reading the file |
| `learning_outcomes` | yes | LO texts in document order (matched by similarity ≥ 0.8, so small wording differences are fine) |
| `assessments` | yes | `name` + `course_weight_percent` (or `null` if the document has none) |
| `stated_lo_po_links` | yes | Links **printed in the document**: `{"lo", "po", "weight"}`. Empty list if none |
| `human_lo_po_links` | no | The labellers' own LO→PO mapping, used only for "suggestion agreement" (report only) |
| `labelled_by`, `notes` | yes | Who labelled it and anything they disagreed on |

`apps/ingestion/evals/expected/cse311.json`, labelled from the real Fall 2026 syllabus:

```json
{
  "file": "cse311.pdf",
  "is_course_syllabus": true,
  "course_code": "CSE 311",
  "learning_outcomes": [
    "Learn design choices & philosophy behind widely popular SD practices.",
    "Learn agile-SD methodology & best practices & the soft skill-set.",
    "Apply the skill-set on a team project.",
    "Write a term report detailing your experience and exposure."
  ],
  "assessments": [
    {"name": "Midterm I", "course_weight_percent": 25},
    {"name": "Midterm II", "course_weight_percent": 25},
    {"name": "Attendance & Participation & Preparation", "course_weight_percent": 10},
    {"name": "Project (Presentations, Demo) – Final", "course_weight_percent": 40}
  ],
  "stated_lo_po_links": [],
  "human_lo_po_links": [],
  "labelled_by": ["Person A", "Person B"],
  "notes": "No LO→PO table in the document, so every link is a suggestion. Fill human_lo_po_links after the team maps CSE 311 by hand in the app; until then suggestion agreement shows '—'."
}
```

`apps/ingestion/evals/expected/menu.json`:

```json
{
  "file": "menu.pdf",
  "is_course_syllabus": false,
  "labelled_by": ["Person A", "Person C"],
  "notes": "Negative example: any run that returns learning outcomes is a failure."
}
```

### Files

| Path | Create/modify | What |
|---|---|---|
| `apps/ingestion/evals/syllabi/*` | create | The six documents |
| `apps/ingestion/evals/expected/*.json` | create | Gold files |
| `apps/ingestion/evals/__init__.py`, `metrics.py` | create | Pure scoring functions |
| `apps/ingestion/management/__init__.py`, `management/commands/__init__.py`, `management/commands/eval_extraction.py` | create | The command |
| `apps/ingestion/tests/test_eval_metrics.py` | create | Tests for the scoring maths (no API) |
| `docs/process/sprint-05/eval.md` | create | First results table |

### Steps

**1. The scoring functions.** These are pure and tested, because a wrong metric is worse than none. LOs are matched with `difflib` similarity ≥ 0.8 after normalising, so "1. Apply the skill-set on a team project" matches "Apply the skill-set on a team project." The matching is greedy and one-to-one: one found LO can't satisfy two expected LOs, which would inflate recall.

```python
"""Scoring one extraction against a hand-labelled gold file (spec §7.9). Pure: no API, no database."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from statistics import mean

from apps.ingestion.schemas import SyllabusExtraction

LO_SIMILARITY = 0.8
NAME_SIMILARITY = 0.8
WEIGHT_TOLERANCE = 0.5          # percentage points


def norm(text: str) -> str:
    """Lower-case, drop leading numbering like '1.' or 'a)', collapse spaces and punctuation."""
    text = re.sub(r"^\s*(\d+|[a-z])[.)]\s*", "", text.casefold())
    return " ".join(re.sub(r"[^\w%]+", " ", text).split())


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def greedy_match(expected: list[str], found: list[str], threshold: float) -> list[tuple[int, int]]:
    """Pair each expected item with at most one found item, best-similarity pairs first."""
    pairs = sorted(
        ((similarity(e, f), i, j) for i, e in enumerate(expected) for j, f in enumerate(found)),
        reverse=True,
    )
    used_e: set[int] = set()
    used_f: set[int] = set()
    matched = []
    for score, i, j in pairs:
        if score < threshold:
            break
        if i in used_e or j in used_f:
            continue
        used_e.add(i)
        used_f.add(j)
        matched.append((i, j))
    return matched


def ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


@dataclass(frozen=True)
class RunScore:
    syllabus: str
    run: int
    correct_kind: bool                      # syllabus recognised as syllabus (or a non-syllabus rejected)
    lo_recall: float | None
    lo_precision: float | None
    assessment_recall: float | None
    weight_accuracy: float | None
    stated_mapping_accuracy: float | None
    suggestion_agreement: float | None
    lo_signature: tuple[str, ...]           # for the stability check across runs


def score_run(gold: dict, extraction: SyllabusExtraction, *, syllabus: str, run: int) -> RunScore:
    if not gold["is_course_syllabus"]:
        return RunScore(syllabus, run, not extraction.is_course_syllabus, None, None, None, None, None, None, ())

    expected_los = gold["learning_outcomes"]
    found_los = [lo.description for lo in extraction.learning_outcomes]
    lo_pairs = greedy_match(expected_los, found_los, LO_SIMILARITY)

    expected_as = gold["assessments"]
    found_as = extraction.assessments
    as_pairs = greedy_match([a["name"] for a in expected_as], [a.name for a in found_as], NAME_SIMILARITY)
    weighted = [(expected_as[i], found_as[j]) for i, j in as_pairs
                if expected_as[i].get("course_weight_percent") is not None]
    weights_ok = sum(
        found.course_weight_percent is not None
        and abs(found.course_weight_percent - exp["course_weight_percent"]) <= WEIGHT_TOLERANCE
        for exp, found in weighted
    )

    expected_stated = {(l["lo"], l["po"]): l["weight"] for l in gold.get("stated_lo_po_links", [])}
    found_stated = {(l.lo_number, l.po_number): l.weight for l in extraction.lo_po_links if l.stated_in_document}
    keys = set(expected_stated) | set(found_stated)
    stated_ok = sum(expected_stated.get(k) == found_stated.get(k) for k in keys)

    human = {(l["lo"], l["po"]): l["weight"] for l in gold.get("human_lo_po_links", [])}
    suggested = {(l.lo_number, l.po_number): l.weight for l in extraction.lo_po_links if not l.stated_in_document}
    shared = set(human) & set(suggested)
    agree = sum(abs(human[k] - suggested[k]) <= 1 for k in shared)

    return RunScore(
        syllabus=syllabus, run=run,
        correct_kind=extraction.is_course_syllabus,
        lo_recall=ratio(len(lo_pairs), len(expected_los)),
        lo_precision=ratio(len(lo_pairs), len(found_los)),
        assessment_recall=ratio(len(as_pairs), len(expected_as)),
        weight_accuracy=ratio(weights_ok, len(weighted)),
        stated_mapping_accuracy=ratio(stated_ok, len(keys)),
        suggestion_agreement=ratio(agree, len(shared)),
        lo_signature=tuple(norm(d) for d in found_los),
    )


def is_stable(runs: list[RunScore]) -> bool:
    """Same LO list (after normalising) in every run."""
    return len({r.lo_signature for r in runs}) <= 1


def average(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None
```

**2. The command.** It calls `extract_syllabus` directly, without the task, so the eval measures the *model plus prompt*, not our retry plumbing. It prints a coloured table with each metric against its target from §7.9, and optionally writes JSON for the report.

```python
# apps/ingestion/management/commands/eval_extraction.py
"""Measure syllabus extraction against hand-labelled answers (spec §7.9).

    uv run python manage.py eval_extraction --runs 3
    uv run python manage.py eval_extraction --only cse311 --runs 1 --out docs/process/sprint-05/eval.json

Calls the real Claude API: about $0.20–0.35 per syllabus per run. Not part of CI."""
import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Program
from apps.catalog.selectors import active_po_set
from apps.ingestion.evals.metrics import average, is_stable, score_run
from apps.ingestion.extraction import ExtractionError, cost_usd, extract_syllabus
from apps.ingestion.files import prepare_document

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals"
METRICS = [
    ("LO recall", "lo_recall", 1.0),
    ("LO precision", "lo_precision", 1.0),
    ("Assessment recall", "assessment_recall", 1.0),
    ("Course weight accuracy", "weight_accuracy", 0.95),
    ("Stated mapping accuracy", "stated_mapping_accuracy", 1.0),
    ("Suggestion agreement", "suggestion_agreement", None),     # report only
]


def pct(value):
    return "—" if value is None else f"{value * 100:.0f}%"


class Command(BaseCommand):
    help = "Run the extraction eval set against the live Claude API and print accuracy per syllabus."

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=3)
        parser.add_argument("--only", help="Run a single gold file, by name without .json")
        parser.add_argument("--program", default="CSE", help="Program whose active POs are sent")
        parser.add_argument("--out", help="Also write the raw results as JSON to this path")

    def handle(self, *args, runs, only, program, out, **options):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise CommandError("ANTHROPIC_API_KEY is not set. Put it in .env (never commit it).")
        golds = sorted((EVAL_DIR / "expected").glob("*.json"))
        if only:
            golds = [g for g in golds if g.stem == only]
        if not golds:
            raise CommandError("No gold files found in apps/ingestion/evals/expected/.")
        try:
            po_set = active_po_set(Program.objects.get(code=program))
        except Program.DoesNotExist as exc:
            raise CommandError(f"No program {program!r}. Run migrations / seed_demo first.") from exc
        po_list = "\n".join(f"PO {po.number}: {po.description}" for po in po_set.outcomes.order_by("number"))

        self.stdout.write(f"Model {settings.ANTHROPIC_MODEL} · {len(golds)} syllabi × {runs} runs\n")
        report, total_cost = [], Decimal("0")
        for gold_path in golds:
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            scores, failures = [], []
            for run in range(1, runs + 1):
                with tempfile.TemporaryDirectory() as workdir:
                    document = prepare_document(EVAL_DIR / "syllabi" / gold["file"], Path(workdir))
                    try:
                        extraction, response = extract_syllabus(document.path, document.media_type, po_list)
                    except ExtractionError as exc:
                        failures.append(str(exc))
                        continue
                usage = response.usage
                total_cost += cost_usd(response.model or "", usage.input_tokens, usage.output_tokens)
                scores.append(score_run(gold, extraction, syllabus=gold_path.stem, run=run))
            report.append(self._print_syllabus(gold_path.stem, gold, scores, failures))

        self.stdout.write(f"\nTotal cost of this eval: ${total_cost:.2f}")
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps({
                "model": settings.ANTHROPIC_MODEL, "runs": runs, "cost_usd": str(total_cost), "results": report,
            }, indent=2), encoding="utf-8")
            self.stdout.write(f"Results written to {out}")

    def _print_syllabus(self, name, gold, scores, failures):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{name}"))
        for message in failures:
            self.stdout.write(self.style.WARNING(f"  run failed: {message}"))
        if not gold["is_course_syllabus"]:
            # For a non-syllabus, a refusal-style failure ("doesn't look like a syllabus") is a pass too.
            correct = sum(s.correct_kind for s in scores) + len(failures)
            total = len(scores) + len(failures)
            line = f"  rejected as not a syllabus: {correct}/{total}"
            self.stdout.write(self.style.SUCCESS(line) if correct == total else self.style.ERROR(line))
            return {"syllabus": name, "rejected": correct, "runs": total}

        row = {"syllabus": name, "runs": len(scores), "failed_runs": len(failures)}
        for label, attr, target in METRICS:
            value = average([getattr(s, attr) for s in scores])
            row[attr] = value
            text = f"  {label:<26} {pct(value):>5}"
            if target is not None and value is not None:
                text += f"   (target {pct(target)})"
                style = self.style.SUCCESS if value >= target else self.style.ERROR
                self.stdout.write(style(text))
            else:
                self.stdout.write(text)
        row["stable"] = is_stable(scores)
        self.stdout.write(f"  {'Stable across runs':<26} {'yes' if row['stable'] else 'NO'}")
        return row
```

**3. Label, run, record.** Label the six gold files in pairs (about 15 minutes each). Then:

```bash
uv run python manage.py eval_extraction --runs 3 --out docs/process/sprint-05/eval.json
```

Expected cost: 6 files × 3 runs × ~$0.25 ≈ **$4.50**. Copy the printed table into `docs/process/sprint-05/eval.md` with the date, model and `PROMPT_VERSION`. If a metric misses its target, write down *why*: read the extraction, find the pattern, and decide whether it's a prompt problem or a gold-file mistake. Don't tune the prompt to one document. Any prompt change bumps `PROMPT_VERSION` and gets a fresh full run.

### Tests

`apps/ingestion/tests/test_eval_metrics.py`:

```python
# apps/ingestion/tests/test_eval_metrics.py — the eval's own maths, tested without calling Claude
import pytest

from apps.ingestion.evals.metrics import greedy_match, is_stable, norm, score_run
from apps.ingestion.tests.fixtures import assessment, cse311, link, lo

GOLD = {
    "is_course_syllabus": True,
    "learning_outcomes": [
        "Learn design choices & philosophy behind widely popular SD practices.",
        "Learn agile-SD methodology & best practices & the soft skill-set.",
        "Apply the skill-set on a team project.",
        "Write a term report detailing your experience and exposure.",
    ],
    "assessments": [
        {"name": "Midterm I", "course_weight_percent": 25},
        {"name": "Midterm II", "course_weight_percent": 25},
        {"name": "Attendance & Participation & Preparation", "course_weight_percent": 10},
        {"name": "Project (Presentations, Demo) – Final", "course_weight_percent": 40},
    ],
    "stated_lo_po_links": [],
    "human_lo_po_links": [{"lo": 3, "po": 5, "weight": 4}, {"lo": 4, "po": 7, "weight": 2}],
}


def test_norm_strips_numbering_and_punctuation():
    assert norm("1. Apply the skill-set!") == "apply the skill set"


def test_greedy_match_pairs_each_item_once():
    matched = greedy_match(["alpha", "beta"], ["beta", "alpha", "alpha"], 0.8)
    assert sorted(matched) in ([(0, 1), (1, 0)], [(0, 2), (1, 0)])      # "alpha" used once, not twice


def test_perfect_extraction_scores_one():
    score = score_run(GOLD, cse311(), syllabus="cse311", run=1)
    assert (score.lo_recall, score.lo_precision, score.assessment_recall, score.weight_accuracy) == (1, 1, 1, 1)
    assert score.stated_mapping_accuracy is None                  # nothing stated, nothing found: not measured
    assert score.suggestion_agreement == 0.5                      # (3,5): 5 vs 4 ok; (4,7): 4 vs 2 off by 2


def test_missing_lo_and_wrong_weight_are_counted():
    extraction = cse311(
        learning_outcomes=[lo(1, GOLD["learning_outcomes"][0]), lo(2, GOLD["learning_outcomes"][1]),
                           lo(3, GOLD["learning_outcomes"][2]), lo(4, "An invented outcome about databases.")],
        assessments=[assessment("Midterm I", "midterm", 25.0), assessment("Midterm II", "midterm", 20.0),
                     assessment("Attendance & Participation & Preparation", "participation", 10.0)],
    )
    score = score_run(GOLD, extraction, syllabus="cse311", run=1)
    assert score.lo_recall == 0.75 and score.lo_precision == 0.75
    assert score.assessment_recall == 0.75
    assert score.weight_accuracy == pytest.approx(2 / 3)


def test_stated_links_must_be_copied_exactly():
    gold = {**GOLD, "stated_lo_po_links": [{"lo": 1, "po": 1, "weight": 4}, {"lo": 2, "po": 5, "weight": 3}]}
    extraction = cse311(lo_po_links=[link(1, 1, 4, stated=True), link(2, 5, 2, stated=True),
                                     link(3, 6, 3, stated=True)])
    assert score_run(gold, extraction, syllabus="x", run=1).stated_mapping_accuracy == pytest.approx(1 / 3)


def test_negative_example_scores_only_rejection():
    gold = {"is_course_syllabus": False}
    rejected = cse311(is_course_syllabus=False, learning_outcomes=[], assessments=[], lo_po_links=[])
    assert score_run(gold, rejected, syllabus="menu", run=1).correct_kind is True
    assert score_run(gold, cse311(), syllabus="menu", run=1).correct_kind is False


def test_stability():
    a = score_run(GOLD, cse311(), syllabus="s", run=1)
    b = score_run(GOLD, cse311(), syllabus="s", run=2)
    c = score_run(GOLD, cse311(learning_outcomes=cse311().learning_outcomes[:3]), syllabus="s", run=3)
    assert is_stable([a, b]) and not is_stable([a, b, c])
```

### Check it works

`uv run pytest apps/ingestion -q` passes without a key or network. With the key set, `uv run python manage.py eval_extraction --only cse311 --runs 1` prints one block with LO recall 100%, assessment recall 100%, course weight accuracy 100%, and a total cost under $0.50.

### Done when

- [ ] Six documents with gold files, each labelled by two people
- [ ] T1.2 AC 1 measured: LO recall and assessment recall reported for every syllabus
- [ ] T1.2 AC 4 measured: `menu.pdf` rejected in every run
- [ ] First results in `docs/process/sprint-05/eval.md`, with model, prompt version and cost

### Commits and PR

```
Add eval scoring functions with tests (#S5-05)
Add eval_extraction management command
Add six eval documents and hand-labelled gold files
Record first extraction eval results
```

PR title: **Extraction eval set and command (S5-05)**

---

## Code map additions

Names this chapter adds beyond spec §4.8. Add each line to §4.8 in the PR that introduces it.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `core.jobs` | `enqueue_on_commit` | `(task, *args, **kwargs) -> None` | Queue a Celery task after commit (S5-02) |
| `core.tasks` | `ping` | `(message="") -> str` | Worker smoke test (S5-02) |
| `grading.upload` | `guess_mapping` | `(header, assessments, sample_rows=()) -> ColumnMapping` | Signature gains `sample_rows`, needed to recognise student numbers by value |
| `grading.upload` | `ColumnMapping`, `DryRunReport`, `GradeChange`, `CellError`, `RowIssue`, `UploadContext`, `AssessmentInfo`, `EnrollmentInfo` | dataclasses | Upload plan data; `DryRunReport.to_dict/from_dict` for JSON storage |
| `grading.upload` | `load_context`, `plan` | `(offering) -> UploadContext`; `(rows, mapping, ctx) -> DryRunReport` | `dry_run` = `plan(rows, mapping, load_context(offering))`; `plan` is pure |
| `grading.upload` | `parse_cell`, `CellProblem`, `normalise`, `column_letter`, `fmt` | — | Cell parsing with error codes; header normalisation |
| `grading.services` | `start_grade_upload` | `(user, offering, uploaded_file) -> IngestionJob` | Step 1 of T1.1 |
| `grading.services` | `set_upload_mapping` | `(user, job, mapping) -> DryRunReport` | Step 2–3 of T1.1 |
| `grading.services` | `UploadResult` | dataclass | Return value of `apply_grade_upload` |
| `ingestion.files` | `sniff_media_type`, `check_upload`, `docx_to_text`, `downscale_image`, `prepare_document`, `PreparedDocument`, `UnsupportedFile` | — | Input handling, spec §7.3 |
| `ingestion.prompts` | `PROMPT_VERSION`, `SYSTEM_PROMPT`, `format_po_list(offering)`, `build_instruction(po_list_text)` | — | Prompt text and PO list |
| `ingestion.extraction` | `cost_usd` | `(model, input_tokens, output_tokens) -> Decimal` | Cost per call, spec §7.7 |
| `ingestion.tasks` | `mark_failed`, `record_usage`, `save_ready`, `backoff_seconds` | — | Task helpers |
| `ingestion.validation` | `derive_draft` | `(extraction, valid_po_numbers: set[int]) -> ReviewDraft` | Pure core of `validate_and_derive` |
| `ingestion.validation` | `ReviewDraft`, `DraftCourse`, `DraftLO`, `DraftAssessment`, `DraftALO`, `DraftLOPO`, `Origin` | dataclasses | The reviewable draft (consumed by S6-02, S6-03) |
| `ingestion.evals.metrics` | `score_run`, `RunScore`, `is_stable`, `greedy_match`, `average` | — | Eval scoring |
| — | URL `grading:upload_*` views take `(request, offering, perms_for, job_id, **kwargs)` | — | Assumes the decorator passes `offering` and `perms_for` as keywords (spec §4.8) |

`IngestionJob.result` layout, for the record:

| Kind | `result` keys |
|---|---|
| `grades` | `rows`, `mapping`, `report` (after mapping), `applied` (after confirm) |
| `syllabus` | `prompt_version`, `extraction` (raw model output), `draft` (`ReviewDraft.to_json()`); on failure `prompt_version`, `detail` |
