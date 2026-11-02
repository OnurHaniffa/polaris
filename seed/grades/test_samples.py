# ruff: noqa: S101

# collected by pytest because python_files = test_*.py
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FILES = ["clean.csv", "turkish_excel.csv", "messy.xlsx", "lms_export.xlsx", "large.csv"]


@pytest.mark.parametrize("name", FILES)
def test_sample_file_exists(name):
    assert (HERE / name).stat().st_size > 0


def test_turkish_sample_is_cp1254_with_semicolons():
    raw = (HERE / "turkish_excel.csv").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    assert raw.decode("cp1254").splitlines()[0] == "Öğrenci No;Adı Soyadı;Vize;Proje"
