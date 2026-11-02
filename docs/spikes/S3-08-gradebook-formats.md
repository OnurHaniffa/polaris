# Spike S3-08: gradebook file formats

**Question:** Can POlaris read the grade files instructors actually have, well enough to make
T1.1's dry run trustworthy?
**Timebox:** 1.5 days · **Spent:** … h · **Author:** … · **Date:** 2026-11-03

## Files examined
| File | Source (program, locale) | Real or generated | Rows | Notes |
|---|---|---|---|---|
| clean.csv | Ideal export, UTF-8, comma | Generated | 21 | Exact assessment names |
| turkish_excel.csv | Excel, Turkish locale, "CSV (semicolon delimited)" | Generated | 21 | cp1254, `;`, decimal comma, `G`, `M`, blank |
| messy.xlsx | Hand-made instructor sheet | Generated | 23 | Title rows, numbers stored as numbers, `EX`, `-`, `105`, `-3`, `abc`, formula column, duplicate and unknown student |
| lms_export.xlsx | Moodle-style export | Generated | 21 | `Quiz: Midterm I (Real)`, email and "Last downloaded" columns |
| large.csv | Big class | Generated | 200 | 6 assessments |
| real file 1 | … | Real | … | Not tested |
| real file 2 | … | Real | … | Not tested |

## Results
| Check | clean.csv | turkish_excel.csv | messy.xlsx | lms_export.xlsx | large.csv | real file 1 | real file 2 |
|---|---|---|---|---|---|---|---|
| Decoded correctly (Q1) | ✓ | ✓ (cp1254) | n/a (xlsx) | n/a (xlsx) | ✓ | Not tested | Not tested |
| Separator sniffed (Q1) | ✓ `,` | ✓ `;` | n/a | n/a | ✓ `,` | Not tested | Not tested |
| Header row found (Q2) | ✓ row 1 | ✓ row 1 | ✓ row 4 | ✓ row 1 | ✓ row 1 | Not tested | Not tested |
| Student column found (Q3) | ✓ Student No | ✓ Öğrenci No | ✓ No | ✓ ID number | ✓ Student No | Not tested | Not tested |
| All student numbers normalised (Q3) | ✓ | ✓ | ✓ (numbers stored as numbers handled) | ✓ | ✓ | Not tested | Not tested |
| Marks parsed: `85,5`, EX/M/G, blanks (Q4) | ✓ | ✓ (2 missing, 1 excused) | ✓ (1 missing, 1 excused, 1 invalid) | ✓ | ✓ | Not tested | Not tested |
| Columns auto-matched (Q5) | ✓ | ✓ (`Vize`, `Proje`) | ✓ (`Midterm-1 `, `PROJECT`) | ✓ (`Quiz: Midterm I (Real)`) | ✓ | Not tested | Not tested |
| Extra columns ignored (Q6) | ✓ | ✓ | ✓ (`Total`) | ✓ (email, total, last downloaded) | ✓ | Not tested | Not tested |
| Formula cells (Q7) | n/a | n/a | `Total` ignored; cached values missing in generated file | n/a | n/a | Not tested | Not tested |
| Time, ms (Q8) | 1 | 1 | 2 | 5 | 1 | Not tested | Not tested |

Other findings:
- `105` and `-3` in `messy.xlsx` were counted as valid values. The probe does no range check.
- The duplicate student `2024-0001` in `messy.xlsx` was detected.
- The unknown student