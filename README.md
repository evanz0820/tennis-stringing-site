# Tennis Stringing Service

A small full-stack app for a racquet stringing shop.

- **Backend:** FastAPI + SQLAlchemy + JWT auth. SQLite in dev, Postgres in prod via `DATABASE_URL`. Schema managed by Alembic.
- **Frontend:** React + Vite.

Two roles — **customer** and **stringer**. Jobs move through
`requested → received → in_progress → completed → picked_up` (or `cancelled`).

A job carries an optional `dropoff_at` (a naive local datetime): when the
customer plans to hand off the racquet. It is **not** an appointment slot —
there is no capacity limit and no booking, and any number of jobs may share the
same drop-off time.

A job carries a **required** `tension` (string tension in lbs): a whole number
between **40 and 60** inclusive. Omitting it, a value out of range, or a
non-integer (e.g. `52.5`) returns `422`.

The racquet is chosen from a curated catalog served by `GET /racquets`
(`app/racquets.py`), with an "Other" option in the UI for models not on the list.
This is a hand-maintained list, not an exhaustive external database — extend it
by editing `app/racquets.py`.

## Backend

Run from `backend/` in a virtualenv:

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create/upgrade the schema (production and dev both rely on this):
alembic upgrade head

# Optional: load sample users and jobs.
python -m app.seed

# Run the API.
uvicorn app.main:app --reload
```

### Database migrations (Alembic)

The schema is owned by Alembic, **not** `Base.metadata.create_all`. Alembic reads
`DATABASE_URL` from `app/config.py` and applies the same `postgres://` →
`postgresql://` normalization the app uses (see `app/database.py`), so migrations
and the app always target the same database — `alembic.ini` holds no URL.

```bash
alembic upgrade head          # apply all migrations (run this in prod on deploy)
alembic revision --autogenerate -m "describe change"   # after editing models
alembic downgrade -1          # roll back one revision
```

`Base.metadata.create_all` is not run at startup by default. For throwaway dev
databases you can opt in by setting `CREATE_ALL_ON_STARTUP=true`, but production
must rely on `alembic upgrade head`.

### Using a free remote Postgres (Neon)

No code changes needed — the app reads `DATABASE_URL` and normalizes it. To point
it at a free [Neon](https://neon.tech) database:

1. Sign up at neon.tech (free tier, no credit card) and **create a project**
   (pick the region closest to you).
2. In the project's **Connection Details**, copy the connection string. It looks
   like `postgresql://user:pass@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`.
   Keep the `?sslmode=require` — Neon requires SSL.
3. Put it in `backend/.env`:
   ```
   DATABASE_URL=postgresql://user:pass@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. Create the schema and (optionally) seed it:
   ```bash
   source venv/bin/activate
   alembic upgrade head
   python -m app.seed
   ```
5. `uvicorn app.main:app --reload` — you're now on Neon.

The Postgres driver (`psycopg2-binary`) is already installed, and the engine uses
`pool_pre_ping` so idle serverless connections don't cause errors. If your libpq
rejects the `channel_binding` parameter some strings include, just delete that
one query param; `sslmode=require` is the part that matters.

### Tests

```bash
cd backend
source venv/bin/activate
python -m pytest
```

Tests use an isolated in-memory SQLite database and never touch `dev.db`.

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api/* to :8000 (prefix stripped)
```

The frontend calls the API under `/api`. In dev, Vite proxies `/api/*` to the
backend on `:8000` (stripping the `/api` prefix). In production, Vercel serves
both from the same domain (see Deployment).

Log in as a seeded user (password `password`):

- Stringer: `stringer@example.com`
- Customer: `alice@example.com` / `bob@example.com`

The **stringer console** has a live active queue: a `Queue N` button in the top
bar opens a top-right panel listing active jobs (`requested`, `received`,
`in_progress`), sorted by drop-off time (flexible last). Crossing a job off marks
it `completed` and removes it from the queue. The queue polls every 15s so new
jobs appear without a reload.

## Environment variables

All are optional in dev (sensible defaults in `app/config.py`). Set these in prod:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./dev.db` | DB connection. Use a Postgres URL in prod. `postgres://` is normalized to `postgresql://`. |
| `SECRET_KEY` | `dev-secret-change-me` | JWT signing key. **Change in prod.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime. |
| `OPEN_TIME` | `09:00` | Shop open time (`HH:MM`, naive local). |
| `CLOSE_TIME` | `18:00` | Shop close time. |
| `SLOT_MINUTES` | `30` | Drop-off slot grid size. |
| `TURNAROUND_NOTE` | "Most racquets are ready within a day, depending on the current queue." | Informational note shown to customers. |
| `DROP_OFF_ADDRESS` | `123 Court Lane, Atlanta, GA 30303` | Physical drop-off address. Returned only on the create-job response, and only when a drop-off time was set. Not in `/info`. **Set to your real address.** |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins. |
| `CREATE_ALL_ON_STARTUP` | `false` | Dev-only: create tables at startup instead of via Alembic. |

`OPEN_TIME`, `CLOSE_TIME`, and `SLOT_MINUTES` define the valid drop-off slot
boundaries. A `dropoff_at` is accepted only if it is in the future and lands on
one of these boundaries; otherwise the API returns `422`. A null `dropoff_at`
(flexible) is always allowed. This is input validation only — no capacity or
booking is implied.

## Deployment (Vercel — single project)

Frontend (static React) and backend (FastAPI as Python serverless functions)
deploy together as **one** Vercel project on the same domain, so there is no CORS
and the frontend keeps calling `/api/*`. Config lives in:

- `vercel.json` — builds the frontend (`buildCommand` → `outputDirectory`) and
  rewrites `/api/*` to the Python function.
- `api/index.py` — auto-detected serverless function; mounts the FastAPI app
  under `/api` (so `/api/jobs` reaches the app as `/jobs`).
- `requirements.txt` (repo root) — runtime deps for the function.

Steps:

1. Push this repo to GitHub, then in Vercel **New Project → Import** it.
   **Important:** the project's **Root Directory** (Settings → General) must be the
   folder that contains `vercel.json`, `api/`, and `frontend/` — i.e. the repo
   root, **not** `frontend`. If it's set to `frontend`, `vercel.json` and the API
   are ignored and you get a 404.
2. Add **Environment Variables** in the Vercel project settings:
   - `DATABASE_URL` — your Neon pooled connection string (`...-pooler...?sslmode=require`).
   - `SECRET_KEY` — a long random string (do **not** ship the dev default).
   - Optional: `TURNAROUND_NOTE`, `DROP_OFF_ADDRESS`, `OPEN_TIME`, `CLOSE_TIME`, `SLOT_MINUTES`.
   - `CORS_ORIGINS` is not needed (same-origin), but harmless if set.
3. **Run migrations yourself** against Neon (Vercel does not run them):
   ```bash
   cd backend && source venv/bin/activate
   alembic upgrade head
   python -m app.seed   # optional
   ```
4. Deploy. The app is served from your Vercel domain; the API is at `/api/*`.

Notes:
- Requests are stateless serverless invocations (cold starts possible); the app
  needs no persistent server and uses polling, not websockets.
- To run the backend somewhere persistent instead (Render/Railway/Fly), point the
  frontend at it by setting `VITE_API_BASE` to the backend's URL at build time and
  set `CORS_ORIGINS` on the backend to the frontend's origin.
