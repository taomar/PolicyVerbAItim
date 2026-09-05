"""An administrator can issue an API key, and only where that means something.

WHAT THIS FILE IS FOR

Three questions, and the third is the one that is easy to get wrong:

1. Does issuing, listing and revoking work?
2. Is the surface refused to everyone it should be refused to?
3. **Are the refusals refusing for the right reason?** A guard that rejects
   everything passes every refusal test ever written. So each refusal below is
   paired with a control that must succeed, and the pair only passes if the
   guard is discriminating rather than merely closed.

WHY THE DATABASE IS WIRED IN TWO PLACES

The router takes its session through `Depends(get_session)`, which a test
overrides the ordinary way. The authentication path does not: `_try_managed_key`
reaches for `get_sessionmaker()` directly, because `enforce_rbac` runs in front
of every route in the application and must not acquire a connection for the
overwhelming majority of requests that never present a key. So the tests point
both at the same SQLite engine.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from policy_platform.api import authz
from policy_platform.api.authz import (
    SUBSCRIPTION_KEY_HEADER,
    Principal,
    enforce_rbac,
    require_authenticated_principal,
)
from policy_platform.api.roles import ADMIN, POLICY_AUTHOR, USE, VIEWER
from policy_platform.api.routers import integration
from policy_platform.domain.base import Base
from policy_platform.domain.models import ApiSubscriptionKey, AuditEvent
from policy_platform.infrastructure.persistence.db import get_session
from policy_platform.infrastructure.settings import Settings

pytestmark = pytest.mark.anyio

CONFIGURED_KEY = "a-configured-pre-shared-key-0123456789"


# JSONB and UUID are Postgres-only. Compiling them for SQLite lets the real
# tables be built here rather than a stand-in schema that could drift.
@compiles(JSONB, "sqlite")
def _compile_jsonb(_type, _compiler, **_kw) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid(_type, _compiler, **_kw) -> str:
    return "CHAR(36)"


def _settings(**overrides: Any) -> Settings:
    """A real `Settings`, with every field this surface reads pinned.

    `local` in particular. `Settings` reads `.env` for anything a caller does
    not pass, so leaving it out would make these tests depend on whether the
    developer's machine has `LOCAL=true` — the difference between a test that
    asserts something and a test that reports the machine it ran on.
    """

    values: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///unused",
        "alembic_database_url": "sqlite:///unused",
        "environment": "development",
        "rbac_enabled": True,
        "dev_auth_enabled": True,
        "trust_platform_auth_header": False,
        "entra_issuer": None,
        "entra_audience": None,
        "entra_jwks_url": None,
        "local_accounts_enabled": False,
        "policy_subscription_key": CONFIGURED_KEY,
        "policy_subscription_key_identity": "expenses-agent",
        "policy_subscription_key_role": VIEWER,
        "local": True,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
async def harness(monkeypatch):
    """The integration router behind the real global guard, on a real database.

    The app carries `dependencies=[Depends(enforce_rbac)]` exactly as
    `create_app` does, so band enforcement here is the production mechanism
    rather than a restatement of it. `/consume` stands in for the decision
    endpoints: it is not a copy of their logic, it is the same dependency they
    use — `require_authenticated_principal` — which is the part a subscription
    key has to satisfy.
    """

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    state: dict[str, Settings] = {"settings": _settings()}
    monkeypatch.setattr(authz, "get_settings", lambda: state["settings"])
    monkeypatch.setattr(integration, "get_settings", lambda: state["settings"])
    monkeypatch.setattr(authz, "get_sessionmaker", lambda: maker)

    # `/consume` needs a band for the same reason every real route does: the
    # global guard denies anything it cannot classify. Registering it here is
    # what mounting a real endpoint does, and it keeps the route subject to the
    # genuine guard rather than exempt from it.
    monkeypatch.setattr(
        authz, "OPERATION_BANDS", {**authz.OPERATION_BANDS, ("GET", "/consume"): USE}
    )

    app = FastAPI(dependencies=[Depends(enforce_rbac)])
    app.include_router(integration.router)

    @app.get("/consume")
    async def consume(principal: Principal = Depends(require_authenticated_principal)) -> dict:
        return {"identity": principal.identity, "role": principal.role, "source": principal.source}

    async def _override():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        http.configure = lambda **o: state.update(settings=_settings(**o))  # type: ignore[attr-defined]
        http.maker = maker  # type: ignore[attr-defined]
        yield http

    await engine.dispose()


def _as(role: str) -> dict[str, str]:
    return {"X-Dev-Role": role}


def _key(value: str) -> dict[str, str]:
    return {SUBSCRIPTION_KEY_HEADER: value}


async def _issue(client, label: str) -> str:
    """Issue a key as an administrator and return the plaintext."""

    response = await client.post("/api/integration/keys", json={"label": label}, headers=_as(ADMIN))
    assert response.status_code == 201, response.text
    return response.json()["key"]


# ── the deployment gate ──────────────────────────────────────────────


async def test_the_surface_is_refused_when_the_deployment_does_not_own_its_keys(harness) -> None:
    """Where a gateway fronts the API, this deployment does not issue keys.

    404 rather than 403 on purpose: the feature does not exist here, and
    "forbidden" would assert that it does and that the caller lacks permission.
    """

    harness.configure(local=False)

    for method, path in (
        ("get", "/api/integration/keys"),
        ("delete", f"/api/integration/keys/{uuid.uuid4()}"),
    ):
        response = await getattr(harness, method)(path, headers=_as(ADMIN))
        assert response.status_code == 404, f"{method} {path} was not refused"
        assert response.json()["detail"]["code"] == "integration_keys_not_available"

    created = await harness.post(
        "/api/integration/keys", json={"label": "nope"}, headers=_as(ADMIN)
    )
    assert created.status_code == 404
    assert created.json()["detail"]["code"] == "integration_keys_not_available"


async def test_the_same_administrator_is_allowed_when_the_deployment_does_own_its_keys(
    harness,
) -> None:
    """The control for the gate.

    Same caller, same role, same three routes — only `local` differs. Without
    this, the refusal above would also pass if the endpoints were broken, or if
    admin were refused everywhere.
    """

    listed = await harness.get("/api/integration/keys", headers=_as(ADMIN))
    assert listed.status_code == 200
    assert listed.json() == {"keys": []}

    created = await harness.post(
        "/api/integration/keys", json={"label": "expenses-bot"}, headers=_as(ADMIN)
    )
    assert created.status_code == 201

    revoked = await harness.delete(
        f"/api/integration/keys/{created.json()['id']}", headers=_as(ADMIN)
    )
    assert revoked.status_code == 200


async def test_the_capability_probe_answers_both_ways_and_names_nothing_else(harness) -> None:
    """The menu needs an answer even when the answer is "no".

    So the probe is the one route here that is not gated — a probe that refuses
    when the answer is negative cannot communicate a negative. It must also say
    nothing beyond the shape of the deployment.
    """

    yes = await harness.get("/api/integration/capability", headers=_as(VIEWER))
    assert yes.status_code == 200
    assert yes.json() == {"manages_subscription_keys": True}

    harness.configure(local=False)
    no = await harness.get("/api/integration/capability", headers=_as(VIEWER))
    assert no.status_code == 200
    assert no.json() == {"manages_subscription_keys": False}


# ── the role gate ────────────────────────────────────────────────────


@pytest.mark.parametrize("role", [VIEWER, POLICY_AUTHOR])
async def test_only_an_administrator_may_see_or_issue_keys(harness, role: str) -> None:
    """Issuing a credential is an administrative act, and so is knowing which exist.

    The list is banded with the writes rather than at READ because these rows
    describe how machine callers reach the decision API — which is
    reconnaissance, not governed content.
    """

    listed = await harness.get("/api/integration/keys", headers=_as(role))
    assert listed.status_code == 403

    created = await harness.post(
        "/api/integration/keys", json={"label": "mine"}, headers=_as(role)
    )
    assert created.status_code == 403


async def test_a_viewer_is_refused_here_but_not_everywhere(harness) -> None:
    """The control for the role gate.

    A viewer reaching the capability probe proves the 403s above come from the
    band on these particular routes, not from the viewer role being unable to
    reach anything at all.
    """

    response = await harness.get("/api/integration/capability", headers=_as(VIEWER))
    assert response.status_code == 200


# ── the key actually works, and stops working ────────────────────────


async def test_an_issued_key_authenticates_a_real_call(harness) -> None:
    """The control that makes every refusal below meaningful.

    Through the global guard and `require_authenticated_principal` — the same
    dependency the decision endpoints use — rather than by calling a helper,
    because what is being tested is that the key satisfies the real path.
    """

    plaintext = await _issue(harness, "expenses-bot")

    response = await harness.get("/consume", headers=_key(plaintext))

    assert response.status_code == 200, response.text
    assert response.json()["source"] == "subscription-key"
    assert response.json()["identity"] == "expenses-agent"


async def test_a_revoked_key_stops_working_while_a_second_key_carries_on(harness) -> None:
    """Rotation without downtime, demonstrated rather than asserted.

    Two keys are live at once; one is revoked; the other keeps working. If the
    store only ever held one key, or if revocation were implemented as "reject
    everything", the second half of this test would fail.
    """

    old = await _issue(harness, "old-integration")
    new = await _issue(harness, "new-integration")

    assert (await harness.get("/consume", headers=_key(old))).status_code == 200
    assert (await harness.get("/consume", headers=_key(new))).status_code == 200

    listed = await harness.get("/api/integration/keys", headers=_as(ADMIN))
    old_id = next(k["id"] for k in listed.json()["keys"] if k["label"] == "old-integration")
    assert (await harness.delete(f"/api/integration/keys/{old_id}", headers=_as(ADMIN))).status_code == 200

    assert (await harness.get("/consume", headers=_key(old))).status_code == 401
    assert (await harness.get("/consume", headers=_key(new))).status_code == 200


async def test_an_unknown_key_is_refused_and_does_not_become_an_anonymous_request(
    harness,
) -> None:
    """A rejected credential must not be laundered into a weaker accepted one."""

    response = await harness.get("/consume", headers=_key("not-a-key-anyone-issued"))

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "subscription_key_rejected"


async def test_an_issued_key_is_refused_once_the_deployment_stops_owning_its_keys(
    harness,
) -> None:
    """`local` gates verification, not only issuance.

    The user's requirement was that the feature is off in the backend as well as
    the menu. It is also the safe direction: behind a gateway an administrator
    cannot see or revoke these keys, and a credential nobody can revoke is worse
    than one that no longer authenticates.
    """

    plaintext = await _issue(harness, "expenses-bot")
    assert (await harness.get("/consume", headers=_key(plaintext))).status_code == 200

    harness.configure(local=False)

    assert (await harness.get("/consume", headers=_key(plaintext))).status_code == 401


async def test_the_configured_environment_key_still_works(harness) -> None:
    """The regression control for making the principal chain asynchronous.

    Exercised as a real request through the global guard, not by calling
    `_establish_principal`, because the thing that could break is the dependency
    wiring rather than the function body.
    """

    response = await harness.get("/consume", headers=_key(CONFIGURED_KEY))

    assert response.status_code == 200, response.text
    assert response.json()["source"] == "subscription-key"


async def test_issuing_a_key_does_not_disturb_the_configured_one(harness) -> None:
    """Issued keys are additional, never a replacement.

    Superseding the environment key would break any deployment where a gateway
    supplies it as the backend credential, at the instant an administrator first
    clicked Generate.
    """

    issued = await _issue(harness, "expenses-bot")

    assert (await harness.get("/consume", headers=_key(CONFIGURED_KEY))).status_code == 200
    assert (await harness.get("/consume", headers=_key(issued))).status_code == 200


# ── the secret does not leak ─────────────────────────────────────────


async def test_the_key_is_returned_once_and_appears_nowhere_afterwards(harness) -> None:
    """Generation is the only disclosure. Everything else holds a hash."""

    plaintext = await _issue(harness, "expenses-bot")

    listed = await harness.get("/api/integration/keys", headers=_as(ADMIN))
    assert plaintext not in listed.text

    async with harness.maker() as session:
        stored = (await session.execute(select(ApiSubscriptionKey))).scalars().all()
        assert len(stored) == 1
        assert stored[0].key_hash != plaintext
        assert plaintext not in stored[0].key_hash

        events = (await session.execute(select(AuditEvent))).scalars().all()
        assert [e.event_type for e in events] == ["api_subscription_key.issued"]
        for event in events:
            assert plaintext not in str(event.details_json)
            assert plaintext not in str(event.actor)


async def test_no_log_record_repeats_the_key(harness, caplog) -> None:
    """Not the issued key, and not a rejected one.

    A refused credential is the more tempting one to log, and the more dangerous:
    a key that failed because it was stale is still a live key somewhere else.
    """

    with caplog.at_level("DEBUG"):
        plaintext = await _issue(harness, "expenses-bot")
        await harness.get("/consume", headers=_key(plaintext))
        await harness.get("/consume", headers=_key("a-wrong-key-value-9876543210"))

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert plaintext not in logged
    assert "a-wrong-key-value-9876543210" not in logged


async def test_revocation_is_audited_and_names_the_key_without_quoting_it(harness) -> None:
    """A credential change is a security event, so it leaves a trail.

    The trail names the label and the row id. It does not name the key, because
    `GET /api/audit-events` is readable by any viewer.
    """

    plaintext = await _issue(harness, "expenses-bot")
    listed = await harness.get("/api/integration/keys", headers=_as(ADMIN))
    key_id = listed.json()["keys"][0]["id"]

    await harness.delete(f"/api/integration/keys/{key_id}", headers=_as(ADMIN))

    async with harness.maker() as session:
        events = (await session.execute(select(AuditEvent))).scalars().all()
        types = sorted(e.event_type for e in events)
        assert types == ["api_subscription_key.issued", "api_subscription_key.revoked"]
        for event in events:
            assert event.details_json["label"] == "expenses-bot"
            assert str(event.entity_id) == key_id
            assert plaintext not in str(event.details_json)


# ── the cost of the change ───────────────────────────────────────────


async def test_a_request_with_no_key_header_opens_no_database_session(harness, monkeypatch) -> None:
    """`enforce_rbac` runs in front of every route, so it must stay free.

    A session here would mean every page view in the admin application paid for
    a connection in order to support a credential type it never presents.
    """

    opened: list[str] = []
    real = authz.get_sessionmaker

    def _spy():
        opened.append("session")
        return real()

    monkeypatch.setattr(authz, "get_sessionmaker", _spy)

    assert (await harness.get("/api/integration/capability", headers=_as(VIEWER))).status_code == 200
    assert (await harness.get("/consume", headers=_as(ADMIN))).status_code in (200, 401)

    assert opened == [], "the authentication path opened a session for a request with no key"


async def test_a_request_with_a_key_header_does_open_one(harness, monkeypatch) -> None:
    """The control for the test above.

    Without it, "no session was opened" would also pass if the store were never
    consulted at all — which would mean issued keys never worked.

    WHY TWO AND NOT ONE

    An audited route resolves the caller twice, and always has: once in
    `enforce_rbac` (which asks "is this permitted?") and once in
    `require_authenticated_principal` (which asks "who is this, regardless of
    whether enforcement is switched on?"). Those are different questions and
    `authz.py` deliberately keeps them apart. Before this change each resolution
    was a string comparison and the duplication was free; now each one is an
    indexed lookup, so it is two.

    The number is asserted exactly rather than as "at least one" so that a
    future change to the dependency wiring shows up here as a number rather than
    passing silently. It is deliberately **not** fixed by memoising the
    principal on the request: this repository holds a standing decision against
    same-answer-as-last-time shortcuts, and quietly introducing one on the
    authentication path to save a hash lookup is not a trade worth making
    without being asked.
    """

    plaintext = await _issue(harness, "expenses-bot")

    opened: list[str] = []
    real = authz.get_sessionmaker

    def _spy():
        opened.append("session")
        return real()

    monkeypatch.setattr(authz, "get_sessionmaker", _spy)

    assert (await harness.get("/consume", headers=_key(plaintext))).status_code == 200
    assert opened == ["session", "session"]


async def test_an_admin_only_route_resolves_the_caller_once(harness, monkeypatch) -> None:
    """The other half of the count above.

    A route carrying only the global guard opens one session, not two — which
    shows the pair in the previous test comes from the second dependency and not
    from the key path looking twice on its own.
    """

    plaintext = await _issue(harness, "expenses-bot")

    opened: list[str] = []
    real = authz.get_sessionmaker

    def _spy():
        opened.append("session")
        return real()

    monkeypatch.setattr(authz, "get_sessionmaker", _spy)

    # 403, because a key resolves to `viewer` and this route is ADMINISTER. The
    # status is beside the point: the caller was still resolved, once.
    await harness.get("/api/integration/keys", headers=_key(plaintext))
    assert opened == ["session"]
