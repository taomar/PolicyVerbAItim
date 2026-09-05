"""Guard: text read across columns must be reported, and left exactly as it is.

WHAT THIS PROTECTS
------------------
A page that sets two columns side by side can be read the wrong way by an
extractor. What comes out is one string with the two columns' letters
alternating inside individual words -- ``O\u0631n\u062ee\u0623`` is the Latin
word "One" zipped together with an Arabic one. Every character of both texts is
present and none was invented; only the order is wrong, and neither text can be
read.

Deterministic coordinate-based reading order recovers the overwhelming majority
of these before anything here runs. What this covers is the residue: text that
came through ordinary ingestion still damaged, which a reviewer will otherwise
meet as nonsense in a citation with nothing to explain it.

THREE PROPERTIES, ALL LOAD-BEARING
----------------------------------
1. It fires on the pattern in any pair of scripts, and stays silent on ordinary
   text -- including the mixed-language text a naive check would accuse.
2. It changes nothing. Detection only, exactly as ``detect_display_glyphs``:
   a stored value that reads oddly is a defect a reviewer can see; a value
   silently rewritten into something the document does not contain is a defect
   nobody can see.
3. It is informational, and *only* informational. The upload succeeds, the
   clauses persist, the index builds. The user directed this explicitly: the
   warning must not stop, gate, filter, skip, rewrite or delay any step. The
   remedy is a corrected source file, so withholding the corpus would deny the
   reviewer the document without bringing the fix any closer.

ON THE FIXTURES
---------------
The two damaged fragments below are the real ones recovered from the failing
unit, kept because a synthetic approximation of this defect is easy to make
tidier than the thing itself. They are fragments of the damage, not policy
prose: no readable sentence of any customer document appears in this file.
"""
from __future__ import annotations

import logging
import os
import shutil
import unicodedata
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "******localhost:5433/test")
os.environ.setdefault("ALEMBIC_DATABASE_URL", "******/test")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402

from policy_platform.api.app import create_app  # noqa: E402
from policy_platform.api.routers import documents as documents_router  # noqa: E402
from policy_platform.api.schemas import ingestion_status_of  # noqa: E402
from policy_platform.contracts.canonical_document import (  # noqa: E402
    CanonicalDocument,
    CanonicalElement,
    SourceFragment,
)
from policy_platform.domain.models import (  # noqa: E402
    Clause,
    DocumentVersion,
    SourceDocument,
)
from policy_platform.infrastructure.ingestion import document_extraction  # noqa: E402
from policy_platform.infrastructure.ingestion.mixed_script_text import (  # noqa: E402
    INTERLEAVED_TEXT_CODE,
    interleaved_tokens,
    is_interleaved,
)
from policy_platform.infrastructure.persistence.db import get_session  # noqa: E402
from policy_platform.infrastructure.search import policy_index  # noqa: E402
from policy_platform.infrastructure.settings import Settings  # noqa: E402


@compiles(JSONB, "sqlite")
def _compile_jsonb(_type, _compiler, **_kw) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid(_type, _compiler, **_kw) -> str:
    return "CHAR(36)"


#: Damaged text. The first two are the fragments actually recovered from the
#: failing unit; the rest are the same *pattern* in other script pairs, present
#: so that nothing here can come to depend on one alphabet or one corpus.
DAMAGED = {
    "observed_latin_arabic": "O\u0631n\u062ee\u0623",
    "observed_arabic_latin": "\u0636\u0627o\u0641\u0629w",
    "cyrillic_latin": "\u041fa\u0440b\u0438c",
    "greek_latin": "\u03a0x\u03bby\u03b7z",
    "hebrew_latin": "\u05e9a\u05dc b".replace(" ", ""),
    "devanagari_latin": "\u0928a\u092eb\u0938c",
}

#: Ordinary text that must never be accused. Every entry mixes scripts or is in
#: a script whose shaping or direction would fool a cruder check; a detector
#: keyed on "two scripts present" or on right-to-left would fire on all of them.
CLEAN = {
    "arabic": "\u062c\u062f\u0627\u0648\u0644 \u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0627\u062a",
    "english": "Employees must submit the request within 15 minutes.",
    # A quoted foreign term beside its translation: two scripts, one switch per
    # word boundary, entirely routine in this corpus.
    "arabic_quoting_english": "\u064a\u062c\u0628 \u0625\u0631\u0633\u0627\u0644 \u0637\u0644\u0628 (request) \u062e\u0644\u0627\u0644 15 \u062f\u0642\u064a\u0642\u0629",
    "english_quoting_arabic": "The term \u0625\u062c\u0627\u0632\u0629 means leave.",
    # Run together across one boundary -- a missing space, not interleaving.
    "one_switch_only": "\u0625\u062c\u0627\u0632\u0629leave",
    "hebrew": "\u05de\u05d3\u05d9\u05e0\u05d9\u05d5\u05ea \u05de\u05e9\u05d0\u05d1\u05d9 \u05d0\u05e0\u05d5\u05e9",
    "greek": "\u03a0\u03bf\u03bb\u03b9\u03c4\u03b9\u03ba\u03ae \u03b1\u03bd\u03b8\u03c1\u03ce\u03c0\u03b9\u03bd\u03bf\u03c5",
    "cjk": "\u4eba\u4e8b\u65b9\u91dd",
    # Punctuation and digits are shared between writing systems and must not be
    # allowed to look like a strand of their own.
    "identifier": "AIS-2024/07 \u0645\u0627\u062f\u0629(5)",
    "punctuation_only": "--- 123 ... ///",
    "empty": "",
}


def _document(*texts: str, pages: tuple[int, ...] | None = None) -> CanonicalDocument:
    """A canonical document whose elements carry the given text, one per page."""

    page_numbers = pages or tuple(range(1, len(texts) + 1))
    elements = [
        CanonicalElement(
            element_id=f"E{index:06d}",
            element_type="paragraph",
            logical_order=index,
            text=text,
            source_fragments=[
                SourceFragment(page=page, start_offset=0, end_offset=len(text), text=text)
            ],
        )
        for index, (text, page) in enumerate(zip(texts, page_numbers))
    ]
    return CanonicalDocument(
        document_id="d",
        source_hash="a" * 64,
        parser="test",
        page_count=max(page_numbers, default=1),
        elements=elements,
    )


def _script_switches(text: str) -> int:
    """Script alternations in ``text``, computed without asking the detector.

    Deliberately a second implementation. If it agreed with the module by
    calling it, a detector that had stopped seeing anything would satisfy the
    fixture guards and the silence tests together, and only the fire tests
    would notice -- which is the failure mode these guards exist to catch.
    """

    scripts: list[str] = []
    for char in text:
        if not char.isalpha():
            continue
        try:
            scripts.append(unicodedata.name(char).split(" ", 1)[0])
        except ValueError:
            continue
    return sum(1 for before, after in zip(scripts, scripts[1:]) if before != after)


class TestTheFixturesStillSayWhatTheyClaim:
    """Guard the guard.

    A detector that has stopped seeing anything passes every silence test
    perfectly. These assertions are written against ``unicodedata`` directly,
    so they establish that the two corpora really do differ in the property
    under test even if the detector is broken or stubbed out.
    """

    @pytest.mark.parametrize("label", sorted(DAMAGED))
    def test_the_damaged_corpus_really_does_alternate(self, label: str) -> None:
        assert _script_switches(DAMAGED[label]) >= 2, (
            f"the {label!r} fixture no longer alternates between scripts, so a "
            "test asserting the diagnostic fires on it would prove nothing"
        )

    @pytest.mark.parametrize("label", sorted(CLEAN))
    def test_no_clean_fixture_alternates_within_a_word(self, label: str) -> None:
        for token in CLEAN[label].split():
            assert _script_switches(token) < 2, (
                f"the {label!r} fixture now contains an alternating token, so "
                "asserting the diagnostic stays silent on it would be asserting "
                "against text that has the defect"
            )

    def test_the_detector_separates_the_two_corpora(self) -> None:
        """The mutation control.

        Everything else in this file is either a fire test or a silence test,
        and each half alone can be satisfied by a detector stuck in one answer.
        This states the discrimination itself: stub ``is_interleaved`` to a
        constant either way and this fails.
        """

        fires = {label for label in DAMAGED if is_interleaved(DAMAGED[label])}
        accuses = {label for label in CLEAN if interleaved_tokens(CLEAN[label])}

        assert fires == set(DAMAGED)
        assert accuses == set()


class TestItFiresOnInterleavedText:
    @pytest.mark.parametrize("label", sorted(DAMAGED))
    def test_the_pattern_is_reported_in_any_pair_of_scripts(self, label: str) -> None:
        """No corpus shaping: the rule is about codepoints, not about Arabic."""

        diagnostic = document_extraction.detect_interleaved_text(_document(DAMAGED[label]))

        assert diagnostic is not None
        assert diagnostic.code == INTERLEAVED_TEXT_CODE

    def test_it_fires_when_one_word_of_an_ordinary_passage_is_affected(self) -> None:
        document = _document(f"The term {DAMAGED['observed_latin_arabic']} appears here.")

        assert document_extraction.detect_interleaved_text(document) is not None

    def test_the_severity_says_loaded_but_not_readable(self) -> None:
        """A warning, never an error.

        The document parsed and its structure is sound. What is unsound is the
        source file, and only its author can put that right.
        """

        diagnostic = document_extraction.detect_interleaved_text(
            _document(DAMAGED["observed_latin_arabic"])
        )

        assert diagnostic is not None
        assert diagnostic.severity == "warning"

    def test_it_reports_scale_and_place_rather_than_a_bare_boolean(self) -> None:
        """A reviewer needs to know whether this is one word or the whole annex."""

        document = _document(
            CLEAN["english"],
            DAMAGED["observed_latin_arabic"] + " " + DAMAGED["observed_arabic_latin"],
            CLEAN["arabic"],
            DAMAGED["cyrillic_latin"],
            pages=(1, 2, 3, 4),
        )

        diagnostic = document_extraction.detect_interleaved_text(document)

        assert diagnostic is not None
        assert "3 word(s)" in diagnostic.detail
        assert "2 passage(s)" in diagnostic.detail
        assert "[2, 4]" in diagnostic.detail

    def test_it_tells_the_author_to_correct_the_source_file(self) -> None:
        """The whole point of reporting it.

        Interleaving comes from the original PDF or DOCX. A diagnostic that
        described the defect without saying that leaves the reader with a
        complaint and no action.
        """

        diagnostic = document_extraction.detect_interleaved_text(
            _document(DAMAGED["observed_latin_arabic"])
        )

        assert diagnostic is not None
        wording = diagnostic.detail.lower()
        assert "original pdf" in wording or "original" in wording
        assert "new version" in wording

    def test_it_carries_no_policy_wording(self) -> None:
        """Counts and locations only. The passage is customer text."""

        secret = "Employees must submit the request within 15 minutes."
        diagnostic = document_extraction.detect_interleaved_text(
            _document(secret + " " + DAMAGED["observed_latin_arabic"])
        )

        assert diagnostic is not None
        assert secret not in diagnostic.detail
        assert DAMAGED["observed_latin_arabic"] not in diagnostic.detail

    def test_it_surfaces_to_the_upload_caller(self) -> None:
        """``ingestion_warnings`` is what the upload route returns and stores."""

        document = _document(DAMAGED["observed_latin_arabic"])
        diagnostic = document_extraction.detect_interleaved_text(document)
        assert diagnostic is not None
        document.diagnostics.append(diagnostic)

        codes = {d.code for d in document_extraction.ingestion_warnings(document)}
        assert INTERLEAVED_TEXT_CODE in codes

    def test_a_warning_alone_does_not_read_as_a_failed_ingestion(self) -> None:
        """The status the API derives must be ``warning``, not ``error``.

        This is the boundary where informational-only becomes visible or turns
        into a blockage: an ``error`` status is what the portal presents as a
        document that did not load.
        """

        assert (
            ingestion_status_of([{"code": INTERLEAVED_TEXT_CODE, "severity": "warning"}], None)
            == "warning"
        )


class TestItStaysSilentOnOrdinaryText:
    @pytest.mark.parametrize("label", sorted(CLEAN))
    def test_ordinary_text_is_never_flagged(self, label: str) -> None:
        """Including the cases a cruder check gets wrong.

        Mixed-script text is normal in this corpus: an Arabic policy quoting an
        English term, or an English one quoting an Arabic term, is the ordinary
        state of the documents this platform holds. A check that fired on "two
        scripts present", or on right-to-left, would cry wolf on all of them.
        """

        assert document_extraction.detect_interleaved_text(_document(CLEAN[label])) is None

    def test_an_empty_document_is_not_flagged(self) -> None:
        assert document_extraction.detect_interleaved_text(_document()) is None


class TestItDetectsWithoutRepairing:
    """The rule that must never be relaxed."""

    def test_the_text_is_left_exactly_as_the_converter_produced_it(self) -> None:
        original = DAMAGED["observed_latin_arabic"] + " " + CLEAN["english"]
        document = _document(original)

        document_extraction.detect_interleaved_text(document)

        assert document.elements[0].text == original
        assert document.elements[0].source_fragments[0].text == original

    def test_detection_reads_no_model(self, monkeypatch) -> None:
        """No network, no LLM, no cost, no latency, nothing to fail.

        The automatic-repair design this replaced called a model per damaged
        window. Detection is arithmetic over codepoints, and the difference is
        the reason it can run on every upload.
        """

        import urllib.request

        def _refuse(*_args, **_kwargs):
            raise AssertionError("detection must not open a connection")

        monkeypatch.setattr(urllib.request, "urlopen", _refuse)

        assert document_extraction.detect_interleaved_text(
            _document(DAMAGED["observed_latin_arabic"])
        ) is not None


class TestBothConverterPathsAreChecked:
    """Whichever parser ran, the check belongs to the text it produced."""

    def _settings(self, converter: str) -> Settings:
        return Settings(
            database_url="******localhost:5433/db",
            alembic_database_url="******localhost:5433/db",
            document_converter=converter,
        )

    def _pin(self, monkeypatch, converter: str, produced: CanonicalDocument) -> None:
        monkeypatch.setattr(
            document_extraction, "get_settings", lambda: self._settings(converter)
        )
        monkeypatch.setattr(document_extraction, "ingest_document", lambda *a, **k: produced)
        monkeypatch.setattr(
            document_extraction, "_extract_with_docling", lambda *a, **k: produced
        )

    @pytest.mark.parametrize("converter", ["legacy", "docling"])
    def test_the_seam_appends_the_diagnostic_whichever_parser_ran(
        self, monkeypatch, converter: str
    ) -> None:
        self._pin(monkeypatch, converter, _document(DAMAGED["observed_latin_arabic"]))

        result = document_extraction.extract_document("f.pdf", "application/pdf")

        assert INTERLEAVED_TEXT_CODE in {d.code for d in result.diagnostics}

    @pytest.mark.parametrize("converter", ["legacy", "docling"])
    def test_a_clean_document_gains_no_diagnostic_on_either_path(
        self, monkeypatch, converter: str
    ) -> None:
        self._pin(monkeypatch, converter, _document(CLEAN["arabic_quoting_english"]))

        result = document_extraction.extract_document("f.pdf", "application/pdf")

        assert INTERLEAVED_TEXT_CODE not in {d.code for d in result.diagnostics}


class TestTheRebuildReportsTheSameFinding:
    """One implementation, two callers.

    A portal that noticed and a rebuild that did not would be two opinions
    about one corpus, and the reviewer would have no way to tell which held.
    """

    def _group(self) -> list[tuple[str, str]]:
        return [
            ("policy", CLEAN["arabic_quoting_english"]),
            ("rule-1", "A clause containing " + DAMAGED["observed_latin_arabic"]),
            ("rule-2", CLEAN["english"]),
        ]

    def test_the_build_names_the_same_code(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            policy_index._warn_about_interleaved_text({"policy_key": "P1"}, self._group())

        assert INTERLEAVED_TEXT_CODE in caplog.text

    def test_the_build_reports_only_the_affected_keys(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            policy_index._warn_about_interleaved_text({"policy_key": "P1"}, self._group())

        assert "rule-1" in caplog.text
        assert "rule-2" not in caplog.text

    def test_the_build_logs_no_policy_wording(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            policy_index._warn_about_interleaved_text({"policy_key": "P1"}, self._group())

        assert CLEAN["english"] not in caplog.text
        assert DAMAGED["observed_latin_arabic"] not in caplog.text

    def test_a_clean_policy_produces_no_line_at_all(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            policy_index._warn_about_interleaved_text(
                {"policy_key": "P1"}, [("policy", CLEAN["arabic_quoting_english"])]
            )

        assert INTERLEAVED_TEXT_CODE not in caplog.text

    def test_the_group_the_build_indexes_is_untouched(self, caplog) -> None:
        """Informational only: the same texts are rendered either way."""

        group = self._group()
        before = [(key, text) for key, text in group]

        with caplog.at_level(logging.WARNING):
            policy_index._warn_about_interleaved_text({"policy_key": "P1"}, group)

        assert group == before

    def test_it_returns_nothing_a_caller_could_branch_on(self) -> None:
        """The shape of the guarantee.

        A function that returned a verdict would invite a caller to skip on it.
        There is nothing here to skip on.
        """

        assert (
            policy_index._warn_about_interleaved_text({"policy_key": "P1"}, self._group())
            is None
        )


async def _upload(http: AsyncClient, *, title: str, content: bytes):
    response = await http.post(
        "/api/documents/upload",
        params={"title": title, "owner": "reviewer"},
        files={"file": (f"{uuid.uuid4().hex}.pdf", content, "application/pdf")},
    )
    return response.status_code, (response.json() if response.content else {})


@pytest.mark.parametrize(
    "label,expect_warning",
    [("damaged", True), ("clean", False)],
    ids=["a damaged document warns", "a clean document does not"],
)
async def test_the_portal_upload_reports_it_and_carries_on_regardless(
    monkeypatch, label: str, expect_warning: bool
) -> None:
    """The route the portal actually posts to, both ways round.

    Two uploads through ``/api/documents/upload`` differing only in whether the
    extracted text is interleaved. The warning must appear in the response and
    in the stored version for the damaged one -- and the clause count, the
    stored clause text and the request's success must be identical to the clean
    one, because the user directed that this warning changes nothing.
    """

    scratch = Path("data") / "documents" / f"_interleaved_scratch_{uuid.uuid4().hex}"
    monkeypatch.setattr(documents_router, "_STORAGE_ROOT", scratch)

    body = DAMAGED["observed_latin_arabic"] if label == "damaged" else "One word here"
    produced = _document(f"Clause one: {body}", CLEAN["english"])
    monkeypatch.setattr(
        document_extraction,
        "get_settings",
        lambda: Settings(
            database_url="******localhost:5433/db",
            alembic_database_url="******localhost:5433/db",
            document_converter="legacy",
        ),
    )
    monkeypatch.setattr(document_extraction, "ingest_document", lambda *a, **k: produced)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            for table in (
                SourceDocument.__table__,
                DocumentVersion.__table__,
                Clause.__table__,
            ):
                await connection.run_sync(lambda c, t=table: t.create(c, checkfirst=True))

        maker = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app()

        async def _override():
            async with maker() as session:
                yield session

        app.dependency_overrides[get_session] = _override

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            status, response = await _upload(
                http, title="Interleaving probe", content=uuid.uuid4().bytes
            )

        # The upload succeeded either way. This is the informational-only
        # requirement at its sharpest: a warning is not a failure.
        assert status == 200
        assert not response.get("extraction_error")
        assert response.get("clause_count") == len(produced.elements)

        codes = {
            entry.get("code") for entry in (response.get("ingestion_diagnostics") or [])
        }
        assert (INTERLEAVED_TEXT_CODE in codes) is expect_warning

        async with maker() as session:
            version = (await session.execute(select(DocumentVersion))).scalars().one()
            clauses = (await session.execute(select(Clause))).scalars().all()

            # Durable, not just in the response body.
            stored = {
                entry.get("code") for entry in (version.ingestion_diagnostics_json or [])
            }
            assert (INTERLEAVED_TEXT_CODE in stored) is expect_warning
            assert version.ingestion_error in (None, "")

            # The clauses were persisted, and the damaged one was persisted
            # verbatim. Nothing was withheld, rewritten or reordered.
            assert len(clauses) == len(produced.elements)
            assert {clause.text for clause in clauses} == {
                element.text for element in produced.elements
            }

        await engine.dispose()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
