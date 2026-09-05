"""What the rules confer is not the same question as what may be done now.

THE DEFECT

Records can settle that something is conferred — an amount, a duration, an
entitlement — and be entirely silent on whether it may be acted on today, by
whom, or after what step. A reply that answers the first while the second was
asked is not wrong about the records; it is answering a question nobody put, and
it reaches a caller as permission the records never gave.

WHY THE REPLY DECLARES IT

Whether a rule reaches the question is a fact about the *question*, and the
server never sees the question's meaning — only its text and the records. Rule
types cannot decide it either: a record that confers an entitlement carries
perfectly ordinary prescriptive rules, so nothing structural distinguishes
"settles what is conferred" from "settles whether it is approved now". The reply
says which it settled; this module's counterpart in the decision stage compares
that claim against the status the reply chose.

THE TRAP THIS SUITE GUARDS

The obvious repair for a wrongly-approved case is to demand a missing document.
That would put a requirement in the records' mouth that they never state, and it
is the same error a withdrawn evaluation criterion once made from the other
direction. The correct outcome names nothing outstanding.
"""

from __future__ import annotations

import pytest

from policy_platform.infrastructure.assistants.ai_case_plan import (
    CasePlan,
    plan_from_reply,
)


def _reply(**overrides: object) -> dict:
    reply = {
        "status": "answered",
        "answer": "the records confer it",
        "verdict": "allowed",
        "cited_rule_ids": ["R-1"],
        "missing_required_facts": [],
        "declined": False,
        "note": "",
    }
    reply.update(overrides)
    return reply


def test_a_reply_may_say_the_rules_did_not_reach_the_question():
    plan = plan_from_reply(_reply(settles_requested_decision=False))

    assert plan.settles_requested_decision is False


def test_a_reply_may_say_the_rules_did_reach_it():
    plan = plan_from_reply(_reply(settles_requested_decision=True))

    assert plan.settles_requested_decision is True


def test_a_reply_that_says_nothing_has_not_claimed_the_rules_reach_the_question():
    """Absence is not assent, and it is not denial either — it is no claim."""

    assert plan_from_reply(_reply()).settles_requested_decision is None


@pytest.mark.parametrize("value", ["", "false", "no", 0, 1, [], {}, None])
def test_only_a_boolean_is_read_as_a_claim(value: object):
    """A string "false" is not a claim; reading it as one would invent the reply's
    position from a spelling. Anything that is not a boolean is no claim."""

    plan = plan_from_reply(_reply(settles_requested_decision=value))

    assert plan.settles_requested_decision is None


def test_the_claim_cannot_hold_a_sentence():
    """However the reply words its reasoning, the plan carries one boolean."""

    terse = plan_from_reply(_reply(settles_requested_decision=False, answer="no"))
    verbose = plan_from_reply(
        _reply(
            settles_requested_decision=False,
            answer="a much longer explanation of the very same position",
        )
    )

    assert terse.settles_requested_decision == verbose.settles_requested_decision


def test_the_claim_is_independent_of_every_other_plan_member():
    """INVERSION. The same reply with the claim flipped differs in that member
    and in nothing else, so nothing else can be steering it."""

    settled = plan_from_reply(_reply(settles_requested_decision=True))
    unsettled = plan_from_reply(_reply(settles_requested_decision=False))

    assert settled.settles_requested_decision != unsettled.settles_requested_decision
    for member in (
        "status",
        "declined",
        "cited_rule_ids",
        "named_facts",
        "named_verifications",
        "unsettled_reason",
        "states_answer",
        "states_verdict",
        "evidence_dispositions",
    ):
        assert getattr(settled, member) == getattr(unsettled, member)


def test_saying_the_rules_did_not_reach_the_question_names_no_missing_fact():
    """THE TRAP.

    A reply that says the records are silent on the decision must not thereby
    acquire an outstanding fact. Blocking on an invented document is the error
    this correction exists to avoid, not the correction itself.
    """

    plan = plan_from_reply(_reply(settles_requested_decision=False))

    assert plan.named_facts == ()
    assert plan.names_a_fact is False


def test_what_the_records_do_settle_still_survives():
    """PRECISION CONTROL. Partial settlement is reported, never rounded away.

    The reply still composed an answer, and the plan still records that it did.
    A correction that discarded the explanation would replace one silence with
    another.
    """

    plan = plan_from_reply(
        _reply(settles_requested_decision=False, answer="the records confer thirty units")
    )

    assert plan.states_answer is True


def test_a_default_plan_makes_no_claim():
    """MUTATION CONTROL. Remove the field — the pre-fix reply — and the plan
    carries no claim, which is what the decision stage must treat as no assent."""

    assert CasePlan().settles_requested_decision is None


# ---------------------------------------------------------------------------
# The repair itself, at the boundary that owns the status.
# ---------------------------------------------------------------------------

RULES = [
    {
        "rule_id": "R-1",
        "rule_type": "permission",
        "effect": "confers the thing",
        "required_facts": [],
        "evidence_refs": ["S1"],
    }
]
SPANS = {"S1": {"text": "The records confer thirty units.", "page": 1, "section": "1"}}


def _decide(**overrides: object) -> dict:
    from policy_platform.infrastructure.assistants import ai_case_intent

    reply = _reply(**overrides)
    reply.setdefault(
        "evidence_dispositions",
        [{"key": "P", "disposition": "used", "rule_ids": ["R-1"]}],
    )
    return ai_case_intent._decision_from_parsed(
        reply,
        rules=RULES,
        spans=SPANS,
        evidence_keys=frozenset({"P"}),
    )


def test_a_reply_that_did_not_reach_the_question_is_not_returned_as_answered():
    """THE DEFECT, at the boundary. `allowed` becomes an honest non-settlement."""

    from policy_platform.infrastructure.assistants import ai_case_intent

    decision = _decide(settles_requested_decision=False)

    assert decision["status"] == ai_case_intent.NOT_SETTLED_BY_RULES
    assert decision["verdict"] == "", "a verdict must not survive a non-settlement"


def test_the_non_settlement_invents_no_missing_fact():
    """THE TRAP, at the boundary.

    Blocking on a document the records never require would be a different way of
    being wrong. Nothing is named, and the status is not the blocked one.
    """

    from policy_platform.infrastructure.assistants import ai_case_intent

    decision = _decide(settles_requested_decision=False)

    assert decision["status"] != ai_case_intent.MISSING_REQUIRED_FACTS
    assert decision["missing_required_facts"] == []
    assert decision["missing_information"] == []


def test_what_the_records_settle_is_still_explained():
    """PRECISION CONTROL at the boundary: the explanation survives the repair."""

    decision = _decide(
        settles_requested_decision=False, answer="the records confer thirty units"
    )

    assert decision["answer"] == "the records confer thirty units"


def test_a_reply_that_did_reach_the_question_is_still_answered():
    """RECALL CONTROL.

    Without this, the repair could be satisfied by never answering anything —
    which is a different way of never answering.
    """

    from policy_platform.infrastructure.assistants import ai_case_intent

    decision = _decide(settles_requested_decision=True)

    assert decision["status"] == ai_case_intent.ANSWERED
    assert decision["verdict"] == "allowed"


def test_a_reply_that_makes_no_claim_is_left_as_it_was():
    """The repair turns on a stated `false`, never on silence.

    A reply that says nothing is handled by the checks that already existed, so
    this correction cannot quietly become "block everything that did not opt in".
    """

    from policy_platform.infrastructure.assistants import ai_case_intent

    decision = _decide()

    assert decision["status"] == ai_case_intent.ANSWERED
