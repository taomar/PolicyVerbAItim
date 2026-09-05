"""Every project's policy index in one place, and one build's progress by id.

WHY THESE ARE NOT ON `/api/policy-sets/{key}/...`

Both routes here are about the *set* of indexes rather than about one project.

`GET /api/policy-index/states` answers a question no per-project endpoint can:
which projects in this deployment have an index that cannot be matched against
right now. Asked one project at a time it is a request per project on every load
of an operator's console, and the answer arrives as a list the client has to
assemble — so a project that failed to load looks identical to one that is
healthy. Asked once, it is one query and every project is either in the list or
demonstrably missing from it.

`GET /api/policy-index/builds/{operation_id}` is keyed on an operation, not a
project. That is the point: the client generates the id *before* the long POST,
exactly as an upload does, because it cannot learn a server-side id until the
response arrives — which is after the work it wanted to watch has ended. A poll
that had to name a project would also have to know which project, which is
precisely what a page that has just navigated back does not.

WHAT THE TWO BANDS ARE, AND WHY THEY DIFFER

The aggregate is ADMINISTER. It enumerates every project in the deployment
together with its index name, its failure reasons and its build history — which
is a description of the whole estate's health, and knowing which projects are
broken and for how long is operator knowledge rather than governed content. The
usual "a read is a read, so READ" does not reach it, the same way it does not
reach the subscription-key list.

The single-operation progress read is AUTHOR: it reports the stages of a build
that only an author could have started, on a project named in the payload, and it
is the companion of the rebuild the same person is authorised to run.

NO POLICY TEXT, ON EITHER ROUTE

Counts, stage keys, timestamps, index names, profile names and bounded failure
descriptions. Never a rendered text, a source text, a prompt or a service reply.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_platform.domain.models import PolicyIndexState, PolicySet
from policy_platform.infrastructure.assistants.ai_case_language import (
    ENGLISH_PROJECTION_PROFILE,
)
from policy_platform.infrastructure.persistence.db import get_session
from policy_platform.infrastructure.projection.published_case_payload import (
    active_version_for_policy_set,
)
from policy_platform.infrastructure.search.policy_index import (
    policy_index_freshness,
    policy_index_name,
)
from policy_platform.infrastructure.search.policy_index_build_progress import (
    build_payload,
    build_by_operation,
    builds_for_policy_set,
    running_build,
)

router = APIRouter(prefix="/api/policy-index", tags=["policy-index"])


#: The health words this console classifies into, and every one of them is a
#: state some project can actually be in. They are deliberately not collapsed:
#:
#:   healthy       built for the active version, under the current rendering
#:                 contract, and its faithfulness check passed
#:   unvalidated   built and current, but never checked — the retrieval gate
#:                 refuses it, and the repair is one validation run, not a
#:                 rebuild, so calling it `failed` would send an operator to do
#:                 a full re-render for nothing
#:   stale         built, but for a superseded version or under a superseded
#:                 rendering contract; a query rendered under the current one is
#:                 not comparable with the text it would be scored against
#:   failed        the last attempt did not finish
#:   building      a build is running for this project right now
#:   not_built     nothing has ever been attempted
#:   empty         there is no active approved version, so there is correctly
#:                 nothing to index; reporting this as `not_built` would put a
#:                 warning on a project that is behaving exactly as it should
_HEALTHY = "healthy"
_UNVALIDATED = "unvalidated"
_STALE = "stale"
_FAILED = "failed"
_BUILDING = "building"
_NOT_BUILT = "not_built"
_EMPTY = "empty"


def _health(
    state: PolicyIndexState | None,
    *,
    freshness: str,
    last_attempt: str,
    building: bool,
) -> str:
    """One project's index health, derived only from what the record can prove.

    Ordered from the most immediate fact to the least. A build running now is the
    first thing an operator needs, because every other reading is about to be
    replaced; an active version's absence comes next, because without one there
    is nothing an index could be behind; and a failure outranks staleness because
    a failed attempt is the reason a stale index stayed stale.
    """

    if building:
        return _BUILDING
    if freshness == "nothing_to_index":
        return _EMPTY
    if last_attempt == "never_attempted":
        return _NOT_BUILT
    if last_attempt == "failed":
        return _FAILED
    if freshness in ("stale", "unknown"):
        return _STALE
    # Current and last attempt succeeded. The remaining question is whether the
    # corpus was ever checked against the record it was built from — which the
    # retrieval gate asks and refuses on, so a console that reported this as
    # healthy would be contradicted by every query the project answers.
    if state is None or state.quality_state != "passed":
        return _UNVALIDATED
    return _HEALTHY


@router.get("/states")
async def list_policy_index_states_endpoint(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Every project's recorded index state, its health, and its latest build.

    Reads PostgreSQL only, and probes Azure Search for nothing. That is the same
    boundary `GET /api/policy-sets/{key}/policy-index` draws and for the same
    reason: this has to load when Search is down, because Search being down is
    one of the conditions somebody opens it in. It reports what the app recorded,
    and live retrieval performs its own separate guard when a query actually runs.

    Projects with no recorded state are listed too, saying so. A console that
    silently omitted them would answer "which projects are unindexed" with a
    blank space, which is the one answer that looks like good news.
    """

    projects = (
        (await session.execute(select(PolicySet).order_by(PolicySet.name, PolicySet.key)))
        .scalars()
        .all()
    )
    states = {
        state.policy_set_id: state
        for state in (await session.execute(select(PolicyIndexState))).scalars().all()
    }
    active = await running_build(session)
    active_payload = build_payload(active)

    rows: list[dict] = []
    for project in projects:
        state = states.get(project.id)
        version = await active_version_for_policy_set(session, project.id)
        active_version_number = version.version_number if version else None
        freshness = policy_index_freshness(
            state,
            active_version_number,
            expected_projection_profile=ENGLISH_PROJECTION_PROFILE,
        )
        history = await builds_for_policy_set(session, policy_set_id=project.id, limit=1)
        building = bool(active) and active.policy_set_id == project.id
        rows.append(
            {
                "policy_set_key": project.key,
                "policy_set_name": project.name,
                "index_name": state.index_name if state else policy_index_name(project.key),
                "health": _health(
                    state,
                    freshness=freshness.freshness,
                    last_attempt=freshness.last_attempt,
                    building=building,
                ),
                "last_attempt": freshness.last_attempt,
                "freshness": freshness.freshness,
                "active_version_number": active_version_number,
                "indexed_version_number": state.indexed_version_number if state else None,
                "attempted_version_number": state.attempted_version_number if state else None,
                "document_count": state.document_count if state else 0,
                "built_at": state.built_at.isoformat() if state and state.built_at else None,
                "attempted_at": (
                    state.attempted_at.isoformat() if state and state.attempted_at else None
                ),
                # Already bounded where it was written. Passed through rather
                # than re-rendered so this row and the project's own endpoint
                # cannot come to say two different things about one failure.
                "error": state.error if state else None,
                "projection_profile": state.projection_profile if state else None,
                "expected_projection_profile": ENGLISH_PROJECTION_PROFILE,
                "quality_state": state.quality_state if state else None,
                "quality_profile": state.quality_profile if state else None,
                "quality_checked_documents": (
                    state.quality_checked_documents if state else None
                ),
                "quality_structural_findings": (
                    state.quality_structural_findings if state else None
                ),
                "quality_min_similarity": state.quality_min_similarity if state else None,
                "quality_mean_similarity": state.quality_mean_similarity if state else None,
                "quality_validated_at": (
                    state.quality_validated_at.isoformat()
                    if state and state.quality_validated_at
                    else None
                ),
                # The most recent attempt, which is what says *when* and *why* a
                # project reached the state above. `policy_index_states` cannot:
                # it holds one row that every attempt overwrites.
                "latest_build": build_payload(history[0]) if history else {"active": False},
            }
        )

    return {
        "projects": rows,
        # The one build slot, deployment-wide. Every rebuild control in the
        # console is disabled while this is present, including the ones for
        # projects it does not belong to.
        "active": active_payload,
    }


@router.get("/builds/{operation_id}")
async def policy_index_build_progress_endpoint(
    operation_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Stages, counters and outcome for one build, by the id its caller polls on.

    Returns `{"active": false}` when nothing is recorded for this id — a poll
    that beat the handler, or an operation that was never made. Both are normal
    states rather than errors, and the panel falls back to its elapsed clock;
    a 404 would make a page that navigated back before the build started render
    an error where there is none.

    Because the record is a row rather than a process-local dict, this answers
    correctly after the page has been closed and reopened, after the build has
    finished, and from a replica other than the one that ran it.
    """

    build = await build_by_operation(session, operation_id)
    return build_payload(build)
