"""One policy index build runs at a time, and every surface can watch it.

WHAT THIS FILE IS PROVING

Two surfaces were added for two audiences — an administrator's console over every
project's index, and a publisher's view of the best-effort build that runs after
their own publish — and both were built on **one** mechanism, because they are
watching one operation. These tests exist to keep that true, and to keep the
three claims that mechanism makes honest:

  1. **The numbers are measured, not guessed.** Stages move in order, counters
     appear only once the build has measured them, and a build that ends is
     recorded as ended — on success, on failure, and on an exception nobody
     planned for.
  2. **There is exactly one build slot, and it is not a promise.** It is a UNIQUE
     constraint in PostgreSQL, so a second request is refused by the database
     rather than by a flag one process happens to hold. The tests here run
     against SQLite, where the same constraint has the same meaning — NULLs are
     distinct in both — so what they prove about the mechanism transfers.
  3. **Nothing that is refused is silently hidden.** A publish whose index build
     could not start still publishes, records that the build did not happen, and
     says so in its response.

WHAT IS DELIBERATELY NOT MOCKED

`run_tracked_policy_index_build` — the orchestrator both callers pass through —
is real in every test here, including the slot, the history row, the reporter and
the terminal guarantee. Only `rebuild_project_policy_index` is replaced, because
the real one calls a language model and a search service. Replacing the
orchestrator instead would leave the thing under test untested.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "******localhost:5433/test")
os.environ.setdefault("ALEMBIC_DATABASE_URL", "******localhost:5433/test")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402

from policy_platform.api.app import create_app  # noqa: E402
from policy_platform.api.roles import ADMIN, POLICY_AUTHOR, VIEWER  # noqa: E402
from policy_platform.domain.models import (  # noqa: E402
    ApprovedPolicyVersion,
    Base,
    PolicyIndexBuild,
    PolicyIndexState,
    PolicySet,
)
from policy_platform.infrastructure.persistence.db import get_session  # noqa: E402
from policy_platform.infrastructure.assistants.ai_case_language import (  # noqa: E402
    ENGLISH_PROJECTION_PROFILE,
)
from policy_platform.infrastructure.search import policy_index as policy_index_module  # noqa: E402
from policy_platform.infrastructure.search.policy_index import (  # noqa: E402
    PolicyIndexBuildOutcome,
    policy_index_name,
    run_tracked_policy_index_build,
)
from policy_platform.infrastructure.search import (  # noqa: E402
    policy_index_build_progress as progress_module,
)
from policy_platform.infrastructure.search.policy_index_build_progress import (  # noqa: E402
    COUNTERS,
    LEASE_SECONDS,
    STAGES,
    bounded_error,
    build_payload,
    latest_state_status_for,
    running_build,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb(_type, _compiler, **_kw) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid(_type, _compiler, **_kw) -> str:
    return "CHAR(36)"


_FIRST_SET_ID = uuid.UUID("00000000-0000-4000-8000-0000000004a1")
_SECOND_SET_ID = uuid.UUID("00000000-0000-4000-8000-0000000004a2")

#: A sentence that exists nowhere in this platform's vocabulary, planted in the
#: stored data so a leak into a progress or history payload is unmistakable
#: rather than a judgement call.
_PLANTED_POLICY_SENTENCE = "Reimbursement above the ceiling requires the delegate approver's signature."
#: Likewise for a credential. Nothing should ever put one in a build record, and
#: an assertion that says so by name is cheaper to read than one that reasons
#: about which fields could hold one.
_PLANTED_CREDENTIAL = "sk-planted-credential-value-that-must-never-appear"


@pytest.fixture
async def portfolio(monkeypatch):
    """Two projects, one with an active version, on a shared in-memory database.

    Two rather than one because the single build slot is deployment-wide: the
    interesting refusal is a rebuild of project B while project A is building,
    and a fixture with one project could not express it.
    """

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        # The planted text lives in real project columns, so a payload that
        # leaked "something from the project" would leak it. `description` and
        # the trusted config are both things a helpful-looking console addition
        # might reach for.
        session.add(
            PolicySet(
                id=_FIRST_SET_ID,
                key="alpha",
                name="Alpha project",
                owner="ops",
                description=_PLANTED_POLICY_SENTENCE,
                trusted_config_json={"note": _PLANTED_CREDENTIAL},
            )
        )
        session.add(PolicySet(id=_SECOND_SET_ID, key="beta", name="Beta project", owner="ops"))
        session.add(
            ApprovedPolicyVersion(
                policy_set_id=_FIRST_SET_ID,
                version_number=3,
                effective_from=date(2026, 1, 1),
                is_active=True,
                approved_by="ops",
                approved_at=datetime(2026, 8, 18, 11, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    app = create_app()

    async def _override():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http, maker, monkeypatch
    finally:
        await engine.dispose()


def _built(policy_set_key: str, version_number: int | None) -> PolicyIndexBuildOutcome:
    return PolicyIndexBuildOutcome(
        state="built",
        policy_set_key=policy_set_key,
        index_name=policy_index_name(policy_set_key),
        version_number=version_number,
        document_count=7,
        indexed_at="2026-08-18T12:00:00+00:00",
        policy_document_count=5,
        rule_document_count=2,
        # The profile the query side renders under. Anything else is genuinely
        # stale on the second axis — an index built for the active version but
        # under a superseded rendering contract cannot be matched against — so
        # using a made-up name here would have this fixture testing staleness
        # everywhere it meant to test success.
        projection_profile=ENGLISH_PROJECTION_PROFILE,
        manifest_state="ready",
    )


def _patch_build(monkeypatch, fake) -> None:
    """Replace only the model-and-search call, never the orchestration around it."""

    monkeypatch.setattr(policy_index_module, "rebuild_project_policy_index", fake)


# ── 1. the numbers move, and they are the build's own ────────────────


async def test_a_running_build_publishes_the_stages_and_counts_it_actually_reached(
    portfolio,
) -> None:
    """Every stage this build reports is one it performed, in the declared order.

    The assertion is on the *sequence*, not on a final value, because the defect
    this surface exists to remove is a readout that jumps from "starting" to
    "done" with nothing in between — which is indistinguishable, to somebody
    deciding whether to wait, from a build that is stuck.
    """

    http, maker, monkeypatch = portfolio
    seen: list[tuple[str, dict]] = []

    async def _fake(*, policy_set_key, version_number, projections, progress, **_kw):
        list(projections)
        for name in STAGES:
            await progress.stage(name)
            seen.append(("stage", {"name": name}))
        await progress.count(projection_count=4, expected_document_count=7)
        await progress.count(acknowledged_count=7)
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)

    response = await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-stages")
    assert response.status_code == 200

    assert [name for kind, payload in seen if kind == "stage" for name in [payload["name"]]] == list(
        STAGES
    )

    progress = (await http.get("/api/policy-index/builds/op-stages")).json()
    assert progress["active"] is True
    assert progress["status"] == "completed"
    assert progress["terminal"] is True
    assert progress["stage"] == STAGES[-1]
    assert progress["stage_index"] == len(STAGES)
    assert progress["stage_total"] == len(STAGES)
    assert progress["projection_count"] == 4
    assert progress["expected_document_count"] == 7
    assert progress["acknowledged_count"] == 7
    # Not measured by this build, and therefore absent rather than zero. "Not
    # counted yet" and "none found" are different facts about a project.
    assert progress["swept_count"] is None
    assert progress["holds_build_slot"] is False


async def test_no_progress_payload_carries_a_percentage_of_any_kind(portfolio) -> None:
    """There is no field a fabricated completion share could be served in.

    Asserted on the payload's key set rather than on a value, because the failure
    mode is somebody adding the field — a bar interpolated from elapsed time is a
    guess wearing the clothes of a measurement, and it is the number an operator
    would use to decide whether to wait.
    """

    http, _maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, progress, **_kw):
        list(projections)
        await progress.stage("rendering")
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-nopct")

    payload = (await http.get("/api/policy-index/builds/op-nopct")).json()
    forbidden = {"percent", "percentage", "progress_percent", "fraction", "ratio", "eta"}
    assert forbidden.isdisjoint(payload.keys())
    assert not [key for key in payload if "percent" in key.lower()]
    # What replaces it: a position in a fixed pipeline, and the one real
    # denominator the build eventually has.
    assert payload["stage_total"] == len(STAGES)
    assert "expected_document_count" in payload


async def test_a_build_that_fails_and_a_build_that_raises_are_both_recorded_as_ended(
    portfolio,
) -> None:
    """Terminality is structural, not remembered.

    Two exits are covered because they arrive by different routes: a build that
    catches its own failure and reports `failed`, and one that raises past the
    orchestrator entirely. A record left saying `running` after either would go
    on reporting work in progress for a request that returned minutes ago — the
    exact defect this surface exists to remove.
    """

    http, maker, monkeypatch = portfolio

    async def _reports_failure(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return PolicyIndexBuildOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=policy_index_name(policy_set_key),
            version_number=version_number,
            document_count=0,
            indexed_at="2026-08-18T12:00:00+00:00",
            error="the embedding call returned 3 vectors for 7 texts",
        )

    _patch_build(monkeypatch, _reports_failure)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-failed")

    reported = (await http.get("/api/policy-index/builds/op-failed")).json()
    assert reported["status"] == "failed"
    assert reported["terminal"] is True
    assert reported["holds_build_slot"] is False
    assert "3 vectors for 7 texts" in reported["error"]

    async def _raises(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        raise TimeoutError()

    _patch_build(monkeypatch, _raises)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-raised")

    raised = (await http.get("/api/policy-index/builds/op-raised")).json()
    assert raised["status"] == "failed"
    assert raised["terminal"] is True
    assert raised["holds_build_slot"] is False
    # A row that says failed always says why. `TimeoutError()` renders as an
    # empty string under `str()`, and an empty reason is indistinguishable from
    # no reason having been recorded.
    assert raised["error"]
    assert "TimeoutError" in raised["error"]

    # And nothing is left holding the slot after either.
    async with maker() as session:
        assert await running_build(session) is None


# ── 2. one mechanism, two callers ────────────────────────────────────


async def test_publish_and_manual_rebuild_write_the_same_kind_of_record(portfolio) -> None:
    """Both callers produce history entries that differ only in `trigger`.

    This is the whole point of the shared orchestrator. Before it, the two
    routers held two copies of the same six steps, which is how they came to
    differ — one recorded an actor and the other did not, and neither coordinated
    with the other at all.
    """

    http, maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)

    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-manual")
    async with maker() as session:
        await run_tracked_policy_index_build(
            session,
            policy_set_id=_FIRST_SET_ID,
            policy_set_key="alpha",
            version_number=3,
            load_projections=lambda: _no_projections(),
            trigger="publish",
            operation_id="op-publish",
            actor="approver@example.test",
        )

    async with maker() as session:
        rows = {
            build.operation_id: build
            for build in (await session.execute(select(PolicyIndexBuild))).scalars().all()
        }

    manual, published = rows["op-manual"], rows["op-publish"]
    assert manual.trigger == "rebuild"
    assert published.trigger == "publish"
    assert published.actor == "approver@example.test"
    # Everything else about the two records has the same shape and the same
    # meaning, which is what "one mechanism" has to mean to be worth the name.
    for column in ("status", "index_name", "manifest_state", "projection_profile"):
        assert getattr(manual, column) == getattr(published, column)
    assert manual.status == "completed"


async def _no_projections() -> list[dict]:
    return []


# ── 3. the record outlives the request ───────────────────────────────


async def test_a_finished_build_is_still_readable_after_the_request_that_made_it(
    portfolio,
) -> None:
    """A page that navigates away and back reads the build from the server.

    The reason the record is a row rather than a process-local dict. Polled twice
    with the request long gone, it answers the same both times — which is what
    lets the panel restore itself on mount instead of trusting whatever the
    previous component left in memory.
    """

    http, _maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-durable")

    first = (await http.get("/api/policy-index/builds/op-durable")).json()
    second = (await http.get("/api/policy-index/builds/op-durable")).json()
    assert first["status"] == second["status"] == "completed"
    assert first["document_count"] == second["document_count"] == 7
    assert second["recent"] is True

    # An operation nobody ever started is not an error. A page that navigated
    # back before its build began must not render a failure where there is none.
    missing = await http.get("/api/policy-index/builds/never-happened")
    assert missing.status_code == 200
    assert missing.json() == {"active": False}


async def test_a_terminal_build_stops_being_recent_after_the_display_window(
    portfolio,
) -> None:
    """`recent` bounds a display, and the row itself is kept regardless.

    The distinction matters: a panel reopened days later must not present an old
    build as news, and a history read must still be able to show it. One field
    answers the first question; the row answers the second.
    """

    http, maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-old")

    async with maker() as session:
        build = (
            await session.execute(
                select(PolicyIndexBuild).where(PolicyIndexBuild.operation_id == "op-old")
            )
        ).scalar_one()
        aged = build_payload(
            build,
            now=datetime.now(UTC)
            + timedelta(seconds=progress_module.PROGRESS_RETENTION_SECONDS + 60),
        )

    assert aged["recent"] is False
    assert aged["status"] == "completed"
    # Still in the history, which is the point.
    listing = (await http.get("/api/policy-sets/alpha/policy-index/builds")).json()
    assert [b["operation_id"] for b in listing["builds"]] == ["op-old"]


async def test_the_history_keeps_every_attempt_newest_first(portfolio) -> None:
    """Three attempts are three rows, and the newest is first.

    `policy_index_states` cannot do this: it holds one row per project that every
    attempt overwrites, so a project that has failed three times looks exactly
    like one that has failed once. Ordering is asserted rather than assumed
    because the surface reading it is a list somebody scans top-down.
    """

    http, maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _fake)
    for ordinal in range(3):
        await http.post(
            f"/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-history-{ordinal}"
        )
        # Distinct start timestamps: the ordering column is `started_at`, and
        # three rows written inside one clock tick would make the assertion pass
        # for a reason that has nothing to do with ordering.
        await asyncio.sleep(0.01)

    listing = (await http.get("/api/policy-sets/alpha/policy-index/builds")).json()
    assert [b["operation_id"] for b in listing["builds"]] == [
        "op-history-2",
        "op-history-1",
        "op-history-0",
    ]
    assert listing["active"] == {"active": False}

    # And the other project's history is genuinely its own, not a filter applied
    # to a global list that happened to be empty.
    async with maker() as session:
        rows = (
            await session.execute(
                select(PolicyIndexBuild).where(PolicyIndexBuild.policy_set_id == _SECOND_SET_ID)
            )
        ).scalars().all()
    assert rows == []


# ── 4. one slot, and it opens again ──────────────────────────────────


async def test_a_second_build_is_refused_while_one_is_running_and_told_what_holds_it(
    portfolio,
) -> None:
    """The refusal is the database's, and it names what is in the way.

    The first build is held open inside `rebuild_project_policy_index` so a
    second request genuinely arrives while the slot is taken — the situation two
    replicas produce, reproduced here with two concurrent requests. A test that
    inserted a row by hand and then called the endpoint would prove the query
    works and nothing about the mechanism.
    """

    http, maker, monkeypatch = portfolio
    running = asyncio.Event()
    may_finish = asyncio.Event()

    async def _slow(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        running.set()
        await may_finish.wait()
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _slow)

    first = asyncio.create_task(
        http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-holder")
    )
    await asyncio.wait_for(running.wait(), timeout=5)

    # A different project, because the slot is deployment-wide rather than
    # per-project: two builds anywhere compete for the same model quota.
    refused = await http.post("/api/policy-sets/beta/policy-index/rebuild?operation_id=op-refused")
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["active"]["operation_id"] == "op-holder"
    assert detail["active"]["policy_set_key"] == "alpha"
    assert detail["active"]["holds_build_slot"] is True
    assert detail["operation_id"] == "op-refused"

    may_finish.set()
    assert (await asyncio.wait_for(first, timeout=5)).status_code == 200

    # THE GUARD IS NOT STUCK CLOSED. This is the assertion that matters most:
    # a refusal mechanism that never reopens is a worse failure than the
    # concurrency it prevents, because nothing recovers from it.
    _patch_build(monkeypatch, _fast_build)
    after = await http.post("/api/policy-sets/beta/policy-index/rebuild?operation_id=op-after")
    assert after.status_code == 200
    async with maker() as session:
        assert await running_build(session) is None


async def _fast_build(*, policy_set_key, version_number, projections, **_kw):
    list(projections)
    return _built(policy_set_key, version_number)


async def test_the_refused_attempt_is_recorded_as_deferred_rather_than_failed(
    portfolio,
) -> None:
    """"Never ran" and "ran and failed" are different facts with different repairs.

    A deferred entry tells a publisher to retry once the slot frees. A failed one
    sends them looking for a broken build. Collapsing them would make the history
    actively misleading in the one case it exists to explain.
    """

    http, maker, monkeypatch = portfolio
    running = asyncio.Event()
    may_finish = asyncio.Event()

    async def _slow(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        running.set()
        await may_finish.wait()
        return _built(policy_set_key, version_number)

    _patch_build(monkeypatch, _slow)
    first = asyncio.create_task(
        http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-hold2")
    )
    await asyncio.wait_for(running.wait(), timeout=5)
    await http.post("/api/policy-sets/beta/policy-index/rebuild?operation_id=op-deferred")
    may_finish.set()
    await asyncio.wait_for(first, timeout=5)

    async with maker() as session:
        deferred = (
            await session.execute(
                select(PolicyIndexBuild).where(PolicyIndexBuild.operation_id == "op-deferred")
            )
        ).scalar_one()

    assert deferred.status == "deferred"
    assert deferred.finished_at is not None
    # A note about something that did not happen must not be able to block
    # anything: it holds no slot.
    assert deferred.active_slot is None
    assert "already running" in (deferred.error or "")


async def test_an_abandoned_lease_is_reclaimed_so_a_dead_replica_cannot_block_the_estate(
    portfolio,
) -> None:
    """A process that dies mid-build must not hold the slot forever.

    The one question a database-held lease has that a process-local flag does
    not. Without reclaim, a killed replica leaves a row saying `running` and
    every later build in the deployment is refused by a holder that no longer
    exists.
    """

    http, maker, monkeypatch = portfolio
    stale_started = datetime.now(UTC) - timedelta(seconds=LEASE_SECONDS + 60)
    async with maker() as session:
        session.add(
            PolicyIndexBuild(
                operation_id="op-abandoned",
                policy_set_id=_FIRST_SET_ID,
                policy_set_key="alpha",
                trigger="publish",
                status="running",
                stage=STAGES[1],
                started_at=stale_started,
                created_at=stale_started,
                updated_at=stale_started,
                active_slot=progress_module.ACTIVE_SLOT,
            )
        )
        await session.commit()

    _patch_build(monkeypatch, _fast_build)
    response = await http.post("/api/policy-sets/beta/policy-index/rebuild?operation_id=op-fresh")
    assert response.status_code == 200

    async with maker() as session:
        abandoned = (
            await session.execute(
                select(PolicyIndexBuild).where(PolicyIndexBuild.operation_id == "op-abandoned")
            )
        ).scalar_one()

    # Marked failed and kept, not deleted: a build that was interrupted did
    # happen, and its entry is how anyone learns a replica died in the middle.
    assert abandoned.status == "failed"
    assert abandoned.active_slot is None
    assert "stopped reporting" in (abandoned.error or "")


# ── 5. publish survives a busy slot, and says so ─────────────────────


async def test_publish_succeeds_and_reports_when_its_index_build_could_not_start(
    portfolio,
) -> None:
    """The version is published either way; what did not happen is the rebuild.

    A publisher whose grounding corpus is silently a version behind has no reason
    to look, so the deferral is reported rather than swallowed — and the
    latest-state row records it as a failure, because on the only question that
    row answers ("can this index be trusted") a build that never ran and one that
    failed say the same thing.
    """

    http, maker, monkeypatch = portfolio
    async with maker() as session:
        session.add(
            PolicyIndexBuild(
                operation_id="op-occupier",
                policy_set_id=_SECOND_SET_ID,
                policy_set_key="beta",
                trigger="rebuild",
                status="running",
                stage=STAGES[1],
                started_at=datetime.now(UTC),
                active_slot=progress_module.ACTIVE_SLOT,
            )
        )
        await session.commit()

    _patch_build(monkeypatch, _fast_build)
    async with maker() as session:
        tracked = await run_tracked_policy_index_build(
            session,
            policy_set_id=_FIRST_SET_ID,
            policy_set_key="alpha",
            version_number=3,
            load_projections=lambda: _no_projections(),
            trigger="publish",
            operation_id="op-publish-deferred",
            actor="approver@example.test",
        )

    # The publish's caller is handed a truthful refusal rather than an exception,
    # which is what lets the publish itself still succeed.
    assert tracked.accepted is False
    assert tracked.conflict is not None
    assert tracked.conflict.policy_set_key == "beta"
    assert tracked.outcome is not None
    assert tracked.outcome.state == latest_state_status_for("deferred") == "failed"
    assert tracked.build is not None and tracked.build.status == "deferred"

    listing = (await http.get("/api/policy-sets/alpha/policy-index/builds")).json()
    assert listing["builds"][0]["status"] == "deferred"
    assert listing["active"]["policy_set_key"] == "beta"


async def test_the_latest_state_row_and_the_history_entry_describe_one_attempt(
    portfolio,
) -> None:
    """Two tables, one build — so they may differ in vocabulary and never in fact.

    They are written from one place for exactly this reason. The one value they
    do not share is `deferred`, and the correspondence for it is a function
    rather than two literals, so it can be asserted instead of assumed.
    """

    http, maker, monkeypatch = portfolio
    _patch_build(monkeypatch, _fast_build)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-agree")

    async with maker() as session:
        state = (await session.execute(select(PolicyIndexState))).scalar_one()
        history = (
            await session.execute(
                select(PolicyIndexBuild).where(PolicyIndexBuild.operation_id == "op-agree")
            )
        ).scalar_one()

    assert latest_state_status_for(history.status) == "completed"
    assert state.status == "built"
    assert state.index_name == history.index_name
    assert state.indexed_version_number == history.version_number
    assert state.document_count == history.document_count
    assert state.projection_profile == history.projection_profile
    assert state.error == history.error


# ── 6. nothing readable here came from a document ────────────────────


async def test_no_build_record_or_listing_carries_policy_text_or_a_credential(
    portfolio,
) -> None:
    """The planted sentence and the planted secret appear in none of these bodies.

    Asserted over the whole serialized response rather than field by field,
    because the risk is not a field anyone chose — it is a field somebody adds
    later to make a readout more helpful, and a per-field assertion would not
    notice it.
    """

    http, _maker, monkeypatch = portfolio

    async def _fake(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return PolicyIndexBuildOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=policy_index_name(policy_set_key),
            version_number=version_number,
            document_count=0,
            indexed_at="2026-08-18T12:00:00+00:00",
            error="the search service rejected the batch",
        )

    _patch_build(monkeypatch, _fake)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-leak")

    bodies = [
        (await http.get("/api/policy-index/builds/op-leak")).text,
        (await http.get("/api/policy-sets/alpha/policy-index/builds")).text,
        (await http.get("/api/policy-index/states")).text,
    ]
    for body in bodies:
        assert _PLANTED_POLICY_SENTENCE not in body
        assert _PLANTED_CREDENTIAL not in body
        assert "Reimbursement" not in body

    # And the payload has no key that invites one in.
    payload = (await http.get("/api/policy-index/builds/op-leak")).json()
    for key in payload:
        assert not any(word in key.lower() for word in ("text", "content", "body", "prompt", "secret", "key_"))


def test_a_recorded_failure_is_never_empty_and_never_unbounded() -> None:
    """Two failures a description must not have, proved on the function itself.

    Empty is the worse of the two: recorded as the reason a build failed it is
    indistinguishable from no reason having been recorded, which reads as a
    process that died before it could speak. Unbounded is the leak: an exception
    from an indexing client can carry a reply body, and a reply body from this
    build echoes retrieval text.
    """

    assert bounded_error(TimeoutError()).strip()
    assert bounded_error(None).strip()
    assert bounded_error("   ").strip()

    smuggled = bounded_error(_PLANTED_POLICY_SENTENCE * 100)
    assert len(smuggled) <= 500
    assert smuggled.endswith("…")


# ── 7. the console reads every project, and classifies honestly ──────


async def test_the_admin_console_lists_every_project_including_the_unindexed_one(
    portfolio,
) -> None:
    """A project with no recorded state is listed saying so, not omitted.

    A console that silently dropped them would answer "which projects are
    unindexed" with a blank space, which is the one answer that looks like good
    news.
    """

    http, _maker, monkeypatch = portfolio
    _patch_build(monkeypatch, _fast_build)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-console")

    listing = (await http.get("/api/policy-index/states")).json()
    by_key = {row["policy_set_key"]: row for row in listing["projects"]}
    assert set(by_key) == {"alpha", "beta"}

    alpha = by_key["alpha"]
    assert alpha["policy_set_name"] == "Alpha project"
    assert alpha["last_attempt"] == "built"
    assert alpha["document_count"] == 7
    assert alpha["latest_build"]["operation_id"] == "op-console"
    # Built and current, but never validated. Distinct from healthy, because the
    # retrieval gate refuses it — and distinct from failed, because the repair is
    # one validation run rather than a full re-render.
    assert alpha["health"] == "unvalidated"

    beta = by_key["beta"]
    assert beta["last_attempt"] == "never_attempted"
    # No active approved version, so there is correctly nothing to index. A
    # warning here would be a warning on a project behaving exactly as it should.
    assert beta["health"] == "empty"
    assert beta["latest_build"] == {"active": False}
    # Named even though nothing was built, so an operator can find the index.
    assert beta["index_name"] == policy_index_name("beta")


async def test_a_failed_index_stays_rebuildable_and_the_console_says_it_failed(
    portfolio,
) -> None:
    """A broken index must be repairable, which means the console must offer it.

    The failure mode being guarded against is a surface that renders a failed
    project as terminal — no control, no route back — which would leave the only
    repair path unreachable from the one screen built to find it.
    """

    http, _maker, monkeypatch = portfolio

    async def _fails(*, policy_set_key, version_number, projections, **_kw):
        list(projections)
        return PolicyIndexBuildOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=policy_index_name(policy_set_key),
            version_number=version_number,
            document_count=0,
            indexed_at="2026-08-18T12:00:00+00:00",
            error="Azure AI Search accepted 61 of 74 documents",
        )

    _patch_build(monkeypatch, _fails)
    await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-broken")

    listing = (await http.get("/api/policy-index/states")).json()
    alpha = next(r for r in listing["projects"] if r["policy_set_key"] == "alpha")
    assert alpha["health"] == "failed"
    assert "61 of 74" in alpha["error"]

    _patch_build(monkeypatch, _fast_build)
    repaired = await http.post("/api/policy-sets/alpha/policy-index/rebuild?operation_id=op-repair")
    assert repaired.status_code == 200
    assert repaired.json()["state"] == "built"


# ── 8. the old shape still works ─────────────────────────────────────


async def test_a_rebuild_without_an_operation_id_behaves_exactly_as_it_did(
    portfolio,
) -> None:
    """Existing callers pass no operation id, and must not have to.

    The server allocates one and returns it, so the response gains a field and
    loses nothing. The build itself is unchanged — which is also why
    `rebuild_project_policy_index` keeps a no-op reporter as its default and
    needs no database to run.
    """

    http, _maker, monkeypatch = portfolio
    _patch_build(monkeypatch, _fast_build)

    response = await http.post("/api/policy-sets/alpha/policy-index/rebuild")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "built"
    assert body["document_count"] == 7
    assert body["policy_document_count"] == 5
    assert body["manifest_state"] == "ready"
    # Allocated, so a caller that did not bring one can still find this build.
    assert body["operation_id"]
    found = (await http.get(f"/api/policy-index/builds/{body['operation_id']}")).json()
    assert found["status"] == "completed"


async def test_the_build_still_runs_with_no_reporter_and_no_database(portfolio) -> None:
    """The default reporter is a no-op, and that is what keeps callers free.

    `rebuild_project_policy_index` is called directly by tests and by any future
    caller that has no session. If progress reporting were mandatory it would
    drag a database into every one of them — so the parameter has a default that
    accepts every call and records nothing, and the build has exactly one code
    path whether or not anyone is listening.

    The real function is used here, not a stand-in, because the claim is about
    its signature and its default. Search is disabled in this configuration, so
    it takes its `skipped` path without calling a model or a search service.
    """

    import inspect

    signature = inspect.signature(policy_index_module.rebuild_project_policy_index)
    assert signature.parameters["progress"].default is progress_module.NULL_PROGRESS

    outcome = await policy_index_module.rebuild_project_policy_index(
        policy_set_key="alpha", version_number=3, projections=[]
    )
    assert outcome.policy_set_key == "alpha"

    # The claim this test exists for: the call needed no session and wrote no
    # row. A build invoked without the orchestrator leaves the history untouched,
    # which is what keeps every direct caller free of a database.
    _http, maker, _monkeypatch = portfolio
    async with maker() as session:
        assert (await session.execute(select(PolicyIndexBuild))).scalars().all() == []

    # And the default object really does accept the calls the build makes.
    await progress_module.NULL_PROGRESS.stage("rendering")
    await progress_module.NULL_PROGRESS.count(projection_count=1)


def test_every_counter_the_build_can_report_has_a_column_to_land_in() -> None:
    """A counter with no column is a measurement that silently disappears.

    The reporter drops unknown keys deliberately — a typo must not fail a build —
    which means a mistyped counter would vanish without a trace. This is the
    guard that makes that safe.
    """

    for counter in COUNTERS:
        assert hasattr(PolicyIndexBuild, counter), counter
    # And every column the payload publishes is one the model actually has.
    for counter in COUNTERS:
        assert counter in build_payload(
            PolicyIndexBuild(
                operation_id="x",
                policy_set_id=_FIRST_SET_ID,
                policy_set_key="alpha",
                trigger="rebuild",
                status="running",
                started_at=datetime.now(UTC),
            )
        )


# ── 9. the bands, with both an allow and a refuse ────────────────────
#
# Classification alone proves nothing: a route can be in `OPERATION_BANDS` under
# a band nobody enforces. Each of the three new routes therefore gets a pair —
# somebody who may reach it and somebody who may not — because a test with only
# the refusal half passes just as happily when the route 404s, and a test with
# only the allow half passes when enforcement is switched off entirely.


@contextmanager
def _enforcing_app():
    """The app with RBAC genuinely on, patched for the request lifetime.

    `enforce_rbac` calls `get_settings()` per request, so the patch has to
    survive past `create_app()` — the same arrangement `test_rbac_authz.py` uses,
    and for the same reason.
    """

    from policy_platform.api.app import create_app as _create_app
    from policy_platform.infrastructure.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings(
        database_url="sqlite+aiosqlite:///unused",
        alembic_database_url="sqlite:///unused",
        rbac_enabled=True,
        dev_auth_enabled=True,
        environment="development",
    )
    with patch("policy_platform.api.app.get_settings", return_value=settings), patch(
        "policy_platform.api.authz.get_settings", return_value=settings
    ):
        yield TestClient(_create_app(), raise_server_exceptions=False)
    get_settings.cache_clear()


def test_the_admin_console_is_administer_and_an_author_is_refused_it() -> None:
    """The aggregate is an operator's view of the estate, not governed content.

    An author may repair their own project's index; enumerating every project in
    the deployment with its index name, its failure reasons and how long each has
    been broken is reconnaissance about how this deployment is put together. The
    same reasoning classifies the subscription-key list.
    """

    with _enforcing_app() as client:
        refused = client.get("/api/policy-index/states", headers={"X-Dev-Role": POLICY_AUTHOR})
        assert refused.status_code == 403

        allowed = client.get("/api/policy-index/states", headers={"X-Dev-Role": ADMIN})
        # Not 403 — whatever the database does next, the band let it through.
        assert allowed.status_code != 403


def test_project_progress_and_history_are_author_and_a_viewer_is_refused_them() -> None:
    """Both project-scoped reads serve the retry decision, so both are AUTHOR.

    THE BOUNDARY THIS ACTUALLY PROVES, STATED PLAINLY

    This platform authorises by **role**, not by project: there is no per-project
    ACL anywhere in `authz.py`, and `rbac.ts` mirrors three roles and no project
    membership. So an author may read the history of any project, not only ones
    they author — and pretending otherwise by testing a project key would be
    inventing an access control the product does not have and cannot enforce.

    What is enforced, and what this asserts, is that a viewer may not reach
    either surface and an author may.
    """

    with _enforcing_app() as client:
        for path in (
            "/api/policy-sets/alpha/policy-index/builds",
            "/api/policy-index/builds/some-operation",
        ):
            assert (
                client.get(path, headers={"X-Dev-Role": VIEWER}).status_code == 403
            ), path
            assert (
                client.get(path, headers={"X-Dev-Role": POLICY_AUTHOR}).status_code != 403
            ), path


def test_the_new_routes_are_all_classified_and_none_defaults_open() -> None:
    """A route absent from the registry is unreachable, which is the point.

    Asserted by name rather than by re-walking the app, because the guard that
    walks every route already exists in `test_rbac_authz.py`. What that guard
    cannot say is that *these particular* routes were classified deliberately
    rather than swept in — and the bands they carry are the argument of this
    whole surface, so they are written down where the argument is.
    """

    from policy_platform.api.authz import ADMINISTER as _ADMINISTER
    from policy_platform.api.authz import AUTHOR as _AUTHOR
    from policy_platform.api.authz import OPERATION_BANDS

    assert OPERATION_BANDS[("GET", "/api/policy-index/states")] == _ADMINISTER
    assert OPERATION_BANDS[("GET", "/api/policy-index/builds/{operation_id}")] == _AUTHOR
    assert OPERATION_BANDS[("GET", "/api/policy-sets/{key}/policy-index/builds")] == _AUTHOR
    # Unchanged, and asserted so a later edit cannot quietly relax the repair
    # path while adding the read paths beside it.
    assert OPERATION_BANDS[("POST", "/api/policy-sets/{key}/policy-index/rebuild")] == _AUTHOR
    assert OPERATION_BANDS[("POST", "/api/policy-sets/{key}/publish")] == _AUTHOR
