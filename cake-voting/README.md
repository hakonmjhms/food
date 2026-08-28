# Cake Voting

A small, fun internal app where employees predict which cake will be served in the
cafeteria every Thursday, vote once per week, and browse historical statistics.

Voting is fully anonymous, there is no login and no admin of any kind - there is no
dependency on Microsoft, Azure, or any other identity provider at all. Even the
"actual cake" is determined by the crowd, not by an administrator.

## Stack

- **Backend:** FastAPI (Python), server-rendered Jinja2 templates
- **Identity:** none - each browser gets a random, opaque cookie used only to stop double-voting
- **Database:** SQLAlchemy ORM; SQLite for local dev, PostgreSQL in production
- **Frontend:** Plain HTML/CSS/JS (no framework)
- **Sessions:** Signed cookie sessions (`itsdangerous` via Starlette's `SessionMiddleware`) - used only to hold the CSRF token, no Redis/server-side session store needed

## Project layout

```
cake-voting/
  app/
    main.py          FastAPI app, middleware, routers
    config.py        Settings loaded from environment / .env
    database.py      SQLAlchemy engine/session setup
    models.py        Cake, Week, Vote, ActualCakeVote
    crud.py          Database read/write helpers
    stats.py         Current-week and historical statistics
    security.py      Anonymous voter cookie, CSRF, rate limiting
    routers/         pages, votes, cakes
    templates/        Jinja2 templates
    static/           CSS/JS
  scripts/
    seed_dev_data.py  Optional: populate sample cakes/week for local dev
  tests/              pytest tests for voting/statistics logic
  requirements.txt
  requirements-dev.txt
  .env.example
  Dockerfile
  docker-compose.yml  Local Postgres + app, for testing against Postgres
```

## Data model

- **Cake** - a possible cake option. Anyone can add one from `/cakes` - there's no gate on this either.
- **Week** - one Thursday voting event: `event_date`, the prediction-voting window (`voting_opens_at`/`voting_closes_at`), when actual-cake reporting opens (`actual_vote_opens_at`), and `actual_cake_id` once it's been determined. Status (upcoming/open/closed/reporting/revealed) is derived from these fields rather than stored, to avoid drift.
- **Vote** - a prediction: `(week, voter_token, cake, created_at, updated_at)`. A **unique constraint on `(week_id, voter_token)`** enforces "one prediction per browser per week" at the database level; casting a new vote for the same week updates the existing row instead of inserting a second one.
- **ActualCakeVote** - an anonymous report of what the actual cake was, shaped just like `Vote` but in its own table with its own one-report-per-browser-per-week constraint (see below).

## Weekly schedule

Each Thursday has two independent voting windows, both handled automatically (there's no admin to open/close anything):

| Time (Thursday) | What happens |
|---|---|
| 7:00 AM | Prediction voting opens |
| 11:15 AM | Prediction voting closes |
| 11:35 AM | Actual-cake reporting opens |

The gap between 11:15 and 11:35 is a quiet period where neither form is shown - just the current prediction results.

## How the actual cake is decided (no admin required)

Once actual-cake reporting opens, anyone can anonymously report what they believe
the actual cake was. As soon as one cake reaches **a strict majority of reports,
with at least 2 reports**, it's automatically locked in as that week's actual cake -
see `crud.cast_actual_cake_vote`. There is no administrator action involved; the
crowd decides.

## Local development

1. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
2. Copy `.env.example` to `.env` and set a `SESSION_SECRET_KEY` (see below). SQLite works out of the box with no further setup.
3. (Optional) Seed some sample cakes and a voting week:
   ```
   python -m scripts.seed_dev_data
   ```
4. Run the app:
   ```
   uvicorn app.main:app --reload
   ```
5. Open http://localhost:8000

Run tests with `pytest`.

## How voting works without accounts

When a browser first visits the site, it's given a random, opaque `voter_id` cookie
(valid for ~2 years, `HttpOnly`). That value is the only thing that identifies a
vote - there's no name, email, or account behind it. It's used to:

- Enforce "one prediction per browser per week" and "one actual-cake report per browser per week" (database unique constraints)
- Let a visitor see their own current pick and personal streak on `/history`

Clearing cookies (or using another browser/device) resets that identity and allows another vote for the current week - this is a deliberate, proportional trade-off for a fun internal tool, not a high-stakes ballot.

## Privacy

- Votes are anonymous by design - the database has no link between a vote and any personal identity, only an opaque per-browser cookie value.
- Public pages only ever show **aggregate** results (vote counts/percentages).
- "Your" current pick and personal streak on `/history` are derived from your own cookie and never shown to anyone else.

## Deployment

The app is a single stateless FastAPI process plus a Postgres database, so it can run on
almost any host. Suggested low-maintenance, low/no-cost options:

- **App hosting:** [Render](https://render.com), [Fly.io](https://fly.io), or [Railway](https://railway.app) - all support deploying directly from a Git repo, free HTTPS, and a `Dockerfile`-based build.
- **Database:** a managed free-tier Postgres such as [Neon](https://neon.tech) or [Supabase](https://supabase.com), or the hosting platform's own managed Postgres add-on. Set `DATABASE_URL` accordingly.
- **Backups:** use `pg_dump`/`pg_restore` (or the provider's built-in backup/export tool) against `DATABASE_URL` periodically.

None of this requires any cloud provider at all - the app has zero external dependencies beyond its own database.

### Environment variables (set on the host, never committed)

See `.env.example` for the full list: `APP_BASE_URL`, `SESSION_SECRET_KEY`, `DATABASE_URL`.

## Security notes

- CSRF protection: a per-session token is embedded in every state-changing form and validated server-side.
- The anonymous `voter_id` cookie is `HttpOnly` and `SameSite=Lax`; `secure` is enabled automatically when `APP_BASE_URL` is `https://`.
- All database access goes through SQLAlchemy's parameterized queries (no raw SQL string building).
- The one-vote-per-browser-per-week rule (for both predictions and actual-cake reports) is enforced by database unique constraints, not just application logic.
- Simple in-memory rate limiters throttle both voting endpoints per voter cookie.

## Future ideas (not implemented yet)

Cake photos, public leaderboards, prediction streak badges, "cake of the month", historical charts, reminder notifications, and multiple concurrent voting categories are all reasonable extensions once the basic flow has real data behind it - see the project guideline for the full list.

