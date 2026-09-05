"""Rebuild a canonical document from the clauses already persisted for it.

This existed before this module did — it lived as a private helper on the
extraction router, and it is the seam that lets any later stage recover the
document's *structure* without re-parsing the source. It has been moved here,
rather than copied, so there is exactly one rebuild in the system.

Moved because of direction, not taste. Infrastructure may read ``domain`` and
``contracts``; it may not reach up into ``api``. A stage that needed this had
only two honest choices — move the one implementation down to a layer both
callers may see, or write a second one. A second one would drift from the first
the moment either changed, and the two would disagree about what the document
is while both claiming to describe it.
"""

from __future__ import annotations

from typing import Any, Iterable

from policy_platform.contracts.canonical_document import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    SourceFragment,
    TABLE_STRUCTURE_KEY,
    TableStructure,
    table_cell_of,
)
from policy_platform.domain.models import Clause

#: The fragment fields a persisted clause is allowed to contribute.
#:
#: Named rather than passed through: ``source_fragments`` is stored as free JSON,
#: so a writer that added a key would otherwise hand it straight to a constructor
#: that has never heard of it.
_FRAGMENT_FIELDS = {"page", "start_offset", "end_offset", "text"}

#: Marks an entry in that list as a *sidecar* — a namespaced record travelling
#: with the fragments rather than being one.
#:
#: Recognised by shape, not by name. A reader that skipped one known key would
#: still hand every other sidecar to the fragment constructor, so the rule is
#: "every key is namespaced" and it holds for records this module has never
#: heard of. A source fragment names its page and offsets and so can never
#: match; a legacy clause has no sidecars at all and reads back unchanged.
_SIDECAR_PREFIX = "__"


def _is_sidecar(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and bool(entry)
        and all(isinstance(key, str) and key.startswith(_SIDECAR_PREFIX) for key in entry)
    )


def stored_fragments(entries: Iterable[Any] | None) -> list[dict]:
    """The source fragments in a clause's stored provenance, and nothing else.

    Public because the fragments are shown to callers — the canonical-document
    endpoint hands them straight out — and a payload that leaked a sidecar would
    make every consumer iterating fragments deal with an entry that has no page
    and no offsets. Filtering in one place is what keeps that shape exactly as it
    was before any sidecar existed.
    """

    return [entry for entry in (entries or []) if not _is_sidecar(entry)]


def stored_table_structure(entries: Iterable[Any] | None) -> TableStructure | None:
    """The grid a clause was part of, or ``None`` for a clause that was not.

    ``None`` covers both a clause that is not part of a table and a clause stored
    before the carrier existed. The two are indistinguishable here on purpose:
    neither has a recorded shape, and a reader must treat "no structure" as "do
    not claim any", never as "assume the default one".

    A malformed record is *not* absorbed into that silence. It raises, for the
    same reason ``table_headers`` is passed through unguarded: a corrupt value
    quietly mapped onto ``None`` becomes indistinguishable from an honest
    absence, and the whole point of the record is that it can be checked.
    """

    for entry in entries or []:
        if isinstance(entry, dict) and TABLE_STRUCTURE_KEY in entry:
            payload = entry[TABLE_STRUCTURE_KEY]
            if payload is None:
                return None
            return TableStructure.model_validate(payload)
    return None


def canonical_from_clauses(document_id: str, clauses: list[Clause]) -> CanonicalDocument:
    """Rebuild a canonical document from the persisted clauses.

    Rebuilt rather than re-converted. Re-running Docling would take minutes and,
    worse, could produce a *different* artifact from the one whose offsets are
    already stored — so every span a reviewer is looking at would silently stop
    referring to what produced it.

    A clause that was part of a grid brings that grid's shape back with it.
    Without it the rebuilt element would keep the row's rendered text and lose
    every coordinate behind it, and the only way left to answer "which value sits
    under which column" would be to split the rendering back apart — a guess this
    layer is not entitled to make on a reviewer's behalf.
    """

    elements: list[CanonicalElement] = []
    pages: dict[int, list[str]] = {}

    for index, clause in enumerate(clauses):
        stored = list(clause.source_fragments or [])
        fragments = [
            SourceFragment(
                **{k: v for k, v in fragment.items() if k in _FRAGMENT_FIELDS}
            )
            for fragment in stored_fragments(stored)
        ]
        structure = stored_table_structure(stored)
        elements.append(
            CanonicalElement(
                element_id=clause.element_id or f"E{index:06d}",
                element_type=clause.element_type or "paragraph",  # type: ignore[arg-type]
                logical_order=clause.sequence,
                text=clause.text,
                section=clause.section,
                source_fragments=fragments,
                # Restored, so a rebuilt document still knows which grid a row
                # belongs to and what that grid's columns are called. Passed
                # through untouched, and deliberately not guarded: `None` means
                # the converter found no row stating column labels, and mapping
                # anything else onto `None` here would make a corrupt value
                # indistinguishable from that fact. A value this projection did
                # not write fails validation loudly instead.
                table_id=clause.table_id,
                table_headers=clause.table_headers,
                table_structure=structure,
                # The coordinate an element holds in its own right, which only a
                # single-cell element has. Derived from the restored structure
                # rather than stored twice, so the two can never disagree about
                # where the same cell sits.
                table_cell=table_cell_of(clause.element_type, structure),
            )
        )
        for fragment in fragments:
            pages.setdefault(fragment.page, [])

    return CanonicalDocument(
        document_id=document_id,
        page_count=len(pages) or 1,
        pages=[CanonicalPage(page=page, raw_text="") for page in sorted(pages)]
        or [CanonicalPage(page=1, raw_text="")],
        elements=elements,
        parser="persisted",
    )
