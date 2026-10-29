"""Turn the backlog table in the spec (Part 12) into GitHub issues on the project board.

    uv run python scripts/import_backlog.py                  # dry run: prints what it would do
    uv run python scripts/import_backlog.py --apply          # creates issues + board items

Needs the GitHub CLI logged in with the project scope:  gh auth refresh -s project
Run it ONCE. A second --apply skips rows whose title already exists as an issue.

It sets the Points, Area, Tier and Priority fields. The Sprint (iteration) field is set by
hand afterwards in the Backlog table view: select the rows of one sprint, paste the iteration.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OWNER = "OnurHaniffa"
REPO = "OnurHaniffa/polaris"
PROJECT_TITLE = "POlaris Backlog"
SPEC = Path(__file__).resolve().parent.parent / "POLARIS-PROJECT-SPEC.md"

AREA_BY_OWNER = {"A": "Engine & Data", "B": "Instructor", "C": "Platform & Insights"}
PROCESS_FEATURES = {"Process", "CSE 311", "CSE 321", "Demo", "Reports", "Release"}
MILESTONES = [
    # (title, due date, last sprint number it covers)
    ("CSE 321 checkpoint", "2026-11-12", 4),
    ("CSE 311 checkpoint", "2026-11-17", 5),
    ("Feature complete", "2026-12-06", 7),
    ("Final demo", "2026-12-29", 99),
]


def gh(*args, capture=True):
    result = subprocess.run(["gh", *args], check=True, text=True, capture_output=capture)  # noqa: S603, S607
    return result.stdout.strip()


def parse_backlog():
    """Rows of the table under '# PART 12', as dicts."""
    text = SPEC.read_text(encoding="utf-8")
    part = text[text.index("# PART 12") : text.index("# PART 13")]
    rows = []
    for line in part.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 7 or cells[0] in {"ID", "---"} or set(cells[0]) <= {"-"}:
            continue
        story_id, story, feature, tier, points, owner, sprint = cells
        if not points.isdigit():
            continue
        if story_id == "—":  # Tier 2/3 extras with no sprint yet: "T3.1 What-if simulator"
            story_id = story.split()[0]
        rows.append(
            {
                "id": story_id,
                "story": story,
                "feature": feature,
                "tier": tier,
                "points": int(points),
                "owner": owner,
                "sprint": int(sprint) if sprint.isdigit() else None,
            }
        )
    return rows


def title_of(row):
    """'S1-06 · Every score is computed by one tested engine…' (drops the 'As a …,' part)."""
    words = re.sub(r"^As [^,]+, (I |we )?", "", row["story"])
    words = words.removeprefix(row["id"]).strip()  # Tier 2/3 rows repeat their ID
    return f"{row['id']} · {words[0].upper()}{words[1:]}"[:120]


def area_of(row):
    """None for unowned extras (T2.7, T3.x): set the Area when someone picks them up."""
    if row["feature"] in PROCESS_FEATURES:
        return "Process"
    return AREA_BY_OWNER.get(row["owner"][:1])


def priority_of(row):
    if row["tier"] in {"Tier 2", "Tier 3"} or row["sprint"] is None:
        return "P2"
    if row["tier"] == "Baseline" or (row["tier"] == "Chore" and row["sprint"] <= 3):
        return "P0"
    return "P1"


def milestone_of(row):
    sprint = 99 if row["sprint"] is None else row["sprint"]
    return next(title for title, _, last in MILESTONES if sprint <= last)


def label_of(row):
    if row["tier"] == "Chore":
        return "chore"
    if "(spike)" in row["story"]:
        return "spike"
    return "story"


def body_of(row):
    sprint = "unscheduled (if time)" if row["sprint"] is None else f"Sprint {row['sprint']}"
    return (
        f"### Story ID (from the spec backlog)\n\n{row['id']}\n\n"
        f"### User story\n\n{row['story']}\n\n"
        "### Acceptance criteria\n\n"
        f"See `POLARIS-PROJECT-SPEC.md` Part 6, feature **{row['feature']}**. "
        "Copy the ACs that this story delivers here at refinement.\n\n"
        "### Tasks\n\n- [ ] Tests\n- [ ] Implementation\n- [ ] Blank + error states\n"
        "- [ ] Spec updated if needed\n\n"
        f"### Notes\n\nPlanned: {sprint} · Owner: Person {row['owner']} · "
        f"Initial estimate: {row['points']} pts · Tier: {row['tier']}\n"
    )


def ensure_labels_and_milestones(apply):
    for name, color in [
        ("story", "1f3a68"),
        ("bug", "b42318"),
        ("chore", "6c737f"),
        ("spike", "6941c6"),
        ("docs", "0e7c86"),
    ]:
        print(f"label {name}")
        if apply:
            gh("label", "create", name, "--repo", REPO, "--color", color, "--force")
    existing = gh("api", f"repos/{REPO}/milestones?state=all", "--jq", ".[].title") if apply else ""
    for title, due, _ in MILESTONES:
        print(f"milestone {title} due {due}")
        if apply and title not in existing.splitlines():
            gh(
                "api",
                f"repos/{REPO}/milestones",
                "-f",
                f"title={title}",
                "-f",
                f"due_on={due}T20:59:59Z",
            )


def project_ids():
    projects = json.loads(gh("project", "list", "--owner", OWNER, "--format", "json"))["projects"]
    project = next(p for p in projects if p["title"] == PROJECT_TITLE)
    fields = json.loads(
        gh("project", "field-list", str(project["number"]), "--owner", OWNER, "--format", "json")
    )["fields"]
    return project, {f["name"]: f for f in fields}


def set_field(project, field, item_id, value):
    args = ["project", "item-edit", "--id", item_id, "--project-id", project["id"]]
    args += ["--field-id", field["id"]]
    if field["type"] == "ProjectV2Field":  # number
        args += ["--number", str(value)]
    else:
        option = next(o for o in field["options"] if o["name"] == value)
        args += ["--single-select-option-id", option["id"]]
    gh(*args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="really create the issues")
    apply = parser.parse_args().apply

    rows = parse_backlog()
    print(f"{len(rows)} backlog rows, {sum(r['points'] for r in rows)} points\n")
    ensure_labels_and_milestones(apply)

    if apply:
        project, fields = project_ids()
        existing_titles = set(
            gh(
                "issue",
                "list",
                "--repo",
                REPO,
                "--state",
                "all",
                "--limit",
                "500",
                "--json",
                "title",
                "--jq",
                ".[].title",
            ).splitlines()
        )
    for row in rows:
        title = title_of(row)
        print(
            f"{title}  [{label_of(row)} · {row['points']} pts · {area_of(row)} · "
            f"{priority_of(row)} · {milestone_of(row)}]"
        )
        if not apply or title in existing_titles:
            continue
        url = gh(
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            title,
            "--body",
            body_of(row),
            "--label",
            label_of(row),
            "--milestone",
            milestone_of(row),
        )
        item = json.loads(
            gh(
                "project",
                "item-add",
                str(project["number"]),
                "--owner",
                OWNER,
                "--url",
                url,
                "--format",
                "json",
            )
        )
        set_field(project, fields["Points"], item["id"], row["points"])
        if area_of(row):
            set_field(project, fields["Area"], item["id"], area_of(row))
        set_field(project, fields["Tier"], item["id"], row["tier"])
        set_field(project, fields["Priority"], item["id"], priority_of(row))
    if not apply:
        print("\nDry run only. Re-run with --apply to create them.")


if __name__ == "__main__":
    sys.exit(main())
