"""Rule mode returns rules. Policy mode returns policies. Never the other.

WHY THIS FILE EXISTS

`rule_retrieval` was implemented as *rule-first policy selection*: it ranked
rules and then delivered their parent provisions. That inverted the unit of
discovery while leaving the unit of delivery alone, so the evidence that
selected a record and the record put in front of the model were different
things — and the second was an entire provision. A mode intended to be narrower
was therefore structurally wider, and no amount of tuning could have fixed it,
because the width was the contract rather than a parameter.

The corrected contract is one sentence:

    POLICIES => provide policy records. RULES => provide rule records.
    No cross-conversion.

So these tests hold the *separation*, not a size threshold. Nothing here is
tuned to a corpus or to a question set: a size property that followed from a
constant would start passing or failing when the constant moved, which is
exactly the kind of test that stops meaning anything.
"""
from __future__ import annotations

import json

import pytest

from pydantic import TypeAdapter, ValidationError

from policy_platform.contracts.case_decision import (
    CaseDecisionEnvelope,
    CaseDecisionEnvelopeV2,
    request_hash,
)
from policy_platform.contracts.policy_retrieval import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_RULE,
    PolicyRetrievalEnvelope,
    RetrievalEnvelope,
    RetrievedRuleRecord,
    RuleMatchRef,
    RuleRetrievalEnvelope,
    RuleSourceRef,
)
from policy_platform.infrastructure.assistants import ai_case_project as A

_PV = "22222222-2222-4222-8222-222222222222"


def _rule_hit(rule_id: str, provision_key: str, *, reranker: float | None = None) -> dict:
    hit = {
        "id": f"doc-{rule_id}",
        "rule_id": rule_id,
        "policy_id": provision_key,
        "provision_key": provision_key,
        "parent_document_id": f"parent-{provision_key}",
        "document_id": "a-project",
        "document_version": _PV,
        "content_type": A.CONTENT_TYPE_RULE,
        "retrieval_text": f"{provision_key} {rule_id}",
        "@search.score": 0.1,
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


def _policy_hit(provision_key: str, *, score: float, reranker: float | None = None) -> dict:
    hit = {
        "id": f"parent-{provision_key}",
        "policy_id": provision_key,
        "document_id": "a-project",
        "document_version": _PV,
        "content_type": A.CONTENT_TYPE_POLICY,
        "@search.score": score,
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


def _language() -> dict:
    return {
        "source_language": "en",
        "processing_language": "en",
        "response_language": "en",
        "boundary_state": "same_language",
        "output_rendering_state": "not_required",
        "guidance_rendering_state": "not_required",
        "input_translation_profile": "none",
        "processing_scenario": "a question",
        "processing_scenario_hash": "h" * 64,
    }


def _envelope(**overrides) -> dict:
    base = {
        "correlation_id": "correlation-1",
        "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
        "query": {"scenario": "a question", "scenario_hash": "h" * 64},
        "retrieval": {"status": "narrowed"},
        "size": {"combined_chars": 10, "budget_chars": 200000, "oversize": False},
        "language": _language(),
        "token_usage": {
            "calls": 0,
            "calls_without_usage": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "latency_ms": 1,
    }
    base.update(overrides)
    return base


def _rule_record(rule_id: str = "R-1") -> dict:
    return {
        "rule_id": rule_id,
        "source": {"provision_key": "4.1", "heading_path": ["4", "4.1 Faulty equipment"]},
        "match": {"best_rank": 0, "best_score": 2.5, "admitted_as": "matched"},
        "rule": {"rule_id": rule_id, "text": "The rule's own terms."},
    }


class TestTheTwoModesAreDifferentContracts:
    def test_the_policy_envelope_has_no_rules_property_at_all(self) -> None:
        """Absent, not empty — the distinction the whole contract rests on.

        One envelope carrying both arrays would serialise `rules: []` in policy
        mode and `policies: []` in rule mode. A client written for the other
        mode would then read an empty list rather than fail, and "0 policies
        retrieved" is indistinguishable from a genuine negative answer. That
        misreport is silent, which makes it worse than an error.
        """

        assert "rules" not in PolicyRetrievalEnvelope.model_fields
        assert set(PolicyRetrievalEnvelope.model_fields) == {
            "schema_version",
            "correlation_id",
            "policy_set",
            "active_version",
            "query",
            "retrieval",
            "policies",
            "size",
            "language",
            "token_usage",
            "latency_ms",
            "stage_latency_ms",
        }

    def test_the_rule_envelope_has_no_policies_property_at_all(self) -> None:
        assert "policies" not in RuleRetrievalEnvelope.model_fields
        assert set(RuleRetrievalEnvelope.model_fields) == {
            "schema_version",
            "correlation_id",
            "policy_set",
            "active_version",
            "query",
            "retrieval",
            "rules",
            "size",
            "language",
            "token_usage",
            "latency_ms",
            "stage_latency_ms",
        }

    def test_neither_shape_serialises_the_other_ones_field(self) -> None:
        """Checked on the wire, not only on the model."""

        rule_wire = RuleRetrievalEnvelope(**_envelope(), rules=[_rule_record()]).model_dump(
            mode="json"
        )
        policy_wire = PolicyRetrievalEnvelope(**_envelope()).model_dump(mode="json")

        assert "policies" not in rule_wire
        assert "rules" not in policy_wire
        assert rule_wire["schema_version"] == "rule_retrieval_v1"
        assert policy_wire["schema_version"] == "policy_retrieval_v1"

    def test_a_rule_mode_response_cannot_carry_policy_records(self) -> None:
        """The cross-conversion, refused by the type rather than by a check."""

        with pytest.raises(ValidationError):
            RuleRetrievalEnvelope(
                **_envelope(),
                policies=[{"policy": {"provision_key": "4.1"}, "match": {}, "payload": {"a": 1}}],
            )

    def test_rule_retrieval_metadata_cannot_carry_policy_counters(self) -> None:
        with pytest.raises(ValidationError):
            RuleRetrievalEnvelope(
                **{
                    **_envelope(),
                    "retrieval": {
                        "status": "narrowed",
                        "retrieval_mode": "rule",
                        "policies_retained": 1,
                    },
                }
            )

    def test_a_policy_mode_response_cannot_carry_rule_records(self) -> None:
        with pytest.raises(ValidationError):
            PolicyRetrievalEnvelope(**_envelope(), rules=[_rule_record()])

    def test_the_two_modes_answer_under_different_schema_versions(self) -> None:
        """A stale client must fail loudly, not read an absent field as a negative."""

        rule_mode = RuleRetrievalEnvelope(**_envelope(), rules=[_rule_record()])
        policy_mode = PolicyRetrievalEnvelope(**_envelope())

        assert rule_mode.schema_version == "rule_retrieval_v1"
        assert policy_mode.schema_version == "policy_retrieval_v1"
        assert rule_mode.schema_version != policy_mode.schema_version

    def test_the_response_union_is_discriminated_on_the_runtime_tag(self) -> None:
        """The tag chooses the shape, so a caller can dispatch on one field."""

        adapter = TypeAdapter(RetrievalEnvelope)

        as_rule = adapter.validate_python(
            {**_envelope(), "schema_version": "rule_retrieval_v1", "rules": [_rule_record()]}
        )
        as_policy = adapter.validate_python(
            {**_envelope(), "schema_version": "policy_retrieval_v1"}
        )

        assert isinstance(as_rule, RuleRetrievalEnvelope)
        assert isinstance(as_policy, PolicyRetrievalEnvelope)

    def test_a_rule_record_is_not_a_policy_record(self) -> None:
        """No `PolicyMatchRef`, and no field that could be read as one."""

        record = RetrievedRuleRecord(**_rule_record())

        assert isinstance(record.match, RuleMatchRef)
        assert isinstance(record.source, RuleSourceRef)
        assert not hasattr(record, "policy")
        assert not hasattr(record, "payload")


class TestRuleModeAsksNoPolicyQuestion:
    def test_the_rule_selector_takes_no_policy_hits_at_all(self) -> None:
        """Structural, not behavioural.

        `select_rules_only` has no parameter through which a policy hit could
        arrive. A policy channel cannot be re-added by passing one, only by
        changing the signature — which is a change a reviewer sees.
        """

        import inspect

        parameters = set(inspect.signature(A.select_rules_only).parameters)
        assert "policy_hits" not in parameters
        assert parameters == {"rule_hits", "budget", "minimum_gap"}

    def test_every_selected_record_is_a_rule(self) -> None:
        selected, ranked, disclosure = A.select_rules_only(
            [
                _rule_hit("R-1", "A", reranker=3.4),
                _rule_hit("R-2", "A", reranker=3.3),
                _rule_hit("R-3", "B", reranker=0.6),
            ]
        )

        assert selected
        assert all(hit["content_type"] == A.CONTENT_TYPE_RULE for hit in selected)
        assert all(hit["content_type"] == A.CONTENT_TYPE_RULE for hit in ranked)
        assert disclosure["retrieval_mode"] == A.RETRIEVAL_MODE_RULE
        assert disclosure["rules_selected"] == len(selected)

    def test_no_policy_body_or_projection_reaches_a_selected_rule(self) -> None:
        """A rule carries its own terms. A provision's payload is a different thing."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.4), _rule_hit("R-2", "B", reranker=0.5)]
        )

        for hit in selected:
            assert "payload" not in hit
            assert "rules" not in hit
            assert "spans" not in hit
            assert "facts" not in hit

    async def test_the_gather_receives_a_rule_native_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from policy_platform.infrastructure.assistants import ai_case_intent

        seen: dict[str, str] = {}

        async def classify(_scenario: str, **_kwargs):
            return {
                "information_requested": True,
                "verdict_requested": False,
                "reasoning": "information requested",
                "classifier_version": "test",
            }

        async def chat(system: str, user: str, **_kwargs):
            seen["system"] = system
            seen["user"] = user
            return {
                "bears": True,
                "answer": "The rule applies.",
                "cited_rule_ids": ["R-1"],
                "declined": False,
                "note": "",
            }

        monkeypatch.setattr(ai_case_intent, "classify_case_needs", classify)
        monkeypatch.setattr(ai_case_intent, "_chat_json", chat)
        result = await ai_case_intent.answer_case_over_rules(
            [
                {
                    "source": {
                        "provision_key": "4.1",
                        "provision_id": "provision-1",
                        "heading_path": ["Hours"],
                    },
                    "payload": {
                        "spans": {
                            "span-1": {
                                "state": "quoted",
                                "text": "The rule applies.",
                            }
                        },
                        "facts": {},
                        "rules": [
                            {
                                "rule_id": "R-1",
                                "evidence_refs": ["span-1"],
                            }
                        ],
                    },
                }
            ],
            scenario="What applies?",
        )

        assert '"rules":' in seen["user"]
        assert '"policies":' not in seen["user"]
        citation = result["informational"]["citations"][0]
        assert citation["source_provision"]["provision_key"] == "4.1"
        assert "policy" not in citation
        assert result["informational"]["grounding"]["rules_grounded"] == 1

    def test_the_removed_policy_channel_is_not_named_at_all(self) -> None:
        """No zero counter, and no "not applicable" either.

        A zero says a channel ran and admitted nothing. A field named after the
        channel says one exists to be not-applicable. Neither is true here, so
        rule mode names its own strategy and the policy-fallback vocabulary is
        simply absent. Historical `rule_first_parent_grouped_v1` receipts keep
        those counters, which is the only place they still mean anything.
        """

        _selected, _ranked, disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.0)]
        )

        assert not [key for key in disclosure if "fallback" in key]
        assert disclosure["retrieval_strategy"] == A.RULE_ONLY_STRATEGY


class TestTheRuleEnvelopeIsHeldToAStrictTotal:
    """Two budgets, both hard, neither with an exception.

    Characters are not bytes and bytes are not tokens. A character budget on a
    multilingual corpus silently admits up to four times what it claims; a byte
    budget does not predict what the model is charged. Both are measured, and
    the first to bind decides.
    """

    def test_the_envelope_is_bounded_in_exact_serialized_utf8_bytes(self) -> None:
        rules = [{"rule_id": f"R-{index}", "text": "x" * 3000} for index in range(40)]

        kept, omitted, measured = A.fit_rules_within_budget(rules)

        assert measured["rule_grounding_bytes"] <= A.RULE_GROUNDING_BUDGET_BYTES
        assert len(kept) + len(omitted) == len(rules)
        assert omitted

    def test_non_ascii_rules_are_charged_their_real_byte_cost(self) -> None:
        """The reason a character budget was wrong.

        These rules are the same *length* as ASCII ones and several times the
        size. A character budget would admit them as though they were cheap.
        """

        ascii_rules = [{"rule_id": f"A-{i}", "text": "x" * 2000} for i in range(30)]
        arabic_rules = [{"rule_id": f"R-{i}", "text": "\u0645" * 2000} for i in range(30)]

        kept_ascii, _o1, ascii_measured = A.fit_rules_within_budget(ascii_rules)
        kept_arabic, _o2, arabic_measured = A.fit_rules_within_budget(arabic_rules)

        # Same character count per rule, more bytes each, so fewer fit.
        assert len(kept_arabic) < len(kept_ascii)
        assert arabic_measured["rule_grounding_bytes"] <= A.RULE_GROUNDING_BUDGET_BYTES
        assert arabic_measured["rule_grounding_chars"] < arabic_measured["rule_grounding_bytes"]

    def test_the_envelope_is_also_bounded_in_estimated_input_tokens(self) -> None:
        rules = [{"rule_id": f"R-{index}", "text": "x" * 3000} for index in range(40)]

        _kept, _omitted, measured = A.fit_rules_within_budget(rules)

        assert measured["rule_grounding_proxy_tokens"] <= A.RULE_GROUNDING_PROXY_TOKEN_BUDGET

    def test_a_rule_exactly_on_the_boundary_is_admitted(self) -> None:
        """`>` not `>=`: a rule that exactly fills the budget still fits."""

        one = {"rule_id": "R-1", "text": "x" * 100}
        exact = A.canonical_rule_bytes(one)

        kept, omitted, measured = A.fit_rules_within_budget(
            [one], budget_bytes=exact, budget_proxy_tokens=10**9
        )

        assert [rule["rule_id"] for rule in kept] == ["R-1"]
        assert omitted == []
        assert measured["rule_grounding_bytes"] == exact

    def test_the_verdict_selector_catalogue_is_inside_the_byte_cap(self) -> None:
        candidate = {
            "rule_id": "R-1",
            "_grounding_record": {
                "rule": {
                    "rule_id": "R-1",
                    "required_facts": [
                        {
                            "name": "approval-state",
                            "phrase": "approval state",
                            "required": True,
                        }
                    ],
                },
                "source": {"provision_key": "4.1"},
                "spans": {},
                "facts": {},
            },
        }
        information_only_bytes = len(
            A._rule_grounding_transport(
                [candidate], include_selector_catalogue=False
            ).encode("utf-8")
        )

        with pytest.raises(A.RuleGroundingBudgetExceeded):
            A.fit_rules_within_budget(
                [candidate],
                budget_bytes=information_only_bytes,
                budget_proxy_tokens=10**9,
            )

    def test_truncation_happens_only_at_whole_rule_boundaries(self) -> None:
        """Half an instruction is not a smaller answer, it is an unreadable one."""

        rules = [{"rule_id": f"R-{index}", "text": "x" * 3000} for index in range(40)]

        kept, _omitted, _measured = A.fit_rules_within_budget(rules)

        for rule in kept:
            assert len(rule["text"]) == 3000

    def test_every_dropped_rule_is_named_with_a_reason_and_is_deterministic(self) -> None:
        rules = [{"rule_id": f"R-{index}", "text": "x" * 3000} for index in range(40)]

        first = A.fit_rules_within_budget(rules)
        second = A.fit_rules_within_budget(rules)

        assert first[1] == second[1]
        assert all(entry["rule_id"] for entry in first[1])
        assert {entry["reason"] for entry in first[1]} <= {
            A.RULE_OMITTED_OVER_BUDGET_BYTES,
            A.RULE_OMITTED_OVER_PROXY_TOKEN_BUDGET,
        }

    def test_a_single_oversize_rule_is_refused_explicitly_not_returned(self) -> None:
        """No exception may exceed the ceiling, and no false negative either.

        Returning the rule would make the budget advisory. Returning nothing
        would read as "no rule bears on this question", which a caller cannot
        tell from a true negative. So it is a typed refusal carrying
        identifiers and measurements — and not the text that did not fit.
        """

        with pytest.raises(A.RuleGroundingBudgetExceeded) as raised:
            A.fit_rules_within_budget([{"rule_id": "HUGE", "text": "y" * 99_999}])

        error = raised.value
        assert error.code == "rule_grounding_budget_exceeded"
        assert error.rule_id == "HUGE"
        assert error.bytes_measured > A.RULE_GROUNDING_BUDGET_BYTES
        assert "y" * 50 not in str(error)

    def test_a_refusal_is_never_reported_as_no_rule_found(self) -> None:
        """The false-negative control for the refusal path."""

        kept, _omitted, _measured = A.fit_rules_within_budget(
            [{"rule_id": "R-1", "text": "x" * 100}]
        )
        assert kept

        with pytest.raises(A.RuleGroundingBudgetExceeded):
            A.fit_rules_within_budget([{"rule_id": "HUGE", "text": "y" * 99_999}])

    def test_the_rule_budgets_are_well_below_the_policy_grounding_budget(self) -> None:
        assert A.RULE_GROUNDING_BUDGET_BYTES < A.PAYLOAD_BUDGET_CHARS

    def test_the_token_estimate_is_conservative_and_deterministic(self) -> None:
        """It over-counts on purpose: under-counting admits more than promised."""

        assert A.estimate_input_tokens("hello") == A.estimate_input_tokens("hello")
        assert A.estimate_input_tokens("\u0645" * 100) > A.estimate_input_tokens("x" * 100)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "a",
            "plain ascii prose that a tokenizer handles densely",
            "\u0645\u0631\u062d\u0628\u0627 " * 40,          # Arabic
            "\u4f60\u597d\u4e16\u754c" * 60,                  # CJK
            "\U0001f600\U0001f601\U0001f602" * 40,            # astral plane, surrogate pairs
            '{"quoted":"value","escaped":"\\n\\t\\""}' * 30,  # JSON escaping
            "\u200b\u200c\u200d" * 100,                       # zero-width, invisible but not free
            "e\u0301" * 200,                                  # combining marks
            "\x00\x01\x02" * 100,                             # control characters
        ],
        ids=[
            "empty",
            "single",
            "ascii-prose",
            "arabic",
            "cjk",
            "emoji-astral",
            "json-escaping",
            "zero-width",
            "combining-marks",
            "control-characters",
        ],
    )
    def test_the_proxy_is_an_upper_bound_on_any_byte_level_tokenizer(self, text: str) -> None:
        """The guarantee, stated as the thing that is actually provable.

        An earlier version asserted `estimate >= bytes / 2.5`, which merely
        restated the formula and validated nothing about model tokens. This
        asserts the property the bound actually rests on: every token of a
        byte-level BPE vocabulary maps to at least one input byte, so real
        tokens can never exceed the byte count. One proxy token per byte is
        therefore an upper bound that holds without the deployed tokenizer.

        The simulated tokenizers below stand in for that class: any grouping of
        bytes into non-empty tokens produces no more tokens than there are
        bytes.
        """

        proxy = A.estimate_input_tokens(text)
        byte_length = len(text.encode("utf-8"))

        assert proxy == byte_length
        assert proxy == A.estimate_input_tokens(text)
        for group in (1, 2, 3, 4, 8):
            simulated_real_tokens = -(-byte_length // group)
            assert simulated_real_tokens <= proxy

    def test_the_estimator_is_monotonic_under_appending(self) -> None:
        """A larger envelope can never be estimated cheaper than a smaller one.

        Without this the budget could be defeated by adding content: if some
        suffix lowered the estimate, an envelope could grow while appearing to
        shrink, which is precisely the silent over-admission the cap exists to
        stop.
        """

        pieces = ["", "a", "\u0645", "\U0001f600", '"\\n"', "\u200b"]
        running = ""
        previous = A.estimate_input_tokens(running)
        for piece in pieces * 4:
            running += piece
            current = A.estimate_input_tokens(running)
            assert current >= previous
            previous = current

    def test_a_non_ascii_envelope_is_bounded_in_tokens_too(self) -> None:
        """The token cap binds independently of the byte cap."""

        rules = [{"rule_id": f"R-{i}", "text": "\U0001f600" * 500} for i in range(40)]

        _kept, _omitted, measured = A.fit_rules_within_budget(rules)

        assert measured["rule_grounding_bytes"] <= A.RULE_GROUNDING_BUDGET_BYTES
        assert measured["rule_grounding_proxy_tokens"] <= A.RULE_GROUNDING_PROXY_TOKEN_BUDGET

    def test_a_rule_is_cut_on_its_own_evidence_not_by_a_budget(self) -> None:
        """The elbow reads rule scores, so the cut is evidence-shaped."""

        hits = [_rule_hit("LEAD", "A", reranker=3.6)]
        hits.extend(_rule_hit(f"T-{i}", "B", reranker=2.0) for i in range(8))

        selected, _ranked, disclosure = A.select_rules_only(hits)

        assert [hit["rule_id"] for hit in selected] == ["LEAD"]
        assert disclosure["semantic_elbow_applied"] is True
        assert len(selected) < A.RETRIEVAL_RULE_BUDGET


class TestRecallIsPreservedWithinTheRuleContract:
    def test_a_matched_rule_brings_the_neighbour_it_depends_on(self) -> None:
        """THE recall control for this design.

        A rule stating an entitlement and a rule stating the condition on it are
        one instruction split across two records. Delivering the first alone is
        not a smaller answer, it is a wrong one — and that risk is why
        "matched rules only" was too dangerous to ship before. It is answered
        here by admitting the neighbour, not by widening back out to the parent.
        """

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-ENTITLEMENT", "A", reranker=3.5), _rule_hit("R-OTHER", "B", reranker=0.4)]
        )
        rules_by_id = {
            "R-ENTITLEMENT": {"rule_id": "R-ENTITLEMENT", "related_rule_ids": ["R-CONDITION"]},
            "R-CONDITION": {"rule_id": "R-CONDITION", "text": "Only after twelve months."},
        }

        admitted, omitted = A.expand_rule_neighbours(selected, rules_by_id=rules_by_id)

        assert [hit["rule_id"] for hit in admitted] == ["R-ENTITLEMENT", "R-CONDITION"]
        assert admitted[1][A.RULE_ADMITTED_AS_FIELD] == A.RULE_ADMITTED_NEIGHBOUR
        assert admitted[1]["required_by_rule_id"] == "R-ENTITLEMENT"
        assert omitted == []

    def test_an_override_brings_what_it_overrides(self) -> None:
        """Half a change is not a smaller answer either."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-NEW", "A", reranker=3.5)]
        )
        rules_by_id = {
            "R-NEW": {"rule_id": "R-NEW", "supersedes_rule_ids": ["R-OLD"]},
            "R-OLD": {"rule_id": "R-OLD", "text": "The displaced rule."},
        }

        admitted, _omitted = A.expand_rule_neighbours(selected, rules_by_id=rules_by_id)

        assert {hit["rule_id"] for hit in admitted} == {"R-NEW", "R-OLD"}

    def test_expansion_reaches_rules_and_never_the_parent_provision(self) -> None:
        """The recall argument is exactly how the policy body would come back."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.5)]
        )
        rules_by_id = {
            "R-1": {"rule_id": "R-1", "related_rule_ids": ["R-2"]},
            "R-2": {"rule_id": "R-2", "text": "A neighbour."},
        }

        admitted, _omitted = A.expand_rule_neighbours(selected, rules_by_id=rules_by_id)

        for hit in admitted:
            assert "payload" not in hit
            assert "rules" not in hit
            assert "spans" not in hit

    def test_a_neighbour_that_cannot_be_admitted_is_named_not_dropped(self) -> None:
        """No silent drops, for either reason it can fail."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.5)]
        )
        rules_by_id = {
            "R-1": {"rule_id": "R-1", "related_rule_ids": ["R-MISSING", "R-2"]},
            "R-2": {"rule_id": "R-2", "text": "A neighbour."},
        }

        admitted, omitted = A.expand_rule_neighbours(selected, rules_by_id=rules_by_id)
        assert {
            "rule_id": "R-MISSING",
            "reason": A.RULE_OMITTED_UNRESOLVED,
            "required_by_rule_id": "R-1",
        } in omitted

        _bounded, omitted_by_budget = A.expand_rule_neighbours(
            selected, rules_by_id=rules_by_id, budget=1
        )
        assert {
            "rule_id": "R-2",
            "reason": A.RULE_OMITTED_NO_SLOT,
            "required_by_rule_id": "R-1",
        } in omitted_by_budget

    def test_expansion_is_bounded_and_cannot_grow_without_limit(self) -> None:
        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.5)]
        )
        rules_by_id = {"R-1": {"rule_id": "R-1", "related_rule_ids": [f"N-{i}" for i in range(40)]}}
        rules_by_id.update({f"N-{i}": {"rule_id": f"N-{i}"} for i in range(40)})

        admitted, omitted = A.expand_rule_neighbours(selected, rules_by_id=rules_by_id, budget=4)

        assert len(admitted) == 4
        assert len(omitted) == 37


class TestRuleGroundingIsSmallerThanPolicyGrounding:
    def test_a_rule_record_is_smaller_than_the_provision_that_contains_it(self) -> None:
        """The size property follows from the contract, not from a threshold.

        A rule record carries one rule's terms and citation identifiers. A policy
        record carries the provision: every rule of it, and the spans and facts
        they reference. Comparing them on a fixture rather than on a corpus is
        deliberate — a size assertion tuned to particular questions would stop
        being about the contract.
        """

        provision_rules = [
            {"rule_id": f"R-{i}", "text": f"Rule {i} of the provision.", "span_ids": [f"S-{i}"]}
            for i in range(20)
        ]
        policy_record = {
            "policy": {"provision_key": "4.1", "heading_path": ["4", "4.1"]},
            "record": {
                "provision_key": "4.1",
                "rules": provision_rules,
                "spans": {f"S-{i}": {"text": "A verbatim source sentence." * 4} for i in range(20)},
                "facts": {f"F-{i}": {"value": i} for i in range(20)},
            },
        }
        rule_record = {
            "rule_id": "R-3",
            "source": {"provision_key": "4.1", "heading_path": ["4", "4.1"]},
            "match": {"best_rank": 0, "best_score": 2.5, "admitted_as": "matched"},
            "rule": provision_rules[3],
        }

        policy_bytes = len(json.dumps(policy_record, separators=(",", ":")))
        rule_bytes = len(json.dumps(rule_record, separators=(",", ":")))

        assert rule_bytes < policy_bytes

    def test_a_rule_carries_citation_identifiers_and_not_provision_content(self) -> None:
        """Minimal parent metadata is the limit, and it is a real limit.

        A citation has to resolve, so the provision is named. Naming it is not
        the same as carrying it, and this is the line that keeps rule mode from
        becoming policy mode again one convenience field at a time.
        """

        record = RetrievedRuleRecord(**_rule_record())

        assert record.source.provision_key == "4.1"
        assert record.source.heading_path == ["4", "4.1 Faulty equipment"]
        source_fields = set(RuleSourceRef.model_fields)
        assert source_fields == {
            "provision_key",
            "provision_id",
            "heading_path",
            "document_id",
            "document_version",
        }
        assert "rules" not in source_fields
        assert "payload" not in source_fields
        assert "spans" not in source_fields


class TestPolicyModeIsUntouched:
    def test_policy_mode_selection_is_unchanged(self) -> None:
        """The control.

        "Rule mode is smaller" must not be achievable by making policy mode
        larger, or by narrowing it. Policy mode's recall-biased flat default is
        deliberate and is asserted here so this work cannot quietly move it.
        """

        flat = [
            _policy_hit("A", score=0.9, reranker=1.02),
            _policy_hit("B", score=0.8, reranker=1.01),
            _policy_hit("C", score=0.7, reranker=1.00),
        ]

        selected, evidence = A.select_semantic_policy_hits(flat)

        assert len(selected) == 3
        assert evidence["semantic_selected"] == 3

    def test_the_policy_retrieval_schema_version_is_unchanged(self) -> None:
        assert SCHEMA_VERSION == "policy_retrieval_v1"
        assert PolicyRetrievalEnvelope(**_envelope()).schema_version == SCHEMA_VERSION


class TestTheOlderContractsStillHold:
    def test_request_hash_separation_is_unchanged(self) -> None:
        """Two modes remain two requests, and old keys still replay."""

        base = {
            "policy_set_key": "a-project",
            "scenario": "a question",
            "provision_id": None,
            "reasoning_effort": "medium",
        }

        assert request_hash(**base) == request_hash(**base, rule_retrieval=False)
        assert request_hash(**base) != request_hash(**base, rule_retrieval=True)

    def test_receipts_written_before_this_change_still_parse(self) -> None:
        """Both envelope versions, unchanged by the rule contract."""

        common = {
            "decision_id": "decision-1",
            "correlation_id": "correlation-1",
            "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
            "request": {
                "scenario": "a question",
                "scenario_hash": "h" * 64,
                "scope": "project",
                "reasoning_effort_requested": "medium",
                "received_at": "2026-01-01T00:00:00Z",
            },
            "retrieval": {"status": "narrowed"},
            "caller": {
                "principal_identity": "agent-1",
                "principal_role": "viewer",
                "authentication_source": "subscription-key",
            },
            "trace": {"prompt_version": "p1"},
            "decision_hash": "b" * 64,
            "receipt_url": "/api/policy-decisions/decision-1",
            "decided_at": "2026-01-01T00:00:00Z",
            "latency_ms": 10,
            "considered": [{"provision_key": "older-policy", "retained": True}],
        }

        v2 = CaseDecisionEnvelopeV2.model_validate(
            {
                **common,
                "schema_version": "case_decision_v2",
                "hash_basis": "case_decision_v2",
                "receipt_status": "completed",
                "asked": {"information_requested": True, "verdict_requested": False},
                "outcome": {"information": "not_evaluated", "verdict": "not_evaluated"},
            }
        )
        v1 = CaseDecisionEnvelope.model_validate(
            {
                **common,
                "schema_version": "case_decision_v1",
                "hash_basis": "case_decision_v1",
                "decision_status": "answered",
                "decision": {"intent": "decision", "status": "answered"},
            }
        )

        assert v2.considered[0].provision_key == "older-policy"
        assert v1.considered[0].provision_key == "older-policy"
        assert v2.request.rule_retrieval is False



class TestEvidenceDecidesCardinalityNotTheBudget:
    """Ledger rewrites #10, #11, #12, #14.

    The original shipped defect was a mode with no cardinality cut: every
    candidate was ordered, the budget was the only surviving limit, and it was
    always saturated. These are that defect's regression tests, carried across
    to the rule contract rather than lost with the parent-grouped code they
    happened to be written against.
    """

    def test_a_dominant_lead_over_a_flat_tail_grounds_one(self) -> None:
        """Ledger #10."""

        hits = [_rule_hit("LEAD", "A", reranker=3.6)]
        hits.extend(_rule_hit(f"T-{i}", "B", reranker=2.0) for i in range(10))

        selected, ranked, disclosure = A.select_rules_only(hits)

        assert [hit["rule_id"] for hit in selected] == ["LEAD"]
        # The control on the control: every tail rule existed and placed. The
        # evidence did not support reading them; nothing was missing.
        assert len(ranked) == 11
        assert disclosure["semantic_elbow_applied"] is True

    def test_a_rule_below_the_cut_is_not_admitted_because_budget_remains(self) -> None:
        """Ledger #11. Slots left over are not an argument for filling them."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("STRONG", "A", reranker=3.2), _rule_hit("WEAK", "B", reranker=1.0)]
        )

        assert [hit["rule_id"] for hit in selected] == ["STRONG"]
        assert len(selected) < A.RETRIEVAL_RULE_BUDGET

    def test_a_flat_rule_ranking_is_not_cut_because_nothing_separates_it(self) -> None:
        """Ledger #12. Uncertainty must not be turned into false confidence."""

        hits = [_rule_hit(f"R-{i}", "A", reranker=2.00 + i / 1000) for i in range(4)]

        selected, _ranked, disclosure = A.select_rules_only(hits)

        assert len(selected) == 4
        assert disclosure["semantic_elbow_applied"] is False

    def test_an_irrelevant_question_does_not_ground_the_budget_because_rules_exist(
        self,
    ) -> None:
        """Ledger #14 — the defect that started this whole line of work.

        A question the corpus does not answer once retained five policies
        because five existed. The rule contract must not reproduce it: a corpus
        full of weakly-scoring rules is not evidence, and the cut must say so.
        """

        hits = [_rule_hit(f"R-{i}", "A", reranker=0.3 + i / 1000) for i in range(20)]

        selected, ranked, _disclosure = A.select_rules_only(hits)

        assert len(ranked) == 20
        assert len(selected) < A.RETRIEVAL_RULE_BUDGET


class TestTheModeAndItsCutAreOnTheRecord:
    """Ledger rewrites #19, #20, #23, #24, #25, #26."""

    def test_the_rule_disclosure_reports_the_mode_the_cut_and_the_cardinality(self) -> None:
        """Ledger #19."""

        _selected, _ranked, disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.4), _rule_hit("R-2", "B", reranker=0.6)]
        )

        assert disclosure["retrieval_mode"] == A.RETRIEVAL_MODE_RULE
        assert disclosure["retrieval_strategy"] == A.RULE_ONLY_STRATEGY
        assert disclosure["precision_mode"] == A.RULE_ONLY_RETRIEVAL_METHOD
        assert disclosure["direct_rule_order"] == A.DIRECT_RULE_ORDER_SEMANTIC
        assert disclosure["rules_selected"] == 1
        assert disclosure["semantic_cutoff_score"] is not None

    def test_the_rule_mode_method_is_never_the_parent_grouped_one(self) -> None:
        """Ledger #20's surviving half, stated as a property of the name.

        The retired path was `rule_first_parent_grouped_v1`. A receipt that
        still said so would describe a selection that no longer happens.
        """

        _selected, _ranked, disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.0)]
        )

        assert disclosure["precision_mode"] == "rule_documents_semantic_v1"
        assert "parent" not in disclosure["precision_mode"]

    def test_a_rule_score_is_on_the_scale_of_the_cutoff_beside_it(self) -> None:
        """Ledger #23 — the Phase B disclosure defect, in rule terms.

        A receipt reported `semantic_cutoff_score` beside a fusion score that
        could not be compared to it. In rule mode every score is a rule reranker
        score, so the property is simpler to state and must still be stated.
        """

        selected, _ranked, disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.4), _rule_hit("R-2", "B", reranker=0.6)]
        )

        cutoff = disclosure["semantic_cutoff_score"]
        for hit in selected:
            named = A._score_disclosure(hit)
            assert named["best_score_kind"] == A.BEST_SCORE_KIND_SEMANTIC
            assert named["semantic_score"] is not None
            assert named["semantic_score"] >= cutoff

    def test_a_rule_retrieval_counter_the_decider_emits_reaches_the_receipt(self) -> None:
        """Ledger #24. The allow-list guard that caught the original inert patch."""

        from policy_platform.application.policy_case_decision import _RETRIEVAL_FIELDS

        _selected, _ranked, disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.0)]
        )

        contract_keys = set(_RETRIEVAL_FIELDS)
        emitted = set(disclosure)
        # Every key is either already carried by the contract or is a rule-mode
        # key this change introduced. Nothing is emitted under a name that would
        # be silently dropped without anyone noticing.
        introduced = {
            "retrieval_strategy",
            "rules_selected",
            "rule_grounding_bytes",
            "rule_grounding_budget_bytes",
            "rule_grounding_proxy_tokens",
            "rule_grounding_proxy_token_budget",
            "rule_grounding_chars",
            "rules_grounded",
            "rules_omitted",
        }
        assert emitted <= contract_keys | introduced, sorted(
            emitted - contract_keys - introduced
        )

    def test_every_rule_record_carries_its_own_cut_disclosure(self) -> None:
        """Ledger #25. Per-record disclosure, now attached to each rule."""

        selected, _ranked, _disclosure = A.select_rules_only(
            [_rule_hit("R-1", "A", reranker=3.4), _rule_hit("R-2", "A", reranker=3.3)]
        )

        assert selected
        for hit in selected:
            named = A._score_disclosure(hit)
            assert named["best_score_kind"] is not None
            assert hit[A.RULE_ADMITTED_AS_FIELD] == A.RULE_ADMITTED_MATCHED

    def test_a_semantic_rule_score_is_the_reranker_score_it_names(self) -> None:
        hit = _rule_hit("R-1", "A", reranker=3.4)
        hit["@search.score"] = 0.1

        selected, _ranked, _disclosure = A.select_rules_only([hit])

        assert selected[0]["@search.score"] == pytest.approx(3.4)
        assert selected[0][A.SCORE_KIND_FIELD] == A.BEST_SCORE_KIND_SEMANTIC
        disclosure = A._score_disclosure(selected[0])
        assert disclosure["best_score_kind"] == A.BEST_SCORE_KIND_SEMANTIC
        assert disclosure["semantic_score"] == pytest.approx(3.4)

    def test_naming_a_rule_score_changes_no_rule_selection(self) -> None:
        """Ledger #26. Additivity by observation, not by assertion."""

        hits = [
            _rule_hit("R-1", "A", reranker=3.4),
            _rule_hit("R-2", "B", reranker=3.3),
            _rule_hit("R-3", "C", reranker=0.8),
        ]
        named, _r1, _d1 = A.select_rules_only(hits)

        bare_hits = [
            {k: v for k, v in hit.items() if k != A.SCORE_KIND_FIELD}
            for hit in [
                _rule_hit("R-1", "A", reranker=3.4),
                _rule_hit("R-2", "B", reranker=3.3),
                _rule_hit("R-3", "C", reranker=0.8),
            ]
        ]
        bare, _r2, _d2 = A.select_rules_only(bare_hits)

        assert [hit["rule_id"] for hit in named] == [hit["rule_id"] for hit in bare]



# ── the rule receipt seals rule evidence ─────────────────────────────


def _rule_envelope(**overrides):
    from policy_platform.contracts.case_decision import CaseDecisionRuleEnvelope

    data = {
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
        "caller": {
            "principal_identity": "agent-1",
            "principal_role": "viewer",
            "authentication_source": "subscription-key",
        },
        "request": {
            "scenario": "a question",
            "scenario_hash": "h" * 64,
            "scope": "project",
            "reasoning_effort_requested": "medium",
            "rule_retrieval": True,
            "received_at": "2026-01-01T00:00:00Z",
        },
        "asked": {"information_requested": True, "verdict_requested": False},
        "outcome": {"information": "not_evaluated", "verdict": "not_evaluated"},
        "retrieval": {"status": "narrowed", "retrieval_mode": "rule"},
        "considered_rules": [
            {
                "rule_id": "R-1",
                "source": {"provision_key": "4.1"},
                "grounded": True,
                "admitted_as": "matched",
            },
            {
                "rule_id": "R-9",
                "source": {"provision_key": "4.1"},
                "grounded": True,
                "admitted_as": "neighbour",
                "required_by_rule_id": "R-1",
            },
        ],
        "trace": {"prompt_version": "p1"},
        "decision_hash": "b" * 64,
        "receipt_url": "/api/policy-decisions/decision-1",
        "decided_at": "2026-01-01T00:00:00Z",
        "latency_ms": 10,
    }
    data.update(overrides)
    return CaseDecisionRuleEnvelope.model_validate(data)


def _rule_citation(*, serves: list[str] | None = None) -> dict:
    citation = {
        "rule_id": "R-1",
        "source": {
            "provision_key": "4.1",
            "provision_id": "provision-1",
            "heading_path": ["Hours"],
        },
        "quote": {
            "state": "quoted",
            "text": "Work must not exceed the stated limit.",
            "page": 4,
            "section": "Hours",
        },
    }
    if serves is not None:
        citation["serves"] = serves
    return citation


def _semantic_rule_envelope(**overrides):
    data = {
        "asked": {"information_requested": True, "verdict_requested": True},
        "outcome": {"information": "answered", "verdict": "answered"},
        "information": {
            "status": "answered",
            "answered": True,
            "answer": "The rule states a limit.",
            "route": "informational",
            "citations": [_rule_citation()],
            "note": "Information note",
        },
        "verdict": {
            "status": "answered",
            "reached": True,
            "decision": "within limit",
            "explanation": "The supplied value is below the limit.",
            "verification_requirements": [
                {
                    "fact": "record",
                    "label": "Recorded value",
                    "why_needed": "Confirm the source record.",
                    "required_by_rule_ids": ["R-1"],
                }
            ],
            "route": "decision",
            "citations": [_rule_citation()],
            "note": "Verdict note",
        },
        "citations": [_rule_citation(serves=["information", "verdict"])],
    }
    data.update(overrides)
    return _rule_envelope(**data)


class TestTheRuleReceiptIsItsOwnContract:
    def test_it_has_no_policy_considered_field_to_leave_empty(self) -> None:
        """The defect this design exists to avoid.

        An empty `considered` on a rule receipt would be sealed by the hash, so
        the receipt would verify while attesting to nothing about the evidence
        actually read. There is no such field to be empty.
        """

        from policy_platform.contracts.case_decision import (
            CaseDecisionRuleEnvelope,
            RuleCitationRef,
        )

        assert "considered" not in CaseDecisionRuleEnvelope.model_fields
        assert "excluded" not in CaseDecisionRuleEnvelope.model_fields
        assert "considered_rules" in CaseDecisionRuleEnvelope.model_fields
        # And a rule citation cannot carry a policy reference.
        assert "policy" not in RuleCitationRef.model_fields

    def test_it_answers_under_its_own_version_and_basis(self) -> None:
        from policy_platform.contracts.case_decision import (
            HASH_BASIS_RULE_V1,
            SCHEMA_VERSION_RULE_V1,
            SCHEMA_VERSION_V2,
        )

        envelope = _rule_envelope()

        assert envelope.schema_version == SCHEMA_VERSION_RULE_V1 == "case_decision_rule_v1"
        assert envelope.hash_basis == HASH_BASIS_RULE_V1
        assert envelope.schema_version != SCHEMA_VERSION_V2


class TestTheRuleHashSealsTheRuleEvidence:
    """Tamper tests. A hash that does not move is a hash that seals nothing."""

    def test_changing_a_rule_id_changes_the_hash(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        base = decision_hash_rule_v1(_rule_envelope())
        tampered = _rule_envelope(
            considered_rules=[
                {"rule_id": "R-2", "source": {"provision_key": "4.1"}, "grounded": True,
                 "admitted_as": "matched"},
                {"rule_id": "R-9", "source": {"provision_key": "4.1"}, "grounded": True,
                 "admitted_as": "neighbour", "required_by_rule_id": "R-1"},
            ]
        )

        assert decision_hash_rule_v1(tampered) != base

    def test_changing_whether_a_rule_was_grounded_changes_the_hash(self) -> None:
        """A rule considered and dropped is a different decision from one read."""

        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        base = decision_hash_rule_v1(_rule_envelope())
        tampered = _rule_envelope(
            considered_rules=[
                {"rule_id": "R-1", "source": {"provision_key": "4.1"}, "grounded": False,
                 "admitted_as": "matched"},
                {"rule_id": "R-9", "source": {"provision_key": "4.1"}, "grounded": True,
                 "admitted_as": "neighbour", "required_by_rule_id": "R-1"},
            ]
        )

        assert decision_hash_rule_v1(tampered) != base

    def test_changing_how_a_rule_was_admitted_changes_the_hash(self) -> None:
        """Two answers on the same rules for different reasons differ."""

        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        base = decision_hash_rule_v1(_rule_envelope())
        tampered = _rule_envelope(
            considered_rules=[
                {"rule_id": "R-1", "source": {"provision_key": "4.1"}, "grounded": True,
                 "admitted_as": "matched"},
                {"rule_id": "R-9", "source": {"provision_key": "4.1"}, "grounded": True,
                 "admitted_as": "matched"},
            ]
        )

        assert decision_hash_rule_v1(tampered) != base

    def test_dropping_a_rule_for_budget_does_not_hash_like_never_selecting_it(self) -> None:
        """Why `omitted_reason` is sealed."""

        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        dropped = _rule_envelope(
            considered_rules=[
                {"rule_id": "R-1", "source": {"provision_key": "4.1"}, "grounded": False,
                 "admitted_as": "matched",
                 "omitted_reason": "over_rule_grounding_byte_budget"},
            ]
        )
        never = _rule_envelope(
            considered_rules=[
                {"rule_id": "R-1", "source": {"provision_key": "4.1"}, "grounded": False,
                 "admitted_as": "matched"},
            ]
        )

        assert decision_hash_rule_v1(dropped) != decision_hash_rule_v1(never)

    def test_rule_order_does_not_change_the_hash(self) -> None:
        """Sorted, so a reordering is not mistaken for a different decision."""

        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        forward = _rule_envelope()
        reversed_order = _rule_envelope(
            considered_rules=list(reversed(forward.model_dump()["considered_rules"]))
        )

        assert decision_hash_rule_v1(reversed_order) == decision_hash_rule_v1(forward)

    def test_the_preimage_names_every_sealed_rule_field(self) -> None:
        """Documented and checked, so the docstring cannot drift from the code."""

        from policy_platform.contracts.case_decision import decision_hash_preimage_rule_v1

        preimage = decision_hash_preimage_rule_v1(_rule_envelope())

        assert set(preimage["rules"][0]) == {
            "rule_id",
            "source",
            "grounded",
            "best_rank",
            "best_score",
            "score_kind",
            "semantic_score",
            "admitted_as",
            "required_by_rule_id",
            "omitted_reason",
        }
        assert preimage["rule_retrieval"] is True
        assert preimage["retrieval"]["retrieval_mode"] == "rule"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("answer", "A changed answer."),
            ("explanation", "A changed explanation."),
            ("route", "changed-route"),
            ("note", "A changed note."),
        ],
    )
    def test_every_semantic_information_field_moves_the_hash(
        self, field: str, value: object
    ) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        tampered = original.model_copy(deep=True)
        assert tampered.information is not None
        tampered.information = tampered.information.model_copy(update={field: value})

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("decision", "outside limit"),
            ("explanation", "A changed explanation."),
            ("route", "changed-route"),
            ("note", "A changed note."),
        ],
    )
    def test_every_semantic_verdict_field_moves_the_hash(
        self, field: str, value: object
    ) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        tampered = original.model_copy(deep=True)
        assert tampered.verdict is not None
        tampered.verdict = tampered.verdict.model_copy(update={field: value})

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    @pytest.mark.parametrize(
        ("section_name", "field", "value"),
        [
            ("information", "text", "A changed information quote."),
            ("verdict", "page", 99),
        ],
    )
    def test_each_section_seals_its_own_rule_citations(
        self, section_name: str, field: str, value: object
    ) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        tampered = original.model_copy(deep=True)
        section = getattr(tampered, section_name)
        citation = section.citations[0]
        citation.quote = citation.quote.model_copy(update={field: value})

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    def test_missing_information_and_its_flat_compatibility_list_are_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _rule_envelope(
            asked={"information_requested": False, "verdict_requested": True},
            outcome={
                "information": "not_requested",
                "verdict": "missing_required_facts",
            },
            verdict={
                "status": "missing_required_facts",
                "reached": False,
                "missing_information": [
                    {
                        "fact": "duration",
                        "label": "Duration",
                        "why_needed": "The rule turns on duration.",
                        "required_by_rule_ids": ["R-1"],
                    }
                ],
                "missing_required_facts": ["duration"],
                "citations": [_rule_citation()],
            },
            citations=[_rule_citation(serves=["verdict"])],
        )
        changed_structured = original.model_copy(deep=True)
        assert changed_structured.verdict is not None
        item = changed_structured.verdict.missing_information[0]
        changed_structured.verdict.missing_information[0] = item.model_copy(
            update={"why_needed": "Changed reason."}
        )
        changed_flat = original.model_copy(deep=True)
        assert changed_flat.verdict is not None
        changed_flat.verdict.missing_required_facts = ["different-fact"]

        base = decision_hash_rule_v1(original)
        assert decision_hash_rule_v1(changed_structured) != base
        assert decision_hash_rule_v1(changed_flat) != base

    def test_verification_requirements_are_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        tampered = original.model_copy(deep=True)
        assert tampered.verdict is not None
        item = tampered.verdict.verification_requirements[0]
        tampered.verdict.verification_requirements[0] = item.model_copy(
            update={"required_by_rule_ids": ["R-9"]}
        )

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    def test_the_merged_citation_source_and_track_tags_are_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        changed_source = original.model_copy(deep=True)
        changed_source.citations[0].source = changed_source.citations[
            0
        ].source.model_copy(update={"provision_id": "provision-2"})
        changed_serves = original.model_copy(deep=True)
        changed_serves.citations[0].serves = ["verdict"]

        base = decision_hash_rule_v1(original)
        assert decision_hash_rule_v1(changed_source) != base
        assert decision_hash_rule_v1(changed_serves) != base

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("best_rank", 99),
            ("best_score", 0.25),
            ("score_kind", "changed"),
            ("semantic_score", 1.5),
            ("required_by_rule_id", "R-2"),
        ],
    )
    def test_rule_evidence_metadata_is_sealed(
        self, field: str, value: object
    ) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _rule_envelope()
        tampered = original.model_copy(deep=True)
        tampered.considered_rules[0] = tampered.considered_rules[0].model_copy(
            update={field: value}
        )

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    def test_requested_and_executed_modes_are_read_not_hardcoded(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _rule_envelope()
        changed_request = original.model_copy(deep=True)
        changed_request.request = changed_request.request.model_copy(
            update={"rule_retrieval": False}
        )
        changed_execution = original.model_copy(deep=True)
        changed_execution.retrieval = changed_execution.retrieval.model_copy(
            update={"retrieval_mode": "policy"}
        )

        base = decision_hash_rule_v1(original)
        assert decision_hash_rule_v1(changed_request) != base
        assert decision_hash_rule_v1(changed_execution) != base

    def test_request_asked_and_outcome_fields_are_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _semantic_rule_envelope()
        changed_request = original.model_copy(deep=True)
        changed_request.request = changed_request.request.model_copy(
            update={"additional_instructions_hash": "c" * 64}
        )
        changed_asked = original.model_copy(deep=True)
        changed_asked.asked = changed_asked.asked.model_copy(
            update={"information_requested": False}
        )
        changed_outcome = original.model_copy(deep=True)
        changed_outcome.outcome = changed_outcome.outcome.model_copy(
            update={"information": "declined"}
        )

        base = decision_hash_rule_v1(original)
        assert decision_hash_rule_v1(changed_request) != base
        assert decision_hash_rule_v1(changed_asked) != base
        assert decision_hash_rule_v1(changed_outcome) != base

    def test_considered_rule_source_identifiers_are_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        original = _rule_envelope()
        tampered = original.model_copy(deep=True)
        source = tampered.considered_rules[0].source
        tampered.considered_rules[0].source = source.model_copy(
            update={"heading_path": ["Changed"]}
        )

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)

    def test_the_adjudicated_language_rendering_is_sealed(self) -> None:
        from policy_platform.contracts.case_decision import decision_hash_rule_v1

        language = {
            "source_language": "en",
            "processing_language": "en",
            "response_language": "en",
            "boundary_state": "identity",
            "output_rendering_state": "not_required",
            "guidance_rendering_state": "not_required",
            "input_translation_profile": "input-v1",
            "processing_scenario": "a question",
            "processing_scenario_hash": "a" * 64,
        }
        original = _rule_envelope(language=language)
        tampered = original.model_copy(deep=True)
        assert tampered.language is not None
        tampered.language = tampered.language.model_copy(
            update={"processing_scenario_hash": "b" * 64}
        )

        assert decision_hash_rule_v1(tampered) != decision_hash_rule_v1(original)


class TestTheRuleReceiptFailsClosed:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("receipt_status", "pending"),
            ("hash_basis", "case_decision_v2"),
            ("request", {
                "scenario": "a question",
                "scenario_hash": "h" * 64,
                "scope": "project",
                "reasoning_effort_requested": "medium",
                "rule_retrieval": False,
                "received_at": "2026-01-01T00:00:00Z",
            }),
            ("retrieval", {"status": "narrowed", "retrieval_mode": "policy"}),
            ("retrieval", {
                "status": "narrowed",
                "retrieval_mode": "rule",
                "policies_retained": 1,
            }),
            ("policies", []),
            ("considered", []),
        ],
    )
    def test_policy_or_incomplete_top_level_shapes_are_rejected(
        self, field: str, value: object
    ) -> None:
        with pytest.raises(ValidationError):
            _rule_envelope(**{field: value})

    def test_a_policy_shaped_section_citation_is_rejected(self) -> None:
        citation = _rule_citation()
        citation["policy"] = {"provision_key": "4.1"}

        with pytest.raises(ValidationError):
            _semantic_rule_envelope(
                information={
                    "status": "answered",
                    "answered": True,
                    "answer": "An answer.",
                    "citations": [citation],
                }
            )

    @pytest.mark.parametrize("grounded", [None])
    def test_grounded_must_be_a_real_boolean(self, grounded: object) -> None:
        rules = _rule_envelope().model_dump(mode="json")["considered_rules"]
        rules[0]["grounded"] = grounded

        with pytest.raises(ValidationError):
            _rule_envelope(considered_rules=rules)

    def test_grounded_must_be_present(self) -> None:
        rules = _rule_envelope().model_dump(mode="json")["considered_rules"]
        rules[0].pop("grounded")

        with pytest.raises(ValidationError):
            _rule_envelope(considered_rules=rules)

    def test_duplicate_rule_ids_are_rejected_before_canonical_sorting(self) -> None:
        rules = _rule_envelope().model_dump(mode="json")["considered_rules"]
        rules[1]["rule_id"] = rules[0]["rule_id"]

        with pytest.raises(ValidationError, match="duplicate rule_id"):
            _rule_envelope(considered_rules=rules)

    def test_outcome_and_section_must_agree(self) -> None:
        with pytest.raises(ValidationError, match="information section is null"):
            _rule_envelope(
                outcome={"information": "answered", "verdict": "not_requested"},
                asked={"information_requested": True, "verdict_requested": False},
            )


class TestHistoricalReceiptsAreUntouched:
    def test_the_policy_preimage_is_unchanged_by_the_rule_basis(self) -> None:
        """Never recompute or reinterpret a stored receipt.

        The rule basis is additive: a new schema version and a new preimage
        function. The V2 preimage must still seal exactly what it sealed, or
        every stored receipt's hash would stop verifying.
        """

        from policy_platform.contracts.case_decision import (
            CaseDecisionEnvelopeV2,
            decision_hash_preimage_v2,
        )

        stored = CaseDecisionEnvelopeV2.model_validate(
            {
                "schema_version": "case_decision_v2",
                "hash_basis": "case_decision_v2",
                "receipt_status": "completed",
                "decision_id": "decision-1",
                "correlation_id": "correlation-1",
                "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
                "caller": {
                    "principal_identity": "agent-1",
                    "principal_role": "viewer",
                    "authentication_source": "subscription-key",
                },
                "request": {
                    "scenario": "a question",
                    "scenario_hash": "h" * 64,
                    "scope": "project",
                    "reasoning_effort_requested": "medium",
                    "received_at": "2026-01-01T00:00:00Z",
                },
                "asked": {"information_requested": True, "verdict_requested": False},
                "outcome": {"information": "not_evaluated", "verdict": "not_evaluated"},
                "retrieval": {"status": "narrowed"},
                "considered": [{"provision_key": "older-policy", "retained": True}],
                "trace": {"prompt_version": "p1"},
                "decision_hash": "b" * 64,
                "receipt_url": "/api/policy-decisions/decision-1",
                "decided_at": "2026-01-01T00:00:00Z",
                "latency_ms": 10,
            }
        )

        preimage = decision_hash_preimage_v2(stored)

        assert set(preimage["policies"][0]) == {
            "provision_key",
            "retained",
            "discard_reason",
            "selected_rule_ids",
            "total_rules",
        }
        assert "rules" not in preimage
        assert stored.considered[0].provision_key == "older-policy"

    def test_a_rule_receipt_is_not_parseable_as_a_policy_receipt(self) -> None:
        """Fail closed, rather than read an absent field as a negative."""

        import pytest as _pytest
        from policy_platform.contracts.case_decision import CaseDecisionEnvelopeV2

        rule_receipt = _rule_envelope().model_dump(mode="json")

        with _pytest.raises(Exception):
            CaseDecisionEnvelopeV2.model_validate(rule_receipt)

    def test_the_authoritative_reader_accepts_historical_and_rule_receipts(self) -> None:
        from policy_platform.contracts.case_decision import (
            CaseDecisionRuleEnvelope,
            validate_receipt,
        )

        rule = validate_receipt(_rule_envelope().model_dump(mode="json"))
        assert isinstance(rule, CaseDecisionRuleEnvelope)

        historical = validate_receipt(
            {
                "schema_version": "case_decision_v1",
                "decision_id": "decision-1",
                "correlation_id": "correlation-1",
                "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
                "caller": {
                    "principal_identity": "agent-1",
                    "principal_role": "viewer",
                    "authentication_source": "subscription-key",
                },
                "request": {
                    "scenario": "a question",
                    "scenario_hash": "h" * 64,
                    "scope": "project",
                    "reasoning_effort_requested": "medium",
                    "received_at": "2026-01-01T00:00:00Z",
                },
                "retrieval": {"status": "narrowed"},
                "decision_status": "not_evaluated",
                "decision": {"status": "not_evaluated"},
                "trace": {},
                "decision_hash": "b" * 64,
                "hash_basis": "case_decision_v1",
                "receipt_url": "/api/policy-decisions/decision-1",
                "decided_at": "2026-01-01T00:00:00Z",
                "latency_ms": 10,
            }
        )
        assert isinstance(historical, CaseDecisionEnvelope)

    @pytest.mark.parametrize(
        "payload",
        [
            {"schema_version": "case_decision_unknown"},
            {
                **_rule_envelope().model_dump(mode="json"),
                "schema_version": "case_decision_v2",
            },
        ],
    )
    def test_the_authoritative_reader_rejects_unknown_or_mixed_receipts(
        self, payload: dict
    ) -> None:
        from policy_platform.contracts.case_decision import validate_receipt

        with pytest.raises((ValidationError, ValueError)):
            validate_receipt(payload)


class TestTheLightRuleProjectionKeepsTheSeparation:
    def test_the_light_rule_envelope_has_no_policies_property(self) -> None:
        from policy_platform.contracts.case_decision_light import (
            CaseDecisionLightEnvelope,
            CaseDecisionRuleLightEnvelope,
        )

        assert "policies" not in CaseDecisionRuleLightEnvelope.model_fields
        assert "rules" in CaseDecisionRuleLightEnvelope.model_fields
        # And the policy light envelope is untouched.
        assert "policies" in CaseDecisionLightEnvelope.model_fields
        assert "rules" not in CaseDecisionLightEnvelope.model_fields

    def test_the_light_rule_envelope_answers_under_its_own_version(self) -> None:
        from policy_platform.contracts.case_decision_light import (
            SCHEMA_VERSION,
            SCHEMA_VERSION_RULE,
        )

        assert SCHEMA_VERSION_RULE == "case_decision_rule_light_v1"
        assert SCHEMA_VERSION_RULE != SCHEMA_VERSION

    def test_a_light_rule_citation_traces_to_a_rule_not_a_policy(self) -> None:
        from policy_platform.contracts.case_decision_light import LightRuleCitationRef

        assert "policy" not in LightRuleCitationRef.model_fields
        assert "rule" in LightRuleCitationRef.model_fields

    @staticmethod
    def _payload(**overrides) -> dict:
        data = {
            "schema_version": "case_decision_rule_light_v1",
            "response_type": "informational",
            "decision_id": "decision-1",
            "correlation_id": "correlation-1",
            "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
            "request": {
                "scenario": "a question",
                "scenario_hash": "h" * 64,
                "rule_retrieval": True,
            },
            "asked": {"information_requested": True, "verdict_requested": False},
            "outcome": {"information": "answered", "verdict": "not_requested"},
            "information": {"status": "answered", "answer": "The rule states a limit."},
            "retrieval": {"status": "narrowed", "retrieval_mode": "rule"},
            "rules": [
                {
                    "rule_id": "R-1",
                    "provision_key": "4.1",
                    "provision_id": "provision-1",
                }
            ],
            "citations": [
                {
                    "rule_id": "R-1",
                    "rule": {"rule_id": "R-1", "provision_key": "4.1"},
                    "source": {"state": "quoted", "text": "A source sentence."},
                    "serves": ["information"],
                }
            ],
            "trace": {},
            "decision_hash": "b" * 64,
            "hash_basis": "case_decision_rule_v1",
            "receipt_url": "/api/policy-decisions/decision-1",
            "latency_ms": 10,
        }
        data.update(overrides)
        return data

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("hash_basis", "anything"),
            ("policies", []),
            ("request", {
                "scenario": "a question",
                "scenario_hash": "h" * 64,
                "rule_retrieval": False,
            }),
            ("retrieval", {"status": "narrowed", "retrieval_mode": "policy"}),
        ],
    )
    def test_light_rule_receipts_reject_policy_or_unknown_shapes(
        self, field: str, value: object
    ) -> None:
        from policy_platform.contracts.case_decision_light import (
            CaseDecisionRuleLightEnvelope,
        )

        with pytest.raises(ValidationError):
            CaseDecisionRuleLightEnvelope.model_validate(
                self._payload(**{field: value})
            )

    def test_light_rule_citations_reject_a_policy_field(self) -> None:
        from policy_platform.contracts.case_decision_light import (
            CaseDecisionRuleLightEnvelope,
        )

        payload = self._payload()
        payload["citations"][0]["policy"] = {"provision_key": "4.1"}

        with pytest.raises(ValidationError):
            CaseDecisionRuleLightEnvelope.model_validate(payload)

    def test_light_receipt_union_accepts_both_and_rejects_mixed_or_unknown(self) -> None:
        from policy_platform.contracts.case_decision_light import (
            CaseDecisionLightReceipt,
            CaseDecisionRuleLightEnvelope,
        )

        adapter = TypeAdapter(CaseDecisionLightReceipt)
        parsed = adapter.validate_python(self._payload())
        assert isinstance(parsed, CaseDecisionRuleLightEnvelope)

        with pytest.raises(ValidationError):
            adapter.validate_python(
                {**self._payload(), "schema_version": "case_decision_light_unknown"}
            )
        with pytest.raises(ValidationError):
            adapter.validate_python(
                {
                    **self._payload(),
                    "schema_version": "case_decision_light_v1",
                }
            )
