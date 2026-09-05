"""Compact external projection of a full stored case-decision receipt."""
from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from policy_platform.contracts.case_decision import (
    CitationSourceRef,
    HASH_BASIS_RULE_V1,
    InformationOutcome,
    MissingInformationItem,
    NOT_EVALUATED,
    NOT_REQUESTED,
    PolicySetRef,
    RuleCitationSourceRef,
    TokenUsageRef,
    VerificationRequirementItem,
    VerdictOutcome,
    VersionRef,
)

SCHEMA_VERSION: Final[str] = "case_decision_light_v1"
ResponseType = Literal["informational", "decision", "mixed", "not_evaluated"]


class LightRequestRef(BaseModel):
    scenario: str
    scenario_hash: str
    rule_retrieval: bool = Field(
        default=False,
        description=(
            "Which retrieval mode the caller asked for. Echoed here because the light response "
            "is the whole of what an A/B caller sees: without it the two arms of a comparison "
            "are indistinguishable in the body, and the mode would have to be taken on trust "
            "from the request that is no longer in hand. `false` is what a request that omits "
            "the field records, and what every receipt written before the field existed "
            "projects as."
        ),
    )


class LightAskedRef(BaseModel):
    information_requested: bool
    verdict_requested: bool
    classifier_version: str | None = None


class LightOutcomeRef(BaseModel):
    information: InformationOutcome
    verdict: VerdictOutcome


class LightInformationRef(BaseModel):
    status: str
    answer: str = ""
    explanation: str | None = None
    note: str = ""


class LightVerdictRef(BaseModel):
    status: str
    reached: bool
    decision: str = ""
    explanation: str = ""
    missing_information: list[MissingInformationItem] = Field(default_factory=list)
    verification_requirements: list[VerificationRequirementItem] = Field(default_factory=list)
    note: str = ""


class LightPolicyRef(BaseModel):
    provision_id: str | None = None
    provision_key: str | None = None
    heading_path: list[str] = Field(default_factory=list)


class LightCitationRef(BaseModel):
    rule_id: str
    policy: LightPolicyRef | None = None
    source: CitationSourceRef
    serves: list[Literal["information", "verdict"]] = Field(default_factory=list)


class LightRetrievalRef(BaseModel):
    status: str
    method: str | None = None
    retrieval_mode: str | None = Field(
        default=None,
        description=(
            "Which mode actually ran: `policy` or `rule`. Reported beside the requested mode in "
            "`request.rule_retrieval` because those are two different claims — what was asked "
            "for and what was served. They agree today, since a rule-retrieval request is "
            "refused rather than downgraded, and a reader can only confirm that if both are "
            "visible. Null on a receipt written before the modes were named, which is a "
            "policy-mode retrieval either way."
        ),
    )
    policies_retained: int | None = None
    rule_rescued_policies: int | None = None
    reason: str | None = None


class LightTraceRef(BaseModel):
    classifier_version: str | None = None
    prompt_version: str | None = None
    plan_profile: str | None = None
    selector_catalogue_version: str | None = None
    model_deployment: str | None = None
    stage_latency_ms: dict[str, int] | None = None
    token_usage: TokenUsageRef | None = None


class CaseDecisionLightEnvelope(BaseModel):
    """Essential decision output; the full receipt remains available by URL."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["case_decision_light_v1"] = SCHEMA_VERSION
    response_type: ResponseType
    decision_id: str
    correlation_id: str
    idempotency_key: str | None = None
    policy_set: PolicySetRef
    active_version: VersionRef | None = None
    request: LightRequestRef
    asked: LightAskedRef
    outcome: LightOutcomeRef
    information: LightInformationRef | None = None
    verdict: LightVerdictRef | None = None
    retrieval: LightRetrievalRef
    policies: list[LightPolicyRef] = Field(default_factory=list)
    citations: list[LightCitationRef] = Field(default_factory=list)
    trace: LightTraceRef
    decision_hash: str
    hash_basis: str
    receipt_url: str
    latency_ms: int

    @model_validator(mode="after")
    def _policy_light_receipt_is_policy_mode(self) -> "CaseDecisionLightEnvelope":
        if self.request.rule_retrieval or self.retrieval.retrieval_mode == "rule":
            raise ValueError(
                "case_decision_light_v1 cannot carry rule-mode request or retrieval values"
            )
        return self


#: Rule mode's light projection answers under its own version too, for the same
#: fail-closed reason as the full receipt: a reader pinned to
#: `case_decision_light_v1` must not parse a rule answer and find `policies`
#: empty.
SCHEMA_VERSION_RULE: Final[str] = "case_decision_rule_light_v1"


class LightRuleRef(BaseModel):
    """One rule a light rule-mode answer rested on. Identifiers only."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    provision_key: str | None = None
    provision_id: str | None = None
    heading_path: list[str] = Field(default_factory=list)


class LightRuleCitationRef(BaseModel):
    """A light citation that traces to a rule, never to a policy."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule: LightRuleRef | None = None
    source: RuleCitationSourceRef
    serves: list[Literal["information", "verdict"]] = Field(default_factory=list)


class LightRuleRequestRef(LightRequestRef):
    """A compact rule request, closed to policy-mode values."""

    model_config = ConfigDict(extra="forbid")

    rule_retrieval: Literal[True] = True


class LightRuleInformationRef(LightInformationRef):
    model_config = ConfigDict(extra="forbid")


class LightRuleVerdictRef(LightVerdictRef):
    model_config = ConfigDict(extra="forbid")


class LightRuleRetrievalRef(BaseModel):
    """A compact rule retrieval, closed to policy-mode values."""

    model_config = ConfigDict(extra="forbid")

    status: str
    method: str | None = None
    retrieval_mode: Literal["rule"] = "rule"
    rules_selected: int | None = None
    rules_grounded: int | None = None
    rules_omitted: list[dict] = Field(default_factory=list)
    rule_grounding_bytes: int | None = None
    rule_grounding_budget_bytes: int | None = None
    rule_grounding_proxy_tokens: int | None = None
    rule_grounding_proxy_token_budget: int | None = None
    reason: str | None = None


class CaseDecisionRuleLightEnvelope(BaseModel):
    """The compact projection of a rule receipt.

    Carries `rules` and has **no `policies` property at all**, so the same
    absent-not-empty guarantee the retrieval envelopes give holds here too.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["case_decision_rule_light_v1"] = SCHEMA_VERSION_RULE
    response_type: ResponseType
    decision_id: str
    correlation_id: str
    idempotency_key: str | None = None
    policy_set: PolicySetRef
    active_version: VersionRef | None = None
    request: LightRuleRequestRef
    asked: LightAskedRef
    outcome: LightOutcomeRef
    information: LightRuleInformationRef | None = None
    verdict: LightRuleVerdictRef | None = None
    retrieval: LightRuleRetrievalRef
    rules: list[LightRuleRef] = Field(default_factory=list)
    citations: list[LightRuleCitationRef] = Field(default_factory=list)
    trace: LightTraceRef
    decision_hash: str
    hash_basis: Literal["case_decision_rule_v1"] = HASH_BASIS_RULE_V1
    receipt_url: str
    latency_ms: int

    @model_validator(mode="after")
    def _rule_light_receipt_is_consistent(self) -> "CaseDecisionRuleLightEnvelope":
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rules must not contain duplicate rule_id values")

        for track, section, outcome in (
            ("information", self.information, self.outcome.information),
            ("verdict", self.verdict, self.outcome.verdict),
        ):
            if section is None:
                if outcome not in (NOT_REQUESTED, NOT_EVALUATED):
                    raise ValueError(
                        f"outcome.{track} is {outcome!r} but the {track} section is null"
                    )
            elif outcome in (NOT_REQUESTED, NOT_EVALUATED):
                raise ValueError(
                    f"outcome.{track} is {outcome!r} but a {track} section was carried"
                )
            elif section.status != outcome:
                raise ValueError(
                    f"outcome.{track} is {outcome!r} but {track}.status is "
                    f"{section.status!r}"
                )
        return self


CaseDecisionLightReceipt = Annotated[
    CaseDecisionLightEnvelope | CaseDecisionRuleLightEnvelope,
    Field(discriminator="schema_version"),
]
