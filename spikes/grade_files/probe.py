"""S3-08 throwaway probe. NOT product code. Delete after S4-03 is merged.
Run:  uv run python spikes/grade_files/probe.py seed/grades/*.csv seed/grades/*.xlsx"""

from __future__ import annotations

import csv
import difflib
import io
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

ASSESSMENTS = ["Midterm I", "Project", "Final exam", "Quiz 1", "Quiz 2", "Homework"]
STUDENT_HEADER = re.compile(r"(student|öğrenci|ogrenci|id number|^no\.?$|number)", re.I)
STUDENT_VALUE = re.compile(r"^\d{4}-?\d{4}$")
EXCUSED = {"ex", "excused", "m", "muaf"}
MISSING = {"", "-", "g", "girmedi", "na", "n/a"}
ALIASES = {
    "vize": "midterm i",
    "midterm-1": "midterm i",
    "midterm 1": "midterm i",
    "proje": "project",
    "final": "final exam",
    "ödev": "homework",
    "odev": "homework",
}


def read_table(path: Path) -> list[list[str]]:
    if path.suffix.lower() == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        return [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1254"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("unknown encoding")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def find_header(rows: list[list[str]]) -> int:
    """First row with >= 2 non-empty cells where one looks like a student-number header."""
    for i, row in enumerate(rows[:15]):
        cells = [c.strip() for c in row if c and c.strip()]
        if len(cells) >= 2 and any(STUDENT_HEADER.search(c) for c in cells):
            return i
    return 0


def normalise_number(value: str) -> str:
    value = value.strip()
    if value.endswith(".0"):
        value = value[:-2]  # 20240001.0 -> 20240001
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:]}"  # 20240001 -> 2024-0001
    return value


def parse_mark(value: str):
    v = value.strip().lower().lstrip("%")
    if v in MISSING:
        return ("missing", None)
    if v in EXCUSED:
        return ("excused", None)
    try:
        number = Decimal(v.replace(",", "."))
    except InvalidOperation:
        return ("invalid", value)
    return ("value", number)


def guess_column(header: str) -> str | None:
    h = re.sub(r"\s*\((real|100)\)\s*$", "", header.strip().lower())
    h = re.sub(r"^(quiz|assignment):\s*", "", h)
    h = ALIASES.get(h, h)
    names = {a.lower(): a for a in ASSESSMENTS}
    if h in names:
        return names[h]
    match = difflib.get_close_matches(h, names, n=1, cutoff=0.75)
    return names[match[0]] if match else None


def probe(path: Path) -> None:
    start = time.perf_counter()
    rows = read_table(path)
    h = find_header(rows)
    header = rows[h]
    student_col = next((i for i, c in enumerate(header) if STUDENT_HEADER.search(c or "")), None)
    mapping = {i: guess_column(c) for i, c in enumerate(header) if i != student_col and c}
    counts = {"value": 0, "missing": 0, "excused": 0, "invalid": 0}
    numbers = []
    for row in rows[h + 1 :]:
        if not any(c.strip() for c in row):
            continue
        numbers.append(normalise_number(row[student_col]) if student_col is not None else "?")
        for i, target in mapping.items():
            if target and i < len(row):
                counts[parse_mark(row[i])[0]] += 1
    elapsed = (time.perf_counter() - start) * 1000
    dupes = {n for n in numbers if numbers.count(n) > 1}
    bad_numbers = [n for n in numbers if not STUDENT_VALUE.match(n)]
    print(f"\n== {path.name}  ({elapsed:.0f} ms)")
    print(f"   header row: {h + 1}  student column: {header[student_col] if student_col is not None else 'NOT FOUND'}")
    print(f"   columns: { {header[i]: t for i, t in mapping.items()} }")
    print(f"   marks: {counts}   rows: {len(numbers)}   duplicates: {sorted(dupes)}")
    print(f"   odd student numbers: {bad_numbers}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        probe(Path(arg))
