"""One mechanism for watching, recording and coordinating policy-index builds.

WHY THIS MODULE EXISTS

Two surfaces needed the same three things and were about to grow two of each.

An administrator needed to see every project's index in one place and repair a
broken one. A publisher needed to see the best-effort build that runs after their
own publish, and to retry it when it failed. Those are different audiences, but
the thing they are watching is a single operation with a single vocabulary of
stages, a single set of counts, and — the part neither surface could have known
on its own — a single global constraint, because a build renders and embeds a
whole corpus through rate-limited model endpoints and then rewrites an entire
search index. Two of those at once compete for the same quota, and two on one
project race each other's manifest writes, which is the one state the build's own
ordering argument cannot recover from.

So there is one registry, one stage list, one lifecycle, and one slot. Publish and
manual rebuild both go through it; a third caller would too.

THE SHAPE IS `upload_progress`, THE STORAGE IS NOT

`infrastructure/ingestion/upload_progress.py` draws exactly this boundary for an
upload: the handler publishes what it is doing, the API reads it back, and neither
learns about the other. This module keeps that shape — the same "truthful, or
absent" rule, the same client-generated operation id, the same guarantee that a
record ends in a terminal state on every exit — and changes one thing.

Upload progress lives in a dict, and says so: its own docstring records that a
poll served by a different worker sees nothing, and accepts it, because losing an
upload's progress has no correctness consequence. That reasoning does not carry
over. Here the record is *also* the history a publisher reads afterwards, and it
is *also* the slot that stops a second build starting — and neither of those may
be lost with a process, nor be invisible to the replica next door. So the rows
live in PostgreSQL, in `policy_index_builds`.

TRUTHFUL, OR ABSENT

Every number published here is one the build actually measured. There is
deliberately no percentage: the stages before rendering have no denominator at
all — the document count is unknown until the corpus has been rendered — so any
bar spanning them would be interpolated from elapsed time, which is a guess
wearing the clothes of a measurement, and it is the number somebody would use to
decide whether to wait.

What replaces it is a fixed, ordered pipeline, so "step 4 of 8" is exactly true
even while a stage has no count of its own, plus the one honest denominator the
build does eventually have: how many documents it expects to write, published
beside how many were acknowledged. A counter that has not been measured is NULL
and renders as "—", never as 0: "not counted yet" and "none found" are different
facts about a project and must not look identical.

NO POLICY TEXT, ON ANY PATH

Stage keys, counts, timestamps, an actor and a bounded failure description. Never
a rendered text, a source text, a service reply body, a prompt or a credential.
These rows are served to the browser and copied into logs.

INVARIANT: reporting must never change a build's outcome. Every reporting call
here swallows its own failure, because a progress bug that could fail a build
would be worse than the blindness it set out to fix.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from policy_platform.domain.models import PolicyIndexBuild
from policy_platform.infrastructure.errors import describe_exception

__all__ = [
    "ACTIVE_SLOT",
    "BUILD_TRIGGERS",
    "COUNTERS",
    "LEASE_SECONDS",
    "PROGRESS_RETENTION_SECONDS",
    "STAGES",
    "BuildProgress",
    "NULL_PROGRESS",
    "NullBuildProgress",
    "RecordedBuildProgress",
    "acquire_build_slot",
    "bounded_error",
    "build_by_operation",
    "build_payload",
    "builds_for_policy_set",
    "finish_build",
    "latest_state_status_for",
    "new_operation_id",
    "reclaim_abandoned_builds",
    "record_deferred_build",
    "running_build",
]

#: The single value `policy_index_builds.active_slot` may hold while a build is
#: running. Any string would do; what matters is that there is exactly one of
#: them, so the table's UNIQUE constraint admits exactly one running row.
ACTIVE_SLOT: Final[str] = "global"

#: What can start a build. Both do identical work through one code path; this is
#: the only thing that tells them apart in the history afterwards.
BUILD_TRIGGERS: Final[tuple[str, ...]] = ("publish", "rebuild")

#: The pipeline, as stable keys, in the order `rebuild_project_policy_index`
#: performs them. The reader turns these into labels, so wording can change
#: without breaking a client, and "step N of M" is computed from this tuple
#: rather than hard-coded in two places.
#:
#: Each name is a stage the build genuinely has — they were read off the
#: function's own structure, not invented to make a nicer-looking bar:
#:
#:   collecting  the project's published projections are gathered
#:   rendering   each policy's retrieval text, and each indexable rule's, is
#:               rendered into the language the pipeline matches in
#:   embedding   the renderings are embedded
#:   indexing    the index is created if absent and the manifest is moved out of
#:               `ready`, which is the point of no return
#:   uploading   documents are written and acknowledgements counted
#:   sweeping    documents this build did not recognise are removed
#:   validating  the corpus is checked against the record it was built from
#:   publishing  the manifest is moved to `ready`
STAGES: Final[tuple[str, ...]] = (
    "collecting",
    "rendering",
    "embedding",
    "indexing",
    "uploading",
    "sweeping",
    "validating",
    "publishing",
)

#: The counters a build may publish. Named here so `RecordedBuildProgress` can
#: refuse an unknown one rather than silently dropping a typo — a counter that
#: never appears is indistinguishable from a stage that never measured it.
COUNTERS: Final[tuple[str, ...]] = (
    "projection_count",
    "policy_unit_count",
    "rule_unit_count",
    "rendered_count",
    "embedded_count",
    "expected_document_count",
    "submitted_count",
    "acknowledged_count",
    "swept_count",
)

#: How long a `running` row may go without a write before another build may take
#: the slot from it.
#:
#: This is the answer to the one question a database-held lease has that a
#: process-local flag does not: what happens when the process holding it dies. A
#: row left saying `running` forever would leave the slot held by nobody and
#: every later build refused — the guard stuck closed, which is a worse failure
#: than the concurrency it prevents, because nothing recovers from it.
#:
#: Deliberately far longer than any build. The row is written at every stage
#: boundary, so a live build heartbeats; the longest stage is a single rendering
#: and embedding pass over a whole corpus, which on a large project is minutes
#: rather than hours. A threshold in the minutes would reclaim the slot from
#: builds that are working, which is exactly the race this exists to prevent.
LEASE_SECONDS: Final[int] = 2 * 60 * 60

#: How long after finishing a build is still reported as "recent" by the progress
#: reader, so a panel shows the terminal state rather than the record appearing
#: to vanish mid-animation.
#:
#: This bounds a *display*, not the record: the row is history and is kept. It is
#: the difference between "this build just finished" and "there was a build here
#: last Tuesday", which a panel that reopened days later would otherwise present
#: as news.
PROGRESS_RETENTION_SECONDS: Final[int] = 30 * 60

#: A failure description is cut to this before it is written. `describe_exception`
#: produces a sentence, but an exception raised by a client library can carry a
#: reply body, and a reply body from an indexing call echoes the request — which
#: for this build is retrieval text. The ceiling is a second line of defence
#: behind not passing bodies in at all.
_MAX_ERROR_CHARS: Final[int] = 500

_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"completed", "failed", "deferred"})


def new_operation_id() -> str:
    """A server-side operation id, for a caller that did not bring one.

    The client generates its own where it can, because it cannot learn a
    server-side id until the response arrives — which is after the work it wanted
    to watch has ended. This is for the callers that have no client: a scripted
    rebuild, and every existing caller that predates progress reporting.
    """

    return uuid.uuid4().hex


def bounded_error(exc: BaseException | str | None) -> str:
    """A failure description that is never empty and never long.

    `describe_exception` supplies the "never empty" half — an httpx timeout's
    `str()` is empty, and an empty error column reads as "no reason was recorded",
    which is a different diagnosis pointing at a different repair. This adds the
    ceiling, and it is not tidiness: an exception from an indexing client can
    carry a reply body, and a reply body from this build echoes retrieval text.
    """

    text = exc if isinstance(exc, str) else describe_exception(exc)
    text = text.strip()
    if not text:
        return describe_exception(None)
    if len(text) <= _MAX_ERROR_CHARS:
        return text
    return text[: _MAX_ERROR_CHARS - 1].rstrip() + "…"


def latest_state_status_for(history_status: str) -> str:
    """The `policy_index_states.status` that corresponds to a history status.

    The two vocabularies differ by exactly one value and the difference is
    deliberate. This table can say `deferred` — the build never ran because
    another held the slot — because a history exists to explain a pattern, and
    "never ran" and "ran and failed" point at different repairs.

    `policy_index_states` cannot, and is not widened to. What that row reports is
    whether this project's index can be trusted right now, and on that question a
    build that never ran and one that failed say the same thing. Adding a third
    value would make every existing reader of that column learn one that changes
    nothing for it.

    Stated here as a function rather than left implicit at two call sites, so the
    correspondence is one thing a test can assert on.
    """

    return "failed" if history_status == "deferred" else history_status


# ── the reporter ─────────────────────────────────────────────────────


class BuildProgress(Protocol):
    """What a running build may say about itself.

    Deliberately two methods and no return values. A build must not be able to
    branch on reporting — there is no "did that get through" for it to check, and
    nothing here raises — so instrumentation cannot become control flow.
    """

    async def stage(self, name: str) -> None:
        """Move to a named stage. An unknown name is ignored."""

    async def count(self, **counts: int | None) -> None:
        """Set known counters. Unknown keys are ignored.

        Assignment rather than accumulation: each of these is a total the build
        has just measured, so setting one twice with the same value is harmless
        and a retry cannot double a count.
        """


class NullBuildProgress:
    """Reports nothing, to nobody.

    The default for `rebuild_project_policy_index`, which is what keeps every
    existing caller — and every test that calls the build directly — working
    unchanged and free of a database. A no-op object rather than `None` so the
    build has one code path instead of an `if reporter is not None` at each of
    eight stage boundaries, each of which would be a place to forget one.
    """

    async def stage(self, name: str) -> None:  # noqa: D102 - see the protocol
        return None

    async def count(self, **counts: int | None) -> None:  # noqa: D102 - see the protocol
        return None


NULL_PROGRESS: Final[NullBuildProgress] = NullBuildProgress()


@dataclass
class RecordedBuildProgress:
    """Writes a running build's stage and counters onto its own row.

    WHY IT COMMITS

    The row is the slot as well as the report. A stage write that sat in an open
    transaction would be invisible to the replica deciding whether to refuse the
    next build, and would leave that decision resting on a lease whose last
    heartbeat nobody else can see. It is also what a poll from another process
    reads. So each write commits, and the cost is one small UPDATE per stage
    boundary — eight or so for a build that renders an entire corpus.

    WHY IT SWALLOWS EVERYTHING

    A build must not fail because its progress could not be recorded. Every write
    here is wrapped, and a failure rolls back and returns: the build carries on
    and the panel keeps its last reading, which is exactly the behaviour before
    any of this existed.
    """

    session: AsyncSession
    build_id: uuid.UUID

    async def stage(self, name: str) -> None:
        if name not in STAGES:
            return
        await self._write(stage=name)

    async def count(self, **counts: int | None) -> None:
        known = {key: value for key, value in counts.items() if key in COUNTERS}
        if not known:
            return
        await self._write(**known)

    async def _write(self, **changes: object) -> None:
        try:
            build = await self.session.get(PolicyIndexBuild, self.build_id)
            if build is None or build.status != "running":
                # A build whose row has already reached a terminal status is not
                # one this reporter may reopen. That happens when the slot was
                # reclaimed underneath a very slow build; letting a late stage
                # write move it back to `running` would resurrect a lease the
                # database has already given to somebody else.
                return
            for key, value in changes.items():
                setattr(build, key, value)
            await self.session.commit()
        except SQLAlchemyError:
            # Reporting is not the build. Roll the failed write back so the
            # session is usable for the work that matters, and say nothing.
            try:
                await self.session.rollback()
            except SQLAlchemyError:
                return


# ── the slot, and the history rows ───────────────────────────────────


async def reclaim_abandoned_builds(
    session: AsyncSession, *, now: datetime | None = None
) -> list[PolicyIndexBuild]:
    """Release the slot from any running row that has stopped heartbeating.

    The recovery half of a database-held lease, and the reason it can be held
    across processes at all. A replica that is killed mid-build leaves its row
    saying `running` with the slot in it; without this, every later build in the
    entire deployment is refused by a holder that no longer exists — the guard
    stuck closed, which nothing recovers from and which is a worse failure than
    the concurrent builds it was preventing.

    The reclaimed row is marked `failed` and says so, rather than being deleted.
    A build that was interrupted did happen, and its history entry is how anyone
    finds out that a replica died in the middle of one.
    """

    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(seconds=LEASE_SECONDS)
    result = await session.execute(
        select(PolicyIndexBuild).where(PolicyIndexBuild.active_slot.is_not(None))
    )
    reclaimed: list[PolicyIndexBuild] = []
    for build in result.scalars().all():
        heartbeat = _aware(build.updated_at) or _aware(build.started_at)
        if heartbeat is not None and heartbeat > cutoff:
            continue
        build.status = "failed"
        build.error = bounded_error(
            "this build stopped reporting for longer than the build lease allows, so the "
            "build slot was released for another build to use; the process running it "
            "most likely ended before it could finish"
        )
        build.finished_at = moment
        build.active_slot = None
        reclaimed.append(build)
    if reclaimed:
        await session.commit()
    return reclaimed


async def acquire_build_slot(
    session: AsyncSession,
    *,
    operation_id: str,
    policy_set_id: object,
    policy_set_key: str,
    trigger: str,
    actor: str | None = None,
    started_at: datetime | None = None,
) -> PolicyIndexBuild | None:
    """Claim the one build slot, or return None because somebody else holds it.

    THE REFUSAL IS THE DATABASE'S, NOT THIS FUNCTION'S

    Nothing here reads the table and then decides. It inserts a row holding
    `ACTIVE_SLOT` and lets the UNIQUE constraint answer, because a read-then-write
    has a window between the two halves and two replicas can both pass the read.
    The constraint has no window: exactly one INSERT succeeds, whichever process,
    worker or replica issued it, and the losers get an `IntegrityError`.

    A caller that is handed `None` has not started anything and holds nothing.

    WHY IT COMMITS BEFORE RETURNING

    An uncommitted slot is not a slot. It is invisible to every other connection,
    so a second build elsewhere would insert its own row happily and both would
    run. Committing here is safe at both call sites: publish has already
    committed its version, and a manual rebuild has nothing pending — which is
    stated rather than assumed, because it is the precondition for this line.
    """

    moment = started_at or datetime.now(UTC)
    # Take the slot back from a build whose process died before asking for it.
    # Ordered this way round deliberately: reclaiming after a refusal would mean
    # the first caller to arrive after a crash is always refused once for no
    # reason, and would teach the UI to retry on a 409 that was not real.
    await reclaim_abandoned_builds(session, now=moment)

    build = PolicyIndexBuild(
        operation_id=operation_id,
        policy_set_id=policy_set_id,
        policy_set_key=policy_set_key,
        trigger=trigger if trigger in BUILD_TRIGGERS else "rebuild",
        actor=actor,
        status="running",
        stage=STAGES[0],
        started_at=moment,
        active_slot=ACTIVE_SLOT,
    )
    session.add(build)
    try:
        await session.flush()
    except IntegrityError:
        # Either the slot is held, or this operation id has already been used.
        # Both mean "this request did not start a build", and both are answered
        # the same way: the caller asks what *is* running and reports that.
        await session.rollback()
        return None
    await session.commit()
    return build


async def record_deferred_build(
    session: AsyncSession,
    *,
    operation_id: str,
    policy_set_id: object,
    policy_set_key: str,
    trigger: str,
    actor: str | None = None,
    error: str,
    started_at: datetime | None = None,
) -> PolicyIndexBuild | None:
    """Write the history entry for a build that never ran, holding no slot.

    A publish's index build is best-effort and the publish is already committed
    by the time it runs, so a busy slot must not fail the request. What it must
    not do either is vanish: a publisher whose index was never rebuilt and who is
    told nothing has a project whose grounding corpus is silently behind, and no
    reason to look.

    So the attempt is recorded with `deferred` — never ran, as distinct from ran
    and failed — and `active_slot` stays NULL, because this row is a note about
    something that did not happen and must not be able to block anything.
    """

    moment = started_at or datetime.now(UTC)
    build = PolicyIndexBuild(
        operation_id=operation_id,
        policy_set_id=policy_set_id,
        policy_set_key=policy_set_key,
        trigger=trigger if trigger in BUILD_TRIGGERS else "rebuild",
        actor=actor,
        status="deferred",
        stage=None,
        started_at=moment,
        finished_at=moment,
        error=bounded_error(error),
        active_slot=None,
    )
    session.add(build)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return None
    await session.commit()
    return build


async def finish_build(
    session: AsyncSession,
    build_id: uuid.UUID,
    *,
    status: str,
    error: str | None = None,
    finished_at: datetime | None = None,
    **outcome: object,
) -> PolicyIndexBuild | None:
    """Write a build's terminal status and release the slot, in one statement.

    The two are done together and cannot be done apart. A build that ended
    without releasing would hold the slot until the lease expired, refusing every
    build in the deployment for two hours over a success; a slot released without
    a terminal status would leave a row saying `running` that nothing will ever
    finish, and the progress reader would report a build in flight forever.

    `status` is coerced to a terminal one. There is no path through this function
    that leaves a row running, because "we finished, but the status write took the
    non-terminal branch" is precisely the defect the whole surface exists to
    remove.
    """

    terminal = status if status in _TERMINAL_STATUSES else "failed"
    try:
        build = await session.get(PolicyIndexBuild, build_id)
        if build is None:
            return None
        build.status = terminal
        if error is not None:
            build.error = bounded_error(error)
        elif terminal == "failed" and not (build.error or "").strip():
            # The same invariant `record_policy_index_build_state` enforces: a
            # row that says `failed` always says why. An empty reason is worse
            # than a vague one — it is indistinguishable from no reason having
            # been recorded, which reads as a process that died before it could
            # speak, and sends the reader looking for a crash that never happened.
            build.error = bounded_error(
                "the build failed and raised an exception that carried no message; "
                "see the server log for the traceback"
            )
        for key, value in outcome.items():
            if hasattr(build, key):
                setattr(build, key, value)
        build.finished_at = finished_at or datetime.now(UTC)
        build.active_slot = None
        await session.commit()
        return build
    except SQLAlchemyError:
        await session.rollback()
        return None


# ── reading ──────────────────────────────────────────────────────────


async def running_build(session: AsyncSession) -> PolicyIndexBuild | None:
    """The build currently holding the slot, anywhere in the deployment, or None.

    Read from the slot column rather than from `status`, because the slot is what
    the next build will actually contend for. A row that somehow said `running`
    without holding the slot would not refuse anybody, and reporting it as the
    active build would tell a UI to disable a button that in fact works.
    """

    result = await session.execute(
        select(PolicyIndexBuild).where(PolicyIndexBuild.active_slot.is_not(None))
    )
    return result.scalars().first()


async def build_by_operation(
    session: AsyncSession, operation_id: str
) -> PolicyIndexBuild | None:
    """One build by the id its caller polls on."""

    if not operation_id:
        return None
    result = await session.execute(
        select(PolicyIndexBuild).where(PolicyIndexBuild.operation_id == operation_id)
    )
    return result.scalars().first()


async def builds_for_policy_set(
    session: AsyncSession, *, policy_set_id: object, limit: int = 20
) -> Sequence[PolicyIndexBuild]:
    """One project's build attempts, newest first.

    Bounded by default because a history is read to answer "what has been
    happening lately", and a project that has been publishing for a year would
    otherwise send its whole life down the wire to answer it.
    """

    result = await session.execute(
        select(PolicyIndexBuild)
        .where(PolicyIndexBuild.policy_set_id == policy_set_id)
        .order_by(PolicyIndexBuild.started_at.desc(), PolicyIndexBuild.created_at.desc())
        .limit(max(1, limit))
    )
    return list(result.scalars().all())


def build_payload(build: PolicyIndexBuild | None, *, now: datetime | None = None) -> dict:
    """One build as an API payload: stages, counts, outcome, and nothing else.

    `active: false` for an absent record — a poll that arrived before the handler
    started, or for an operation that was never made. Both are normal states, not
    errors, and the panel falls back to its elapsed clock.

    There is no percentage field, and there is no place to put one. `stage_index`
    and `stage_total` say where the build is in a fixed pipeline, which is exactly
    true; `expected_document_count` beside `acknowledged_count` is the one real
    denominator the build ever has, and it is absent until rendering has finished
    because until then nobody knows it.
    """

    if build is None:
        return {"active": False}

    moment = now or datetime.now(UTC)
    started = _aware(build.started_at)
    finished = _aware(build.finished_at)
    updated = _aware(build.updated_at) or started
    terminal = build.status in _TERMINAL_STATUSES
    since_end = (moment - finished).total_seconds() if finished else None
    return {
        "active": True,
        "operation_id": build.operation_id,
        "policy_set_key": build.policy_set_key,
        "trigger": build.trigger,
        "actor": build.actor,
        "status": build.status,
        "stage": build.stage,
        "stages": list(STAGES),
        # 1-based, so the client renders "step 4 of 8" without knowing the
        # tuple's indexing. A stage the reader does not recognise — and a
        # deferred build, which has none — yields 0, which reads as "not one of
        # the known steps" rather than silently pointing at the first one.
        "stage_index": (STAGES.index(build.stage) + 1) if build.stage in STAGES else 0,
        "stage_total": len(STAGES),
        "projection_count": build.projection_count,
        "policy_unit_count": build.policy_unit_count,
        "rule_unit_count": build.rule_unit_count,
        "rendered_count": build.rendered_count,
        "embedded_count": build.embedded_count,
        "expected_document_count": build.expected_document_count,
        "submitted_count": build.submitted_count,
        "acknowledged_count": build.acknowledged_count,
        "swept_count": build.swept_count,
        "index_name": build.index_name,
        "version_number": build.version_number,
        "document_count": build.document_count,
        "policy_document_count": build.policy_document_count,
        "rule_document_count": build.rule_document_count,
        "projection_profile": build.projection_profile,
        "manifest_state": build.manifest_state,
        "quality_state": build.quality_state,
        "quality_profile": build.quality_profile,
        "quality_checked_documents": build.quality_checked_documents,
        "quality_structural_findings": build.quality_structural_findings,
        "quality_min_similarity": build.quality_min_similarity,
        "quality_mean_similarity": build.quality_mean_similarity,
        "error": build.error,
        "started_at": started.isoformat() if started else None,
        "finished_at": finished.isoformat() if finished else None,
        "elapsed_seconds": round(((finished or moment) - started).total_seconds(), 1)
        if started
        else None,
        # Seconds since the build last wrote anything, computed entirely from
        # server-stamped values so no client clock enters it. A browser a few
        # minutes ahead of the server would otherwise mark a healthy build quiet
        # on its first poll, and one running behind would never report a stalled
        # build — both wrong for a reason that has nothing to do with the build.
        "seconds_since_update": round((moment - updated).total_seconds(), 1)
        if updated
        else None,
        "terminal": terminal,
        # Whether a finished build is recent enough to still be presented as
        # news. The row is kept forever — it is history — so this bounds the
        # display and nothing else.
        "recent": (since_end is None) or (since_end <= PROGRESS_RETENTION_SECONDS),
        # Whether this build is the one holding the slot right now. The UI
        # disables rebuild on it, and it is read from the slot rather than
        # inferred from the status for the same reason `running_build` is.
        "holds_build_slot": build.active_slot is not None,
    }


def _aware(value: datetime | None) -> datetime | None:
    """A timestamp that can be compared, whatever dialect returned it.

    PostgreSQL hands back an aware datetime for a `timestamptz`; SQLite, which
    the tests run on, hands back a naive one for the same column. Subtracting one
    from the other raises, and it raises inside a progress reader — so the
    normalisation is here, once, rather than at each of the several places that
    do arithmetic on these fields.
    """

    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
