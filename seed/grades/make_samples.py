"""Generate the sample gradebook files for the S3-08 spike and the T1.1 golden tests.
Run from the repo root:  uv run python seed/grades/make_samples.py
Deterministic: the same files every time."""

from __future__ import annotations

import csv
import random
import re
import zipfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent
rng = random.Random(3118) # noqa: S311
FIXED_TIME = datetime(2026, 11, 6, 12, 0, 0)
STUDENTS = [f"2024-{i:04d}" for i in range(1, 21)] + ["2024-0041"]  # 20 seeded + Elif
NAMES = [
    "Ayşe Kaya",
    "Mert Demir",
    "Zeynep Çelik",
    "Can Şahin",
    "Elif Öztürk",
    "Burak Yıldız",
    "Selin Arslan",
    "Emre Koç",
    "Damla Kurt",
    "Oğuz Polat",
    "İrem Aslan",
    "Kerem Güneş",
    "Ceren Tekin",
    "Barış Bulut",
    "Defne Aktaş",
    "Umut Ateş",
    "Ece Uçar",
    "Kaan Karaca",
    "Melis Doğan",
    "Arda Kılıç",
    "Elif Yıldız",
]


def mark() -> float:
    return round(rng.uniform(35, 100) * 2) / 2


def write_csv(name: str, rows: list[list], *, encoding="utf-8", delimiter=",") -> None:
    with open(HERE / name, "w", newline="", encoding=encoding) as f:
        csv.writer(f, delimiter=delimiter).writerows(rows)


def save_deterministic(wb: Workbook, path: Path) -> None:
    """Save an .xlsx with fixed timestamps so the file is identical on every run."""
    wb.properties.created = FIXED_TIME
    tmp = path.with_name(path.stem + ".tmp.xlsx")
    wb.save(tmp)
    stamp = FIXED_TIME.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with zipfile.ZipFile(tmp) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            content = src.read(item.filename)
            if item.filename == "docProps/core.xml":
                content = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", rb"\g<1>" + stamp, content)
            info = zipfile.ZipInfo(item.filename, FIXED_TIME.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, content)
    tmp.unlink()


def clean_csv() -> None:
    rows = [["Student No", "Name", "Midterm I", "Project"]]
    for number, name in zip(STUDENTS, NAMES, strict=True):
        rows.append([number, name, mark(), mark()])
    rows[-1][2:] = [90, 80]  # Elif, as on the slide
    write_csv("clean.csv", rows)


def turkish_excel_csv() -> None:
    rows = [["Öğrenci No", "Adı Soyadı", "Vize", "Proje"]]
    for number, name in zip(STUDENTS, NAMES, strict=True):
        rows.append([number, name, str(mark()).replace(".", ","), str(mark()).replace(".", ",")])
    rows[3][2] = "G"  # girmedi: did not sit the exam -> missing
    rows[5][3] = "M"  # muaf: exempt -> excused
    rows[7][2] = ""  # blank cell
    write_csv("turkish_excel.csv", rows, encoding="cp1254", delimiter=";")


def messy_xlsx() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Notlar"
    ws.append(["CSE 311 Software Engineering — Fall 2026 grades"])
    ws.append(["Instructor: Prof. Deniz Kara"])
    ws.append([])
    ws.append(["No", "Student", "Midterm-1 ", "PROJECT", "Total"])
    for r, (number, name) in enumerate(zip(STUDENTS, NAMES, strict=True), start=5):
        as_number = int(number.replace("-", "")) if r % 4 == 0 else number  # Q3: some numbers are numbers
        ws.append([as_number, name, mark(), mark(), f"=0.25*C{r}+0.4*D{r}"])
    ws["C6"] = "EX"  # excused
    ws["D7"] = "-"  # dash: empty
    ws["C8"] = 105  # above max
    ws["D9"] = -3  # negative
    ws["C10"] = "abc"  # not a number
    last = ws.max_row
    ws.append([STUDENTS[0], NAMES[0], mark(), mark(), f"=0.25*C{last + 1}+0.4*D{last + 1}"])  # duplicate
    ws.append(["2099-0001", "Unknown Student", mark(), mark(), ""])  # not enrolled
    save_deterministic(wb, HERE / "messy.xlsx")


def lms_export_xlsx() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Grades"
    ws.append(
        [
            "First name",
            "Surname",
            "ID number",
            "Email address",
            "Quiz: Midterm I (Real)",
            "Assignment: Project (Real)",
            "Course total (Real)",
            "Last downloaded from this course",
        ]
    )
    for number, name in zip(STUDENTS, NAMES, strict=True):
        first, last = name.split(" ", 1)
        ws.append(
            [first, last, number, f"{number}@students.polaris.test", mark(), mark(), "", "Friday, 6 November 2026, 12:00 PM"]
        )
        save_deterministic(wb, HERE / "lms_export.xlsx")


def large_csv() -> None:
    header = ["Student No", "Name", "Quiz 1", "Quiz 2", "Midterm I", "Project", "Homework", "Final exam"]
    rows = [header]
    for i in range(1, 201):
        rows.append([f"2024-{i:04d}", f"Student {i}"] + [mark() for _ in range(6)])
    write_csv("large.csv", rows)


if __name__ == "__main__":
    for make in (clean_csv, turkish_excel_csv, messy_xlsx, lms_export_xlsx, large_csv):
        make()
        print(f"wrote {make.__name__}")
