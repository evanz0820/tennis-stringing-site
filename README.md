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
npm run dev        # http://localhost:5173, proxies /auth /jobs /info to :8000
```

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
