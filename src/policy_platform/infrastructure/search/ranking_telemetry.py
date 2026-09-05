"""Which component ranked a retrieval result, and which projection it was read from.

WHY THIS FILE EXISTS

A retrieval that comes back in the wrong order is the hardest kind of failure to
argue about, because the evidence is gone by the time anyone asks. The service
returns one number per hit and that number means four different things depending
on what was asked for:

  * a text query alone → the number is the lexical (BM25) score;
  * a vector query alone → the number is the vector similarity;
  * both → the number is the *fused* score, and the two scores that went into
    it are **not returned at all**; and
  * a semantic configuration → a second number appears beside it, and the
    order of the results is that second number's order, not the first's.

So "the score" is not a fact on its own. Without recording which of those four
it was, a stored score cannot be compared against another stored score, and a
report that ranking changed cannot be told from a report that the *question*
changed. This module records the distinction, once, at the only place that knows
it.

WHERE IT IS CALLED FROM, AND WHY ONLY THERE

`AzureSearchClient.vector_search` composes the request and receives the answer,
so it is the single point that knows which components were asked for and holds
the untouched scores. Every retrieval in the platform goes through it. Callers
above it legitimately rewrite these numbers — the decision path copies the
semantic score over the base score before it selects — so a caller is the one
place the distinction has already been lost. Instrumenting there would record
the rewrite as though it were the service's answer, and would have to be
repeated in each caller to boot. One boundary, one policy.

WHAT IT MAY NOT DO

Observation may not change what was retrieved, in what order, or what a failure
means to the caller. Nothing here is written back, and `record_ranking` is total:
it builds and emits inside one guard, because building the record reads the
response, and a fault while reading it would escape a function whose entire
purpose is to watch without consequence.

WHAT IT MAY NOT SAY

No query text, no document text, no document identifier, no filter value, no
index name, no endpoint and no credential. What is emitted is: which components
ranked, how many hits each ranked, the scores those hits carried, how far the
returned order departs from the base order, and two hashes standing in for
identity. A relevance score is a property of the match, not of the record — it
names nothing and quotes nothing — which is why scores are the one measurement
that may be reported in full.

THE TWO HASHES, AND WHY THERE ARE TWO

`index_projection_hash` answers "was this read under the same retrieval contract
as last time". It is deliberately *corpus-independent*: two unrelated projects
querying the same shape hash alike, so a change to the hash means the contract
changed and nothing else. Exactly these structural inputs enter it, in this
order:

  1. the selected field names, in the order the query asked for them — order is
     part of the contract, not incidental;
  2. the vector field name, or nothing when no vector was supplied;
  3. the semantic configuration name, or nothing when none was requested; and
  4. the field names the filter constrains, sorted — *names only, never values*.

`retrieval_scope_hash` answers the different question "was this the same scope".
Exactly two inputs enter it: the index name and the filter expression as sent.
Both are live identifiers, which is why they enter a digest and never a log
line. Two runs against one scope agree; two scopes differ; and neither can be
read back out.

Deliberately absent from both: the query text, the requested depth, and anything
the response carried. A hash that moved with the question would identify the
question, which is the one thing this file must never do.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from policy_platform.contracts.canonical import canonical_hash

logger = logging.getLogger(__name__)

#: Stable prefix so an operator can select these lines out of a log stream, and
#: a JSON body for the same reason the finalisation record uses one: a Python
#: dict interpolated into a format string is readable by a person and by nothing
#: else.
RANKING_EVENT: str = "search.ranking_components"

#: The response keys the service uses for the two numbers. Named here rather
#: than spelled at each use so that a service-side rename is one edit.
BASE_SCORE_KEY: str = "@search.score"
SEMANTIC_SCORE_KEY: str = "@search.rerankerScore"

#: The wildcard a match-all query is written as. A query that is only this asked
#: no lexical question, and reporting it as a lexical ranking would invent a
#: component that never ran.
MATCH_ALL: str = "*"

# ── the component vocabulary ─────────────────────────────────────────

COMPONENT_LEXICAL: str = "lexical"
COMPONENT_VECTOR: str = "vector"
COMPONENT_FUSION: str = "fusion"
COMPONENT_SEMANTIC: str = "semantic"

#: Every component this boundary can observe, in the order they are reported.
#: A component that is not in this tuple does not reach the record.
RANKING_COMPONENTS: tuple[str, ...] = (
    COMPONENT_LEXICAL,
    COMPONENT_VECTOR,
    COMPONENT_FUSION,
    COMPONENT_SEMANTIC,
)

#: The ranking that produced the base score. Three of the four are named after
#: the component that produced them; the fourth is the honest name for a request
#: that asked no ranked question at all and was narrowed by its filter alone.
MODE_FILTER_ONLY: str = "filter_only"

# ── why a component is absent, said explicitly ───────────────────────
#
# A component that did not rank anything is reported as absent *with a reason*
# rather than as a zero, a null or a missing key. Zero is a score a component can
# genuinely produce, and a missing key is indistinguishable from a record that
# was never written — both of which read, later, as though the component had run
# and found nothing. These five reasons are the complete set, and each says
# something different about where to look next.

#: The request never asked for it.
ABSENT_NOT_REQUESTED: str = "not_requested"
#: It ran, and its score was consumed by the fusion rather than returned. This
#: is a property of the service's response shape, not a fault.
ABSENT_FUSED: str = "fused"
#: Fusion cannot have happened, because only one ranked component was asked for.
#: Distinct from "not requested": a ranking *did* happen, it just was not a
#: fused one, which points at the request rather than at the corpus.
ABSENT_SINGLE_COMPONENT: str = "single_component"
#: It carries the returned number, and there were no hits for it to rank. Only
#: the component that actually carries that number can be absent for this
#: reason; the others are absent structurally, whatever came back.
ABSENT_NO_RESULTS: str = "no_results"
#: It was asked for, hits came back, and none of them carried its score. This is
#: the reason worth an alert: a semantic configuration that silently stopped
#: applying looks exactly like a corpus that got worse.
ABSENT_NOT_RETURNED: str = "not_returned"

# ── what happened to the request ─────────────────────────────────────

#: The service answered and the answer was ranked.
OUTCOME_RANKED: str = "ranked"
#: The service answered with an error status. There is a status code to report.
OUTCOME_REFUSED: str = "refused"
#: There was no answer — a timeout or a transport fault. There is a fault type
#: to report, and deliberately not a fault *message*: a transport message can
#: carry the endpoint it failed to reach.
OUTCOME_FAULTED: str = "faulted"

#: How many scores of one component are reported individually. The head of the
#: list is where the shape of a ranking lives — the gap between the first and
#: second hit decides a selection far more often than the tail does — and an
#: unbounded list would put a log line's size at the mercy of a caller's depth.
#: Counts and extremes below cover the whole set regardless.
OBSERVED_SCORE_DEPTH: int = 10

# ── reading field names out of a filter, and never a value ───────────
#
# Two shapes cover what this platform composes: `<field> <operator> <value>` and
# `search.<function>(<field>, …)`. Both capture the *left* side only. A quoted
# value cannot be captured by either: the first requires whitespace immediately
# after the name, which a closing quote is not, and both refuse a name preceded
# by a quote character.
#
# An expression written in some other shape simply contributes no name — the
# structural hash then says less than it could, which is a smaller loss than the
# one this restraint prevents. What neither pattern can do, by construction, is
# capture a value.

_FILTER_FIELD = re.compile(r"(?<!['\"\w])([A-Za-z_][A-Za-z0-9_]*)\s+(?:eq|ne|gt|ge|lt|le)\s")
_FILTER_FUNCTION_FIELD = re.compile(
    r"(?<!['\"\w])search\.[A-Za-z_]+\(\s*([A-Za-z_][A-Za-z0-9_]*)"
)


@dataclass(frozen=True)
class ComponentObservation:
    """One component's contribution to a ranking, or its documented absence."""

    component: str
    observed: bool
    absent_reason: str | None = None
    ranked: int = 0
    best_score: float | None = None
    worst_score: float | None = None
    scores: tuple[float, ...] = ()


@dataclass(frozen=True)
class ProjectionIdentity:
    """What was read, as two digests and two counts — never as a name.

    The counts are reported beside the hashes because a hash alone cannot be
    read. "The contract hash changed and the selected-field count went from nine
    to eight" is a diagnosis; a changed hash on its own is only a question. Both
    counts are magnitudes of the *schema*, so neither says anything about a
    corpus.
    """

    index_projection_hash: str
    retrieval_scope_hash: str
    projection_fields: int
    filter_fields: int


@dataclass(frozen=True)
class RankingObservation:
    """One retrieval, as the record an operator can act on."""

    outcome: str
    mode: str
    semantic_requested: bool
    requested_top: int
    results: int
    projection: ProjectionIdentity
    components: tuple[ComponentObservation, ...]
    semantic_reorder: int | None = None
    status_code: int | None = None
    fault: str | None = None

    def as_event(self) -> dict:
        """The emitted body. Its keys are the contract, pinned below."""

        return {
            "outcome": self.outcome,
            "mode": self.mode,
            "semantic_requested": self.semantic_requested,
            "requested_top": self.requested_top,
            "results": self.results,
            "semantic_reorder": self.semantic_reorder,
            "status_code": self.status_code,
            "fault": self.fault,
            "index_projection_hash": self.projection.index_projection_hash,
            "retrieval_scope_hash": self.projection.retrieval_scope_hash,
            "projection_fields": self.projection.projection_fields,
            "filter_fields": self.projection.filter_fields,
            "components": {
                observation.component: {
                    "observed": observation.observed,
                    "absent_reason": observation.absent_reason,
                    "ranked": observation.ranked,
                    "best_score": observation.best_score,
                    "worst_score": observation.worst_score,
                    "scores": list(observation.scores),
                }
                for observation in self.components
            },
        }


#: The event's attributes, named so that adding or dropping one is a visible
#: change to a contract rather than an edit inside a function. Anything reading
#: these lines — a query, a dashboard, a test — is entitled to assume this set.
RANKING_EVENT_ATTRIBUTES: tuple[str, ...] = (
    "outcome",
    "mode",
    "semantic_requested",
    "requested_top",
    "results",
    "semantic_reorder",
    "status_code",
    "fault",
    "index_projection_hash",
    "retrieval_scope_hash",
    "projection_fields",
    "filter_fields",
    "components",
)

#: The same, for each component's block.
COMPONENT_ATTRIBUTES: tuple[str, ...] = (
    "observed",
    "absent_reason",
    "ranked",
    "best_score",
    "worst_score",
    "scores",
)


def filter_field_names(filter_expr: str | None) -> tuple[str, ...]:
    """The sorted field names a filter constrains. Never a value it compares to."""

    if not filter_expr:
        return ()
    found = set(_FILTER_FIELD.findall(f"{filter_expr} "))
    found.update(_FILTER_FUNCTION_FIELD.findall(filter_expr))
    return tuple(sorted(found))


def select_field_names(select: str | None) -> tuple[str, ...]:
    """The selected fields, in the order the query asked for them."""

    if not select:
        return ()
    return tuple(part.strip() for part in select.split(",") if part.strip())


def projection_identity(
    *,
    index: str,
    select: str | None,
    filter_expr: str | None,
    vector_field: str | None,
    semantic_configuration: str | None,
) -> ProjectionIdentity:
    """Identify the projection that was read, without naming it.

    Canonical by construction: both digests are taken over sorted-key JSON of a
    fixed structure, so the same inputs give the same digest on any machine, in
    any process, in any order the caller happened to build them.
    """

    selected = select_field_names(select)
    constrained = filter_field_names(filter_expr)
    return ProjectionIdentity(
        index_projection_hash=canonical_hash(
            {
                "select": list(selected),
                "vector_field": vector_field,
                "semantic_configuration": semantic_configuration,
                "filter_fields": list(constrained),
            }
        ),
        retrieval_scope_hash=canonical_hash({"index": index, "filter": filter_expr}),
        projection_fields=len(selected),
        filter_fields=len(constrained),
    )


def ranking_mode(*, query_text: str | None, vector_present: bool) -> str:
    """Which ranking produced the base score."""

    asked = (query_text or "").strip()
    lexical = bool(asked) and asked != MATCH_ALL
    if lexical and vector_present:
        return COMPONENT_FUSION
    if lexical:
        return COMPONENT_LEXICAL
    if vector_present:
        return COMPONENT_VECTOR
    return MODE_FILTER_ONLY


def observe_ranking(
    *,
    query_text: str | None,
    vector_present: bool,
    semantic_configuration: str | None,
    requested_top: int,
    hits: Sequence[object] | None,
    projection: ProjectionIdentity,
    outcome: str = OUTCOME_RANKED,
    status_code: int | None = None,
    fault: str | None = None,
) -> RankingObservation:
    """Read one retrieval's components off the request and the response.

    Pure, and total over anything the response could plausibly be: a run that
    produced no answer passes `hits=None`, which is reported as no results
    rather than as an empty ranking, because those are different facts.
    """

    mode = ranking_mode(query_text=query_text, vector_present=vector_present)
    semantic_requested = bool(semantic_configuration)
    rows = [hit for hit in (hits or []) if isinstance(hit, Mapping)]

    base = [_score(hit.get(BASE_SCORE_KEY)) for hit in rows]
    semantic = [_score(hit.get(SEMANTIC_SCORE_KEY)) for hit in rows]

    components = (
        _rank_component(
            COMPONENT_LEXICAL,
            requested=mode in (COMPONENT_LEXICAL, COMPONENT_FUSION),
            carries_base=mode == COMPONENT_LEXICAL,
            structural_reason=ABSENT_FUSED,
            rows=rows,
            scores=base,
        ),
        _rank_component(
            COMPONENT_VECTOR,
            requested=mode in (COMPONENT_VECTOR, COMPONENT_FUSION),
            carries_base=mode == COMPONENT_VECTOR,
            structural_reason=ABSENT_FUSED,
            rows=rows,
            scores=base,
        ),
        _rank_component(
            COMPONENT_FUSION,
            requested=mode != MODE_FILTER_ONLY,
            carries_base=mode == COMPONENT_FUSION,
            structural_reason=ABSENT_SINGLE_COMPONENT,
            rows=rows,
            scores=base,
        ),
        _semantic_component(requested=semantic_requested, rows=rows, scores=semantic),
    )

    return RankingObservation(
        outcome=outcome,
        mode=mode,
        semantic_requested=semantic_requested,
        requested_top=requested_top,
        results=len(rows),
        projection=projection,
        components=components,
        semantic_reorder=_semantic_reorder(base, semantic),
        status_code=status_code,
        fault=fault,
    )


def record_ranking(
    *,
    index: str,
    select: str | None,
    filter_expr: str | None,
    vector_field: str | None,
    semantic_configuration: str | None,
    query_text: str | None,
    requested_top: int,
    hits: Sequence[object] | None = None,
    outcome: str = OUTCOME_RANKED,
    status_code: int | None = None,
    fault: str | None = None,
) -> None:
    """Build and emit one record, and never let either fail a retrieval.

    The whole body is inside the guard, not just the emit. Building the record
    reads a response this module did not produce, and a fault while reading one
    would escape a function whose entire purpose is to observe without
    consequence — turning a retrieval that succeeded into a request that failed
    because it was measured.
    """

    try:
        observation = observe_ranking(
            query_text=query_text,
            vector_present=vector_field is not None,
            semantic_configuration=semantic_configuration,
            requested_top=requested_top,
            hits=hits,
            projection=projection_identity(
                index=index,
                select=select,
                filter_expr=filter_expr,
                vector_field=vector_field,
                semantic_configuration=semantic_configuration,
            ),
            outcome=outcome,
            status_code=status_code,
            fault=fault,
        )
        logger.info("%s %s", RANKING_EVENT, json.dumps(observation.as_event(), sort_keys=True))
    except Exception:  # noqa: BLE001 - measuring a retrieval never decides its fate
        # Reported rather than swallowed, so telemetry that stopped working is
        # itself visible. Guarded in turn because a logging handler that raises
        # would otherwise re-raise here and undo the containment above — which
        # has to hold even when the thing that failed is the log.
        try:
            logger.warning("%s could not be emitted", RANKING_EVENT)
        except Exception:  # noqa: BLE001 - nothing further can be said
            pass


# ── internals ────────────────────────────────────────────────────────


def _score(value: object) -> float | None:
    """A score, or nothing.

    `bool` is excluded explicitly: it is a subclass of `int` in Python, and a
    flag read as a relevance score would be reported as a ranking of 1.0.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _rank_component(
    component: str,
    *,
    requested: bool,
    carries_base: bool,
    structural_reason: str,
    rows: Sequence[object],
    scores: Sequence[float | None],
) -> ComponentObservation:
    """One of the three base-score components, observed or explained.

    The order of these three questions is the substance of the rule. A
    structural absence is checked *before* an empty result, because it holds
    whatever came back: a component whose score the fusion consumed would not
    have reported one had there been a thousand hits, and calling that "no
    results" would suggest a score was within reach if only the corpus had
    answered. Only the component that actually carries the returned number can
    be absent for want of hits.
    """

    if not requested:
        return ComponentObservation(
            component=component, observed=False, absent_reason=ABSENT_NOT_REQUESTED
        )
    if not carries_base:
        return ComponentObservation(
            component=component, observed=False, absent_reason=structural_reason
        )
    if not rows:
        return ComponentObservation(
            component=component, observed=False, absent_reason=ABSENT_NO_RESULTS
        )
    return _observed(component, scores)


def _semantic_component(
    *, requested: bool, rows: Sequence[object], scores: Sequence[float | None]
) -> ComponentObservation:
    """The reranker, which is the one component that can be asked for and not arrive."""

    if not requested:
        return ComponentObservation(
            component=COMPONENT_SEMANTIC, observed=False, absent_reason=ABSENT_NOT_REQUESTED
        )
    if not rows:
        return ComponentObservation(
            component=COMPONENT_SEMANTIC, observed=False, absent_reason=ABSENT_NO_RESULTS
        )
    return _observed(COMPONENT_SEMANTIC, scores)


def _observed(component: str, scores: Sequence[float | None]) -> ComponentObservation:
    """Whatever the component actually scored, or the fact that it scored nothing."""

    present = [score for score in scores if score is not None]
    if not present:
        return ComponentObservation(
            component=component, observed=False, absent_reason=ABSENT_NOT_RETURNED
        )
    return ComponentObservation(
        component=component,
        observed=True,
        ranked=len(present),
        best_score=max(present),
        worst_score=min(present),
        scores=tuple(present[:OBSERVED_SCORE_DEPTH]),
    )


def _semantic_reorder(
    base: Sequence[float | None], semantic: Sequence[float | None]
) -> int | None:
    """How many positions the returned order departs from the base score's order.

    The returned order is the reranker's. Sorting the same hits by their base
    score gives the order they would have been returned in without one, so the
    count of positions where the two disagree is how much work the reranker did
    — zero meaning it agreed with the ranking it was given, which is worth
    knowing and is invisible in the scores alone.

    `None` when the question cannot be asked: fewer than two hits carry both
    numbers, so there is no order to disagree about. Absent rather than zero,
    because zero would claim agreement that was never tested.
    """

    positions = [
        index
        for index, (first, second) in enumerate(zip(base, semantic))
        if first is not None and second is not None
    ]
    if len(positions) < 2:
        return None
    # Stable by construction: ties keep the order the service returned them in,
    # so an equal-scored pair is never reported as a reordering.
    by_base = sorted(range(len(positions)), key=lambda seat: -base[positions[seat]])
    return sum(1 for seat, source in enumerate(by_base) if seat != source)
