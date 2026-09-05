"""The retrieval-only external contract.

This is the light companion to ``case_decision_v2``. It returns the exact
published policy records selected for a scenario and stops before intent
classification, adjudication, prose generation, or receipt persistence.
"""
from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from policy_platform.contracts.case_decision import (
    LanguageRef,
    PolicySetRef,
    RetrievalRef,
    RuleRetrievalRef,
    RuleSelectionRef,
    SizeRef,
    TokenUsageRef,
    VersionRef,
)

SCHEMA_VERSION: Final[str] = "policy_retrieval_v1"

#: Rule mode answers under its own schema version, and that is the whole of the
#: compatibility story for it.
#:
#: `rule_retrieval=true` searches rule documents and returns rule records. A
#: rule is not a policy and must never be projected as one, so this envelope
#: does not reuse `policies` for them: a client written against
#: `policy_retrieval_v1` that received rules under that name would either parse
#: a rule as a policy or, worse, read an empty `policies` list and report "no
#: policy bears on this question" when rules were in fact returned. Both are
#: silent, and the second is indistinguishable from a real negative answer.
#:
#: Changing the version is what makes the difference loud. A strict client
#: pinned to `policy_retrieval_v1` fails closed on an unknown version instead of
#: succeeding with the wrong shape.
SCHEMA_VERSION_RULE: Final[str] = "rule_retrieval_v1"


class RuleSourceRef(BaseModel):
    """Where a rule came from — identifiers only, never the policy's content.

    A rule has to be citable, and a citation that named only a rule id would be
    unresolvable by a reader holding the corpus. So the provision that contains
    the rule is named: its key, its id, and its heading path.

    That is the whole of what crosses over, and the limit is the point. These
    are **identifiers for citation**, not the provision's terms. No policy body,
    no rules of the parent other than this one, no spans or facts belonging to
    the provision at large. A caller that wants the provision can ask for it by
    key, in policy mode, which is the mode that returns provisions.
    """

    model_config = ConfigDict(extra="forbid")

    provision_key: str | None = None
    provision_id: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    document_id: str | None = None
    document_version: str | None = None


class RuleMatchRef(BaseModel):
    """Why this rule is in the returned set.

    The rule ranking's own quantities. There is no `PolicyMatchRef` here and no
    parent score: in rule mode a rule is ranked as a rule, and reporting a
    parent's score beside it would re-import the unit of delivery this mode
    exists to get away from.
    """

    model_config = ConfigDict(extra="forbid")

    best_rank: int | None = None
    best_score: float | None = None
    score_kind: str | None = Field(
        default=None,
        description="Which quantity `best_score` is, on the same terms as a decision receipt.",
    )
    semantic_score: float | None = Field(
        default=None,
        description="The reranker score for this rule, comparable to the retrieval block's cutoff.",
    )
    admitted_as: str = Field(
        default="matched",
        description=(
            "`matched` when the rule placed in the ranking on its own evidence, or `neighbour` "
            "when it was admitted because a matched rule depends on it — a condition, exception "
            "or override without which the matched rule cannot be read correctly."
        ),
    )
    required_by_rule_id: str | None = Field(
        default=None,
        description="Set on a `neighbour`: the matched rule that pulled it in.",
    )


class RetrievedRuleRecord(BaseModel):
    """One rule, as a rule.

    `rule` is the rule's own published record. It is not a policy payload and
    does not contain one.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    source: RuleSourceRef
    match: RuleMatchRef
    rule: dict[str, Any] = Field(
        description=(
            "The rule's own record: its terms and the spans and facts it itself references. "
            "Never the parent provision's payload, and never another rule's."
        )
    )


class PolicyRetrievalQueryRef(BaseModel):
    """The caller's scenario; the processed form is in ``language``."""

    scenario: str
    scenario_hash: str


class RetrievedPolicyIdentity(BaseModel):
    """The stable identity of one selected published policy."""

    provision_id: str | None = None
    provision_key: str
    heading_path: list[str] = Field(default_factory=list)


class PolicyMatchRef(BaseModel):
    """Why this policy is in the returned set and which rules were retained."""

    best_rank: int | None = None
    best_score: float | None = None
    rule_selection: RuleSelectionRef | None = None


class RetrievedPolicyRecord(BaseModel):
    """One exact policy record that the decision path would have read."""

    policy: RetrievedPolicyIdentity
    match: PolicyMatchRef
    payload: dict[str, Any] = Field(
        description=(
            "The selected grounding_projection_v1 record. Large policies contain only the rules "
            "named by match.rule_selection; source evidence remains verbatim."
        )
    )


class _RetrievalEnvelopeBase(BaseModel):
    """Everything both modes report, and nothing either one of them does not.

    The two modes are separate wire models rather than one model with two
    optional arrays. That is a correction of a real defect: a single envelope
    serialising `rules: []` alongside policies — or `policies: []` alongside
    rules — hands a client written for the other mode an *empty list* rather
    than an error. "0 policies retrieved" is indistinguishable from a genuine
    negative answer, so the misreport is silent, which is the worst available
    failure and the one this contract exists to prevent.

    Absent, not empty. A client that reaches for the field its mode does not
    have gets nothing to misread.

    `extra="forbid"` for the same reason: Pydantic's default would *silently
    ignore* an attempt to set the other mode's field, so a cross-conversion bug
    would construct successfully and simply drop the data. Forbidding it turns
    that into an error at the point it is made.
    """

    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    policy_set: PolicySetRef
    active_version: VersionRef | None = None
    query: PolicyRetrievalQueryRef
    retrieval: RetrievalRef
    size: SizeRef
    language: LanguageRef
    token_usage: TokenUsageRef
    latency_ms: int
    stage_latency_ms: dict[str, int] | None = Field(
        default=None,
        description=(
            "Observed wall-clock stage timings in milliseconds for this retrieval. Additive and "
            "diagnostic only: a client that has never read it is unaffected, and no field beside "
            "it changes meaning. A stage that did not run is absent rather than zero, so this "
            "route reports fewer keys than a decision does — it runs no embedding call, no rule "
            "query, no classifier and no gather. Counters are never reported here; every value is "
            "a duration."
        ),
    )


class PolicyRetrievalEnvelope(_RetrievalEnvelopeBase):
    """Policy mode. Filtered policy JSON with no decision-shaped fields.

    Has `policies` and **has no `rules` property at all**.
    """

    schema_version: Literal["policy_retrieval_v1"] = SCHEMA_VERSION
    policies: list[RetrievedPolicyRecord] = Field(default_factory=list)


class RuleRetrievalEnvelope(_RetrievalEnvelopeBase):
    """Rule mode. Rule records, as rules.

    Has `rules` and **has no `policies` property at all**. A caller that asked
    for rules is given rules; a caller written for policy mode fails on the
    unknown `schema_version` rather than reading an empty `policies` list and
    reporting that nothing bears on the question.
    """

    schema_version: Literal["rule_retrieval_v1"] = SCHEMA_VERSION_RULE
    retrieval: RuleRetrievalRef
    rules: list[RetrievedRuleRecord] = Field(default_factory=list)


#: The route's response type. Discriminated on the runtime schema tag, so the
#: shape is chosen by the mode that ran and neither shape can carry the other's
#: field.
RetrievalEnvelope = Annotated[
    PolicyRetrievalEnvelope | RuleRetrievalEnvelope,
    Field(discriminator="schema_version"),
]
