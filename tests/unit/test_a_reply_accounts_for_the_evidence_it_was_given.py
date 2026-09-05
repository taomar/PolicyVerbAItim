"""A reply accounts for all the evidence, or it does not get to call itself an answer.

The fixtures are invented and mean nothing: an accounting check that could be
steered by what a provision says would not be an accounting check. Non-Latin
identities and an unrelated invented domain appear for the same reason.
"""

from __future__ import annotations

import pytest

from policy_platform.infrastructure.assistants.ai_case_evidence_accounting import (
    ACCOUNTING_INCOMPLETE,
    ACCOUNTING_UNDECLARED,
    ACCOUNTING_UNOWNED,
    ACCOUNTING_UNREASONED,
    ACCOUNTING_UNRECOGNISED,
    account_for_evidence,
)
from policy_platform.infrastructure.assistants.ai_case_plan import (
    DISPOSITION_IRRELEVANT,
    DISPOSITION_USED,
    CasePlan,
    EvidenceDisposition,
    plan_from_reply,
)

RULES = frozenset({"r1", "r2", "r3"})


def _plan(*claims: EvidenceDisposition) -> CasePlan:
    return CasePlan(status="answered", evidence_dispositions=claims)


def _used(key: str, *rule_ids: str) -> EvidenceDisposition:
    return EvidenceDisposition(
        key=key, disposition=DISPOSITION_USED, rule_ids=tuple(rule_ids)
    )


def _set_aside(key: str, *, reasoned: bool = True) -> EvidenceDisposition:
    return EvidenceDisposition(
        key=key, disposition=DISPOSITION_IRRELEVANT, states_reason=reasoned
    )


def _account(plan: CasePlan, keys: set[str]):
    return account_for_evidence(
        plan, evidence_keys=frozenset(keys), available_rule_ids=RULES
    )


def test_a_reply_that_accounts_for_everything_is_complete():
    result = _account(_plan(_used("alpha", "r1"), _set_aside("beta")), {"alpha", "beta"})

    assert result.complete
    assert result.failures == ()
    assert not result.blocks_answer


def test_evidence_the_reply_never_mentions_blocks_the_answer():
    """THE DEFECT. The reply rests on one unit and says nothing about the other."""

    result = _account(_plan(_used("alpha", "r1")), {"alpha", "beta"})

    assert result.blocks_answer
    assert ACCOUNTING_INCOMPLETE in result.failures
    assert result.unaccounted_keys == ("beta",)


def test_a_reply_that_declares_nothing_at_all_blocks_the_answer():
    result = _account(_plan(), {"alpha", "beta"})

    assert result.blocks_answer
    assert result.failures == (ACCOUNTING_UNDECLARED,)
    assert result.unaccounted_keys == ("alpha", "beta")


def test_setting_evidence_aside_is_legitimate_and_stays_legitimate():
    """THE ANTI-CITE-EVERYTHING CONTROL.

    If the repair had been "cite everything", this is the test that would fail.
    One unit carries the answer, two are set aside with reasons, and the reply is
    complete. Precision is preserved; only silence is removed.
    """

    result = _account(
        _plan(_used("alpha", "r1"), _set_aside("beta"), _set_aside("gamma")),
        {"alpha", "beta", "gamma"},
    )

    assert result.complete


def test_evidence_set_aside_without_a_reason_is_not_accounted_for():
    result = _account(
        _plan(_used("alpha", "r1"), _set_aside("beta", reasoned=False)),
        {"alpha", "beta"},
    )

    assert result.blocks_answer
    assert ACCOUNTING_UNREASONED in result.failures
    assert result.unaccounted_keys == ("beta",)


def test_a_used_claim_must_own_a_citation_from_the_closed_rule_set():
    """OWNERSHIP. "I relied on this" without saying through what is not an account."""

    unowned = _account(_plan(_used("alpha")), {"alpha"})
    fabricated = _account(_plan(_used("alpha", "not-a-rule")), {"alpha"})
    owned = _account(_plan(_used("alpha", "r2")), {"alpha"})

    assert unowned.blocks_answer and ACCOUNTING_UNOWNED in unowned.failures
    assert fabricated.blocks_answer, "a citation nobody handed over cannot prove use"
    assert owned.complete


def test_an_invented_disposition_token_is_not_an_account():
    result = _account(
        _plan(EvidenceDisposition(key="alpha", disposition="partially_considered")),
        {"alpha"},
    )

    assert result.blocks_answer
    assert ACCOUNTING_UNRECOGNISED in result.failures


def test_no_evidence_means_nothing_to_account_for():
    """A reply is not asked to account for evidence that does not exist."""

    assert _account(_plan(), set()).complete


def test_evidence_the_reply_invented_cannot_complete_the_account():
    """A disposition for a unit nobody handed over must not fill a real gap."""

    result = _account(_plan(_used("phantom", "r1")), {"alpha"})

    assert result.blocks_answer
    assert result.unaccounted_keys == ("alpha",)


def test_a_repeated_disposition_does_not_let_a_later_entry_overturn_an_earlier_one():
    result = _account(
        _plan(_set_aside("alpha", reasoned=False), _used("alpha", "r1")),
        {"alpha"},
    )

    assert result.blocks_answer, "the first claim stands; a second cannot repair it"


def test_every_way_of_failing_is_reported_not_just_the_first():
    result = _account(
        _plan(_used("alpha"), _set_aside("beta", reasoned=False)),
        {"alpha", "beta", "gamma"},
    )

    assert set(result.failures) == {
        ACCOUNTING_UNOWNED,
        ACCOUNTING_UNREASONED,
        ACCOUNTING_INCOMPLETE,
    }
    assert result.unaccounted_keys == ("alpha", "beta", "gamma")


@pytest.mark.parametrize(
    "carried,set_aside",
    [
        ("berth-allocation", "pilotage-exemption"),
        ("البند-٧", "البند-٩"),
        ("положение-3", "положение-4"),
        ("條款-一", "條款-二"),
        ("グレルビン", "morticle-14"),
    ],
)
def test_the_accounting_is_blind_to_what_the_identity_says(carried: str, set_aside: str):
    complete = _account(
        _plan(_used(carried, "r1"), _set_aside(set_aside)), {carried, set_aside}
    )
    incomplete = _account(_plan(_used(carried, "r1")), {carried, set_aside})

    assert complete.complete
    assert incomplete.blocks_answer
    assert incomplete.unaccounted_keys == (set_aside,)


def test_the_account_follows_the_claims_and_not_the_order():
    """INVERSION. Swap which unit carries the answer; the accounting still holds."""

    first = _account(_plan(_used("alpha", "r1"), _set_aside("beta")), {"alpha", "beta"})
    second = _account(_plan(_set_aside("alpha"), _used("beta", "r1")), {"alpha", "beta"})

    assert first.complete and second.complete


def test_a_reply_is_read_into_dispositions_without_inference():
    """The reader makes no claim the reply did not make."""

    plan = plan_from_reply(
        {
            "status": "answered",
            "evidence_dispositions": [
                {"key": "alpha", "disposition": "USED", "rule_ids": ["r1"]},
                {"key": "beta", "disposition": "irrelevant", "reason": "does not bear"},
                {"key": "", "disposition": "used"},
                {"disposition": "used"},
                "not-a-mapping",
            ],
        }
    )

    assert [claim.key for claim in plan.evidence_dispositions] == ["alpha", "beta"]
    assert plan.evidence_dispositions[0].disposition == DISPOSITION_USED
    assert plan.evidence_dispositions[0].rule_ids == ("r1",)
    assert plan.evidence_dispositions[1].states_reason is True


def test_the_reason_is_presence_and_never_content():
    """Rewording a reason cannot move the decision, because nothing reads it."""

    terse = plan_from_reply(
        {"evidence_dispositions": [{"key": "a", "disposition": "irrelevant", "reason": "no"}]}
    )
    verbose = plan_from_reply(
        {
            "evidence_dispositions": [
                {
                    "key": "a",
                    "disposition": "irrelevant",
                    "reason": "an altogether longer sentence saying the same thing",
                }
            ]
        }
    )

    assert terse.evidence_dispositions == verbose.evidence_dispositions


def test_the_declaration_is_what_makes_the_account_complete():
    """MUTATION CONTROL. Remove the declaration — the pre-fix reply — and it blocks."""

    declared = _account(_plan(_used("alpha", "r1"), _set_aside("beta")), {"alpha", "beta"})
    undeclared = _account(_plan(), {"alpha", "beta"})

    assert declared.complete
    assert undeclared.blocks_answer
