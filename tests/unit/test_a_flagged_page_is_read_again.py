"""A flagged page is re-read; a clean one is never sent.

THE RULE, STATED ONCE AND WITHOUT REFERENCE TO ANY DOCUMENT

A parser walking a table of side-by-side columns can return one cell's
characters interleaved with its neighbour's. The characters are right and the
order is not. Where the existing detector proves that, and only there, the page
is re-read; everywhere else nothing happens and no model is called.

Nothing here is shaped around a corpus, a project, a page number or a script.
The cases below are invented, in several writing systems, because the property
is a property of the mechanism.

WHAT MAKES THE RESULT SAFE

The model's text is never stored. What is stored is a permutation of the
*parser's own characters*, and the row is derived by replaying it. So a
character the parser never read has no index to arrive by: translation,
invention and omission are not caught, they are unrepresentable. These tests
pin that, and pin the refusals for everything a permutation cannot express.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from policy_platform.contracts.canonical_document import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    SourceFragment,
)
from policy_platform.infrastructure.ingestion import visual_page_reading
from policy_platform.infrastructure.ingestion.canonical_fidelity import (
    replay_reading_order,
    verify_element_text,
)
from policy_platform.infrastructure.ingestion.visual_page_reading import (
    CELL_SEPARATOR,
    apply_reading_order,
    build_recovery,
    parse_reading,
    parser_cells,
    recover_reading_order,
)

#: Latin interleaved with Arabic, Cyrillic with Greek. Invented, and about
#: nothing. Two scripts, because the damage is a script-alternation signature and
#: a mechanism that only worked for one pair would be shaped around that pair.
DAMAGED_PAIRS = [
    (("Oرnخeأ", "بcd"), ("One", "رخأبcd")),
    (("AбBвC", "гd"), ("ABC", "бвгd")),
]

#: The same damage, with the parser's own spacing in it and a reading that
#: spaces it differently. The printed characters are identical in both.
SPACED_SOURCE = ("O رnخeأ", "بcd\n")
SPACED_READING = ("One", "رخأ  بcd")
SPACED_TEXT = "One | رخأ بcd"


def _run(coro):
    return asyncio.run(coro)


def _row(element_id: str, text: str, page: int = 1) -> CanonicalElement:
    return CanonicalElement(
        element_id=element_id,
        element_type="table_row",
        logical_order=0,
        text=text,
        transformations=["table_cell_join"],
        source_fragments=[SourceFragment(page=page, start_offset=0, end_offset=len(text), text=text)],
    )


def _document(*elements: CanonicalElement, pages: int = 1) -> CanonicalDocument:
    return CanonicalDocument(
        document_id="D1",
        page_count=pages,
        pages=[CanonicalPage(page=n + 1, raw_text="") for n in range(pages)],
        elements=list(elements),
        parser="test",
    )


class _Reader:
    """Returns a scripted reading, and records what was asked and how often."""

    def __init__(
        self,
        by_page: dict[int, list[tuple[str, ...]]],
        *,
        status: str = "exact",
        echo_page: int | None = None,
        retry: list[tuple[str, ...]] | None = None,
    ):
        self.by_page = by_page
        self.status = status
        self.echo_page = echo_page
        #: What comes back when one row is asked about again. `None` means the
        #: page's own rows come back unchanged, which settles nothing new.
        self.retry = retry
        self.pages_called: list[int] = []
        self.rows_called: list[int] = []
        self.prompts: list[str] = []

    async def chat(self, messages, **_kwargs) -> str:
        text = messages[-1]["content"][0]["text"]
        self.prompts.append(text)
        page = int(text.split("page_id: p", 1)[1].split("\n", 1)[0])
        if "\nrow_cells: " in text:
            self.rows_called.append(page)
            rows = self.by_page.get(page, []) if self.retry is None else self.retry
        else:
            self.pages_called.append(page)
            rows = self.by_page.get(page, [])
        return json.dumps(
            {
                "page_id": f"p{self.echo_page or page}",
                "status": self.status,
                "rows": [
                    {
                        "row_index": i,
                        "cells": [
                            {"col_index": j, "status": "exact", "text": c}
                            for j, c in enumerate(cells)
                        ],
                    }
                    for i, cells in enumerate(rows)
                ],
            },
            ensure_ascii=False,
        )


@pytest.fixture(autouse=True)
def _no_rendering(monkeypatch):
    """These tests are about routing and acceptance, not about PDF rasterising."""

    monkeypatch.setattr(visual_page_reading, "render_page_png", lambda *a, **k: b"png")


# --------------------------------------------------------------------------
# A clean document is never sent
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Notice of 30 days applies to every request.",
        "الإشعار ثلاثون يوما مطلوب قبل الطلب.",
        "Annual leave | الإجازة السنوية | 30 days",
        "Срок подачи | 30 дней",
    ],
)
def test_ordinary_content_makes_no_model_call(text):
    """Including ordinary multilingual content. Two languages in one row is not
    damage; characters alternating *within a word* is."""

    reader = _Reader({})
    outcome = _run(
        recover_reading_order(
            _document(_row("E1", text)),
            storage_path="x.pdf",
            client=reader,
            deployment="d",
        )
    )

    assert outcome.elements_flagged == 0
    assert outcome.calls_attempted == 0
    assert reader.pages_called == []
    assert reader.rows_called == []


def test_a_clean_page_beside_a_damaged_one_is_not_sent():
    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({2: [repaired]})
    document = _document(
        _row("clean1", "Perfectly ordinary text", page=1),
        _row("bad", CELL_SEPARATOR.join(damaged), page=2),
        _row("clean2", "More ordinary text", page=3),
        pages=3,
    )

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    assert reader.pages_called == [2], "a page with no flagged element was read"
    assert outcome.calls_attempted == 1


# --------------------------------------------------------------------------
# A flagged page is re-read, and the result is derived not copied
# --------------------------------------------------------------------------


@pytest.mark.parametrize("damaged,repaired", DAMAGED_PAIRS)
def test_a_flagged_row_is_recovered_and_replays_exactly(damaged, repaired):
    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )
    assert outcome.elements_recovered == 1
    assert outcome.elements_refused == 0

    applied = apply_reading_order(document, outcome)
    element = applied.elements[0]
    assert element.text == CELL_SEPARATOR.join(repaired)
    assert "visual_reading_order" in element.transformations
    assert replay_reading_order(element) == element.text


@pytest.mark.parametrize("damaged,repaired", DAMAGED_PAIRS)
def test_a_recovered_row_is_verified_not_excused(damaged, repaired):
    """The disposition that matters: the fidelity check examines it."""

    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))
    applied = apply_reading_order(
        document,
        _run(recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")),
    )

    report = verify_element_text(applied)
    assert report.verified == 1
    assert report.failures == []
    assert report.unprovable == []


def test_the_stored_provenance_is_the_parsers_characters_not_the_models_text():
    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))
    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    recovery = outcome.recoveries["bad"]
    assert list(recovery.source_cells) == list(damaged), (
        "provenance stored the reading rather than what the parser produced"
    )
    assert sorted(recovery.order) == list(range(len("".join(damaged))))


# --------------------------------------------------------------------------
# Spacing is structure, and it is settled rather than argued about
# --------------------------------------------------------------------------


def test_a_reading_that_differs_only_in_spacing_is_accepted():
    """The printed characters are the subject. A reading that states all of them,
    in the right order, laid out over its own word and line boundaries, is the
    reading -- and is accepted on that basis."""

    recovery, failure = build_recovery(SPACED_SOURCE, SPACED_READING)

    assert failure is None
    assert recovery is not None
    assert list(recovery.source_cells) == list(SPACED_SOURCE), (
        "provenance stored the reading rather than what the parser produced"
    )


def test_the_accepted_spacing_is_replayed_rather_than_stored_as_the_models_text():
    """The proof still holds with spacing in play: the persisted text is derived
    from the parser's own character indices plus the recorded offsets, so it is
    reproducible without the reply."""

    recovery, _ = build_recovery(SPACED_SOURCE, SPACED_READING)
    element = CanonicalElement(
        element_id="E1",
        element_type="table_row",
        logical_order=0,
        text=SPACED_TEXT,
        transformations=["table_cell_join", "visual_reading_order"],
        reading_order=recovery,
    )

    assert replay_reading_order(element) == SPACED_TEXT
    report = verify_element_text(_document(element))
    assert report.verified == 1
    assert report.failures == []


def test_the_same_reading_twice_over_settles_on_the_same_text():
    """Deterministic, so the same page read twice cannot persist two texts."""

    first, _ = build_recovery(SPACED_SOURCE, SPACED_READING)
    second, _ = build_recovery(SPACED_SOURCE, ("One  ", "\nرخأ\tبcd "))

    assert first is not None and second is not None
    assert first.model_dump() == second.model_dump()


def test_a_row_settled_this_way_is_accepted_without_anything_being_reported():
    """Silently. There is no finding to raise, so none is raised."""

    reader = _Reader({1: [SPACED_READING]})
    document = _document(_row("bad", CELL_SEPARATOR.join(SPACED_SOURCE)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )
    applied = apply_reading_order(document, outcome)

    assert outcome.elements_recovered == 1
    assert outcome.elements_refused == 0
    assert outcome.reasons == ()
    assert applied.elements[0].text == SPACED_TEXT
    assert replay_reading_order(applied.elements[0]) == SPACED_TEXT
    assert verify_element_text(applied).verified == 1


@pytest.mark.parametrize(
    "candidate,expected",
    [
        (("One", "رخأ بcdz"), "character count differs"),
        (("One", "رخأ بc"), "character count differs"),
        (("One", "رخأ بcz"), "did not read"),
        (("One", "رخأ بcdd"), "character count differs"),
    ],
)
def test_a_printed_character_added_or_missing_is_still_refused(candidate, expected):
    """The control on the tolerance above. Only the separators are structural;
    every printed character is still counted, one for one."""

    recovery, failure = build_recovery(SPACED_SOURCE, candidate)

    assert recovery is None
    assert expected in failure


# --------------------------------------------------------------------------
# Everything a permutation cannot express is refused
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate,expected",
    [
        (("Oneرخأبcd",), "cell count differs"),
        (("One", "رخأبcdz"), "character count differs"),
        (("One", "رخأبc"), "character count differs"),
        (("One", "رخأبcz"), "did not read"),
    ],
)
def test_a_reading_that_is_not_a_permutation_is_refused(candidate, expected):
    damaged = DAMAGED_PAIRS[0][0]
    recovery, failure = build_recovery(parser_cells(CELL_SEPARATOR.join(damaged)), candidate)

    assert recovery is None
    assert expected in failure


def test_the_parsers_empty_padding_is_kept_and_not_demanded_of_the_reading():
    """A reconstructed grid pads rows with empty cells. They state nothing and
    show nothing, so a reading is not asked to reproduce them -- but the row must
    come back the same width, with every empty where it was."""

    original = ("Oرnخeأ", "", "", "بcd", "")
    candidate = ("One", "رخأبcd")

    recovery, failure = build_recovery(original, candidate)

    assert failure is None and recovery is not None
    assert recovery.cell_lengths == [3, 0, 0, 6, 0], (
        "the row lost the parser's shape; empties must stay empty and in place"
    )

    element = CanonicalElement(
        element_id="E1",
        element_type="table_row",
        logical_order=0,
        text="x",
        transformations=["visual_reading_order"],
        reading_order=recovery,
    )
    replayed = replay_reading_order(element)
    assert replayed == "One |  |  | رخأبcd | "
    assert len(replayed.split(CELL_SEPARATOR)) == len(original)


def test_a_reading_with_the_wrong_number_of_written_cells_is_still_refused():
    """Ignoring empty padding is not ignoring structure: the cells that carry
    text must still correspond one to one."""

    original = ("Oرnخeأ", "", "بcd")
    recovery, failure = build_recovery(original, ("Oneرخأبcd",))

    assert recovery is None
    assert "cell count differs (2 parsed with text, 1 read with text)" == failure


def test_a_refused_row_keeps_its_original_text_and_is_still_flagged():
    damaged = DAMAGED_PAIRS[0][0]
    original = CELL_SEPARATOR.join(damaged)
    reader = _Reader({1: [("One", "somethingelse")]})
    document = _document(_row("bad", original))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )
    applied = apply_reading_order(document, outcome)

    assert outcome.elements_recovered == 0
    assert outcome.elements_refused == 1
    assert applied.elements[0].text == original
    assert "correct the original file" in outcome.detail().lower()


def test_a_printed_pipe_inside_a_cell_is_content_not_a_separator():
    recovery, failure = build_recovery(("a|b", "cd"), ("a|b", "cd"))
    assert failure is None and recovery is not None

    lost, failure = build_recovery(("a|b", "cd"), ("ab", "cdd"))
    assert lost is None and "did not read" in failure


def test_a_reading_that_is_still_interleaved_is_refused():
    damaged = DAMAGED_PAIRS[0][0]
    recovery, failure = build_recovery(damaged, damaged)
    assert recovery is None
    assert "still interleaved" in failure


@pytest.mark.parametrize(
    "reply,expected",
    [
        ('{"page_id":"p1","status":"needs_review","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":"A"}]}]}', "not 'exact'"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":null}]}]}', "unreadable"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"unreadable","text":"A"}]}]}', "reported a cell as"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":"A"}]},{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":"B"}]}]}', "more than once"),
        ('{"page_id":"p1","status":"exact","rows":[]}', "no rows"),
        ('{"page_id":"p2","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":"A"}]}]}', "echoed page_id"),
        ('{"status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"status":"exact","text":"A"}]}]}', "echoed page_id"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":1,"status":"exact","text":"A"}]}]}', "not contiguous"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":1,"cells":[{"col_index":0,"status":"exact","text":"A"}]}]}', "not contiguous"),
        ('{"page_id":"p1","status":"exact","rows":[{"row_index":0,"cells":[{"col_index":0,"text":"A"}]}]}', "reported a cell as None"),
    ],
)
def test_a_reply_that_is_not_a_clean_exact_reading_is_refused(reply, expected):
    with pytest.raises(ValueError) as caught:
        parse_reading(1, reply)
    assert expected in str(caught.value)


def test_a_recovery_survives_clause_persistence_and_canonical_rebuild():
    """The proof has to outlive the upload, or the fidelity check has to trust it.

    Round trip through the real seams: `clauses_from_document` writes the replay
    record into the provenance the clause already stores, and
    `canonical_from_clauses` restores it. A rebuilt element must still replay to
    its own text -- not merely carry the recovered wording with the evidence for
    it gone.
    """

    from types import SimpleNamespace

    from policy_platform.infrastructure.ingestion.canonical_rebuild import (
        canonical_from_clauses,
    )
    from policy_platform.infrastructure.ingestion.document_extraction import (
        clauses_from_document,
    )

    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))
    applied = apply_reading_order(
        document,
        _run(recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")),
    )

    clause_data = clauses_from_document(applied)
    assert any(
        "__reading_order__" in entry for entry in clause_data[0].source_fragments
    ), "the replay record was not persisted with the clause's provenance"

    # The shape `ClauseRepository` stores and reads back.
    stored = [
        SimpleNamespace(
            element_id=c.element_id,
            element_type=c.element_type,
            sequence=i,
            text=c.text,
            section=c.section,
            source_fragments=c.source_fragments,
            table_id=c.table_id,
            table_headers=c.table_headers,
        )
        for i, c in enumerate(clause_data)
    ]
    rebuilt = canonical_from_clauses("D1", stored)
    element = rebuilt.elements[0]

    assert element.text == CELL_SEPARATOR.join(repaired)
    assert element.reading_order is not None
    assert replay_reading_order(element) == element.text
    assert verify_element_text(rebuilt).verified == 1

    # Ordinary fragments are unchanged, and the record is not one of them.
    assert len(element.source_fragments) == 1
    assert element.source_fragments[0].text == CELL_SEPARATOR.join(damaged)


def test_a_row_settled_over_its_own_separators_survives_persistence_and_rebuild():
    """The same round trip, for a row whose separators are recorded rather than
    claimed. The rebuilt element must still replay to its own text."""

    from types import SimpleNamespace

    from policy_platform.infrastructure.ingestion.canonical_rebuild import (
        canonical_from_clauses,
    )
    from policy_platform.infrastructure.ingestion.document_extraction import (
        clauses_from_document,
    )

    reader = _Reader({1: [SPACED_READING]})
    document = _document(_row("bad", CELL_SEPARATOR.join(SPACED_SOURCE)))
    applied = apply_reading_order(
        document,
        _run(recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")),
    )

    clause_data = clauses_from_document(applied)
    stored = [
        SimpleNamespace(
            element_id=c.element_id,
            element_type=c.element_type,
            sequence=i,
            text=c.text,
            section=c.section,
            source_fragments=c.source_fragments,
            table_id=c.table_id,
            table_headers=c.table_headers,
        )
        for i, c in enumerate(clause_data)
    ]
    rebuilt = canonical_from_clauses("D1", stored)
    element = rebuilt.elements[0]

    assert element.text == SPACED_TEXT
    assert element.reading_order is not None
    assert element.reading_order.spacing, "the replay record lost its separators"
    assert replay_reading_order(element) == element.text
    assert verify_element_text(rebuilt).verified == 1


def test_a_clause_written_before_this_existed_still_rebuilds():
    """Backward compatibility, stated as a test rather than assumed. A clause
    with no replay record rebuilds exactly as it always did."""

    from types import SimpleNamespace

    from policy_platform.infrastructure.ingestion.canonical_rebuild import (
        canonical_from_clauses,
    )

    stored = [
        SimpleNamespace(
            element_id="E1",
            element_type="paragraph",
            sequence=0,
            text="Ordinary text",
            section=None,
            source_fragments=[
                {"page": 1, "start_offset": 0, "end_offset": 13, "text": "Ordinary text"}
            ],
            table_id=None,
            table_headers=None,
        )
    ]
    rebuilt = canonical_from_clauses("D1", stored)

    assert rebuilt.elements[0].reading_order is None
    assert rebuilt.elements[0].transformations == []
    assert len(rebuilt.elements[0].source_fragments) == 1


def test_cells_are_ordered_by_their_stated_indices_not_by_array_order():
    """A cell's position is what makes it that cell. Trusting the order the array
    happens to arrive in would let a reordered response become a different row
    without anything noticing."""

    reply = json.dumps(
        {
            "page_id": "p1",
            "status": "exact",
            "rows": [
                {
                    "row_index": 0,
                    "cells": [
                        {"col_index": 1, "status": "exact", "text": "second"},
                        {"col_index": 0, "status": "exact", "text": "first"},
                    ],
                }
            ],
        }
    )

    assert parse_reading(1, reply).rows == (("first", "second"),)


def test_a_reading_of_a_different_page_is_refused_end_to_end():
    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [repaired]}, echo_page=9)
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    assert outcome.calls_attempted == 1
    assert outcome.elements_recovered == 0
    assert outcome.elements_refused == 1


def test_one_reading_row_cannot_satisfy_two_damaged_rows():
    """Two identical damaged rows and one row offered by the page reading:
    exactly one is settled by it.

    Otherwise an omitted row is reported as two successes. The second row gets
    its own question, which here settles nothing, so it is refused.
    """

    damaged, repaired = DAMAGED_PAIRS[0]
    original = CELL_SEPARATOR.join(damaged)
    reader = _Reader({1: [repaired]}, retry=[("still", "wrong")])
    document = _document(_row("bad1", original), _row("bad2", original))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    assert outcome.elements_recovered == 1
    assert outcome.elements_refused == 1
    assert reader.pages_called == [1]
    assert reader.rows_called == [1], "the unsettled row was asked about more than once"


# --------------------------------------------------------------------------
# One further question per unsettled row, and only one
# --------------------------------------------------------------------------


def test_a_row_the_page_reading_did_not_settle_is_asked_about_once_more():
    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [("One", "somethingelse")]}, retry=[repaired])
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )
    applied = apply_reading_order(document, outcome)

    assert outcome.calls_attempted == 2
    assert outcome.calls_succeeded == 2
    assert reader.pages_called == [1] and reader.rows_called == [1]
    assert outcome.elements_recovered == 1
    assert outcome.elements_refused == 0
    assert applied.elements[0].text == CELL_SEPARATOR.join(repaired)
    assert replay_reading_order(applied.elements[0]) == applied.elements[0].text
    assert verify_element_text(applied).verified == 1


def test_a_second_question_that_still_does_not_conserve_is_refused_and_not_asked_again():
    damaged = DAMAGED_PAIRS[0][0]
    original = CELL_SEPARATOR.join(damaged)
    reader = _Reader({1: [("One", "somethingelse")]}, retry=[("still", "wrong")])
    document = _document(_row("bad", original))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )
    applied = apply_reading_order(document, outcome)

    assert outcome.calls_attempted == 2
    assert outcome.calls_succeeded == 2
    assert outcome.elements_recovered == 0
    assert outcome.elements_refused == 1
    assert applied.elements[0].text == original


def test_a_page_reading_that_settles_the_row_is_never_followed_by_a_second_question():
    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    assert outcome.calls_attempted == 1
    assert reader.rows_called == []


def test_the_second_question_supplies_the_parsers_own_cells_and_the_same_page():
    """Its evidence is this row's cells, not anything shaped around a document."""

    damaged = DAMAGED_PAIRS[0][0]
    reader = _Reader({1: [("One", "somethingelse")]}, retry=[("still", "wrong")])

    _run(
        recover_reading_order(
            _document(_row("bad", CELL_SEPARATOR.join(damaged))),
            storage_path="x.pdf",
            client=reader,
            deployment="d",
        )
    )

    targeted = [prompt for prompt in reader.prompts if "\nrow_cells: " in prompt]
    assert len(targeted) == 1
    assert json.loads(targeted[0].split("\nrow_cells: ", 1)[1]) == list(damaged)
    assert "page_id: p1" in targeted[0]


def test_a_failing_second_question_is_counted_and_leaves_the_row_as_it_was():
    class _FailsTheSecondTime:
        def __init__(self, reader):
            self.reader = reader

        async def chat(self, messages, **kwargs):
            text = messages[-1]["content"][0]["text"]
            if "\nrow_cells: " in text:
                raise RuntimeError("transport")
            return await self.reader.chat(messages, **kwargs)

    damaged = DAMAGED_PAIRS[0][0]
    original = CELL_SEPARATOR.join(damaged)
    document = _document(_row("bad", original))

    outcome = _run(
        recover_reading_order(
            document,
            storage_path="x.pdf",
            client=_FailsTheSecondTime(_Reader({1: [("One", "somethingelse")]})),
            deployment="d",
        )
    )

    assert outcome.calls_attempted == 2
    assert outcome.calls_succeeded == 1
    assert outcome.elements_refused == 1
    assert apply_reading_order(document, outcome).elements[0].text == original


def test_no_diagnostic_carries_source_text_after_a_second_question():
    damaged = DAMAGED_PAIRS[0][0]
    reader = _Reader({1: [("One", "somethingelse")]}, retry=[("still", "wrong")])

    outcome = _run(
        recover_reading_order(
            _document(_row("bad", CELL_SEPARATOR.join(damaged))),
            storage_path="x.pdf",
            client=reader,
            deployment="d",
        )
    )

    assert outcome.reasons
    for cell in damaged:
        assert cell not in outcome.detail()
        for reason in outcome.reasons:
            assert cell not in reason


def test_no_model_configured_leaves_the_text_alone_and_still_warns():
    damaged = DAMAGED_PAIRS[0][0]
    original = CELL_SEPARATOR.join(damaged)
    document = _document(_row("bad", original))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=None, deployment=None)
    )

    assert outcome.calls_attempted == 0
    assert outcome.elements_refused == 1
    assert apply_reading_order(document, outcome).elements[0].text == original
    assert "no visual reading was available" in outcome.detail()


def test_a_failing_call_is_counted_as_attempted():
    """Otherwise a page that was asked for and failed reports as never asked."""

    class _Broken:
        async def chat(self, *a, **k):
            raise RuntimeError("transport")

    damaged = DAMAGED_PAIRS[0][0]
    outcome = _run(
        recover_reading_order(
            _document(_row("bad", CELL_SEPARATOR.join(damaged))),
            storage_path="x.pdf",
            client=_Broken(),
            deployment="d",
        )
    )

    assert outcome.calls_attempted == 1
    assert outcome.calls_succeeded == 0
    assert outcome.elements_refused == 1


def test_no_diagnostic_carries_source_text():
    damaged = DAMAGED_PAIRS[0][0]
    outcome = _run(
        recover_reading_order(
            _document(_row("bad", CELL_SEPARATOR.join(damaged))),
            storage_path="x.pdf",
            client=None,
            deployment=None,
        )
    )
    detail = outcome.detail()

    for cell in damaged:
        assert cell not in detail
    for reason in outcome.reasons:
        for cell in damaged:
            assert cell not in reason


# --------------------------------------------------------------------------
# Mutation control: the detector is what decides, and it both fires and stays silent
# --------------------------------------------------------------------------


def test_with_the_detector_silenced_nothing_is_read():
    """Proves routing is driven by the detector rather than by element type."""

    damaged = DAMAGED_PAIRS[0][0]
    reader = _Reader({1: [DAMAGED_PAIRS[0][1]]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    original = visual_page_reading.interleaved_tokens
    visual_page_reading.interleaved_tokens = lambda _text: ()
    try:
        outcome = _run(
            recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
        )
    finally:
        visual_page_reading.interleaved_tokens = original

    assert outcome.elements_flagged == 0
    assert reader.pages_called == [], "a page was read with the detector silenced"


def test_with_the_detector_firing_the_same_document_is_read():
    """The other half of the control. Without this the test above would pass on a
    mechanism that never reads anything at all."""

    damaged, repaired = DAMAGED_PAIRS[0]
    reader = _Reader({1: [repaired]})
    document = _document(_row("bad", CELL_SEPARATOR.join(damaged)))

    outcome = _run(
        recover_reading_order(document, storage_path="x.pdf", client=reader, deployment="d")
    )

    assert outcome.elements_flagged == 1
    assert reader.pages_called == [1]
