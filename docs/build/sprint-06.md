# Sprint 6: The AI wizard (Mon 23 – Sun 29 Nov)

**Sprint goal.** An instructor uploads a syllabus (PDF, Word file or a phone photo), watches it being read, reviews and edits everything Claude found, and clicks **Apply**. Only then does the course get its LOs, assessments and both weight grids. Hand-made courses get a **Suggest PO weights** button, and the head gets the first half of the department dashboard: PO attainment by cohort or term.

Sprint 5 left us with the hard parts already working in a shell: `schemas.py`, `prompts.py`, `extract_syllabus()` (S5-03), `validate_and_derive()` with fixture tests (S5-04), a real Celery worker in production (S5-02) and the eval set (S5-05). This sprint puts screens, a background job and a transaction around them.

| ID | Story | Pts | Owner | Branch |
|---|---|---|---|---|
| S6-01 | Upload page, background job with retries, status polling page | 5 | A | `feature/S6-01-syllabus-upload` |
| S6-02 | Review screen: editable LOs, assessments, both grids, source colours, warnings | 8 | B | `feature/S6-02-syllabus-review` |
| S6-03 | Apply service: one transaction, replace rule, audit, `source` fields, discard | 3 | A | `feature/S6-03-syllabus-apply` |
| S6-04 | "Suggest PO weights" for hand-made courses, lint L007, accept all | 3 | C | `feature/S6-04-suggest-po-weights` |
| S6-05 | Attainment aggregate + department attainment table and chart (T1.6 part 1) | 5 | C | `feature/S6-05-attainment` |

**Merge order.** S6-01 first (Mon–Tue): it creates the job lifecycle the other wizard stories hang off. S6-03's service can be written in parallel because it only needs a `ReviewDraft` in `job.result`, and a test can build one by hand; merge it second. S6-02 merges third, because its Apply button posts to S6-03's view. S6-04 and S6-05 don't touch the wizard and can merge whenever they're green.

```
Mon ──────── Tue ──────── Wed ──────── Thu ──────── Fri ──────── Sat ──────── Sun
A: S6-01 ─────────────►merge  S6-03 ─────────►merge         eval run → docs/process/sprint-06/eval.md
B: review.py + tests ────── S6-02 review form ─────────────────────►merge   staging walkthrough
C: S6-04 suggest ─────────►merge   S6-05 attainment ───────────────────►merge
```

**What must work by Sunday (sprint checkpoint).** On staging: upload `seed/syllabi/cse311.pdf` to an empty CSE 311 offering → the progress page shows "Reading your syllabus…" and moves to review on its own → change one LO→PO cell (it turns from violet to plain) → Apply → the Mapping tab shows the grids, and the setup checklist is complete. Upload a restaurant menu PDF → FAILED with "This doesn't look like a course syllabus" and a "Set up manually instead" link. As the head, `/department/` shows a PO × cohort attainment table with the target colouring. Record one `eval_extraction --runs 3` result table in `docs/process/sprint-06/eval.md`.

---

## Contracts this sprint relies on

These come from earlier stories. They are written out here so you can check them before you start. If the merged code differs, adapt **your** side and fix the code map (spec §4.8) in your PR. Don't silently change someone else's function.

**From S5-03 (`apps/ingestion/extraction.py`, `prompts.py`, `schemas.py`):** `extract_syllabus(path, media_type, po_list_text) -> (SyllabusExtraction, response)`, `ExtractionError`, `PROMPT_VERSION`. `_content_blocks` treats any media type other than PDF or image as UTF-8 text, so we hand it a `.txt` file for Word documents.

**From S5-04 (`apps/ingestion/validation.py`):** `validate_and_derive(extraction, offering) -> ReviewDraft`. It raises `ExtractionError` for the two FAIL rows of spec §7.6 (not a syllabus, no LOs found), and puts every other problem into `draft.warnings`. This sprint needs the draft to be JSON-serialisable, because it lives in `IngestionJob.result` between the worker and the review screen. The shape we rely on:

```python
# apps/ingestion/validation.py (delivered by S5-04, shown here for reference)
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal


class Origin:
    """Where a value in the review draft came from. Drives the cell colours (spec §8.2)."""
    DOCUMENT = "document"          # read from a table or statement in the syllabus (blue)
    DERIVED = "derived"            # computed by our rule in spec §7.6 (teal)
    AI_SUGGESTED = "ai_suggested"  # proposed by Claude, not in the document (violet)
    MANUAL = "manual"              # typed or changed by a human in the review screen (no colour)


@dataclass
class DraftCourse:
    code: str | None = None
    title: str | None = None
    credits: Decimal | None = None
    ects: Decimal | None = None


@dataclass
class DraftLO:
    key: str                 # stable id inside the draft, e.g. "l1". Never shown to the user
    number: int              # 1..n, contiguous
    description: str
    source_quote: str = ""


@dataclass
class DraftAssessment:
    key: str                 # e.g. "a1"
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
    origin: str              # DOCUMENT, DERIVED or MANUAL


@dataclass
class DraftLOPO:
    lo_key: str
    po_number: int           # number inside the offering program's active PO set
    weight: int              # 1..5
    origin: str              # DOCUMENT, AI_SUGGESTED or MANUAL
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
        """JSON-safe dict: Decimal -> str, dict keys -> str."""
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
            course=DraftCourse(code=c.get("code"), title=c.get("title"),
                               credits=_dec(c.get("credits")), ects=_dec(c.get("ects"))),
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
```

Why keys instead of database ids: nothing exists in the database until Apply, and the instructor can delete or add rows in the review screen. Keys like `a2` and `l3` let the grids refer to a row that has no id yet.

**From S2-05 (`apps/outcomes/matrix.py`, `templates/includes/weight_grid.html`):** `validate_assessment_lo_cell(raw) -> Decimal | None` and `validate_lo_po_cell(raw) -> int | None`, both raising `ValidationError` with a user-facing message; `save_lo_po_matrix(...)` sets `source=MANUAL` on any cell whose value a human changes. The grid include takes `grid` (a `WeightGrid`) and `editable`. S2-05 already gives cells `origin` and `rationale` and colours them; S6-02 reuses the include unchanged.

**From S2-02 / S5-02:** `require_offering_access`, `can_edit_offering`, `ensure_term_open` (raises `ValidationError("…term is closed…")`), Celery eager in tests (`CELERY_TASK_ALWAYS_EAGER = True`), and pytest-django's `django_capture_on_commit_callbacks` fixture for code that enqueues with `transaction.on_commit`.

**Test fixture used by every story below** (add it to `apps/ingestion/tests/conftest.py` in S6-01; S6-04 and S6-05 reuse the factories directly):

```python
# apps/ingestion/tests/conftest.py
from decimal import Decimal

import pytest

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import (
    MembershipFactory, OfferingFactory, ProgramOutcomeFactory, ProgramOutcomeSetFactory, UserFactory,
)
from apps.ingestion.validation import (
    DraftALO, DraftAssessment, DraftCourse, DraftLO, DraftLOPO, Origin, ReviewDraft,
)


@pytest.fixture
def wizard(db):
    """An open-term offering with one instructor and an active 3-PO set."""
    offering = OfferingFactory()
    program = offering.course.program
    po_set = ProgramOutcomeSetFactory(program=program, is_active=True)
    pos = [ProgramOutcomeFactory(po_set=po_set, number=n, description=f"Outcome {n} text")
           for n in (1, 2, 3)]
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=program, role=ProgramMembership.Role.INSTRUCTOR)
    offering.instructors.add(instructor)

    class W:
        pass
    w = W()
    w.offering, w.program, w.po_set, w.pos, w.instructor = offering, program, po_set, pos, instructor
    return w


def make_draft() -> ReviewDraft:
    """Two LOs, two assessments, the Elif-shaped grids, with every origin represented."""
    return ReviewDraft(
        course=DraftCourse(code="CSE 311", title="Software Engineering",
                           credits=Decimal("3"), ects=Decimal("6")),
        los=[DraftLO("l1", 1, "Explain design choices", "Learn design choices…"),
             DraftLO("l2", 2, "Apply agile practices", "Learn agile-SD methodology…")],
        assessments=[DraftAssessment("a1", "Midterm I", "midterm", Decimal("100"), Decimal("40"),
                                     "Midterm 40%"),
                     DraftAssessment("a2", "Project", "project", Decimal("100"), Decimal("60"),
                                     "Project 60%")],
        a_lo=[DraftALO("a1", "l1", Decimal("40"), Origin.DERIVED),
              DraftALO("a1", "l2", Decimal("40"), Origin.DERIVED),
              DraftALO("a2", "l2", Decimal("60"), Origin.DOCUMENT)],
        lo_po=[DraftLOPO("l1", 1, 4, Origin.DOCUMENT),
               DraftLOPO("l1", 2, 2, Origin.AI_SUGGESTED, "Design trade-offs need analysis."),
               DraftLOPO("l2", 3, 5, Origin.AI_SUGGESTED, "Agile is a team practice.")],
        course_po_levels={1: 5, 2: 3, 3: 5},
        warnings=["Course weights sum to 100%."],
    )


@pytest.fixture
def draft():
    return make_draft()
```

---
## S6-01 · Upload page, background job with retries, status polling page

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S6-01-syllabus-upload` · **Depends on:** S5-02, S5-03, S5-04, S2-02

### Goal

An instructor drops a syllabus file onto `/offerings/<id>/syllabus/`. We check the file's real type by reading its first bytes, store it under a random name, create an `IngestionJob` in `PENDING`, and hand the job to the Celery worker *after* the transaction commits. The browser goes to a progress page that asks the server for the job's status every 2 seconds and moves to the review screen by itself when the job is ready. A failed job never shows a 500: it shows a human message plus "Set up manually instead". This delivers T1.2 screens 1–2 and AC 3, 4 and 6 (spec Part 6).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/ingestion/files.py` | create | `sniff_media_type`, `docx_to_text`, `downscale_image`, `prepared_file`, `UnsupportedFile` |
| `apps/ingestion/forms.py` | create | `SyllabusUploadForm` |
| `apps/ingestion/services.py` | create | `create_syllabus_job`, `po_list_text` |
| `apps/ingestion/tasks.py` | create | `run_syllabus_extraction`, `mark_failed`, `save_ready`, `estimate_cost` |
| `apps/accounts/decorators.py` | modify | add `require_job_access` |
| `apps/ingestion/views.py` | create | `start`, `job`, `status` |
| `apps/ingestion/urls.py` | create | the routes for this story |
| `config/urls.py` | modify | `include("apps.ingestion.urls")` |
| `apps/ingestion/templates/ingestion/start.html` | create | Upload page with drag-and-drop |
| `apps/ingestion/templates/ingestion/job.html` | create | Progress page with the `status` partial |
| `templates/includes/job_status.html` | create | Status card used by syllabus jobs (and by exports in Sprint 7) |
| `static/js/polaris.js` | modify | `initDropzones()` |
| `static/css/polaris.css` | modify | dropzone styles |
| `apps/ingestion/tests/test_files.py`, `test_upload.py`, `test_tasks.py`, `test_status.py` | create | Tests |
| `apps/accounts/tests/test_permission_matrix.py` | modify | three new URLs |

### Steps

**1. Check the file type from its bytes, not its name.** A file called `syllabus.pdf` can be anything. Spec §7.3 says to validate type by content. Every format we accept has a fixed signature in its first bytes ("magic bytes"). DOCX is a ZIP archive, so for ZIPs we also look inside for `word/document.xml`, which every Word document has and other ZIPs don't. HEIC (the iPhone photo format) gets a specific message, because it's the one instructors will actually try.

```python
# apps/ingestion/files.py
"""Turning an uploaded file into something Claude can read (spec §7.3)."""
from __future__ import annotations

import io
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

from docx import Document
from PIL import Image, ImageOps

PDF = "application/pdf"
PNG = "image/png"
JPEG = "image/jpeg"
WEBP = "image/webp"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT = "text/plain"

ACCEPTED = {PDF, PNG, JPEG, WEBP, DOCX}
IMAGE_TYPES = {PNG, JPEG, WEBP}
EXTENSIONS = {PDF: ".pdf", PNG: ".png", JPEG: ".jpg", WEBP: ".webp", DOCX: ".docx"}
MAX_IMAGE_SIDE = 2000


class UnsupportedFile(Exception):
    """The file is not a type we can send to Claude. The message is shown to the user."""


def sniff_media_type(fileobj) -> str:
    """Return the media type from the file's first bytes. Raises UnsupportedFile.
    Leaves the file position at 0."""
    fileobj.seek(0)
    head = fileobj.read(16)
    fileobj.seek(0)
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        raise UnsupportedFile("iPhone photos (HEIC) can't be read. Please export the photo as JPG.")
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(fileobj) as zf:
                is_docx = "word/document.xml" in zf.namelist()
        except zipfile.BadZipFile:
            is_docx = False
        finally:
            fileobj.seek(0)
        if is_docx:
            return DOCX
    raise UnsupportedFile("Please upload a PDF, a Word (.docx) file, or a JPG/PNG/WEBP image. "
                          "Other formats can be exported as PDF first.")


def docx_to_text(data: bytes) -> str:
    """Paragraphs and tables in reading order. Assessment tables are usually Word tables,
    so dropping them (python-docx's doc.paragraphs alone does) would lose the weights."""
    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for block in doc.iter_inner_content():          # Paragraph and Table objects, in order
        if hasattr(block, "rows"):                  # a Table
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells]
                lines.append(" | ".join(cells))
            lines.append("")
        else:
            text = block.text.strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def downscale_image(data: bytes, media_type: str) -> bytes:
    """Rotate phone photos upright (EXIF) and cap the long side at 2000 px.
    Smaller images cost fewer tokens and read just as well."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    fmt = {PNG: "PNG", JPEG: "JPEG", WEBP: "WEBP"}[media_type]
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(out, format=fmt)
    return out.getvalue()


@contextmanager
def prepared_file(job):
    """Yield (path, media_type) of a temporary file ready for extract_syllabus().
    DOCX becomes UTF-8 text; images are downscaled; PDFs pass through unchanged.
    The temporary directory is deleted on exit, whatever happens."""
    with job.file.open("rb") as fh:
        media_type = sniff_media_type(fh)
        data = fh.read()
    with tempfile.TemporaryDirectory(prefix="polaris-") as tmp:
        if media_type == DOCX:
            data = docx_to_text(data).encode("utf-8")
            media_type = TEXT
        elif media_type in IMAGE_TYPES:
            data = downscale_image(data, media_type)
        path = Path(tmp) / "input"
        path.write_bytes(data)
        yield path, media_type
```

`Document.iter_inner_content()` exists in python-docx 1.1 and later; `uv add python-docx` installs a newer version than that.

**2. The upload form.** The size check lives in the form so the instructor gets the message next to the field. 20 MB is the cap from T1.2. The real-type check runs here as well as in the worker: here so the user gets an instant answer, there because the worker must never trust data it didn't check itself.

```python
# apps/ingestion/forms.py
from django import forms

from .files import UnsupportedFile, sniff_media_type

MAX_SYLLABUS_BYTES = 20 * 1024 * 1024


class SyllabusUploadForm(forms.Form):
    file = forms.FileField(
        label="Syllabus file",
        help_text="PDF, Word (.docx), or a photo (JPG, PNG, WEBP). Up to 20 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.docx,.jpg,.jpeg,.png,.webp"}),
    )

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > MAX_SYLLABUS_BYTES:
            raise forms.ValidationError("This file is larger than 20 MB. Upload only the syllabus pages.")
        try:
            self.media_type = sniff_media_type(f)
        except UnsupportedFile as e:
            raise forms.ValidationError(str(e)) from e
        return f
```

**3. The service that creates the job.** Three choices to understand:

- The stored file gets a random name (`uuid4().hex` plus the extension that matches the sniffed type). Spec §7.8: the original name is kept only for display. A random name also means two instructors uploading `syllabus.pdf` never collide.
- The job is handed to Celery with `transaction.on_commit`. If we called `.delay()` directly, the worker could pick up the job before our transaction commits and find no row (spec Part 15 gotcha).
- **A daily cap of 10 uploads per user.** Each run costs about $0.20–0.35 (spec §7.7). The cap means a stuck "Retry" habit or a bug in a loop can't spend the monthly budget in an afternoon. 10 is far more than a real instructor needs in a day.

```python
# apps/ingestion/services.py
from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.catalog.services import ensure_term_open
from apps.core import audit

from .files import EXTENSIONS
from .models import IngestionJob

DAILY_UPLOAD_LIMIT = 10


def po_list_text(po_set) -> str:
    """The active POs in the form the prompt expects: one 'PO n: description' per line."""
    return "\n".join(f"PO {po.number}: {po.description}" for po in po_set.outcomes.order_by("number"))


def create_syllabus_job(user, offering, uploaded_file, *, media_type: str) -> IngestionJob:
    from .tasks import run_syllabus_extraction   # local import: tasks imports services

    ensure_term_open(offering)
    since = timezone.now() - timedelta(days=1)
    recent = IngestionJob.objects.filter(created_by=user, kind=IngestionJob.Kind.SYLLABUS,
                                         created_at__gte=since).count()
    if recent >= DAILY_UPLOAD_LIMIT:
        raise ValidationError("You've uploaded 10 syllabi in the last 24 hours. "
                              "Please try again tomorrow or set up the course manually.")

    original_name = uploaded_file.name[:255]
    uploaded_file.name = f"{uuid.uuid4().hex}{EXTENSIONS[media_type]}"
    with transaction.atomic():
        job = IngestionJob.objects.create(
            offering=offering, kind=IngestionJob.Kind.SYLLABUS, file=uploaded_file,
            original_filename=original_name, created_by=user,
        )
        audit.record(user, "syllabus.upload", job, after={"file": original_name}, offering=offering)
        transaction.on_commit(lambda: run_syllabus_extraction.delay(job.pk))
    return job
```

`create_syllabus_job` takes `media_type` as a keyword argument, which the form already computed. Add that to the code map line for this function.

**4. The Celery task.** This replaces the sketch in spec §7.5 with the full version. Reading it top to bottom:

- **Idempotent start.** If the job is no longer `PENDING`/`PROCESSING` (applied, discarded, already failed), do nothing. Celery can deliver a task twice (we use `acks_late`), so this check matters.
- **Every write to the job is a conditional `UPDATE … WHERE status IN (pending, processing)`.** If the instructor clicks Discard while Claude is still reading, the worker's later "save the result" finds zero matching rows and changes nothing. Discard wins, which is what the instructor asked for.
- **Which errors are retried.** Rate limits (429), server errors (5xx, including "overloaded") and connection problems are temporary: try again later. A 400 means our request or the file is bad: retrying won't help, so fail at once. We check status codes instead of listing exception classes, so a new SDK error subclass can't slip through.
- **Backoff.** 30 s, 60 s, 120 s, 240 s (capped at 600 s). After the 4th retry the job fails with "The AI service is unavailable right now…". The SDK has already retried quick blips twice inside each attempt (spec §7.5).
- **Cost.** We store `cost_usd` from token counts and the per-model price table in spec §7.7. Unknown models fall back to Opus prices, so we over-estimate rather than under-estimate.

```python
# apps/ingestion/tasks.py
from __future__ import annotations

import logging
from decimal import Decimal

import anthropic
from celery import shared_task
from django.utils import timezone

from apps.catalog.selectors import active_po_set

from .extraction import ExtractionError, extract_syllabus
from .files import UnsupportedFile, prepared_file
from .models import IngestionJob
from .prompts import PROMPT_VERSION
from .services import po_list_text
from .validation import validate_and_derive

log = logging.getLogger(__name__)

MAX_RETRIES = 4
ACTIVE = [IngestionJob.Status.PENDING, IngestionJob.Status.PROCESSING]
UNAVAILABLE = ("The AI service is unavailable right now. "
               "Try again later or set up the course manually.")
UNREADABLE = "The file could not be read. Is it a valid PDF, Word file or image?"

# USD per million tokens (input, output). Spec §7.7.
PRICES = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10")),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    price_in, price_out = next((p for name, p in PRICES.items() if model.startswith(name)),
                               PRICES["claude-opus-5-5"])
    million = Decimal(1_000_000)
    cost = Decimal(input_tokens) / million * price_in + Decimal(output_tokens) / million * price_out
    return cost.quantize(Decimal("0.0001"))


def mark_failed(job: IngestionJob, message: str, *, detail: str = "") -> None:
    """User-facing message in `error`; the technical detail goes to the log only."""
    if detail:
        log.warning("ingestion job %s failed: %s", job.pk, detail)
    IngestionJob.objects.filter(pk=job.pk, status__in=ACTIVE).update(
        status=IngestionJob.Status.FAILED, error=message, updated_at=timezone.now())


def save_ready(job: IngestionJob, draft, response) -> None:
    usage = response.usage
    result = draft.to_json()
    result["meta"] = {"prompt_version": PROMPT_VERSION}
    IngestionJob.objects.filter(pk=job.pk, status__in=ACTIVE).update(
        status=IngestionJob.Status.READY,
        result=result,
        warnings=list(draft.warnings),
        model=response.model,
        request_id=getattr(response, "_request_id", None) or "",
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=estimate_cost(response.model, usage.input_tokens, usage.output_tokens),
        updated_at=timezone.now(),
    )


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIConnectionError):           # includes APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def backoff_seconds(retries: int) -> int:
    return min(30 * 2 ** retries, 600)


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def run_syllabus_extraction(self, job_id: int) -> None:
    job = IngestionJob.objects.select_related("offering__course__program").get(pk=job_id)
    if job.status not in ACTIVE:
        return
    IngestionJob.objects.filter(pk=job.pk, status__in=ACTIVE).update(
        status=IngestionJob.Status.PROCESSING, updated_at=timezone.now())

    try:
        po_set = active_po_set(job.offering.course.program)
        with prepared_file(job) as (path, media_type):
            extraction, response = extract_syllabus(path, media_type, po_list_text(po_set))
        draft = validate_and_derive(extraction, job.offering)
    except (ExtractionError, UnsupportedFile) as e:
        mark_failed(job, str(e))
        return
    except anthropic.APIError as e:
        if not is_transient(e):
            mark_failed(job, UNREADABLE, detail=repr(e))
            return
        if self.request.retries >= self.max_retries:
            mark_failed(job, UNAVAILABLE, detail=repr(e))
            return
        raise self.retry(exc=e, countdown=backoff_seconds(self.request.retries)) from e
    except Exception as e:                       # a bug in our code: never leave the job spinning
        mark_failed(job, "Something went wrong on our side. Please set up the course manually.",
                    detail=repr(e))
        raise
    save_ready(job, draft, response)
```

The last `except Exception` re-raises after marking the job failed. The job page stops spinning, and the error still reaches the worker log (and Sentry once T2.10 lands).

**5. A decorator for job URLs.** Job URLs have `job_id`, not `offering_id`, so `require_offering_access` can't load them. The rule from spec §3.4 still holds: permission checks live in decorators, never inside views. This one loads the job, checks `can_edit_offering` on the job's offering, returns 404 otherwise, and passes `job=` and `offering=` into the view. Only syllabus jobs are reachable through these URLs.

```python
# apps/accounts/decorators.py  (add below require_offering_access)
from functools import wraps

from django.http import Http404

from .permissions import can_edit_offering, offering_perms


def require_job_access(view):
    """For /ingestion/<job_id>/… views. 404 unless the user may edit the job's offering."""
    @wraps(view)
    def wrapper(request, *args, job_id, **kwargs):
        from apps.ingestion.models import IngestionJob

        job = (IngestionJob.objects
               .select_related("offering__course__program", "offering__term", "created_by")
               .filter(pk=job_id, kind=IngestionJob.Kind.SYLLABUS).first())
        if job is None or not can_edit_offering(request.user, job.offering):
            raise Http404
        return view(request, *args, job=job, offering=job.offering,
                    perms_for=offering_perms(request.user, job.offering), **kwargs)
    return wrapper
```

Because `can_edit_offering` is false for closed terms, a job on a closed term returns 404 too. That's consistent with spec §3.3: a closed term is read-only for everyone except the admin.

**6. Views and URLs.** `status` is the polled partial. Three outcomes:

- Still `PENDING` or `PROCESSING`: return the status card *with* `hx-trigger="every 2s"`, so HTMX asks again.
- `READY`: respond with `HttpResponseClientRedirect` from django-htmx. It sets the `HX-Redirect` header, and HTMX then does a full page load of the review screen. The instructor doesn't have to click anything.
- `FAILED` or `DISCARDED`: return the card *without* the trigger, so polling stops (spec §8.5).

```python
# apps/ingestion/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django_htmx.http import HttpResponseClientRedirect

from apps.accounts.decorators import require_job_access, require_offering_access

from .forms import SyllabusUploadForm
from .models import IngestionJob
from .services import create_syllabus_job


@login_required
@require_offering_access(edit=True)
@require_http_methods(["GET", "POST"])
def start(request, offering_id, offering, perms_for):
    form = SyllabusUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            job = create_syllabus_job(request.user, offering, form.cleaned_data["file"],
                                      media_type=form.media_type)
        except ValidationError as e:
            form.add_error(None, e)
        else:
            return redirect("ingestion:job", job_id=job.pk)
    has_setup = offering.learning_outcomes.exists() or offering.assessments.exists()
    recent_jobs = offering.ingestion_jobs.filter(kind=IngestionJob.Kind.SYLLABUS)[:5]
    return render(request, "ingestion/start.html", {
        "offering": offering, "perms_for": perms_for, "form": form,
        "has_setup": has_setup, "recent_jobs": recent_jobs,
    })


@login_required
@require_job_access
@require_GET
def job(request, job, offering, perms_for):
    if job.status == IngestionJob.Status.READY:
        return redirect("ingestion:review", job_id=job.pk)
    return render(request, "ingestion/job.html", {"job": job, "offering": offering,
                                                  "perms_for": perms_for})


@login_required
@require_job_access
@require_GET
def status(request, job, offering, perms_for):
    if job.status == IngestionJob.Status.READY:
        url = reverse("ingestion:review", kwargs={"job_id": job.pk})
        if request.htmx:
            return HttpResponseClientRedirect(url)
        return redirect(url)
    return render(request, "ingestion/job.html#status", {"job": job, "offering": offering})
```

The `start` view keeps `offering_id` in its signature: Django passes the URL kwarg, and the decorator reads it and adds `offering` and `perms_for`.

```python
# apps/ingestion/urls.py
from django.urls import path

from . import views

app_name = "ingestion"

urlpatterns = [
    path("offerings/<int:offering_id>/syllabus/", views.start, name="start"),
    path("ingestion/<int:job_id>/", views.job, name="job"),
    path("ingestion/<int:job_id>/status/", views.status, name="status"),
    # S6-02 adds review; S6-03 adds apply and discard
]
```

```python
# config/urls.py  (add to urlpatterns)
path("", include("apps.ingestion.urls")),
```

**7. Templates.** The upload page shows a different notice when the course already has a setup, so the instructor learns about the replace rule *before* paying for an extraction. The drop zone is a `<label>` wrapped around the real file input. Keyboard and screen-reader users get a normal file picker, and the drag-and-drop JavaScript is only an extra.

```django
{# apps/ingestion/templates/ingestion/start.html #}
{% extends "base.html" %}
{% block title %}Set up from syllabus · {{ offering.course.code }}{% endblock %}
{% block content %}
<nav aria-label="breadcrumb"><ol class="breadcrumb">
  <li class="breadcrumb-item"><a href="{% url 'catalog:offering' offering.pk %}">{{ offering.course.code }} · {{ offering.term.name }}</a></li>
  <li class="breadcrumb-item active" aria-current="page">Set up from syllabus</li>
</ol></nav>

<h1 class="h3 mb-3">Set up this course from its syllabus</h1>
<p class="text-body-secondary">We read the file, find the learning outcomes, assessments and any outcome mapping,
  and show you everything to review. <strong>Nothing is saved to the course until you click Apply.</strong></p>

{% if has_setup %}
  <div class="alert alert-warning" role="alert">
    This course already has learning outcomes or assessments. You can still upload a syllabus, but applying it
    will <strong>replace</strong> the current setup, and that is only allowed while the course has no grades.
  </div>
{% endif %}

<form method="post" enctype="multipart/form-data" class="card card-body mb-4" novalidate>
  {% csrf_token %}
  {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors|join:" " }}</div>{% endif %}
  <label class="pl-dropzone" data-dropzone for="{{ form.file.id_for_label }}">
    <span class="pl-dropzone__title">Drop the syllabus here, or click to choose a file</span>
    <span class="pl-dropzone__hint">{{ form.file.help_text }}</span>
    <span class="pl-dropzone__name" data-dropzone-name aria-live="polite"></span>
    {{ form.file }}
  </label>
  {% for err in form.file.errors %}<div class="invalid-feedback d-block">{{ err }}</div>{% endfor %}
  <div class="d-flex gap-2 mt-3">
    <button type="submit" class="btn btn-primary">Read syllabus</button>
    <a class="btn btn-link" href="{% url 'outcomes:setup' offering.pk %}">Set up manually instead</a>
  </div>
</form>

{% if recent_jobs %}
<h2 class="h5">Earlier uploads</h2>
<ul class="list-group mb-4">
  {% for j in recent_jobs %}
  <li class="list-group-item d-flex justify-content-between align-items-center">
    <span>{{ j.original_filename }} · {{ j.created_at|date:"j M, H:i" }}</span>
    <a href="{% url 'ingestion:job' j.pk %}" class="badge text-bg-light text-decoration-none">{{ j.get_status_display }}</a>
  </li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}
```

```django
{# apps/ingestion/templates/ingestion/job.html #}
{% extends "base.html" %}
{% block title %}Reading {{ job.original_filename }}{% endblock %}
{% block content %}
<nav aria-label="breadcrumb"><ol class="breadcrumb">
  <li class="breadcrumb-item"><a href="{% url 'catalog:offering' offering.pk %}">{{ offering.course.code }} · {{ offering.term.name }}</a></li>
  <li class="breadcrumb-item active" aria-current="page">Syllabus</li>
</ol></nav>
<h1 class="h3 mb-3">{{ job.original_filename }}</h1>

{% partialdef status inline %}
<div id="job-status"
     {% if job.status == "pending" or job.status == "processing" %}
       hx-get="{% url 'ingestion:status' job.pk %}" hx-trigger="every 2s" hx-swap="outerHTML"
     {% endif %}>
  {% include "includes/job_status.html" with job=job offering=offering only %}
</div>
{% endpartialdef %}
{% endblock %}
```

`inline` makes the partial render in place on the full page, and the `status` view renders only that piece through `"ingestion/job.html#status"`.

```django
{# templates/includes/job_status.html  — params: job (IngestionJob), offering #}
{% if job.status == "pending" or job.status == "processing" %}
  <div class="card card-body" role="status" aria-live="polite">
    <div class="d-flex align-items-center gap-3">
      <div class="spinner-border text-primary" aria-hidden="true"></div>
      <div>
        <p class="mb-1 fw-semibold">{% if job.status == "pending" %}Waiting to start…{% else %}Reading your syllabus…{% endif %}</p>
        <p class="mb-0 text-body-secondary small">This usually takes 20–60 seconds. You can leave this page; we'll keep working,
          and the result will be under "Earlier uploads" on the syllabus page.</p>
      </div>
    </div>
  </div>
{% elif job.status == "failed" %}
  <div class="card card-body border-danger" role="alert">
    <p class="fw-semibold text-danger mb-1">We couldn't set up the course from this file</p>
    <p class="mb-3">{{ job.error|default:"Something went wrong." }}</p>
    <div class="d-flex gap-2">
      <a class="btn btn-primary" href="{% url 'outcomes:setup' offering.pk %}">Set up manually instead</a>
      <a class="btn btn-outline-secondary" href="{% url 'ingestion:start' offering.pk %}">Try another file</a>
    </div>
  </div>
{% elif job.status == "discarded" %}
  <div class="card card-body"><p class="mb-2">This upload was discarded.</p>
    <a href="{% url 'ingestion:start' offering.pk %}">Upload another file</a></div>
{% elif job.status == "applied" %}
  <div class="card card-body border-success"><p class="mb-2">Applied {{ job.applied_at|date:"j M Y, H:i" }}.</p>
    <a href="{% url 'outcomes:mapping' offering.pk %}">Open the mapping</a></div>
{% endif %}
```

**8. Drag-and-drop JavaScript and CSS.** Assigning `input.files = e.dataTransfer.files` is allowed in every current browser and keeps the normal form submit, so no upload code is needed.

```javascript
// static/js/polaris.js  (add; call initDropzones() from the existing DOMContentLoaded handler)
function initDropzones(root = document) {
  root.querySelectorAll("[data-dropzone]").forEach((zone) => {
    const input = zone.querySelector("input[type=file]");
    const nameEl = zone.querySelector("[data-dropzone-name]");
    const showName = () => {
      nameEl.textContent = input.files.length ? `Selected: ${input.files[0].name}` : "";
    };
    ["dragenter", "dragover"].forEach((ev) =>
      zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("is-dragover"); }));
    ["dragleave", "drop"].forEach((ev) =>
      zone.addEventListener(ev, () => zone.classList.remove("is-dragover")));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        showName();
      }
    });
    input.addEventListener("change", showName);
  });
}
```

```css
/* static/css/polaris.css */
.pl-dropzone { display: flex; flex-direction: column; align-items: center; gap: .25rem;
  padding: 2.5rem 1rem; border: 2px dashed var(--bs-border-color); border-radius: .75rem;
  text-align: center; cursor: pointer; }
.pl-dropzone:focus-within, .pl-dropzone.is-dragover { border-color: var(--pl-primary);
  background: var(--bs-tertiary-bg); }
.pl-dropzone input[type=file] { position: absolute; width: 1px; height: 1px; opacity: 0; }
.pl-dropzone__title { font-weight: 600; }
.pl-dropzone__hint { color: var(--bs-secondary-color); font-size: .875rem; }
```

The input is visually hidden, not `display: none`. A `display: none` input can't take keyboard focus, and the `:focus-within` outline is how a keyboard user sees where they are.

**9. Permission matrix.** The three URLs already have rows in `ROUTES` (`apps/accounts/tests/routes.py`, S2-02); they switch on when the URLs exist. Check that The expected results are: student 404, instructor of another offering 404, instructor of this offering 200, head 200, anonymous 302 to login. For `ingestion:job` and `ingestion:status`, the fixture builds a `PENDING` syllabus job on the matrix's offering.

### Tests

```python
# apps/ingestion/tests/test_files.py
import io
import zipfile

import pytest
from docx import Document
from PIL import Image

from apps.ingestion.files import (
    DOCX, JPEG, PDF, PNG, WEBP, UnsupportedFile, docx_to_text, downscale_image, sniff_media_type,
)


def _image_bytes(fmt, size=(3000, 1500)):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format=fmt)
    return out.getvalue()


def _docx_bytes():
    doc = Document()
    doc.add_paragraph("Learning outcomes")
    doc.add_paragraph("1. Explain design choices")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Midterm", "40%"
    table.cell(1, 0).text, table.cell(1, 1).text = "Project", "60%"
    doc.add_paragraph("After the table")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


@pytest.mark.parametrize("data, expected", [
    (b"%PDF-1.7\n%...", PDF),
    (_image_bytes("PNG", (10, 10)), PNG),
    (_image_bytes("JPEG", (10, 10)), JPEG),
    (_image_bytes("WEBP", (10, 10)), WEBP),
    (_docx_bytes(), DOCX),
])
def test_sniff_accepts_supported_types(data, expected):
    f = io.BytesIO(data)
    assert sniff_media_type(f) == expected
    assert f.tell() == 0


def test_sniff_rejects_heic_with_specific_message():
    with pytest.raises(UnsupportedFile, match="HEIC"):
        sniff_media_type(io.BytesIO(b"\x00\x00\x00\x18ftypheic\x00\x00"))


def test_sniff_rejects_plain_zip_and_text():
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("hello.txt", "hi")
    with pytest.raises(UnsupportedFile):
        sniff_media_type(io.BytesIO(z.getvalue()))
    with pytest.raises(UnsupportedFile):
        sniff_media_type(io.BytesIO(b"just some text"))


def test_docx_text_keeps_tables_in_reading_order():
    text = docx_to_text(_docx_bytes())
    lines = [line for line in text.splitlines() if line]
    assert lines == ["Learning outcomes", "1. Explain design choices",
                     "Midterm | 40%", "Project | 60%", "After the table"]


def test_downscale_caps_long_side_at_2000():
    small = downscale_image(_image_bytes("JPEG"), JPEG)
    assert max(Image.open(io.BytesIO(small)).size) == 2000
```

```python
# apps/ingestion/tests/test_upload.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.ingestion.models import IngestionJob

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _upload(client, offering, name="CSE311 syllabus.pdf", data=PDF_BYTES):
    return client.post(reverse("ingestion:start", args=[offering.pk]),
                       {"file": SimpleUploadedFile(name, data)})


def test_upload_creates_pending_job_and_enqueues_after_commit(client, wizard, monkeypatch,
                                                              django_capture_on_commit_callbacks):
    queued = []
    monkeypatch.setattr("apps.ingestion.tasks.run_syllabus_extraction.delay", queued.append)
    client.force_login(wizard.instructor)
    with django_capture_on_commit_callbacks(execute=True):
        resp = _upload(client, wizard.offering)
    job = IngestionJob.objects.get()
    assert resp.status_code == 302
    assert resp.url == reverse("ingestion:job", args=[job.pk])
    assert job.status == IngestionJob.Status.PENDING
    assert job.original_filename == "CSE311 syllabus.pdf"
    assert job.file.name.endswith(".pdf") and "syllabus" not in job.file.name   # random name
    assert queued == [job.pk]


def test_upload_rejects_wrong_type_by_content(client, wizard):
    client.force_login(wizard.instructor)
    resp = _upload(client, wizard.offering, name="fake.pdf", data=b"not a pdf at all")
    assert resp.status_code == 200
    assert "Please upload a PDF" in resp.content.decode()
    assert not IngestionJob.objects.exists()


def test_upload_rejects_files_over_20_mb(client, wizard):
    client.force_login(wizard.instructor)
    big = PDF_BYTES + b"0" * (20 * 1024 * 1024)
    resp = _upload(client, wizard.offering, data=big)
    assert "larger than 20 MB" in resp.content.decode()


def test_daily_limit(client, wizard, monkeypatch):
    monkeypatch.setattr("apps.ingestion.tasks.run_syllabus_extraction.delay", lambda pk: None)
    client.force_login(wizard.instructor)
    for _ in range(10):
        _upload(client, wizard.offering)
    resp = _upload(client, wizard.offering)
    assert "10 syllabi in the last 24 hours" in resp.content.decode()
    assert IngestionJob.objects.count() == 10


def test_other_instructor_gets_404(client, wizard):
    from apps.core.tests.factories import UserFactory
    client.force_login(UserFactory())
    assert client.get(reverse("ingestion:start", args=[wizard.offering.pk])).status_code == 404
```

```python
# apps/ingestion/tests/test_tasks.py
"""No network: extract_syllabus is replaced by a fake in every test."""
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from django.core.files.base import ContentFile

from apps.ingestion import tasks
from apps.ingestion.extraction import ExtractionError
from apps.ingestion.models import IngestionJob

from .conftest import make_draft

REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, code):
    return cls(message=f"HTTP {code}", response=httpx.Response(code, request=REQ), body=None)


FAKE_RESPONSE = SimpleNamespace(
    model="claude-opus-5-5", _request_id="req_123",
    usage=SimpleNamespace(input_tokens=15000, output_tokens=8000),
)


@pytest.fixture
def job(wizard):
    return IngestionJob.objects.create(
        offering=wizard.offering, kind=IngestionJob.Kind.SYLLABUS,
        file=ContentFile(b"%PDF-1.4\n%%EOF", name="x.pdf"), original_filename="x.pdf",
        created_by=wizard.instructor)


@pytest.fixture
def ok_pipeline(monkeypatch):
    monkeypatch.setattr(tasks, "extract_syllabus", lambda *a: ("EXTRACTION", FAKE_RESPONSE))
    monkeypatch.setattr(tasks, "validate_and_derive", lambda extraction, offering: make_draft())


def _raise(exc):
    def f(*args, **kwargs):
        raise exc
    return f


def test_success_saves_draft_tokens_cost_and_request_id(job, ok_pipeline):
    tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.READY
    assert [lo["key"] for lo in job.result["los"]] == ["l1", "l2"]
    assert job.result["meta"]["prompt_version"]
    assert (job.input_tokens, job.output_tokens) == (15000, 8000)
    assert job.cost_usd == Decimal("0.2200")          # 0.015 * 4 + 0.008 * 20
    assert job.request_id == "req_123" and job.model == "claude-opus-5-5"
    assert job.warnings == ["Course weights sum to 100%."]


def test_extraction_error_fails_with_its_message(job, monkeypatch):
    monkeypatch.setattr(tasks, "extract_syllabus",
                        _raise(ExtractionError("This doesn't look like a course syllabus")))
    tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.FAILED
    assert job.error == "This doesn't look like a course syllabus"


def test_bad_request_fails_immediately(job, monkeypatch):
    monkeypatch.setattr(tasks, "extract_syllabus", _raise(_status_error(anthropic.BadRequestError, 400)))
    tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.FAILED and job.error == tasks.UNREADABLE


@pytest.mark.parametrize("exc", [
    _status_error(anthropic.RateLimitError, 429),
    _status_error(anthropic.InternalServerError, 500),
    _status_error(anthropic.APIStatusError, 529),
    anthropic.APIConnectionError(request=REQ),
])
def test_transient_errors_are_retried_with_backoff(job, monkeypatch, exc):
    monkeypatch.setattr(tasks, "extract_syllabus", _raise(exc))
    calls = []

    def fake_retry(exc, countdown):
        calls.append(countdown)
        return RuntimeError("retry scheduled")

    monkeypatch.setattr(tasks.run_syllabus_extraction, "retry", fake_retry)
    with pytest.raises(RuntimeError, match="retry scheduled"):
        tasks.run_syllabus_extraction(job.pk)
    assert calls == [30]
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.PROCESSING


def test_last_retry_marks_job_failed(job, monkeypatch):
    monkeypatch.setattr(tasks, "extract_syllabus", _raise(_status_error(anthropic.RateLimitError, 429)))
    tasks.run_syllabus_extraction.push_request(retries=tasks.MAX_RETRIES)
    try:
        tasks.run_syllabus_extraction(job.pk)
    finally:
        tasks.run_syllabus_extraction.pop_request()
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.FAILED and job.error == tasks.UNAVAILABLE


def test_discard_during_processing_wins(job, monkeypatch):
    def slow_extract(*args):
        IngestionJob.objects.filter(pk=job.pk).update(status=IngestionJob.Status.DISCARDED)
        return "EXTRACTION", FAKE_RESPONSE
    monkeypatch.setattr(tasks, "extract_syllabus", slow_extract)
    monkeypatch.setattr(tasks, "validate_and_derive", lambda e, o: make_draft())
    tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.DISCARDED and job.result is None


def test_already_finished_job_is_left_alone(job, ok_pipeline):
    IngestionJob.objects.filter(pk=job.pk).update(status=IngestionJob.Status.APPLIED)
    tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.APPLIED


def test_unexpected_bug_marks_failed_and_reraises(job, monkeypatch):
    monkeypatch.setattr(tasks, "extract_syllabus", _raise(KeyError("oops")))
    with pytest.raises(KeyError):
        tasks.run_syllabus_extraction(job.pk)
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.FAILED


@pytest.mark.parametrize("model, expected", [
    ("claude-opus-5-5", Decimal("0.2200")),
    ("claude-sonnet-5-5", Decimal("0.1100")),
    ("some-future-model", Decimal("0.2200")),
])
def test_estimate_cost(model, expected):
    assert tasks.estimate_cost(model, 15000, 8000) == expected
```

```python
# apps/ingestion/tests/test_status.py
import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.ingestion.models import IngestionJob


@pytest.fixture
def make_job(wizard):
    def make(status, **extra):
        return IngestionJob.objects.create(
            offering=wizard.offering, kind=IngestionJob.Kind.SYLLABUS, status=status,
            file=ContentFile(b"%PDF-1.4", name="x.pdf"), original_filename="cse311.pdf",
            created_by=wizard.instructor, **extra)
    return make


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_running_job_keeps_polling(client, wizard, make_job, status):
    job = make_job(status)
    client.force_login(wizard.instructor)
    html = client.get(reverse("ingestion:status", args=[job.pk]), HTTP_HX_REQUEST="true").content.decode()
    assert 'hx-trigger="every 2s"' in html
    assert "<html" not in html                            # partial only


def test_ready_job_redirects_htmx_to_review(client, wizard, make_job):
    job = make_job("ready", result={})
    client.force_login(wizard.instructor)
    resp = client.get(reverse("ingestion:status", args=[job.pk]), HTTP_HX_REQUEST="true")
    assert resp["HX-Redirect"] == reverse("ingestion:review", args=[job.pk])


def test_failed_job_stops_polling_and_offers_manual_setup(client, wizard, make_job):
    job = make_job("failed", error="This doesn't look like a course syllabus")
    client.force_login(wizard.instructor)
    html = client.get(reverse("ingestion:status", args=[job.pk]), HTTP_HX_REQUEST="true").content.decode()
    assert "hx-trigger" not in html
    assert "This doesn&#x27;t look like a course syllabus" in html
    assert reverse("outcomes:setup", args=[wizard.offering.pk]) in html


def test_job_page_is_404_for_a_student(client, wizard, make_job):
    from apps.core.tests.factories import UserFactory
    job = make_job("pending")
    client.force_login(UserFactory())
    assert client.get(reverse("ingestion:job", args=[job.pk])).status_code == 404
```

`test_ready_job_redirects_htmx_to_review` needs the `ingestion:review` URL, which S6-02 adds. Until then, mark it `@pytest.mark.xfail(strict=True, reason="needs S6-02")` and remove the marker in S6-02.

### Check it works

1. Run `CELERY_EAGER=False uv run celery -A config worker -l info` in one terminal and `uv run python manage.py runserver` in another. Your `.env` must hold the team's `ANTHROPIC_API_KEY`.
2. Log in as the seeded CSE 311 instructor, open an empty offering, and click **Upload syllabus instead** in the setup empty state.
3. Drag `seed/syllabi/cse311.pdf` onto the drop zone. The file name appears under the hint. Click **Read syllabus**.
4. The progress page spins. The worker log shows `Task apps.ingestion.tasks.run_syllabus_extraction[...] received`, then `succeeded` 20–60 s later. Until S6-02 merges, the browser then lands on a 404 for `/ingestion/<id>/review/`, which is expected.
5. In `uv run python manage.py shell`: `IngestionJob.objects.latest("created_at").cost_usd` gives a value of about 0.2–0.35.
6. Upload `seed/syllabi/menu.pdf` (any non-syllabus PDF). The page shows the red card with "This doesn't look like a course syllabus" and both buttons.
7. Stop the worker, upload again, then wait. The card stays on "Waiting to start…". Start the worker: it picks the job up and finishes.

### Done when

- [ ] T1.2 AC3 (failure gives a human message and a manual-setup link, never a 500): `test_extraction_error_fails_with_its_message`, `test_bad_request_fails_immediately`, `test_last_retry_marks_job_failed`, `test_unexpected_bug_marks_failed_and_reraises`, `test_failed_job_stops_polling_and_offers_manual_setup`
- [ ] T1.2 AC4 (non-syllabus fails): the S5-04 validation test plus `test_extraction_error_fails_with_its_message`
- [ ] T1.2 AC6 (model, tokens, cost, request id recorded): `test_success_saves_draft_tokens_cost_and_request_id`
- [ ] Type is checked by content and the 20 MB cap holds: `test_files.py`, `test_upload_rejects_*`
- [ ] Permission matrix updated; `test_job_page_is_404_for_a_student`
- [ ] Manual check 1–7 done on staging

### Commits and PR

```
Add syllabus file sniffing and DOCX/image preparation
Create syllabus jobs on upload and enqueue after commit
Run syllabus extraction in Celery with retries and cost tracking
Add syllabus progress page with HTMX status polling
```

PR title: **S6-01 Syllabus upload, background extraction and progress page** (`Closes #<issue>`).

---
## S6-02 · Review screen: editable LOs, assessments, both grids, source colours, warnings

**Points:** 8 · **Owner:** Person B · **Branch:** `feature/S6-02-syllabus-review` · **Depends on:** S6-01, S2-05

### Goal

When a job is `READY`, `/ingestion/<job_id>/review/` shows everything Claude found as an editable form. Course info is compared with the catalog, and mismatches are highlighted. LOs show their quoted source text, and assessments are editable too. Both weight grids reuse the B5 grid component, and every cell is coloured by where its value came from: **document** (blue), **derived** by our rule (teal), or **AI-suggested** (violet, with the reason on hover). Warnings sit at the top. **Save draft** stores the edits on the job; nothing touches the course until Apply (S6-03). This delivers T1.2 screen 3 and AC 2 and 5 on the screen side.

This is the biggest story of the sprint (8 points). Split the PR into two if it passes 400 lines: (a) `review.py` and its tests, (b) the view and template.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/ingestion/review.py` | create | `ReviewForm`, `LOForm`, `AssessmentForm`, `build_review_grids`, `review_warnings`, `course_mismatches`, `new_key` |
| `apps/ingestion/forms.py` | modify | re-export `ReviewForm` (code map location) |
| `apps/ingestion/services.py` | modify | `save_review` |
| `apps/ingestion/views.py` | modify | `review` |
| `apps/ingestion/urls.py` | modify | `review` route |
| `apps/ingestion/templates/ingestion/review.html` | create | The review page |
| `apps/ingestion/tests/test_review.py` | create | Tests |

### Steps

**1. Grid data shape (already done in S2-05).** S2-05 shipped the grid dataclasses in `apps/outcomes/matrix.py` with the two fields this screen needs: `GridCell.origin` (`""`, `"document"`, `"derived"`, `"ai_suggested"`, and `"manual"` for a value a human edited) and `GridCell.rationale` (one sentence, shown on hover for AI-suggested cells). It also shipped the coloured cells, the `doc` / `calc` / `AI` text markers, the visually hidden text for screen readers, and the `--pl-origin-*` tint tokens in `polaris.css`. **Don't copy or replace `templates/includes/weight_grid.html` in this story.** It also holds the `{% partialdef cell %}` and the HTMX attributes the Mapping tab's live validation depends on (B5 AC2), and a replaced copy would silently break them.

**2. How the review screen uses the include.** It builds two `WeightGrid` objects in `build_review_grids` (step 3) and includes the component exactly like the Mapping tab does:

```django
{% include "includes/weight_grid.html" with grid=a_lo_grid editable=True only %}
```

Two differences from the Mapping tab, both deliberate:

- **No live validation.** The review grids leave `WeightGrid.validate_url` empty, so the include renders plain inputs without `hx-post`. The cells in a review are named by draft keys (`alo__a1__l2`), not database ids, so `outcomes:validate_cell` couldn't parse them. They are validated on **Save draft** with the same `validate_assessment_lo_cell` / `validate_lo_po_cell` functions instead, so the rules are identical.
- **A legend.** The review page shows all three origin colours, so it adds a legend above the grids (step 6). The Mapping tab only ever shows the AI colour and has its own one-line legend.

The cell-naming helpers in `review.py` (`cell_name`, `A_LO = "alo"`, `LO_PO = "lopo"`) are local to the review form and are **not** the ones in `outcomes/matrix.py` (which name cells by database id, `a_lo-12-34`). Import them from `apps.ingestion.review`, never mix the two.

**3. The review form.** A review contains four kinds of input: an LO list, an assessment list, and two grids whose rows and columns depend on those lists. One Django `Form` can't express that, so `ReviewForm` is a small plain class holding two formsets and the grid inputs, with one `is_valid()` and one `to_draft()`. The rules:

- **Rows are identified by keys** (`l1`, `a2`), carried in hidden fields. A new row typed into the blank extra form gets a fresh key (`n1`, `n2`…). Deleting a row (the formset's DELETE box) drops every grid cell that pointed at it.
- **LO numbers are renumbered 1..n** in display order on save, so B4 AC1 (contiguous numbers) already holds before Apply.
- **Origin tracking.** A grid cell keeps its origin and rationale only if its value is unchanged. Any edit, including clearing and retyping, makes it `manual`. That's how a violet cell turns plain the moment a human decides (L007's definition).
- **Grid cells are validated** with the same `validate_assessment_lo_cell` / `validate_lo_po_cell` that B5 uses, so the review screen can never accept a weight that the Mapping tab would refuse.
- **New rows appear in the grids after Save draft.** The page is a normal form post: adding an LO and saving re-renders the grids with a new column. This is simpler and sturdier than growing the grid in JavaScript.

```python
# apps/ingestion/review.py
"""The review screen's form logic (T1.2 step 3). Pure: no database writes."""
from __future__ import annotations

import itertools
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.outcomes.matrix import (
    GridCell, GridCol, GridRow, WeightGrid, validate_assessment_lo_cell, validate_lo_po_cell,
)
from apps.outcomes.models import Assessment

from .validation import (
    DraftALO, DraftAssessment, DraftLO, DraftLOPO, Origin, ReviewDraft,
)

A_LO = "alo"
LO_PO = "lopo"


def cell_name(prefix: str, row_key: str, col_key: str | int) -> str:
    return f"{prefix}__{row_key}__{col_key}"


def new_key(taken: set[str]) -> str:
    for n in itertools.count(1):
        key = f"n{n}"
        if key not in taken:
            taken.add(key)
            return key
    raise AssertionError("unreachable")


def _fmt(value: Decimal | int | None) -> str:
    """40.00 -> '40', 33.50 -> '33.5'. Same idea as the |weight filter."""
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    text = format(value.normalize(), "f")
    return text


class LOForm(forms.Form):
    key = forms.CharField(widget=forms.HiddenInput, required=False)
    source_quote = forms.CharField(widget=forms.HiddenInput, required=False)
    description = forms.CharField(label="Learning outcome", max_length=2000,
                                  widget=forms.Textarea(attrs={"rows": 2}))


class AssessmentForm(forms.Form):
    key = forms.CharField(widget=forms.HiddenInput, required=False)
    source_quote = forms.CharField(widget=forms.HiddenInput, required=False)
    name = forms.CharField(max_length=100)
    kind = forms.ChoiceField(choices=Assessment.Kind.choices)
    max_score = forms.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"),
                                   initial=Decimal("100"))
    course_weight = forms.DecimalField(label="Course %", max_digits=5, decimal_places=2,
                                       required=False, min_value=Decimal("0.01"),
                                       max_value=Decimal("100"))


LOFormSet = forms.formset_factory(LOForm, extra=1, can_delete=True)
AssessmentFormSet = forms.formset_factory(AssessmentForm, extra=1, can_delete=True)


class ReviewForm:
    """Formsets for LOs and assessments plus both grids, built from a ReviewDraft."""

    def __init__(self, draft: ReviewDraft, po_set, data=None):
        self.draft = draft
        self.pos = list(po_set.outcomes.order_by("number"))
        self.data = data
        self.is_bound = data is not None
        self.lo_formset = LOFormSet(
            data, prefix="lo",
            initial=[{"key": lo.key, "description": lo.description, "source_quote": lo.source_quote}
                     for lo in draft.los])
        self.assessment_formset = AssessmentFormSet(
            data, prefix="as",
            initial=[{"key": a.key, "name": a.name, "kind": a.kind, "max_score": a.max_score,
                      "course_weight": a.course_weight, "source_quote": a.source_quote}
                     for a in draft.assessments])
        self.cell_errors: dict[str, str] = {}
        self.non_form_errors: list[str] = []
        self._cleaned: ReviewDraft | None = None

    # ---------- validation ----------

    def is_valid(self) -> bool:
        if not self.is_bound:
            return False
        ok = self.lo_formset.is_valid() & self.assessment_formset.is_valid()
        if not ok:
            return False
        draft = self._build_draft()
        if not draft.los:
            self.non_form_errors.append("Keep at least one learning outcome.")
        names = [a.name.strip().casefold() for a in draft.assessments]
        if len(names) != len(set(names)):
            self.non_form_errors.append("Two assessments have the same name. Rename one of them.")
        if self.cell_errors or self.non_form_errors:
            return False
        self._cleaned = draft
        return True

    def to_draft(self) -> ReviewDraft:
        if self._cleaned is None:
            raise ValueError("call is_valid() first")
        return self._cleaned

    @staticmethod
    def _kept_forms(formset):
        """Rows that survive: not ticked for removal, and not the untouched blank extra row
        (an unchanged extra form validates with empty cleaned_data)."""
        return [f for f in formset.forms
                if f.cleaned_data and not f.cleaned_data.get("DELETE")]

    def _build_draft(self) -> ReviewDraft:
        old = self.draft
        taken = {lo.key for lo in old.los} | {a.key for a in old.assessments}

        los = []
        for number, f in enumerate(self._kept_forms(self.lo_formset), start=1):
            key = f.cleaned_data["key"] or new_key(taken)
            los.append(DraftLO(key=key, number=number,
                               description=f.cleaned_data["description"].strip(),
                               source_quote=f.cleaned_data["source_quote"] or ""))
        assessments = []
        for f in self._kept_forms(self.assessment_formset):
            cd = f.cleaned_data
            assessments.append(DraftAssessment(
                key=cd["key"] or new_key(taken), name=cd["name"].strip(), kind=cd["kind"],
                max_score=cd["max_score"], course_weight=cd["course_weight"],
                source_quote=cd["source_quote"] or ""))

        lo_keys = {lo.key for lo in los}
        a_keys = {a.key for a in assessments}
        old_alo = {(c.assessment_key, c.lo_key): c for c in old.a_lo}
        old_lopo = {(c.lo_key, c.po_number): c for c in old.lo_po}

        a_lo = []
        for a in assessments:
            for lo in los:
                name = cell_name(A_LO, a.key, lo.key)
                if name not in self.data:          # new row/column: not on the page yet
                    prev = old_alo.get((a.key, lo.key))
                    if prev:
                        a_lo.append(prev)
                    continue
                try:
                    value = validate_assessment_lo_cell(self.data.get(name, ""))
                except ValidationError as e:
                    self.cell_errors[name] = " ".join(e.messages)
                    continue
                if value is None:
                    continue
                prev = old_alo.get((a.key, lo.key))
                origin = prev.origin if prev and prev.weight == value else Origin.MANUAL
                a_lo.append(DraftALO(a.key, lo.key, value, origin))

        po_numbers = [po.number for po in self.pos]
        lo_po = []
        for lo in los:
            for number in po_numbers:
                name = cell_name(LO_PO, lo.key, number)
                if name not in self.data:
                    prev = old_lopo.get((lo.key, number))
                    if prev:
                        lo_po.append(prev)
                    continue
                try:
                    value = validate_lo_po_cell(self.data.get(name, ""))
                except ValidationError as e:
                    self.cell_errors[name] = " ".join(e.messages)
                    continue
                if value is None:
                    continue
                prev = old_lopo.get((lo.key, number))
                if prev and prev.weight == value:
                    lo_po.append(prev)
                else:
                    lo_po.append(DraftLOPO(lo.key, number, value, Origin.MANUAL))

        # Cells pointing at deleted rows or columns are dropped by construction:
        # the loops above only visit keys that are still present.
        assert {c.lo_key for c in a_lo} <= lo_keys and {c.assessment_key for c in a_lo} <= a_keys

        draft = ReviewDraft(course=old.course, los=los, assessments=assessments, a_lo=a_lo,
                            lo_po=lo_po, course_po_levels=dict(old.course_po_levels))
        draft.warnings = review_warnings(draft)
        return draft

    # ---------- rendering ----------

    def grids(self) -> tuple[WeightGrid, WeightGrid]:
        return build_review_grids(self.draft, self.pos, posted=self.data,
                                  errors=self.cell_errors)


def build_review_grids(draft: ReviewDraft, pos, *, posted=None, errors=None):
    """Both grids for the template. `posted` (a QueryDict) wins over draft values so an
    invalid submission re-renders exactly what the user typed."""
    errors = errors or {}
    alo = {(c.assessment_key, c.lo_key): c for c in draft.a_lo}
    lopo = {(c.lo_key, c.po_number): c for c in draft.lo_po}

    def shown(name, current):
        if posted is not None and name in posted:
            return posted.get(name, "")
        return current

    a_lo_rows = []
    for a in draft.assessments:
        cells = []
        for lo in draft.los:
            name = cell_name(A_LO, a.key, lo.key)
            c = alo.get((a.key, lo.key))
            cells.append(GridCell(name=name, value=shown(name, _fmt(c.weight) if c else ""),
                                  label=f"{a.name} to LO {lo.number}", error=errors.get(name, ""),
                                  origin=c.origin if c else ""))
        a_lo_rows.append(GridRow(label=a.name, cells=cells, tooltip=a.source_quote))
    a_lo_grid = WeightGrid(
        kind="a_lo", caption="Assessment → LO weights (%). Blank = this assessment doesn't measure that LO.",
        cols=[GridCol(f"LO {lo.number}", lo.description) for lo in draft.los], rows=a_lo_rows)

    lo_po_rows = []
    totals = {po.number: 0 for po in pos}
    for lo in draft.los:
        cells = []
        for po in pos:
            name = cell_name(LO_PO, lo.key, po.number)
            c = lopo.get((lo.key, po.number))
            if c:
                totals[po.number] += c.weight
            cells.append(GridCell(name=name, value=shown(name, str(c.weight) if c else ""),
                                  label=f"LO {lo.number} to PO {po.number}", error=errors.get(name, ""),
                                  origin=c.origin if c else "", rationale=c.rationale if c else ""))
        lo_po_rows.append(GridRow(label=f"LO {lo.number}", cells=cells, tooltip=lo.description))
    levels = draft.course_po_levels
    cols = [GridCol(f"PO {po.number}",
                    po.description + (f" (syllabus level: {levels[po.number]})" if po.number in levels else ""))
            for po in pos]
    lo_po_grid = WeightGrid(kind="lo_po", caption="LO → PO weights (1–5). Blank = no contribution.",
                            cols=cols, rows=lo_po_rows, footer=[str(totals[po.number]) for po in pos])
    return a_lo_grid, lo_po_grid


def review_warnings(draft: ReviewDraft) -> list[str]:
    """Recomputed after every save, so the panel always describes what is on screen."""
    out = []
    weights = [a.course_weight for a in draft.assessments if a.course_weight is not None]
    if weights and abs(sum(weights) - Decimal("100")) > 1:
        out.append(f"Course weights sum to {_fmt(sum(weights))}%, not 100%.")
    if draft.assessments and len(weights) < len(draft.assessments):
        out.append("Some assessments have no course weight.")
    measured = {c.lo_key for c in draft.a_lo}
    linked = {c.lo_key for c in draft.lo_po}
    used = {c.assessment_key for c in draft.a_lo}
    for lo in draft.los:
        if lo.key not in measured:
            out.append(f"LO {lo.number} is not measured by any assessment, so it can never get a score.")
        if lo.key not in linked:
            out.append(f"LO {lo.number} has no PO link, so it contributes to no program outcome.")
    for a in draft.assessments:
        if a.key not in used:
            out.append(f"{a.name} measures no LO, so its grades won't count toward any score.")
    for c in draft.lo_po:
        level = draft.course_po_levels.get(c.po_number)
        if level is not None and c.weight > level:
            lo_number = next(lo.number for lo in draft.los if lo.key == c.lo_key)
            out.append(f"LO {lo_number} → PO {c.po_number} is {c.weight}, above the syllabus's "
                       f"course-level contribution ({level}).")
    return out


def course_mismatches(draft: ReviewDraft, offering) -> list[str]:
    """Fields where the syllabus disagrees with the catalog. Shown, never auto-fixed:
    the catalog belongs to the head (B3)."""
    def norm(s):
        return "".join((s or "").split()).casefold()
    course = offering.course
    out = []
    c = draft.course
    if c.code and norm(c.code) != norm(course.code):
        out.append(f"Code: syllabus says {c.code}, catalog says {course.code}")
    if c.title and norm(c.title) != norm(course.title):
        out.append(f"Title: syllabus says “{c.title}”, catalog says “{course.title}”")
    if c.credits is not None and c.credits != course.credits:
        out.append(f"Credits: syllabus says {_fmt(c.credits)}, catalog says {_fmt(course.credits)}")
    if c.ects is not None and c.ects != course.ects:
        out.append(f"ECTS: syllabus says {_fmt(c.ects)}, catalog says {_fmt(course.ects)}")
    return out
```

A note on `_kept_forms`: Django skips validation of an extra form the user didn't touch, and its `cleaned_data` is an empty dict. That's how the blank "add a row" line is ignored. Clearing the text of an existing row is a validation error ("This field is required"); removing a row is done with the Remove box.

```python
# apps/ingestion/forms.py  (add at the bottom so `from apps.ingestion.forms import ReviewForm` works)
from .review import ReviewForm  # noqa: E402,F401
```

**4. `save_review`.** It stores the edited draft on the job. It's deliberately **not** audited: the draft isn't course data, and the audit trail records what Apply writes. It refuses anything that isn't `READY`, so an applied job can't be edited afterwards. It locks the job row so a Save and an Apply racing in two tabs can't interleave.

```python
# apps/ingestion/services.py  (add)
def save_review(user, job: IngestionJob, draft) -> IngestionJob:
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().get(pk=job.pk)
        if job.status != IngestionJob.Status.READY:
            raise ValidationError("This upload can no longer be edited "
                                  f"(it is {job.get_status_display().lower()}).")
        result = draft.to_json()
        result["meta"] = (job.result or {}).get("meta", {})
        job.result = result
        job.warnings = list(draft.warnings)
        job.save(update_fields=["result", "warnings", "updated_at"])
    return job
```

**5. The view.** GET builds the form from the stored draft. POST validates. If invalid, the page re-renders with per-cell errors and the user's own input. If valid, `save_review` runs, and we redirect (Post/Redirect/Get, so refreshing doesn't resubmit) with a "Draft saved" message. The Apply button posts the same form to `ingestion:apply` via `formaction`. S6-03's view validates and saves it first, then applies, so unsaved edits are never lost.

```python
# apps/ingestion/views.py  (add)
from apps.catalog.selectors import active_po_set

from .review import ReviewForm, build_review_grids, course_mismatches
from .services import save_review
from .validation import ReviewDraft


def _review_context(job, offering, perms_for, form):
    a_lo_grid, lo_po_grid = form.grids()
    has_grades = offering.assessments.filter(grades__isnull=False).exists()
    has_setup = offering.learning_outcomes.exists() or offering.assessments.exists()
    return {
        "job": job, "offering": offering, "perms_for": perms_for, "form": form,
        "a_lo_grid": a_lo_grid, "lo_po_grid": lo_po_grid,
        "warnings": form.draft.warnings, "mismatches": course_mismatches(form.draft, offering),
        "has_setup": has_setup, "has_grades": has_grades,
    }


@login_required
@require_job_access
@require_http_methods(["GET", "POST"])
def review(request, job, offering, perms_for):
    if job.status != IngestionJob.Status.READY:
        return redirect("ingestion:job", job_id=job.pk)
    po_set = active_po_set(offering.course.program)
    draft = ReviewDraft.from_json(job.result)
    form = ReviewForm(draft, po_set, data=request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            try:
                save_review(request.user, job, form.to_draft())
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
                return redirect("ingestion:job", job_id=job.pk)
            messages.success(request, "Draft saved. Nothing has been written to the course yet.")
            return redirect("ingestion:review", job_id=job.pk)
        messages.error(request, "Some values need fixing. They are marked in red.")
    return render(request, "ingestion/review.html", _review_context(job, offering, perms_for, form))
```

`has_grades` uses `grades__isnull=False` on the reverse relation. That means "at least one Grade row exists", which is stricter than S6-03's check, so the page may warn in a case where Apply would still succeed. The warning is only advisory: S6-03's service makes the real decision.

```python
# apps/ingestion/urls.py  (add)
path("ingestion/<int:job_id>/review/", views.review, name="review"),
```

**6. The template.** It follows the wireframe in spec §8.4 (Syllabus review). The Discard button belongs to a separate form, because HTML forms can't nest. It uses the `form` attribute to submit that form from inside the header.

```django
{# apps/ingestion/templates/ingestion/review.html #}
{% extends "base.html" %}
{% block title %}Review · {{ job.original_filename }}{% endblock %}
{% block content %}
<form id="discard-form" method="post" action="{% url 'ingestion:discard' job.pk %}">{% csrf_token %}</form>

<form method="post" action="{% url 'ingestion:review' job.pk %}" novalidate>
  {% csrf_token %}
  <div class="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3 pl-sticky-actions">
    <div>
      <h1 class="h4 mb-0">Review what we read from {{ job.original_filename }}</h1>
      <p class="text-body-secondary small mb-0">{{ offering.course.code }} · {{ offering.term.name }} ·
        nothing is saved to the course until you click Apply</p>
    </div>
    <div class="d-flex gap-2">
      <button type="submit" form="discard-form" class="btn btn-outline-danger">Discard</button>
      <button type="submit" class="btn btn-outline-primary">Save draft</button>
      <button type="submit" class="btn btn-primary" formaction="{% url 'ingestion:apply' job.pk %}">Apply to course ▶</button>
    </div>
  </div>

  {% if form.non_form_errors %}<div class="alert alert-danger">{{ form.non_form_errors|join:" " }}</div>{% endif %}

  {% if warnings %}
  <div class="alert alert-warning" role="status">
    <p class="fw-semibold mb-1">Check these before applying</p>
    <ul class="mb-0">{% for w in warnings %}<li>{{ w }}</li>{% endfor %}</ul>
  </div>
  {% endif %}

  {% if has_setup %}
  <div class="alert {% if has_grades %}alert-danger{% else %}alert-info{% endif %}">
    {% if has_grades %}
      This course already has grades, so applying a syllabus is not possible. Edit the setup by hand instead.
    {% else %}
      This course already has a setup.
      <div class="form-check mt-1">
        <input class="form-check-input" type="checkbox" name="replace" value="1" id="replace">
        <label class="form-check-label" for="replace">Replace the current learning outcomes, assessments and weights</label>
      </div>
    {% endif %}
  </div>
  {% endif %}

  <section class="card mb-3" aria-labelledby="course-h">
    <div class="card-body">
      <h2 id="course-h" class="h5">Course</h2>
      <p class="mb-1">{{ form.draft.course.code|default:"—" }} · {{ form.draft.course.title|default:"—" }}</p>
      {% if mismatches %}
        <ul class="small text-warning-emphasis mb-0">{% for m in mismatches %}<li>{{ m }}</li>{% endfor %}</ul>
        <p class="small text-body-secondary mb-0">The catalog is not changed. Ask the head if the catalog is wrong.</p>
      {% else %}
        <p class="small text-success mb-0">✓ Matches the catalog</p>
      {% endif %}
    </div>
  </section>

  <section class="card mb-3" aria-labelledby="lo-h">
    <div class="card-body">
      <h2 id="lo-h" class="h5">Learning outcomes</h2>
      {{ form.lo_formset.management_form }}
      {% for f in form.lo_formset %}
      <div class="row g-2 align-items-start mb-2">
        {{ f.key }}{{ f.source_quote }}
        <div class="col-auto pt-2 fw-semibold">{% if f.initial %}{{ forloop.counter }}{% else %}+{% endif %}</div>
        <div class="col">
          <label class="visually-hidden" for="{{ f.description.id_for_label }}">Learning outcome {{ forloop.counter }}</label>
          {{ f.description.as_widget }}
          {% for e in f.description.errors %}<div class="invalid-feedback d-block">{{ e }}</div>{% endfor %}
          {% if f.initial.source_quote %}
            <details class="small mt-1"><summary>Source in the syllabus</summary>
              <blockquote class="blockquote-footer mb-0 mt-1">{{ f.initial.source_quote }}</blockquote></details>
          {% endif %}
        </div>
        {% if f.initial %}<div class="col-auto pt-2">
          <div class="form-check"><input class="form-check-input" type="checkbox" name="{{ f.DELETE.html_name }}" id="{{ f.DELETE.id_for_label }}">
          <label class="form-check-label small" for="{{ f.DELETE.id_for_label }}">Remove</label></div></div>{% endif %}
      </div>
      {% endfor %}
      <p class="small text-body-secondary mb-0">Type into the last row to add an outcome, then Save draft to give it grid cells.</p>
    </div>
  </section>

  <section class="card mb-3" aria-labelledby="as-h">
    <div class="card-body">
      <h2 id="as-h" class="h5">Assessments</h2>
      {{ form.assessment_formset.management_form }}
      <div class="table-responsive">
      <table class="table table-sm align-middle">
        <thead><tr><th>Name</th><th>Kind</th><th>Max</th><th>Course %</th><th><span class="visually-hidden">Remove</span></th></tr></thead>
        <tbody>
        {% for f in form.assessment_formset %}
          <tr title="{{ f.initial.source_quote }}">
            <td>{{ f.key }}{{ f.source_quote }}{{ f.name.as_widget }}{% for e in f.name.errors %}<div class="invalid-feedback d-block">{{ e }}</div>{% endfor %}</td>
            <td>{{ f.kind.as_widget }}</td>
            <td style="max-width:7rem">{{ f.max_score.as_widget }}{% for e in f.max_score.errors %}<div class="invalid-feedback d-block">{{ e }}</div>{% endfor %}</td>
            <td style="max-width:7rem">{{ f.course_weight.as_widget }}{% for e in f.course_weight.errors %}<div class="invalid-feedback d-block">{{ e }}</div>{% endfor %}</td>
            <td>{% if f.initial %}<input class="form-check-input" type="checkbox" name="{{ f.DELETE.html_name }}" aria-label="Remove {{ f.initial.name }}">{% endif %}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
      </div>
    </div>
  </section>

  <section class="card mb-3" aria-labelledby="grid-h">
    <div class="card-body">
      <h2 id="grid-h" class="h5">Weights</h2>
      <p class="small mb-2">
        <span class="pl-legend__swatch" style="background:var(--pl-origin-document)"></span>doc: from the document ·
        <span class="pl-legend__swatch" style="background:var(--pl-origin-derived)"></span>calc: derived from the course weight ·
        <span class="pl-legend__swatch" style="background:var(--pl-origin-ai)"></span>AI: suggested by AI (hover for the reason) ·
        plain: entered by you
      </p>
      <div class="row g-4">
        <div class="col-xl-5">{% include "includes/weight_grid.html" with grid=a_lo_grid editable=True only %}</div>
        <div class="col-xl-7">{% include "includes/weight_grid.html" with grid=lo_po_grid editable=True only %}</div>
      </div>
    </div>
  </section>
</form>
{% endblock %}
```

The `replace` checkbox sits inside the main form, so it reaches the Apply view. `Save draft` ignores it.

`.pl-sticky-actions` keeps the buttons visible while scrolling long syllabi:

```css
.pl-sticky-actions { position: sticky; top: 0; z-index: 10; background: var(--bs-body-bg);
  padding: .5rem 0; border-bottom: 1px solid var(--bs-border-color-translucent); }
```

### Tests

```python
# apps/ingestion/tests/test_review.py
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.http import QueryDict
from django.urls import reverse

from apps.ingestion.models import IngestionJob
from apps.ingestion.review import (
    A_LO, LO_PO, ReviewForm, build_review_grids, cell_name, course_mismatches, review_warnings,
)
from apps.ingestion.validation import Origin, ReviewDraft

from .conftest import make_draft


def _post_from(form_draft, po_set, **overrides):
    """Build the POST a browser would send for an unchanged review page, then apply overrides."""
    data = {
        "lo-TOTAL_FORMS": str(len(form_draft.los) + 1), "lo-INITIAL_FORMS": str(len(form_draft.los)),
        "lo-MIN_NUM_FORMS": "0", "lo-MAX_NUM_FORMS": "1000",
        "as-TOTAL_FORMS": str(len(form_draft.assessments) + 1),
        "as-INITIAL_FORMS": str(len(form_draft.assessments)),
        "as-MIN_NUM_FORMS": "0", "as-MAX_NUM_FORMS": "1000",
    }
    for i, lo in enumerate(form_draft.los):
        data |= {f"lo-{i}-key": lo.key, f"lo-{i}-description": lo.description,
                 f"lo-{i}-source_quote": lo.source_quote}
    for i, a in enumerate(form_draft.assessments):
        data |= {f"as-{i}-key": a.key, f"as-{i}-name": a.name, f"as-{i}-kind": a.kind,
                 f"as-{i}-max_score": str(a.max_score), f"as-{i}-course_weight": str(a.course_weight),
                 f"as-{i}-source_quote": a.source_quote}
    a_grid, p_grid = build_review_grids(form_draft, list(po_set.outcomes.order_by("number")))
    for grid in (a_grid, p_grid):
        for row in grid.rows:
            for cell in row.cells:
                data[cell.name] = cell.value
    data.update(overrides)
    q = QueryDict(mutable=True)
    for k, v in data.items():
        q[k] = v
    return q


def test_unchanged_post_keeps_every_origin(wizard, draft):
    form = ReviewForm(draft, wizard.po_set, data=_post_from(draft, wizard.po_set))
    assert form.is_valid(), (form.cell_errors, form.non_form_errors)
    out = form.to_draft()
    assert {(c.assessment_key, c.lo_key, c.origin) for c in out.a_lo} == {
        ("a1", "l1", Origin.DERIVED), ("a1", "l2", Origin.DERIVED), ("a2", "l2", Origin.DOCUMENT)}
    assert {(c.lo_key, c.po_number, c.origin) for c in out.lo_po} == {
        ("l1", 1, Origin.DOCUMENT), ("l1", 2, Origin.AI_SUGGESTED), ("l2", 3, Origin.AI_SUGGESTED)}
    assert next(c for c in out.lo_po if c.po_number == 2).rationale == "Design trade-offs need analysis."


def test_editing_an_ai_cell_makes_it_manual_and_drops_rationale(wizard, draft):
    post = _post_from(draft, wizard.po_set, **{cell_name(LO_PO, "l1", 2): "3"})
    form = ReviewForm(draft, wizard.po_set, data=post)
    assert form.is_valid()
    cell = next(c for c in form.to_draft().lo_po if (c.lo_key, c.po_number) == ("l1", 2))
    assert (cell.weight, cell.origin, cell.rationale) == (3, Origin.MANUAL, "")


def test_clearing_a_cell_removes_the_arrow(wizard, draft):
    post = _post_from(draft, wizard.po_set, **{cell_name(A_LO, "a1", "l1"): ""})
    form = ReviewForm(draft, wizard.po_set, data=post)
    assert form.is_valid()
    assert ("a1", "l1") not in {(c.assessment_key, c.lo_key) for c in form.to_draft().a_lo}


@pytest.mark.parametrize("raw", ["0", "6", "2.5", "abc"])
def test_invalid_lo_po_cell_is_reported_and_nothing_saved(wizard, draft, raw):
    name = cell_name(LO_PO, "l2", 1)
    form = ReviewForm(draft, wizard.po_set, data=_post_from(draft, wizard.po_set, **{name: raw}))
    assert not form.is_valid()
    assert name in form.cell_errors
    a_grid, p_grid = form.grids()
    cell = next(c for row in p_grid.rows for c in row.cells if c.name == name)
    assert cell.value == raw and cell.error          # re-rendered with what the user typed


def test_deleting_an_lo_drops_its_cells_and_renumbers(wizard, draft):
    post = _post_from(draft, wizard.po_set, **{"lo-0-DELETE": "on"})
    form = ReviewForm(draft, wizard.po_set, data=post)
    assert form.is_valid()
    out = form.to_draft()
    assert [(lo.key, lo.number) for lo in out.los] == [("l2", 1)]
    assert all(c.lo_key == "l2" for c in out.a_lo + out.lo_po)


def test_new_lo_gets_a_fresh_key_and_appears_in_the_grids(wizard, draft):
    post = _post_from(draft, wizard.po_set, **{"lo-2-description": "Write tests first"})
    form = ReviewForm(draft, wizard.po_set, data=post)
    assert form.is_valid()
    out = form.to_draft()
    assert [lo.number for lo in out.los] == [1, 2, 3]
    assert out.los[2].key == "n1"
    a_grid, _ = build_review_grids(out, wizard.pos)
    assert [col.label for col in a_grid.cols] == ["LO 1", "LO 2", "LO 3"]
    assert any("LO 3 is not measured" in w for w in out.warnings)


def test_duplicate_assessment_names_are_refused(wizard, draft):
    form = ReviewForm(draft, wizard.po_set,
                      data=_post_from(draft, wizard.po_set, **{"as-1-name": "midterm i"}))
    assert not form.is_valid()
    assert "same name" in form.non_form_errors[0]


def test_warnings_cover_weights_unmeasured_and_level():
    d = make_draft()
    d.assessments[0].course_weight = Decimal("30")
    d.lo_po[0].weight = 5
    d.course_po_levels[1] = 3
    texts = review_warnings(d)
    assert "Course weights sum to 90%, not 100%." in texts
    assert any("above the syllabus's course-level contribution (3)" in t for t in texts)


def test_course_mismatch_ignores_spacing_and_case(wizard, draft):
    wizard.offering.course.code = "cse311"
    wizard.offering.course.title = "Software Engineering"
    wizard.offering.course.credits = Decimal("3")
    wizard.offering.course.ects = Decimal("5")
    assert course_mismatches(draft, wizard.offering) == ["ECTS: syllabus says 6, catalog says 5"]


@pytest.fixture
def ready_job(wizard, draft):
    return IngestionJob.objects.create(
        offering=wizard.offering, kind=IngestionJob.Kind.SYLLABUS, status=IngestionJob.Status.READY,
        file=ContentFile(b"%PDF-1.4", name="x.pdf"), original_filename="cse311.pdf",
        created_by=wizard.instructor, result=draft.to_json(), warnings=draft.warnings)


def test_review_page_shows_origins_and_rationale(client, wizard, ready_job):
    client.force_login(wizard.instructor)
    html = client.get(reverse("ingestion:review", args=[ready_job.pk])).content.decode()
    assert "pl-cell--ai_suggested" in html and "pl-cell--derived" in html and "pl-cell--document" in html
    assert 'title="Design trade-offs need analysis."' in html
    assert "Source in the syllabus" in html


def test_save_draft_stores_edits_but_writes_nothing_to_the_course(client, wizard, ready_job, draft):
    client.force_login(wizard.instructor)
    post = _post_from(draft, wizard.po_set, **{cell_name(LO_PO, "l1", 2): "3"})
    resp = client.post(reverse("ingestion:review", args=[ready_job.pk]), post)
    assert resp.status_code == 302
    ready_job.refresh_from_db()
    saved = ReviewDraft.from_json(ready_job.result)
    assert next(c for c in saved.lo_po if c.po_number == 2).origin == Origin.MANUAL
    assert not wizard.offering.learning_outcomes.exists()          # T1.2 AC2
    assert not wizard.offering.assessments.exists()


def test_review_of_applied_job_redirects(client, wizard, ready_job):
    IngestionJob.objects.filter(pk=ready_job.pk).update(status=IngestionJob.Status.APPLIED)
    client.force_login(wizard.instructor)
    resp = client.get(reverse("ingestion:review", args=[ready_job.pk]))
    assert resp.status_code == 302 and resp.url == reverse("ingestion:job", args=[ready_job.pk])
```

Remove the `xfail` marker from `test_ready_job_redirects_htmx_to_review` (S6-01) in this PR. `ingestion:review` already has its row in `ROUTES` (S2-02); check it matches `ingestion:job`.

### Check it works

1. With a `READY` job from S6-01, open `/ingestion/<id>/review/`. The four sections appear, cells are coloured, and the legend explains them.
2. Hover a violet cell: the reason appears. Tab into it with the keyboard: a screen reader (VoiceOver: Cmd+F5) reads "suggested by AI: …".
3. Type `6` into an LO→PO cell and click **Save draft**. The cell turns red with "Weights are whole numbers from 1 to 5" (S2-05's message), your `6` is still shown, and the other edits are kept.
4. Fix it to `3` and save. The cell is now plain (manual), and "Draft saved" appears.
5. Type a new LO into the blank row and save. It gets number 3, a new grid column appears, and the warning "LO 3 is not measured by any assessment" shows.
6. Tick **Remove** on LO 1 and save. Its row and column disappear, and LO 2 becomes LO 1.
7. Check the Mapping tab of the offering: still empty. Nothing was written.
8. Shrink the window to tablet width: the grids scroll horizontally and the action bar stays at the top.

### Done when

- [ ] T1.2 screen 3: four editable sections, colour-coded cells, rationale tooltips, quoted sources, warnings: `test_review_page_shows_origins_and_rationale`, `test_warnings_cover_weights_unmeasured_and_level`
- [ ] T1.2 AC2 (nothing written before Apply): `test_save_draft_stores_edits_but_writes_nothing_to_the_course`
- [ ] T1.2 AC5 (origin visible in the UI) and L007 groundwork (human edit → manual): `test_editing_an_ai_cell_makes_it_manual_and_drops_rationale`
- [ ] B5 AC2 holds in the review screen: `test_invalid_lo_po_cell_is_reported_and_nothing_saved`
- [ ] Course mismatches highlighted: `test_course_mismatch_ignores_spacing_and_case`
- [ ] Keyboard and screen-reader check (step 2) done; Lighthouse accessibility ≥ 90 on the page

### Commits and PR

```
Add origin and rationale to weight grid cells
Build the syllabus review form from a ReviewDraft
Add review page with source colours and warnings
Save review edits on the job without touching the course
```

PR title: **S6-02 Syllabus review screen** (`Closes #<issue>`). If you split it: **S6-02a Review form logic** and **S6-02b Review page**.

---
## S6-03 · Apply service: one transaction, replace rule, audit, `source` fields, discard

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S6-03-syllabus-apply` · **Depends on:** S6-01 (S6-02 for the button, not for the service)

### Goal

**Apply** turns the reviewed draft into real rows: LOs, assessments, assessment→LO weights and LO→PO weights. It all happens in one database transaction, so a crash halfway leaves the course exactly as it was. If the course already has a setup, Apply replaces it, but only when the instructor ticked "Replace" *and* no grades exist. **Discard** ends a job at any point. This delivers T1.2 screens 4–5 and AC 2 and 5 (spec Part 6), plus the §7.10 `test_apply.py` requirements.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/ingestion/services.py` | modify | `apply_syllabus_job`, `discard_job`, `check_draft`, `setup_snapshot` |
| `apps/ingestion/views.py` | modify | `apply`, `discard` |
| `apps/ingestion/urls.py` | modify | two routes |
| `apps/ingestion/tests/test_apply.py` | create | Tests |

### Steps

**1. Decide what "has grades" means.** The rule in T1.2 is "allowed only when it has no grades". A `Grade` row can exist with an empty score: an instructor typed a value in the sheet and then deleted it. That isn't a grade. We count a grade as present when it has a draft score, a published score, or is excused. Empty rows are removed with their assessment by the database cascade.

**2. Where `source` lives.** `LearningOutcome.source` and `LOPOWeight.source` exist (spec §5.2), so:

| Draft value | Stored as |
|---|---|
| LO from the document | `LearningOutcome.source = syllabus` |
| LO typed in the review screen (key starts with `n`) | `source = manual` |
| LO→PO with origin `document` | `LOPOWeight.source = syllabus` |
| LO→PO with origin `ai_suggested` | `source = ai_suggested`, `rationale` kept (lint L007 flags it) |
| LO→PO with origin `manual` | `source = manual` |
| Assessment→LO weight (any origin) | no `source` column on `AssessmentLOWeight`; the origin is kept in the audit event |

`Assessment` and `AssessmentLOWeight` have no `source` field. Rather than change the data model in Sprint 6, the `syllabus.apply` audit event stores the full created setup **with each value's origin**. T1.2 AC5 says "visible in the UI and audit trail": for those two tables, the audit trail is where the origin is visible. This gap is listed under "Spec contradictions" at the end of this chapter.

**3. Re-check the draft on the server.** The review form validated the draft, but Apply must not trust that: the job could have been saved by older code, or a buggy form. `check_draft` repeats the rules that the database constraints would otherwise turn into a 500: LO numbers 1..n, weights in range, unique assessment names, no arrows to unknown rows, POs inside the active set.

**4. The service.** Things to understand:

- **Lock order.** `select_for_update` on the job first (two clicks on Apply: the second waits, then sees `APPLIED` and stops), then on the offering row. Every setup-writing service in `outcomes.services` should lock the offering the same way. Then a teammate saving the Mapping tab during an Apply waits instead of mixing rows.
- **`bulk_create`** writes each table in one `INSERT`. On PostgreSQL it returns the objects with their new ids, which we need for the weight rows.
- **One audit event for the whole setup** (`syllabus.apply`, attached to the offering), plus a `setup.replace` event holding the old setup when something was replaced. It's the same reasoning as the matrix save in spec §5.4: an auditor wants to read "the syllabus set up the course like this", not 40 separate row inserts.
- **The syllabus file is attached to the offering** (`CourseOffering.syllabus`), so the course page can link to the document the setup came from.

```python
# apps/ingestion/services.py  (add)
from django.db.models import Q

from apps.catalog.models import CourseOffering
from apps.catalog.selectors import active_po_set
from apps.grading.models import Grade
from apps.outcomes.models import (
    Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight, Source,
)

from .validation import Origin, ReviewDraft

LOPO_SOURCE = {Origin.DOCUMENT: Source.SYLLABUS, Origin.AI_SUGGESTED: Source.AI_SUGGESTED,
               Origin.MANUAL: Source.MANUAL}


def offering_has_grades(offering) -> bool:
    return Grade.objects.filter(assessment__offering=offering).filter(
        Q(score__isnull=False) | Q(published_score__isnull=False) | Q(is_excused=True)).exists()


def check_draft(draft: ReviewDraft, po_numbers: set[int]) -> list[str]:
    """Problems that would make Apply fail or write nonsense. Empty list = OK."""
    problems = []
    if not draft.los:
        problems.append("There are no learning outcomes.")
    if [lo.number for lo in draft.los] != list(range(1, len(draft.los) + 1)):
        problems.append("Learning outcome numbers must be 1, 2, 3… in order.")
    names = [a.name.strip() for a in draft.assessments]
    if any(not n for n in names):
        problems.append("Every assessment needs a name.")
    if len(names) != len(set(names)):
        problems.append("Two assessments have the same name.")
    for a in draft.assessments:
        if a.kind not in Assessment.Kind.values:
            problems.append(f"{a.name}: unknown kind “{a.kind}”.")
        if a.max_score <= 0:
            problems.append(f"{a.name}: max score must be positive.")
        if a.course_weight is not None and not (0 < a.course_weight <= 100):
            problems.append(f"{a.name}: course weight must be between 0 and 100.")
    lo_keys = {lo.key for lo in draft.los}
    a_keys = {a.key for a in draft.assessments}
    for c in draft.a_lo:
        if c.assessment_key not in a_keys or c.lo_key not in lo_keys:
            problems.append("A weight points at a removed row. Save the draft again.")
        elif not (0 < c.weight <= 100):
            problems.append("Assessment → LO weights must be between 0 and 100.")
    for c in draft.lo_po:
        if c.lo_key not in lo_keys:
            problems.append("A weight points at a removed learning outcome. Save the draft again.")
        elif c.po_number not in po_numbers:
            problems.append(f"PO {c.po_number} is not in the program's active outcome list.")
        elif not (1 <= c.weight <= 5):
            problems.append("LO → PO weights must be whole numbers from 1 to 5.")
    return list(dict.fromkeys(problems))           # de-duplicate, keep order


def setup_snapshot(offering) -> dict:
    """JSON-safe picture of an offering's whole setup, for the audit trail."""
    los = list(offering.learning_outcomes.order_by("number"))
    assessments = list(offering.assessments.all())
    return {
        "los": [{"number": lo.number, "description": lo.description, "source": lo.source} for lo in los],
        "assessments": [{"name": a.name, "kind": a.kind, "max_score": str(a.max_score),
                         "course_weight": None if a.course_weight is None else str(a.course_weight)}
                        for a in assessments],
        "a_lo": [{"assessment": w.assessment.name, "lo": w.learning_outcome.number, "weight": str(w.weight)}
                 for w in AssessmentLOWeight.objects.filter(assessment__offering=offering)
                 .select_related("assessment", "learning_outcome")],
        "lo_po": [{"lo": w.learning_outcome.number, "po": w.program_outcome.number, "weight": w.weight,
                   "source": w.source}
                  for w in LOPOWeight.objects.filter(learning_outcome__offering=offering)
                  .select_related("learning_outcome", "program_outcome")],
    }


def apply_syllabus_job(user, job: IngestionJob, *, replace: bool = False) -> CourseOffering:
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().get(pk=job.pk)
        if job.status != IngestionJob.Status.READY:
            raise ValidationError("This upload was already applied or discarded.")
        offering = (CourseOffering.objects.select_for_update()
                    .select_related("course__program", "term").get(pk=job.offering_id))
        ensure_term_open(offering)

        draft = ReviewDraft.from_json(job.result)
        po_set = active_po_set(offering.course.program)
        pos_by_number = {po.number: po for po in po_set.outcomes.all()}
        problems = check_draft(draft, set(pos_by_number))
        if problems:
            raise ValidationError(problems)

        has_setup = offering.learning_outcomes.exists() or offering.assessments.exists()
        if has_setup:
            if offering_has_grades(offering):
                raise ValidationError("This course already has grades, so its setup can't be replaced "
                                      "from a syllabus. Edit the setup by hand instead.")
            if not replace:
                raise ValidationError("This course already has a setup. Tick “Replace the current "
                                      "learning outcomes…” to replace it.")
            before = setup_snapshot(offering)
            offering.assessments.all().delete()          # cascades: weights, empty grade rows
            offering.learning_outcomes.all().delete()    # cascades: LO→PO weights
            audit.record(user, "setup.replace", offering, before=before, after=None, offering=offering)

        los = LearningOutcome.objects.bulk_create([
            LearningOutcome(offering=offering, number=lo.number, description=lo.description,
                            source=Source.MANUAL if lo.key.startswith("n") else Source.SYLLABUS)
            for lo in draft.los])
        lo_by_key = {d.key: obj for d, obj in zip(draft.los, los, strict=True)}

        assessments = Assessment.objects.bulk_create([
            Assessment(offering=offering, name=a.name.strip(), kind=a.kind, max_score=a.max_score,
                       course_weight=a.course_weight, position=i)
            for i, a in enumerate(draft.assessments)])
        a_by_key = {d.key: obj for d, obj in zip(draft.assessments, assessments, strict=True)}

        AssessmentLOWeight.objects.bulk_create([
            AssessmentLOWeight(assessment=a_by_key[c.assessment_key], learning_outcome=lo_by_key[c.lo_key],
                               weight=c.weight)
            for c in draft.a_lo])
        LOPOWeight.objects.bulk_create([
            LOPOWeight(learning_outcome=lo_by_key[c.lo_key], program_outcome=pos_by_number[c.po_number],
                       weight=c.weight, source=LOPO_SOURCE[c.origin],
                       rationale=c.rationale if c.origin == Origin.AI_SUGGESTED else "")
            for c in draft.lo_po])

        offering.syllabus = job.file.name
        offering.save(update_fields=["syllabus"])
        job.status = IngestionJob.Status.APPLIED
        job.applied_at = timezone.now()
        job.save(update_fields=["status", "applied_at", "updated_at"])

        after = draft.to_json()
        after.pop("meta", None)
        after["job_id"] = job.pk
        after["file"] = job.original_filename
        audit.record(user, "syllabus.apply", offering, after=after, offering=offering)
    return offering


def discard_job(user, job: IngestionJob) -> IngestionJob:
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().get(pk=job.pk)
        if job.status == IngestionJob.Status.APPLIED:
            raise ValidationError("This upload was already applied. Change the setup on the course pages.")
        if job.status == IngestionJob.Status.DISCARDED:
            return job
        job.status = IngestionJob.Status.DISCARDED
        job.save(update_fields=["status", "updated_at"])
        audit.record(user, "syllabus.discard", job, offering=job.offering)
    return job
```

The audit `after` for `syllabus.apply` is the draft itself, so it carries the origin of every value (`document`, `derived`, `ai_suggested`, `manual`) for all four tables. T1.4's history viewer (Sprint 7) shows it as "Set up from syllabus cse311.pdf".

The file stays on disk after a discard. It's small, and it's evidence if someone asks "what did that upload say?". A cleanup command for files older than a term is Sprint 8 polish, not needed now.

**5. Views.** `apply` receives the whole review form: it validates and saves the edits first, then applies, so a change typed just before clicking Apply isn't lost. If anything fails, the instructor lands back on the review page with the reason.

```python
# apps/ingestion/views.py  (add)
from django.views.decorators.http import require_POST

from .services import apply_syllabus_job, discard_job


@login_required
@require_job_access
@require_POST
def apply(request, job, offering, perms_for):
    if job.status != IngestionJob.Status.READY:
        return redirect("ingestion:job", job_id=job.pk)
    form = ReviewForm(ReviewDraft.from_json(job.result), active_po_set(offering.course.program),
                      data=request.POST)
    if not form.is_valid():
        messages.error(request, "Some values need fixing before applying. They are marked in red.")
        return render(request, "ingestion/review.html",
                      _review_context(job, offering, perms_for, form), status=422)
    try:
        save_review(request.user, job, form.to_draft())
        apply_syllabus_job(request.user, job, replace=request.POST.get("replace") == "1")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("ingestion:review", job_id=job.pk)
    messages.success(request, f"{offering.course.code} is set up from {job.original_filename}. "
                              "AI-suggested PO weights are marked until you confirm them.")
    return redirect("outcomes:mapping", offering_id=offering.pk)


@login_required
@require_job_access
@require_POST
def discard(request, job, offering, perms_for):
    try:
        discard_job(request.user, job)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("ingestion:job", job_id=job.pk)
    messages.info(request, "Upload discarded. Nothing was changed.")
    return redirect("catalog:offering", offering_id=offering.pk)
```

Status 422 on the invalid re-render tells tests (and HTMX, if we ever boost this form) that the submission failed, while the browser still shows the page normally.

```python
# apps/ingestion/urls.py  (add)
path("ingestion/<int:job_id>/apply/", views.apply, name="apply"),
path("ingestion/<int:job_id>/discard/", views.discard, name="discard"),
```

Add both to the permission matrix as POST-only rows: allowed roles get 302, others 404. The matrix must build a fresh `READY` job per row, because a successful Apply consumes it.

### Tests

```python
# apps/ingestion/tests/test_apply.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import AssessmentFactory, EnrollmentFactory, GradeFactory, LearningOutcomeFactory
from apps.grading.models import Grade
from apps.ingestion.models import IngestionJob
from apps.ingestion.services import apply_syllabus_job, check_draft, discard_job
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight, Source

from .conftest import make_draft


@pytest.fixture
def ready_job(wizard, draft):
    return IngestionJob.objects.create(
        offering=wizard.offering, kind=IngestionJob.Kind.SYLLABUS, status=IngestionJob.Status.READY,
        file=ContentFile(b"%PDF-1.4", name="x.pdf"), original_filename="cse311.pdf",
        created_by=wizard.instructor, result=draft.to_json())


def test_apply_creates_exactly_the_reviewed_setup(wizard, ready_job):
    apply_syllabus_job(wizard.instructor, ready_job)
    off = wizard.offering
    assert [(lo.number, lo.source) for lo in off.learning_outcomes.all()] == [
        (1, Source.SYLLABUS), (2, Source.SYLLABUS)]
    assert [(a.name, a.course_weight, a.position) for a in off.assessments.all()] == [
        ("Midterm I", Decimal("40"), 0), ("Project", Decimal("60"), 1)]
    assert sorted((w.assessment.name, w.learning_outcome.number, w.weight)
                  for w in AssessmentLOWeight.objects.filter(assessment__offering=off)) == [
        ("Midterm I", 1, Decimal("40")), ("Midterm I", 2, Decimal("40")), ("Project", 2, Decimal("60"))]
    lopo = {(w.learning_outcome.number, w.program_outcome.number): w
            for w in LOPOWeight.objects.filter(learning_outcome__offering=off)}
    assert {k: (w.weight, w.source) for k, w in lopo.items()} == {
        (1, 1): (4, Source.SYLLABUS), (1, 2): (2, Source.AI_SUGGESTED), (2, 3): (5, Source.AI_SUGGESTED)}
    assert lopo[(1, 2)].rationale == "Design trade-offs need analysis."
    ready_job.refresh_from_db()
    assert ready_job.status == IngestionJob.Status.APPLIED and ready_job.applied_at
    off.refresh_from_db()
    assert off.syllabus.name == ready_job.file.name


def test_apply_writes_one_audit_event_with_origins(wizard, ready_job):
    apply_syllabus_job(wizard.instructor, ready_job)
    event = AuditEvent.objects.get(action="syllabus.apply")
    assert event.actor == wizard.instructor and event.offering == wizard.offering
    origins = {c["origin"] for c in event.after["a_lo"]}
    assert origins == {"derived", "document"}
    assert event.after["file"] == "cse311.pdf"


def test_failure_midway_leaves_the_course_untouched(wizard, ready_job, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database fell over")
    monkeypatch.setattr(LOPOWeight.objects, "bulk_create", boom)
    with pytest.raises(RuntimeError):
        apply_syllabus_job(wizard.instructor, ready_job)
    assert not LearningOutcome.objects.exists()
    assert not Assessment.objects.exists()
    ready_job.refresh_from_db()
    assert ready_job.status == IngestionJob.Status.READY
    assert not AuditEvent.objects.filter(action="syllabus.apply").exists()


def test_second_apply_is_refused(wizard, ready_job):
    apply_syllabus_job(wizard.instructor, ready_job)
    with pytest.raises(ValidationError, match="already applied"):
        apply_syllabus_job(wizard.instructor, ready_job)
    assert LearningOutcome.objects.count() == 2


def test_existing_setup_needs_replace_flag(wizard, ready_job):
    LearningOutcomeFactory(offering=wizard.offering, number=1, description="Old LO")
    with pytest.raises(ValidationError, match="Tick"):
        apply_syllabus_job(wizard.instructor, ready_job)
    apply_syllabus_job(wizard.instructor, ready_job, replace=True)
    assert list(wizard.offering.learning_outcomes.values_list("description", flat=True)) == [
        "Explain design choices", "Apply agile practices"]
    replaced = AuditEvent.objects.get(action="setup.replace")
    assert replaced.before["los"][0]["description"] == "Old LO"


def test_replace_is_refused_when_grades_exist(wizard, ready_job):
    a = AssessmentFactory(offering=wizard.offering, name="Old quiz")
    GradeFactory(assessment=a, enrollment=EnrollmentFactory(offering=wizard.offering), score=Decimal("70"))
    with pytest.raises(ValidationError, match="already has grades"):
        apply_syllabus_job(wizard.instructor, ready_job, replace=True)
    assert Assessment.objects.get().name == "Old quiz"


def test_empty_grade_rows_do_not_block_replace(wizard, ready_job):
    a = AssessmentFactory(offering=wizard.offering, name="Old quiz")
    GradeFactory(assessment=a, enrollment=EnrollmentFactory(offering=wizard.offering), score=None)
    apply_syllabus_job(wizard.instructor, ready_job, replace=True)
    assert not Grade.objects.exists()


def test_closed_term_is_refused(wizard, ready_job):
    Term.objects.filter(pk=wizard.offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError, match="closed"):
        apply_syllabus_job(wizard.instructor, ready_job)


def test_manual_lo_added_in_review_is_stored_as_manual(wizard, draft):
    draft.los.append(type(draft.los[0])("n1", 3, "Write tests first"))
    job = IngestionJob.objects.create(
        offering=wizard.offering, kind=IngestionJob.Kind.SYLLABUS, status=IngestionJob.Status.READY,
        file=ContentFile(b"%PDF-1.4", name="x.pdf"), original_filename="x.pdf",
        created_by=wizard.instructor, result=draft.to_json())
    apply_syllabus_job(wizard.instructor, job)
    assert LearningOutcome.objects.get(number=3).source == Source.MANUAL


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.los.clear(), "no learning outcomes"),
    (lambda d: setattr(d.los[1], "number", 5), "1, 2, 3"),
    (lambda d: setattr(d.assessments[1], "name", "Midterm I"), "same name"),
    (lambda d: setattr(d.lo_po[0], "po_number", 9), "PO 9 is not in"),
    (lambda d: setattr(d.lo_po[0], "weight", 6), "1 to 5"),
    (lambda d: setattr(d.a_lo[0], "lo_key", "gone"), "removed row"),
])
def test_check_draft_catches_bad_drafts(mutate, message):
    d = make_draft()
    mutate(d)
    assert any(message in p for p in check_draft(d, {1, 2, 3}))


def test_check_draft_accepts_the_fixture():
    assert check_draft(make_draft(), {1, 2, 3}) == []


def test_discard_then_apply_is_refused(wizard, ready_job):
    discard_job(wizard.instructor, ready_job)
    ready_job.refresh_from_db()
    assert ready_job.status == IngestionJob.Status.DISCARDED
    with pytest.raises(ValidationError):
        apply_syllabus_job(wizard.instructor, ready_job)
    assert AuditEvent.objects.filter(action="syllabus.discard").count() == 1


def test_apply_view_saves_edits_then_applies(client, wizard, ready_job, draft):
    from django.urls import reverse

    from .test_review import _post_from
    client.force_login(wizard.instructor)
    post = _post_from(draft, wizard.po_set, **{"lopo__l1__2": "3"})
    resp = client.post(reverse("ingestion:apply", args=[ready_job.pk]), post)
    assert resp.status_code == 302
    assert resp.url == reverse("outcomes:mapping", args=[wizard.offering.pk])
    w = LOPOWeight.objects.get(learning_outcome__number=1, program_outcome__number=2)
    assert (w.weight, w.source, w.rationale) == (3, Source.MANUAL, "")
```

`monkeypatch.setattr(LOPOWeight.objects, "bulk_create", boom)` patches the manager instance for the length of the test. Because the error happens *after* LOs and assessments were inserted, the test proves the rollback, not just early validation.

### Check it works

1. Continue from S6-02's check on staging: on the review page, click **Apply to course**. You land on the Mapping tab with "CSE 311 is set up from cse311.pdf…". Violet cells are visible and lint shows L007 warnings.
2. Open the offering home: the setup checklist shows LOs, assessments and both weight grids ticked.
3. Open the same job URL again (`/ingestion/<id>/`): it says "Applied …" with a link to the mapping. The review URL redirects there.
4. Upload the syllabus again for the same course and try to Apply without ticking Replace: the message asks you to tick it. Tick it and Apply: the setup is replaced. In Django admin → Audit events, `setup.replace` holds the old setup.
5. Type one grade on the grade sheet, upload once more, and Apply with Replace: refused with "already has grades".
6. Upload, then **Discard** on the review page: you're back on the offering page and nothing changed.

### Done when

- [ ] T1.2 screen 4 (one transaction, replace rule): `test_apply_creates_exactly_the_reviewed_setup`, `test_existing_setup_needs_replace_flag`, `test_replace_is_refused_when_grades_exist`
- [ ] T1.2 AC2 / §7.10 rollback: `test_failure_midway_leaves_the_course_untouched`
- [ ] T1.2 AC5 (source in the database and the audit trail): `test_apply_creates_exactly_the_reviewed_setup`, `test_apply_writes_one_audit_event_with_origins`, `test_manual_lo_added_in_review_is_stored_as_manual`
- [ ] T1.2 screen 5 (discard at any point): `test_discard_then_apply_is_refused`; S6-01's `test_discard_during_processing_wins`
- [ ] Spec §5.3 closed-term rule: `test_closed_term_is_refused`
- [ ] Sprint checkpoint walkthrough done on staging

### Commits and PR

```
Apply reviewed syllabus setup in one transaction
Refuse replacing a course setup once grades exist
Add discard for syllabus uploads
Save review edits before applying from the review page
```

PR title: **S6-03 Apply and discard syllabus setups** (`Closes #<issue>`).

---
## S6-04 · "Suggest PO weights" for hand-made courses, lint L007, accept all

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S6-04-suggest-po-weights` · **Depends on:** S2-05, S2-07, S5-03

### Goal

An instructor who set up a course by hand, with no syllabus, can click **Suggest PO weights** on the Mapping tab. We send only the course's LO texts and the program's PO wording to Claude, and get back suggested LO→PO weights with a one-sentence reason each. We check them and write them into the **empty** cells as `ai_suggested`. They stay flagged by lint L007 until a human edits them or clicks **Accept all suggestions**. This delivers T1.3 and its three ACs (spec Part 6).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/suggest.py` | create | Schemas, prompt, `suggest_lo_po_weights`, `clean_suggestions`, `course_po_levels`, `SuggestionError`, `SuggestionResult`, `LOPOSuggestion` |
| `apps/outcomes/services.py` | modify | `apply_lo_po_suggestions`, `accept_suggestions` |
| `apps/outcomes/lint.py` | modify (check) | `l007_unconfirmed_ai` |
| `apps/outcomes/views.py` | modify | `suggest_lo_po`, `accept_suggestions` |
| `apps/outcomes/urls.py` | modify | two routes |
| `apps/outcomes/templates/outcomes/mapping.html` | modify | the two buttons and the AI legend |
| `apps/outcomes/tests/test_suggest.py` | create | Tests |

### Steps

**1. Why a separate, smaller call.** The syllabus extraction (S5-03) already suggests PO weights when it reads a document. Hand-made courses never went through it. This call is much smaller: about 1–2k input tokens (LO texts plus 11 PO descriptions) and a short JSON answer. At Opus prices that's roughly $0.02–0.05 per click.

It runs **inside the web request**, not in Celery. With effort `medium` and a short answer, it typically takes 5–20 s. We set the SDK timeout to 45 s, below gunicorn's 60 s worker timeout (spec §10.5 `Dockerfile`), so the request always ends with our own friendly message rather than gunicorn killing the worker. It is a deliberate trade: a Celery job with polling would add a job table or cache keys plus another polling page, for a button used a few times a term. If staging shows calls over 30 s, move it to Celery using the S6-01 pattern.

**Privacy (spec §7.8, D11):** only LO texts and PO texts are sent. No student data, no grades.

**2. Respect a course-level table when we have one.** Bologna syllabi often print "contribution of this course to program outcomes, 0–5". If this offering was ever set up from a syllabus (an `APPLIED` job exists), its draft holds those levels in `course_po_levels`, and we pass them in. Our validation then enforces them whatever the model returns: never above the level, nothing for level 0 (T1.3 AC2).

**3. What validation does with bad entries (T1.3 AC1).** Out-of-range weights are **dropped** with a warning, not clamped. That differs from §7.6 on purpose: in extraction, a clamped value is still shown to a human on the review screen before anything is saved. Here, suggestions go straight into the grid, so we don't keep a value the model got wrong. Unknown LOs and POs are dropped, and duplicates keep the first entry. Cells a human already filled are never overwritten.

```python
# apps/outcomes/suggest.py
"""T1.3: suggest LO→PO weights for a hand-made course. Sends only LO and PO texts."""
from __future__ import annotations

from dataclasses import dataclass, field

import anthropic
from django.conf import settings
from pydantic import BaseModel, ConfigDict

from apps.catalog.selectors import active_po_set

SUGGEST_PROMPT_VERSION = "suggest-v1"

_client = anthropic.Anthropic(timeout=45.0, max_retries=1)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuggestedLink(_Strict):
    lo_number: int
    po_number: int
    weight: int
    rationale: str


class SuggestionResponse(_Strict):
    links: list[SuggestedLink]
    warnings: list[str]


SYSTEM_PROMPT = """\
You help a university department map a course's learning outcomes (LOs) to the
department's program outcomes (POs) so that PO scores can be computed.

Rules:
- Use weights 1-5. 5 means the learning outcome is a central, directly assessed part of
  the program outcome; 1 means a minor but real contribution.
- Suggest only clear links, usually 1-3 per learning outcome. Leave a pair out rather than
  guess. Never invent learning outcomes or program outcomes; use only the numbers given.
- When a course-level contribution level is given for a program outcome, never exceed it,
  and give no links to program outcomes whose level is 0.
- Give a one-sentence rationale per link that names what in the LO matches the PO wording.
- Put anything ambiguous in warnings, in plain English.
"""


def build_prompt(los, pos, levels: dict[int, int]) -> str:
    lo_text = "\n".join(f"LO {lo.number}: {lo.description}" for lo in los)
    po_text = "\n".join(f"PO {po.number}: {po.description}" for po in pos)
    level_text = ("\n".join(f"PO {n}: level {lvl}" for n, lvl in sorted(levels.items()))
                  if levels else "None given.")
    return (f"<learning_outcomes>\n{lo_text}\n</learning_outcomes>\n\n"
            f"<program_outcomes>\n{po_text}\n</program_outcomes>\n\n"
            f"<course_level_contributions>\n{level_text}\n</course_level_contributions>\n\n"
            "Suggest LO to PO links following the rules.")


@dataclass(frozen=True)
class LOPOSuggestion:
    lo_id: int
    po_id: int
    weight: int
    rationale: str


@dataclass
class SuggestionResult:
    suggestions: list[LOPOSuggestion]
    warnings: list[str] = field(default_factory=list)


class SuggestionError(Exception):
    """Shown to the user as is."""


def course_po_levels(offering) -> dict[int, int]:
    """Course-level PO table from the latest applied syllabus job, if any (PO number -> 0..5)."""
    from apps.ingestion.models import IngestionJob
    job = (IngestionJob.objects
           .filter(offering=offering, kind=IngestionJob.Kind.SYLLABUS, status=IngestionJob.Status.APPLIED)
           .order_by("-applied_at").first())
    if not job or not job.result:
        return {}
    return {int(k): int(v) for k, v in (job.result.get("course_po_levels") or {}).items()}


def clean_suggestions(links, *, lo_ids: dict[int, int], po_ids: dict[int, int],
                      levels: dict[int, int], filled: set[tuple[int, int]]):
    """Pure. links: SuggestedLink-like objects. lo_ids/po_ids map numbers to database ids.
    filled: (lo_id, po_id) pairs a human already set. Returns (suggestions, warnings)."""
    out: list[LOPOSuggestion] = []
    warnings: list[str] = []
    seen: set[tuple[int, int]] = set()
    for link in links:
        where = f"LO {link.lo_number} → PO {link.po_number}"
        if link.lo_number not in lo_ids:
            warnings.append(f"Ignored a suggestion for LO {link.lo_number}, which doesn't exist.")
            continue
        if link.po_number not in po_ids:
            warnings.append(f"Ignored {where}: PO {link.po_number} is not in the active list.")
            continue
        if not 1 <= link.weight <= 5:
            warnings.append(f"Ignored {where}: weight {link.weight} is outside 1–5.")
            continue
        weight = link.weight
        level = levels.get(link.po_number)
        if level is not None:
            if level == 0:
                warnings.append(f"Ignored {where}: the syllabus says this course doesn't contribute to "
                                f"PO {link.po_number}.")
                continue
            if weight > level:
                warnings.append(f"Lowered {where} from {weight} to {level}, the course-level contribution.")
                weight = level
        pair = (lo_ids[link.lo_number], po_ids[link.po_number])
        if pair in seen:
            continue
        seen.add(pair)
        if pair in filled:
            continue                                 # never overwrite a human's cell
        out.append(LOPOSuggestion(lo_id=pair[0], po_id=pair[1], weight=weight,
                                  rationale=link.rationale.strip()))
    return out, warnings


def suggest_lo_po_weights(offering) -> SuggestionResult:
    from .models import LOPOWeight

    los = list(offering.learning_outcomes.order_by("number"))
    if not los:
        raise SuggestionError("Add learning outcomes first. Suggestions are based on their text.")
    pos = list(active_po_set(offering.course.program).outcomes.order_by("number"))
    levels = course_po_levels(offering)

    try:
        response = _client.beta.messages.parse(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=6000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(los, pos, levels)}],
            output_format=SuggestionResponse,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
    except anthropic.APIError as e:
        raise SuggestionError("The AI service didn't answer in time. Try again in a minute, "
                              "or fill the grid by hand.") from e
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise SuggestionError("No suggestions could be made for this course. Fill the grid by hand.")

    filled = set(LOPOWeight.objects.filter(learning_outcome__offering=offering)
                 .values_list("learning_outcome_id", "program_outcome_id"))
    suggestions, warnings = clean_suggestions(
        response.parsed_output.links,
        lo_ids={lo.number: lo.pk for lo in los}, po_ids={po.number: po.pk for po in pos},
        levels=levels, filled=filled)
    return SuggestionResult(suggestions, list(response.parsed_output.warnings) + warnings)
```

The `parse(...)` call uses the same parameters that S5-03's spike confirmed for `extract_syllabus`. If that spike had to drop `output_config`, drop it here too.

**4. Services.** `apply_lo_po_suggestions` writes into empty cells only. It re-checks emptiness *inside* the transaction, because a human may have typed into a cell during the 10–20 s the call took. `accept_suggestions` turns every AI cell of the offering into `manual`: that's T1.3 AC3, and it clears L007. Each writes one audit event with the whole list, matching the matrix-save convention (spec §5.4).

`transaction`, `ValidationError`, `audit`, `ensure_term_open`, `LOPOWeight` and `Source` are already imported at the top of `outcomes/services.py` (S2-04, S2-05). Only add the imports that are new.

```python
# apps/outcomes/services.py  (add)
from apps.catalog.models import CourseOffering


def apply_lo_po_suggestions(user, offering, suggestions) -> int:
    """Write AI suggestions into empty LO→PO cells. Returns how many were written."""
    with transaction.atomic():
        offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
        ensure_term_open(offering)
        lo_ids = set(offering.learning_outcomes.values_list("pk", flat=True))
        filled = set(LOPOWeight.objects.filter(learning_outcome__offering=offering)
                     .values_list("learning_outcome_id", "program_outcome_id"))
        rows = [LOPOWeight(learning_outcome_id=s.lo_id, program_outcome_id=s.po_id, weight=s.weight,
                           source=Source.AI_SUGGESTED, rationale=s.rationale)
                for s in suggestions
                if s.lo_id in lo_ids and (s.lo_id, s.po_id) not in filled]
        LOPOWeight.objects.bulk_create(rows)
        if rows:
            audit.record(user, "lo_po.suggest", offering, offering=offering, after={
                "written": [{"lo_id": r.learning_outcome_id, "po_id": r.program_outcome_id,
                             "weight": r.weight, "rationale": r.rationale} for r in rows]})
    return len(rows)


def accept_suggestions(user, offering) -> int:
    """'Accept all suggestions' (T1.3): AI-suggested cells become human-confirmed."""
    with transaction.atomic():
        offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
        ensure_term_open(offering)
        qs = LOPOWeight.objects.filter(learning_outcome__offering=offering, source=Source.AI_SUGGESTED)
        before = [{"lo_id": w.learning_outcome_id, "po_id": w.program_outcome_id, "weight": w.weight}
                  for w in qs]
        count = qs.update(source=Source.MANUAL)
        if count:
            audit.record(user, "lo_po.accept", offering, offering=offering, before={"accepted": before})
    return count
```

The rationale stays on accepted cells. It's still a useful explanation, and the audit trail records that a human accepted it.

**5. Lint L007.** S2-07 wrote all seven rules. Check that L007 reads `source` from the snapshot. If S2-07 left it as a stub, this is the full rule, assuming `MappingSnapshot.lo_po` is a list of link records with `lo_number`, `po_number` and `source` (adapt the attribute names to the merged snapshot):

```python
# apps/outcomes/lint.py
def l007_unconfirmed_ai(snap) -> list[LintIssue]:
    """AI-suggested LO→PO weights that no human has edited or accepted (T1.3)."""
    pending = [link for link in snap.lo_po if link.source == "ai_suggested"]
    if not pending:
        return []
    pairs = ", ".join(f"LO {link.lo_number}→PO {link.po_number}" for link in pending[:5])
    more = f" and {len(pending) - 5} more" if len(pending) > 5 else ""
    return [LintIssue(code="L007", severity="warning",
                      message=f"{len(pending)} AI-suggested weight(s) not yet confirmed: {pairs}{more}. "
                              "Edit them or click “Accept all suggestions”.",
                      target="lo_po")]
```

One issue per offering, not one per cell: eleven identical warnings would bury the real errors (L001, L002) above them.

**6. Views, URLs and buttons.** Both are plain POST forms that redirect back to the Mapping tab with a message. No HTMX: a full reload is the simplest way to show the new grid, lint and footer totals together. The Suggest button disables itself on submit and shows "Thinking… (up to 40 s)", so nobody clicks it three times.

`login_required`, `redirect`, `ValidationError` and `require_offering_access` are already imported in `outcomes/views.py`.

```python
# apps/outcomes/views.py  (add)
from django.contrib import messages
from django.views.decorators.http import require_POST

from . import services
from .suggest import SuggestionError, suggest_lo_po_weights


@login_required
@require_offering_access(edit=True)
@require_POST
def suggest_lo_po(request, offering_id, offering, perms_for):
    try:
        result = suggest_lo_po_weights(offering)
        written = services.apply_lo_po_suggestions(request.user, offering, result.suggestions)
    except (SuggestionError, ValidationError) as e:
        messages.error(request, " ".join(getattr(e, "messages", [str(e)])))
        return redirect("outcomes:mapping", offering_id=offering.pk)
    if written:
        messages.success(request, f"{written} suggested weight(s) added in violet. Hover a cell for the reason; "
                                  "edit any you disagree with, then accept the rest.")
    else:
        messages.info(request, "No new suggestions: every clear link is already filled in.")
    for w in result.warnings:
        messages.warning(request, w)
    return redirect("outcomes:mapping", offering_id=offering.pk)


@login_required
@require_offering_access(edit=True)
@require_POST
def accept_suggestions(request, offering_id, offering, perms_for):
    try:
        count = services.accept_suggestions(request.user, offering)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"Accepted {count} suggestion(s).")
    return redirect("outcomes:mapping", offering_id=offering.pk)
```

`SuggestionError` is a plain exception with no `.messages`, which is why the view uses the `getattr` fallback.

```python
# apps/outcomes/urls.py  (add)
path("offerings/<int:offering_id>/mapping/lo-po/suggest/", views.suggest_lo_po, name="suggest_lo_po"),
path("offerings/<int:offering_id>/mapping/lo-po/accept/", views.accept_suggestions, name="accept_suggestions"),
```

Add to `mapping.html`, above the LO→PO grid (`ai_count` comes from the view: the number of AI-suggested cells, which `mapping_grid` can return or the view can count):

```django
{% if perms_for.can_edit %}
<div class="d-flex flex-wrap gap-2 align-items-center mb-2">
  <form method="post" action="{% url 'outcomes:suggest_lo_po' offering.pk %}"
        onsubmit="const b=this.querySelector('button'); b.disabled=true; b.textContent='Thinking… (up to 40 s)';">
    {% csrf_token %}
    <button type="submit" class="btn btn-outline-primary btn-sm">Suggest PO weights</button>
  </form>
  {% if ai_count %}
  <form method="post" action="{% url 'outcomes:accept_suggestions' offering.pk %}">
    {% csrf_token %}
    <button type="submit" class="btn btn-outline-secondary btn-sm">Accept all {{ ai_count }} suggestion{{ ai_count|pluralize }}</button>
  </form>
  <span class="small"><span class="pl-legend__swatch" style="background:var(--pl-origin-ai)"></span>AI: suggested, not yet confirmed (hover for the reason)</span>
  {% endif %}
</div>
{% endif %}
```

Make sure S2-05's `mapping_grid` passes `origin="ai_suggested"` and `rationale` into each `GridCell` of the LO→PO grid. That's two lines in the selector, and the include from S6-02 does the rest.

Add both URLs to the permission matrix: POST, allowed roles get 302 (instructor of this offering, head), others 404. In the matrix test, monkeypatch `apps.outcomes.views.suggest_lo_po_weights` to return an empty `SuggestionResult`, so the matrix never calls the API.

### Tests

```python
# apps/outcomes/tests/test_suggest.py
"""No network: the Claude client is replaced with a fake in every test."""
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    LearningOutcomeFactory, LOPOWeightFactory, MembershipFactory, OfferingFactory,
    ProgramOutcomeFactory, ProgramOutcomeSetFactory, UserFactory,
)
from apps.outcomes import services, suggest
from apps.outcomes.lint import run_lint
from apps.outcomes.models import LOPOWeight, Source
from apps.outcomes.selectors import snapshot_mapping
from apps.outcomes.suggest import SuggestedLink, SuggestionError, clean_suggestions


@pytest.fixture
def course(db):
    offering = OfferingFactory()
    po_set = ProgramOutcomeSetFactory(program=offering.course.program, is_active=True)
    pos = {n: ProgramOutcomeFactory(po_set=po_set, number=n) for n in (1, 2, 3)}
    los = {n: LearningOutcomeFactory(offering=offering, number=n, description=f"LO text {n}") for n in (1, 2)}
    teacher = UserFactory()
    MembershipFactory(user=teacher, program=offering.course.program, role=ProgramMembership.Role.INSTRUCTOR)
    offering.instructors.add(teacher)
    return SimpleNamespace(offering=offering, pos=pos, los=los, teacher=teacher)


class FakeClient:
    """Stands in for anthropic.Anthropic. Records the request, returns a canned parse result."""
    def __init__(self, links=(), warnings=(), stop_reason="end_turn", error=None):
        self.calls = []
        parsed = suggest.SuggestionResponse(links=list(links), warnings=list(warnings))

        def parse(**kwargs):
            self.calls.append(kwargs)
            if error:
                raise error
            return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))


def link(lo, po, w, why="Because."):
    return SuggestedLink(lo_number=lo, po_number=po, weight=w, rationale=why)


# ---------- clean_suggestions (pure) ----------

IDS = dict(lo_ids={1: 101, 2: 102}, po_ids={1: 201, 2: 202, 3: 203})


def test_clean_keeps_valid_links():
    out, warns = clean_suggestions([link(1, 1, 4)], levels={}, filled=set(), **IDS)
    assert [(s.lo_id, s.po_id, s.weight) for s in out] == [(101, 201, 4)] and warns == []


@pytest.mark.parametrize("bad, text", [
    (link(9, 1, 3), "LO 9"), (link(1, 11, 3), "PO 11 is not in"),
    (link(1, 1, 0), "outside 1–5"), (link(1, 1, 6), "outside 1–5"),
])
def test_clean_drops_invalid_links_with_a_warning(bad, text):           # T1.3 AC1
    out, warns = clean_suggestions([bad], levels={}, filled=set(), **IDS)
    assert out == [] and text in warns[0]


def test_clean_respects_course_level_table():                           # T1.3 AC2
    out, warns = clean_suggestions([link(1, 1, 5), link(1, 2, 2), link(2, 3, 4)],
                                   levels={1: 3, 2: 0, 3: 5}, filled=set(), **IDS)
    assert [(s.po_id, s.weight) for s in out] == [(201, 3), (203, 4)]
    assert any("Lowered" in w for w in warns) and any("doesn't contribute" in w for w in warns)


def test_clean_never_overwrites_a_filled_cell_and_skips_duplicates():
    out, _ = clean_suggestions([link(1, 1, 4), link(1, 1, 2), link(2, 2, 3)],
                               levels={}, filled={(102, 202)}, **IDS)
    assert [(s.lo_id, s.po_id, s.weight) for s in out] == [(101, 201, 4)]


# ---------- suggest_lo_po_weights with a fake client ----------

def test_prompt_contains_only_lo_and_po_texts(course, monkeypatch):
    fake = FakeClient(links=[link(1, 1, 4)])
    monkeypatch.setattr(suggest, "_client", fake)
    suggest.suggest_lo_po_weights(course.offering)
    content = fake.calls[0]["messages"][0]["content"]
    assert "LO 1: LO text 1" in content and "PO 3:" in content
    assert "student" not in content.lower()
    assert fake.calls[0]["output_format"] is suggest.SuggestionResponse


def test_api_error_becomes_friendly_message(course, monkeypatch):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    monkeypatch.setattr(suggest, "_client", FakeClient(error=anthropic.APITimeoutError(request=req)))
    with pytest.raises(SuggestionError, match="didn't answer"):
        suggest.suggest_lo_po_weights(course.offering)


def test_refusal_becomes_friendly_message(course, monkeypatch):
    monkeypatch.setattr(suggest, "_client", FakeClient(stop_reason="refusal"))
    with pytest.raises(SuggestionError):
        suggest.suggest_lo_po_weights(course.offering)


def test_no_los_means_no_call(db, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(suggest, "_client", fake)
    offering = OfferingFactory()
    ProgramOutcomeSetFactory(program=offering.course.program, is_active=True)
    with pytest.raises(SuggestionError, match="Add learning outcomes first"):
        suggest.suggest_lo_po_weights(offering)
    assert fake.calls == []


# ---------- services, lint and views ----------

def test_suggestions_fill_empty_cells_as_ai_and_trigger_l007(course, monkeypatch):
    LOPOWeightFactory(learning_outcome=course.los[2], program_outcome=course.pos[2], weight=5,
                      source=Source.MANUAL)
    monkeypatch.setattr(suggest, "_client", FakeClient(links=[link(1, 1, 4, "Matches."), link(2, 2, 1)]))
    result = suggest.suggest_lo_po_weights(course.offering)
    assert services.apply_lo_po_suggestions(course.teacher, course.offering, result.suggestions) == 1
    w = LOPOWeight.objects.get(learning_outcome=course.los[1])
    assert (w.weight, w.source, w.rationale) == (4, Source.AI_SUGGESTED, "Matches.")
    assert LOPOWeight.objects.get(learning_outcome=course.los[2]).weight == 5     # human cell kept
    assert "L007" in {i.code for i in run_lint(snapshot_mapping(course.offering))}
    assert AuditEvent.objects.filter(action="lo_po.suggest").count() == 1


def test_accept_all_clears_l007(course):                                # T1.3 AC3
    LOPOWeightFactory(learning_outcome=course.los[1], program_outcome=course.pos[1], weight=3,
                      source=Source.AI_SUGGESTED, rationale="r")
    assert services.accept_suggestions(course.teacher, course.offering) == 1
    assert LOPOWeight.objects.get().source == Source.MANUAL
    assert "L007" not in {i.code for i in run_lint(snapshot_mapping(course.offering))}


def test_editing_an_ai_cell_in_the_grid_clears_l007(course):
    from apps.outcomes.matrix import Cell, matrix_version
    LOPOWeightFactory(learning_outcome=course.los[1], program_outcome=course.pos[1], weight=3,
                      source=Source.AI_SUGGESTED, rationale="r")
    services.save_lo_po_matrix(course.teacher, course.offering,
                               [Cell(course.los[1].pk, course.pos[1].pk, "4")],
                               expected_version=matrix_version(course.offering, "lo_po"))
    assert LOPOWeight.objects.get().source == Source.MANUAL


def test_closed_term_refuses_suggestions(course):
    from apps.catalog.models import Term
    Term.objects.filter(pk=course.offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.apply_lo_po_suggestions(course.teacher, course.offering, [])


def test_suggest_view_round_trip(client, course, monkeypatch):
    monkeypatch.setattr(suggest, "_client", FakeClient(links=[link(1, 1, 4)], warnings=["LO 2 is vague."]))
    client.force_login(course.teacher)
    resp = client.post(reverse("outcomes:suggest_lo_po", args=[course.offering.pk]), follow=True)
    html = resp.content.decode()
    assert "1 suggested weight(s) added" in html and "LO 2 is vague." in html
    assert LOPOWeight.objects.filter(source=Source.AI_SUGGESTED).count() == 1


def test_suggest_view_is_404_for_other_instructors(client, course, monkeypatch):
    monkeypatch.setattr(suggest, "_client", FakeClient())
    client.force_login(UserFactory())
    assert client.post(reverse("outcomes:suggest_lo_po", args=[course.offering.pk])).status_code == 404
```

`test_editing_an_ai_cell_in_the_grid_clears_l007` checks S2-05's promise that a human edit sets `source=manual`. If it fails, the fix belongs in `save_lo_po_matrix`: a cell whose value changed gets `source=Source.MANUAL` and `rationale=""`.

### Check it works

1. On staging, open a seeded hand-made offering with LOs but an empty LO→PO grid. Click **Suggest PO weights**. The button reads "Thinking…", and 5–20 s later the grid has violet cells. Hover one to see the reason.
2. Lint shows one L007 warning naming the pairs.
3. Change one violet cell to another number and save the grid: it turns plain, and the L007 count drops by one.
4. Click **Accept all N suggestions**: all violet is gone and the L007 warning is gone.
5. Click **Suggest** again: "No new suggestions: every clear link is already filled in."
6. Django admin → Audit events: `lo_po.suggest` and `lo_po.accept` are there with the lists.
7. In the job log (or the Anthropic Console), check the cost of one suggest call: it should be a few cents.

### Done when

- [ ] T1.3 AC1 (only 1–5, only active POs; invalid dropped with a warning): `test_clean_drops_invalid_links_with_a_warning`, `test_suggest_view_round_trip`
- [ ] T1.3 AC2 (course-level table respected): `test_clean_respects_course_level_table`
- [ ] T1.3 AC3 (accept → manual, L007 clears): `test_accept_all_clears_l007`, `test_editing_an_ai_cell_in_the_grid_clears_l007`
- [ ] Human cells never overwritten: `test_clean_never_overwrites_a_filled_cell_and_skips_duplicates`, `test_suggestions_fill_empty_cells_as_ai_and_trigger_l007`
- [ ] Only LO and PO text is sent (D11): `test_prompt_contains_only_lo_and_po_texts`
- [ ] Permission matrix updated

### Commits and PR

```
Suggest LO to PO weights from outcome texts with Claude
Validate suggestions against course-level contribution levels
Write suggestions into empty cells and add accept-all
Add suggest and accept buttons to the mapping tab
```

PR title: **S6-04 Suggested PO weights for hand-made courses** (`Closes #<issue>`).

---
## S6-05 · Attainment aggregate + department attainment table and chart (T1.6 part 1)

**Points:** 5 · **Owner:** Person C · **Branch:** `feature/S6-05-attainment` · **Depends on:** S1-06, S1-07, S3-04

### Goal

The head sees, for every PO, **what share of students attain it** (score ≥ the program's threshold, P11), split either by **cohort** (2023, 2024, 2025…) or by **term**. Cells are coloured against a target (default: 70% of students attaining), and clicking a cell lists the students behind it. This is the first half of T1.6 and AC1 ("10 students, 6 above threshold → 60%"). The coverage heat map (S7-01) and the full filter bar and completion panel (S7-02) come next sprint. This story reuses the term selection and "include open terms" toggle that S3-04 built for B10.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/scoring/aggregates.py` | modify | `AttainmentCell`, `AttainmentColumn`, `AttainmentRow`, `AttainmentMatrix`, `attainment_matrix`, `attainment_students`, `student_po_scores` |
| `apps/reports/forms.py` | create or modify | `AttainmentOptionsForm` |
| `apps/reports/views.py` | modify | attainment section in `department`; new `attainment_students` |
| `apps/reports/urls.py` | modify | `attainment_students` route |
| `apps/reports/templates/reports/department.html` | modify | attainment card, chart, modal |
| `apps/reports/templates/reports/attainment_students.html` | create | Drill-down partial |
| `static/js/polaris.js` | modify | `renderAttainmentChart` |
| `apps/scoring/tests/test_attainment.py`, `apps/reports/tests/test_attainment_views.py` | create | Tests |

### Steps

**1. The method, in plain language.** Spec §2.4 says class- and department-level numbers are built from **per-student results**, never from pooled grades. So:

1. For each student, compute their PO scores with the engine, exactly as their own profile does.
2. For each PO and each column, count the students who **have** a score for that PO ("scored"), and those whose score is ≥ the threshold ("attaining").
3. Attainment rate = attaining ÷ scored (P11). A student with no evidence for a PO is left out of both counts, never counted as failing (P12). If nobody has a score, the cell shows "—", not 0%.

What a **column** means:

| `by` | Column | Which offerings feed a student's score | Why |
|---|---|---|---|
| `cohort` | Students admitted in that year | All selected terms, **latest attempt per course** (P9) | "How well does the 2023 cohort meet PO 7 so far?", the accreditation question |
| `term` | One term | Only that term's offerings | "Did things change after we reworked CSE 321 in Spring?" Each term stands alone, so a weak term isn't hidden by older good ones |

The **threshold** is `Program.attainment_threshold` (default 60). The **target** (default 70%) is not stored: it's a display setting in the URL (`?target=75`), because only the colouring depends on it, not the numbers. If the head wants it saved, that's a one-field change to `Program` later.

**2. Loading data without hundreds of queries.** Calling `load_student_inputs` once per student would cost a few queries × 120 students on every dashboard load. Instead we call `load_offering_inputs(offering)` once per offering in the selected terms. That's about 12 offerings per term, and it returns inputs for the whole class in one pass. We then regroup by student. Both loaders apply P4 (published only) and use the same edge-building code, so the numbers are identical. A test proves it by comparing against `load_student_inputs` for every seeded student.

**P13 (PO set per cohort) in memory.** Each student is measured against the newest PO set with `effective_from_year ≤ cohort_year`. The table's rows are the **active** set's POs, so a student on an older set adds nothing to those rows. With one PO set (our seed data) nothing changes. If no set is old enough for a cohort (a student admitted before the first recorded set), we use the oldest set rather than dropping the student. That fallback isn't in the spec yet; it's listed under "Spec contradictions" at the end of this chapter.

```python
# apps/scoring/aggregates.py  (add; keep `from __future__ import annotations` as the file's first line)
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from apps.accounts.models import ProgramMembership
from apps.catalog.models import CourseOffering, Enrollment
from apps.catalog.selectors import active_po_set

from .engine import compute_student_profile
from .loaders import load_offering_inputs

BY_COHORT = "cohort"
BY_TERM = "term"


@dataclass(frozen=True)
class AttainmentCell:
    scored: int                    # students with a score for this PO in this column
    attaining: int                 # of those, score >= threshold
    key: str = ""                  # the column's key, so the template can build drill-down links
    label: str = ""                # the column's label, for screen-reader text

    @property
    def rate(self) -> Decimal | None:
        """0..1, or None when nobody has evidence (P12)."""
        return None if self.scored == 0 else Decimal(self.attaining) / Decimal(self.scored)


@dataclass(frozen=True)
class AttainmentColumn:
    key: str                       # "2023" or a term code like "2026F"
    label: str


@dataclass(frozen=True)
class AttainmentRow:
    po: object                     # catalog.ProgramOutcome
    cells: tuple[AttainmentCell, ...]


@dataclass(frozen=True)
class AttainmentMatrix:
    by: str
    threshold: Decimal
    columns: tuple[AttainmentColumn, ...]
    rows: tuple[AttainmentRow, ...]

    def chart_data(self, target: Decimal) -> dict:
        """Plain dict for json_script → Chart.js. Rates as percentages with 1 decimal.
        float only here, at the JSON boundary: the chart is not a place where scores are computed."""
        return {
            "labels": [f"PO {r.po.number}" for r in self.rows],
            "datasets": [{
                "label": col.label,
                "data": [None if r.cells[i].rate is None
                         else float((r.cells[i].rate * 100).quantize(Decimal("0.1")))
                         for r in self.rows],
            } for i, col in enumerate(self.columns)],
            "target": float(target),
        }


def _po_set_ids_by_cohort(program) -> callable:
    """P13 in memory: cohort_year -> set of PO ids the student is measured on."""
    sets = list(program.po_sets.prefetch_related("outcomes").order_by("-effective_from_year"))
    ids = {s.pk: {po.pk for po in s.outcomes.all()} for s in sets}

    def for_cohort(cohort_year: int) -> set[int]:
        for s in sets:
            if s.effective_from_year <= cohort_year:
                return ids[s.pk]
        return ids[sets[-1].pk] if sets else set()     # admitted before the first recorded set
    return for_cohort


def student_po_scores(program, *, by: str, terms, cohort: int | None = None
                      ) -> tuple[list[AttainmentColumn], dict[str, dict[int, dict[int, Decimal]]]]:
    """Per column, per student, the PO scores that count (P4, P9, P13 applied).
    Returns (columns, {column_key: {student_id: {po_id: score}}})."""
    if by not in (BY_COHORT, BY_TERM):
        raise ValueError(f"by must be {BY_COHORT!r} or {BY_TERM!r}")
    terms = sorted(terms, key=lambda t: t.starts_on)
    cohorts = dict(ProgramMembership.objects
                   .filter(program=program, role=ProgramMembership.Role.STUDENT)
                   .values_list("user_id", "cohort_year"))
    if cohort is not None:
        cohorts = {uid: c for uid, c in cohorts.items() if c == cohort}
    allowed_pos = _po_set_ids_by_cohort(program)

    offerings = list(CourseOffering.objects.filter(course__program=program, term__in=terms)
                     .select_related("term", "course"))
    student_of = dict(Enrollment.objects
                      .filter(offering__in=offerings, status=Enrollment.Status.ENROLLED)
                      .values_list("id", "student_id"))

    # (student_id, column_key) -> {course_id: (term.starts_on, offering_id, inputs)}
    grouped: dict[tuple[int, str], dict[int, tuple]] = defaultdict(dict)
    for off in offerings:
        for enrollment_id, inputs in load_offering_inputs(off).items():
            sid = student_of.get(enrollment_id)
            if sid not in cohorts:
                continue
            key = str(cohorts[sid]) if by == BY_COHORT else off.term.code
            attempt = (off.term.starts_on, off.pk, inputs)
            current = grouped[(sid, key)].get(off.course_id)
            if current is None or attempt[:2] > current[:2]:      # P9: latest attempt wins
                grouped[(sid, key)][off.course_id] = attempt

    scores: dict[str, dict[int, dict[int, Decimal]]] = defaultdict(dict)
    for (sid, key), by_course in grouped.items():
        profile = compute_student_profile(a[2] for a in by_course.values())
        allowed = allowed_pos(cohorts[sid])
        scores[key][sid] = {po_id: ns.score for po_id, ns in profile.po_scores.items()
                            if ns.score is not None and po_id in allowed}

    if by == BY_COHORT:
        columns = [AttainmentColumn(str(c), str(c)) for c in sorted(set(cohorts.values()))]
    else:
        columns = [AttainmentColumn(t.code, t.name) for t in terms]
    return columns, scores


def attainment_matrix(program, *, by: str, terms, threshold: Decimal | None = None,
                      cohort: int | None = None) -> AttainmentMatrix:
    threshold = program.attainment_threshold if threshold is None else threshold
    columns, scores = student_po_scores(program, by=by, terms=terms, cohort=cohort)
    pos = list(active_po_set(program).outcomes.order_by("number"))
    rows = []
    for po in pos:
        cells = []
        for col in columns:
            values = [s[po.pk] for s in scores.get(col.key, {}).values() if po.pk in s]
            cells.append(AttainmentCell(scored=len(values),
                                        attaining=sum(1 for v in values if v >= threshold),
                                        key=col.key, label=col.label))
        rows.append(AttainmentRow(po=po, cells=tuple(cells)))
    return AttainmentMatrix(by=by, threshold=threshold, columns=tuple(columns), rows=tuple(rows))


@dataclass(frozen=True)
class StudentPOScore:
    student_id: int
    score: Decimal
    attains: bool


def attainment_students(program, *, po, by: str, key: str, terms,
                        threshold: Decimal | None = None) -> list[StudentPOScore]:
    """The students behind one cell, lowest score first (the head's to-do list)."""
    threshold = program.attainment_threshold if threshold is None else threshold
    _, scores = student_po_scores(program, by=by, terms=terms)
    rows = [StudentPOScore(sid, s[po.pk], s[po.pk] >= threshold)
            for sid, s in scores.get(key, {}).items() if po.pk in s]
    return sorted(rows, key=lambda r: (r.score, r.student_id))
```

Why `attempt[:2] > current[:2]`: tuples compare item by item, so this means "later term start, or the same term and a higher offering id". Two offerings of the same course in one term (sections) are rare. The id tiebreak just keeps the result deterministic.

`attainment_matrix` loops POs × columns × students in Python. At our scale (11 POs × 3 columns × 120 students) that's about 4,000 cheap operations: negligible next to the queries. The `mv_po_attainment` materialized view (T2.3) replaces this if the dashboard ever gets slow (T1.6 AC3: under 1.5 s).

**3. The options form.** Only the two settings this story owns. S7-02 later folds them into the full filter bar.

```python
# apps/reports/forms.py
from decimal import Decimal

from django import forms

from apps.scoring.aggregates import BY_COHORT, BY_TERM


class AttainmentOptionsForm(forms.Form):
    by = forms.ChoiceField(choices=[(BY_COHORT, "By cohort"), (BY_TERM, "By term")],
                           initial=BY_COHORT, required=False)
    target = forms.IntegerField(label="Target % attaining", min_value=1, max_value=100,
                                initial=70, required=False)

    def values(self) -> tuple[str, Decimal]:
        """Valid values or defaults. A bad query string never breaks the dashboard."""
        data = self.cleaned_data if self.is_valid() else {}
        return data.get("by") or BY_COHORT, Decimal(data.get("target") or 70)
```

**4. The department view.** S3-04's `department` view already resolves the head's `program`, the selected `terms` and `include_open_terms`, and renders `reports/department.html`. Add the attainment context next to what it already passes. The new lines are marked.

```python
# apps/reports/views.py — at the top of the file:
#     from apps.scoring.aggregates import attainment_matrix
#     from .forms import AttainmentOptionsForm
# then inside department(), after terms are resolved and `context` is built:
    options = AttainmentOptionsForm(request.GET or None)                     # NEW
    by, target = options.values()                                            # NEW
    matrix = attainment_matrix(program, by=by, terms=terms)                  # NEW
    context |= {                                                             # NEW
        "attainment": matrix,
        "attainment_options": options,
        "attainment_target": target,
        "attainment_target_rate": target / 100,
        "attainment_chart": matrix.chart_data(target),
    }
```

The drill-down view returns the partial that fills a Bootstrap modal (the "Modal content" HTMX pattern, spec §8.5). It must rebuild the same term selection as the dashboard, so it reuses S3-04's helper. S3-04 defines `_selected_terms(request, program)` in `apps/reports/views.py`; it returns `(terms, include_open, form)`.

```python
# apps/reports/views.py  (add)
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.accounts.permissions import head_program_or_404
from apps.catalog.models import ProgramOutcome
from apps.scoring.aggregates import attainment_students as attainment_students_for


@login_required
@require_role("head")
@require_GET
def attainment_students(request, po_id):
    program = head_program_or_404(request.user)               # S2-02
    po = get_object_or_404(ProgramOutcome, pk=po_id, po_set__program=program)
    terms, _include_open, _form = _selected_terms(request, program)  # S3-04 helper
    options = AttainmentOptionsForm(request.GET or None)
    by, _target = options.values()
    key = request.GET.get("key", "")
    if not key:
        raise Http404
    rows = attainment_students_for(program, po=po, by=by, key=key, terms=terms)
    users = User.objects.in_bulk([r.student_id for r in rows])
    return render(request, "reports/attainment_students.html", {
        "po": po, "key": key, "by": by, "threshold": program.attainment_threshold,
        "rows": [(users[r.student_id], r) for r in rows],
    })
```

```python
# apps/reports/urls.py  (add)
path("department/attainment/<int:po_id>/", views.attainment_students, name="attainment_students"),
```

`po_set__program=program` means a head of another program gets a 404 for this PO, which T2.6 will need anyway.

**5. Templates.** Each cell shows the rate, an icon and the count. The icon means the meaning isn't carried by colour alone: ✓ meets the target, ▼ below, — no evidence. Each cell is a button that loads the student list into the modal.

```django
{# apps/reports/templates/reports/department.html — add this card where the B10 PO table was #}
{# uses |weight, |pct and {% query_transform %}: department.html must start with {% load polaris %} (S3-04 already does) #}
<section class="card mb-4" aria-labelledby="attain-h">
  <div class="card-body">
    <div class="d-flex flex-wrap justify-content-between align-items-end gap-2 mb-3">
      <div>
        <h2 id="attain-h" class="h5 mb-0">PO attainment</h2>
        <p class="small text-body-secondary mb-0">Share of students with a score ≥ {{ attainment.threshold|weight }}
          · target {{ attainment_target|weight }}% · {{ include_open_terms|yesno:"includes open terms,closed terms only" }}</p>
      </div>
      <form method="get" class="d-flex gap-2 align-items-end">
        {% for name, value in request.GET.items %}{% if name != "by" and name != "target" %}
          <input type="hidden" name="{{ name }}" value="{{ value }}">{% endif %}{% endfor %}
        <div><label class="form-label small mb-0" for="att-by">Columns</label>
          <select id="att-by" name="by" class="form-select form-select-sm">
            <option value="cohort" {% if attainment.by == "cohort" %}selected{% endif %}>By cohort</option>
            <option value="term" {% if attainment.by == "term" %}selected{% endif %}>By term</option>
          </select></div>
        <div><label class="form-label small mb-0" for="att-target">Target %</label>
          <input id="att-target" name="target" type="number" min="1" max="100" value="{{ attainment_target|weight }}"
                 class="form-control form-control-sm" style="width:5.5rem"></div>
        <button class="btn btn-sm btn-outline-primary">Update</button>
      </form>
    </div>

    {% if not attainment.columns %}
      {% include "includes/empty_state.html" with title="No students to show yet" message="Attainment appears once students are enrolled and grades are published in the selected terms." only %}
    {% else %}
    <div class="table-responsive">
      <table class="table table-sm align-middle pl-attain">
        <thead><tr><th scope="col">Program outcome</th>
          {% for col in attainment.columns %}<th scope="col" class="text-center">{{ col.label }}</th>{% endfor %}</tr></thead>
        <tbody>
        {% for row in attainment.rows %}
          <tr>
            <th scope="row" title="{{ row.po.description }}">PO {{ row.po.number }} <span class="fw-normal">{{ row.po.short_name }}</span></th>
            {% for cell in row.cells %}
            <td class="text-center pl-num">
              {% if cell.rate is None %}
                <span class="text-body-secondary" title="No student has evidence for this outcome">—</span>
              {% else %}
                <button type="button" class="btn btn-sm pl-attain__cell {% if cell.rate >= attainment_target_rate %}is-met{% else %}is-below{% endif %}"
                        data-bs-toggle="modal" data-bs-target="#attain-modal"
                        hx-get="{% url 'reports:attainment_students' row.po.pk %}?{% query_transform key=cell.key %}"
                        hx-target="#attain-modal-body"
                        aria-label="PO {{ row.po.number }}, {{ cell.label }}: {{ cell.rate|pct }} attaining, {{ cell.attaining }} of {{ cell.scored }} students">
                  {{ cell.rate|pct }} {% if cell.rate >= attainment_target_rate %}✓{% else %}▼{% endif %}
                  <span class="d-block small text-body-secondary">{{ cell.attaining }}/{{ cell.scored }}</span>
                </button>
              {% endif %}
            </td>
            {% endfor %}
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    <canvas id="attain-chart" height="120" aria-label="Bar chart of attainment rate per PO and column" role="img"></canvas>
    {{ attainment_chart|json_script:"attain-chart-data" }}
    {% endif %}
  </div>
</section>

<div class="modal fade" id="attain-modal" tabindex="-1" aria-labelledby="attain-modal-title" aria-hidden="true">
  <div class="modal-dialog modal-dialog-scrollable"><div class="modal-content">
    <div class="modal-header"><h2 class="modal-title h5" id="attain-modal-title">Students</h2>
      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
    <div class="modal-body" id="attain-modal-body"><div class="spinner-border" aria-hidden="true"></div></div>
  </div></div>
</div>
```

Each cell carries its column's `key` and `label` (step 2), because Django templates can't look up "the column at the same index" without a custom tag.

`query_transform` (core template tag, spec §4.8) keeps the dashboard's term and toggle parameters in the drill-down URL and adds `key`. Students therefore see the same term selection the head is looking at.

```django
{# apps/reports/templates/reports/attainment_students.html #}
{% load polaris %}
<p class="small text-body-secondary">PO {{ po.number }} {{ po.short_name }} ·
  {% if by == "cohort" %}cohort {{ key }}{% else %}term {{ key }}{% endif %} · threshold {{ threshold|weight }}</p>
{% if rows %}
<table class="table table-sm">
  <thead><tr><th scope="col">Student</th><th scope="col" class="text-end">PO {{ po.number }}</th><th scope="col"><span class="visually-hidden">Attains</span></th></tr></thead>
  <tbody>
  {% for user, row in rows %}
    <tr>
      <td><a href="{% url 'reports:department_student' user.pk %}">{{ user.get_full_name }}</a>
        <span class="small text-body-secondary">{{ user.student_number }}</span></td>
      <td class="text-end pl-num">{{ row.score|score }}</td>
      <td>{% if row.attains %}<span class="text-success">✓ attains</span>{% else %}<span class="text-danger">▼ below</span>{% endif %}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p>No student has a score for this outcome here.</p>
{% endif %}
```

```css
/* static/css/polaris.css */
.pl-attain__cell { min-width: 5.5rem; line-height: 1.1; }
.pl-attain__cell.is-met { background: var(--bs-success-bg-subtle); color: var(--bs-success-text-emphasis); }
.pl-attain__cell.is-below { background: var(--bs-danger-bg-subtle); color: var(--bs-danger-text-emphasis); }
```

**6. The chart.** A grouped horizontal bar chart: one group per PO, one bar per column, with a dashed vertical line at the target. Chart.js 4 has no built-in reference line without the annotation plugin, so a ten-line inline plugin draws it. That's one less vendored file. Gaps (`null`) are left blank, not drawn as zero (P12).

```javascript
// static/js/polaris.js  (add; call from the DOMContentLoaded handler)
function renderAttainmentChart() {
  const canvas = document.getElementById("attain-chart");
  const dataEl = document.getElementById("attain-chart-data");
  if (!canvas || !dataEl || !window.Chart) return;
  const data = JSON.parse(dataEl.textContent);
  const targetLine = {
    id: "targetLine",
    afterDatasetsDraw(chart) {
      const x = chart.scales.x.getPixelForValue(data.target);
      const { top, bottom } = chart.chartArea;
      const ctx = chart.ctx;
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--bs-danger");
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
      ctx.restore();
    },
  };
  new Chart(canvas, {
    type: "bar",
    data: { labels: data.labels, datasets: data.datasets },
    options: {
      indexAxis: "y",
      scales: { x: { min: 0, max: 100, title: { display: true, text: "% of students attaining" } } },
      plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw === null ? "no evidence" : c.raw + "%"}` } } },
    },
    plugins: [targetLine],
  });
}
```

The table stays the primary display. The chart is the "at a glance" view, and screen readers get the table.

**7. Permission matrix.** `reports:attainment_students` is new (not in §4.8), so add a line to `ROUTES` in `apps/accounts/tests/routes.py`:

```python
    Route("reports:attainment_students", HEAD, kwargs=lambda w: {"po_id": w.po.pk}, story="S6-05"),
```

The matrix sends no `?key=`, so the allowed roles get the view's 404 for a missing key; give the row `ok=P({200, 404})` if you keep that behaviour, or have the view fall back to the first cohort. Everyone else gets 404 (`require_role("head")`), anonymous 302.

### Tests

```python
# apps/scoring/tests/test_attainment.py
from decimal import Decimal

import pytest

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, AssessmentLOWeightFactory, CourseFactory, EnrollmentFactory, GradeFactory,
    LearningOutcomeFactory, LOPOWeightFactory, MembershipFactory, OfferingFactory,
    ProgramOutcomeFactory, ProgramOutcomeSetFactory, TermFactory, UserFactory,
)
from apps.core.tests.scenarios import small_department
from apps.scoring.aggregates import attainment_matrix, attainment_students, student_po_scores
from apps.scoring.engine import compute_student_profile
from apps.scoring.loaders import load_student_inputs


def one_assessment_course(program, term, po, *, course=None):
    """An offering whose single assessment feeds a single LO linked to `po` with weight 3.
    A student's PO score is then exactly their published mark."""
    off = OfferingFactory(course=course or CourseFactory(program=program), term=term)
    a = AssessmentFactory(offering=off, max_score=Decimal("100"))
    lo = LearningOutcomeFactory(offering=off, number=1)
    AssessmentLOWeightFactory(assessment=a, learning_outcome=lo, weight=Decimal("100"))
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=3)
    return off, a


def student(program, cohort):
    u = UserFactory()
    MembershipFactory(user=u, program=program, role=ProgramMembership.Role.STUDENT, cohort_year=cohort)
    return u


def grade(off, a, user, mark):
    e = EnrollmentFactory(offering=off, student=user)
    GradeFactory(assessment=a, enrollment=e, score=Decimal(mark), published_score=Decimal(mark))
    return e


@pytest.fixture
def dept(db):
    term = TermFactory(code="2026S", status=Term.Status.CLOSED)
    off0 = OfferingFactory(term=term)
    program = off0.course.program
    program.attainment_threshold = Decimal("60")
    program.save()
    po_set = ProgramOutcomeSetFactory(program=program, is_active=True, effective_from_year=2020)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1)
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2)
    return program, term, po1, po2


def test_ten_students_six_above_threshold_is_60_percent(dept):          # T1.6 AC1
    program, term, po1, po2 = dept
    off, a = one_assessment_course(program, term, po1)
    for mark in [70, 75, 80, 85, 90, 60, 59, 40, 30, 20]:                 # 60 counts as attaining
        grade(off, a, student(program, 2023), mark)
    m = attainment_matrix(program, by="cohort", terms=[term])
    cell = m.rows[0].cells[0]
    assert (cell.scored, cell.attaining, cell.rate) == (10, 6, Decimal("0.6"))
    assert m.rows[1].cells[0].rate is None                                # PO 2: no evidence, not 0%


def test_draft_grades_do_not_count(dept):                                 # P4
    program, term, po1, _ = dept
    off, a = one_assessment_course(program, term, po1)
    e = EnrollmentFactory(offering=off, student=student(program, 2023))
    GradeFactory(assessment=a, enrollment=e, score=Decimal("90"), published_score=None)
    assert attainment_matrix(program, by="cohort", terms=[term]).rows[0].cells[0].scored == 0


def test_cohorts_become_columns(dept):
    program, term, po1, _ = dept
    off, a = one_assessment_course(program, term, po1)
    grade(off, a, student(program, 2023), 80)
    grade(off, a, student(program, 2024), 50)
    m = attainment_matrix(program, by="cohort", terms=[term])
    assert [c.key for c in m.columns] == ["2023", "2024"]
    assert [c.rate for c in m.rows[0].cells] == [Decimal(1), Decimal(0)]


def test_by_term_scores_each_term_alone(dept):
    program, spring, po1, _ = dept
    fall = TermFactory(code="2026F", starts_on=spring.ends_on, status=Term.Status.OPEN)
    s = student(program, 2023)
    off1, a1 = one_assessment_course(program, spring, po1)
    off2, a2 = one_assessment_course(program, fall, po1)
    grade(off1, a1, s, 90)
    grade(off2, a2, s, 40)
    m = attainment_matrix(program, by="term", terms=[fall, spring])
    assert [c.key for c in m.columns] == ["2026S", "2026F"]               # chronological
    assert [c.attaining for c in m.rows[0].cells] == [1, 0]


def test_retake_latest_attempt_counts_in_cohort_view(dept):              # P9
    program, spring, po1, _ = dept
    fall = TermFactory(code="2026F", starts_on=spring.ends_on, status=Term.Status.CLOSED)
    course = CourseFactory(program=program)
    s = student(program, 2023)
    off1, a1 = one_assessment_course(program, spring, po1, course=course)
    off2, a2 = one_assessment_course(program, fall, po1, course=course)
    grade(off1, a1, s, 30)
    grade(off2, a2, s, 75)
    _, scores = student_po_scores(program, by="cohort", terms=[spring, fall])
    assert scores["2023"][s.pk][po1.pk] == Decimal("75")


def test_older_cohort_measured_on_its_own_po_set(dept):                  # P13
    program, term, po1, _ = dept
    po1.po_set.effective_from_year = 2024
    po1.po_set.save()
    old_set = ProgramOutcomeSetFactory(program=program, is_active=False, effective_from_year=2015)
    ProgramOutcomeFactory(po_set=old_set, number=1)
    off, a = one_assessment_course(program, term, po1)                    # links to the active set
    grade(off, a, student(program, 2022), 90)                             # 2022 → old set
    grade(off, a, student(program, 2024), 90)                             # 2024 → active set
    m = attainment_matrix(program, by="cohort", terms=[term])
    assert [c.scored for c in m.rows[0].cells] == [0, 1]


def test_matches_per_student_loader_on_seed_data(db):
    """The batch path must give the same PO scores as each student's own profile."""
    dept_data = small_department()
    program = dept_data.program
    terms = list(Term.objects.all())
    _, scores = student_po_scores(program, by="cohort", terms=terms)
    flat = {sid: s for col in scores.values() for sid, s in col.items()}
    for s in dept_data.students:
        profile = compute_student_profile(load_student_inputs(s, include_open_terms=True))
        expected = {po: ns.score for po, ns in profile.po_scores.items() if ns.score is not None}
        assert flat.get(s.pk, {}) == expected


def test_drill_down_lists_lowest_first(dept):
    program, term, po1, _ = dept
    off, a = one_assessment_course(program, term, po1)
    grade(off, a, student(program, 2023), 80)
    low = student(program, 2023)
    grade(off, a, low, 45)
    rows = attainment_students(program, po=po1, by="cohort", key="2023", terms=[term])
    assert [(r.student_id, r.attains) for r in rows][0] == (low.pk, False)
    assert [r.score for r in rows] == [Decimal("45"), Decimal("80")]


def test_query_count_does_not_grow_with_students(dept, django_assert_max_num_queries):
    program, term, po1, _ = dept
    off, a = one_assessment_course(program, term, po1)
    for i in range(40):
        grade(off, a, student(program, 2023), 50 + i)
    with django_assert_max_num_queries(15):
        attainment_matrix(program, by="cohort", terms=[term])
```

`test_matches_per_student_loader_on_seed_data` assumes `small_department()` returns an object with `.program` and `.students`, and that its students hold student memberships with a cohort year. If the S1-08 scenario differs, adjust the two attribute names, not the assertion: that assertion is the guarantee that the dashboard and the student profile never disagree.

```python
# apps/reports/tests/test_attainment_views.py
import pytest
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.scoring.tests.test_attainment import dept, grade, one_assessment_course, student  # noqa: F401


@pytest.fixture
def head(dept):
    program = dept[0]
    u = UserFactory()
    MembershipFactory(user=u, program=program, role=ProgramMembership.Role.HEAD)
    return u


def test_dashboard_shows_attainment_with_target_colouring(client, dept, head):
    program, term, po1, _ = dept
    off, a = one_assessment_course(program, term, po1)
    for mark in (80, 80, 40):
        grade(off, a, student(program, 2023), mark)
    client.force_login(head)
    html = client.get(reverse("reports:department") + "?target=60").content.decode()
    assert "67%" in html and "is-met" in html and "2/3" in html
    html = client.get(reverse("reports:department") + "?target=70").content.decode()
    assert "is-below" in html


def test_bad_options_fall_back_to_defaults(client, dept, head):
    client.force_login(head)
    assert client.get(reverse("reports:department") + "?by=nonsense&target=abc").status_code == 200


def test_drill_down_is_head_only(client, dept, head):
    program, term, po1, _ = dept
    url = reverse("reports:attainment_students", args=[po1.pk]) + "?key=2023"
    client.force_login(UserFactory())
    assert client.get(url).status_code == 404
    client.force_login(head)
    assert client.get(url).status_code == 200
```

The dashboard tests assume S3-04's term selection includes closed terms by default. The `dept` fixture's term is `CLOSED` for that reason.

### Check it works

1. `uv run python manage.py seed_demo --reset`, log in as Prof. Deniz Kara, and open `/department/`.
2. The PO attainment card shows 11 rows and the cohorts 2023, 2024, 2025 as columns. PO 11 shows "—" everywhere (Appendix B leaves it uncovered on purpose).
3. Change the target to 80 and click Update: more cells turn red with ▼. The numbers don't change, only the colours.
4. Switch to "By term": one column per selected term, oldest first.
5. Click a cell: the modal lists its students, lowest first. Click a name: that student's profile opens. Cross-check one student's PO score there against the modal.
6. Log in as a student and request `/department/attainment/1/?key=2023`: 404.
7. With django-debug-toolbar, the dashboard runs about 15 queries or fewer and loads in under 1.5 s on the seed data (T1.6 AC3).

### Done when

- [ ] T1.6 AC1 (10 students, 6 above → 60%): `test_ten_students_six_above_threshold_is_60_percent`
- [ ] P4, P9, P12, P13 respected: `test_draft_grades_do_not_count`, `test_retake_latest_attempt_counts_in_cohort_view`, the None assertion in the AC1 test, `test_older_cohort_measured_on_its_own_po_set`
- [ ] Dashboard and student profile agree: `test_matches_per_student_loader_on_seed_data`
- [ ] Target colouring with icon + colour; drill-down head-only: `test_dashboard_shows_attainment_with_target_colouring`, `test_drill_down_is_head_only`
- [ ] Query count bounded (T1.6 AC3 groundwork): `test_query_count_does_not_grow_with_students`
- [ ] Permission matrix updated

### Commits and PR

```
Compute PO attainment per cohort and term from per-student scores
Add attainment table and chart to the department dashboard
Add attainment drill-down with the students behind each cell
```

PR title: **S6-05 PO attainment on the department dashboard** (`Closes #<issue>`).

---

## Sprint 6 review and retro prompts

- **Demo order for the sprint review (10 min):** S6-01 → S6-02 → S6-03 as one story (upload `cse311.pdf`, edit a violet cell, Apply), then the restaurant-menu failure, then S6-04 on a hand-made course, then S6-05 as the head.
- **Evidence to save in `docs/process/sprint-06/`:** board screenshot, burndown, `eval.md` (the `eval_extraction --runs 3` table), the total API cost for the sprint from the Anthropic Console, and one screenshot of the review screen (the CSE 311 report and the demo both use it).
- **Retro question worth asking:** did the `ReviewDraft` contract from S5-04 hold, or did S6-02 have to change it? Write the answer in the retro notes. It's a concrete example for the "interfaces between people" point in the CSE 311 report.

---

## Code map additions

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `apps/ingestion/files.py` | `sniff_media_type` | `(fileobj) -> str` | Real file type from magic bytes; raises `UnsupportedFile` |
| `apps/ingestion/files.py` | `docx_to_text` | `(data: bytes) -> str` | Word paragraphs and tables in reading order |
| `apps/ingestion/files.py` | `downscale_image` | `(data: bytes, media_type: str) -> bytes` | EXIF-rotate and cap at 2000 px |
| `apps/ingestion/files.py` | `prepared_file` | context manager `(job) -> (Path, media_type)` | Temp file ready for `extract_syllabus` |
| `apps/ingestion/files.py` | `UnsupportedFile` | exception | User-facing "wrong file type" |
| `apps/ingestion/services.py` | `create_syllabus_job` | **changed:** `(user, offering, uploaded_file, *, media_type) -> IngestionJob` | Adds `media_type` keyword; daily cap of 10 |
| `apps/ingestion/services.py` | `po_list_text` | `(po_set) -> str` | "PO n: description" lines for prompts |
| `apps/ingestion/services.py` | `check_draft` | `(draft, po_numbers: set[int]) -> list[str]` | Server-side re-validation before Apply |
| `apps/ingestion/services.py` | `setup_snapshot` | `(offering) -> dict` | Whole setup as JSON for `setup.replace` audit |
| `apps/ingestion/services.py` | `offering_has_grades` | `(offering) -> bool` | A grade = draft, published or excused value |
| `apps/ingestion/tasks.py` | `mark_failed`, `save_ready`, `estimate_cost`, `is_transient`, `backoff_seconds` | see S6-01 | Job lifecycle helpers |
| `apps/ingestion/review.py` | `ReviewForm`, `LOForm`, `AssessmentForm`, `build_review_grids`, `review_warnings`, `course_mismatches`, `cell_name`, `new_key` | see S6-02 | Review screen logic (`ReviewForm` re-exported from `forms.py`) |
| `apps/ingestion/validation.py` | `Origin`, `DraftCourse`, `DraftLO`, `DraftAssessment`, `DraftALO`, `DraftLOPO`, `ReviewDraft.to_json/from_json` | see "Contracts" | The review draft (owned by S5-04; listed so the shape is recorded) |
| `apps/accounts/decorators.py` | `require_job_access` | decorator; view gets `job=`, `offering=`, `perms_for=` | Permission check for `/ingestion/<job_id>/…` |
| `apps/outcomes/matrix.py` | `GridCol`, `GridCell`, `GridRow`, `WeightGrid` | `GridCell` gains `origin`, `rationale` | Grid include data shape |
| `apps/outcomes/suggest.py` | `suggest_lo_po_weights` | **changed:** `(offering) -> SuggestionResult` (was `list[LOPOSuggestion]`) | Needs to return warnings for T1.3 AC1 |
| `apps/outcomes/suggest.py` | `SuggestionResult`, `LOPOSuggestion`, `SuggestionError`, `SuggestedLink`, `SuggestionResponse`, `clean_suggestions`, `course_po_levels`, `build_prompt` | see S6-04 | |
| `apps/outcomes/services.py` | `apply_lo_po_suggestions` | `(user, offering, suggestions) -> int` | Write AI suggestions into empty cells |
| `apps/scoring/aggregates.py` | `attainment_matrix` | `(program, *, by, terms, threshold=None, cohort=None) -> AttainmentMatrix` | Adds optional `cohort` |
| `apps/scoring/aggregates.py` | `student_po_scores`, `attainment_students`, `AttainmentCell`, `AttainmentColumn`, `AttainmentRow`, `AttainmentMatrix`, `StudentPOScore`, `BY_COHORT`, `BY_TERM` | see S6-05 | |
| `apps/reports/forms.py` | `AttainmentOptionsForm` | `.values() -> (by, target)` | `by` and `target` from the query string |
| URL | `reports:attainment_students` | `/department/attainment/<po_id>/` GET (`?key=…` plus dashboard params) → `reports.views.attainment_students` | Drill-down partial, head only |

## Spec contradictions and gaps found while writing this chapter

1. **`validate_and_derive` return type.** Spec §4.8 says `validate_and_derive(extraction, offering) -> ReviewDraft`, but the task sketch in §7.5 says `result, warnings = validate_and_derive(extraction, job.offering)`. This chapter follows §4.8 (warnings live on `draft.warnings`); §7.5's sketch should be updated.
2. **`source` on assessments and assessment→LO weights.** T1.2 AC5 says "Every created LO and weight carries `source` = `syllabus` or `ai_suggested`", but `Assessment` and `AssessmentLOWeight` in §5.2 have no `source` field. This chapter records their origin in the `syllabus.apply` audit event instead. Either reword AC5 or add the field in Sprint 8.
3. **Out-of-range weights: clamp or drop?** §7.6 says "LO→PO weight outside 1–5 → Clamp to 1–5; warning", and T1.3 AC1 says "invalid entries dropped with a warning". This chapter keeps both, on purpose: clamp in extraction (a human reviews it next), drop in suggestions (written straight to the grid). Say so in §7.6.
4. **P13 fallback.** P13 doesn't say what happens when no PO set has `effective_from_year ≤ cohort_year`. S6-05 uses the oldest set. Add that to P13 (and make `po_set_for_student` do the same).
5. **T1.6 attainment target** "head can change it" has no field in §5.2. This chapter uses a URL parameter (`?target=`, default 70). Add `Program.attainment_target` if it should persist.
6. **`suggest_lo_po_weights` return type** changed to `SuggestionResult` (see the code map additions). §4.8 lists `list[LOPOSuggestion]`.
