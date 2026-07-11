"""API tests.

Uses a throwaway in-memory SQLite DB and overrides get_db so the real dev
database is never touched. Covers auth, job flow, drop-off validation (Task 2),
/info + turnaround note (Task 3), the active-queue data (Task 4 backend), the
drop-off address gate, required tension (40-60), and the racquet catalog.
"""
from datetime import datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

# Enable stringer sign-up for tests with a known code.
STRINGER_CODE = "test-stringer-code"
settings.STRINGER_SIGNUP_CODE = STRINGER_CODE

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


# --- helpers -----------------------------------------------------------------
def register(name, email, password, role, code=None):
    """Register + verify (email is disabled in tests, so the code is returned as
    dev_code). Returns the Token payload, matching pre-verification behaviour."""
    body = {"name": name, "email": email, "password": password, "role": role}
    if code is not None:
        body["stringer_code"] = code
    resp = client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    dev_code = resp.json()["dev_code"]
    assert dev_code, "email disabled in tests should return dev_code"
    v = client.post("/auth/verify", json={"email": email, "code": dev_code})
    assert v.status_code == 200, v.text
    return v.json()


@pytest.fixture
def sent(monkeypatch):
    """Capture outbound emails (to, subject, body) from the routers."""
    box = []

    def fake(to, subject, body):
        box.append((to, subject, body))
        return True

    monkeypatch.setattr("app.routers.jobs.try_send", fake)
    monkeypatch.setattr("app.routers.auth.try_send", fake)
    return box


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def next_open_slot(hour, minute):
    """A future, on-grid, in-hours naive-local datetime string."""
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    return datetime.combine(tomorrow, time(hour, minute)).isoformat()


def make_job(token, **fields):
    """POST /jobs with sensible required defaults (racquet + tension)."""
    payload = {"racquet": "Wilson Blade 98 16x19 v9", "tension": 55}
    payload.update(fields)
    return client.post("/jobs", json=payload, headers=auth_header(token))


@pytest.fixture
def customer():
    return register("Alice", "alice@example.com", "password", "customer")


@pytest.fixture
def stringer():
    return register("Sam", "sam@example.com", "password", "stringer", code=STRINGER_CODE)


# --- auth --------------------------------------------------------------------
def test_login_returns_token(customer):
    resp = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["user"]["role"] == "customer"


# --- email verification ------------------------------------------------------
def test_register_requires_verification_before_login():
    resp = client.post("/auth/register", json={
        "name": "Vera", "email": "vera@example.com", "password": "password",
    })
    assert resp.status_code == 201
    assert resp.json()["verification_required"] is True
    code = resp.json()["dev_code"]
    assert code

    # Login blocked until verified.
    pre = client.post("/auth/login", json={"email": "vera@example.com", "password": "password"})
    assert pre.status_code == 403
    assert "verif" in pre.json()["detail"].lower()

    # Verify -> token, and login now works.
    v = client.post("/auth/verify", json={"email": "vera@example.com", "code": code})
    assert v.status_code == 200
    assert v.json()["user"]["email_verified"] is True
    post = client.post("/auth/login", json={"email": "vera@example.com", "password": "password"})
    assert post.status_code == 200


def test_verify_wrong_code_rejected():
    client.post("/auth/register", json={
        "name": "Wanda", "email": "wanda@example.com", "password": "password",
    })
    resp = client.post("/auth/verify", json={"email": "wanda@example.com", "code": "000000"})
    assert resp.status_code == 400


# --- stringer role is gated by the secret code -------------------------------
def test_public_signup_is_customer_only():
    res = register("Nobody", "n1@example.com", "password", "customer")
    assert res["user"]["role"] == "customer"


def test_stringer_signup_without_code_forbidden():
    resp = client.post("/auth/register", json={
        "name": "Faker", "email": "f@example.com", "password": "password", "role": "stringer",
    })
    assert resp.status_code == 403


def test_stringer_signup_with_wrong_code_forbidden():
    resp = client.post("/auth/register", json={
        "name": "Faker", "email": "f2@example.com", "password": "password",
        "role": "stringer", "stringer_code": "not-the-code",
    })
    assert resp.status_code == 403


def test_stringer_signup_with_correct_code_succeeds():
    res = register("Owner", "owner@example.com", "password", "stringer", code=STRINGER_CODE)
    assert res["user"]["role"] == "stringer"


# --- info / turnaround (Task 3) ----------------------------------------------
def test_info_includes_turnaround_note():
    resp = client.get("/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_time"] == settings.OPEN_TIME
    assert body["close_time"] == settings.CLOSE_TIME
    assert body["slot_minutes"] == settings.SLOT_MINUTES
    assert body["turnaround_note"] == settings.TURNAROUND_NOTE
    assert body["turnaround_note"]


def test_racquet_catalog_available():
    resp = client.get("/racquets")
    assert resp.status_code == 200
    racquets = resp.json()
    assert isinstance(racquets, list) and len(racquets) > 0
    assert all(isinstance(r, str) for r in racquets)


# --- job creation + dropoff validation (Task 2) ------------------------------
def test_create_job_with_valid_slot(customer):
    resp = make_job(customer["access_token"], dropoff_at=next_open_slot(10, 0))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "requested"


def test_create_job_flexible_dropoff_allowed(customer):
    resp = make_job(customer["access_token"], dropoff_at=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["dropoff_at"] is None


def test_reject_past_dropoff(customer):
    past = (datetime.now() - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    resp = make_job(customer["access_token"], dropoff_at=past.isoformat())
    assert resp.status_code == 422
    assert "past" in resp.json()["detail"].lower()


def test_reject_off_grid_dropoff(customer):
    resp = make_job(customer["access_token"], dropoff_at=next_open_slot(10, 7))
    assert resp.status_code == 422
    assert "slot" in resp.json()["detail"].lower()


def test_reject_out_of_hours_dropoff(customer):
    resp = make_job(customer["access_token"], dropoff_at=next_open_slot(6, 0))
    assert resp.status_code == 422


def test_reschedule_validates_dropoff(customer, stringer):
    created = make_job(customer["access_token"], dropoff_at=None).json()
    resp = client.patch(
        f"/jobs/{created['id']}",
        json={"dropoff_at": next_open_slot(11, 13)},
        headers=auth_header(stringer["access_token"]),
    )
    assert resp.status_code == 422
    resp = client.patch(
        f"/jobs/{created['id']}",
        json={"dropoff_at": next_open_slot(11, 30)},
        headers=auth_header(stringer["access_token"]),
    )
    assert resp.status_code == 200


# --- tension (required, integer 40-60) ---------------------------------------
def test_tension_required(customer):
    resp = client.post(
        "/jobs",
        json={"racquet": "Head Speed MP"},  # no tension
        headers=auth_header(customer["access_token"]),
    )
    assert resp.status_code == 422


def test_tension_valid_echoed(customer):
    resp = make_job(customer["access_token"], tension=55)
    assert resp.status_code == 201, resp.text
    assert resp.json()["tension"] == 55


@pytest.mark.parametrize("bad", [39, 61, 0, -5, 52.5, "fifty", None])
def test_tension_out_of_range_or_non_integer_rejected(customer, bad):
    resp = make_job(customer["access_token"], tension=bad)
    assert resp.status_code == 422


@pytest.mark.parametrize("value", [40, 60])
def test_tension_boundaries_inclusive(customer, value):
    resp = make_job(customer["access_token"], tension=value)
    assert resp.status_code == 201, resp.text


def test_stringer_can_update_tension(customer, stringer):
    job = make_job(customer["access_token"], tension=50).json()
    resp = client.patch(
        f"/jobs/{job['id']}", json={"tension": 58},
        headers=auth_header(stringer["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["tension"] == 58
    resp = client.patch(
        f"/jobs/{job['id']}", json={"tension": 70},
        headers=auth_header(stringer["access_token"]),
    )
    assert resp.status_code == 422


# --- drop-off address gate ---------------------------------------------------
def test_dropoff_address_shown_only_with_a_time(customer):
    with_time = make_job(customer["access_token"], dropoff_at=next_open_slot(10, 0)).json()
    assert with_time["dropoff_address"] == settings.DROP_OFF_ADDRESS

    flexible = make_job(customer["access_token"], dropoff_at=None).json()
    assert flexible["dropoff_address"] is None


def test_dropoff_address_not_leaked_to_browsers(customer, stringer):
    make_job(customer["access_token"], dropoff_at=next_open_slot(10, 0))
    assert "dropoff_address" not in client.get("/info").json()
    for viewer in (customer, stringer):
        for job in client.get("/jobs", headers=auth_header(viewer["access_token"])).json():
            assert "dropoff_address" not in job


# --- listing / roles ---------------------------------------------------------
def test_stringer_sees_all_jobs_with_customer_info(customer, stringer):
    make_job(customer["access_token"], dropoff_at=next_open_slot(10, 0))
    resp = client.get("/jobs", headers=auth_header(stringer["access_token"]))
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["customer"]["name"] == "Alice"


def test_customer_only_sees_own_jobs(customer, stringer):
    other = register("Bob", "bob@example.com", "password", "customer")
    make_job(customer["access_token"], racquet="A")
    make_job(other["access_token"], racquet="B")
    resp = client.get("/jobs", headers=auth_header(customer["access_token"]))
    assert [j["racquet"] for j in resp.json()] == ["A"]


# --- cross-off / active queue (Task 4 backend) -------------------------------
def test_active_statuses_and_cross_off(customer, stringer):
    ids = [make_job(customer["access_token"], racquet=r).json()["id"] for r in ("A", "B", "C")]
    jobs = client.get("/jobs", headers=auth_header(stringer["access_token"])).json()
    active = [j for j in jobs if j["status"] in ("requested", "received", "in_progress")]
    assert len(active) == 3

    resp = client.patch(
        f"/jobs/{ids[0]}", json={"status": "completed"},
        headers=auth_header(stringer["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    jobs = client.get("/jobs", headers=auth_header(stringer["access_token"])).json()
    active = [j for j in jobs if j["status"] in ("requested", "received", "in_progress")]
    assert len(active) == 2


def test_ready_email_and_pickup_confirmation(customer, stringer, sent):
    job = make_job(customer["access_token"]).json()

    # Stringer marks it ready (completed) -> customer gets a ready email.
    r = client.patch(
        f"/jobs/{job['id']}", json={"status": "completed"},
        headers=auth_header(stringer["access_token"]),
    )
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert any("ready" in subj.lower() for _, subj, _ in sent)

    # Customer confirms a valid pickup time -> stringer gets notified.
    r = client.patch(
        f"/jobs/{job['id']}", json={"pickup_eta": next_open_slot(11, 0)},
        headers=auth_header(customer["access_token"]),
    )
    assert r.status_code == 200 and r.json()["pickup_eta"] is not None
    assert any("pickup scheduled" in subj.lower() for _, subj, _ in sent)


def test_ready_email_only_fires_once(customer, stringer, sent):
    job = make_job(customer["access_token"]).json()
    for _ in range(2):
        client.patch(
            f"/jobs/{job['id']}", json={"status": "completed"},
            headers=auth_header(stringer["access_token"]),
        )
    ready = [s for s in sent if "ready" in s[1].lower()]
    assert len(ready) == 1  # no duplicate emails on re-PATCH to same status


def test_pickup_eta_off_grid_rejected(customer):
    job = make_job(customer["access_token"]).json()
    r = client.patch(
        f"/jobs/{job['id']}", json={"pickup_eta": next_open_slot(11, 7)},
        headers=auth_header(customer["access_token"]),
    )
    assert r.status_code == 422


def test_customer_cannot_advance_status(customer):
    job = make_job(customer["access_token"]).json()
    resp = client.patch(
        f"/jobs/{job['id']}", json={"status": "completed"},
        headers=auth_header(customer["access_token"]),
    )
    assert resp.status_code == 403
    resp = client.patch(
        f"/jobs/{job['id']}", json={"status": "cancelled"},
        headers=auth_header(customer["access_token"]),
    )
    assert resp.status_code == 200
