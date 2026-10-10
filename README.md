# BillBrief

**Legislative tracker: plain-language briefs on what Congress is doing and what changed, plus a weekly HTML newsletter.**

BillBrief pulls bills from the Congress.gov API, uses Claude to draft structured,
plain-language briefs, and requires an editor's approval before anything publishes.

> Status: in active development. Live demo coming soon.

## What works today

- **Bill ingestion:** syncs current (119th) Congress bills, sponsors, and full action
  timelines from the Congress.gov API into PostgreSQL. Safe to re-run (upserts, no duplicates).
- **AI briefs:** Claude turns each bill's CRS summary and timeline into a structured brief
  (what it does, why it matters, who's affected, stage) plus a "what changed" note.
  Output is enforced with a tool schema.
- **Editorial review:** every brief starts as a draft. Editors approve or reject in the
  admin, with a record of who reviewed it and when. Only approved briefs appear publicly.

## Design principles

- **The code supplies the facts; the model only writes.** Key facts (latest action,
  constitutional deadlines) are added to the input in code, not left to the model.
- **When AI output looks wrong, check the input first.** See the build log for real examples.
- **Human review is a feature, not a fallback.** Review caught a misleading status and an
  imprecise acreage figure before either reached a reader.
- **Writing style** follows Smart Brevity principles ("why it matters," "what's next").

## Concept designs

How one approved brief feeds four products: the bill brief, alerts, member one-pagers,
and the weekly newsletter.

![BillBrief content map](docs/images/BB_contentmap.png)
![Bill brief and alerts](docs/images/BB_brief-alerts.png)
![Member one-pager and weekly newsletter](docs/images/BB_onepage-weekly.png)

## Stack

Python · Django · Django REST Framework · PostgreSQL · Docker Compose · Claude API · Congress.gov API

## Run it locally

    docker compose up -d
    pipenv install && pipenv shell
    python manage.py migrate
    python manage.py sync_bills --days 7 --limit 50
    python manage.py generate_briefs --bill S-283

Requires a `.env` with `CONGRESS_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`,
and `DJANGO_SECRET_KEY`.

## Roadmap

- Public bill pages and briefs feed
- Member one-pagers
- Deployment (Railway) with CI
- Automatic change tracking and the weekly newsletter

## Build log

Day-by-day progress, including the problems I hit and how I solved them: [NOTES.md](NOTES.md)