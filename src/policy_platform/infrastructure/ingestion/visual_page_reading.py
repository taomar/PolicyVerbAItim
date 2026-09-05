"""Re-read a page whose composed rows a parser returned in the wrong order.

WHAT THIS IS FOR

A page may print independently composed runs side by side — columns of a table,
parallel texts, facing blocks. A parser walking such a layout cell by cell can
return one run's characters interleaved with its neighbour's, so a word of one
alternates with a word of the other. The characters are right; the order is not.

WHERE IT SITS

Deterministic extraction stays the primary path and is never replaced. This runs
after it, only for elements the shared detector has already proved are damaged,
and only for pages holding one. A document the detector does not flag makes no
model call at all — including one that simply contains more than one language,
which is ordinary content and not damage.

WHY A WHOLE PAGE

Because there may be nothing to crop with. Fragments do not always carry a
bounding box, so there is often no trustworthy geometry to cut on, and a guessed
crop can remove the very column boundary the reading order depends on. A flagged
page is the smallest region that is certainly sufficient.

WHY THE MODEL IS NEVER TRUSTED, AND WHY THAT IS STRUCTURAL

A model asked to read a hard region will fill it from whatever context it has —
including a neighbouring run that says something similar — and will report
success. Measured here rather than feared: a probe returned a well-formed word
that was not the word in the image, and called itself ``exact``.

So its output is never stored. What is stored is a **claim over the parser's
own characters**: the cells the parser produced, the order the page shows them
in, and where the separators between them fall. The recovered text is then
*derived* by replaying that claim, and
:func:`canonical_fidelity.replay_reading_order` checks it independently. A
character the parser never read cannot appear in the result, because the only
thing the replay reads is an index into the parser's cells. Translation,
invention and omission are not things this has to be clever enough to catch —
they cannot be represented.

ASKING TWICE, AND NEVER MORE THAN TWICE

The page is asked about first, because a row's order is a fact about its
neighbours. A row the page reading does not account for gets one further
question, carrying that same page image and that row's own cells. It is put
through the identical acceptance, so it can only turn a row that was going to be
refused into one that conserves — never into one that is trusted.
"""

from __future__ import annotations

import base64
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Final, Sequence

from policy_platform.contracts.canonical_document import (
    CanonicalDocument,
    CanonicalElement,
    ReadingOrderRecovery,
)
from policy_platform.infrastructure.errors import describe_exception
from policy_platform.infrastructure.ingestion.mixed_script_text import interleaved_tokens

#: 200 DPI against a 72-DPI page box: enough for small marks and diacritics to
#: survive rasterising, well inside the service's image limits.
_RENDER_SCALE: Final[float] = 200 / 72

#: How the parser joins the cells of one row. Split on it to recover the cells,
#: and regenerate it when assembling. A pipe printed *inside* a cell is content
#: and stays part of that cell.
CELL_SEPARATOR: Final[str] = " | "

#: The only element type this reads. A row is what the prompt asks for and what
#: the acceptance rule can pair one-to-one; anything else flagged is refused in
#: as many words rather than passed through a check written for something else.
SUPPORTED_ELEMENT_TYPE: Final[str] = "table_row"

VISUAL_READING_CODE: Final[str] = "visual_reading_order_recovered"
VISUAL_READING_REFUSED: Final[str] = "visual_reading_order_refused"

PROMPT: Final[str] = (
    "Transcribe every table row in this page image.\n"
    "\n"
    "First identify the table grid: its rows, its columns, and any merged or\n"
    "empty cells. Then transcribe cell by cell.\n"
    "\n"
    "Rules, all of which matter more than fluency:\n"
    "- Transcribe ONLY what is visibly printed. Do not translate.\n"
    "- Treat every cell independently. Never reconstruct one cell from another,\n"
    "  and never merge cells that are printed separately, whatever script or\n"
    "  writing direction each uses.\n"
    "- Do not correct, normalise, reorder within a cell, join lines or\n"
    "  dehyphenate. Preserve the line boundaries and the reading direction of\n"
    "  each run as printed.\n"
    "- Preserve every digit, mark and diacritic exactly as printed, in the\n"
    "  numeral system printed. Do not convert between numeral systems.\n"
    "- Preserve empty cells as empty strings, in the position they are printed.\n"
    "- If a cell is unreadable, mark it unreadable. Never guess.\n"
    "\n"
    "Row and column indices must be contiguous from 0 within each row.\n"
    "Return JSON only, echoing the page_id you were given:\n"
    '{"page_id":<string>,"status":"exact|needs_review|input_insufficient",'
    '"rows":[{"row_index":<int>,"cells":[{"col_index":<int>,'
    '"status":"exact|unreadable","text":<string|null>}]}]}'
)


ROW_PROMPT: Final[str] = (
    "One row of a table on this page image was read in the wrong order.\n"
    "\n"
    "Under row_cells below are that row's cells exactly as a parser returned\n"
    "them: a JSON array of strings, in the parser's own order. Every character\n"
    "the row prints is already there. What may be wrong is which cell each\n"
    "character belongs to, and the order they are printed in.\n"
    "\n"
    "Use the page image only to decide the correct order and the correct cell\n"
    "for each character. Do not read anything else off the image.\n"
    "\n"
    "Rules, all of which matter more than fluency:\n"
    "- Use every supplied character exactly once. Do not translate, correct,\n"
    "  substitute, add or omit anything, whatever script or writing direction a\n"
    "  run uses.\n"
    "- Return exactly as many cells as were supplied, in the same positions. A\n"
    "  cell supplied without content comes back without content.\n"
    "- Never reconstruct one cell from another, and never merge cells that are\n"
    "  printed separately.\n"
    "- Preserve every digit, mark and diacritic exactly as supplied, in the\n"
    "  numeral system supplied. Do not convert between numeral systems.\n"
    "- If the image does not settle the order, report input_insufficient.\n"
    "  Never guess.\n"
    "\n"
    "Column indices must be contiguous from 0. Return JSON only, as a single\n"
    "row, echoing the page_id you were given:\n"
    '{"page_id":<string>,"status":"exact|needs_review|input_insufficient",'
    '"rows":[{"row_index":0,"cells":[{"col_index":<int>,'
    '"status":"exact|unreadable","text":<string|null>}]}]}'
)


@dataclass(frozen=True)
class PageReading:
    """One page as the model returned it, before anything is accepted."""

    page: int
    rows: tuple[tuple[str, ...], ...]


@dataclass
class ReadingOutcome:
    """What happened, in terms a diagnostic may repeat.

    Counts, page numbers and reasons. No source text: the subject of this module
    is policy wording, and a diagnostic that quoted it would put the passage in a
    log in order to explain that the passage was mishandled.
    """

    pages_flagged: tuple[int, ...] = ()
    pages_read: tuple[int, ...] = ()
    calls_attempted: int = 0
    calls_succeeded: int = 0
    elements_flagged: int = 0
    elements_recovered: int = 0
    elements_refused: int = 0
    reasons: tuple[str, ...] = ()
    recoveries: dict[str, ReadingOrderRecovery] = field(default_factory=dict)

    @property
    def attempted(self) -> bool:
        return self.calls_attempted > 0

    def detail(self) -> str:
        if not self.elements_flagged:
            return ""
        if not self.attempted:
            return (
                f"{self.elements_flagged} element(s) on page(s) "
                f"{list(self.pages_flagged)} carry interleaved text and were left "
                "unchanged: no visual reading was available. Correct the original "
                "file and upload a new version to resolve it."
            )
        parts = [
            f"{self.elements_recovered} of {self.elements_flagged} interleaved "
            f"element(s) were re-read from page(s) {list(self.pages_read)} and "
            "restored to the order the page shows, using only characters the "
            "parser already read"
        ]
        if self.elements_refused:
            parts.append(
                f"{self.elements_refused} were refused and keep their original "
                "text and warning; correct the original file and upload a new "
                "version to resolve those"
            )
        return ". ".join(parts) + "."


def parse_reading(page: int, reply: str) -> PageReading:
    """The model's reply, or a refusal. Never a partial reading.

    Each of these raises rather than dropping something quietly, because every
    dropped thing is a way for a shorter reading to look like a matching one:
    a status other than ``exact``; a null cell, which is the model saying it
    could not read one; a duplicate or missing index, which is what one-to-one
    pairing is proved with; anything malformed.
    """

    parsed = json.loads(reply)
    if not isinstance(parsed, dict):
        raise ValueError("the reply was not an object")

    echoed = parsed.get("page_id")
    if echoed != f"p{page}":
        # The reply must say which page it read. Without this a reading of one
        # page could be accepted against another's rows -- and because acceptance
        # then still requires an exact permutation, the mismatch would surface as
        # a puzzling refusal rather than as the wrong page it is.
        raise ValueError(f"the reading echoed page_id {echoed!r}, not 'p{page}'")

    status = str(parsed.get("status") or "")
    if status != "exact":
        raise ValueError(f"the reading reported status {status or 'missing'!r}, not 'exact'")

    raw_rows = parsed.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("the reading carried no rows")

    rows: list[tuple[str, ...]] = []
    seen_rows: set[int] = set()
    for position, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise ValueError("a row was not an object")
        index = row.get("row_index", position)
        if not isinstance(index, int):
            raise ValueError("a row carried a non-integer row_index")
        if index in seen_rows:
            raise ValueError(f"row_index {index} appeared more than once")
        seen_rows.add(index)

        raw_cells = row.get("cells")
        if not isinstance(raw_cells, list) or not raw_cells:
            raise ValueError(f"row {index} carried no cells")

        # Ordered by the indices the reply states, not by the order the array
        # happens to arrive in. A cell's position is what makes it that cell, and
        # trusting array order would let a reordered response silently become a
        # different row.
        numbered: dict[int, str] = {}
        for offset, cell in enumerate(raw_cells):
            if not isinstance(cell, dict):
                raise ValueError(f"row {index} carried a cell that was not an object")
            col = cell.get("col_index", offset)
            if not isinstance(col, int):
                raise ValueError(f"row {index} carried a non-integer col_index")
            if col in numbered:
                raise ValueError(f"row {index} repeated col_index {col}")

            cell_status = cell.get("status")
            if cell_status != "exact":
                # Required, not defaulted. Treating an absent status as "exact"
                # would silently promote a reply that never made the claim, which
                # is the opposite of what asking for it is for.
                raise ValueError(f"row {index} reported a cell as {cell_status!r}")

            text = cell.get("text")
            if text is None:
                raise ValueError(f"row {index} reported an unreadable cell")
            if not isinstance(text, str):
                raise ValueError(f"row {index} carried a non-string cell")
            numbered[col] = text

        if sorted(numbered) != list(range(len(numbered))):
            raise ValueError(
                f"row {index} carried column indices {sorted(numbered)}, which are "
                "not contiguous from 0, so a cell is missing or misnumbered"
            )
        rows.append(tuple(numbered[col] for col in sorted(numbered)))

    if sorted(seen_rows) != list(range(len(seen_rows))):
        raise ValueError(
            f"the reading carried row indices {sorted(seen_rows)}, which are not "
            "contiguous from 0, so a row is missing or misnumbered"
        )
    return PageReading(page=page, rows=tuple(rows))


def parser_cells(text: str) -> tuple[str, ...]:
    """The cells the parser joined to make this row.

    Split on the separator the parser declares it inserted, so a pipe printed
    inside a cell stays that cell's content and is compared like any other
    character. Discarding every ``|`` instead would silently forgive a reading
    that lost a whole cell.
    """

    return tuple(text.split(CELL_SEPARATOR))


def _laid_out(cell: str) -> str:
    """One cell on its own word and line boundaries, settled to one shape.

    ``str.split`` with no argument breaks on Unicode whitespace of every kind,
    so what comes back is the cell's own boundaries with a single separator at
    each of them and none at either end.
    """

    return " ".join(cell.split())


def build_recovery(
    original: Sequence[str], candidate: Sequence[str]
) -> tuple[ReadingOrderRecovery | None, str | None]:
    """A replayable derivation from the parser's cells to the page's order.

    Returns the provenance, or the reason it cannot be built. Refusing here is
    the whole safety property: the derivation only exists when the two state
    exactly the same printed characters, in the same numbers, so a candidate that
    added, dropped, translated or normalised anything printed has no
    representation to be stored as.

    EMPTY CELLS ARE THE PARSER'S SHAPE, NOT THE PAGE'S CONTENT

    A reconstructed grid is usually ragged: measured on real rows, sixteen cells
    of which thirteen are empty, seventeen of which twelve are. Those empties are
    how the parser padded a row to the table's width. They state nothing, they
    contribute no characters, and nothing on the page shows them -- so requiring a
    reading to reproduce them is requiring it to reproduce an artifact of the
    reconstruction rather than anything the document says.

    So the correspondence is between the cells that carry text, and the row's
    shape is preserved by putting the recovered text back into the same slots the
    parser filled. Every empty stays empty and stays where it was, the cell count
    is unchanged, and the character conservation below is untouched -- which is
    the property that actually keeps a reading honest.
    """

    filled = [index for index, cell in enumerate(original) if cell.strip()]
    offered = [cell for cell in candidate if cell.strip()]

    if len(filled) != len(offered):
        return None, (
            f"cell count differs ({len(filled)} parsed with text, "
            f"{len(offered)} read with text)"
        )

    # The row keeps the parser's shape: its width, and every empty where it was.
    # Each written cell is laid out on the word and line boundaries the reading
    # shows, deterministically, so what is stored is one settled shape rather
    # than whichever one happened to arrive.
    target = ["" for _ in original]
    for slot, cell in zip(filled, offered):
        target[slot] = _laid_out(cell)

    source = "".join(original)
    rendered = "".join(target)
    # Unicode whitespace is structural here: it separates the printed characters
    # rather than being one of them, so only printed characters are paired.
    printed = [(index, char) for index, char in enumerate(source) if not char.isspace()]
    claimed = [char for char in rendered if not char.isspace()]
    if len(printed) != len(claimed):
        return None, f"character count differs ({len(printed)} parsed, {len(claimed)} read)"

    # Every character is claimed from the parser's own text, once. A character
    # the parser did not read has no index to claim, so it cannot get in.
    pool: dict[str, list[int]] = defaultdict(list)
    for index, char in printed:
        pool[char].append(index)

    order: list[int] = []
    for char in claimed:
        indices = pool.get(char)
        if not indices:
            return None, "the reading states a character the parser did not read"
        order.append(indices.pop())

    if any(pool.values()):
        return None, "the reading does not state every character the parser read"

    joined = CELL_SEPARATOR.join(target)
    if interleaved_tokens(joined):
        return None, "the reading is still interleaved"

    return (
        ReadingOrderRecovery(
            source_cells=list(original),
            cell_lengths=[len(cell) for cell in target],
            order=order,
            spacing=[offset for offset, char in enumerate(rendered) if char.isspace()],
        ),
        None,
    )


def render_page_png(storage_path: str, page: int, *, scale: float = _RENDER_SCALE) -> bytes:
    """One page as a PNG."""

    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(storage_path)
    try:
        bitmap = document[page - 1].render(scale=scale)
        buffer = io.BytesIO()
        bitmap.to_pil().save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


def flagged_elements(document: CanonicalDocument) -> list[CanonicalElement]:
    """The elements the shared detector proves are interleaved. Nothing else."""

    return [element for element in document.elements if interleaved_tokens(element.text or "")]


def page_image(storage_path: str, page: int) -> str:
    """One page as a data URL, so a page rendered once can be asked about twice."""

    png = render_page_png(storage_path, page)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


async def _ask(
    client: Any, *, deployment: str, page: int, text: str, image: str, timeout: float
) -> PageReading:
    reply = await client.chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        ],
        deployment=deployment,
        json_mode=True,
        max_tokens=32_000,
        timeout=timeout,
    )
    return parse_reading(page, reply)


async def read_page(
    client: Any,
    *,
    deployment: str,
    page: int,
    storage_path: str | None = None,
    image: str | None = None,
    timeout: float = 300.0,
) -> PageReading:
    return await _ask(
        client,
        deployment=deployment,
        page=page,
        text=f"{PROMPT}\n\npage_id: p{page}",
        image=image if image is not None else page_image(str(storage_path), page),
        timeout=timeout,
    )


async def read_row(
    client: Any,
    *,
    deployment: str,
    page: int,
    cells: Sequence[str],
    image: str,
    timeout: float = 300.0,
) -> PageReading:
    """Ask again about one row, with the parser's own cells as evidence.

    The whole page is asked first and is what settles nearly everything. This is
    the one further question allowed per row the page reading did not account
    for: the same image, plus the cells that row has to be made of. It buys
    nothing on its own -- the reply is put through exactly the same acceptance,
    so a reply that does not conserve the row is refused like any other.
    """

    supplied = json.dumps(list(cells), ensure_ascii=False)
    return await _ask(
        client,
        deployment=deployment,
        page=page,
        text=f"{ROW_PROMPT}\n\npage_id: p{page}\nrow_cells: {supplied}",
        image=image,
        timeout=timeout,
    )


async def recover_reading_order(
    document: CanonicalDocument,
    *,
    storage_path: str,
    client: Any | None,
    deployment: str | None,
) -> ReadingOutcome:
    """Re-read the flagged pages; keep only rows that replay exactly."""

    flagged = flagged_elements(document)
    pages = tuple(
        sorted({f.page for e in flagged for f in (e.source_fragments or [])})
    )
    outcome = ReadingOutcome(pages_flagged=pages, elements_flagged=len(flagged))
    if not flagged or client is None or not deployment:
        outcome.elements_refused = len(flagged)
        return outcome

    reasons: list[str] = []
    by_page: dict[int, list[CanonicalElement]] = {}
    for element in flagged:
        if element.element_type != SUPPORTED_ELEMENT_TYPE:
            outcome.elements_refused += 1
            reasons.append(
                f"element type {element.element_type!r} is outside this recovery, "
                f"which reads {SUPPORTED_ELEMENT_TYPE} only"
            )
            continue
        for page in {f.page for f in (element.source_fragments or [])}:
            by_page.setdefault(page, []).append(element)

    read_pages: list[int] = []
    for page in sorted(by_page):
        # Counted before the await, so a call that was made and failed is
        # reported as a call rather than as "we never asked".
        outcome.calls_attempted += 1
        try:
            # Rendered here so the same bytes serve the page reading and any
            # further question about a row of it, within this one page's turn.
            image = page_image(storage_path, page)
            reading = await read_page(
                client, deployment=deployment, page=page, image=image
            )
        except Exception as exc:  # noqa: BLE001 - a refusal is a result, not a crash
            reasons.append(f"page {page}: {describe_exception(exc)}")
            outcome.elements_refused += len(by_page[page])
            continue

        outcome.calls_succeeded += 1
        read_pages.append(page)
        # Drained as rows are claimed, so two damaged rows cannot both be
        # satisfied by one row of the reading -- which would report an omitted
        # row as two successes.
        available = list(reading.rows)
        for element in by_page[page]:
            original = parser_cells(element.text or "")
            claimed: ReadingOrderRecovery | None = None
            last: str | None = None
            for position, candidate in enumerate(available):
                recovery, failure = build_recovery(original, candidate)
                if recovery is not None:
                    available.pop(position)
                    claimed = recovery
                    break
                last = failure

            if claimed is None:
                # One further question about this row, and only one. Asked with
                # the same image and this row's own cells, and accepted on
                # exactly the same terms -- so the retry can only turn a row that
                # was going to be refused into one that conserves, never into one
                # that is trusted.
                outcome.calls_attempted += 1
                try:
                    retry = await read_row(
                        client,
                        deployment=deployment,
                        page=page,
                        cells=original,
                        image=image,
                    )
                except Exception as exc:  # noqa: BLE001 - a refusal is a result
                    outcome.elements_refused += 1
                    reasons.append(f"page {page}: {describe_exception(exc)}")
                    continue
                outcome.calls_succeeded += 1
                for candidate in retry.rows:
                    recovery, failure = build_recovery(original, candidate)
                    if recovery is not None:
                        claimed = recovery
                        break
                    last = failure

            if claimed is None:
                outcome.elements_refused += 1
                reasons.append(f"page {page}: {last or 'no row was offered'}")
                continue
            outcome.recoveries[element.element_id] = claimed
            outcome.elements_recovered += 1

    outcome.pages_read = tuple(read_pages)
    outcome.reasons = tuple(reasons[:10])
    return outcome


def apply_reading_order(
    document: CanonicalDocument, outcome: ReadingOutcome
) -> CanonicalDocument:
    """Derive the recovered rows from the stored permutation.

    The text is *computed* from the parser's own cells, never copied from the
    model's reply, so what lands in the document is provably characters the
    parser read. `verify_element_text` replays the same permutation and checks
    it, which is why a recovered row is verified rather than excused.

    Called before clauses are derived, so offsets, ids and everything downstream
    read the document this returns.
    """

    if not outcome.recoveries:
        return document

    from policy_platform.infrastructure.ingestion.canonical_fidelity import (
        replay_reading_order,
    )

    elements = []
    for element in document.elements:
        recovery = outcome.recoveries.get(element.element_id)
        if recovery is None:
            elements.append(element)
            continue
        candidate = element.model_copy(
            update={
                "reading_order": recovery,
                "transformations": [*(element.transformations or []), "visual_reading_order"],
            }
        )
        replayed = replay_reading_order(candidate)
        if replayed is None:
            # Built but not replayable: keep the original rather than store a
            # provenance that its own verifier would reject.
            elements.append(element)
            continue
        elements.append(candidate.model_copy(update={"text": replayed}))
    return document.model_copy(update={"elements": elements})
