"""Coverage expansion is eligible by property, never by a list of orderings.

THE DEFECT AND WHY IT RECURRED

Coverage expansion spends retention budget that a relevance cut left unspent. The
gate that decided whether it could run named the orderings that do that, and an
ordering absent from the list never reached the expansion however much budget its
cut had left. That happened once already — rule mode was missing — and adding the
missing name fixed the instance while leaving the mechanism intact, so the next
ordering to cut was omitted the same way.

The gate now reads the two facts that make expansion meaningful: a cut was
applied, and budget remains. An ordering added later qualifies by being what it
is rather than by being remembered, which is the only version of this that cannot
regress again.

WHAT THIS DOES NOT CHANGE

No threshold, no budget, no selection limit, no ordering. Eligibility is a
question asked *after* the selection has run, about its own reported outcome.
"""

from __future__ import annotations

import pytest

from policy_platform.infrastructure.assistants.ai_case_project import (
    RETRIEVAL_POLICY_BUDGET,
    coverage_expansion_is_eligible,
)

BUDGET = RETRIEVAL_POLICY_BUDGET


def test_a_cut_that_left_budget_unspent_is_eligible():
    assert coverage_expansion_is_eligible({"semantic_elbow_applied": True}, 1)


def test_no_cut_is_not_eligible():
    """PRECISION CONTROL.

    Where no cut was made the pool already reaches the budget, so there is
    nothing unspent to expand into. An eligibility rule that said yes here would
    be widening retrieval on every request.
    """

    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": False}, 1)
    assert not coverage_expansion_is_eligible({}, 1)


def test_a_cut_with_the_budget_already_spent_is_not_eligible():
    """EXACT-BUDGET CONTROL. At the budget, not merely near it."""

    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": True}, BUDGET)
    assert coverage_expansion_is_eligible({"semantic_elbow_applied": True}, BUDGET - 1)


def test_over_budget_is_not_eligible():
    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": True}, BUDGET + 1)


@pytest.mark.parametrize("selected", range(0, 8))
def test_eligibility_is_exactly_cut_and_room(selected: int):
    """The property in full, over every count either side of the budget."""

    assert coverage_expansion_is_eligible({"semantic_elbow_applied": True}, selected) == (
        selected < BUDGET
    )
    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": False}, selected)


@pytest.mark.parametrize(
    "order",
    [
        "rrf_hybrid_semantic_v1",
        "rule_weighted_rrf_v1",
        "semantic_strong_lead_v1",
        "hybrid_search_order_v1",
        # An ordering that does not exist yet. The point of the property is that
        # it does not need to be added here to be treated correctly.
        "an_ordering_invented_after_this_test_was_written",
        "",
    ],
)
def test_no_ordering_can_change_the_answer(order: str):
    """ORDER-AGNOSTICISM — the regression guard for the original defect.

    Whatever the selection called its ordering, eligibility follows the cut and
    the budget. If anyone reintroduces an enumeration, this fails.
    """

    cut = {"semantic_elbow_applied": True, "direct_policy_order": order}
    flat = {"semantic_elbow_applied": False, "direct_policy_order": order}

    assert coverage_expansion_is_eligible(cut, 1)
    assert not coverage_expansion_is_eligible(flat, 1)


def test_the_strong_lead_case_that_was_previously_excluded_is_now_eligible():
    """THE DEFECT ITSELF, as a named case.

    A lead strong enough to keep one policy of the budget is still a cut, and it
    left the rest of the budget unspent. Under the enumeration this was excluded
    and the unspent budget was unreachable.
    """

    strong_lead = {
        "semantic_elbow_applied": True,
        "direct_policy_order": "semantic_strong_lead_v1",
    }

    assert coverage_expansion_is_eligible(strong_lead, 1)


def test_the_cut_flag_is_what_makes_it_eligible():
    """MUTATION CONTROL. Drop the cut and eligibility must disappear."""

    with_cut = {"semantic_elbow_applied": True}
    without_cut = {key: value for key, value in with_cut.items() if key != "semantic_elbow_applied"}

    assert coverage_expansion_is_eligible(with_cut, 1)
    assert not coverage_expansion_is_eligible(without_cut, 1)


def test_a_non_boolean_cut_report_is_read_as_its_truth_and_not_its_spelling():
    """INVERSION over the flag's own representation.

    The selector reports a boolean. Anything falsey means no cut was recorded,
    and nothing here reads a string as a claim.
    """

    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": None}, 1)
    assert not coverage_expansion_is_eligible({"semantic_elbow_applied": 0}, 1)
    assert coverage_expansion_is_eligible({"semantic_elbow_applied": 1}, 1)


def test_the_gate_reads_no_identity_at_all():
    """The precision report carries corpus-shaped values on other keys. None of
    them may reach this decision — so a report full of them answers identically
    to one carrying only the two facts."""

    bare = {"semantic_elbow_applied": True}
    noisy = {
        "semantic_elbow_applied": True,
        "direct_policy_order": "rrf_hybrid_semantic_v1",
        "semantic_candidates": 40,
        "semantic_selected": 1,
        "semantic_cutoff_score": 7.77,
        "semantic_largest_gap": 0.41,
        "precision_mode": "direct_policy_rrf_elbow_rule_rescue_v1",
    }

    assert coverage_expansion_is_eligible(bare, 1) == coverage_expansion_is_eligible(noisy, 1)
