"""Evidence the answer held is accounted for, one way or the other.

THE DEFECT THIS CLOSES

Retrieval keeping a policy and the answer resting on it are two different events,
and only the first was written down. A policy could be carried into the
evaluation, contribute nothing, and leave a receipt indistinguishable from one
where it had been weighed and found not to apply. A reader could not tell the
difference, and neither could a test.

WHAT IS NOT CLAIMED

`uncited` is not a defect and this suite never asserts that it is. Retrieval
deliberately keeps more than one answer needs, and a contract that forced every
retained policy into the citations would buy completeness with precision — the
degenerate repair. The controls below exist to prove that repair was *not* made:
held-and-unused remains legal, and only remains *silent* becomes impossible.

WHY THE FIXTURES LOOK LIKE NOTHING

The disposition is derived from identity alone — does a citation resolve to this
provision key — so it cannot read a heading, a question or a corpus. The fixtures
are therefore invented: nonsense keys, an unrelated invented domain, and a
non-Latin script, none of which the mechanism can distinguish from each other.
That is the property under test.
"""

from __future__ import annotations

import pytest

from policy_platform.application.policy_case_decision import _apply_composition
from policy_platform.contracts.case_decision import (
    COMPOSITION_CITED,
    COMPOSITION_UNCITED,
    CitationSourceRef,
    MergedCitationRef,
    PolicyRef,
    _sealed_policy_entry,
)


def _policy(key: str, *, retained: bool = True) -> PolicyRef:
    return PolicyRef(provision_key=key, retained=retained)


def _citation(rule_id: str, policy_key: str | None) -> MergedCitationRef:
    return MergedCitationRef(
        rule_id=rule_id,
        policy=None if policy_key is None else PolicyRef(provision_key=policy_key),
        source=CitationSourceRef(state="quoted", text="x"),
        serves=["verdict"],
    )


def test_a_policy_the_answer_rested_on_is_recorded_as_cited():
    considered = [_policy("alpha")]

    _apply_composition(considered, [_citation("r1", "alpha")])

    assert considered[0].composition == COMPOSITION_CITED


def test_a_policy_that_was_held_and_never_used_says_so():
    """The defect, in one assertion.

    Before this field the two policies below produced identical receipts. Now the
    one the answer never touched says which of the two it is.
    """

    considered = [_policy("alpha"), _policy("beta")]

    _apply_composition(considered, [_citation("r1", "alpha")])

    assert considered[0].composition == COMPOSITION_CITED
    assert considered[1].composition == COMPOSITION_UNCITED


def test_a_policy_retrieval_discarded_gets_no_disposition():
    """Not kept and kept-but-unused are different facts and stay different.

    Writing `uncited` on a discarded policy would merge them, which would defeat
    the only thing this field is for.
    """

    considered = [_policy("alpha", retained=False)]

    _apply_composition(considered, [])

    assert considered[0].composition is None


def test_holding_evidence_without_using_it_remains_legal():
    """THE ANTI-CITE-EVERYTHING CONTROL.

    If the repair had been "every retained policy must be cited", this would be
    the test that failed. The contract records the disposition; it never demands
    a particular one. A precision-preserving answer that rests on one of three
    retained policies is valid, and stays valid.
    """

    considered = [_policy("alpha"), _policy("beta"), _policy("gamma")]

    _apply_composition(considered, [_citation("r1", "alpha")])

    dispositions = [ref.composition for ref in considered]
    assert dispositions.count(COMPOSITION_CITED) == 1
    assert dispositions.count(COMPOSITION_UNCITED) == 2
    assert all(disposition is not None for disposition in dispositions)


def test_every_retained_policy_carries_a_disposition_whatever_the_answer_did():
    """The completeness property itself, stated over an arbitrary split."""

    considered = [_policy(f"k{index}") for index in range(6)]

    _apply_composition(considered, [_citation("r1", "k0"), _citation("r2", "k4")])

    assert all(ref.composition is not None for ref in considered)
    assert {ref.provision_key for ref in considered if ref.composition == COMPOSITION_CITED} == {
        "k0",
        "k4",
    }


def test_the_disposition_follows_the_citations_and_not_the_order():
    """INVERSION CONTROL.

    The same two policies with the citation moved to the other one must invert
    the dispositions. A mechanism that had latched onto position — first is used,
    rest are not — would pass the earlier tests and fail this one.
    """

    first = [_policy("alpha"), _policy("beta")]
    _apply_composition(first, [_citation("r1", "alpha")])

    second = [_policy("alpha"), _policy("beta")]
    _apply_composition(second, [_citation("r1", "beta")])

    assert [ref.composition for ref in first] == [COMPOSITION_CITED, COMPOSITION_UNCITED]
    assert [ref.composition for ref in second] == [COMPOSITION_UNCITED, COMPOSITION_CITED]


@pytest.mark.parametrize(
    "used,held",
    [
        # An invented domain with no relation to any corpus this has been run on.
        ("berth-allocation", "pilotage-exemption"),
        # Non-Latin identities. The mechanism compares strings for equality and
        # has no notion of script, which is what this proves.
        ("البند-٧", "البند-٩"),
        ("положение-3", "положение-4"),
        ("條款-一", "條款-二"),
        # A key that is not word-like at all.
        ("グレルビン", "morticle-14"),
    ],
)
def test_the_disposition_is_blind_to_what_the_identity_says(used: str, held: str):
    considered = [_policy(used), _policy(held)]

    _apply_composition(considered, [_citation("r1", used)])

    assert considered[0].composition == COMPOSITION_CITED
    assert considered[1].composition == COMPOSITION_UNCITED


def test_a_citation_that_resolved_to_no_policy_cites_nothing():
    """A citation without a resolved policy cannot mark anything as used.

    It must also not crash the derivation, and it must not silently mark the
    first retained policy — which is what an implementation that skipped the
    `None` check would do.
    """

    considered = [_policy("alpha")]

    _apply_composition(considered, [_citation("r1", None)])

    assert considered[0].composition == COMPOSITION_UNCITED


def test_the_disposition_is_sealed_when_present():
    cited = _sealed_policy_entry(PolicyRef(provision_key="k", retained=True, composition=COMPOSITION_CITED))
    uncited = _sealed_policy_entry(
        PolicyRef(provision_key="k", retained=True, composition=COMPOSITION_UNCITED)
    )

    assert cited["composition"] == COMPOSITION_CITED
    assert uncited["composition"] == COMPOSITION_UNCITED
    assert cited != uncited, (
        "held-and-used and held-and-unused must not seal identically, or the "
        "account of what the answer rested on could be rewritten after the fact"
    )


def test_a_receipt_written_before_the_disposition_existed_seals_exactly_as_before():
    """BACKWARD-COMPATIBILITY CONTROL.

    Every receipt ever issued carries no disposition. If the key were written
    unconditionally their preimages would all change and every stored decision
    hash would stop verifying. The key is therefore written only when there is
    something to seal, exactly as the verdict's verification requirements are.
    """

    legacy = _sealed_policy_entry(PolicyRef(provision_key="k", retained=True))

    assert "composition" not in legacy
    assert legacy == {
        "provision_key": "k",
        "retained": True,
        "discard_reason": None,
        "selected_rule_ids": None,
        "total_rules": None,
    }


def test_the_derivation_is_what_makes_the_disposition_true():
    """MUTATION CONTROL.

    Skipping the derivation is the mutation: it is what the code did before this
    fix. The retained-but-unused policy then carries no disposition at all, and
    the assertion that catches that must be the one doing the work — if this test
    passes with the derivation removed, nothing here is load-bearing.
    """

    unmutated = [_policy("alpha"), _policy("beta")]
    _apply_composition(unmutated, [_citation("r1", "alpha")])

    mutated = [_policy("alpha"), _policy("beta")]  # derivation deliberately not run

    assert unmutated[1].composition == COMPOSITION_UNCITED
    assert mutated[1].composition is None
    assert _sealed_policy_entry(unmutated[1]) != _sealed_policy_entry(mutated[1])
