# POlaris

A web system that manages and maintains every student's Program Outcome (PO) scores.
Team project for CSE 311 Software and CSE 321 Data Systems, Fall 2026, Acıbadem University.

Start with [`POLARIS-PROJECT-SPEC.md`](POLARIS-PROJECT-SPEC.md). It is the single source of truth for
what we build and how: product, scoring method, data model, process, sprint plan and backlog.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Docker.

```bash
git clone https://github.com/OnurHaniffa/polaris.git && cd polaris
uv sync                                   # installs Python 3.13 if needed + all packages
cp .env.example .env                      # then ask the team for the shared dev ANTHROPIC_API_KEY (Sprint 5+)
docker compose up -d                      # Postgres + Redis
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run pre-commit install                 # ruff runs on every commit
uv run python manage.py runserver         # http://localhost:8000
uv run pytest                             # everything green?
```
