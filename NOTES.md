# BillBrief — Build Notes

AI-powered congressional bill tracker + HTML newsletter.

---

## October 7 — TODO

- [ ] Create superuser and check bills in the Django admin
- [ ] Add `--congress` argument to `sync_bills` (default 119) so the sync only pulls the current Congress
- [ ] Re-run the sync, confirm 119th Congress bills, commit

---

## October 6 — Environment, Postgres, first sync

**1. Set up the environment**

```bash
pipenv shell
pipenv install django djangorestframework "psycopg[binary]" requests dj-database-url python-dotenv
django-admin startproject config .   # "config" = settings package; "." keeps manage.py at the repo root
python manage.py startapp bills      # the app
python manage.py runserver
```
![alt text](<The install worked successfully! Congratulations!.png>)

**2. Pushed progress**

```bash
git add .
git commit -m "..."
git push
```

- Problem: push failed with `Failed to connect to github.com port 443`.
- Debugged: `curl -I https://github.com` returned 200, no proxy configured; it was a temporary network drop. Push succeeded on retry.

**3. Installed Docker Desktop** to run PostgreSQL locally

- Problem: `docker: command not found` right after install.
- Fix: the terminal was opened before Docker was installed; a fresh terminal picked up the new PATH.

**4. Postgres via Docker Compose**

- Created `docker-compose.yml` at the repo root (same level as `manage.py`)
- Ran `docker compose up -d`

**5. Config**

- Created `.env` with the Congress.gov API key and `DATABASE_URL` (confirmed with `git status` that `.env` is ignored)
- In `config/settings.py`:

```python
import dj_database_url
from dotenv import load_dotenv
load_dotenv()

DATABASES = {"default": dj_database_url.config()}
```

- Added `rest_framework` and `bills` to `INSTALLED_APPS`

**6. Models and ingestion**

- Models: `Member`, `Bill`, `Action`
- Ingestion command: `bills/management/commands/sync_bills.py`

```
bills/
├── models.py
└── management/
    ├── __init__.py
    └── commands/
        ├── __init__.py
        └── sync_bills.py
```

**7. Migrated and ran the first sync**

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py sync_bills --days 3 --limit 5
```

- Problem: `ModuleNotFoundError: No module named 'django'`.
- Debugged: `which python` pointed to an old virtualenv (`...-O9mgv4Bi`) left over from an earlier install in the wrong folder, while `pipenv --venv` showed the project's real one (`...-m0y9PZYD`). Exited the stale shell, re-ran `pipenv shell`, and it worked.
- Also: first tried running migrations from the wrong folder level.

**8. Registered the 3 models in `admin.py`**

**Result:** sync worked: 5 bills saved to Postgres with actions.

- Finding: all 5 were from the **117th Congress**. The `fromDateTime` filter returns bills whose *records* were recently updated, which includes old bills. Next step: scope the sync to the current (119th) Congress.
![alt text](<(BilBrief) aqcunningham@x BillBrief & python manage-py syne_bills --days 3 -limit 5.png>)

---

## October 5 — Repo setup

1. Requested a Congress.gov API key (stored in `.env` only, never committed)
2. Created the GitHub repo: README, Python `.gitignore`, MIT license
3. Cloned it: `git clone https://github.com/aqcunningham/BillBrief.git`

---

## October 4 — Research and planning


**Visual ideas:** briefs feed, bill journey timeline, BillBrief Weekly email (see the BillBrief Visual Concepts canvas)