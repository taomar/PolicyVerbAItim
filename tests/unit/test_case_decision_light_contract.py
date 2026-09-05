"""Decision Light is a compact projection, never a second decision path."""
from __future__ import annotations

from datetime import datetime, timezone

from policy_platform.application.policy_case_decision import (
    compact_decision_receipt,
    compact_rule_decision_receipt,
)
from policy_platform.contracts.case_decision import (
    CaseDecisionEnvelope,
    CaseDecisionEnvelopeV2,
    CaseDecisionRuleEnvelope,
)


def _common() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "key-1",
        "policy_set": {"id": "set-1", "key": "set-key", "name": "Policy set"},
        "active_version": {"version_id": "version-1", "version_number": 3},
        "caller": {
            "principal_identity": "agent-1",
            "principal_role": "viewer",
            "authentication_source": "subscription-key",
        },
        "request": {
            "scenario": "Is this entitlement available?",
            "scenario_hash": "a" * 64,
            "scope": "project",
            "reasoning_effort_requested": "medium",
            "received_at": now,
        },
        "retrieval": {
            "status": "narrowed",
            "method": "direct_policy_rrf_elbow_rule_rescue_v1",
            "policies_retained": 1,
            "rule_rescued_policies": 0,
            "reason": "one policy retained",
        },
        "trace": {
            "prompt_version": "prompt-v1",
            "model_deployment": "model-1",
            "stage_latency_ms": {"policy_search": 125, "gather_wall": 900},
            "token_usage": {
                "calls": 2,
                "calls_without_usage": 0,
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "reasoning_tokens": 10,
            },
        },
        "decision_hash": "b" * 64,
        "hash_basis": "case_decision_v2_lang_verification",
        "receipt_url": "/api/policy-decisions/decision-1",
        "decided_at": now,
        "latency_ms": 1200,
    }


def _citation(*, serves: list[str] | None = None) -> dict:
    citation = {
        "rule_id": "R-ONE",
        "policy": {
            "provision_id": "provision-1",
            "provision_key": "entitlement",
            "heading_path": ["Entitlement"],
        },
        "source": {
            "state": "quoted",
            "text": "The record states the entitlement.",
            "page": 4,
            "section": "Entitlement",
        },
    }
    if serves is not None:
        citation["serves"] = serves
    return citation


def test_v2_light_response_keeps_only_essential_decision_fields() -> None:
    data = {
        **_common(),
        "schema_version": "case_decision_v2",
        "receipt_status": "completed",
        "language": None,
        "asked": {
            "information_requested": True,
            "verdict_requested": True,
            "classifier_version": "classifier-v2",
        },
        "outcome": {"information": "answered", "verdict": "answered"},
        "information": {
            "status": "answered",
            "answered": True,
            "answer": "The policy states an entitlement.",
            "citations": [_citation()],
        },
        "verdict": {
            "status": "answered",
            "reached": True,
            "decision": "Entitled under the stated rate",
            "explanation": "The supplied duration produces the requested amount.",
            "verification_requirements": [
                {
                    "fact": "recorded-balance",
                    "label": "Recorded balance",
                    "why_needed": "Confirm before acting.",
                    "required_by_rule_ids": ["R-ONE"],
                }
            ],
            "citations": [_citation()],
            "grounding": {
                "plan_profile": "case-plan-v4",
                "selector_catalogue_version": "case-selectors-v1",
            },
        },
        "considered": [{"provision_key": "unused-extra-policy", "retained": False}],
        "excluded": [{"provision_key": "another-extra-policy"}],
        "citations": [_citation(serves=["information", "verdict"])],
        "size": {"combined_chars": 50000, "budget_chars": 200000, "oversize": False},
    }
    full = CaseDecisionEnvelopeV2.model_validate(data)

    light = compact_decision_receipt(full).model_dump(mode="json")

    assert set(light) == {
        "schema_version",
        "response_type",
        "decision_id",
        "correlation_id",
        "idempotency_key",
        "policy_set",
        "active_version",
        "request",
        "asked",
        "outcome",
        "information",
        "verdict",
        "retrieval",
        "policies",
        "citations",
        "trace",
        "decision_hash",
        "hash_basis",
        "receipt_url",
        "latency_ms",
    }
    assert light["schema_version"] == "case_decision_light_v1"
    assert light["response_type"] == "mixed"
    assert light["verdict"]["decision"] == "Entitled under the stated rate"
    assert light["verdict"]["verification_requirements"][0]["fact"] == "recorded-balance"
    assert [policy["provision_key"] for policy in light["policies"]] == ["entitlement"]
    assert light["citations"][0]["serves"] == ["information", "verdict"]
    assert light["trace"]["plan_profile"] == "case-plan-v4"
    assert light["trace"]["stage_latency_ms"] == {"policy_search": 125, "gather_wall": 900}
    assert light["trace"]["token_usage"]["total_tokens"] == 150
    assert light["latency_ms"] == 1200
    assert light["retrieval"]["method"] == "direct_policy_rrf_elbow_rule_rescue_v1"
    assert light["retrieval"]["policies_retained"] == 1
    assert light["decision_hash"] == full.decision_hash
    assert "considered" not in light
    assert "excluded" not in light
    assert "size" not in light
    assert "language" not in light
    assert "grounding" not in light["verdict"]


def test_v1_replay_can_be_projected_without_rewriting_the_stored_receipt() -> None:
    full = CaseDecisionEnvelope.model_validate(
        {
            **_common(),
            "schema_version": "case_decision_v1",
            "hash_basis": "case_decision_v1",
            "decision_status": "answered",
            "decision": {
                "intent": "decision",
                "status": "answered",
                "verdict": "allowed",
                "explanation": "The rule allows it.",
                "decider_route": "decision",
            },
            "citations": [_citation()],
        }
    )

    light = compact_decision_receipt(full)

    assert light.schema_version == "case_decision_light_v1"
    assert light.response_type == "decision"
    assert light.verdict is not None and light.verdict.decision == "allowed"
    assert light.outcome.verdict == "answered"
    assert light.outcome.information == "not_requested"
    assert light.decision_hash == full.decision_hash
    assert light.receipt_url == full.receipt_url


def _v2(**overrides) -> dict:
    """A minimal complete v2 receipt, so a test can vary one thing at a time."""

    data = {
        **_common(),
        "schema_version": "case_decision_v2",
        "receipt_status": "completed",
        "language": None,
        "asked": {
            "information_requested": True,
            "verdict_requested": False,
            "classifier_version": "classifier-v2",
        },
        "outcome": {"information": "answered", "verdict": "not_requested"},
        "information": {
            "status": "answered",
            "answered": True,
            "answer": "The policy states an entitlement.",
            "citations": [_citation()],
        },
        "citations": [_citation(serves=["information"])],
    }
    data.update(overrides)
    return data


def _rule_full() -> CaseDecisionRuleEnvelope:
    return CaseDecisionRuleEnvelope.model_validate(
        {
            **_common(),
            "schema_version": "case_decision_rule_v1",
            "receipt_status": "completed",
            "request": {
                **_common()["request"],
                "rule_retrieval": True,
            },
            "asked": {
                "information_requested": True,
                "verdict_requested": False,
                "classifier_version": "classifier-v2",
            },
            "outcome": {
                "information": "answered",
                "verdict": "not_requested",
            },
            "information": {
                "status": "answered",
                "answered": True,
                "answer": "The rule states an entitlement.",
                "citations": [
                    {
                        "rule_id": "R-ONE",
                        "source": {
                            "provision_id": "provision-1",
                            "provision_key": "entitlement",
                            "heading_path": ["Entitlement"],
                        },
                        "quote": {
                            "state": "quoted",
                            "text": "The record states the entitlement.",
                            "page": 4,
                            "section": "Entitlement",
                        },
                    }
                ],
            },
            "retrieval": {
                "status": "narrowed",
                "method": "rule_native_v1",
                "retrieval_mode": "rule",
                "rules_selected": 1,
                "rules_grounded": 1,
            },
            "considered_rules": [
                {
                    "rule_id": "R-ONE",
                    "source": {
                        "provision_id": "provision-1",
                        "provision_key": "entitlement",
                        "heading_path": ["Entitlement"],
                    },
                    "grounded": True,
                    "admitted_as": "matched",
                }
            ],
            "citations": [
                {
                    "rule_id": "R-ONE",
                    "source": {
                        "provision_id": "provision-1",
                        "provision_key": "entitlement",
                        "heading_path": ["Entitlement"],
                    },
                    "quote": {
                        "state": "quoted",
                        "text": "The record states the entitlement.",
                        "page": 4,
                        "section": "Entitlement",
                    },
                    "serves": ["information"],
                }
            ],
            "hash_basis": "case_decision_rule_v1",
        }
    )


def test_the_light_response_discloses_the_mode_asked_for_and_the_mode_that_ran() -> None:
    """A/B arms are indistinguishable in the body without this.

    The light response is the whole of what an external caller sees. A caller
    comparing rule retrieval against the default had to take the mode on trust
    from a request no longer in hand, while the route contract promised the
    receipt disclosed it. Requested and executed are reported separately
    because they are two different claims — they agree only because a request
    that cannot be served is refused rather than quietly downgraded, and a
    reader can confirm that only if both are visible.
    """

    full = _rule_full()

    light = compact_rule_decision_receipt(full).model_dump(mode="json")

    assert light["request"]["rule_retrieval"] is True
    assert light["retrieval"]["retrieval_mode"] == "rule"


def test_a_policy_mode_light_response_is_distinguishable_from_a_rule_mode_one() -> None:
    """The discriminating half. A field that never varies discloses nothing."""

    policy_arm = compact_decision_receipt(
        CaseDecisionEnvelopeV2.model_validate(
            _v2(retrieval={**_common()["retrieval"], "retrieval_mode": "policy"})
        )
    ).model_dump(mode="json")
    rule_arm = compact_rule_decision_receipt(_rule_full()).model_dump(mode="json")

    assert policy_arm["request"]["rule_retrieval"] is False
    assert policy_arm["retrieval"]["retrieval_mode"] == "policy"
    assert rule_arm["request"]["rule_retrieval"] is True
    assert rule_arm["retrieval"]["retrieval_mode"] == "rule"
    assert policy_arm["schema_version"] == "case_decision_light_v1"
    assert rule_arm["schema_version"] == "case_decision_rule_light_v1"
    assert policy_arm["request"] != rule_arm["request"]
    assert policy_arm["retrieval"] != rule_arm["retrieval"]


def test_a_receipt_written_before_the_modes_were_named_still_projects() -> None:
    """Null is not a claim that rule retrieval ran, and false is the honest default."""

    full = CaseDecisionEnvelopeV2.model_validate(_v2())

    light = compact_decision_receipt(full).model_dump(mode="json")

    assert light["request"]["rule_retrieval"] is False
    assert light["retrieval"]["retrieval_mode"] is None


def test_naming_the_mode_does_not_disturb_the_sealed_hash() -> None:
    """The echo is a projection of a stored receipt, never an input to one."""

    full = _rule_full()

    light = compact_rule_decision_receipt(full)

    assert light.decision_hash == full.decision_hash
    assert light.hash_basis == full.hash_basis


def test_a_receipt_written_before_the_scores_were_named_still_parses() -> None:
    """Historical receipts under both envelopes, with no `score_disclosure`.

    `PolicyRef` is shared by `considered`, `excluded` and every citation's
    policy, and by both envelope versions. A stored receipt predates all of the
    new fields, so each must be optional and each must read as absent rather
    than as a measurement that came back empty.
    """

    from policy_platform.contracts.case_decision import decision_hash_preimage_v2

    v2 = CaseDecisionEnvelopeV2.model_validate(
        _v2(
            considered=[{"provision_key": "older-policy", "retained": False}],
            excluded=[{"provision_key": "another-older-policy"}],
        )
    )

    assert v2.considered[0].score_disclosure is None
    assert v2.excluded[0].score_disclosure is None
    assert v2.citations[0].policy is not None
    assert v2.citations[0].policy.score_disclosure is None
    # And the sealed subset never mentioned the scores, so naming them cannot
    # move the hash of a receipt written before they had names.
    assert "score_disclosure" not in str(decision_hash_preimage_v2(v2))

    v1 = CaseDecisionEnvelope.model_validate(
        {
            **_common(),
            "schema_version": "case_decision_v1",
            "hash_basis": "case_decision_v1",
            "decision_status": "answered",
            "decision": {
                "intent": "decision",
                "status": "answered",
                "verdict": "Entitled under the stated rate",
                "explanation": "The supplied duration produces the requested amount.",
            },
            "considered": [{"provision_key": "older-policy", "retained": True}],
            "citations": [_citation()],
        }
    )

    assert v1.considered[0].score_disclosure is None
