"""A re-read row is checked, not excused.

WHY THIS FILE EXISTS

`table_cell_join` builds a row's text with a separator that is not in the
source, so `verify_element_text` reports such a row *unprovable*: it cannot be
rebuilt from its fragments by any deterministic rule. That is honest, and it is
also a blind spot -- 98 rows of one real document sit in it.

A row whose reading order was recovered from the rendered page is the worst
possible thing to put in that blind spot. It is the one kind of text that did
*not* come straight from the parser, so it is the one that most needs proving,
and "we cannot check this" would have been exactly the wrong answer. Declaring
`visual_reading_order` and letting it fall into the unprovable set would have
produced a fidelity report with no failures that had examined nothing.

So the recovery carries its own provenance: the cells the parser produced, and a
permutation over their characters. Replaying it reproduces the text. Two
properties follow, and they are what these tests pin:

  * a character that was not in the parser's cells cannot appear in the result,
    because the only thing the replay reads is an index into them;
  * a character that was dropped, or used twice, breaks the permutation.

A model that translated, invented or omitted anything therefore cannot be
represented in this shape at all.
"""

from __future__ import annotations

from policy_platform.contracts.canonical_document import (
    CanonicalDocument,
    CanonicalElement,
    ReadingOrderRecovery,
)
from policy_platform.infrastructure.ingestion.canonical_fidelity import (
    replay_reading_order,
    verify_element_text,
)

#: Two cells whose characters a parser interleaved. Invented, and about nothing:
#: the property is a property of the mechanism, not of any document.
SOURCE_CELLS = ["Oa", "nb"]
#: The same four characters, regrouped as the page prints them.
RECOVERED_TEXT = "On | ab"
ORDER = [0, 2, 1, 3]
CELL_LENGTHS = [2, 2]

#: The same row with a separator in the parser's cells and a separator in the
#: recovered text. `order` claims the printed characters; `spacing` records the
#: offset the replay fills instead of reading one.
SPACED_CELLS = ["O a", "nb"]
SPACED_TEXT = "On | a b"
SPACED_ORDER = [0, 3, 2, 4]
SPACED_LENGTHS = [2, 3]
SPACING = [3]


def _spaced(
    *,
    text: str = SPACED_TEXT,
    order: list[int] | None = None,
    cell_lengths: list[int] | None = None,
    spacing: list[int] | None = None,
) -> CanonicalElement:
    return CanonicalElement(
        element_id="E000001",
        element_type="table_row",
        logical_order=0,
        text=text,
        transformations=["table_cell_join", "visual_reading_order"],
        reading_order=ReadingOrderRecovery(
            source_cells=list(SPACED_CELLS),
            cell_lengths=list(SPACED_LENGTHS if cell_lengths is None else cell_lengths),
            order=list(SPACED_ORDER if order is None else order),
            spacing=list(SPACING if spacing is None else spacing),
        ),
    )


def _element(
    *,
    text: str = RECOVERED_TEXT,
    order: list[int] | None = None,
    cell_lengths: list[int] | None = None,
    cells: list[str] | None = None,
    with_provenance: bool = True,
) -> CanonicalElement:
    recovery = (
        ReadingOrderRecovery(
            source_cells=list(SOURCE_CELLS if cells is None else cells),
            cell_lengths=list(CELL_LENGTHS if cell_lengths is None else cell_lengths),
            order=list(ORDER if order is None else order),
        )
        if with_provenance
        else None
    )
    return CanonicalElement(
        element_id="E000001",
        element_type="table_row",
        logical_order=0,
        text=text,
        transformations=["table_cell_join", "visual_reading_order"],
        reading_order=recovery,
    )


def _document(element: CanonicalElement) -> CanonicalDocument:
    return CanonicalDocument(
        document_id="D1", page_count=1, pages=[], elements=[element], parser="test"
    )


# --------------------------------------------------------------------------
# It is verified, not excused
# --------------------------------------------------------------------------


def test_a_recovered_row_is_verified_rather_than_counted_unprovable():
    report = verify_element_text(_document(_element()))

    assert report.verified == 1
    assert report.failures == []
    assert report.unprovable == [], (
        "a recovered row was excused as unprovable, which is the blind spot this "
        "provenance exists to close"
    )


def test_the_replay_reproduces_the_text_exactly():
    assert replay_reading_order(_element()) == RECOVERED_TEXT


# --------------------------------------------------------------------------
# Nothing can be added, dropped, or used twice
# --------------------------------------------------------------------------


def test_a_character_the_parser_never_read_cannot_be_represented():
    """The structural guarantee. There is no way to express "and also a 'z'":
    the replay reads indices into the parser's own cells and nothing else."""

    element = _element(text="On | abz")
    report = verify_element_text(_document(element))

    assert report.verified == 0
    assert len(report.failures) == 1
    assert "did not read" in report.failures[0]


def test_an_index_used_twice_is_refused():
    assert replay_reading_order(_element(order=[0, 0, 1, 3])) is None


def test_an_index_out_of_range_is_refused():
    assert replay_reading_order(_element(order=[0, 2, 1, 9])) is None


def test_a_dropped_character_is_refused():
    assert replay_reading_order(_element(order=[0, 2, 1], cell_lengths=[2, 1])) is None


def test_cell_lengths_that_do_not_account_for_every_character_are_refused():
    assert replay_reading_order(_element(cell_lengths=[2, 1])) is None


def test_a_declared_recovery_with_no_provenance_is_a_failure_not_a_pass():
    """The case that would otherwise be silent: a row claiming a recovered order
    and carrying nothing to check it against."""

    report = verify_element_text(_document(_element(with_provenance=False)))

    assert report.verified == 0
    assert len(report.failures) == 1
    assert "cannot be checked" in report.failures[0]


def test_a_permutation_of_different_cells_does_not_verify_the_text():
    """Provenance has to be *this* row's. Cells that replay into something else
    are a failure, not a pass on the strength of having provenance at all."""

    report = verify_element_text(_document(_element(cells=["Xa", "nb"])))

    assert report.verified == 0
    assert report.failures


# --------------------------------------------------------------------------
# A recorded separator is replayed, and is the only thing that may be
# --------------------------------------------------------------------------


def test_a_row_with_recorded_separators_replays_exactly():
    assert replay_reading_order(_spaced()) == SPACED_TEXT


def test_a_row_with_recorded_separators_is_verified_rather_than_excused():
    report = verify_element_text(_document(_spaced()))

    assert report.verified == 1
    assert report.failures == []
    assert report.unprovable == []


def test_a_printed_character_left_unclaimed_is_refused():
    """The separators are filled by the replay; every printed character still
    has to be claimed from the parser's own cells, exactly once."""

    assert replay_reading_order(_spaced(order=[0, 3, 2], cell_lengths=[2, 2])) is None


def test_a_printed_character_the_parser_never_read_still_cannot_be_represented():
    report = verify_element_text(_document(_spaced(text="On | a bz")))

    assert report.verified == 0
    assert len(report.failures) == 1


def test_a_separator_offset_outside_the_text_is_refused():
    assert replay_reading_order(_spaced(spacing=[9])) is None


def test_a_repeated_separator_offset_is_refused():
    assert replay_reading_order(_spaced(order=[0, 3, 2], spacing=[3, 3])) is None


def test_a_record_written_before_separators_were_recorded_replays_as_it_always_did():
    """Backward compatibility, stated rather than assumed. A record that claims
    every character of its cells and records no separator is unaffected."""

    element = _element()

    assert element.reading_order.spacing == []
    assert replay_reading_order(element) == RECOVERED_TEXT
    assert verify_element_text(_document(element)).verified == 1


def test_separators_cannot_stand_in_for_a_dropped_character():
    """Claiming fewer characters and recording more separators does not balance:
    every printed character of the source must still be claimed."""

    assert replay_reading_order(_spaced(order=[0, 3, 2], spacing=[3, 4])) is None


# --------------------------------------------------------------------------
# The control
# --------------------------------------------------------------------------


def test_an_ordinary_joined_row_is_still_unprovable():
    """The pre-existing disposition is unchanged. A row that only declares
    `table_cell_join` was never reconstructible and still is not -- this change
    added a way to prove one kind of row, it did not quietly start passing the
    rest."""

    element = CanonicalElement(
        element_id="E000002",
        element_type="table_row",
        logical_order=0,
        text="On | ab",
        transformations=["table_cell_join"],
    )
    report = verify_element_text(_document(element))

    assert report.verified == 0
    assert report.failures == []
    assert len(report.unprovable) == 1
