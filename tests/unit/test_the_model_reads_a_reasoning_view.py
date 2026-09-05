"""Measured model views remain separate from the served policy record.

WHY THIS FILE EXISTS

The flattened `llm_reasoning_v2` view is retained as analysis after it failed the
scenario gate. Serving uses the complete `grounding_projection_v1`; the analyzed
view must therefore remain pure, lossless in the fields it claims to carry, and
strictly smaller without becoming reachable from a decision path.

**Nothing operative may be lost.** A view that quietly dropped a rule, or a
rule's own sentence, or the exception that carves it back, would produce answers
that are wrong in a way no downstream check catches — the citation would still
resolve, the seal would still verify, and the reasoning would have been done
against less than the policy says.

**Nothing may be mutated.** The full original records are what
`_checked_citation_ids`, `_citation_source`, `_citations`, the selector catalogue
and receipt construction all read afterwards. A builder that edited a rule in
place to flatten it would corrupt the evidence trail while looking like a
formatting change.

**The retention gate may not move.** What fits in one grounded pass is a property
of the retained set, and it is measured on the served record. If a cheaper
encoding became the budget, the retained set would silently widen and every
receipt's retained/discarded split would change with a transport decision nobody
asked for.

Nothing here names a corpus: the policy, its headings and its sentences are
invented, and the assertions are relationships rather than literals.
"""
from __future__ import annotations

import copy
import json

from policy_platform.infrastructure.assistants import ai_case_intent
from policy_platform.infrastructure.projection.llm_reasoning_view import (
    REASONING_VIEW,
    build_reasoning_view,
)
from policy_platform.infrastructure.projection.policy_case_payload import to_compact


_SENTENCE_ONE = (
    "A member of staff who has completed twelve months of continuous service is "
    "entitled to twenty working days of paid leave in each leave year."
)
_SENTENCE_TWO = (
    "Leave not taken by the end of the leave year lapses, except where the member "
    "of staff was prevented from taking it by an operational instruction."
)


def _record() -> dict:
    """One policy in the served shape, with every part a rule can carry.

    Written out rather than built from the projector so this file tests the
    *view*, not the projector: a change to how a record is produced should fail
    the projector's own tests, and a change to what the view keeps should fail
    here.
    """

    return {
        "projection": "grounding_projection_v1",
        "representation": "canonical",
        "envelope": {
            "schema_version": "canonical-policy-v1",
            "policy_set_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "provision_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "provision_key": "PART-3-LEAVE",
            "heading_path": ["Staff handbook", "Part 3", "Annual leave"],
            "policy_version_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "document_version_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "effective_from": "2024-01-01",
            "effective_to": None,
        },
        "spans": {
            "span-one": {
                "document_version_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                "text": _SENTENCE_ONE,
                "clause_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                "search_document_id": "dddddddd_eeeeeeee",
                "source_hash": "0123456789abcdef",
                "page": 7,
                "section": "3.1",
                "start_offset": 1024,
                "end_offset": 1180,
            },
            "span-two": {
                "document_version_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                "text": _SENTENCE_TWO,
                "clause_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                "search_document_id": "dddddddd_ffffffff",
                "source_hash": "fedcba9876543210",
                "page": 8,
                "section": "3.2",
                "start_offset": 2048,
                "end_offset": 2200,
            },
            "span-supporting": {
                "document_version_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                "clause_id": "99999999-9999-4999-8999-999999999999",
                "search_document_id": "dddddddd_99999999",
                "source_hash": "aaaa000011112222",
                "page": 9,
                "section": "3.3",
                "start_offset": None,
                "end_offset": None,
            },
        },
        "facts": {
            "continuous_service": {
                "name": "continuous_service",
                "source_phrase": "twelve months of continuous service",
                "data_type": "duration",
            },
            "leave_days": {
                "name": "leave_days",
                "source_phrase": "twenty working days",
                "data_type": "quantity",
            },
            "unused_leave": {
                "name": "unused_leave",
                "source_phrase": "Leave not taken by the end of the leave year",
                "data_type": None,
            },
        },
        "rules": [
            {
                "rule_id": "R-LEAVE-ENTITLEMENT",
                "rule_revision": 4,
                "rule_type": "entitlement",
                "evaluation_mode": "deterministic",
                "ambiguity_status": "none",
                "modality": "is entitled to",
                "effect": {"type": "PERMIT", "action": "grant paid leave"},
                "attributes": {
                    "applies": [
                        {
                            "attribute": "staff.continuous_service",
                            "fact_ref": "continuous_service",
                            "data_type": "duration",
                        }
                    ],
                    "outcome": [
                        {
                            "attribute": "leave.days",
                            "fact_ref": "leave_days",
                            "data_type": "quantity",
                        }
                    ],
                },
                "facts": [
                    {"ref": "continuous_service", "roles": ["condition"]},
                    {"ref": "leave_days", "roles": ["outcome"]},
                ],
                "required_facts": [
                    {"name": "continuous_service", "data_type": "duration", "required": True}
                ],
                "evidence_refs": ["span-one", "span-supporting"],
                "dmn_status": "mapped",
                "related_rule_ids": ["R-LEAVE-LAPSE"],
                "scope": {"personas": ["member of staff"]},
            },
            {
                "rule_id": "R-LEAVE-LAPSE",
                "rule_revision": 2,
                "rule_type": "obligation",
                "evaluation_mode": "ai_ready",
                "ambiguity_status": "non_blocking",
                "effect": {"type": "DENY", "action": "carry leave forward"},
                "attributes": {
                    "applies": [
                        {
                            "attribute": "leave.unused",
                            "fact_ref": "unused_leave",
                            "data_type": None,
                        },
                        {
                            "attribute": "leave.year_end",
                            "text": "the end of the leave year",
                            "data_type": "date",
                        },
                    ],
                    "outcome": [],
                },
                "facts": [{"ref": "unused_leave", "roles": ["condition"]}],
                "required_facts": [],
                "evidence_refs": ["span-two"],
                "dmn_status": "not_applicable",
                "dmn_missing": ["no_decision_table"],
                "is_explicit_override": True,
                "supersedes_rule_ids": ["R-LEAVE-OLD"],
                "tags": ["leave"],
                "effective_from": "2025-04-01",
                "exceptions": [
                    {
                        "exception_id": "X-OPERATIONAL",
                        "description": "prevented from taking it by an operational instruction",
                        "limit_value": None,
                        "limit_unit": None,
                    }
                ],
                "advice": [{"advice_id": "A-1", "text": "raise it with the line manager early"}],
            },
        ],
    }


def _policies_view() -> list[dict]:
    """What the retrieval layer already pairs for the gather."""

    record = _record()
    return [
        {
            "policy": {
                "provision_id": record["envelope"]["provision_id"],
                "provision_key": record["envelope"]["provision_key"],
                "heading_path": record["envelope"]["heading_path"],
            },
            "record": record,
        }
    ]


def _rules(view: dict) -> dict[str, dict]:
    return {rule["rule_id"]: rule for rule in view["policies"][0]["rules"]}


# ── what it keeps ────────────────────────────────────────────────────


class TestNothingOperativeIsLost:
    def test_every_selected_rule_is_present_in_order(self) -> None:
        view = build_reasoning_view(_policies_view())

        assert [rule["rule_id"] for rule in view["policies"][0]["rules"]] == [
            "R-LEAVE-ENTITLEMENT",
            "R-LEAVE-LAPSE",
        ]

    def test_each_rule_carries_its_own_source_sentence_verbatim(self) -> None:
        """The one thing this platform may never alter, read without a join.

        On the served record the sentence lives once in `spans` and the rule
        points at it by id. Here it is on the rule, byte-for-byte — not a
        summary, not a prefix, not re-wrapped.
        """

        rules = _rules(build_reasoning_view(_policies_view()))

        assert rules["R-LEAVE-ENTITLEMENT"]["source"] == _SENTENCE_ONE
        assert rules["R-LEAVE-LAPSE"]["source"] == _SENTENCE_TWO

    def test_the_policys_heading_and_effective_dates_are_carried_once(self) -> None:
        policy = build_reasoning_view(_policies_view())["policies"][0]

        assert policy["policy"] == "Staff handbook > Part 3 > Annual leave"
        assert policy["provision_key"] == "PART-3-LEAVE"
        assert policy["effective_from"] == "2024-01-01"

    def test_the_operative_semantics_of_each_rule_survive(self) -> None:
        rules = _rules(build_reasoning_view(_policies_view()))
        entitlement = rules["R-LEAVE-ENTITLEMENT"]
        lapse = rules["R-LEAVE-LAPSE"]

        assert entitlement["rule_type"] == "entitlement"
        assert entitlement["modality"] == "is entitled to"
        assert entitlement["effect"] == {"type": "PERMIT", "action": "grant paid leave"}
        assert entitlement["scope"] == {"personas": ["member of staff"]}
        assert entitlement["related_rule_ids"] == ["R-LEAVE-LAPSE"]
        assert entitlement["required_facts"] == [
            {"name": "continuous_service", "data_type": "duration", "required": True}
        ]

        assert lapse["is_explicit_override"] is True
        assert lapse["supersedes_rule_ids"] == ["R-LEAVE-OLD"]
        assert lapse["tags"] == ["leave"]
        assert lapse["exceptions"][0]["description"] == (
            "prevented from taking it by an operational instruction"
        )
        assert lapse["advice"][0]["text"] == "raise it with the line manager early"

    def test_a_date_that_departs_from_the_policys_is_carried_and_one_that_agrees_is_not(
        self,
    ) -> None:
        """Same rule the served record follows: an override, never a restatement."""

        rules = _rules(build_reasoning_view(_policies_view()))

        assert rules["R-LEAVE-LAPSE"]["effective_from"] == "2025-04-01"
        assert "effective_from" not in rules["R-LEAVE-ENTITLEMENT"]

    def test_only_a_non_default_ambiguity_marker_is_carried(self) -> None:
        """A marker present on every rule is not a marker."""

        rules = _rules(build_reasoning_view(_policies_view()))

        assert "ambiguity" not in rules["R-LEAVE-ENTITLEMENT"]
        assert rules["R-LEAVE-LAPSE"]["ambiguity"] == "non_blocking"

    def test_facts_and_attributes_are_read_out_rather_than_pointed_at(self) -> None:
        """The join the served record needs, done once here instead of by the model."""

        rules = _rules(build_reasoning_view(_policies_view()))
        entitlement = rules["R-LEAVE-ENTITLEMENT"]

        assert entitlement["facts"] == [
            {
                "name": "continuous_service",
                "phrase": "twelve months of continuous service",
                "data_type": "duration",
                "roles": ["condition"],
            },
            {
                "name": "leave_days",
                "phrase": "twenty working days",
                "data_type": "quantity",
                "roles": ["outcome"],
            },
        ]
        assert entitlement["applies"] == [
            {
                "attribute": "staff.continuous_service",
                "text": "twelve months of continuous service",
                "data_type": "duration",
            }
        ]

        lapse = rules["R-LEAVE-LAPSE"]
        # An attribute that names no fact keeps its own verbatim text, and one
        # whose phrase named no kind carries no `data_type` rather than a null.
        assert lapse["applies"] == [
            {
                "attribute": "leave.unused",
                "text": "Leave not taken by the end of the leave year",
            },
            {
                "attribute": "leave.year_end",
                "text": "the end of the leave year",
                "data_type": "date",
            },
        ]

    def test_an_empty_required_facts_list_is_still_stated(self) -> None:
        """`[]` means the rule's test is words, not named quantities."""

        rules = _rules(build_reasoning_view(_policies_view()))

        assert rules["R-LEAVE-LAPSE"]["required_facts"] == []


# ── what it drops ────────────────────────────────────────────────────


class TestOnlyTraceOnlyFieldsAreDropped:
    def test_no_provenance_metadata_reaches_the_model(self) -> None:
        """Each of these is a fact about *retracing* a decision, not making one.

        Asserted over the serialised view rather than key by key, because the
        risk is a value surviving anywhere in the structure — nested under a
        rule, under a policy, or in a dictionary that was carried wholesale.
        """

        serialised = to_compact(build_reasoning_view(_policies_view()))

        for absent in (
            "grounding_projection_v1",
            "canonical",
            "schema_version",
            "policy_set_id",
            "provision_id",
            "policy_version_id",
            "document_version_id",
            "clause_id",
            "search_document_id",
            "source_hash",
            "evidence_refs",
            "span-one",
            "rule_revision",
            "evaluation_mode",
            "dmn_status",
            "dmn_missing",
            "start_offset",
            "end_offset",
        ):
            assert absent not in serialised, f"{absent} reached the model transport"

    def test_the_page_and_section_of_a_span_do_not_travel(self) -> None:
        view = build_reasoning_view(_policies_view())
        serialised = json.dumps(view, ensure_ascii=False)

        assert '"page"' not in serialised
        assert '"section"' not in serialised

    def test_the_view_names_itself_once_instead_of_per_policy(self) -> None:
        view = build_reasoning_view(_policies_view())

        assert view["view"] == REASONING_VIEW
        assert to_compact(view).count(REASONING_VIEW) == 1


class TestTheServedRecordIsNotTouched:
    def test_building_the_view_mutates_nothing(self) -> None:
        """The originals are what every downstream check still reads."""

        policies_view = _policies_view()
        before = copy.deepcopy(policies_view)

        build_reasoning_view(policies_view)

        assert policies_view == before


class TestTheModelTransportIsMateriallySmaller:
    def test_it_is_a_fraction_of_the_served_records_size(self) -> None:
        """Measured on the same serialisation both sides use.

        A ratio rather than a byte count, because the absolute size is a
        property of this fixture and the saving is a property of the shape.
        """

        policies_view = _policies_view()
        served = len(to_compact({"policies": policies_view}))
        model = len(to_compact(build_reasoning_view(policies_view)))

        assert model < served
        assert model < served * 0.75, (
            f"the model transport saved little: {model} against {served}"
        )


# ── the boundary that must not move ──────────────────────────────────


class TestTheRetentionGateStillMeasuresTheServedRecord:
    def test_the_oversize_refusal_is_taken_over_the_projection_not_the_view(self) -> None:
        """A cheaper encoding must not admit a policy the previous one refused.

        The ceiling is dropped to just under the served record's size and just
        over the model view's. If the gate had moved to the model view this
        would answer; because it did not, it refuses — which is the behaviour a
        stored receipt's retained/discarded split depends on.
        """

        policies_view = _policies_view()
        served = len(to_compact({"policies": policies_view}))
        model = len(to_compact(build_reasoning_view(policies_view)))
        assert model < served, "this fixture cannot tell the two gates apart"

        records = [
            {"policy": entry["policy"], "payload": entry["record"]}
            for entry in policies_view
        ]

        import asyncio
        from unittest.mock import patch

        with patch.object(ai_case_intent, "_MAX_RECORD_CHARS", served - 1):
            result = asyncio.run(
                ai_case_intent.answer_informational_over_policies(
                    records, scenario="how much leave is there"
                )
            )

        assert result["status"] == ai_case_intent.DECLINED
        assert result["grounding"]["oversize"] is True
        assert result["citations"] == []

    def test_serving_uses_the_complete_v1_record_after_the_views_failed_the_gate(self) -> None:
        """Measured views stay available for analysis and never reach a decision."""

        policies_view = _policies_view()
        records = [
            {"policy": entry["policy"], "payload": entry["record"]}
            for entry in policies_view
        ]

        captured: dict = {}

        async def _chat_json(system, user, **kwargs):
            captured["user"] = user
            return {"bears": True, "answer": "twenty days", "cited_rule_ids": ["R-LEAVE-ENTITLEMENT"]}

        import asyncio
        from unittest.mock import patch

        with patch.object(ai_case_intent, "_chat_json", _chat_json):
            result = asyncio.run(
                ai_case_intent.answer_informational_over_policies(
                    records, scenario="how much leave is there"
                )
            )

        assert result["status"] == ai_case_intent.ANSWERED
        # The verbatim sentence is still what a citation resolves to, read from
        # the untouched record rather than from the transport.
        assert result["citations"][0]["source"]["text"] == _SENTENCE_ONE

        assert "grounding_projection_v1" in captured["user"]
        assert "evidence_refs" in captured["user"]
        assert "facts" in captured["user"]
        assert "attributes" in captured["user"]
        assert "search_document_id" in captured["user"]
        assert "source_hash" in captured["user"]
        assert REASONING_VIEW not in captured["user"]
        assert _SENTENCE_ONE in captured["user"]
