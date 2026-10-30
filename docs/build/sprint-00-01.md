# Build guide · Sprint 0 and Sprint 1

**Sprint 0: Setup** (Fri 16 – Sun 18 Oct 2026) · **Sprint 1: Domain core** (Mon 19 – Sun 25 Oct 2026)

This chapter is the "how" for the first ten days. The spec ([`POLARIS-PROJECT-SPEC.md`](../../POLARIS-PROJECT-SPEC.md)) says *what* we build; this file says *which commands to type, which files to write, and how to prove each story is done*. Read the spec's §0.4 conventions, Part 2 (scoring) and §4.8 (code map) before you start a story here.

**Every code block in this chapter was run.** The Python files were assembled into a scratch Django 6.1.2 project, linted with the project's own Ruff rules, and the test suite (128 tests) passed with 99% coverage. One difference: that check used SQLite because Docker wasn't available, so run the suite once on Postgres (`docker compose up -d`) before merging S1-04, as the checklist says.

## Contents

- [Sprint 0 overview](#sprint-0-overview)
- [S0-01 · Protected repo, `develop` default, verified identities](#s0-01--protected-repo-develop-default-verified-identities)
- [S0-02 · GitHub Project, fields, views, milestones, backlog import](#s0-02--github-project-fields-views-milestones-backlog-import)
- [S0-03 · Django 6.1 skeleton with uv and split settings](#s0-03--django-61-skeleton-with-uv-and-split-settings)
- [S0-04 · Postgres and Redis with one command, on every laptop](#s0-04--postgres-and-redis-with-one-command-on-every-laptop)
- [S0-05 · CI green on every pull request](#s0-05--ci-green-on-every-pull-request)
- [S0-06 · Spec review, decisions D1–D15, TA email](#s0-06--spec-review-decisions-d1d15-ta-email)
- [Sprint 1 overview](#sprint-1-overview)
- [S1-01 · Custom User (email login) and ProgramMembership](#s1-01--custom-user-email-login-and-programmembership)
- [S1-02 · Catalog models with constraints and admin](#s1-02--catalog-models-with-constraints-and-admin)
- [S1-03 · Outcome models: LOs, assessments, both weight tables](#s1-03--outcome-models-los-assessments-both-weight-tables)
- [S1-04 · Grade, AuditEvent, `audit.record`, and the two job tables](#s1-04--grade-auditevent-auditrecord-and-the-two-job-tables)
- [S1-05 · Data migration: the CSE program and the 11 official POs](#s1-05--data-migration-the-cse-program-and-the-11-official-pos)
- [S1-06 · The scoring engine, test-first](#s1-06--the-scoring-engine-test-first)
- [S1-07 · Loaders: database → engine inputs](#s1-07--loaders-database--engine-inputs)
- [S1-08 · Factories, scenarios and shared fixtures](#s1-08--factories-scenarios-and-shared-fixtures)
- [S1-09 · Base template, design tokens, `|score`, components, login page](#s1-09--base-template-design-tokens-score-components-login-page)
- [S1-10 · `seed_demo` v1](#s1-10--seed_demo-v1)
- [End of Sprint 1: review, retro, evidence](#end-of-sprint-1-review-retro-evidence)
- [Code map additions](#code-map-additions)

### Branch names in this chapter

Branches are named after the **story ID**: `feature/S1-06-scoring-engine`, `feature/S2-05-weight-grids`. §0.4 of the spec says `feature/<issue#>-<slug>`; the team convention for the build guide is the story ID instead, because it is known before the issue exists, it reads the same in every chapter, and `git branch` then lines up with the board. The issue number still goes in every commit message and in `Closes #<issue>` in the PR description, so GitHub links them. (Update §0.4 to match in the S0-06 PR.)

---

# Sprint 0 overview

**Goal:** everyone can run the project locally, CI is green on a pull request, and the backlog exists on a board. No product code yet. Sprint 0 is three days long (Fri–Sun) and is mostly Person C.

| ID | Story | Pts | Owner | Needs |
|---|---|---|---|---|
| S0-01 | Repo: `develop` default, branch protection, git identities verified | 1 | C | — |
| S0-02 | GitHub Project: fields, views, templates, milestones, backlog imported | 2 | C | S0-01 |
| S0-03 | Django 6.1 skeleton with uv, apps, split settings, `.env` | 3 | C | S0-01 |
| S0-04 | Dev `compose.yml`; setup verified on all three laptops | 2 | A | S0-03 |
| S0-05 | CI workflow (lint, test, migrations check, deploy check) green | 3 | C | S0-03 |
| S0-06 | Spec read by all; D1–D15 accepted or changed; TA asked | 1 | A + all | — |

**Order.** Friday: S0-01, S0-06 (everyone reads). Saturday: S0-03 then S0-05 (C), S0-02 (C, in parallel while CI runs). Sunday: S0-04 on all three laptops, Sprint 1 planning meeting (60 min).

**What must work by Sunday 18 Oct 23:59**

- [ ] `uv run pytest` passes on all three laptops (one smoke test exists, see S0-03).
- [ ] A pull request into `develop` shows green `lint`, `test` and `deploy-check` checks, and cannot be merged without one approval.
- [ ] The board shows every Sprint 1 story in **Ready**, with points.
- [ ] The TA email about the 3-person team has been sent.
- [ ] `docs/process/velocity.md` has the Sprint 0 row.

## S0-01 · Protected repo, `develop` default, verified identities

**Points:** 1 · **Owner:** Person C · **Branch:** none (repository settings) · **Depends on:** —

### Goal

The repository already exists: <https://github.com/OnurHaniffa/polaris>, public, default branch `develop`, with `main` holding the first commit (spec + README) and both teammates invited with write access. This story finishes the job. It locks `main` and `develop` so that nobody can push to them directly, sets the merge buttons to match our merge strategy (spec §9.6), and makes sure every commit counts in the contributor charts that report Section 3 needs.

### Files

| Path | Create / modify | What |
|---|---|---|
| `scripts/protect_branches.sh` | create | The branch protection rules as code, so we can re-apply them and show them in the report |

### Steps

**1. Everyone: accept the invite and check your Git identity.** GitHub only credits a commit to you when the commit's author email is an email verified on your GitHub account. A typo here means your work disappears from the contributor graph, and that graph is graded. Do this before your first commit, not after.

```bash
# accept the invitation (or click the link in the email GitHub sent you)
gh api user/repository_invitations --jq '.[] | "\(.id) \(.repository.full_name)"'
gh api -X PATCH user/repository_invitations/<id-from-above>

# set your identity
git config --global user.name  "Your Name"
git config --global user.email "an-email-verified-on-your-github-account@example.com"

# check it: this email must appear in https://github.com/settings/emails as Verified
git config --global user.email
```

If you use GitHub's private `…@users.noreply.github.com` address, use that exact address. Both work; a third, unverified address does not.

**2. Person C: set the merge buttons.** Squash merges for features keep `develop` at one commit per story. Merge commits for `develop → main` keep the release points visible. Rebase merges would give us a third style, so we turn them off. Deleting the branch on merge keeps the branch list short.

```bash
gh repo edit OnurHaniffa/polaris \
  --enable-squash-merge --enable-merge-commit --enable-rebase-merge=false \
  --delete-branch-on-merge --enable-auto-merge
```

**3. Person C: protect `main` and `develop`.** The rules are those of spec §9.6: a pull request, one approval, stale approvals dismissed, CI checks green, branch up to date, no force pushes, no deletions. We write them as a script instead of clicking through Settings, because then the rules are in Git, repeatable, and quotable in report Section 4.

`enforce_admins` is `false`. On a personal repository the owner (Onur) is an admin; leaving the escape hatch open means a broken CI can't lock us out of our own repo the night before a checkpoint. Using it is a team decision, logged in the sprint retro.

```bash
#!/usr/bin/env bash
# scripts/protect_branches.sh: apply branch protection to main and develop (spec §9.6).
# S0-01 runs it with no required checks (CI doesn't exist yet, and a required check that
# never runs would block every PR). S0-05 re-runs it with CHECKS="lint test deploy-check".
set -euo pipefail
REPO="OnurHaniffa/polaris"
CHECKS="${CHECKS:-}"

if [ -n "$CHECKS" ]; then
  contexts=$(printf '"%s",' $CHECKS)
  status_checks="{\"strict\": true, \"contexts\": [${contexts%,}]}"
else
  status_checks="null"
fi

for branch in main develop; do
  gh api -X PUT "repos/$REPO/branches/$branch/protection" --input - <<JSON
{
  "required_status_checks": $status_checks,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
  echo "protected $branch (required checks: ${CHECKS:-none yet})"
done
```

```bash
chmod +x scripts/protect_branches.sh
./scripts/protect_branches.sh
```

The script itself goes into the repo in the S0-03 pull request (the first PR, since nobody can push to `develop` any more).

**4. Person C: confirm `develop` is the default branch.** It already is. The check costs one command:

```bash
gh repo view OnurHaniffa/polaris --json defaultBranchRef --jq .defaultBranchRef.name   # develop
```

### Tests

Branch protection is tested by trying to break it:

```bash
git switch develop && git pull
git commit --allow-empty -m "This push must be rejected"
git push                       # expected: "protected branch hook declined"
git reset --hard origin/develop
```

### Check it works

- `git push` straight to `develop` or `main` is rejected (above).
- *Settings → Branches* shows two rules, for `main` and `develop`.
- *Settings → General → Pull Requests*: only "squash" and "merge commit" are ticked; "Automatically delete head branches" is on.
- Each teammate opens `https://github.com/settings/emails` and sees the email from `git config user.email` marked **Verified**.

### Done when

- [ ] Direct push to `develop` and `main` rejected (manual test above)
- [ ] Merge buttons match §9.6
- [ ] All three identities verified (each person ticks their own name in the issue)
- [ ] `scripts/protect_branches.sh` committed in the S0-03 PR

### Commits and PR

No PR of its own: the settings live on GitHub and the script rides along in S0-03. Close the issue by hand with a comment listing what you set.

---
## S0-02 · GitHub Project, fields, views, milestones, backlog import

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S0-02-backlog` (for the templates and script) · **Depends on:** S0-01

### Goal

Report Section 1 asks which backlog tool we use and why; Section 2 asks for sprints, points and velocity. Both are answered by the GitHub Project's history, but only if the board is set up correctly before the first story moves. This story creates the **POlaris Backlog** project with the fields from spec §9.3, imports all 76 backlog rows from Part 12 as issues, and adds the issue and PR templates.

### Files

| Path | Create / modify | What |
|---|---|---|
| `.github/ISSUE_TEMPLATE/user_story.yml` | create | Copy verbatim from spec §9.3 |
| `.github/ISSUE_TEMPLATE/bug.yml` | create | Bug template (below) |
| `.github/pull_request_template.md` | create | Copy verbatim from spec §9.3 |
| `scripts/import_backlog.py` | create | Reads Part 12 of the spec, creates issues, adds them to the board, sets the fields |
| `docs/process/velocity.md` | create | The velocity table, Sprint 0 row filled |

### Steps

**1. Give the GitHub CLI access to Projects.** `gh` logs in without the `project` scope by default.

```bash
gh auth refresh -h github.com -s project
gh auth status          # Token scopes must now include 'project'
```

**2. Create the project and link it to the repo.** A user-owned project (the repo belongs to a user account, not an organisation). Linking it makes it show up in the repo's *Projects* tab.

```bash
gh project create --owner OnurHaniffa --title "POlaris Backlog" --format json --jq .number
# prints the project number, e.g. 3. Use it below.
N=3
gh project link $N --owner OnurHaniffa --repo OnurHaniffa/polaris
```

Then make it visible to the teammates: open the project → **⋯ → Settings → Manage access → Invite collaborators** → add `Fatmaaa-Demir` and `ZeynepUygun05` with **Write**. (Repo collaborators do not automatically get write access to a user-owned project.)

**3. Create the custom fields.** Three single-selects and one number can be made from the CLI:

```bash
gh project field-create $N --owner OnurHaniffa --name "Points"   --data-type NUMBER
gh project field-create $N --owner OnurHaniffa --name "Area"     --data-type SINGLE_SELECT \
  --single-select-options "Engine & Data,Instructor,Platform & Insights,Process"
gh project field-create $N --owner OnurHaniffa --name "Tier"     --data-type SINGLE_SELECT \
  --single-select-options "Baseline,Tier 1,Tier 2,Tier 3,Chore"
gh project field-create $N --owner OnurHaniffa --name "Priority" --data-type SINGLE_SELECT \
  --single-select-options "P0,P1,P2"
```

Two fields need the web UI, because the CLI cannot create iterations or edit the built-in Status field:

- **Status** (built in, has Todo / In Progress / Done): open the project → any table view → click the **Status** column header → **⋯ → Edit field** (or *Settings → Fields → Status*). Rename *Todo* to **Backlog**, then add **Ready** after it and **In Review** before *Done*. Final order: Backlog · Ready · In Progress · In Review · Done.
- **Sprint** (iteration): *Settings → Fields → + New field* → name `Sprint`, type **Iteration**, duration **1 week**, starts **Mon 19 Oct 2026**. GitHub creates "Sprint 1, Sprint 2, …". Then click **Add iteration** → **More options** and add a 3-day iteration **Sprint 0** on Fri 16 – Sun 18 Oct (spec §9.3).

**4. Views.** Rename the default view and add three more (*+ New view* next to the tabs):

| View | Layout | Settings |
|---|---|---|
| **Board** | Board | Column field: Status. Filter: `sprint:@current` |
| **Backlog** | Table | Sort: Priority ↑, then Tier ↑. Show fields: Points, Area, Tier, Priority, Sprint, Assignees, Milestone |
| **By person** | Table | Group by: Assignees. Filter: `sprint:@current`. Field sum: Points (click the group header ⋯ → *Show sum* on Points) |
| **Roadmap** | Roadmap | Date field: Sprint. Zoom: Month |

**5. Built-in workflows.** Project → **⋯ → Workflows**. Turn on: *Item added to project → Status: Backlog*; *Pull request merged → Status: Done*; *Item closed → Status: Done*. Turn on *Auto-add to project* with the filter `is:issue,pr repo:OnurHaniffa/polaris` so new issues land on the board without anyone remembering to add them.

**6. Templates.** Copy `user_story.yml` and `pull_request_template.md` from spec §9.3 unchanged. The bug template:

```yaml
# .github/ISSUE_TEMPLATE/bug.yml
name: Bug
description: Something on staging or production doesn't work as the spec says
labels: ["bug"]
body:
  - type: textarea
    id: what
    attributes:
      label: What happened
      placeholder: On /offerings/7/grades/ typing 105 saved the grade instead of showing an error.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: What should happen (link the spec section or AC)
      placeholder: "B6 AC1: Typing 105 in a column with max 100 shows 'Max for Midterm I is 100'."
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      value: |
        1. Log in as …
        2. Go to …
        3.
  - type: dropdown
    id: where
    attributes:
      label: Where
      options: [Local, Staging, Production]
    validations:
      required: true
```

**7. Import the backlog.** `scripts/import_backlog.py` reads the backlog table straight out of the spec, so the issues match Part 12 exactly. It creates the labels and the four milestones, then one issue per row, adds each issue to the board and sets Points, Area, Tier and Priority. It does **not** set Sprint (iteration IDs are awkward to reach from the CLI); you do that in step 8 in two minutes. It is safe to re-run: rows whose title already exists are skipped.

How it decides the derived fields, so you can defend them:

| Field | Rule |
|---|---|
| Label | `chore` for Tier = Chore, `spike` when the story text says "(spike)", otherwise `story` |
| Area | Process-type features (Process, CSE 311/321, Demo, Reports, Release) → *Process*; otherwise by owner: A → Engine & Data, B → Instructor, C → Platform & Insights; unowned extras → left empty |
| Priority | Baseline, and chores up to Sprint 3 → P0; Tier 1 and later chores → P1; Tier 2/3 and unscheduled → P2 |
| Milestone | Sprints 0–4 → *CSE 321 checkpoint* (12 Nov), 5 → *CSE 311 checkpoint* (17 Nov), 6–7 → *Feature complete* (6 Dec), 8+ and unscheduled → *Final demo* (29 Dec) |

**`scripts/import_backlog.py`**

```python
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
```

Run it as a dry run first and read the output. It should say `76 backlog rows, 254 points` and list one line per issue.

```bash
uv run python scripts/import_backlog.py            # dry run
uv run python scripts/import_backlog.py --apply    # about 3 minutes: ~380 gh calls
```

> The script runs inside the uv environment only because that's where Python is; it imports nothing from Django. Before S0-03 has merged you can run it with `python3 scripts/import_backlog.py`.

**8. Set the Sprint field and owners.** In the **Backlog** view, type `S1-` in the filter bar, select all rows (click the first row number, Shift-click the last), and set Sprint → *Sprint 1* in one go. Repeat for `S0-` and `S2-`; later sprints are set at their planning meeting. Then assign Sprint 0–1 issues to their owner (A / B / C from spec §0.3).

**9. Velocity file.**

```markdown
<!-- docs/process/velocity.md -->
# Velocity

Velocity = points of stories that met the Definition of Done by Sunday 23:59 (spec §9.5).

| Sprint | Dates | Forecast | Committed | Completed | Carried over | Notes |
|---|---|---|---|---|---|---|
| 0 | 16–18 Oct | – | 12 | | | setup |
| 1 | 19–25 Oct | 24 | 28 | | | first real sprint; forecast is a guess |
```

### Tests

`scripts/` is outside `apps/`, so it is not in the coverage gate. The dry run is the test: its output must list 76 rows, 254 points, and no title starting with "As …".

### Check it works

- The project's **Board** view shows the Sprint 1 issues in *Backlog*; at the planning meeting you drag the ones you commit to into *Ready*.
- Opening any issue shows the four fields filled in the right-hand panel.
- Creating a test issue in the repo puts it on the board automatically in *Backlog* (then close it).

### Done when

- [ ] Project with Status (5 options), Sprint (iteration), Points, Area, Tier, Priority
- [ ] Four views and three workflows on; both teammates can edit the project
- [ ] 76 issues, each on the board with fields set; Sprint 0–1 issues have Sprint and assignee
- [ ] Issue templates, PR template and `velocity.md` merged

### Commits and PR

```
Add issue and pull request templates
Add backlog import script that reads Part 12 of the spec
Start the velocity log with Sprint 0
```

PR title: `S0-02: GitHub Project setup, templates and backlog import (#<issue>)`

---
## S0-03 · Django 6.1 skeleton with uv and split settings

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S0-03-skeleton` · **Depends on:** S0-01

### Goal

Turn the repo (currently: spec, README, `.gitignore`) into a Django 6.1 project that every teammate can run with three commands. It has the eight apps from spec §4.3, settings split by environment, secrets from `.env`, and **the custom `User` model with its first migration**. One smoke test keeps `pytest` green.

> **Why the `User` model is in Sprint 0 (a change from the spec).** Spec §11 says "`AUTH_USER_MODEL` goes in now even though the model is written in Sprint 1". That doesn't work: Django refuses to start (`ImproperlyConfigured: AUTH_USER_MODEL refers to model 'accounts.User' that has not been installed`) the moment the setting points at a model that doesn't exist, so `check`, `runserver` and `pytest` would all fail for a week. We tested this. So S0-03 adds the `User` class and its `0001` migration, and S1-01 adds `ProgramMembership` on top. The rule behind the spec's note still holds: **the custom user model exists before anyone runs `migrate` for the first time.**

### Files

| Path | Create / modify | What |
|---|---|---|
| `pyproject.toml`, `uv.lock`, `.python-version` | create | Written by `uv`; we add the `[tool.*]` sections by hand |
| `manage.py`, `config/wsgi.py`, `config/asgi.py` | create (generated) + modify | Default settings module per entry point |
| `config/settings/{__init__,base,dev,test,prod}.py` | create | The split settings |
| `config/celery.py`, `config/__init__.py` | create | Celery app (tasks run inline until Sprint 5) |
| `config/urls.py` | create | Admin + `/healthz` |
| `apps/<8 apps>/` | create (generated) + modify | `apps.py` names fixed, `tests/` packages, generated `tests.py` removed |
| `apps/accounts/models.py` + `migrations/0001_initial.py` | create | `User` and `UserManager` (spec §5.2) |
| `apps/accounts/tests/test_models.py` | create | User model tests |
| `apps/core/views.py`, `apps/core/tests/test_views.py` | create | Health check and its tests |
| `.env.example`, `.gitignore`, `.pre-commit-config.yaml` | create / modify | Spec §10.3 |
| `static/`, `templates/` | create | Empty, with `.gitkeep` |
| `scripts/protect_branches.sh` | create | From S0-01 |
| `README.md` | modify | Setup section |

### Steps

**1. Clone and branch.** The repo exists already, so this is a clone, not `git init`.

```bash
git clone https://github.com/OnurHaniffa/polaris.git && cd polaris
git switch -c feature/S0-03-skeleton
```

**2. Python project with uv.** `uv init --bare` writes only a `pyproject.toml` (no sample code). `uv python pin` writes `.python-version`, which makes every `uv run` use 3.13 even on a laptop that has 3.14 installed: without it uv picks the newest Python it finds, and we hit exactly that while testing this guide.

```bash
uv init --bare --python 3.13
uv python pin 3.13
uv add "django~=6.1" "psycopg[binary]~=3.3" django-environ "celery[redis]~=5.6" \
       django-htmx anthropic pydantic openpyxl python-docx pillow weasyprint \
       whitenoise gunicorn
uv add --dev pytest pytest-django pytest-cov factory-boy hypothesis faker \
       ruff pre-commit django-debug-toolbar pytest-playwright
uv run python -V          # Python 3.13.x
uv run django-admin --version   # 6.1.x
```

`uv.lock` now records the exact version of every package. Commit it: it is what makes "works on my machine" mean the same machine for all three of us.

**3. Project and apps.**

```bash
uv run django-admin startproject config .
mkdir -p apps && touch apps/__init__.py
for app in core accounts catalog outcomes grading scoring ingestion reports; do
  mkdir apps/$app && uv run python manage.py startapp $app apps/$app
  # Django writes name = 'core'; inside apps/ it must be 'apps.core'
  sed -i.bak "s/name = '$app'/name = 'apps.$app'/" apps/$app/apps.py && rm apps/$app/apps.py.bak
  # tests live in a package (apps/<app>/tests/test_*.py), not one tests.py
  rm apps/$app/tests.py && mkdir apps/$app/tests && touch apps/$app/tests/__init__.py
  # empty the generated stubs: their unused imports would fail ruff (F401)
  : > apps/$app/models.py; : > apps/$app/views.py; : > apps/$app/admin.py
done
mkdir -p config/settings static/css static/js static/vendor templates/includes scripts
git rm -q --cached config/settings.py 2>/dev/null; rm config/settings.py
touch config/settings/__init__.py static/css/.gitkeep static/js/.gitkeep \
      static/vendor/.gitkeep templates/includes/.gitkeep
```

(`sed -i.bak … && rm *.bak` is the form that works on both macOS and Linux/WSL.)

**4. Settings.** One base file plus one small file per environment. `base.py` reads every secret and every machine-specific value from environment variables (via `django-environ`, which also loads `.env`), so the same code runs on a laptop, in CI and on the server.

Two choices worth knowing, because you'll be asked:

- `LOGIN_URL = "accounts:login"` is namespaced (spec §4.8 puts every URL in a namespace). The spec's §10.3 has `"login"`, which would not resolve. The login page itself arrives in S1-09; nothing redirects to it before then.
- Email uses **`MAILERS`**, not `EMAIL_BACKEND`. Django 6.1 deprecated `EMAIL_BACKEND` and the other `EMAIL_*` settings; using them prints a `RemovedInDjango2028Warning` on every test run. The spec's §10.3 still shows the old setting; this guide is the corrected version.

**`config/settings/base.py`**

```python
"""Settings shared by every environment. Secrets and anything that differs per machine come
from environment variables (read from .env locally), never from this file."""

from pathlib import Path

import environ

# settings/ → config/ → repo root: three .parent calls, not two as in the generated file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.outcomes",
    "apps.grading",
    "apps.scoring",
    "apps.ingestion",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {"default": env.db("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"  # BEFORE the first migrate. Never change later.
LOGIN_URL = "accounts:login"  # the view arrives in S2-01; nothing redirects to it before then
LOGIN_REDIRECT_URL = "home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

CELERY_BROKER_URL = env("REDIS_URL")
CELERY_TASK_ACKS_LATE = True  # a crashed worker's task is redelivered
CELERY_TASK_TIME_LIMIT = 15 * 60

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-opus-5-5")
# ANTHROPIC_API_KEY is read by the SDK directly from the environment
```

**`config/settings/dev.py`**

```python
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# Django 6.1 configures email with MAILERS (EMAIL_BACKEND is deprecated). Dev prints emails.
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]
# run Celery tasks inline (no worker needed) until Sprint 5
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=True)  # noqa: F405
```

**`config/settings/test.py`**

```python
from .base import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
```

`prod.py` turns `EMAIL_URL` (a single URL like `smtp+tls://user:password@smtp.provider.com:587`, easy to keep in one secret) into the `MAILERS` dict:

**`config/settings/prod.py`**

```python
from .base import *  # noqa: F403

DEBUG = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Caddy terminates HTTPS
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600  # raise to 1 year once everything works
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SILENCED_SYSTEM_CHECKS = ["security.W021"]  # HSTS preload: not for a student project domain
# EMAIL_URL like smtp+tls://user:password@smtp.provider.com:587 → Django 6.1 MAILERS
_email = env.email_url("EMAIL_URL")  # noqa: F405
_options = {}
if _email["EMAIL_BACKEND"].endswith("smtp.EmailBackend"):
    _options = {
        "host": _email["EMAIL_HOST"],
        "port": _email["EMAIL_PORT"],
        "username": _email["EMAIL_HOST_USER"],
        "password": _email["EMAIL_HOST_PASSWORD"],
        "use_tls": _email.get("EMAIL_USE_TLS", False),
        "use_ssl": _email.get("EMAIL_USE_SSL", False),
    }
MAILERS = {"default": {"BACKEND": _email["EMAIL_BACKEND"], "OPTIONS": _options}}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="POlaris <noreply@example.com>")  # noqa: F405
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,  # keep Django's own loggers (500 tracebacks)
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

**5. Celery wiring.** Nothing uses Celery until Sprint 5, but wiring it now means the import path is stable and `CELERY_TASK_ALWAYS_EAGER` in dev/test runs any task inline (no worker, no Redis queue needed).

**`config/celery.py`**

```python
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
app = Celery("polaris")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

**`config/__init__.py`**

```python
from .celery import app as celery_app

__all__ = ("celery_app",)
```

**6. Entry points.** `manage.py` is what you run on your laptop, so it defaults to dev settings. `wsgi.py` and `asgi.py` are only used by gunicorn on the server, so they default to prod. Change the one `setdefault` line in each:

```python
# manage.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
# config/wsgi.py and config/asgi.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
```

**7. The `User` model.** Copy the `User` and `UserManager` part of spec §5.2 (not `ProgramMembership`: it points at `catalog.Program`, which doesn't exist until S1-02). Email is the login; `username` is removed. `student_number` is unique but nullable, because staff don't have one, and the database allows many NULLs in a unique column.

```python
# apps/accounts/models.py (S0-03 version; S1-01 adds ProgramMembership below it)
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Identity only. What someone *is* lives in ProgramMembership (decision D6)."""

    username = None
    email = models.EmailField(unique=True)
    student_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    objects = UserManager()

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"
```

**8. Health check and URLs.** `/healthz` is what Docker, Caddy and the CD smoke test ping (spec §10.3). It's the only view in Sprint 0.

```python
# apps/core/views.py (S0-03 version; S1-09 adds home and styleguide)
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Used by Docker, Caddy and the CD smoke test (spec §10.3). Public, no login."""
    status = {"db": "ok", "cache": "ok"}
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001
        status["db"] = "down"
    try:
        cache.set("healthz", "1", 5)
    except Exception:  # noqa: BLE001
        status["cache"] = "down"
    code = 200 if all(v == "ok" for v in status.values()) else 503
    return JsonResponse(status, status=code)
```

```python
# config/urls.py (S0-03 version)
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
```

**9. Tool configuration.** Append to `pyproject.toml` (below what `uv add` wrote). Two differences from spec §10.3, both found by running the checks: `S105` joins the test ignores (factories define a test password constant), and `filterwarnings` hides a harmless WhiteNoise warning about the `staticfiles/` folder, which tests never build.

```toml
[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = ["*/migrations/*"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "DJ", "S", "SIM"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101", "S105", "S106"]  # assert and hard-coded test passwords are fine in tests

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "-ra --strict-markers"
filterwarnings = [
    # WhiteNoise looks for collected static files, which tests never build
    "ignore:No directory at:UserWarning",
]

[tool.coverage.run]
source = ["apps"]
branch = true
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
skip_covered = true
```

**10. Environment files, pre-commit.** Copy `.env.example` and `.pre-commit-config.yaml` from spec §10.3 unchanged, and append the spec's `.gitignore` additions (`*.sqlite3`, `.coverage`, `coverage.xml`, `junit.xml`) to the `.gitignore` already in the repo. Then:

```bash
cp .env.example .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))" >> .env
# delete the old SECRET_KEY=dev-only-change-me line from .env so the new one wins
uv run pre-commit install
```

**11. Format, migrate, run.** Postgres must be running for `migrate`: if S0-04 hasn't merged, copy `compose.yml` from spec §10.3 now (it's four lines of work to merge later).

```bash
uv run ruff check --fix . && uv run ruff format .     # tidy the generated files (quotes etc.)
docker compose up -d
uv run python manage.py makemigrations accounts       # → apps/accounts/migrations/0001_initial.py
uv run python manage.py migrate
uv run python manage.py check                          # System check identified no issues
uv run python manage.py runserver                      # http://localhost:8000/healthz → {"db": "ok", "cache": "ok"}
```

**12. README setup section.** Replace the last line of `README.md` ("Setup instructions arrive…") with the teammate setup block from spec §10.4 (minus `seed_demo`, which arrives in S1-10).

### Tests

A test suite with zero tests makes `pytest` exit with code 5 ("no tests collected"), and CI treats that as a failure. The spec's Sprint 0 checkpoint says "`uv run pytest` passes… even with zero tests": it won't. So the skeleton ships with real tests for the two things that exist.

```python
# apps/core/tests/test_views.py (S0-03 version; S1-09 adds login and home tests)
import pytest

pytestmark = pytest.mark.django_db


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"db": "ok", "cache": "ok"}


def test_healthz_reports_a_dead_cache(client, monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr("apps.core.views.cache.set", broken)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["cache"] == "down"
```

**`apps/accounts/tests/test_models.py`**

```python
import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_login_field_is_email():
    assert User.USERNAME_FIELD == "email"
    assert not hasattr(User, "username") or User.username is None


def test_create_user_normalises_email_and_hashes_password():
    user = User.objects.create_user("Elif@LIVE.acibadem.edu.tr", "s3cret-pass", first_name="Elif")
    assert user.email == "Elif@live.acibadem.edu.tr"  # domain part lower-cased
    assert user.check_password("s3cret-pass")
    assert not user.is_staff and not user.is_superuser
    assert str(user) == "Elif <Elif@live.acibadem.edu.tr>"


def test_email_is_required():
    with pytest.raises(ValueError, match="Email is required"):
        User.objects.create_user("", "pw")


def test_create_superuser():
    admin = User.objects.create_superuser("admin@example.com", "pw")
    assert admin.is_staff and admin.is_superuser


def test_email_unique():
    User.objects.create_user("a@example.com", "pw")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("a@example.com", "pw")


def test_student_number_unique_but_optional():
    User.objects.create_user("x@example.com", "pw")
    User.objects.create_user("y@example.com", "pw")  # two NULL student numbers are fine
    User.objects.create_user("s1@example.com", "pw", student_number="2023-0001")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("s2@example.com", "pw", student_number="2023-0001")
```

```bash
uv run pytest --cov          # 8 passed; coverage above 85%
```

### Check it works

- `curl -s localhost:8000/healthz` → `{"db": "ok", "cache": "ok"}`. Stop Redis (`docker compose stop redis`) and repeat: `{"db": "ok", "cache": "down"}` with status 503. Start it again.
- `uv run python manage.py createsuperuser` asks for **Email**, first name, last name: no username. Log in at `/admin/` (the User model isn't registered in the admin until S1-01, so you'll only see Groups).
- `git commit` on any file runs Ruff automatically (pre-commit).

### Done when

- [ ] `uv sync && uv run pytest` passes on a fresh clone
- [ ] `manage.py check` clean with dev settings; `check --deploy` clean with prod settings (S0-05 automates this)
- [ ] `AUTH_USER_MODEL = "accounts.User"` and `accounts/0001_initial.py` committed together
- [ ] No secret in Git (`git grep -n SECRET_KEY` only shows settings and `.env.example`)

### Commits and PR

```
Bootstrap Django 6.1 project with uv and eight apps
Split settings into base/dev/test/prod and read secrets from .env
Add the email-based User model before the first migration
Add health check endpoint with tests
Add ruff, pytest and pre-commit configuration
```

PR title: `S0-03: Django 6.1 skeleton with split settings and email User (#<issue>)`. This is the first PR: everyone reviews it, because everyone builds on it.

---
## S0-04 · Postgres and Redis with one command, on every laptop

**Points:** 2 · **Owner:** Person A · **Branch:** `feature/S0-04-compose` · **Depends on:** S0-03

### Goal

`docker compose up -d` gives every laptop the same PostgreSQL 17 and Redis 7 that CI and production use, and the full teammate setup (spec §10.4) is proven on all three machines before Sprint 1 starts. Django itself runs outside Docker locally: instant reload, and the debugger works.

### Files

| Path | Create / modify | What |
|---|---|---|
| `compose.yml` | create | Copy from spec §10.3 (if S0-03 already added it, review it here instead) |
| `docs/process/setup-check.md` | create | One row per laptop: OS, chip, versions, result |

### Steps

**1. `compose.yml`.** Copy it from spec §10.3. The `pgdata` named volume keeps your database between restarts; `docker compose down -v` deletes it (that's the "reset my database" button).

**2. Each person runs the teammate setup** from spec §10.4 on their own laptop, on `develop` after S0-03 has merged:

```bash
git clone https://github.com/OnurHaniffa/polaris.git && cd polaris
uv sync
cp .env.example .env
docker compose up -d
docker compose ps                 # db "healthy", redis "running"
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run pre-commit install
uv run pytest
```

**3. Record the result** in `docs/process/setup-check.md`:

```markdown
# Setup check (Sprint 0)

| Person | OS / chip | `uv --version` | `docker compose version` | `uv run pytest` | Notes |
|---|---|---|---|---|---|
| A | macOS 26 / M3 | 0.13.x | v2.x | 8 passed | |
| B | Windows 11 + WSL2 Ubuntu 24.04 | | | | |
| C | | | | | |
```

### Troubleshooting (add to it when you hit something new)

| Symptom | Cause | Fix |
|---|---|---|
| `port 5432 is already allocated` / `address already in use` | A Postgres installed with Homebrew or Postgres.app is running | `brew services stop postgresql@17` (or quit Postgres.app). Or change the left side of the port in `compose.yml` to `5433:5432` **and** the port in your `.env` `DATABASE_URL` |
| `connection refused` on migrate | Containers not started, or Docker Desktop not running | Start Docker Desktop, `docker compose up -d`, wait for `healthy` |
| `password authentication failed for user "polaris"` | The volume was created earlier with other credentials | `docker compose down -v && docker compose up -d` (deletes local data) |
| `Error 61 connecting to localhost:6379` in the healthz test | Redis container not running | `docker compose up -d redis` |
| Windows: scripts fail with `\r` errors | Repo cloned on the Windows side with CRLF line endings | Clone inside WSL (`~/code/polaris`), not under `/mnt/c/…`. Run `git config --global core.autocrlf input` |
| `uv run` uses Python 3.14 | `.python-version` missing | It is committed in S0-03; `git pull` |

### Tests

The setup check *is* the test: three rows in `setup-check.md` with `uv run pytest` green.

### Check it works

`uv run python manage.py dbshell` opens `psql` connected to `polaris` (type `\dt` to see the tables, `\q` to leave).

### Done when

- [ ] Three rows filled in, all green
- [ ] Any new problem added to the troubleshooting table above (edit this guide in the same PR)

### Commits and PR

```
Add dev compose file for Postgres 17 and Redis 7
Record the Sprint 0 setup check on all three laptops
```

PR title: `S0-04: Dev services with Docker Compose, verified on all laptops (#<issue>)`

---

## S0-05 · CI green on every pull request

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S0-05-ci` · **Depends on:** S0-03

### Goal

Every pull request is linted, tested on a real PostgreSQL, checked for missing migrations and checked against Django's production checklist, automatically. From the end of this story, the branch rules require those checks, so nothing red reaches `develop`. Report Section 5 shows this YAML and its run history.

### Files

| Path | Create / modify | What |
|---|---|---|
| `.github/workflows/ci.yml` | create | Spec §9.9, with the two changes below |

### Steps

**1. Copy `.github/workflows/ci.yml` from spec §9.9, then make two changes.** Both were found by running the jobs against this skeleton.

*Change 1: leave out the `docker-build` job for now.* It builds the `Dockerfile`, which doesn't exist until S2-08 (spec §10.5). A job that can only fail would block every PR. Delete the whole `docker-build:` block; S2-08 adds it back together with the `Dockerfile`.

*Change 2: give `deploy-check` an SMTP email URL.* With Django 6.1's `MAILERS`, `check --deploy` reports `mail.E001` (an **error**, not a warning) when the production mailer is a development backend such as the console. The spec's `EMAIL_URL: consolemail://` therefore fails the job. Use a dummy SMTP URL; nothing is ever sent from a `check`:

```yaml
  deploy-check:
    runs-on: ubuntu-latest
    env:
      DJANGO_SETTINGS_MODULE: config.settings.prod
      SECRET_KEY: ci-only-but-long-enough-to-pass-the-deploy-check-0123456789abcdef
      DATABASE_URL: sqlite:////tmp/check.db
      REDIS_URL: redis://localhost:6379/0
      ALLOWED_HOSTS: example.com
      CSRF_TRUSTED_ORIGINS: https://example.com
      EMAIL_URL: smtp+tls://ci:ci@smtp.example.com:587     # was consolemail:// (fails mail.E001)
```

Everything else in the spec's file stays as it is: `lint` (Ruff check + format check), `test` (Postgres 17 and Redis 7 service containers, `manage.py check`, `makemigrations --check --dry-run`, pytest with coverage, coverage summary on the run page, reports uploaded as an artifact).

**2. Open the PR and watch it run.**

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI workflow: lint, tests on Postgres, migration and deploy checks"
git push -u origin feature/S0-05-ci
gh pr create --base develop --fill
gh pr checks --watch          # lint ✓  test ✓  deploy-check ✓
```

**3. Prove it can fail.** Push a commit to the same branch that breaks a test (change `== 200` to `== 201` in `test_healthz`), watch `test` go red and the merge button go grey, then revert it. Take a screenshot of the red run for `docs/process/sprint-00/`: a CI that has never been seen failing is not evidence of anything.

**4. Make the checks required.** Only after the checks have run once (GitHub needs to have seen their names):

```bash
CHECKS="lint test deploy-check" ./scripts/protect_branches.sh
```

### Tests

The workflow is its own test: a green run on the PR, plus the deliberate red run from step 3.

### Check it works

- The PR's *Checks* tab shows three jobs; the `test` job's summary page shows the coverage table.
- *Settings → Branches → develop* lists `lint`, `test`, `deploy-check` as required.

### Done when

- [ ] Three green checks on this PR; one deliberate red run screenshotted
- [ ] Checks required on `main` and `develop`
- [ ] Note in the PR description that `docker-build` returns in S2-08

### Commits and PR

```
Add CI workflow: lint, tests on Postgres, migration and deploy checks
Use an SMTP URL in deploy-check (console mailer fails mail.E001 on 6.1)
```

PR title: `S0-05: CI on every pull request (#<issue>)`

---

## S0-06 · Spec review, decisions D1–D15, TA email

**Points:** 1 · **Owner:** Person A (Product Owner) + everyone · **Branch:** `feature/S0-06-decisions` · **Depends on:** —

### Goal

Everyone has read spec Parts 0–3 and either accepted each decision D1–D15 or raised it. The TA has been asked, in writing, whether a 3-person team is accepted (the guidelines say exactly four, and a team without a valid registration scores zero: risk R1).

### Steps

**1. Read** (about 90 minutes each): Part 0, Part 1, Part 2, Part 3, §4.4, §4.8. Skim the rest.

**2. Decision meeting** (Sunday, 30 minutes, before Sprint 1 planning). Go down the D1–D15 table in §0.2. For each: accept (tick it in the spec), or change it (edit the spec in this PR, and add a line to Appendix C, the change log).

**3. Email the TA** (Person A, Friday or Saturday). Save the sent email and the reply as `docs/process/ta-team-size.md`.

```text
To: Doruk.Duz@live.acibadem.edu.tr
Subject: CSE 311/321 team project: confirming a 3-person team (POlaris)

Dear Doruk Hocam,

Our team registered for the CSE 311 / CSE 321 project on 13 October with three members:
<Name A>, <Name B> and <Name C>. The guidelines say teams have exactly four members, so
we would like to confirm in writing that our three-person team is accepted.

If it is not, could you let us know the process for joining or forming a four-person
team before Sprint 1 starts on Monday 19 October?

Repository: https://github.com/OnurHaniffa/polaris

Thank you,
<Name A>, on behalf of the team
```

**4. Sprint 1 planning** (Sunday, 60 minutes, Scrum Master runs it): planning poker on every Sprint 1 story (spec §9.4), record the first-round spread in each issue, drag the committed stories to *Ready*, fill the Sprint 1 row of `velocity.md`.

### Done when

- [ ] D1–D15 ticked or changed in the spec (changes logged in Appendix C)
- [ ] TA email sent; `docs/process/ta-team-size.md` exists (reply pasted in when it comes)
- [ ] Sprint 1 stories estimated and in *Ready*

### Commits and PR

```
Record team decisions D1–D15 from the Sprint 0 review
Save the team-size question sent to the TA
```

PR title: `S0-06: Spec decisions accepted, TA asked about team size (#<issue>)`

---
# Sprint 1 overview

**Goal:** the whole data model exists, the 11 official POs are seeded, and the engine reproduces the professor's numbers *from the database*. By Sunday this works in the Django shell:

```python
>>> from apps.accounts.models import User
>>> from apps.scoring.engine import compute_student_profile, display
>>> from apps.scoring.loaders import load_student_inputs
>>> elif_ = User.objects.get(student_number="2024-0041")
>>> profile = compute_student_profile(load_student_inputs(elif_))
>>> {po: display(s.score) for po, s in sorted(profile.po_scores.items())}
{1: '85.0', 2: '82.9', 3: '—'}
```

(The keys are database ids of PO 1, 2 and 3; on a fresh database they are 1, 2 and 3.)

| ID | Story | Pts | Owner | Needs |
|---|---|---|---|---|
| S1-01 | `ProgramMembership` (one person, several roles) + user admin | 3 | C | S1-02 |
| S1-02 | Catalog models with constraints + admin | 3 | A | S0-03 |
| S1-03 | Outcome models (LO, Assessment, both weight tables) + admin | 3 | B | S1-02 |
| S1-04 | `Grade` (draft/published) + `AuditEvent` + `audit.record` + `IngestionJob` + `ExportJob` | 2 | B | S1-03 |
| S1-05 | Data migration: CSE program + official 11 POs | 1 | A | S1-02 |
| S1-06 | Scoring engine, test-first: golden, policy and property tests | 5 | A | S0-03 |
| S1-07 | Loaders: ORM → `OfferingInputs` (P4 published only, P9 retakes, P10 open terms, P13 PO set) | 3 | A | S1-04, S1-08 |
| S1-08 | Factories for every model, `elif_scenario()`, shared fixtures | 2 | B | S1-04 |
| S1-09 | Base template, design tokens, `|score` filter, components, login page | 3 | C | S0-03 |
| S1-10 | `seed_demo` v1: 3 terms, 4 courses, 30 students, Elif's slide example | 3 | B | S1-05, S1-07 |

**28 points** planned against a guessed velocity of 24 (spec Part 12). If Wednesday's stand-up shows we're behind, S1-10 and S1-09 move to Sprint 2 first.

### Merge order (this matters for migrations)

Models in different apps point at each other, and a migration can only be generated once the models it points at have a migration on `develop`. Generating them out of order produces migrations that depend on files that don't exist yet.

```
day 1–2   S1-02 catalog ──────────────┬──► S1-01 membership (accounts/0002)
          S1-06 engine (no DB)        ├──► S1-05 data migration (catalog/0002)
          S1-09 templates (no models) └──► S1-03 outcomes ──► S1-04 grading, core, ingestion, reports
day 3–5                                                         │
                                                                ▼
day 5–6                                              S1-08 factories ──► S1-07 loaders ──► S1-10 seed
```

**Rule for everyone:** you can write your model code before its dependencies merge, but **don't run `makemigrations` until they're on `develop`**. Then: `git switch develop && git pull && git switch - && git rebase develop && uv run python manage.py makemigrations <your app>`. Only the owner of an app ever creates migrations in it, so two people never produce two `0002_…` files in the same app. If it happens anyway, delete yours, rebase, and generate it again.

> **Reset your local database** whenever a teammate's migration conflicts with a half-finished one of yours: `docker compose down -v && docker compose up -d && uv run python manage.py migrate`.

### Lint-clean models (a change from the spec)

The model code in spec §5.2 fails our own lint configuration: about 30 lines are longer than 100 characters (E501), and 13 models have no `__str__` (Ruff's DJ008). CI's `lint` job would reject the PR. The models in this chapter have **identical fields and constraints** to §5.2; the only differences are line wrapping, some trailing comments moved onto their own line, and a `__str__` on every model (the admin and error messages use it). `makemigrations --check` confirms the wrapping changes nothing in the database.

---
## S1-02 · Catalog models with constraints and admin

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S1-02-catalog` · **Depends on:** S0-03 · **Merge first in Sprint 1**

### Goal

Programs, versioned PO sets, POs, terms, catalog courses, offerings and enrollments exist as tables, with the integrity rules from spec §5.2 enforced **by PostgreSQL**, not just by forms: one active PO set per program (a partial unique index), PO numbers unique per set, term end after start, one enrollment per student per offering. Every model is in the admin. This delivers the storage half of B2 and B3; the screens come in Sprint 2.

This story also starts `apps/core/tests/factories.py`, the test-data builders everyone uses from now on (spec §9.8). Each model story adds the factories for its own models, so tests can be written in the same PR as the models. S1-08 then builds the ready-made scenarios on top.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/catalog/models.py` | create | 7 models (§5.2, lint-clean) |
| `apps/catalog/migrations/0001_initial.py` | create (generated) | |
| `apps/catalog/admin.py` | create | All 7 models registered |
| `apps/core/tests/factories.py` | create | `UserFactory` and the catalog factories |
| `apps/catalog/tests/test_models.py` | create | One test per constraint |

### Steps

**1. Models.** Field for field what §5.2 says. Things to understand before you type it, because they come up at the CSE 321 checkpoint:

- **`ProgramOutcomeSet` is versioned.** Curricula change; a student keeps the PO set of their cohort (policy P13). `is_active` marks the one the department uses for new mappings, and `one_active_po_set_per_program` is a **partial unique index**: unique on `program`, but only among rows where `is_active = true`. PostgreSQL enforces it with `CREATE UNIQUE INDEX … WHERE is_active`. Two inactive sets are fine; two active ones are impossible, even if two heads click "activate" at the same moment.
- **`on_delete` choices are deliberate.** `Course → Program` and `CourseOffering → Course/Term` are `PROTECT`: deleting a course that has offerings must fail loudly, not silently delete years of grades. `Enrollment → CourseOffering` is `CASCADE` (an enrollment means nothing without its offering) but `Enrollment → student` is `PROTECT` (deleting a user who has grades must fail).
- **`Decimal` for credits and the attainment threshold**, never `float` (§0.4).
- **`__str__`** on each model, used by the admin and error messages. `CourseOffering.__str__` touches `course` and `term`, so list pages must `select_related` them (the admin below does).

**`apps/catalog/models.py`**

```python
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Program(models.Model):
    code = models.CharField(max_length=16, unique=True)  # "CSE"
    # "Computer Science and Engineering"
    name = models.CharField(max_length=200)
    attainment_threshold = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("60")
    )

    def __str__(self):
        return self.code


class ProgramOutcomeSet(models.Model):
    """A versioned list of POs. Curricula change; students keep the set of their cohort."""

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="po_sets")
    label = models.CharField(max_length=100)  # "2023 curriculum"
    effective_from_year = models.PositiveSmallIntegerField()  # first cohort it applies to
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["program", "label"], name="uniq_po_set_label"),
            # partial unique index: at most one active set per program
            models.UniqueConstraint(
                fields=["program"],
                condition=Q(is_active=True),
                name="one_active_po_set_per_program",
            ),
        ]

    def __str__(self):
        return f"{self.program} · {self.label}"


class ProgramOutcome(models.Model):
    po_set = models.ForeignKey(ProgramOutcomeSet, on_delete=models.CASCADE, related_name="outcomes")
    number = models.PositiveSmallIntegerField()  # 1..11
    short_name = models.CharField(max_length=80)  # "Teamwork"
    description = models.TextField()  # official wording

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["po_set", "number"], name="uniq_po_number"),
            models.CheckConstraint(
                condition=Q(number__gte=1) & Q(number__lte=30), name="po_number_range"
            ),
        ]

    def __str__(self):
        return f"PO {self.number}"


class Term(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    code = models.CharField(max_length=10, unique=True)  # "2026F"
    name = models.CharField(max_length=40)  # "Fall 2026"
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gt=F("starts_on")), name="term_dates_ordered"
            ),
        ]

    def __str__(self):
        return self.name


class Course(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=16)  # "CSE 311"
    title = models.CharField(max_length=200)
    credits = models.DecimalField(max_digits=4, decimal_places=1)
    ects = models.DecimalField(max_digits=4, decimal_places=1)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["program", "code"], name="uniq_course_code")]

    def __str__(self):
        return f"{self.code} {self.title}"


class CourseOffering(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="offerings")
    section = models.CharField(max_length=8, default="1")
    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="teaching", blank=True
    )
    syllabus = models.FileField(upload_to="syllabi/%Y/", null=True, blank=True)
    cloned_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "term", "section"], name="uniq_offering"),
        ]

    def __str__(self):
        suffix = "" if self.section == "1" else f" (section {self.section})"
        return f"{self.course.code} · {self.term.name}{suffix}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ENROLLED = "enrolled", "Enrolled"
        DROPPED = "dropped", "Dropped"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.CASCADE, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENROLLED)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["offering", "student"], name="uniq_enrollment"),
        ]
        indexes = [models.Index(fields=["student"], name="enrollment_student_idx")]

    def __str__(self):
        return f"{self.student} in {self.offering}"
```

**2. Migration.** S0-03 already created `accounts/0001` (the user model), which `CourseOffering.instructors` and `Enrollment.student` point at.

```bash
uv run python manage.py makemigrations catalog       # → 0001_initial.py
uv run python manage.py sqlmigrate catalog 0001 | grep -i "unique index"
#   CREATE UNIQUE INDEX "one_active_po_set_per_program" ON "catalog_programoutcomeset" ("program_id") WHERE "is_active";
uv run python manage.py migrate
```

That `sqlmigrate` line is a good slide for the CSE 321 checkpoint: it shows the partial index as real SQL.

**3. Admin.** `list_select_related` avoids one extra query per row; `raw_id_fields` on students gives a search popup instead of a dropdown with hundreds of names (and doesn't depend on the user admin, which arrives in S1-01).

**`apps/catalog/admin.py`**

```python
from django.contrib import admin

from .models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "attainment_threshold")
    search_fields = ("code", "name")


class ProgramOutcomeInline(admin.TabularInline):
    model = ProgramOutcome
    extra = 0


@admin.register(ProgramOutcomeSet)
class ProgramOutcomeSetAdmin(admin.ModelAdmin):
    list_display = ("label", "program", "effective_from_year", "is_active")
    list_filter = ("program", "is_active")
    inlines = [ProgramOutcomeInline]


@admin.register(ProgramOutcome)
class ProgramOutcomeAdmin(admin.ModelAdmin):
    list_display = ("number", "short_name", "po_set")
    list_filter = ("po_set",)
    search_fields = ("short_name", "description")


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "starts_on", "ends_on", "status")
    list_filter = ("status",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "program", "credits", "ects")
    list_filter = ("program",)
    search_fields = ("code", "title")


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    raw_id_fields = ("student",)  # a search popup; a dropdown of 400 students would be unusable


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ("course", "term", "section", "created_at")
    list_filter = ("term", "course__program")
    search_fields = ("course__code", "course__title")
    filter_horizontal = ("instructors",)
    inlines = [EnrollmentInline]  # S1-03 adds the LO and assessment inlines
    list_select_related = ("course", "term")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "offering", "status", "enrolled_at")
    list_filter = ("status", "offering__term")
    search_fields = ("student__email", "student__student_number", "offering__course__code")
    raw_id_fields = ("student",)  # a search popup; a dropdown of 400 students would be unusable
    list_select_related = ("student", "offering__course", "offering__term")
```

**4. Start the factories.** A factory builds a valid object with sensible defaults, so a test says only what it cares about: `OfferingFactory(course__code="CSE 311")` creates the program, course and term too. Three details:

- `UserFactory` hashes a known password (`PASSWORD`), so view tests can log in through the real login form.
- `ProgramFactory` makes programs `TST0`, `TST1`, …, never `CSE`: the data migration (S1-05) creates the real `CSE` program in every test database, and tests must not collide with it.
- `TermFactory` uses `django_get_or_create` on `code`, so every `OfferingFactory()` in one test shares one *Fall 2026* term instead of failing the unique constraint. `OfferingFactory(term__status="closed")` works, but if the test already created a `2026F` term, that existing term is reused **with its existing status**. For a second term, pass a code: `TermFactory(code="2025F", name="Fall 2025", starts_on=…, ends_on=…, status="closed")`.

```python
# apps/core/tests/factories.py (S1-02 part; S1-01, S1-03 and S1-04 add to it)
"""One factory per model (spec §4.8). Use them in every test instead of objects.create():
a factory fills every required field with something valid, so a test only states the
fields it actually cares about.

    student = UserFactory()
    offering = OfferingFactory(course__code="CSE 311")
    grade = GradeFactory(score=Decimal("90"))      # also creates assessment, enrollment, ...
"""

import datetime
from decimal import Decimal

import factory

from apps.accounts.models import User
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)

PASSWORD = "polaris-test-pass"  # every factory user can log in with this
```

**`apps/core/tests/factories.py (add)`**

```python
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@live.acibadem.edu.tr")
    first_name = factory.Faker("first_name", locale="tr_TR")
    last_name = factory.Faker("last_name", locale="tr_TR")
    password = factory.PostGenerationMethodCall("set_password", PASSWORD)

    @factory.post_generation
    def _save_password(obj, create, extracted, **kwargs):
        if create:
            obj.save(update_fields=["password"])


class ProgramFactory(factory.django.DjangoModelFactory):
    """The data migration (S1-05) creates the real program "CSE" in every test database.
    Factories make test programs TST0, TST1, ... so tests never depend on, or collide with,
    the seeded one."""

    class Meta:
        model = Program
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"TST{n}")
    name = factory.LazyAttribute(lambda o: f"Program {o.code}")
    attainment_threshold = Decimal("60")


class ProgramOutcomeSetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramOutcomeSet

    program = factory.SubFactory(ProgramFactory)
    label = factory.Sequence(lambda n: f"Curriculum {n}")
    effective_from_year = 2020
    is_active = True


class ProgramOutcomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramOutcome

    po_set = factory.SubFactory(ProgramOutcomeSetFactory)
    number = factory.Sequence(lambda n: n % 30 + 1)
    short_name = factory.LazyAttribute(lambda o: f"Outcome {o.number}")
    description = factory.Faker("sentence")


class TermFactory(factory.django.DjangoModelFactory):
    """get_or_create on code: every OfferingFactory() in a test shares one "2026F" term.
    To get a different term, pass a different code: TermFactory(code="2025F", status="closed").
    OfferingFactory(term__status="closed") works on its own, but if a 2026F term already
    exists in that test, the existing one is reused with its existing status."""

    class Meta:
        model = Term
        django_get_or_create = ("code",)

    code = "2026F"
    name = "Fall 2026"
    starts_on = datetime.date(2026, 9, 28)
    ends_on = datetime.date(2027, 1, 22)
    status = Term.Status.OPEN


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    program = factory.SubFactory(ProgramFactory)
    code = factory.Sequence(lambda n: f"CSE {100 + n}")
    title = factory.Faker("catch_phrase")
    credits = Decimal("3.0")
    ects = Decimal("6.0")


class OfferingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CourseOffering
        skip_postgeneration_save = True

    course = factory.SubFactory(CourseFactory)
    term = factory.SubFactory(TermFactory)
    section = "1"

    @factory.post_generation
    def instructors(obj, create, extracted, **kwargs):
        """OfferingFactory(instructors=[teacher]) adds them to the M2M."""
        if create and extracted:
            obj.instructors.add(*extracted)


class EnrollmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Enrollment

    offering = factory.SubFactory(OfferingFactory)
    student = factory.SubFactory(UserFactory)
    status = Enrollment.Status.ENROLLED
```

### Tests

Each test tries to break one constraint and expects `IntegrityError`, the database refusing. The `transaction.atomic()` around each failing write matters on PostgreSQL: after a failed statement, Postgres refuses every further statement in the same transaction until it's rolled back, and pytest-django runs each test inside a transaction. The inner `atomic()` creates a savepoint that rolls back just the failed write.

**`apps/catalog/tests/test_models.py`**

```python
"""The database enforces these rules itself (constraints in §5.2). Each test proves one
constraint exists by trying to break it. IntegrityError = the database said no.

Each test that expects an IntegrityError wraps the failing write in transaction.atomic():
on PostgreSQL a failed statement poisons the whole transaction, and pytest-django runs
every test inside one."""

import datetime
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import (
    EnrollmentFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
)

pytestmark = pytest.mark.django_db


def test_only_one_active_po_set_per_program():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgramOutcomeSetFactory(program=program, is_active=True)


def test_inactive_sets_are_unlimited():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=False)
    ProgramOutcomeSetFactory(program=program, is_active=False)  # no error


def test_po_number_unique_within_set():
    po_set = ProgramOutcomeSetFactory()
    ProgramOutcomeFactory(po_set=po_set, number=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgramOutcomeFactory(po_set=po_set, number=3)


def test_term_must_end_after_it_starts():
    with pytest.raises(IntegrityError), transaction.atomic():
        TermFactory(
            code="BAD", starts_on=datetime.date(2026, 9, 1), ends_on=datetime.date(2026, 8, 1)
        )


def test_student_enrolled_once_per_offering():
    enrollment = EnrollmentFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        EnrollmentFactory(offering=enrollment.offering, student=enrollment.student)


def test_offering_str_shows_section_only_when_not_default():
    offering = OfferingFactory(course__code="CSE 311")
    assert str(offering) == "CSE 311 · Fall 2026"
    offering.section = "2"
    assert str(offering) == "CSE 311 · Fall 2026 (section 2)"


def test_course_credits_are_decimals():
    offering = OfferingFactory()
    assert offering.course.credits == D("3.0")
```

### Check it works

```bash
uv run pytest apps/catalog -q          # 7 passed
uv run python manage.py runserver      # /admin/ → Catalog: 7 models
```

In the admin, create a program, a PO set with *Is active* ticked, then a second active set for the same program: the save fails with an error page (`IntegrityError … one_active_po_set_per_program`). That's the constraint working. (The friendly message comes with the PO set screen in Sprint 2, B2.)

### Done when

- [ ] B2 storage: PO sets versioned, one active per program enforced by the database (test)
- [ ] B3 storage: terms, courses, offerings, enrollments with their uniqueness rules (tests)
- [ ] `makemigrations --check` clean; migration reviewed in the PR (one `0001_initial.py`, no surprises)
- [ ] All 7 models in the admin

### Commits and PR

```
Add catalog models with database constraints (#<issue>)
Register catalog models in the admin
Start test factories with users and catalog
Test every catalog constraint against the database
```

PR title: `S1-02: Catalog models, constraints and admin (#<issue>)`

---

## S1-01 · Custom User (email login) and ProgramMembership

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S1-01-membership` · **Depends on:** S1-02 (for `catalog.Program`)

### Goal

One person can hold several roles: a department head who also teaches is two `ProgramMembership` rows, not a single `role` field that can only say one thing (decision D6, spec §3.2). Students carry their cohort year, which the database requires. The user admin works with email instead of username. (The `User` model itself landed in S0-03; see the note there.)

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/accounts/models.py` | modify | Add `ProgramMembership` below `User` |
| `apps/accounts/migrations/0002_programmembership.py` | create (generated) | |
| `apps/accounts/admin.py` | create | User admin for an email-only user, membership inline |
| `apps/core/tests/factories.py` | modify | `MembershipFactory` |
| `apps/accounts/tests/test_membership.py` | create | |

### Steps

**1. The model.** Add to `apps/accounts/models.py`, and add `from django.db.models import Q` to its imports. The check constraint `student_has_cohort` reads "role is not student, OR cohort year is filled in": a student without a cohort is impossible at the database level, because P13 needs the cohort to pick the PO set.

```python
class ProgramMembership(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        INSTRUCTOR = "instructor", "Instructor"
        HEAD = "head", "Department Head"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    program = models.ForeignKey(
        "catalog.Program", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    # students only, e.g. 2023
    cohort_year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "program", "role"], name="uniq_membership"),
            models.CheckConstraint(
                condition=~Q(role="student") | Q(cohort_year__isnull=False),
                name="student_has_cohort",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.get_role_display()} · {self.program}"
```

```bash
git rebase develop                                    # S1-02 must be in
uv run python manage.py makemigrations accounts       # → 0002_programmembership.py
uv run python manage.py migrate
```

**2. The user admin.** Django's built-in `UserAdmin` is written for a model with a `username`. Ours has none, so three things change: the fieldsets (what the edit page shows), the add form (`AdminUserCreationForm` subclassed with our fields; Django 6.1's version includes the *usable password* switch, so you can create an account that can only log in after a password reset) and the ordering. Memberships appear as a table inside the user page, so "make Deniz head as well" is one row.

**`apps/accounts/admin.py`**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import ProgramMembership, User


class UserAdminCreationForm(AdminUserCreationForm):
    """Django's form asks for a username; ours has none, so list the fields we do have."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class MembershipInline(admin.TabularInline):
    model = ProgramMembership
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    inlines = [MembershipInline]
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "student_number", "is_staff")
    search_fields = ("email", "first_name", "last_name", "student_number")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "student_number")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(ProgramMembership)
class ProgramMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "program", "role", "cohort_year")
    list_filter = ("program", "role", "cohort_year")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
```

**3. Factory.** Add `ProgramMembership` to the `apps.accounts.models` import in `factories.py`, then:

**`apps/core/tests/factories.py (add)`**

```python
class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramMembership

    user = factory.SubFactory(UserFactory)
    program = factory.SubFactory(ProgramFactory)
    role = ProgramMembership.Role.STUDENT
    cohort_year = factory.Maybe(
        factory.LazyAttribute(lambda o: o.role == ProgramMembership.Role.STUDENT),
        yes_declaration=2023,
        no_declaration=None,
    )
```

`factory.Maybe` gives students a cohort (2023) and everyone else `None`, mirroring the constraint.

### Tests

**`apps/accounts/tests/test_membership.py`**

```python
import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_student_membership_needs_cohort():
    with pytest.raises(IntegrityError), transaction.atomic():
        MembershipFactory(role=ProgramMembership.Role.STUDENT, cohort_year=None)


def test_instructor_membership_needs_no_cohort():
    m = MembershipFactory(role=ProgramMembership.Role.INSTRUCTOR)
    assert m.cohort_year is None


def test_one_person_can_be_instructor_and_head():
    """D6: a department head usually also teaches."""
    user, program = UserFactory(), ProgramFactory()
    MembershipFactory(user=user, program=program, role="instructor")
    MembershipFactory(user=user, program=program, role="head")
    assert set(user.memberships.values_list("role", flat=True)) == {"instructor", "head"}


def test_membership_str():
    m = MembershipFactory(role=ProgramMembership.Role.HEAD)
    assert "Department Head" in str(m)
```

### Check it works

`/admin/accounts/user/add/` asks for email, first and last name and password (no username). Open a user, add two membership rows (instructor, head) for CSE, save. Add a third row with role *Student* and an empty cohort: the save fails (`student_has_cohort`).

### Done when

- [ ] D6: one user, several roles (test)
- [ ] A student without a cohort is impossible (test)
- [ ] User admin can add and edit email-only users (S1-08's admin smoke test covers it)

### Commits and PR

```
Add ProgramMembership so one person can hold several roles (#<issue>)
Adapt the user admin to email login with a membership inline
```

PR title: `S1-01: Program memberships and the email-user admin (#<issue>)`

---

## S1-03 · Outcome models: LOs, assessments, both weight tables

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S1-03-outcomes` · **Depends on:** S1-02

### Goal

The two layers of weighted arrows from spec §2.1 become tables: `AssessmentLOWeight` (percent, 0 < w ≤ 100, policy P1) and `LOPOWeight` (integer 1–5, P2). A missing arrow is a missing row, never a stored 0. Learning outcomes and assessments belong to an **offering**, not a catalog course, because they change from term to term. Every row carries a `source` (manual, syllabus, AI-suggested, cloned) so the AI features in Sprint 6 can show where each value came from.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/outcomes/models.py` | create | `Source`, `LearningOutcome`, `Assessment`, `AssessmentLOWeight`, `LOPOWeight` |
| `apps/outcomes/migrations/0001_initial.py` | create (generated) | |
| `apps/outcomes/admin.py` | create | Weight inlines on LO and assessment pages |
| `apps/catalog/admin.py` | modify | LO and assessment inlines on the offering page (B12) |
| `apps/core/tests/factories.py` | modify | Four factories |
| `apps/outcomes/tests/test_models.py` | create | |

### Steps

**1. Models.** Points to understand:

- `Assessment.max_score` defaults to 100 and must be positive (P3 divides by it).
- `course_weight` is the share of the course grade (e.g. 30%). It does **not** enter any score; the engine uses the assessment→LO weights. It's stored because syllabi state it, lint rule L004 checks it sums to 100, and the AI uses it as a default.
- `published_at` on the assessment is the publish switch (D2). `Grade` (S1-04) has the per-grade copy.
- `LOPOWeight.program_outcome` is `PROTECT`: a PO that courses map to cannot be deleted (B2 AC3).
- The weight range checks are `CheckConstraint`s, so the database rejects a weight of 6 even if a form forgets to.

**`apps/outcomes/models.py`**

```python
from django.db import models
from django.db.models import Q


class Source(models.TextChoices):
    MANUAL = "manual", "Entered by hand"
    SYLLABUS = "syllabus", "Read from syllabus"
    AI_SUGGESTED = "ai_suggested", "Suggested by AI"
    CLONED = "cloned", "Cloned from a previous term"


class LearningOutcome(models.Model):
    offering = models.ForeignKey(
        "catalog.CourseOffering", on_delete=models.CASCADE, related_name="learning_outcomes"
    )
    number = models.PositiveSmallIntegerField()
    description = models.TextField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "number"], name="uniq_lo_number")
        ]

    def __str__(self):
        return f"LO {self.number}"


class Assessment(models.Model):
    class Kind(models.TextChoices):
        MIDTERM = "midterm", "Midterm"
        FINAL = "final", "Final exam"
        PROJECT = "project", "Project"
        QUIZ = "quiz", "Quiz"
        HOMEWORK = "homework", "Homework"
        LAB = "lab", "Lab"
        PRESENTATION = "presentation", "Presentation"
        PARTICIPATION = "participation", "Attendance / participation"
        OTHER = "other", "Other"

    offering = models.ForeignKey(
        "catalog.CourseOffering", on_delete=models.CASCADE, related_name="assessments"
    )
    name = models.CharField(max_length=100)  # "Midterm I"
    kind = models.CharField(max_length=16, choices=Kind.choices)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    course_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # share of the course grade, e.g. 25 (%). Informational; also the AI's default
    # for assessment→LO weights
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "name"], name="uniq_assessment_name"),
            models.CheckConstraint(condition=Q(max_score__gt=0), name="max_score_positive"),
        ]

    def __str__(self):
        return self.name


class AssessmentLOWeight(models.Model):
    """Arrow from an assessment to an LO. Weight in percent, 0 < w ≤ 100 (policy P1)."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="lo_weights")
    learning_outcome = models.ForeignKey(
        LearningOutcome, on_delete=models.CASCADE, related_name="assessment_weights"
    )
    weight = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "learning_outcome"], name="uniq_a_lo"),
            models.CheckConstraint(
                condition=Q(weight__gt=0) & Q(weight__lte=100), name="a_lo_weight_range"
            ),
        ]

    def __str__(self):
        return f"{self.assessment} → {self.learning_outcome}: {self.weight}%"


class LOPOWeight(models.Model):
    """Arrow from an LO to a PO. Integer 1..5 (policy P2). No row = no contribution."""

    learning_outcome = models.ForeignKey(
        LearningOutcome, on_delete=models.CASCADE, related_name="po_weights"
    )
    program_outcome = models.ForeignKey(
        "catalog.ProgramOutcome", on_delete=models.PROTECT, related_name="lo_weights"
    )
    weight = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    # filled by the AI suggestion (T1.3)
    rationale = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_outcome", "program_outcome"], name="uniq_lo_po"
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=1) & Q(weight__lte=5), name="lo_po_weight_range"
            ),
        ]

    def __str__(self):
        return f"{self.learning_outcome} → {self.program_outcome}: {self.weight}"
```

```bash
uv run python manage.py makemigrations outcomes && uv run python manage.py migrate
```

**2. Admin.**

**`apps/outcomes/admin.py`**

```python
from django.contrib import admin

from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight


class AssessmentLOWeightInline(admin.TabularInline):
    model = AssessmentLOWeight
    extra = 0


class LOPOWeightInline(admin.TabularInline):
    model = LOPOWeight
    extra = 0


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "offering", "source")
    list_filter = ("source", "offering__term")
    search_fields = ("description", "offering__course__code")
    inlines = [LOPOWeightInline]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("name", "offering", "kind", "max_score", "course_weight", "published_at")
    list_filter = ("kind", "offering__term")
    search_fields = ("name", "offering__course__code")
    inlines = [AssessmentLOWeightInline]


@admin.register(AssessmentLOWeight)
class AssessmentLOWeightAdmin(admin.ModelAdmin):
    list_display = ("assessment", "learning_outcome", "weight")
    list_filter = ("assessment__offering__term",)


@admin.register(LOPOWeight)
class LOPOWeightAdmin(admin.ModelAdmin):
    list_display = ("learning_outcome", "program_outcome", "weight", "source")
    list_filter = ("source", "program_outcome")
```

And in `apps/catalog/admin.py` (owned by A, but this is a three-line change that belongs with these models), add the import `from apps.outcomes.models import Assessment, LearningOutcome`, these two inlines above `CourseOfferingAdmin`, and change its `inlines` line:

```python
class LearningOutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 0
    fields = ("number", "description", "source")


class AssessmentInline(admin.TabularInline):
    model = Assessment
    extra = 0
    fields = ("position", "name", "kind", "max_score", "course_weight", "due_date", "published_at")
    readonly_fields = ("published_at",)
```

```python
    inlines = [LearningOutcomeInline, AssessmentInline, EnrollmentInline]
```

**3. Factories.** Add `from django.utils import timezone` and `from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight` to the imports, then:

**`apps/core/tests/factories.py (add)`**

```python
class LearningOutcomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearningOutcome

    offering = factory.SubFactory(OfferingFactory)
    number = factory.Sequence(lambda n: n + 1)
    description = factory.Faker("sentence")


class AssessmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assessment

    offering = factory.SubFactory(OfferingFactory)
    name = factory.Sequence(lambda n: f"Assessment {n}")
    kind = Assessment.Kind.MIDTERM
    max_score = Decimal("100")
    published_at = None

    class Params:
        published = factory.Trait(published_at=factory.LazyFunction(timezone.now))


class AssessmentLOWeightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssessmentLOWeight

    assessment = factory.SubFactory(AssessmentFactory)
    learning_outcome = factory.SubFactory(
        LearningOutcomeFactory, offering=factory.SelfAttribute("..assessment.offering")
    )
    weight = Decimal("100")


class LOPOWeightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LOPOWeight

    learning_outcome = factory.SubFactory(LearningOutcomeFactory)
    program_outcome = factory.SubFactory(ProgramOutcomeFactory)
    weight = 3
```

`factory.SelfAttribute("..assessment.offering")` makes the LO belong to **the same offering** as the assessment, which is a rule the database can't enforce (spec §5.3) but our test data must always respect. `AssessmentFactory(published=True)` is a *trait*: one keyword sets `published_at`.

### Tests

The `test_negative_score_rejected` and `test_unpublished_change_flag` tests in this file need `GradeFactory`; add them in S1-04, together with the `GradeFactory` import.

**`apps/outcomes/tests/test_models.py`**

```python
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("weight", [D(0), D("-5"), D("100.01")])
def test_assessment_lo_weight_range(weight):
    """P1: 0 < weight ≤ 100."""
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentLOWeightFactory(weight=weight)


@pytest.mark.parametrize("weight", [0, 6])
def test_lo_po_weight_range(weight):
    """P2: integers 1..5."""
    with pytest.raises(IntegrityError), transaction.atomic():
        LOPOWeightFactory(weight=weight)


def test_valid_weights_save():
    a_lo = AssessmentLOWeightFactory(weight=D("40"))
    lo_po = LOPOWeightFactory(weight=5)
    assert str(a_lo).endswith(": 40%")
    assert str(lo_po).endswith(": 5")


def test_lo_number_unique_per_offering():
    lo = LearningOutcomeFactory(number=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        LearningOutcomeFactory(offering=lo.offering, number=1)
    assert str(lo) == "LO 1"


def test_max_score_must_be_positive():
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentFactory(max_score=D(0))
```

### Check it works

Admin → a course offering shows LO and assessment tables inline. Admin → an LO shows its PO weights inline; entering weight 6 fails to save.

### Done when

- [ ] P1 and P2 ranges enforced by the database (tests)
- [ ] LO numbers unique per offering (test)
- [ ] B12: LOs and assessments inline on the offering admin

### Commits and PR

```
Add learning outcomes, assessments and both weight tables (#<issue>)
Show LOs and assessments inline on the offering admin
Add outcome factories and constraint tests
```

PR title: `S1-03: Outcome models and weight tables (#<issue>)`

---

## S1-04 · Grade, AuditEvent, `audit.record`, and the two job tables

**Points:** 2 · **Owner:** Person B · **Branch:** `feature/S1-04-grades-audit` · **Depends on:** S1-03

### Goal

The last tables of the data model. `Grade` holds two values (D2): `score` is the instructor's working draft, `published_score` is what every student page and every calculation sees. Publishing (S3-01) copies one to the other. `AuditEvent` records every change (spec §5.4), through one function, `core.audit.record`, that every service in later sprints calls. `IngestionJob` and `ExportJob` (spec §5.2) have no screens until Sprints 3–7, but adding them now completes the data model for the CSE 321 checkpoint diagrams.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/grading/models.py`, `apps/core/models.py`, `apps/ingestion/models.py`, `apps/reports/models.py` | create | `Grade`, `AuditEvent`, `IngestionJob`, `ExportJob` |
| 4 × `migrations/0001_initial.py` | create (generated) | |
| `apps/core/audit.py` | create | `record()` and `snapshot()` |
| 4 × `admin.py` | create | Audit admin is read-only |
| `apps/core/tests/factories.py` | modify | `GradeFactory` |
| `apps/core/tests/test_audit.py`, `apps/outcomes/tests/test_models.py` | create / modify | |

### Steps

**1. Models.**

**`apps/grading/models.py`**

```python
from django.conf import settings
from django.db import models
from django.db.models import Q


class Grade(models.Model):
    """One student's mark on one assessment.
    `score` is the instructor's working (draft) value. `published_score` is what students
    and every score calculation see. Publishing copies score → published_score (decision D2)."""

    assessment = models.ForeignKey(
        "outcomes.Assessment", on_delete=models.CASCADE, related_name="grades"
    )
    enrollment = models.ForeignKey(
        "catalog.Enrollment", on_delete=models.CASCADE, related_name="grades"
    )
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_excused = models.BooleanField(default=False)
    published_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    published_is_excused = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "enrollment"], name="uniq_grade"),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=0), name="score_non_negative"
            ),
        ]
        indexes = [models.Index(fields=["enrollment"], name="grade_enrollment_idx")]

    def __str__(self):
        return f"{self.enrollment} · {self.assessment}: {self.score}"

    @property
    def has_unpublished_change(self) -> bool:
        return (self.score, self.is_excused) != (self.published_score, self.published_is_excused)
```

`has_unpublished_change` compares the draft pair with the published pair; the grade sheet (S2-06) uses it for the amber dot.

**`apps/core/models.py`**

```python
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    # "grade.update", "assessment.publish", "lo_po.update", ...
    action = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=40)  # "grade", "assessment", "lo_po_weight", ...
    entity_id = models.BigIntegerField()
    offering = models.ForeignKey("catalog.CourseOffering", null=True, on_delete=models.SET_NULL)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["offering", "-created_at"], name="audit_offering_time_idx"),
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"
```

**`apps/ingestion/models.py`**

```python
from django.db import models


class IngestionJob(models.Model):
    class Kind(models.TextChoices):
        SYLLABUS = "syllabus", "Syllabus"
        GRADES = "grades", "Grade file"
        ENROLLMENTS = "enrollments", "Enrollment list"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        PROCESSING = "processing", "Reading"
        READY = "ready", "Ready for review"
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Failed"
        DISCARDED = "discarded", "Discarded"

    offering = models.ForeignKey(
        "catalog.CourseOffering", on_delete=models.CASCADE, related_name="ingestion_jobs"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to="uploads/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(null=True, blank=True)  # validated extraction / parsed rows
    warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    model = models.CharField(max_length=40, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} job #{self.pk} ({self.status})"
```

**`apps/reports/models.py`**

```python
from django.conf import settings
from django.db import models


class ExportJob(models.Model):
    """A PDF or Excel report built in the background (T1.7, T2.4). The file is kept 7 days."""

    class Kind(models.TextChoices):
        COURSE = "course", "Course report"
        DEPARTMENT = "department", "Department report"
        TRANSCRIPT = "transcript", "PO transcript"

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        XLSX = "xlsx", "Excel"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        RUNNING = "running", "Building"
        DONE = "done", "Ready"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    fmt = models.CharField(max_length=4, choices=Format.choices)
    offering = models.ForeignKey(
        "catalog.CourseOffering", null=True, blank=True, on_delete=models.CASCADE
    )
    program = models.ForeignKey("catalog.Program", null=True, blank=True, on_delete=models.CASCADE)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    # filters used (terms, cohort, include_open)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    file = models.FileField(upload_to="exports/%Y/%m/", null=True, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.fmt}) #{self.pk}"
```

```bash
uv run python manage.py makemigrations grading core ingestion reports
uv run python manage.py migrate
```

**2. The audit helper.** Two rules shape it. First, it writes **inside the caller's transaction**: if the service's write rolls back, so does the audit event, so the log never claims a change that didn't happen (there's a test for this). Second, `before`/`after` must be JSON: `Decimal` and dates aren't, so `snapshot()` converts them. This is a small addition to spec §5.4 (which says "convert `Decimal` to `str`" but gives no helper); it's in the code map additions.

**`apps/core/audit.py`**

```python
"""One function every service calls after a write: record(actor, action, entity, ...).
The event is created inside the caller's transaction, so if the write rolls back,
the audit event rolls back with it."""

import datetime
from decimal import Decimal

from .models import AuditEvent


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, "pk"):  # a model instance (foreign key): store its id
        return value.pk
    return value


def snapshot(instance, fields):
    """A JSON-safe dict of the named fields, for the before/after columns."""
    return {name: _json_safe(getattr(instance, name)) for name in fields}


def record(actor, action, entity, *, before=None, after=None, offering=None):
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        entity_type=entity._meta.model_name,
        entity_id=entity.pk,
        offering=offering,
        before=before,
        after=after,
    )
```

**3. Admin.** The audit admin forbids add, change and delete: an audit trail you can edit is not an audit trail.

**`apps/core/admin.py`**

```python
from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only: an audit trail you can edit is not an audit trail."""

    list_display = ("created_at", "actor", "action", "entity_type", "entity_id", "offering")
    list_filter = ("action", "entity_type")
    search_fields = ("actor__email", "action")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

**`apps/grading/admin.py`**

```python
from django.contrib import admin

from .models import Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "assessment", "score", "published_score", "is_excused")
    list_filter = ("assessment__offering__term", "is_excused")
    search_fields = ("enrollment__student__email", "enrollment__student__student_number")
    list_select_related = ("enrollment__student", "assessment")
    raw_id_fields = ("enrollment", "assessment")
```

**`apps/ingestion/admin.py`**

```python
from django.contrib import admin

from .models import IngestionJob


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "offering",
        "status",
        "original_filename",
        "cost_usd",
        "created_at",
    )
    list_filter = ("kind", "status")
    readonly_fields = ("input_tokens", "output_tokens", "cost_usd", "request_id", "model")
```

**`apps/reports/admin.py`**

```python
from django.contrib import admin

from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "fmt", "status", "created_by", "created_at", "finished_at")
    list_filter = ("kind", "fmt", "status")
```

**4. `GradeFactory`.** Add `Grade` to the imports. `GradeFactory(score=90)` makes a draft; `GradeFactory(score=90, published=True)` makes what a student sees: the published fields are copied and the assessment is marked published too (a published grade on an unpublished assessment is a state the app never creates).

**`apps/core/tests/factories.py (add)`**

```python
class GradeFactory(factory.django.DjangoModelFactory):
    """GradeFactory(score=90) is a draft. GradeFactory(score=90, published=True) is what a
    student sees: published_score copied and the assessment marked published."""

    class Meta:
        model = Grade
        skip_postgeneration_save = True

    assessment = factory.SubFactory(AssessmentFactory)
    enrollment = factory.SubFactory(
        EnrollmentFactory, offering=factory.SelfAttribute("..assessment.offering")
    )
    score = Decimal("75")
    is_excused = False

    class Params:
        published = factory.Trait(
            published_score=factory.SelfAttribute("score"),
            published_is_excused=factory.SelfAttribute("is_excused"),
            published_at=factory.LazyFunction(timezone.now),
        )

    @factory.post_generation
    def _publish_assessment(obj, create, extracted, **kwargs):
        if create and obj.published_at and obj.assessment.published_at is None:
            obj.assessment.published_at = obj.published_at
            obj.assessment.save(update_fields=["published_at"])
```

### Tests

**`apps/core/tests/test_audit.py`**

```python
import datetime
from decimal import Decimal as D

import pytest
from django.db import transaction

from apps.core.audit import record, snapshot
from apps.core.models import AuditEvent
from apps.core.tests.factories import GradeFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_snapshot_is_json_safe():
    grade = GradeFactory(score=D("85.5"))
    snap = snapshot(grade, ["score", "is_excused", "assessment", "updated_at"])
    assert snap["score"] == "85.50" or snap["score"] == "85.5"
    assert snap["is_excused"] is False
    assert snap["assessment"] == grade.assessment_id
    datetime.datetime.fromisoformat(snap["updated_at"])  # parses: it's an ISO string


def test_record_stores_who_what_and_where():
    actor = UserFactory()
    grade = GradeFactory(score=D(75))
    event = record(
        actor,
        "grade.update",
        grade,
        before={"score": "75"},
        after={"score": "78"},
        offering=grade.assessment.offering,
    )
    assert event.entity_type == "grade"
    assert event.entity_id == grade.pk
    assert event.offering == grade.assessment.offering
    assert str(event) == f"grade.update grade#{grade.pk}"


def test_event_rolls_back_with_the_write():
    """Audit events are written in the caller's transaction (§5.3)."""
    grade = GradeFactory()
    with pytest.raises(RuntimeError), transaction.atomic():
        record(None, "grade.update", grade)
        raise RuntimeError("the service failed after recording")
    assert AuditEvent.objects.count() == 0
```

And add the two grade tests to `apps/outcomes/tests/test_models.py` (with `GradeFactory` in its import list):

```python
def test_negative_score_rejected():
    with pytest.raises(IntegrityError), transaction.atomic():
        GradeFactory(score=D(-1))


def test_unpublished_change_flag():
    grade = GradeFactory(score=D(80), published=True)
    assert not grade.has_unpublished_change
    grade.score = D(85)
    assert grade.has_unpublished_change
    assert str(grade.assessment) == grade.assessment.name
    assert "85" in str(grade)
```

**Run the whole suite on PostgreSQL once** (not just SQLite or a single app) before opening the PR: `docker compose up -d && uv run pytest`. The constraint tests behave differently on different databases, and CI runs Postgres.

### Check it works

```bash
uv run python manage.py makemigrations --check --dry-run      # No changes detected
uv run python manage.py showmigrations | grep -c "\[X\]"      # every migration applied
```

Admin → Audit events: the page has no *Add* button, and opening an event shows read-only fields.

### Done when

- [ ] Every model of §5.2 exists, migrated, in the admin
- [ ] Draft vs published grade values (D2) and the unpublished-change flag (test)
- [ ] Audit events roll back with the write (test)
- [ ] Full suite green on Postgres

### Commits and PR

```
Add grades with separate draft and published values (#<issue>)
Add the audit event table and the record() helper
Add ingestion and export job tables to complete the data model
Make the audit admin read-only
```

PR title: `S1-04: Grades, audit trail and job tables (#<issue>)`

---

## S1-05 · Data migration: the CSE program and the 11 official POs

**Points:** 1 · **Owner:** Person A · **Branch:** `feature/S1-05-po-seed` · **Depends on:** S1-02

### Goal

Every database, production included, has the CSE program with its official 11 POs from the first `migrate` (B2 AC1). A **data migration**, not a fixture or the `seed_demo` command: fixtures are easy to forget to load, and `seed_demo` refuses to run in production. The wording is verbatim from Acıbadem OBS (spec Appendix A), including the typos ("of of" in PO 8): we don't silently edit official text.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/catalog/migrations/0002_seed_cse_program.py` | create | `RunPython` with a reverse function |
| `apps/catalog/tests/test_seed_migration.py` | create | |

### Steps

**1. Create an empty migration, then fill it in.**

```bash
uv run python manage.py makemigrations catalog --empty -n seed_cse_program
```

Two rules for data migrations. **Use `apps.get_model(...)`, never `from apps.catalog.models import …`**: the imported class is today's model, and the migration must keep working after later migrations add or rename fields. **Write a reverse function**, so `migrate catalog 0001` works (CI doesn't test it, but you'll need it the first time a migration goes wrong). `get_or_create` / `update_or_create` make it safe to run on a database that already has some of the rows.

The PO set is labelled *2023 curriculum* with `effective_from_year = 2023`, and it is the active set. Our demo cohorts are 2023–2025; a student from an older cohort falls back to the active set (P13 fallback), which with one set changes nothing.

**`apps/catalog/migrations/0002_seed_cse_program.py`**

```python
"""Seed the CSE program and its official 11 Program Outcomes (spec Appendix A).

A data migration, not a fixture or seed command, because the POs must exist on every
database from the first deploy: production included. The wording is copied verbatim from
Acıbadem OBS, typos and all ("of of" in PO 8). Do not fix it here.
"""

from decimal import Decimal

from django.db import migrations

PROGRAM_CODE = "CSE"
PO_SET_LABEL = "2023 curriculum"

OUTCOMES = [
    (
        1,
        "Math, science & engineering knowledge",
        "Gain adequate knowledge in mathematics, science and related engineering discipline "
        "subjects; ability to use theoretical and applied knowledge in these fields in complex "
        "engineering problems.",
    ),
    (
        2,
        "Problem solving",
        "Gain ability to identify, formulate and solve complex engineering problems; gain ability "
        "to choose and apply appropriate analysis and modeling methods for this purpose.",
    ),
    (
        3,
        "System design",
        "Gain ability to design a complex system, process, device or product to meet certain "
        "requirements under realistic constraints and Conditions; ability to apply modern design "
        "methods for this purpose.",
    ),
    (
        4,
        "Modern tools & IT",
        "Analyze and create solutions to complex problems encountered in engineering applications "
        "of modern techniques and tools for development, have skills, gain the ability to use "
        "information technology effectively.",
    ),
    (
        5,
        "Experiments & data",
        "Gain ability to design experiments, conduct experiments, collect data, analyze and "
        "interpret results for the study of complex engineering problems or discipline-specific "
        "research topics.",
    ),
    (
        6,
        "Teamwork",
        "Gain ability to work effectively in interdisciplinary and multidisciplinary teams; work "
        "individually.",
    ),
    (
        7,
        "Communication",
        "Gain ability to communicate effectively in Turkish oral and written; knowledge of at "
        "least one foreign language; ability to write effective reports and understand written "
        "report, design and production reports, make effective presentations, give and receive "
        "clear and understandable instructions.",
    ),
    (
        8,
        "Lifelong learning",
        "Gain awareness of of the need for lifelong learning; the ability to access information, "
        "monitor developments in science and technology, and constantly renew oneself.",
    ),
    (
        9,
        "Ethics & standards",
        "Act in accordance with ethical principles, awareness of professional and ethical "
        "responsibility; gain knowledge of standards used in engineering applications",
    ),
    (
        10,
        "Project, risk & change management",
        "Gain knowledge of business practices such as Project Management, risk Management and "
        "change management; gain awareness about entrepreneurship, innovation; have information "
        "about sustainable development.",
    ),
    (
        11,
        "Health, safety, environment & law",
        "Gain knowledge of the effects of engineering practices on health, environment and safety "
        "in Universal and social dimensions and the problems reflected in the field of "
        "engineering of the era; gain awareness of the legal consequences of engineering "
        "solutions.",
    ),
]


def seed(apps, schema_editor):
    # Always use apps.get_model in migrations: it returns the model as it was at THIS
    # migration, so the file keeps working after later migrations change the model.
    Program = apps.get_model("catalog", "Program")
    ProgramOutcomeSet = apps.get_model("catalog", "ProgramOutcomeSet")
    ProgramOutcome = apps.get_model("catalog", "ProgramOutcome")

    program, _ = Program.objects.get_or_create(
        code=PROGRAM_CODE,
        defaults={
            "name": "Computer Science and Engineering",
            "attainment_threshold": Decimal("60"),
        },
    )
    po_set, _ = ProgramOutcomeSet.objects.get_or_create(
        program=program,
        label=PO_SET_LABEL,
        defaults={"effective_from_year": 2023, "is_active": True},
    )
    for number, short_name, description in OUTCOMES:
        ProgramOutcome.objects.update_or_create(
            po_set=po_set,
            number=number,
            defaults={"short_name": short_name, "description": description},
        )


def unseed(apps, schema_editor):
    Program = apps.get_model("catalog", "Program")
    Program.objects.filter(code=PROGRAM_CODE).delete()  # cascades to the PO set and POs


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
```

**2. Run it forwards, backwards, forwards.**

```bash
uv run python manage.py migrate catalog
uv run python manage.py migrate catalog 0001     # reverse: deletes CSE and its POs
uv run python manage.py migrate catalog          # forwards again
```

### Tests

The test database is built by running every migration, so the POs exist in every test. The factories never create a program called `CSE`, so nothing collides.

**`apps/catalog/tests/test_seed_migration.py`**

```python
import pytest

from apps.catalog.models import Program, ProgramOutcome, ProgramOutcomeSet

pytestmark = pytest.mark.django_db


def active_po_set(program):
    return ProgramOutcomeSet.objects.get(program=program, is_active=True)


def test_official_pos_are_seeded():
    """S1-05 / B2 AC1: a fresh database has CSE with the 11 official POs."""
    cse = Program.objects.get(code="CSE")
    outcomes = ProgramOutcome.objects.filter(po_set=active_po_set(cse))
    assert outcomes.count() == 11
    assert outcomes.get(number=6).short_name == "Teamwork"
    assert outcomes.get(number=8).description.startswith("Gain awareness of of the need")
```

### Check it works

Admin → Program outcome sets → *CSE · 2023 curriculum* lists 11 POs with the official text.

### Done when

- [ ] B2 AC1: a fresh install shows 11 POs with the official wording (test)
- [ ] Migration reversible (ran backwards and forwards locally)

### Commits and PR

```
Seed the CSE program and its 11 official program outcomes (#<issue>)
```

PR title: `S1-05: Official POs as a data migration (#<issue>)`

---
## S1-06 · The scoring engine, test-first

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S1-06-scoring-engine` · **Depends on:** S0-03 (no models needed)

### Goal

`apps/scoring/engine.py` computes every score in POlaris: pure Python, no Django import, no database. It reproduces the professor's slide (LO 1 86.0, LO 2 82.9, PO 1 85.0, PO 2 82.9) and implements policies P1–P3, P5–P8 and P12 from spec §2.3. It is built **test-first**, with the red and green commits kept separate in the history: that history is our evidence for the CSE 311 TDD topic (Week 11) and a ready-made checkpoint slide.

### The method in plain language (read before coding)

At every node the rule is the same weighted average: **score = Σ(weight × source score) ÷ Σ(weights of the sources that have a score)**.

- *Why divide by the weights that are present?* Policy P5: a missing grade is skipped, not counted as 0. Dividing by only the weights of present sources renormalises: in October, an LO fed by a graded midterm (40%) and an ungraded project (100%) shows the midterm score, not a failing mark. The share of weight that was present is reported separately as **coverage** (40 / 140 = 28.6%), so nobody mistakes an early score for a final one.
- *Why can weights be on any scale?* Multiplying every weight by the same number multiplies the top and bottom of the fraction by it, so it cancels. That's why percentages (layer 1) and a 1–5 scale (layer 2) both work, and why weights don't need to sum to 100 (P1). A property test checks this on thousands of random inputs.
- *Why `Decimal` and no rounding until display?* Rounding LO 2 to 82 before computing PO 1 gives 84.7 instead of 85.0: that's exactly the 84-vs-85 discrepancy between the brief and the guidelines (spec §2.2). `Decimal` keeps 28 significant digits and makes 0.1 + 0.2 equal 0.3. Rounding happens once, in `display()`, half-up (84.95 → 85.0; Python's built-in `round()` would use banker's rounding).
- *Why `None` and not 0 when nothing feeds a node?* P12: "no evidence" and "failed" are different things.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/scoring/tests/test_engine.py` | create | 31 tests: golden, policy, property |
| `apps/scoring/engine.py` | create | The engine (spec §2.5) |

### Steps: five red → green cycles

Each cycle is two commits: the failing test (`test: … (red)`), then the code that passes it (`engine: … (green)`). Run `uv run pytest apps/scoring -q` after each step and **see the red before you write the green**: a test you have never seen fail might not be testing anything. Pushing a red commit to your feature branch is fine (CI will show it red, which is the point); only the PR's final state must be green.

| Cycle | Red: write these tests (from the full file below) | Green: write this code | Commit messages |
|---|---|---|---|
| 1 | `test_weighted_average_of_nothing_is_none`, then a first `test_elif_lo1` | `ZERO`, `weighted_average`, `Edge`, `NodeScore`, a `propagate` that groups edges by target and averages | `test: LO 1 from the slide is 86.0 (red)` / `engine: weighted average per target node (green)` |
| 2 | `test_elif_lo2`, `test_elif_po1_on_1_to_5_scale`, `test_elif_po2`, `test_brief_rounding_discrepancy`, `test_display_half_up` | `display()` with `quantize(Decimal("0.1"), ROUND_HALF_UP)` | `test: PO 1 = 85.0 and PO 2 = 82.9 (red)` / `engine: display rounding, half-up, once (green)` |
| 3 | `test_missing_grade_is_skipped_not_zero`, `test_full_coverage_is_exactly_one`, `test_no_data_gives_none`, `test_zero_or_negative_weight_raises` | Skip sources without a score; `coverage = covered ÷ total`; reject weights ≤ 0 | `test: missing grades are skipped, not zero (red)` / `engine: skip missing sources and report coverage (green)` |
| 4 | `test_normalise_out_of_20`, `test_normalise_rejects_zero_max` | `normalise()` | `test: raw marks are normalised to 0-100 (red)` / `engine: normalise raw marks (green)` |
| 5 | The *whole-student* tests: `test_profile_reproduces_the_slide` … `test_no_offerings_gives_empty_profile` | `OfferingInputs`, `StudentProfile`, `compute_student_profile` | `test: a student's profile across courses (red)` / `engine: compute a whole student profile (green)` |
| 6 | The five Hypothesis property tests | Nothing, if cycles 1–5 were right. If one fails, Hypothesis prints the smallest failing input: fix the engine, not the test | `test: property tests for bounds, scale, order, coverage` |

Then **refactor** with the tests green (names, docstrings) and compare your file with the reference below. Don't paste the reference first: the point of the exercise is that the tests drive the code, and that you can explain every line at the demo.

**The finished engine** (identical to spec §2.5 apart from Ruff's import fix: `Hashable`, `Iterable` and `Mapping` come from `collections.abc`, rule UP035):

**`apps/scoring/engine.py`**

```python
"""Pure scoring engine. No Django imports. Every score in POlaris comes from here."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Edge:
    """A weighted arrow from a source node (assessment or LO) to a target node (LO or PO)."""

    source: Hashable
    target: Hashable
    weight: Decimal


@dataclass(frozen=True)
class NodeScore:
    score: Decimal | None  # None = no source feeding this node has a value (P12)
    coverage: Decimal  # share of inbound weight that had a value, 0..1 (P5)


def weighted_average(pairs: Iterable[tuple[Decimal, Decimal]]) -> Decimal | None:
    """score = sum(weight * score) / sum(weights). None when the weights sum to zero."""
    num = ZERO
    den = ZERO
    for score, weight in pairs:
        num += score * weight
        den += weight
    return None if den == ZERO else num / den


def propagate(
    source_scores: Mapping[Hashable, Decimal], edges: Iterable[Edge]
) -> dict[Hashable, NodeScore]:
    """Compute one layer. Sources without a score are skipped and the remaining
    weights renormalise (P5). Coverage records how much inbound weight was present."""
    inbound: dict[Hashable, list[Edge]] = defaultdict(list)
    for e in edges:
        if e.weight <= ZERO:
            raise ValueError(f"weight must be positive: {e}")
        inbound[e.target].append(e)

    result: dict[Hashable, NodeScore] = {}
    for target, es in inbound.items():
        total = sum((e.weight for e in es), ZERO)
        present = [(source_scores[e.source], e.weight) for e in es if e.source in source_scores]
        covered = sum((w for _, w in present), ZERO)
        result[target] = NodeScore(score=weighted_average(present), coverage=covered / total)
    return result


def normalise(raw: Decimal, max_score: Decimal) -> Decimal:
    """Convert a raw mark (e.g. 17 out of 20) to the 0-100 scale (P3)."""
    if max_score <= ZERO:
        raise ValueError("max_score must be positive")
    return raw / max_score * HUNDRED


def display(value: Decimal | None) -> str:
    """Round only for display: 1 decimal, half-up (P7). None -> an em dash (P12)."""
    if value is None:
        return "—"
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


# ---------- whole-student calculation ----------


@dataclass(frozen=True)
class OfferingInputs:
    """Everything the engine needs about one course offering for one student."""

    offering_id: int
    grades: Mapping[int, Decimal]  # assessment_id -> raw mark (published, not excused)
    max_scores: Mapping[int, Decimal]  # assessment_id -> max_score
    assessment_lo_edges: tuple[Edge, ...]  # source=assessment_id, target=lo_id, weight=%
    lo_po_edges: tuple[Edge, ...]  # source=lo_id, target=po_id, weight=1..5
    # P6: assessments this student is excused from. They drop out of the LO entirely, weight
    # included, so an excused piece of work never leaves the LO looking incomplete.
    excused: frozenset = frozenset()


@dataclass(frozen=True)
class StudentProfile:
    lo_scores: dict[tuple[int, int], NodeScore]  # (offering_id, lo_id) -> score
    po_scores: dict[int, NodeScore]  # po_id -> score
    po_contributors: dict[int, list[tuple[int, int, Decimal]]] = field(default_factory=dict)
    # po_id -> [(offering_id, lo_id, weight)], used for "why is my PO 3 this number?"


def compute_student_profile(offerings: Iterable[OfferingInputs]) -> StudentProfile:
    lo_scores: dict[tuple[int, int], NodeScore] = {}
    lo_values: dict[tuple[int, int], Decimal] = {}
    po_edges: list[Edge] = []
    contributors: dict[int, list[tuple[int, int, Decimal]]] = defaultdict(list)

    for off in offerings:
        normalised = {a: normalise(raw, off.max_scores[a]) for a, raw in off.grades.items()}
        a_lo_edges = [e for e in off.assessment_lo_edges if e.source not in off.excused]
        for lo_id, ns in propagate(normalised, a_lo_edges).items():
            key = (off.offering_id, lo_id)
            lo_scores[key] = ns
            if ns.score is not None:
                lo_values[key] = ns.score
        for e in off.lo_po_edges:
            key = (off.offering_id, e.source)
            po_edges.append(Edge(source=key, target=e.target, weight=e.weight))
            contributors[e.target].append((off.offering_id, e.source, e.weight))

    return StudentProfile(
        lo_scores=lo_scores,
        po_scores=propagate(lo_values, po_edges),
        po_contributors=dict(contributors),
    )
```

Notes on details the tests pin down:

- **LO keys are `(offering_id, lo_id)`** in `compute_student_profile`, because "LO 1" of CSE 311 and "LO 1" of MAT 241 are different things (`test_lo_keys_do_not_collide_across_offerings`).
- **Normalisation happens before weighting**, so a midterm marked out of 50 and one out of 100 are comparable (`test_raw_marks_are_normalised_before_weighting`).
- **`po_contributors`** records which (offering, LO, weight) feed each PO, which is what the student's "why is my PO 3 this number?" drawer shows in S3-02.

### Tests

Golden numbers, every policy, and five properties. For the two-course test the expected value is computed in the test from the same formula (and its rounded display, 80.0, is asserted too), so a reader can check it by hand.

The property tests use [Hypothesis](https://hypothesis.readthedocs.io/): instead of one example, it generates hundreds of random inputs that fit a description (`scores` between 0 and 100 with 2 decimals, `weights` 1–100) and checks a statement that must hold for all of them. Comparisons use a tolerance of 1e-20 because `Decimal` division can differ in the 28th digit depending on the order of operations; anything that tight is mathematically equal for our purposes.

**`apps/scoring/tests/test_engine.py`**

```python
"""Tests for the pure scoring engine (spec §2.6). No database: these run in milliseconds.

Golden tests pin the professor's numbers. Policy tests pin each rule in §2.3.
Property tests (Hypothesis) throw hundreds of random inputs at the maths."""

import random
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apps.scoring.engine import (
    Edge,
    NodeScore,
    OfferingInputs,
    compute_student_profile,
    display,
    normalise,
    propagate,
    weighted_average,
)

# ---------- the professor's example (spec §2.2) ----------

GRADES = {"midterm": D(90), "project": D(80)}
A_TO_LO = [
    Edge("midterm", "LO1", D(60)),
    Edge("project", "LO1", D(40)),
    Edge("midterm", "LO2", D(40)),
    Edge("project", "LO2", D(100)),
]
LO_TO_PO = [
    Edge("LO1", "PO1", D(4)),
    Edge("LO2", "PO1", D(2)),
    Edge("LO2", "PO2", D(5)),
]


def lo_scores(grades=GRADES):
    return {k: v.score for k, v in propagate(grades, A_TO_LO).items() if v.score is not None}


# ---------- golden tests ----------


def test_elif_lo1():
    assert propagate(GRADES, A_TO_LO)["LO1"].score == D(86)


def test_elif_lo2():
    score = propagate(GRADES, A_TO_LO)["LO2"].score
    assert display(score) == "82.9"
    assert abs(score - D(11600) / D(140)) < D("1e-20")  # 82.857142…, not rounded


def test_elif_po1_on_1_to_5_scale():
    po = propagate(lo_scores(), LO_TO_PO)
    assert display(po["PO1"].score) == "85.0"


def test_elif_po2():
    po = propagate(lo_scores(), LO_TO_PO)
    assert display(po["PO2"].score) == "82.9"


def test_brief_rounding_discrepancy():
    """The brief rounded LO 2 to 82 before computing PO 1. That gives 84.7, not 85.0:
    this is why we never round intermediate values (P7)."""
    rounded_too_early = {"LO1": D(86), "LO2": D(82)}
    po = propagate(rounded_too_early, LO_TO_PO)
    assert display(po["PO1"].score) == "84.7"


# ---------- policy tests ----------


def test_missing_grade_is_skipped_not_zero():
    lo = propagate({"midterm": D(90)}, A_TO_LO)
    assert display(lo["LO2"].score) == "90.0"
    assert display(lo["LO2"].coverage * 100) == "28.6"  # 40 / 140


def test_full_coverage_is_exactly_one():
    lo = propagate(GRADES, A_TO_LO)
    assert lo["LO1"].coverage == D(1)
    assert lo["LO2"].coverage == D(1)


def test_no_data_gives_none():
    lo = propagate({}, A_TO_LO)
    assert lo["LO1"] == NodeScore(score=None, coverage=D(0))
    assert display(lo["LO1"].score) == "—"


def test_weighted_average_of_nothing_is_none():
    assert weighted_average([]) is None


@pytest.mark.parametrize("bad", [D(0), D(-1)])
def test_zero_or_negative_weight_raises(bad):
    with pytest.raises(ValueError, match="weight must be positive"):
        propagate(GRADES, [Edge("midterm", "LO1", bad)])


def test_normalise_out_of_20():
    assert normalise(D(17), D(20)) == D(85)


@pytest.mark.parametrize("bad_max", [D(0), D(-5)])
def test_normalise_rejects_zero_max(bad_max):
    with pytest.raises(ValueError, match="max_score must be positive"):
        normalise(D(10), bad_max)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(D("84.95"), "85.0"), (D("84.94"), "84.9"), (D("0"), "0.0"), (D("100"), "100.0"), (None, "—")],
)
def test_display_half_up(value, expected):
    assert display(value) == expected


# ---------- whole-student calculation ----------


def elif_cse311():
    """Offering 311 with the slide example. Assessment ids 1 (midterm) and 2 (project),
    LO ids 11 and 12, PO ids 1 and 2."""
    return OfferingInputs(
        offering_id=311,
        grades={1: D(90), 2: D(80)},
        max_scores={1: D(100), 2: D(100)},
        assessment_lo_edges=(
            Edge(1, 11, D(60)),
            Edge(2, 11, D(40)),
            Edge(1, 12, D(40)),
            Edge(2, 12, D(100)),
        ),
        lo_po_edges=(Edge(11, 1, D(4)), Edge(12, 1, D(2)), Edge(12, 2, D(5))),
    )


def test_profile_reproduces_the_slide():
    profile = compute_student_profile([elif_cse311()])
    assert display(profile.lo_scores[(311, 11)].score) == "86.0"
    assert display(profile.lo_scores[(311, 12)].score) == "82.9"
    assert display(profile.po_scores[1].score) == "85.0"
    assert display(profile.po_scores[2].score) == "82.9"


def test_raw_marks_are_normalised_before_weighting():
    """Same example, but the midterm is marked out of 50: 45/50 is still 90%."""
    off = elif_cse311()
    out_of_50 = OfferingInputs(
        offering_id=off.offering_id,
        grades={1: D(45), 2: D(80)},
        max_scores={1: D(50), 2: D(100)},
        assessment_lo_edges=off.assessment_lo_edges,
        lo_po_edges=off.lo_po_edges,
    )
    profile = compute_student_profile([out_of_50])
    assert display(profile.po_scores[1].score) == "85.0"


def test_two_courses_feed_one_po():
    """P8: one flat weighted average over every LO→PO link from every course.
    Course 321 has one assessment (70/100) feeding LO 21, linked to PO 1 with weight 3.
    Expected PO 1 = (86×4 + 82.857…×2 + 70×3) ÷ (4+2+3) = 719.714… ÷ 9 = 79.968…"""
    cse321 = OfferingInputs(
        offering_id=321,
        grades={5: D(70)},
        max_scores={5: D(100)},
        assessment_lo_edges=(Edge(5, 21, D(100)),),
        lo_po_edges=(Edge(21, 1, D(3)),),
    )
    profile = compute_student_profile([elif_cse311(), cse321])
    expected = (D(86) * 4 + D(11600) / D(140) * 2 + D(70) * 3) / D(9)
    assert abs(profile.po_scores[1].score - expected) < D("1e-20")
    assert display(profile.po_scores[1].score) == "80.0"
    assert display(profile.po_scores[2].score) == "82.9"  # untouched by course 321


def test_lo_keys_do_not_collide_across_offerings():
    """LO id 11 exists in both offerings here; they must stay two separate LOs."""
    other = OfferingInputs(
        offering_id=999,
        grades={7: D(50)},
        max_scores={7: D(100)},
        assessment_lo_edges=(Edge(7, 11, D(100)),),
        lo_po_edges=(Edge(11, 3, D(5)),),
    )
    profile = compute_student_profile([elif_cse311(), other])
    assert profile.lo_scores[(311, 11)].score == D(86)
    assert profile.lo_scores[(999, 11)].score == D(50)
    assert profile.po_scores[3].score == D(50)


def test_contributors_list():
    profile = compute_student_profile([elif_cse311()])
    assert profile.po_contributors[1] == [(311, 11, D(4)), (311, 12, D(2))]
    assert profile.po_contributors[2] == [(311, 12, D(5))]


def test_ungraded_course_gives_po_with_no_score():
    """An in-progress course with nothing graded yet: the PO exists but has score None,
    and coverage 0, never a 0 score (P12)."""
    off = elif_cse311()
    ungraded = OfferingInputs(
        offering_id=off.offering_id,
        grades={},
        max_scores=off.max_scores,
        assessment_lo_edges=off.assessment_lo_edges,
        lo_po_edges=off.lo_po_edges,
    )
    profile = compute_student_profile([ungraded])
    assert profile.po_scores[1] == NodeScore(score=None, coverage=D(0))


def test_no_offerings_gives_empty_profile():
    profile = compute_student_profile([])
    assert profile.lo_scores == {}
    assert profile.po_scores == {}


# ---------- properties (Hypothesis) ----------

scores = st.decimals(min_value=0, max_value=100, places=2)
weights = st.decimals(min_value=1, max_value=100, places=0)
pairs_strategy = st.lists(st.tuples(scores, weights), min_size=1, max_size=12)


def _layer(pairs):
    src = {i: s for i, (s, _) in enumerate(pairs)}
    edges = [Edge(i, "T", w) for i, (_, w) in enumerate(pairs)]
    return src, edges


@given(pairs_strategy)
def test_weighted_average_is_bounded(pairs):
    src, edges = _layer(pairs)
    result = propagate(src, edges)["T"].score
    assert min(src.values()) <= result <= max(src.values())


@given(pairs_strategy, st.decimals(min_value=D("0.01"), max_value=1000, places=2))
def test_scale_invariant(pairs, factor):
    src, edges = _layer(pairs)
    scaled = [Edge(e.source, e.target, e.weight * factor) for e in edges]
    a = propagate(src, edges)["T"].score
    b = propagate(src, scaled)["T"].score
    assert abs(a - b) < D("1e-20")


@given(pairs_strategy, st.randoms(use_true_random=False))
def test_order_independent(pairs, rnd: random.Random):
    src, edges = _layer(pairs)
    shuffled = edges[:]
    rnd.shuffle(shuffled)
    a = propagate(src, edges)["T"].score
    b = propagate(src, shuffled)["T"].score
    assert abs(a - b) < D("1e-20")


@given(pairs_strategy, weights)
def test_neutral_addition(pairs, extra_weight):
    src, edges = _layer(pairs)
    before = propagate(src, edges)["T"].score
    src["extra"] = before
    after = propagate(src, [*edges, Edge("extra", "T", extra_weight)])["T"].score
    assert abs(after - before) < D("1e-20")


@given(pairs_strategy, st.data())
def test_coverage_range(pairs, data):
    src, edges = _layer(pairs)
    keep = data.draw(st.sets(st.sampled_from(sorted(src))))
    partial = {k: v for k, v in src.items() if k in keep}
    coverage = propagate(partial, edges)["T"].coverage
    assert D(0) <= coverage <= D(1)
    assert (coverage == D(1)) == (keep == set(src))
```

### Check it works

```bash
uv run pytest apps/scoring/tests/test_engine.py -q \
  --cov=apps.scoring.engine --cov-branch --cov-report=term-missing
# 31 passed · engine.py 100% (statements and branches)
git log --oneline feature/S1-06-scoring-engine   # the red/green pairs are visible
```

### Done when

- [ ] Golden: 86.0, 82.9, 85.0, 82.9 (tests); 84.7 documents the brief's rounding error
- [ ] P3, P5, P6 (via skipping), P7, P8, P12 each pinned by a test
- [ ] Five Hypothesis properties pass
- [ ] `engine.py` at 100% line and branch coverage; no Django import (`grep -n django apps/scoring/engine.py` prints nothing)
- [ ] Red and green commits separate in the branch history. Merge this PR with a **merge commit** instead of squash, as the one exception to §9.6, so the red/green history survives on `develop` for the report

### Commits and PR

The ten commits from the table above. PR title: `S1-06: Scoring engine, built test-first (#<issue>)`. Put the cycle table in the PR description with links to the red CI runs.

---
## S1-08 · Factories, scenarios and shared fixtures

**Points:** 2 · **Owner:** Person B · **Branch:** `feature/S1-08-scenarios` · **Depends on:** S1-04 · **Merge before S1-07**

### Goal

Realistic test data in one line. The factories already exist (each model story added its own); this story adds the two **scenarios** that most later tests start from, the shared pytest fixtures, and one smoke test that opens every admin page. The spec's backlog calls this "factories for every model"; because factories now grow with each model story (so model PRs can carry their own tests), what's left here is the layer above them.

- `elif_scenario()`: the professor's slide as database rows. Used by the loader tests (S1-07), the student profile (S3-02), publishing (S3-01) and the permission matrix (S2-02).
- `small_department()`: 3 students × 2 offerings in a closed term with hand-checkable numbers, for class and department averages (S3-03, S3-04).

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/core/tests/scenarios.py` | create | `elif_scenario`, `small_department` |
| `conftest.py` (repo root) | create | `client_as`, `elif_data` fixtures |
| `apps/core/tests/test_admin.py` | create | Every admin page opens |

### Steps

**1. Scenarios.** Both scenarios build their **own test program** (`TST…`, via `ProgramFactory`) with its own PO set and POs. They do **not** reuse the real CSE program from the data migration, so a test can never change the official POs or depend on their ids. What callers can rely on: `elif_scenario()` returns `program, po_set, offering, enrollment, student, instructor, midterm, project, lo1, lo2, po1, po2`; `small_department()` returns `program, term, offerings, students, po1, po2`. `published=False` creates the same grades as drafts: the student then has no scores at all, which is how S3-01 proves that publishing is what makes them visible.

**`apps/core/tests/scenarios.py`**

```python
"""Ready-made worlds for tests. elif_scenario() is the professor's slide in one line.

Both scenarios build their OWN test program (via ProgramFactory: code TST0, TST1, ...) with
their own PO set. They never touch the real CSE program created by the data migration, so
tests can't interfere with it or with each other."""

import datetime
from decimal import Decimal as D
from types import SimpleNamespace

from apps.accounts.models import ProgramMembership

from .factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)


def elif_scenario(*, published=True):
    """Offering with 2 assessments, 2 LOs, 2 POs, weights and grades from the professor's
    slide (spec §2.2). With published=True, Elif's profile is PO 1 = 85.0, PO 2 = 82.9.
    With published=False the grades are drafts: her profile has no scores at all."""
    program = ProgramFactory()
    po_set = ProgramOutcomeSetFactory(program=program, effective_from_year=2020)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Knowledge")
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Problem solving")

    instructor = UserFactory(first_name="Ahmet", last_name="Hoca")
    MembershipFactory(user=instructor, program=program, role=ProgramMembership.Role.INSTRUCTOR)
    student = UserFactory(first_name="Elif", last_name="Yıldız", student_number="2024-0041")
    MembershipFactory(user=student, program=program, cohort_year=2024)

    course = CourseFactory(program=program, code="CSE 311", title="Software Engineering")
    offering = OfferingFactory(course=course, term=TermFactory(), instructors=[instructor])
    enrollment = EnrollmentFactory(offering=offering, student=student)

    midterm = AssessmentFactory(offering=offering, name="Midterm", position=1)
    project = AssessmentFactory(offering=offering, name="Project", kind="project", position=2)
    lo1 = LearningOutcomeFactory(offering=offering, number=1)
    lo2 = LearningOutcomeFactory(offering=offering, number=2)

    for assessment, lo, weight in [
        (midterm, lo1, 60),
        (project, lo1, 40),
        (midterm, lo2, 40),
        (project, lo2, 100),
    ]:
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(weight))
    LOPOWeightFactory(learning_outcome=lo1, program_outcome=po1, weight=4)
    LOPOWeightFactory(learning_outcome=lo2, program_outcome=po1, weight=2)
    LOPOWeightFactory(learning_outcome=lo2, program_outcome=po2, weight=5)

    GradeFactory(assessment=midterm, enrollment=enrollment, score=D(90), published=published)
    GradeFactory(assessment=project, enrollment=enrollment, score=D(80), published=published)

    return SimpleNamespace(
        program=program,
        po_set=po_set,
        offering=offering,
        enrollment=enrollment,
        student=student,
        instructor=instructor,
        midterm=midterm,
        project=project,
        lo1=lo1,
        lo2=lo2,
        po1=po1,
        po2=po2,
    )


def small_department():
    """3 students × 2 offerings in one closed term, for aggregate tests (B9, B10).

    Course A: one assessment → LO A1 (weight 100) → PO 1 (weight 5).
    Course B: one assessment → LO B1 (weight 100) → PO 1 (weight 5) and PO 2 (weight 3).
    Published marks: Ali 90/70, Ayşe 60/50, Mert 40/(none)."""
    program = ProgramFactory()
    po_set = ProgramOutcomeSetFactory(program=program)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1)
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2)
    term = TermFactory(
        code="2026S",
        name="Spring 2026",
        starts_on=datetime.date(2026, 2, 9),
        ends_on=datetime.date(2026, 6, 12),
        status="closed",
    )
    students = [
        UserFactory(first_name=name, student_number=f"2024-00{i}")
        for i, name in enumerate(["Ali", "Ayşe", "Mert"], start=1)
    ]
    for s in students:
        MembershipFactory(user=s, program=program, cohort_year=2024)

    offerings, assessments = [], []
    for code, links in [("CSE 101", [(po1, 5)]), ("CSE 102", [(po1, 5), (po2, 3)])]:
        offering = OfferingFactory(course=CourseFactory(program=program, code=code), term=term)
        assessment = AssessmentFactory(offering=offering, name="Final", published=True)
        lo = LearningOutcomeFactory(offering=offering, number=1)
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
        for po, weight in links:
            LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=weight)
        offerings.append(offering)
        assessments.append(assessment)

    marks = {"Ali": (90, 70), "Ayşe": (60, 50), "Mert": (40, None)}
    for s in students:
        for assessment, mark in zip(assessments, marks[s.first_name], strict=True):
            enrollment = EnrollmentFactory(offering=assessment.offering, student=s)
            if mark is not None:
                GradeFactory(
                    assessment=assessment, enrollment=enrollment, score=D(mark), published=True
                )
    return SimpleNamespace(
        program=program, term=term, offerings=offerings, students=students, po1=po1, po2=po2
    )
```

**2. Shared fixtures.** pytest loads `conftest.py` automatically, and its fixtures are available to every test by argument name, with no import. `client_as("instructor")` returns a test client already logged in as a fresh instructor. The permission matrix in S2-02 calls it once per role.

`force_login` skips the password check, so these tests stay fast. The login page itself is tested through the real form in S1-09.

**`conftest.py`**

```python
"""Fixtures every test file can use without importing them."""

import pytest

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario


@pytest.fixture
def client_as(client, db):
    """client_as("instructor") → a test client logged in as a fresh user with that role.

    Accepts "student", "instructor", "head" or "admin". The user is available as
    client.user so the test can attach offerings to them."""

    def login(role, program=None):
        if role == "admin":
            user = UserFactory(is_staff=True, is_superuser=True)
        else:
            user = UserFactory()
            MembershipFactory(
                user=user,
                program=program or ProgramFactory(),
                role=ProgramMembership.Role(role),
            )
        client.force_login(user)
        client.user = user
        return client

    return login


@pytest.fixture
def elif_data(db):
    return elif_scenario()
```

**3. Admin smoke test.** Django checks `list_display` and `search_fields` names only when a page is rendered, so a typo passes `manage.py check` and crashes in the demo. This test opens the list page (with a search, to exercise `search_fields`) and an edit page of every registered model, with the Elif scenario loaded so the pages have rows.

**`apps/core/tests/test_admin.py`**

```python
"""Smoke test: every admin page opens. Catches typos in list_display, search_fields etc.,
which Django only notices when the page is rendered."""

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db

MODELS = [m for m in admin.site._registry if m._meta.app_label not in {"auth"}]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m._meta.label)
def test_admin_changelist_and_change_pages_open(admin_client, model):
    elif_scenario()
    opts = model._meta
    url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
    assert admin_client.get(url, {"q": "x"}).status_code == 200
    obj = model.objects.first()
    if obj is not None:
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
        assert admin_client.get(url).status_code == 200


def test_admin_can_add_a_user(admin_client):
    url = reverse("admin:accounts_user_add")
    assert admin_client.get(url).status_code == 200
    response = admin_client.post(
        url,
        {
            "email": "new@live.acibadem.edu.tr",
            "first_name": "Yeni",
            "last_name": "Kişi",
            "usable_password": "true",
            "password1": "a-long-Password-123",
            "password2": "a-long-Password-123",
            # the membership inline's "management form" (0 rows filled in)
            "memberships-TOTAL_FORMS": "0",
            "memberships-INITIAL_FORMS": "0",
        },
    )
    assert response.status_code == 302
```

### Tests

The scenarios are tested by being used: S1-07's `test_elif_profile_from_the_database` checks that `elif_scenario()` yields 85.0 and 82.9. The admin test above has 18 cases: one per registered model (17), plus adding a user.

### Check it works

```bash
uv run pytest apps/core/tests/test_admin.py -q      # 18 passed
uv run python manage.py shell -c "from apps.core.tests.scenarios import elif_scenario; print(elif_scenario())"
# prints the namespace. Note: this writes to your dev database. Reset with docker compose down -v if you mind.
```

### Done when

- [ ] `elif_scenario()` and `small_department()` used by at least one test each (by the end of Sprint 1: loaders and seed tests)
- [ ] `client_as(role)` works for student, instructor, head, admin
- [ ] Every admin page opens (test)

### Commits and PR

```
Add the Elif and small-department test scenarios (#<issue>)
Add client_as and elif_data fixtures for all tests
Smoke-test every admin page
```

PR title: `S1-08: Test scenarios, shared fixtures, admin smoke test (#<issue>)`

---

## S1-07 · Loaders: database → engine inputs

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S1-07-loaders` · **Depends on:** S1-04, S1-08

### Goal

The engine computes *how* data counts; the loaders decide *which* data counts. `apps/scoring/loaders.py` reads the database into `OfferingInputs` and applies the four policies that are about selecting data rather than arithmetic:

| Policy | Rule in the loader |
|---|---|
| P4 | Only grades with a `published_score`, on a published assessment, and not `published_is_excused`. The draft `score` is never read |
| P9 | One attempt per catalog course: the enrollment whose term started latest. Dropped enrollments never count |
| P10 | Open-term courses are included by default (students want early signal); `include_open_terms=False` keeps closed terms only (department numbers). Planned terms never count |
| P13 | LO→PO links only count for POs in the student's PO set (newest set with `effective_from_year` ≤ cohort year; fallback: the active set) |

> **P9 and "completed".** Spec §2.3 says "latest *completed* attempt"; the Sprint 1 how-to note says "latest offering … with status `enrolled`". Combined with P10 these agree: with `include_open_terms=False` (department view) only closed terms are seen, so the latest attempt *is* the latest completed one. On a student's own profile (open terms included), a retake in progress replaces the old attempt and shows its coverage, so the student sees where they stand now.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/catalog/selectors.py` | create | `active_po_set`, `po_set_ids_for_students`, `po_set_for_student` |
| `apps/scoring/loaders.py` | create | `load_student_inputs`, `load_offering_inputs` |
| `apps/catalog/tests/test_selectors.py`, `apps/scoring/tests/test_loaders.py` | create | |

### Steps

**1. PO-set selectors (P13).** `po_set_ids_for_students` does the P13 decision for many students in two queries (all the program's sets, all the students' cohort years) and picks in Python. A class page with 80 students would otherwise make 160 queries. `po_set_for_student` is the one-student convenience from the code map, built on it.

**`apps/catalog/selectors.py`**

```python
"""Read-only queries for the catalog. Later sprints add offerings_for_user,
visible_enrollments and setup_status here (spec §4.8)."""

from apps.accounts.models import ProgramMembership

from .models import ProgramOutcomeSet


def active_po_set(program):
    """The program's active PO set. The partial unique index guarantees at most one."""
    return ProgramOutcomeSet.objects.get(program=program, is_active=True)


def po_set_ids_for_students(student_ids, program):
    """Policy P13 for many students at once: {student_id: po_set_id}.

    Candidates are the active set and the older sets it replaced. A set that is newer than
    the active one (or as new) and not active is a draft being edited: it counts only once
    the head activates it. A student gets the newest candidate whose effective_from_year is
    <= their cohort year; a cohort older than every candidate gets the oldest one; a student
    without a cohort year gets the active set."""
    sets = list(
        ProgramOutcomeSet.objects.filter(program=program)
        .order_by("-effective_from_year", "-id")
        .values_list("id", "effective_from_year", "is_active")
    )

    active = [(set_id, year) for set_id, year, is_active in sets if is_active]
    if not active:
        raise ProgramOutcomeSet.DoesNotExist(f"{program} has no active PO set")
    active_id, active_year = active[0]
    candidates = [
        (set_id, year) for set_id, year, is_active in sets if is_active or year < active_year
    ]

    cohorts = dict(
        ProgramMembership.objects.filter(
            user_id__in=student_ids,
            program=program,
            role=ProgramMembership.Role.STUDENT,
        ).values_list("user_id", "cohort_year")
    )

    def pick(cohort_year):
        if cohort_year is None:
            return active_id
        for set_id, year in candidates:
            if year <= cohort_year:
                return set_id
        return candidates[-1][0]  # older than every set: the oldest one (P13)

    return {student_id: pick(cohorts.get(student_id)) for student_id in student_ids}


def po_set_for_student(student, program):
    """The PO set one student's profile is shown against (P13)."""
    set_id = po_set_ids_for_students([student.id], program)[student.id]
    return ProgramOutcomeSet.objects.get(pk=set_id)
```

**2. Loaders.** The loader never builds one query per offering or per student: it collects the offering ids first, then fetches all grades, all max scores, and both edge sets in one query each (`values_list` returns tuples, not model objects, which is faster and all the engine needs). A test pins this with a query budget.

**`apps/scoring/loaders.py`**

```python
"""Turn database rows into the engine's plain dataclasses (spec §2.4).

This is the only place that decides WHICH data counts. The engine decides HOW it counts.
Policies applied here:
  P4  only published grades count (excused ones are skipped)
  P9  retakes: only the latest attempt at each catalog course counts
  P10 in-progress (open-term) courses are included unless include_open_terms=False
  P13 LO→PO links only count for POs in the student's PO set
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import F

from apps.catalog.models import Enrollment, Term
from apps.catalog.selectors import po_set_ids_for_students
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight

from .engine import Edge, OfferingInputs


def _counted_enrollments(student, *, include_open_terms, up_to_term):
    qs = Enrollment.objects.filter(
        student=student, status=Enrollment.Status.ENROLLED
    ).select_related("offering__course__program", "offering__term")
    if include_open_terms:
        qs = qs.exclude(offering__term__status=Term.Status.PLANNED)
    else:
        qs = qs.filter(offering__term__status=Term.Status.CLOSED)
    if up_to_term is not None:
        qs = qs.filter(offering__term__starts_on__lte=up_to_term.starts_on)

    # P9: keep the latest attempt per catalog course (latest term start date wins)
    latest = {}
    for enrollment in qs.order_by("offering__term__starts_on", "offering_id"):
        latest[enrollment.offering.course_id] = enrollment
    return list(latest.values())


def _published_grades(enrollment_ids):
    """Published scores, and the assessments each enrollment is excused from (P6).

    Only grades whose assessment belongs to the enrollment's own offering count: a grade
    pointing at another course's assessment (possible through the admin) is ignored."""
    rows = Grade.objects.filter(
        enrollment_id__in=enrollment_ids,
        assessment__published_at__isnull=False,
        assessment__offering_id=F("enrollment__offering_id"),
    ).values_list("enrollment_id", "assessment_id", "published_score", "published_is_excused")
    grades = defaultdict(dict)
    excused = defaultdict(set)
    for enrollment_id, assessment_id, score, is_excused in rows:
        if is_excused:
            excused[enrollment_id].add(assessment_id)
        elif score is not None:
            grades[enrollment_id][assessment_id] = score
    return grades, excused


def _offering_structure(offering_ids):
    """Max scores and both edge sets for many offerings, in three queries."""
    max_scores = defaultdict(dict)
    for offering_id, assessment_id, max_score in Assessment.objects.filter(
        offering_id__in=offering_ids
    ).values_list("offering_id", "id", "max_score"):
        max_scores[offering_id][assessment_id] = max_score

    a_lo = defaultdict(list)
    for offering_id, assessment_id, lo_id, weight in AssessmentLOWeight.objects.filter(
        assessment__offering_id__in=offering_ids
    ).values_list("assessment__offering_id", "assessment_id", "learning_outcome_id", "weight"):
        a_lo[offering_id].append(Edge(assessment_id, lo_id, weight))

    lo_po = defaultdict(list)  # offering_id -> [(po_set_id, Edge)]
    for offering_id, lo_id, po_id, po_set_id, weight in LOPOWeight.objects.filter(
        learning_outcome__offering_id__in=offering_ids
    ).values_list(
        "learning_outcome__offering_id",
        "learning_outcome_id",
        "program_outcome_id",
        "program_outcome__po_set_id",
        "weight",
    ):
        lo_po[offering_id].append((po_set_id, Edge(lo_id, po_id, Decimal(weight))))
    return max_scores, a_lo, lo_po


def _inputs(offering_id, grades, excused, max_scores, a_lo, lo_po, po_set_id):
    return OfferingInputs(
        offering_id=offering_id,
        grades=grades,
        excused=frozenset(excused),
        max_scores=max_scores[offering_id],
        assessment_lo_edges=tuple(a_lo[offering_id]),
        lo_po_edges=tuple(edge for set_id, edge in lo_po[offering_id] if set_id == po_set_id),
    )


def load_student_inputs(student, *, include_open_terms=True, up_to_term=None):
    enrollments = _counted_enrollments(
        student, include_open_terms=include_open_terms, up_to_term=up_to_term
    )
    if not enrollments:
        return []
    offering_ids = [e.offering_id for e in enrollments]
    grades, excused = _published_grades([e.id for e in enrollments])
    max_scores, a_lo, lo_po = _offering_structure(offering_ids)

    po_sets = {}
    result = []
    for e in sorted(enrollments, key=lambda e: e.offering_id):
        program = e.offering.course.program
        if program.id not in po_sets:
            po_sets[program.id] = po_set_ids_for_students([student.id], program)[student.id]
        result.append(
            _inputs(
                e.offering_id,
                grades[e.id],
                excused[e.id],
                max_scores,
                a_lo,
                lo_po,
                po_sets[program.id],
            )
        )
    return result


def load_offering_inputs(offering):
    enrollments = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
    )
    if not enrollments:
        return {}
    grades, excused = _published_grades([e.id for e in enrollments])
    max_scores, a_lo, lo_po = _offering_structure([offering.id])
    program = offering.course.program

    po_set_ids = po_set_ids_for_students([e.student_id for e in enrollments], program)
    return {
        e.id: _inputs(
            offering.id,
            grades[e.id],
            excused[e.id],
            max_scores,
            a_lo,
            lo_po,
            po_set_ids[e.student_id],
        )
        for e in enrollments
    }
```

### Tests

Each policy has a test that would fail if the policy were removed, using `elif_scenario()` plus small additions. The retake test shows the number that the *wrong* behaviour would give (61.4) in a comment, so a reader sees what's at stake.

**`apps/scoring/tests/test_loaders.py`**

```python
"""Loader tests: the policies that decide WHICH data reaches the engine (P4, P9, P10, P13).
These hit the database, so they use pytest-django's `db` fixture (via elif_data)."""

import datetime
from decimal import Decimal as D

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_offering_inputs, load_student_inputs

pytestmark = pytest.mark.django_db

SPRING_2026 = {
    "code": "2026S",
    "name": "Spring 2026",
    "starts_on": datetime.date(2026, 2, 9),
    "ends_on": datetime.date(2026, 6, 12),
    "status": Term.Status.CLOSED,
}


def profile_of(student, **kwargs):
    return compute_student_profile(load_student_inputs(student, **kwargs))


def add_simple_offering(program, po, student, *, term, mark, code="MAT 241", weight=5):
    """A one-assessment, one-LO course for `student`, linked to `po`."""
    offering = OfferingFactory(course=CourseFactory(program=program, code=code), term=term)
    assessment = AssessmentFactory(offering=offering, name="Final")
    lo = LearningOutcomeFactory(offering=offering, number=1)
    AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=weight)
    enrollment = EnrollmentFactory(offering=offering, student=student)
    GradeFactory(assessment=assessment, enrollment=enrollment, score=D(mark), published=True)
    return offering


def test_elif_profile_from_the_database(elif_data):
    """The end-to-end check of Sprint 1: database → loader → engine → slide numbers."""
    profile = profile_of(elif_data.student)
    assert display(profile.po_scores[elif_data.po1.id].score) == "85.0"
    assert display(profile.po_scores[elif_data.po2.id].score) == "82.9"


def test_loader_builds_the_expected_inputs(elif_data):
    [inputs] = load_student_inputs(elif_data.student)
    assert inputs.offering_id == elif_data.offering.id
    assert inputs.grades == {elif_data.midterm.id: D(90), elif_data.project.id: D(80)}
    assert inputs.max_scores == {elif_data.midterm.id: D(100), elif_data.project.id: D(100)}
    assert len(inputs.assessment_lo_edges) == 4
    assert len(inputs.lo_po_edges) == 3


def test_draft_grades_are_invisible():
    """P4: unpublished grades never reach the engine."""
    data = elif_scenario(published=False)
    profile = profile_of(data.student)
    assert profile.po_scores[data.po1.id].score is None


def test_edited_published_grade_shows_old_value_until_republished(elif_data):
    """P4: the loader reads published_score, not the draft score."""
    grade = elif_data.enrollment.grades.get(assessment=elif_data.midterm)
    grade.score = D(10)  # instructor edits, does not publish yet
    grade.save()
    [inputs] = load_student_inputs(elif_data.student)
    assert inputs.grades[elif_data.midterm.id] == D(90)


def test_excused_published_grade_is_skipped(elif_data):
    """P6: excused grades are left out, like missing ones."""
    grade = elif_data.enrollment.grades.get(assessment=elif_data.project)
    grade.published_is_excused = True
    grade.save()
    [inputs] = load_student_inputs(elif_data.student)
    assert elif_data.project.id not in inputs.grades
    profile = compute_student_profile([inputs])
    assert display(profile.po_scores[elif_data.po2.id].score) == "90.0"  # midterm only
    # the excused project drops out of coverage too, so the LO isn't "incomplete" forever
    assert profile.lo_scores[(elif_data.offering.id, elif_data.lo2.id)].coverage == 1


def test_grade_for_another_courses_assessment_is_ignored(elif_data):
    """A grade whose assessment belongs to a different offering (only possible through the
    admin) must not crash the profile or count anywhere."""
    other = AssessmentFactory(max_score=D(100))
    GradeFactory(assessment=other, enrollment=elif_data.enrollment, score=D(10), published=True)
    [inputs] = load_student_inputs(elif_data.student)
    assert other.id not in inputs.grades
    profile = compute_student_profile([inputs])
    assert display(profile.po_scores[elif_data.po1.id].score) == "85.0"


def test_dropped_enrollment_does_not_count(elif_data):
    elif_data.enrollment.status = "dropped"
    elif_data.enrollment.save()
    assert load_student_inputs(elif_data.student) == []


def test_retake_latest_attempt_counts(elif_data):
    """P9: Elif failed MAT 241 in Spring 2026 (40) and retook it in Fall 2026 (80).
    Only the Fall attempt reaches the engine."""
    program, po2, student = elif_data.program, elif_data.po2, elif_data.student
    course = CourseFactory(program=program, code="MAT 241")
    spring = TermFactory(**SPRING_2026)
    for term, mark in [(spring, 40), (elif_data.offering.term, 80)]:
        offering = OfferingFactory(course=course, term=term)
        assessment = AssessmentFactory(offering=offering, name="Final")
        lo = LearningOutcomeFactory(offering=offering, number=1)
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
        LOPOWeightFactory(learning_outcome=lo, program_outcome=po2, weight=5)
        enrollment = EnrollmentFactory(offering=offering, student=student)
        GradeFactory(assessment=assessment, enrollment=enrollment, score=D(mark), published=True)

    inputs = load_student_inputs(student)
    assert len(inputs) == 2  # CSE 311 + the latest MAT 241 only
    profile = compute_student_profile(inputs)
    # PO 2 = (82.857… × 5 + 80 × 5) ÷ 10 = 81.43; the old 40 would have given 61.4
    assert display(profile.po_scores[po2.id].score) == "81.4"


def test_open_terms_can_be_excluded(elif_data):
    """P10: department numbers use closed terms only. Elif's CSE 311 is in an open term."""
    add_simple_offering(
        elif_data.program,
        elif_data.po2,
        elif_data.student,
        term=TermFactory(**SPRING_2026),
        mark=70,
    )
    assert len(load_student_inputs(elif_data.student)) == 2
    closed_only = load_student_inputs(elif_data.student, include_open_terms=False)
    assert len(closed_only) == 1
    profile = compute_student_profile(closed_only)
    assert display(profile.po_scores[elif_data.po2.id].score) == "70.0"
    assert elif_data.po1.id not in profile.po_scores


def test_planned_terms_never_count(elif_data):
    planned = TermFactory(
        code="2027S",
        name="Spring 2027",
        starts_on=datetime.date(2027, 2, 8),
        ends_on=datetime.date(2027, 6, 11),
        status=Term.Status.PLANNED,
    )
    add_simple_offering(elif_data.program, elif_data.po2, elif_data.student, term=planned, mark=10)
    assert len(load_student_inputs(elif_data.student)) == 1


def test_up_to_term_cuts_later_terms(elif_data):
    """Used by the trend chart (T1.5): the profile as it was at the end of Spring 2026."""
    spring = TermFactory(**SPRING_2026)
    maths = add_simple_offering(
        elif_data.program, elif_data.po2, elif_data.student, term=spring, mark=70
    )
    inputs = load_student_inputs(elif_data.student, up_to_term=spring)
    assert [i.offering_id for i in inputs] == [maths.id]


def test_po_set_follows_cohort(elif_data):
    """P13: the head activates a 2026 curriculum with a new PO. Elif (cohort 2023) keeps the
    old set, so links to the new set's PO are ignored for her; a 2026 student gets the new set."""
    elif_data.po_set.is_active = False
    elif_data.po_set.save()
    new_set = ProgramOutcomeSetFactory(
        program=elif_data.program,
        label="2026 curriculum",
        effective_from_year=2026,
        is_active=True,
    )
    new_po = ProgramOutcomeFactory(po_set=new_set, number=1)
    LOPOWeightFactory(learning_outcome=elif_data.lo1, program_outcome=new_po, weight=5)

    elif_profile = profile_of(elif_data.student)
    assert new_po.id not in elif_profile.po_scores
    assert display(elif_profile.po_scores[elif_data.po1.id].score) == "85.0"

    newcomer = UserFactory()
    MembershipFactory(user=newcomer, program=elif_data.program, cohort_year=2026)
    enrollment = EnrollmentFactory(offering=elif_data.offering, student=newcomer)
    GradeFactory(assessment=elif_data.midterm, enrollment=enrollment, score=D(50), published=True)
    newcomer_profile = profile_of(newcomer)
    assert set(newcomer_profile.po_scores) == {new_po.id}


def test_offering_inputs_cover_the_whole_class(elif_data):
    classmate = UserFactory()
    MembershipFactory(user=classmate, program=elif_data.program, cohort_year=2023)
    enrollment = EnrollmentFactory(offering=elif_data.offering, student=classmate)
    GradeFactory(assessment=elif_data.midterm, enrollment=enrollment, score=D(70), published=True)

    by_enrollment = load_offering_inputs(elif_data.offering)
    assert set(by_enrollment) == {elif_data.enrollment.id, enrollment.id}
    assert by_enrollment[enrollment.id].grades == {elif_data.midterm.id: D(70)}


def test_offering_inputs_of_empty_class(db):
    assert load_offering_inputs(OfferingFactory()) == {}


def test_student_loader_query_count(elif_data, django_assert_max_num_queries):
    """Four offerings must not mean four times the queries: the loader batches."""
    spring = TermFactory(**SPRING_2026)
    for code in ["MAT 141", "PHY 101", "CSE 102"]:
        add_simple_offering(
            elif_data.program, elif_data.po1, elif_data.student, term=spring, mark=60, code=code
        )
    with django_assert_max_num_queries(7):
        inputs = load_student_inputs(elif_data.student)
    assert len(inputs) == 4
```

**`apps/catalog/tests/test_selectors.py`**

```python
import pytest

from apps.catalog.selectors import po_set_for_student, po_set_ids_for_students
from apps.core.tests.factories import (
    MembershipFactory,
    ProgramFactory,
    ProgramOutcomeSetFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_po_set_fallbacks():
    program = ProgramFactory()
    old = ProgramOutcomeSetFactory(program=program, effective_from_year=2020, is_active=False)
    new = ProgramOutcomeSetFactory(program=program, effective_from_year=2026, is_active=True)
    veteran = UserFactory()
    MembershipFactory(user=veteran, program=program, cohort_year=2019)  # older than every set
    stranger = UserFactory()  # no membership at all
    mid = UserFactory()
    MembershipFactory(user=mid, program=program, cohort_year=2022)

    ids = po_set_ids_for_students([veteran.id, stranger.id, mid.id], program)
    assert ids == {veteran.id: old.id, stranger.id: new.id, mid.id: old.id}
    assert po_set_for_student(mid, program) == old


def test_draft_set_does_not_count_until_activated():
    program = ProgramFactory()
    active = ProgramOutcomeSetFactory(program=program, effective_from_year=2020, is_active=True)
    ProgramOutcomeSetFactory(program=program, effective_from_year=2024, is_active=False)  # draft
    student = UserFactory()
    MembershipFactory(user=student, program=program, cohort_year=2024)
    assert po_set_ids_for_students([student.id], program) == {student.id: active.id}


def test_program_without_active_set_is_an_error():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=False)
    with pytest.raises(Exception, match="no active PO set"):
        po_set_ids_for_students([1], program)
```

### Check it works

The Sprint 1 checkpoint, in the shell, with your own data (or wait for S1-10 and use the seeded Elif):

```bash
uv run python manage.py shell
```

```python
>>> from apps.core.tests.scenarios import elif_scenario
>>> from apps.scoring.engine import compute_student_profile, display
>>> from apps.scoring.loaders import load_student_inputs
>>> d = elif_scenario()
>>> p = compute_student_profile(load_student_inputs(d.student))
>>> display(p.po_scores[d.po1.id].score), display(p.po_scores[d.po2.id].score)
('85.0', '82.9')
```

### Done when

- [ ] Database → engine reproduces 85.0 / 82.9 (test)
- [ ] P4, P6, P9, P10, P13 each pinned by a test; dropped and planned excluded (tests)
- [ ] Query count bounded: 4 offerings in ≤ 7 queries (test)
- [ ] `loaders.py` and `selectors.py` ≥ 95% covered

### Commits and PR

```
Load a student's published, latest-attempt data for the engine (#<issue>)
Resolve each student's PO set from their cohort (P13)
Load a whole class in one pass
Test every data-selection policy against the database
```

PR title: `S1-07: Loaders from the database to the engine (#<issue>)`

---
## S1-09 · Base template, design tokens, `|score`, components, login page

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S1-09-design-system` · **Depends on:** S0-03 (no models needed)

### Goal

Every page from Sprint 2 on extends one base template and prints numbers the same way. This story delivers the layout (navbar, messages as toasts, light and dark mode), the colour tokens from spec §8.2, the four first components (`score_badge`, `coverage_bar`, `empty_state`, `toast`), the template filters (`|score`, `|pct`, `|weight`, `{% query_transform %}`), a `/styleguide/` page to check them by eye, and the login page so `LOGIN_URL = "accounts:login"` resolves. S2-01 later replaces the login view with our own form and adds password reset and role-aware navigation; the URL names stay the same.

### Files

| Path | Create / modify | What |
|---|---|---|
| `static/vendor/*` | create | Pinned Bootstrap 5.3.8, htmx 2.0.11, Chart.js 4.5.1 |
| `static/css/polaris.css`, `static/js/polaris.js` | create | Tokens, components; theme toggle, toasts |
| `templates/base.html` | create | Layout |
| `templates/includes/{score_badge,coverage_bar,empty_state,toast}.html` | create | Components |
| `apps/core/templatetags/{__init__,polaris}.py` | create | Filters |
| `apps/core/views.py`, `apps/core/templates/core/{home,styleguide}.html` | modify / create | Placeholder home, style guide |
| `apps/accounts/urls.py`, `apps/accounts/templates/accounts/login.html` | create | `accounts:login`, `accounts:logout` |
| `config/urls.py` | modify | `home`, `styleguide`, accounts URLs |
| `apps/core/tests/test_design_system.py`, `apps/core/tests/test_views.py` | create / modify | |

### Steps

**1. Vendor the front-end libraries.** Pinned copies in the repo, no CDN at runtime: the final demo must work on the classroom Wi-Fi, and a CDN outage the morning of a checkpoint is not a risk worth taking (spec §4.8). These URLs were checked while writing this guide.

```bash
cd static/vendor
curl -fsSLO https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css
curl -fsSLO https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js
curl -fsSLO https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js
curl -fsSLO https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js
rm -f .gitkeep && cd ../..
```

**2. Design tokens.** Spec §8.2's semantic colours as CSS custom properties, each defined for light **and** dark mode. Components use `var(--pl-attained)` etc., never a hex code, so a colour change is one line and dark mode comes free. Bootstrap's own `--bs-primary` is pointed at our navy. Every state that has a colour also has a symbol or text (✓, ↓, —, ●), because about 1 in 12 men can't tell red from green.

| Token | Meaning |
|---|---|
| `--pl-primary` | navy: actions, links |
| `--pl-accent` | amber: highlights, focus ring |
| `--pl-attained` | green: score ≥ threshold |
| `--pl-below` | red: score < threshold |
| `--pl-none` | grey: no evidence |
| `--pl-draft` | amber dot: unpublished change |
| `--pl-ai` | violet: AI-suggested value |
| `--pl-derived` | teal: value derived by rule |
| `--pl-document` | blue: value read from the document |

**`static/css/polaris.css`**

```css
/* POlaris design tokens (spec §8.2). Bootstrap does the heavy lifting; this file only adds
   our colours and the few components Bootstrap lacks. Use the variables, never raw hex. */

:root {
  --pl-primary: #1f3a68;         /* navy: actions */
  --pl-accent: #e0a100;          /* amber: highlights */
  --pl-attained: #1e7b4a;        /* green: score >= threshold */
  --pl-below: #b42318;           /* red: score < threshold */
  --pl-none: #6c737f;            /* grey: no evidence */
  --pl-draft: #c27c00;           /* amber dot: unpublished change */
  --pl-ai: #6941c6;              /* violet: AI-suggested */
  --pl-derived: #0e7c86;         /* teal: derived by rule */
  --pl-document: #1d5fd1;        /* blue: read from the document */
  --pl-surface: #ffffff;
  --pl-border: #d8dde6;

  --bs-primary: var(--pl-primary);
  --bs-primary-rgb: 31, 58, 104;
  --bs-link-color: var(--pl-primary);
  --bs-link-color-rgb: 31, 58, 104;
}

[data-bs-theme="dark"] {
  --pl-primary: #8fb3ff;
  --pl-accent: #f5c04a;
  --pl-attained: #5fd39a;
  --pl-below: #ff8a80;
  --pl-none: #a3abb8;
  --pl-draft: #f5c04a;
  --pl-ai: #b9a3ff;
  --pl-derived: #5fd4de;
  --pl-document: #8fb3ff;
  --pl-surface: #1b1f27;
  --pl-border: #343b48;

  --bs-primary-rgb: 143, 179, 255;
  --bs-link-color: var(--pl-primary);
  --bs-link-color-rgb: 143, 179, 255;
}

.btn-primary {
  --bs-btn-bg: var(--pl-primary);
  --bs-btn-border-color: var(--pl-primary);
  --bs-btn-hover-bg: color-mix(in srgb, var(--pl-primary) 85%, black);
  --bs-btn-hover-border-color: color-mix(in srgb, var(--pl-primary) 85%, black);
}
[data-bs-theme="dark"] .btn-primary { --bs-btn-color: #10141b; }

/* Digits line up in every score column */
.pl-num, .pl-num td, .pl-badge, .pl-coverage-label { font-variant-numeric: tabular-nums; }

.pl-navbar { border-bottom: 1px solid var(--pl-border); background: var(--pl-surface); }
.pl-accent { color: var(--pl-accent); }

/* score_badge */
.pl-badge {
  display: inline-block; min-width: 4.5rem; padding: .15rem .5rem; border-radius: .375rem;
  font-weight: 600; text-align: right; border: 1px solid currentColor;
}
.pl-badge-ok { color: var(--pl-attained); }
.pl-badge-low { color: var(--pl-below); }
.pl-badge-none { color: var(--pl-none); text-align: center; }

/* coverage_bar */
.pl-coverage { display: flex; align-items: center; gap: .5rem; }
.pl-coverage .progress { flex: 1; height: .5rem; }
.pl-coverage .progress-bar { background: var(--pl-primary); }
.pl-coverage-label { font-size: .8rem; color: var(--pl-none); min-width: 2.75rem; text-align: right; }

/* state chips (grids, wizard) */
.pl-chip { padding: .1rem .5rem; border-radius: 1rem; font-size: .85rem; border: 1px solid currentColor; }
.pl-chip-draft { color: var(--pl-draft); }
.pl-chip-ai { color: var(--pl-ai); }
.pl-chip-derived { color: var(--pl-derived); }
.pl-chip-document { color: var(--pl-document); }

/* empty_state */
.pl-empty { padding: 3rem 1rem; border: 1px dashed var(--pl-border); border-radius: .75rem; }
.pl-empty-mark { font-size: 2rem; color: var(--pl-accent); }

/* toasts: a coloured edge per message level */
.pl-toast { border-left: 4px solid var(--pl-primary); }
.pl-toast-success { border-left-color: var(--pl-attained); }
.pl-toast-error { border-left-color: var(--pl-below); }
.pl-toast-warning { border-left-color: var(--pl-draft); }

/* keyboard focus must always be visible */
:focus-visible { outline: 3px solid var(--pl-accent); outline-offset: 2px; }
```

**3. A little JavaScript.** Only two jobs for now: the theme toggle (remembered in `localStorage`, wrapped in `try` because private windows can block it) and showing Django messages as Bootstrap toasts, including toasts that arrive inside an HTMX response.

**`static/js/polaris.js`**

```javascript
// POlaris front-end glue. No framework: Bootstrap + HTMX do the work.
// Later stories add grid keyboard navigation (S2-06) and chart helpers (S3-02).
(function () {
  "use strict";

  // Theme toggle (light / dark), remembered per browser.
  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-pl-theme-toggle]")) return;
    var root = document.documentElement;
    var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    try { localStorage.setItem("pl-theme", next); } catch (e) { /* private mode: ignore */ }
  });

  // Show any toasts the server rendered (Django messages), including ones HTMX swaps in.
  function showToasts(root) {
    root.querySelectorAll(".toast:not(.show)").forEach(function (el) {
      bootstrap.Toast.getOrCreateInstance(el).show();
    });
  }
  document.addEventListener("DOMContentLoaded", function () { showToasts(document); });
  document.body.addEventListener("htmx:afterSwap", function (event) { showToasts(event.target); });
})();
```

**4. The base template.** Three details: the inline script sets the theme *before* the page paints (no white flash for dark-mode users); `hx-headers` on `<body>` sends the CSRF token with every HTMX request, so `hx-post` works without extra code (spec §8.5); and the toast container is `aria-live`, so screen readers announce messages.

**`templates/base.html`**

```html
{% load static %}<!doctype html>
<html lang="en" data-bs-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}POlaris{% endblock %} · POlaris</title>
  <link rel="stylesheet" href="{% static 'vendor/bootstrap.min.css' %}">
  <link rel="stylesheet" href="{% static 'css/polaris.css' %}">
  <script>
    // Set the theme before the page paints, so dark-mode users never see a white flash.
    (function () {
      var saved = null;
      try { saved = localStorage.getItem("pl-theme"); } catch (e) {}
      var dark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
    })();
  </script>
  {% block head %}{% endblock %}
</head>
{# Every HTMX request sends the CSRF token in a header, so hx-post just works (§8.5). #}
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  <a class="visually-hidden-focusable" href="#main">Skip to content</a>

  <nav class="navbar navbar-expand-md pl-navbar">
    <div class="container-fluid">
      <a class="navbar-brand fw-semibold" href="{% url 'home' %}">PO<span class="pl-accent">laris</span></a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#pl-nav"
              aria-controls="pl-nav" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="pl-nav">
        {# S2-01 fills this block with role-aware links from the navigation context processor. #}
        <ul class="navbar-nav me-auto">{% block nav %}{% endblock %}</ul>
        <ul class="navbar-nav align-items-md-center gap-2">
          <li class="nav-item">
            <button type="button" class="btn btn-sm btn-outline-secondary" data-pl-theme-toggle
                    aria-label="Switch between light and dark mode">◐ Theme</button>
          </li>
          {% if user.is_authenticated %}
            <li class="nav-item"><span class="navbar-text small">{{ user.get_full_name|default:user.email }}</span></li>
            {% if user.is_superuser %}
              <li class="nav-item"><a class="nav-link" href="{% url 'admin:index' %}">Admin</a></li>
            {% endif %}
          {% endif %}
        </ul>
      </div>
    </div>
  </nav>

  <main id="main" class="container-xxl py-4">
    {% block breadcrumbs %}{% endblock %}
    {% block content %}{% endblock %}
  </main>

  {# Django messages become toasts. aria-live makes screen readers announce them. #}
  <div class="toast-container position-fixed bottom-0 end-0 p-3" aria-live="polite" aria-atomic="true" id="pl-toasts">
    {% for message in messages %}
      {% include "includes/toast.html" with message=message only %}
    {% endfor %}
  </div>

  {# One shared modal. HTMX loads confirmation bodies into #modal-content (§8.5 "Modal content"). #}
  <div class="modal fade" id="modal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content" id="modal-content"></div>
    </div>
  </div>

  <script src="{% static 'vendor/bootstrap.bundle.min.js' %}"></script>
  <script src="{% static 'vendor/htmx.min.js' %}"></script>
  {# Chart.js on every page for now. S7-07 makes it opt-in per page to speed up the rest. #}
  {% block chart_js %}<script src="{% static 'vendor/chart.umd.min.js' %}"></script>{% endblock %}
  <script src="{% static 'js/polaris.js' %}"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

**5. Template filters.** `|score` is the **only** way a score is printed (spec §8.2, P7), and it calls `engine.display()`, so the rounding rule lives in exactly one function in the whole codebase. It accepts anything number-like and shows "—" for `None`, empty or garbage, rather than crashing a page.

**`apps/core/templatetags/polaris.py`**

```python
"""Template filters every page uses. Load with {% load polaris %}.

The |score filter is the ONLY way a score is printed (spec §8.2, policy P7): one decimal,
half-up, and an em dash for "no evidence". It reuses engine.display so the rounding rule
lives in exactly one place."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

from apps.scoring.engine import display

register = template.Library()


def _to_decimal(value):
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@register.filter
def score(value):
    """86 → "86.0", Decimal("84.95") → "85.0", None → "—"."""
    return display(_to_decimal(value))


@register.filter
def pct(value):
    """A 0..1 share as a whole percentage: Decimal("0.2857") → "29%", None → "—"."""
    value = _to_decimal(value)
    if value is None:
        return "—"
    return f"{(value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"


@register.filter
def weight(value):
    """A weight without trailing zeros: Decimal("40.00") → "40", Decimal("12.50") → "12.5"."""
    value = _to_decimal(value)
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    return text


@register.simple_tag(takes_context=True)
def query_transform(context, **changes):
    """Rebuild the current query string with some keys changed, for filter links:
    <a href="?{% query_transform term='2026F' %}">. A value of None removes the key."""
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
```

**6. Components.** Each include is used with `only`, so it sees exactly the parameters passed and nothing from the surrounding page. That makes each component's inputs explicit:

| Include | Parameters |
|---|---|
| `includes/score_badge.html` | `value` (Decimal or None), `threshold` (Decimal or None: without it, a plain badge) |
| `includes/coverage_bar.html` | `coverage` (0..1 Decimal or None) |
| `includes/empty_state.html` | `title` (required), `message`, `action_url`, `action_label` (all optional; the button appears only with `action_url`) |
| `includes/toast.html` | `message` (a Django message) |

Example: `{% include "includes/empty_state.html" with title="No learning outcomes yet" message="Add your first LO, or upload your syllabus." action_url=url action_label="Add an LO" only %}`.

**`templates/includes/score_badge.html`**

```html
{% load polaris %}{% comment %}
  Usage: {% include "includes/score_badge.html" with value=po.score threshold=program.attainment_threshold only %}
  Colour AND a text label, so the state is clear without colour (accessibility, §8.2).
{% endcomment %}{% if value is None %}<span class="pl-badge pl-badge-none" title="No evidence yet">— <span class="visually-hidden">no evidence yet</span></span>{% elif threshold is not None and value >= threshold %}<span class="pl-badge pl-badge-ok">✓ {{ value|score }}<span class="visually-hidden"> attained</span></span>{% elif threshold is not None %}<span class="pl-badge pl-badge-low">↓ {{ value|score }}<span class="visually-hidden"> below threshold</span></span>{% else %}<span class="pl-badge">{{ value|score }}</span>{% endif %}
```

**`templates/includes/coverage_bar.html`**

```html
{% load polaris %}{% comment %}
  Usage: {% include "includes/coverage_bar.html" with coverage=node.coverage only %}
  coverage is a 0..1 Decimal (policy P5): how much of the inbound weight had a grade.
{% endcomment %}<div class="pl-coverage" title="Coverage {{ coverage|pct }}: share of the weight with a published grade">
  <div class="progress" role="progressbar" aria-label="Coverage" aria-valuemin="0" aria-valuemax="100"
       aria-valuenow="{{ coverage|pct|cut:'%'|cut:'—' }}">
    <div class="progress-bar" style="width: {{ coverage|pct|cut:'—' }}"></div>
  </div>
  <span class="pl-coverage-label">{{ coverage|pct }}</span>
</div>
```

**`templates/includes/empty_state.html`**

```html
{% comment %}
  Usage: {% include "includes/empty_state.html" with title="No learning outcomes yet" message="Add your first LO, or upload your syllabus and we'll read them for you." action_url=url action_label="Add an LO" only %}
  Getting Real, ch. 9 "The Blank Slate": an empty screen says what to do first.
{% endcomment %}<div class="pl-empty text-center">
  <div class="pl-empty-mark" aria-hidden="true">✦</div>
  <h2 class="h5">{{ title }}</h2>
  {% if message %}<p class="text-body-secondary mb-3">{{ message }}</p>{% endif %}
  {% if action_url %}<a class="btn btn-primary" href="{{ action_url }}">{{ action_label }}</a>{% endif %}
</div>
```

**`templates/includes/toast.html`**

```html
{% comment %}Usage: {% include "includes/toast.html" with message=message only %}{% endcomment %}
<div class="toast align-items-center pl-toast pl-toast-{{ message.tags|default:'info' }}" role="status" data-bs-delay="5000">
  <div class="d-flex">
    <div class="toast-body">{{ message }}</div>
    <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
  </div>
</div>
```

**7. Views, pages and URLs.** `home` is a placeholder (S2-01 turns it into the role-based redirect). `styleguide` exists only while `DEBUG` is on.

**`apps/core/views.py`**

```python
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render


def healthz(request):
    """Used by Docker, Caddy and the CD smoke test (spec §10.3). Public, no login."""
    status = {"db": "ok", "cache": "ok"}
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001
        status["db"] = "down"
    try:
        cache.set("healthz", "1", 5)
    except Exception:  # noqa: BLE001
        status["cache"] = "down"
    code = 200 if all(v == "ok" for v in status.values()) else 503
    return JsonResponse(status, status=code)


@login_required
def home(request):
    """Placeholder until S2-01, which replaces it with the role-based redirect."""
    return render(request, "core/home.html")


def styleguide(request):
    """Every component on one page, so you can check the design system by eye.
    Only exists while DEBUG is on."""
    if not settings.DEBUG:
        raise Http404
    from decimal import Decimal as D

    examples = [D("86"), D("84.95"), D("59.94"), None]
    return render(request, "core/styleguide.html", {"examples": examples, "threshold": D("60")})
```

**`apps/core/templates/core/home.html`**

```html
{% extends "base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
  {% url 'admin:index' as admin_url %}
  {% include "includes/empty_state.html" with title="Welcome to POlaris" message="Your role-based home page arrives in Sprint 2. Until then, explore the data in the admin." action_url=admin_url action_label="Open the admin" only %}
{% endblock %}
```

**`apps/core/templates/core/styleguide.html`**

```html
{% extends "base.html" %}
{% load polaris %}
{% block title %}Style guide{% endblock %}
{% block content %}
  <h1 class="h3 mb-4">Style guide</h1>

  <section class="mb-5">
    <h2 class="h5">The |score filter (one decimal, half-up, — for none)</h2>
    <table class="table table-sm w-auto pl-num">
      <thead><tr><th scope="col">Raw value</th><th scope="col">|score</th><th scope="col">Badge (threshold {{ threshold|score }})</th></tr></thead>
      <tbody>
        {% for value in examples %}
          <tr>
            <td>{{ value|default_if_none:"None" }}</td>
            <td>{{ value|score }}</td>
            <td>{% include "includes/score_badge.html" with value=value threshold=threshold only %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <section class="mb-5">
    <h2 class="h5">Coverage bar</h2>
    <div style="max-width: 16rem">
      {% include "includes/coverage_bar.html" with coverage="0.2857" only %}
      {% include "includes/coverage_bar.html" with coverage="1" only %}
    </div>
  </section>

  <section class="mb-5">
    <h2 class="h5">State colours</h2>
    <ul class="list-unstyled d-flex flex-wrap gap-2">
      <li class="pl-chip pl-chip-draft">● Draft / unpublished</li>
      <li class="pl-chip pl-chip-ai">AI-suggested</li>
      <li class="pl-chip pl-chip-derived">Derived</li>
      <li class="pl-chip pl-chip-document">From document</li>
    </ul>
  </section>

  <section class="mb-5">
    <h2 class="h5">Empty state</h2>
    {% include "includes/empty_state.html" with title="No assessments yet" message="Add the exams and projects you grade." action_url="#" action_label="Add an assessment" only %}
  </section>
{% endblock %}
```

The login page uses Django's own `LoginView` for now. Its form field is called `username` even though it holds the email (Django names it after `USERNAME_FIELD` internally but keeps the form key); the template labels it "Email".

**`apps/accounts/urls.py`**

```python
"""Minimal login/logout so LOGIN_URL resolves from Sprint 1 on.
S2-01 swaps in our own LoginView, form and the password-reset URLs."""

from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

**`apps/accounts/templates/accounts/login.html`**

```html
{% extends "base.html" %}
{% block title %}Log in{% endblock %}
{% block content %}
  <div class="row justify-content-center">
    <div class="col-sm-8 col-md-5 col-lg-4">
      <h1 class="h4 mb-3">Log in</h1>
      <form method="post" novalidate>
        {% csrf_token %}
        {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors|join:" " }}</div>{% endif %}
        <div class="mb-3">
          <label class="form-label" for="{{ form.username.id_for_label }}">Email</label>
          <input class="form-control" type="email" name="{{ form.username.html_name }}" id="{{ form.username.id_for_label }}"
                 value="{{ form.username.value|default:'' }}" autocomplete="email" required autofocus>
        </div>
        <div class="mb-3">
          <label class="form-label" for="{{ form.password.id_for_label }}">Password</label>
          <input class="form-control" type="password" name="{{ form.password.html_name }}" id="{{ form.password.id_for_label }}"
                 autocomplete="current-password" required>
        </div>
        <input type="hidden" name="next" value="{{ next }}">
        <button class="btn btn-primary w-100" type="submit">Log in</button>
      </form>
    </div>
  </div>
{% endblock %}
```

**`config/urls.py`**

```python
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("healthz", core_views.healthz, name="healthz"),
    path("styleguide/", core_views.styleguide, name="styleguide"),
    path("", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
```

### Tests

**`apps/core/tests/test_design_system.py`**

```python
from decimal import Decimal as D

import pytest
from django.template import Context, Template
from django.test import RequestFactory

from apps.core.templatetags.polaris import pct, score, weight


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("86"), "86.0"),
        (D("84.95"), "85.0"),  # half-up, not banker's rounding
        (D("84.94"), "84.9"),
        (D("11600") / D("140"), "82.9"),
        (None, "—"),
        ("", "—"),
        ("not a number", "—"),
        (90, "90.0"),
    ],
)
def test_score_filter(value, expected):
    assert score(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("0.2857"), "29%"), (D("1"), "100%"), (D("0.005"), "1%"), (None, "—")]
)
def test_pct_filter(value, expected):
    assert pct(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("40.00"), "40"), (D("12.50"), "12.5"), (5, "5"), (None, "")]
)
def test_weight_filter(value, expected):
    assert weight(value) == expected


def test_query_transform_changes_one_key():
    request = RequestFactory().get("/department/", {"term": "2025F", "cohort": "2023"})
    out = Template("{% load polaris %}{% query_transform term='2026F' cohort=None %}").render(
        Context({"request": request})
    )
    assert out == "term=2026F"


@pytest.mark.parametrize(
    ("value", "css", "text"),
    [
        (D("86"), "pl-badge-ok", "86.0"),
        (D("59.94"), "pl-badge-low", "59.9"),
        (None, "pl-badge-none", "—"),
    ],
)
def test_score_badge_include(value, css, text):
    html = Template(
        '{% include "includes/score_badge.html" with value=v threshold=t only %}'
    ).render(Context({"v": value, "t": D("60")}))
    assert css in html
    assert text in html


def test_threshold_boundary_counts_as_attained():
    """P11: attains when score >= threshold."""
    html = Template(
        '{% include "includes/score_badge.html" with value=v threshold=t only %}'
    ).render(Context({"v": D("60"), "t": D("60")}))
    assert "pl-badge-ok" in html


def test_styleguide_only_in_debug(client, db, settings):
    settings.DEBUG = False
    assert client.get("/styleguide/").status_code == 404
    settings.DEBUG = True
    response = client.get("/styleguide/")
    assert response.status_code == 200
    assert b"85.0" in response.content
```

`apps/core/tests/test_views.py` gets the login and home tests next to S0-03's health checks:

**`apps/core/tests/test_views.py`**

```python
import pytest

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-test-password"


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        "elif@live.acibadem.edu.tr", PASSWORD, first_name="Elif", last_name="Yıldız"
    )


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"db": "ok", "cache": "ok"}


def test_healthz_reports_a_dead_cache(client, monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr("apps.core.views.cache.set", broken)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["cache"] == "down"


def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/"


def test_login_with_email_then_home(client, user):
    assert client.get("/login/").status_code == 200
    response = client.post("/login/", {"username": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/"
    home = client.get("/")
    assert b"Welcome to POlaris" in home.content
    assert b"X-CSRFToken" in home.content  # HTMX gets the CSRF token from <body>


def test_wrong_password_is_rejected(client, user):
    response = client.post("/login/", {"username": user.email, "password": "nope"})
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
```

### Check it works

- `http://localhost:8000/` → redirected to `/login/?next=/`; log in with your superuser → the welcome page.
- `/styleguide/`: 84.95 shows as **85.0** with a green ✓ badge; 59.94 as **59.9** with a red ↓; `None` as a grey —. Click *◐ Theme*: everything stays readable in dark mode. Reload: the theme is remembered.
- Keyboard only: Tab from the top of the page; the first stop is "Skip to content", and every focused element has a visible amber outline.
- Make the window phone-width: the navbar collapses into the toggler.

### Done when

- [ ] All nine §8.2 tokens defined for light and dark
- [ ] `|score` = `engine.display` (tests, including half-up and "—")
- [ ] Four components with documented parameters; style guide renders them
- [ ] `LOGIN_URL` resolves; login with email works (test)

### Commits and PR

```
Vendor Bootstrap 5.3.8, htmx 2.0.11 and Chart.js 4.5.1 (#<issue>)
Add design tokens for light and dark mode
Add base template with toasts, theme toggle and HTMX CSRF header
Add score, pct and weight filters backed by the engine's rounding
Add score badge, coverage bar, empty state and toast components
Add login page and placeholder home
```

PR title: `S1-09: Design system foundations and login page (#<issue>)`. Attach screenshots of `/styleguide/` in light and dark mode.

---

## S1-10 · `seed_demo` v1

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S1-10-seed-demo` · **Depends on:** S1-05, S1-07

### Goal

`uv run python manage.py seed_demo` fills an empty database with a believable small department, so every teammate, staging, and every sprint review shows the same data. Version 1 (this story) has 3 terms, 4 instructors (the head also teaches), **30 students** in cohorts 2023–2025, and 4 offerings, each with LOs, assessments, both weight sets and grades. It includes **Elif Yıldız (student 2024-0041)**, enrolled **only** in CSE 311 in Fall 2026, with exactly the professor's slide, so her profile shows PO 1 = 85.0 and PO 2 = 82.9. S3-07 grows it to the full Appendix B dataset (12 courses, 120 students, deliberate flaws).

### What it builds

| Offering | Term (status) | Instructor | Taken by | Published |
|---|---|---|---|---|
| CSE 211 Data Structures | 2025F (closed) | Can Aydın | cohorts 2023, 2024 (not Elif) | all 4 assessments |
| MAT 241 Linear Algebra | 2026S (closed) | Mehmet Şahin | cohorts 2023–2025 (not Elif) | all 3 |
| CSE 311 Software Engineering | 2026F (open) | Deniz Kara (head) | Elif + cohorts 2023, 2024 | Midterm I, Project; Final is draft for about half the class |
| CSE 321 Data Systems | 2026F (open) | Ayşe Demir | cohort 2023 | Midterm; the rest drafts |

Grades: each student has a hidden *ability* (normal around 72, spread 11); each mark is ability + noise (spread 9), clipped to 0–100 % of the max, rounded to whole or half points. About 5 % are missing and 2 % excused, so coverage and the "—" state show up in the demo. Draft grades never get a `published_score` (D2).

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/core/management/__init__.py`, `apps/core/management/commands/__init__.py` | create | Empty (Django finds commands through these) |
| `apps/core/management/commands/seed_demo.py` | create | The command |
| `apps/core/seed/__init__.py`, `apps/core/seed/names.py` | create | Turkish first and last names |
| `apps/core/tests/test_seed_demo.py` | create | |

### Steps

**1. Names without Faker.** Faker is a *dev* dependency, and staging runs `seed_demo` from the production install (`uv sync --no-dev`), where importing Faker would crash. So names come from two plain lists, picked by the same seeded generator as everything else.

**`apps/core/seed/names.py`**

```python
"""Name lists for seed_demo. Plain lists instead of Faker, because Faker is a dev-only
dependency and staging runs seed_demo with the production install (uv sync --no-dev)."""

# fmt: off
FIRST_NAMES = [
    "Ahmet", "Ali", "Arda", "Ayşe", "Aylin", "Barış", "Berk", "Beyza", "Burak", "Büşra",
    "Can", "Cem", "Ceren", "Defne", "Deniz", "Derya", "Ece", "Efe", "Ege", "Elif",
    "Emir", "Emre", "Esra", "Gizem", "Gökhan", "Hakan", "Hande", "İrem", "Kaan", "Kerem",
    "Mehmet", "Melis", "Merve", "Mert", "Murat", "Nazlı", "Onur", "Özge", "Selin", "Serkan",
    "Seda", "Sinem", "Tolga", "Tuğba", "Umut", "Yağmur", "Yusuf", "Zehra", "Zeynep", "Fatma",
]

LAST_NAMES = [
    "Acar", "Akın", "Aksoy", "Aslan", "Avcı", "Aydın", "Balcı", "Bulut", "Çakır", "Çelik",
    "Demir", "Doğan", "Erdem", "Eren", "Güler", "Güneş", "Işık", "Kaplan", "Kara", "Kaya",
    "Keskin", "Koç", "Korkmaz", "Kurt", "Özdemir", "Özkan", "Öztürk", "Polat", "Sarı", "Şahin",
    "Şen", "Tekin", "Temiz", "Turan", "Uçar", "Ünal", "Uysal", "Yalçın", "Yavuz", "Yıldırım",
]
# fmt: on
```

**2. The command.** Design choices worth defending:

- **Deterministic.** One `random.Random(311)` drives every choice, so every run builds identical data and tests can rely on it (`test_reset_rebuilds_identical_data`).
- **Safe by default.** It refuses to run with `DEBUG=False` unless you pass `--allow-production`, because every demo account has the same printed password. Staging passes the flag on purpose; production never should.
- **Idempotent.** A second run does nothing ("already exists"); `--reset` wipes and rebuilds. `--reset` keeps superusers and the CSE program with its POs (they come from the migration).
- **One transaction.** If anything fails halfway, nothing is left behind.
- **Fast.** Grades are written with one `bulk_create`.
- **The course specs are data** (the `COURSES` list), so S3-07 adds courses by adding dictionaries, not code.

**`apps/core/management/commands/seed_demo.py`**

```python
"""Fill a fresh database with a believable department (spec Appendix B, v1 = Sprint 1).

    uv run python manage.py seed_demo            # once, on an empty database
    uv run python manage.py seed_demo --reset    # wipe demo data and rebuild
    uv run python manage.py seed_demo --small    # 12 students instead of 30 (fast, for tests)

v1 builds: 3 terms, 4 instructors (the head also teaches), 30 students in cohorts
2023-2025, 4 offerings with LOs, assessments, both weight sets and grades, and Elif Yıldız
with exactly the professor's slide example (PO 1 = 85.0, PO 2 = 82.9). S3-07 grows this to
12 courses and 120 students.

Every random choice comes from one seeded generator, so every run builds identical data.
Names come from apps/core/seed/names.py, not Faker: Faker is a dev-only dependency and
staging runs this command with the production install.
"""

import datetime
import random
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    Term,
)
from apps.catalog.selectors import active_po_set
from apps.core.seed.names import FIRST_NAMES, LAST_NAMES
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight

SEED = 311
DEMO_PASSWORD = "polaris-demo-2026"  # noqa: S105  demo only; the command refuses to run in production

TERMS = [
    ("2025F", "Fall 2025", datetime.date(2025, 9, 29), datetime.date(2026, 1, 23), "closed"),
    ("2026S", "Spring 2026", datetime.date(2026, 2, 9), datetime.date(2026, 6, 12), "closed"),
    ("2026F", "Fall 2026", datetime.date(2026, 9, 28), datetime.date(2027, 1, 22), "open"),
]

STAFF = [
    # (first, last, email local part, roles)
    ("Deniz", "Kara", "deniz.kara", ["head", "instructor"]),
    ("Can", "Aydın", "can.aydin", ["instructor"]),
    ("Ayşe", "Demir", "ayse.demir", ["instructor"]),
    ("Mehmet", "Şahin", "mehmet.sahin", ["instructor"]),
]

# Each course: catalog data, term, instructor, which cohorts take it, LOs, assessments,
# assessment→LO weights (%), LO→PO weights (1-5). Assessment tuple:
# (name, kind, max_score, course_weight %, published?)
COURSES = [
    {
        "code": "CSE 211",
        "title": "Data Structures",
        "credits": "4.0",
        "ects": "6.0",
        "term": "2025F",
        "instructor": "can.aydin",
        "cohorts": [2023, 2024],
        "los": [
            "Analyse the time and space complexity of algorithms using asymptotic notation.",
            "Implement lists, stacks, queues, trees and hash tables and choose between them.",
            "Design and test programs that use appropriate data structures for a problem.",
        ],
        "assessments": [
            ("Quiz 1", "quiz", "20", "10", True),
            ("Midterm", "midterm", "100", "30", True),
            ("Lab assignments", "lab", "100", "20", True),
            ("Final", "final", "100", "40", True),
        ],
        "a_lo": {
            "Quiz 1": {1: 100},
            "Midterm": {1: 50, 2: 50},
            "Lab assignments": {2: 50, 3: 100},
            "Final": {1: 40, 2: 30, 3: 30},
        },
        "lo_po": {1: {1: 5, 2: 3}, 2: {1: 3, 4: 4}, 3: {2: 4, 3: 3, 4: 3}},
    },
    {
        "code": "MAT 241",
        "title": "Linear Algebra",
        "credits": "3.0",
        "ects": "5.0",
        "term": "2026S",
        "instructor": "mehmet.sahin",
        "cohorts": [2023, 2024, 2025],
        "los": [
            "Solve systems of linear equations with Gaussian elimination and matrix methods.",
            "Compute and interpret eigenvalues, eigenvectors and matrix decompositions.",
        ],
        "assessments": [
            ("Midterm", "midterm", "100", "40", True),
            ("Homework", "homework", "50", "20", True),
            ("Final", "final", "100", "40", True),
        ],
        "a_lo": {"Midterm": {1: 100}, "Homework": {1: 50, 2: 50}, "Final": {1: 40, 2: 60}},
        "lo_po": {1: {1: 5}, 2: {1: 4, 2: 3}},
    },
    {
        # Elif's course: the professor's slide (spec §2.2) plus an ungraded final.
        "code": "CSE 311",
        "title": "Software Engineering",
        "credits": "3.0",
        "ects": "6.0",
        "term": "2026F",
        "instructor": "deniz.kara",
        "cohorts": [2023, 2024],
        "los": [
            "Plan and run a software project with Scrum: backlog, sprints, reviews.",
            "Use version control, code review and continuous integration in a team.",
            "Write automated tests and apply test-driven development.",
        ],
        "assessments": [
            ("Midterm I", "midterm", "100", "30", True),
            ("Project", "project", "100", "40", True),
            ("Final", "final", "100", "30", False),
        ],
        "a_lo": {"Midterm I": {1: 60, 2: 40}, "Project": {1: 40, 2: 100}, "Final": {3: 100}},
        "lo_po": {1: {1: 4}, 2: {1: 2, 2: 5}, 3: {3: 4}},
    },
    {
        "code": "CSE 321",
        "title": "Data Systems",
        "credits": "3.0",
        "ects": "6.0",
        "term": "2026F",
        "instructor": "ayse.demir",
        "cohorts": [2023],
        "los": [
            "Design normalised relational schemas from requirements.",
            "Write SQL queries, including joins, aggregation and window functions.",
            "Explain transactions, isolation levels and indexing trade-offs.",
        ],
        "assessments": [
            ("Midterm", "midterm", "100", "35", True),
            ("Team project", "project", "100", "35", False),
            ("Final", "final", "100", "30", False),
        ],
        "a_lo": {
            "Midterm": {1: 50, 2: 50},
            "Team project": {1: 50, 2: 50, 3: 30},
            "Final": {2: 40, 3: 100},
        },
        "lo_po": {1: {3: 4, 4: 3}, 2: {2: 4, 4: 5}, 3: {1: 3, 2: 3}},
    },
]

ELIF = {
    "first_name": "Elif",
    "last_name": "Yıldız",
    "email": "elif.yildiz@live.acibadem.edu.tr",
    "student_number": "2024-0041",
    "cohort_year": 2024,
    "marks": {"Midterm I": Decimal("90"), "Project": Decimal("80")},
}

ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class Command(BaseCommand):
    help = "Fill the database with demo data (spec Appendix B)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="wipe demo data first")
        parser.add_argument("--small", action="store_true", help="12 students instead of 30")
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="run even when DEBUG=False (prints known passwords: think twice)",
        )

    def handle(self, *args, reset, small, allow_production, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError(
                "Refusing to seed with DEBUG=False: demo accounts have a known password. "
                "Pass --allow-production if you really mean it."
            )
        self.rng = random.Random(SEED)  # noqa: S311  reproducible demo data, not security

        with transaction.atomic():
            if reset:
                self.wipe()
            elif Term.objects.filter(code="2026F").exists():
                self.stdout.write("Demo data already exists. Use --reset to rebuild it.")
                return
            self.build(students_per_cohort=4 if small else 10)
        self.report()

    # ---------- wipe ----------

    def wipe(self):
        """Delete everything seed_demo creates. Keeps superusers and the CSE program + POs
        (those come from the data migration and must survive)."""
        CourseOffering.objects.all().delete()  # cascades: LOs, assessments, grades, enrollments
        Course.objects.all().delete()
        Term.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()  # cascades: memberships
        self.stdout.write("Wiped demo data.")

    # ---------- build ----------

    def build(self, *, students_per_cohort):
        self.program = Program.objects.get(code="CSE")
        self.pos = {
            po.number: po
            for po in ProgramOutcome.objects.filter(po_set=active_po_set(self.program))
        }
        self.terms = {
            code: Term.objects.create(code=code, name=name, starts_on=s, ends_on=e, status=st)
            for code, name, s, e, st in TERMS
        }
        self.staff = self.create_staff()
        self.elif_ = self.create_user(**{k: v for k, v in ELIF.items() if k != "marks"})
        self.students = [self.elif_] + self.create_students(students_per_cohort)
        for spec in COURSES:
            self.create_offering(spec)

    def create_user(self, *, first_name, last_name, email, student_number=None, cohort_year=None):
        user = User.objects.create_user(
            email,
            DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            student_number=student_number,
        )
        if cohort_year is not None:
            ProgramMembership.objects.create(
                user=user, program=self.program, role="student", cohort_year=cohort_year
            )
        return user

    def create_staff(self):
        staff = {}
        for first, last, local, roles in STAFF:
            user = self.create_user(
                first_name=first, last_name=last, email=f"{local}@acibadem.edu.tr"
            )
            for role in roles:
                ProgramMembership.objects.create(user=user, program=self.program, role=role)
            staff[local] = user
        return staff

    def create_students(self, per_cohort):
        students = []
        for cohort in (2023, 2024, 2025):
            # Elif is one of the 2024 cohort, so that cohort gets one generated student fewer
            count = per_cohort - 1 if cohort == ELIF["cohort_year"] else per_cohort
            for i in range(1, count + 1):
                first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
                local = f"{first}.{last}".lower().translate(ASCII).replace(" ", "")
                students.append(
                    self.create_user(
                        first_name=first,
                        last_name=last,
                        email=f"{local}.{cohort}{i:02d}@live.acibadem.edu.tr",
                        student_number=f"{cohort}-{i:04d}",
                        cohort_year=cohort,
                    )
                )
        # each student gets a hidden "ability" so profiles differ in believable ways
        self.ability = {s.id: self.rng.gauss(72, 11) for s in students}
        return students

    def create_offering(self, spec):
        term = self.terms[spec["term"]]
        course = Course.objects.create(
            program=self.program,
            code=spec["code"],
            title=spec["title"],
            credits=Decimal(spec["credits"]),
            ects=Decimal(spec["ects"]),
        )
        offering = CourseOffering.objects.create(course=course, term=term)
        offering.instructors.add(self.staff[spec["instructor"]])

        los = {
            n: LearningOutcome.objects.create(offering=offering, number=n, description=text)
            for n, text in enumerate(spec["los"], start=1)
        }
        published_at = timezone.make_aware(
            datetime.datetime.combine(
                min(term.ends_on, datetime.date(2026, 11, 6)), datetime.time(12)
            )
        )
        assessments = {}
        for position, (name, kind, max_score, weight, published) in enumerate(spec["assessments"]):
            assessments[name] = Assessment.objects.create(
                offering=offering,
                name=name,
                kind=kind,
                max_score=Decimal(max_score),
                course_weight=Decimal(weight),
                position=position,
                published_at=published_at if published else None,
            )
        for name, targets in spec["a_lo"].items():
            for lo_number, weight in targets.items():
                AssessmentLOWeight.objects.create(
                    assessment=assessments[name],
                    learning_outcome=los[lo_number],
                    weight=Decimal(weight),
                )
        for lo_number, targets in spec["lo_po"].items():
            for po_number, weight in targets.items():
                LOPOWeight.objects.create(
                    learning_outcome=los[lo_number],
                    program_outcome=self.pos[po_number],
                    weight=weight,
                )

        is_elifs_course = spec["code"] == "CSE 311"
        takers = [
            s
            for s in self.students[1:]
            if s.memberships.get(role="student").cohort_year in spec["cohorts"]
        ]
        if is_elifs_course:
            takers = [self.elif_, *takers]

        grades = []
        for student in takers:
            enrollment = Enrollment.objects.create(offering=offering, student=student)
            for name, assessment in assessments.items():
                if student is self.elif_:
                    mark, excused = ELIF["marks"].get(name), False
                    if mark is None:
                        continue  # Elif has no final yet
                else:
                    mark, excused = self.random_mark(student, assessment)
                    if mark is None and not excused:
                        continue  # ~5% missing
                if assessment.published_at is None and self.rng.random() < 0.5:
                    continue  # unpublished assessments: about half the class entered so far
                grade = Grade(
                    assessment=assessment,
                    enrollment=enrollment,
                    score=mark,
                    is_excused=excused,
                    updated_by=self.staff[spec["instructor"]],
                )
                if assessment.published_at is not None:
                    grade.published_score = mark
                    grade.published_is_excused = excused
                    grade.published_at = assessment.published_at
                grades.append(grade)
        Grade.objects.bulk_create(grades)

    def random_mark(self, student, assessment):
        """(mark, is_excused). About 5% missing, 2% excused, the rest ability + noise."""
        roll = self.rng.random()
        if roll < 0.02:
            return None, True
        if roll < 0.07:
            return None, False
        percent = min(100.0, max(0.0, self.ability[student.id] + self.rng.gauss(0, 9)))
        mark = assessment.max_score * Decimal(str(percent)) / 100
        return (mark * 2).quantize(Decimal("1")) / 2, False  # whole numbers or halves

    # ---------- summary ----------

    def report(self):
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Every demo account's password: {DEMO_PASSWORD}")
        self.stdout.write("  Head (also teaches CSE 311): deniz.kara@acibadem.edu.tr")
        self.stdout.write("  Instructors: can.aydin@, ayse.demir@, mehmet.sahin@acibadem.edu.tr")
        self.stdout.write(f"  Student Elif (slide example): {ELIF['email']}")
        self.stdout.write(
            f"  {User.objects.filter(memberships__role='student').count()} students, "
            f"{CourseOffering.objects.count()} offerings, {Grade.objects.count()} grades"
        )
```

### Tests

`--small` (12 students) keeps these fast. Note the sort in `grade_rows()`: excused grades have `score = None`, and Python can't compare `None` with a `Decimal`, so rows are sorted by their text form.

**`apps/core/tests/test_seed_demo.py`**

```python
import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.catalog.models import CourseOffering, Program
from apps.grading.models import Grade
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


def seed(settings, *args):
    settings.DEBUG = True
    call_command("seed_demo", "--small", *args)


def elif_profile():
    elif_ = User.objects.get(student_number="2024-0041")
    profile = compute_student_profile(load_student_inputs(elif_))
    numbers = {po.number: po for po in Program.objects.get(code="CSE").po_sets.get().outcomes.all()}
    return {
        n: display(profile.po_scores[po.id].score)
        for n, po in numbers.items()
        if po.id in profile.po_scores
    }


def test_elif_matches_the_slide(settings):
    seed(settings)
    assert elif_profile() == {1: "85.0", 2: "82.9", 3: "—"}


def test_second_run_is_a_no_op(settings, capsys):
    seed(settings)
    grades = Grade.objects.count()
    seed(settings)
    assert Grade.objects.count() == grades
    assert "already exists" in capsys.readouterr().out


def grade_rows():
    # excused and missing grades have score None, so sort by the text form
    rows = Grade.objects.values_list(
        "enrollment__student__student_number", "assessment__name", "score", "is_excused"
    )
    return sorted(rows, key=repr)


def test_reset_rebuilds_identical_data(settings):
    seed(settings)
    before = grade_rows()
    seed(settings, "--reset")
    assert grade_rows() == before  # fixed random seed: same data every time
    assert CourseOffering.objects.count() == 4


def test_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Refusing to seed"):
        call_command("seed_demo")


def test_drafts_are_never_published(settings):
    seed(settings)
    drafts = Grade.objects.filter(assessment__published_at__isnull=True)
    assert drafts.exists()
    assert not drafts.filter(published_score__isnull=False).exists()
```

### Check it works

```bash
uv run python manage.py seed_demo
#   Demo data ready.
#   Every demo account's password: polaris-demo-2026
#   …
#   30 students, 4 offerings, 216 grades
uv run python manage.py seed_demo          # Demo data already exists. Use --reset to rebuild it.
uv run python manage.py seed_demo --reset  # identical data again
```

Then the Sprint 1 checkpoint from the [overview](#sprint-1-overview) in the shell: `{1: '85.0', 2: '82.9', 3: '—'}`. Log in at `/admin/` as your superuser and browse Elif's grades (Grades → search `2024-0041`).

### Done when

- [ ] Empty database → believable department in one command; identical on every run (test)
- [ ] Elif enrolled only in CSE 311 2026F, profile 85.0 / 82.9 (test)
- [ ] Refuses without `DEBUG` (test); drafts never published (test)
- [ ] README setup section gains the `seed_demo` line (spec §10.4)

### Commits and PR

```
Add seed_demo with three terms, four courses and thirty students (#<issue>)
Seed Elif with exactly the slide example
Use built-in name lists so staging can seed without Faker
```

PR title: `S1-10: Demo data, version 1 (#<issue>)`

---

# End of Sprint 1: review, retro, evidence

**Sprint review** (Sunday 25 Oct, 30 minutes, record the screen for the evidence folder):

1. `docker compose down -v && docker compose up -d && uv run python manage.py migrate && uv run python manage.py seed_demo` on the presenter's laptop: an empty database to a department in one minute.
2. The shell checkpoint: Elif's 85.0 / 82.9.
3. `uv run pytest --cov`: about 130 tests, coverage above 95 %, under 10 seconds.
4. `git log --oneline` on the engine merge: the red/green pairs (TDD evidence).
5. The admin: a course offering with its LOs, assessments and enrolments inline.

**Retro** (15 minutes): start / stop / continue in `docs/process/sprint-01/retro.md`, plus one action item with an owner.

**Evidence checklist** (Scrum Master, spec §9.5): board screenshots (Monday and Sunday), the Insights burn-up, the review recording link, `retro.md`, the Sprint 1 row of `velocity.md` (completed points = stories meeting the Definition of Done by Sunday 23:59), and a merged release PR `develop → main` tagged `v0.1.0`.

**Sprint 2 planning** (right after the retro): yesterday's weather. Forecast = Sprint 1's completed points (only one sprint of history so far).

---

# Code map additions

Names this chapter introduces that are not in spec §4.8. Add them to §4.8 in the S0-06 or S1-10 PR.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `apps/catalog/selectors.py` | `po_set_ids_for_students` | `(student_ids, program) -> dict[int, int]` | P13 for many students in two queries; `po_set_for_student` and both loaders use it |
| `apps/core/audit.py` | `_json_safe` (private) | `(value) -> JSON-safe value` | Used by `snapshot`; converts `Decimal`, dates, model instances |
| `apps/core/views.py` | `styleguide` | `(request)` | `/styleguide/`, DEBUG only; URL name `styleguide` |
| `apps/accounts/urls.py` | `app_name = "accounts"`, URLs `login`, `logout` | Django auth views | Placeholder until S2-01's `LoginView` and password reset |
| `apps/core/tests/factories.py` | `PASSWORD` | `str` constant | The password of every factory user, for login tests |
| `apps/core/tests/factories.py` | traits `AssessmentFactory(published=True)`, `GradeFactory(published=True)` | | Published test data in one keyword |
| `apps/core/seed/names.py` | `FIRST_NAMES`, `LAST_NAMES` | `list[str]` | Seed names without Faker |
| `apps/core/management/commands/seed_demo.py` | `--allow-production` flag | | Run with `DEBUG=False` (staging) |
| `scripts/protect_branches.sh` | | `CHECKS="…" ./scripts/protect_branches.sh` | Branch protection as code |
| `scripts/import_backlog.py` | | `[--apply]` | Part 12 → GitHub issues and board fields |
