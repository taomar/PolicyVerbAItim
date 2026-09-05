"""What an upload reports about itself while it is still running.

An upload of a real policy document takes over a minute, and every fact about
what it was doing lived in local variables that died with the call. The page
could show a spinner and nothing else. `upload_progress` is the seam that lets
the handler say which stage it is in; these tests hold it to the two properties
that make such a readout worth having.

FIRST: it must be true. Not "roughly true" or "true once it finishes" —
every figure published has to be one the upload actually measured, and a figure
it has not measured has to be absent rather than zero. A progress display is
read by someone deciding whether to keep waiting, so a fabricated number is not
a cosmetic defect; it is the number they act on.

SECOND: it must not be able to change the outcome. Reporting is observation.
An upload with progress tracking and the identical upload without it must
produce the same clauses, the same diagnostics, the same index calls and the
same response — otherwise the act of watching has altered what is watched, and
every measurement taken here describes a run that only happens when observed.

The tests are organised as: the registry's own contract, then the route proving
both properties end to end through the real `/api/documents/upload`.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from policy_platform.api.routers import documents as documents_router
from policy_platform.contracts.canonical_document import (
    CanonicalDocument,
    CanonicalElement,
    SourceFragment,
)
from policy_platform.domain.models import Base
from policy_platform.infrastructure.ingestion import upload_progress
from policy_platform.infrastructure.ingestion.mixed_script_text import INTERLEAVED_TEXT_CODE
from policy_platform.infrastructure.persistence.db import get_session


# --------------------------------------------------------------------------
# sqlite shims, matching tests/unit/test_duplicate_content_is_announced_not_hidden.py
# --------------------------------------------------------------------------
@compiles(postgresql.JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ARG001
    return compiler.visit_JSON(JSON(), **kw)


@compiles(postgresql.UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # noqa: ANN001, ARG001
    return "CHAR(36)"


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test starts from an empty registry and leaves one behind.

    The registry is process-global by design, so without this a test could pass
    on a record another test wrote — which would make the whole file's evidence
    worthless.
    """

    upload_progress.clear()
    yield
    upload_progress.clear()


class TestTheRegistryOnlyReportsWhatItWasTold:
    """The registry's contract: it publishes measurements, never guesses."""

    def test_a_new_upload_knows_its_size_and_nothing_else_yet(self):
        upload_progress.start("op-1", file_bytes=4096)
        record = upload_progress.get("op-1")

        assert record is not None
        assert record["file_bytes"] == 4096
        assert record["status"] == "running"
        assert record["stage"] == "storing"
        # The three counts are None, not 0. This is the property the whole
        # readout rests on: "not measured yet" and "measured, and it is zero"
        # are different facts about a document, and a display that showed both
        # as 0 would report an unread document identically to an empty one.
        assert record["clause_count"] is None
        assert record["warning_count"] is None
        assert record["indexed_count"] is None

    def test_it_publishes_the_ordered_pipeline_so_the_client_holds_no_copy(self):
        upload_progress.start("op-1", file_bytes=1)
        record = upload_progress.get("op-1")

        assert record["stages"] == list(upload_progress.STAGES)
        assert record["stage_total"] == len(upload_progress.STAGES)
        # 1-based, so "step 1 of 5" is exactly true rather than off by one.
        assert record["stage_index"] == 1

    def test_the_step_number_tracks_the_stage(self):
        upload_progress.start("op-1", file_bytes=1)
        seen = []
        for name in upload_progress.STAGES:
            upload_progress.stage("op-1", name)
            seen.append(upload_progress.get("op-1")["stage_index"])

        # Strictly increasing and covering every step: a pipeline that reported
        # the same index twice, or skipped one, would draw a stage as reached
        # when it never was.
        assert seen == list(range(1, len(upload_progress.STAGES) + 1))

    def test_an_unknown_stage_is_ignored_rather_than_published(self):
        upload_progress.start("op-1", file_bytes=1)
        upload_progress.stage("op-1", "reading")
        upload_progress.stage("op-1", "teleporting")

        # The last real stage stands. Accepting an unknown name would put a
        # stage on screen that no client can render and no server produces.
        assert upload_progress.get("op-1")["stage"] == "reading"

    def test_counts_are_set_not_accumulated(self):
        """Assignment, so a retry cannot double a total.

        Each count published is a total the upload has just measured. If these
        accumulated, a stage that ran twice — a retry, a re-entered path — would
        report twice the clauses the document has.
        """

        upload_progress.start("op-1", file_bytes=1)
        upload_progress.update("op-1", clause_count=12)
        upload_progress.update("op-1", clause_count=12)

        assert upload_progress.get("op-1")["clause_count"] == 12

    def test_two_uploads_do_not_see_each_other(self):
        upload_progress.start("op-a", file_bytes=10)
        upload_progress.start("op-b", file_bytes=20)
        upload_progress.update("op-a", clause_count=5)
        upload_progress.stage("op-b", "indexing")

        a = upload_progress.get("op-a")
        b = upload_progress.get("op-b")

        assert a["file_bytes"] == 10 and a["clause_count"] == 5
        assert b["file_bytes"] == 20 and b["clause_count"] is None
        assert a["stage"] == "storing" and b["stage"] == "indexing"

    def test_an_unknown_operation_id_reads_as_nothing_tracked(self):
        # A poll that beats the handler, or arrives after pruning. Both are
        # normal, so this is None rather than an error the page would surface.
        assert upload_progress.get("never-started") is None

    def test_every_entry_point_is_total(self):
        """No call here may raise, whatever it is handed.

        The registry sits inside the upload's try block. A progress bug that
        raised would be caught by the handler's `except` and recorded as an
        extraction failure — the observation would have broken the thing it was
        observing, and the document would carry a permanent error saying so.
        """

        for call in (
            lambda: upload_progress.start("", file_bytes=0),
            lambda: upload_progress.stage("missing", "reading"),
            lambda: upload_progress.stage("missing", "nonsense"),
            lambda: upload_progress.update("missing", clause_count=1),
            lambda: upload_progress.update("missing", not_a_field=1),
            lambda: upload_progress.finish("missing"),
            lambda: upload_progress.fail("missing", "x"),
            lambda: upload_progress.get("missing"),
        ):
            call()  # must not raise

    def test_an_empty_operation_id_tracks_nothing(self):
        # The handler passes "" when the client sent no id. Tracking under a
        # blank key would let every untracked upload collide on one record.
        upload_progress.start("", file_bytes=99)
        assert upload_progress.get("") is None

    def test_unknown_update_keys_cannot_invent_a_field(self):
        upload_progress.start("op-1", file_bytes=1)
        upload_progress.update("op-1", clause_count=3, made_up=7)
        record = upload_progress.get("op-1")

        assert record["clause_count"] == 3
        assert "made_up" not in record

    def test_finishing_and_failing_are_the_only_terminal_writes(self):
        upload_progress.start("op-ok", file_bytes=1)
        upload_progress.finish("op-ok")
        upload_progress.start("op-bad", file_bytes=1)
        upload_progress.fail("op-bad", "PdfReadError: no /Root object")

        assert upload_progress.get("op-ok")["status"] == "completed"
        assert upload_progress.get("op-ok")["error"] is None
        assert upload_progress.get("op-bad")["status"] == "failed"
        assert upload_progress.get("op-bad")["error"] == "PdfReadError: no /Root object"

    def test_elapsed_is_measured_from_the_start_not_invented(self):
        upload_progress.start("op-1", file_bytes=1)
        first = upload_progress.get("op-1")["elapsed_seconds"]
        time.sleep(0.15)
        second = upload_progress.get("op-1")["elapsed_seconds"]

        assert first >= 0
        assert second >= first

    def test_a_finished_upload_is_retained_then_pruned(self, monkeypatch):
        """Retention, so the panel's last poll sees the outcome.

        A record dropped the instant the upload finished would vanish mid-poll
        and the panel would report "nothing tracked" for a run that had just
        succeeded — indistinguishable from one that never started.
        """

        upload_progress.start("op-1", file_bytes=1)
        upload_progress.finish("op-1")
        assert upload_progress.get("op-1")["status"] == "completed"

        # Age it past retention and write again: pruning happens on write, so a
        # stale record cannot accumulate indefinitely. The sleep is real elapsed
        # time rather than a mocked clock because Windows' `time.time()` moves in
        # ~16ms steps — with a zero cutoff and no wait, the finished record and
        # the cutoff can land on the same tick and the record survives for a
        # reason that has nothing to do with the retention rule.
        monkeypatch.setattr(upload_progress, "_RETENTION_SECONDS", 0)
        time.sleep(0.05)
        upload_progress.start("op-2", file_bytes=1)
        assert upload_progress.get("op-1") is None
        assert upload_progress.get("op-2") is not None

    def test_the_payload_carries_no_document_text(self):
        """Counts and stages only — never a word from the document.

        The record is served to the browser and printed in logs. A diagnostic's
        detail, a clause, or a passage of policy prose would put customer wording
        somewhere it was never meant to reach, and no progress readout needs it.

        The one free-text field is `error`, and it is bounded: see
        `TestTheRouteReportsItsRealStages.test_the_only_free_text_is_the_error_the_client_already_has`,
        which pins it to the same string the upload response already returns.
        """

        upload_progress.start("op-1", file_bytes=1)
        upload_progress.update("op-1", clause_count=3, warning_count=1)
        record = upload_progress.get("op-1")

        # Fixed field set, asserted whole. A new field carrying text would fail
        # here rather than silently shipping.
        assert set(record) == {
            "operation_id",
            "status",
            "stage",
            "stages",
            "stage_index",
            "stage_total",
            "file_bytes",
            "clause_count",
            "indexed_count",
            "warning_count",
            "has_interleaved_warning",
            "error",
            "started_at",
            "updated_at",
            "elapsed_seconds",
        }
        assert record["error"] is None
        for key, value in record.items():
            if key in {"stage", "stages", "status", "operation_id", "error"}:
                continue
            assert not isinstance(value, str), f"{key} carries free text"


# --------------------------------------------------------------------------
# The real route
# --------------------------------------------------------------------------
class _Recorder:
    """Counts what the upload did, so two runs can be compared exactly."""

    def __init__(self) -> None:
        self.index_calls: list[dict[str, Any]] = []


@pytest.fixture
async def app_and_recorder(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_connection, _record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    recorder = _Recorder()

    async def _fake_index(**kwargs):
        recorder.index_calls.append(kwargs)
        return len(kwargs.get("clauses") or [])

    monkeypatch.setattr(documents_router, "index_clauses_best_effort", _fake_index)
    monkeypatch.setattr(documents_router, "_STORAGE_ROOT", tmp_path / "documents")

    app = FastAPI()
    app.include_router(documents_router.router)

    async def _session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _session

    yield app, recorder

    await engine.dispose()


def _pdf_bytes(marker: str) -> bytes:
    """Bytes no parser will read. The parse failing is not what is under test —
    what is under test is that the stages, the response and the stored version
    are identical whether or not progress was watched."""

    return f"%PDF-1.4 not-a-real-pdf {marker}".encode()


async def _upload(app, *, title: str, operation_id: str | None, marker: str) -> dict:
    params = {"title": title, "owner": "tester"}
    if operation_id is not None:
        params["operation_id"] = operation_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/documents/upload",
            params=params,
            files={"file": (f"{title}.pdf", _pdf_bytes(marker), "application/pdf")},
        )
    assert response.status_code == 200, response.text
    return response.json()


# A Latin sentence zipped codepoint-by-codepoint with an Arabic one -- the exact
# shape of damage the detector exists to report, reproduced here so a successful
# parse can be observed carrying a warning without any corpus text.
_INTERLEAVED = "O\u0631n\u062ee\u0623 t\u0647h\u0630e\u0627 p\u0644o\u0645l\u0646i\u0632c\u0647y"


def _canonical(*texts: str) -> CanonicalDocument:
    """A real `CanonicalDocument`, mirroring the builder in
    `test_interleaved_extraction_is_reported.py`.

    Deliberately a genuine contract object rather than a mock: it lets
    `clauses_from_document`, `ingestion_warnings` and the interleave detector all
    run for real, so the stages this test watches are the ones production runs.
    Only the file parse is replaced, because bytes a parser will read cannot be
    synthesised here.
    """
    elements = [
        CanonicalElement(
            element_id=f"E{index:06d}",
            element_type="paragraph",
            logical_order=index,
            text=text,
            source_fragments=[
                SourceFragment(page=1, start_offset=0, end_offset=len(text), text=text)
            ],
        )
        for index, text in enumerate(texts)
    ]
    return CanonicalDocument(
        document_id="d",
        source_hash="a" * 64,
        parser="test",
        page_count=1,
        elements=elements,
    )


def _stub_parse(monkeypatch, *texts: str, before=None):
    """Replace only the *parser*, keeping the whole of `extract_document` real.

    The seam matters, and getting it wrong hid a real behaviour once already.
    Stubbing `extract_document` itself skips both fidelity checks it performs
    after parsing — display glyphs and interleaved text — because those run
    inside it, deliberately, so that every caller is told without carrying its
    own copy of the rule. A test that replaced the whole function could never
    observe the warning it claimed to be measuring.

    Patching `ingest_document` instead replaces only the step that turns bytes
    into elements, which is the one part that cannot be synthesised from a
    string. Everything the route depends on afterwards — the detectors, the
    diagnostics list, `clauses_from_document` — is production code.

    `before` runs on the worker thread as the parse begins, which is what lets a
    test hold the route at a known stage and read the panel's view of it.
    """

    def _fake(*_args, **_kwargs):
        if before is not None:
            before()
        return _canonical(*texts)

    monkeypatch.setattr(documents_router.document_extraction, "ingest_document", _fake)


def _stub_one_clause(monkeypatch):
    _stub_parse(monkeypatch, "A clause with enough words in it to be kept by the extractor.")


class TestWatchingAnUploadDoesNotChangeIt:
    """The property that makes every other measurement here meaningful."""
    async def test_the_same_upload_with_and_without_progress_is_identical(
        self, app_and_recorder
    ):
        app, recorder = app_and_recorder

        watched = await _upload(app, title="watched", operation_id="op-1", marker="x")
        unwatched = await _upload(app, title="unwatched", operation_id=None, marker="x")

        def _work_only(body: dict) -> dict:
            """Everything describing the work, with the row's identity removed.

            The identifiers necessarily differ between two uploads, and the
            extraction error names the stored file — whose name is built from
            those identifiers. Stripping the filename leaves the part that says
            what actually went wrong, which is the part that must match.
            """

            stored = body["storage_path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            kept = {
                key: value
                for key, value in body.items()
                if key
                not in {
                    "document_id",
                    "document_version_id",
                    "storage_path",
                    "content_already_present",
                }
            }
            if kept.get("extraction_error"):
                kept["extraction_error"] = kept["extraction_error"].replace(stored, "<file>")
            return kept

        assert _work_only(watched) == _work_only(unwatched)
    async def test_an_upload_without_an_operation_id_still_succeeds(self, app_and_recorder):
        app, _ = app_and_recorder
        body = await _upload(app, title="plain", operation_id=None, marker="y")

        assert body["version_number"] == 1
        # And nothing was tracked, so an untracked upload leaves no record for a
        # later poll to find and misattribute.
        assert upload_progress.get("") is None


class TestTheRouteReportsItsRealStages:
    async def test_it_records_the_upload_under_the_id_the_client_sent(
        self, app_and_recorder
    ):
        app, _ = app_and_recorder
        operation_id = str(uuid.uuid4())
        await _upload(app, title="tracked", operation_id=operation_id, marker="z")

        record = upload_progress.get(operation_id)
        assert record is not None
        assert record["file_bytes"] == len(_pdf_bytes("z"))
        # This body cannot be parsed, so the upload records a read failure — and
        # records it with a description rather than an empty string.
        assert record["status"] == "failed"
        assert record["error"]
        assert record["error"].strip()
    async def test_a_failed_read_is_recorded_but_the_upload_still_returns(
        self, app_and_recorder
    ):
        app, _ = app_and_recorder
        operation_id = str(uuid.uuid4())
        body = await _upload(app, title="unreadable", operation_id=operation_id, marker="q")

        # The deliberate availability behaviour: the version is stored and
        # returned even though extraction failed.
        assert body["document_version_id"]
        assert body["extraction_error"]
        assert upload_progress.get(operation_id)["status"] == "failed"
    async def test_the_progress_endpoint_serves_only_the_asked_for_upload(
        self, app_and_recorder
    ):
        app, _ = app_and_recorder
        await _upload(app, title="one", operation_id="op-one", marker="1")
        await _upload(app, title="two", operation_id="op-two", marker="2")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            one = (await client.get("/api/documents/upload-progress/op-one")).json()
            two = (await client.get("/api/documents/upload-progress/op-two")).json()
            absent = (await client.get("/api/documents/upload-progress/op-none")).json()

        assert one["active"] and one["operation_id"] == "op-one"
        assert two["active"] and two["operation_id"] == "op-two"
        # Not an error and not a 404: a poll for an upload that was never made,
        # or whose record has been pruned, is a normal state the panel handles
        # by falling back to its own clock.
        assert absent == {"active": False}
    async def test_the_only_free_text_is_the_error_the_client_already_has(
        self, app_and_recorder
    ):
        """The endpoint must not become a second, more revealing channel.

        `error` is genuinely free text — a parser failure has to be described or
        the reviewer sees a blank where the reason should be. What it must not
        do is say more than the upload response already said to the same client.
        Pinning the two to the identical string means this endpoint discloses
        nothing new, so the field can carry a real description without becoming
        a leak of its own.
        """

        app, _ = app_and_recorder
        body = await _upload(app, title="checked", operation_id="op-text", marker="t")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            progress = (await client.get("/api/documents/upload-progress/op-text")).json()

        assert body["extraction_error"]
        assert progress["error"] == body["extraction_error"]

        # And every other field is still a number, a bool, or a stage name.
        for key, value in progress.items():
            if key in {"stage", "stages", "status", "operation_id", "error", "active"}:
                continue
            assert not isinstance(value, str), f"{key} carries free text"

    async def test_clause_text_and_diagnostic_detail_never_reach_the_endpoint(
        self, app_and_recorder
    ):
        """The counts travel; the words they count do not.

        A diagnostic's `detail` names a page and a clause and is written for a
        reviewer; a clause is policy prose. Both are returned by the upload
        response to the uploader, and neither belongs on a polling endpoint that
        a browser hits once a second and a proxy may log.
        """

        app, _ = app_and_recorder
        body = await _upload(app, title="detail", operation_id="op-detail", marker="d")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            progress = (await client.get("/api/documents/upload-progress/op-detail")).json()

        serialised = str(progress)
        for diagnostic in body.get("ingestion_diagnostics") or []:
            detail = diagnostic.get("detail")
            if detail:
                assert detail not in serialised


class TestTheParseDoesNotBlockTheReadout:
    """The reason the parse moved to a worker thread.

    `extract_document` is synchronous and runs for over a minute on a real
    document. While it held the event loop, no progress poll could be served —
    the panel froze for precisely the stage it most needed to report, which is
    the failure mode this whole surface exists to remove.
    """
    async def test_a_poll_is_answered_while_the_document_is_being_read(
        self, app_and_recorder, monkeypatch
    ):
        app, _ = app_and_recorder
        started = asyncio.Event()
        release = asyncio.Event()
        loop = asyncio.get_running_loop()

        real_extract = documents_router.document_extraction.extract_document

        def _slow_extract(*args, **kwargs):
            # Runs on the worker thread. Signalling back through the loop is how
            # the test learns the parse is in flight without touching loop state
            # from the wrong thread.
            loop.call_soon_threadsafe(started.set)
            # Block the way a real parse does: synchronously, holding this
            # thread. If this were on the event loop, the poll below would never
            # be served and the test would time out.
            while not release.is_set():
                time.sleep(0.01)
            return real_extract(*args, **kwargs)

        monkeypatch.setattr(
            documents_router.document_extraction, "extract_document", _slow_extract
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            upload = asyncio.create_task(
                client.post(
                    "/api/documents/upload",
                    params={"title": "slow", "owner": "tester", "operation_id": "op-slow"},
                    files={"file": ("slow.pdf", _pdf_bytes("s"), "application/pdf")},
                )
            )
            await asyncio.wait_for(started.wait(), timeout=10)

            # The parse is running right now. This is the assertion the whole
            # threading change exists for.
            mid = await asyncio.wait_for(
                client.get("/api/documents/upload-progress/op-slow"), timeout=5
            )
            body = mid.json()

            release.set()
            await asyncio.wait_for(upload, timeout=20)

        assert body["active"] is True
        assert body["stage"] == "reading"
        assert body["status"] == "running"


class TestEveryExitLeavesTheRecordTerminal:
    """The defect this guards is quiet and long-lived.

    Finished records are retained for minutes so the last poll can still read
    them. So an upload that exits without ending its record does not merely lose
    a reading — it leaves the page reporting a stage, with a spinner, for an
    upload that stopped minutes ago. That is worse than showing nothing, and it
    is precisely the failure this surface was built to remove.

    Only the extraction body has an `except`. Between the start of tracking and
    that `try` sit a directory creation, a file write, two flushes; after it sit
    a commit and the indexing call. `tracking` is a context manager so that
    terminality is structural rather than remembered: a statement added to this
    route later is inside the guard by construction.
    """

    async def test_a_refused_duplicate_leaves_no_record_at_all(self, app_and_recorder):
        """A refusal is not a run.

        The 409 fires before tracking begins, deliberately. An identical
        re-upload answered "you already have this" never started work, and
        recording it would put a phantom upload on the reader's screen — one
        that never ran, cannot progress, and did not fail.
        """
        app, _ = app_and_recorder
        first = await _upload(app, title="dup", operation_id="op-dup-1", marker="same")
        assert first["document_version_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            second = await client.post(
                "/api/documents/upload",
                params={"title": "dup", "owner": "tester", "operation_id": "op-dup-2"},
                files={"file": ("dup.pdf", _pdf_bytes("same"), "application/pdf")},
            )

        assert second.status_code == 409, second.text
        # No record at all, not a record saying "inactive": the registry never
        # heard of this operation, which is the honest state for work that was
        # refused before it began.
        assert upload_progress.get("op-dup-2") is None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            polled = await client.get("/api/documents/upload-progress/op-dup-2")
        # And what a reader polling that id sees: nothing running.
        assert polled.json() == {"active": False}

    async def test_a_failed_storage_write_ends_the_record_and_still_raises(
        self, app_and_recorder, monkeypatch
    ):
        """The first exit after tracking begins, and the one with no `except`."""
        app, _ = app_and_recorder

        def _no_disk(self, _content):  # noqa: ANN001, ARG001
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(Path, "write_bytes", _no_disk)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with pytest.raises(OSError):
                await client.post(
                    "/api/documents/upload",
                    params={"title": "disk", "owner": "tester", "operation_id": "op-disk"},
                    files={"file": ("disk.pdf", _pdf_bytes("d"), "application/pdf")},
                )

        record = upload_progress.get("op-disk")
        assert record["status"] == "failed"
        # Non-empty, because several exceptions stringify to nothing and an empty
        # error reads to a reader as "no error" — the opposite of the truth.
        assert record["error"]
        assert "No space left on device" in record["error"]

    async def test_an_unexpected_exception_after_the_parse_is_terminal(
        self, app_and_recorder, monkeypatch
    ):
        """The exits *after* the extraction `try/except` — commit and indexing.

        This is the case that motivated a context manager over patching each
        exit: nobody adding a call here later has to remember to end the record.
        """
        app, _ = app_and_recorder

        async def _index_explodes(**_kwargs):
            raise RuntimeError("search client unreachable")

        monkeypatch.setattr(documents_router, "index_clauses_best_effort", _index_explodes)

        # Force the indexing branch to be reached at all: it only runs when the
        # parse produced clauses, and the sentinel bytes above produce none.
        _stub_one_clause(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with pytest.raises(RuntimeError):
                await client.post(
                    "/api/documents/upload",
                    params={"title": "idx", "owner": "tester", "operation_id": "op-idx"},
                    files={"file": ("idx.pdf", _pdf_bytes("i"), "application/pdf")},
                )

        record = upload_progress.get("op-idx")
        assert record["status"] == "failed"
        assert "search client unreachable" in (record["error"] or "")

    async def test_a_failed_parse_keeps_its_own_verdict(self, app_and_recorder):
        """A clean exit must not overwrite a `fail` already recorded.

        The upload succeeded — HTTP 200, the version is stored — but extraction
        did not. Those are different facts. If the context manager finished the
        record unconditionally, the panel would report a green completed run for
        a document whose text was never read.
        """
        app, _ = app_and_recorder
        body = await _upload(app, title="badparse", operation_id="op-bad", marker="b")

        assert body["extraction_error"]
        record = upload_progress.get("op-bad")
        assert record["status"] == "failed"
        assert record["error"] == body["extraction_error"]

    async def test_a_disconnected_client_ends_the_record(self, app_and_recorder, monkeypatch):
        """A reader who closes the tab mid-parse is a real ending.

        Cancellation arrives as `BaseException`, not `Exception`, so a guard
        catching only the latter would leave exactly the longest-running uploads
        — the ones most likely to be abandoned — stuck reporting "reading"
        forever.
        """
        app, _ = app_and_recorder
        started = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _never_finishes(*_args, **_kwargs):
            loop.call_soon_threadsafe(started.set)
            time.sleep(30)
            raise AssertionError("should have been cancelled")

        monkeypatch.setattr(
            documents_router.document_extraction, "extract_document", _never_finishes
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            request = asyncio.create_task(
                client.post(
                    "/api/documents/upload",
                    params={"title": "gone", "owner": "tester", "operation_id": "op-gone"},
                    files={"file": ("gone.pdf", _pdf_bytes("g"), "application/pdf")},
                )
            )
            await asyncio.wait_for(started.wait(), timeout=10)
            request.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await request

        record = upload_progress.get("op-gone")
        assert record["status"] == "failed", record
        assert record["error"]

    async def test_the_http_outcome_is_unchanged_by_tracking(self, app_and_recorder):
        """`tracking` records and re-raises; it decides nothing.

        The same refusal and the same success are returned whether or not an
        operation id was supplied, so no reader's result depends on whether the
        page happened to be watching.
        """
        app, _ = app_and_recorder
        watched = await _upload(app, title="w", operation_id="op-w", marker="x")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unwatched_dup = await client.post(
                "/api/documents/upload",
                params={"title": "w", "owner": "tester"},
                files={"file": ("w.pdf", _pdf_bytes("x"), "application/pdf")},
            )
            watched_dup = await client.post(
                "/api/documents/upload",
                params={"title": "w", "owner": "tester", "operation_id": "op-w2"},
                files={"file": ("w.pdf", _pdf_bytes("x"), "application/pdf")},
            )

        assert unwatched_dup.status_code == watched_dup.status_code == 409
        assert unwatched_dup.json()["detail"] == watched_dup.json()["detail"]
        assert watched["extraction_error"]


class TestASuccessfulUploadReportsItsRealSequence:
    """The tests above prove the record always ends. These prove what a reader
    sees on the way there, on a document that actually parses.

    A malformed PDF exercises the failure path and little else: it never reaches
    checking, saving or indexing, so a pipeline that reported those stages in the
    wrong order, or attached counts to the wrong step, would pass every test
    written against it. Here the parse succeeds and is held at a barrier, so each
    stage is observed while it is the current one.
    """

    async def _watch(self, app, *, title: str, operation_id: str, texts, at_parse=None):
        """Run one upload, capturing polls taken while the parse is held."""
        seen: list[dict[str, Any]] = []
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            task = asyncio.create_task(
                client.post(
                    "/api/documents/upload",
                    params={"title": title, "owner": "tester", "operation_id": operation_id},
                    files={"file": (f"{title}.pdf", _pdf_bytes(title), "application/pdf")},
                )
            )
            if at_parse is not None:
                await asyncio.wait_for(at_parse["started"].wait(), timeout=10)
                poll = await client.get(f"/api/documents/upload-progress/{operation_id}")
                seen.append(poll.json())
                at_parse["release"].set()
            response = await asyncio.wait_for(task, timeout=30)
            final = await client.get(f"/api/documents/upload-progress/{operation_id}")
        seen.append(final.json())
        assert response.status_code == 200, response.text
        return response.json(), seen

    async def test_the_stages_advance_in_order_and_counts_appear_with_them(
        self, app_and_recorder, monkeypatch
    ):
        app, recorder = app_and_recorder
        started, release = asyncio.Event(), asyncio.Event()
        loop = asyncio.get_running_loop()

        def _barrier():
            loop.call_soon_threadsafe(started.set)
            while not release.is_set():
                time.sleep(0.01)

        _stub_parse(
            monkeypatch,
            "The insurer shall maintain records of every claim for seven years.",
            "Premiums are payable monthly in advance on the first business day.",
            before=_barrier,
        )

        body, seen = await self._watch(
            app,
            title="ok",
            operation_id="op-ok",
            texts=None,
            at_parse={"started": started, "release": release},
        )
        mid, final = seen[0], seen[1]

        # Mid-parse: reading, and no count yet claimed for work not yet done.
        assert mid["stage"] == "reading"
        assert mid["status"] == "running"
        # `None`, not 0. "Not measured yet" and "none found" must not render
        # identically -- a document nobody has read and an empty one are
        # different facts about the source.
        assert mid["clause_count"] is None
        assert mid["indexed_count"] is None

        # Final: the pipeline ran to its end.
        assert final["status"] == "completed"
        assert final["stage"] == "indexing"
        assert final["stage_index"] == final["stage_total"]
        assert mid["stage_index"] < final["stage_index"]

        # The counts the panel shows are the counts the response returned. If
        # these could differ, the panel would be a second, disagreeing account of
        # the same upload.
        assert final["clause_count"] == body["clause_count"] == 2
        assert final["indexed_count"] == body["clauses_search_indexed"] == 2
        assert recorder.index_calls and len(recorder.index_calls[0]["clauses"]) == 2
        assert body["extraction_error"] is None

    async def test_the_interleaved_warning_is_reported_and_changes_nothing(
        self, app_and_recorder, monkeypatch
    ):
        """The warning is informational, and this is where that is measured.

        Two uploads of the same document differing only in one damaged element:
        the warning appears, and the clause count, the indexing call and the
        extraction outcome are identical. If the detector ever began gating,
        filtering or reordering anything, these equalities are what would break.
        """
        app, recorder = app_and_recorder
        clean = "The insurer shall maintain records of every claim for seven years."

        _stub_parse(monkeypatch, clean, "A second ordinary clause of sufficient length here.")
        without, _ = await self._watch(app, title="cleanrun", operation_id="op-c", texts=None)
        clean_progress = upload_progress.get("op-c")
        clean_calls = len(recorder.index_calls)
        clean_indexed = recorder.index_calls[-1]["clauses"]

        _stub_parse(monkeypatch, clean, _INTERLEAVED)
        withwarn, _ = await self._watch(app, title="warnrun", operation_id="op-w", texts=None)
        warn_progress = upload_progress.get("op-w")

        assert warn_progress["has_interleaved_warning"] is True
        assert clean_progress["has_interleaved_warning"] is False
        assert warn_progress["warning_count"] > clean_progress["warning_count"]
        assert any(
            d["code"] == INTERLEAVED_TEXT_CODE for d in withwarn["ingestion_diagnostics"]
        )
        assert not any(
            d["code"] == INTERLEAVED_TEXT_CODE for d in without["ingestion_diagnostics"]
        )
        # "Informational" does not mean invisible — the reviewer is *supposed* to
        # see a marker, and the status is derived from the diagnostics precisely
        # so they do. What it means is that nothing was withheld or failed: the
        # status is a warning rather than an error, and the clause and index
        # outcomes asserted below are untouched.
        assert withwarn["ingestion_status"] == "warning"
        assert without["ingestion_status"] == "ok"

        # Everything that is not the warning is unchanged.
        assert withwarn["clause_count"] == without["clause_count"]
        assert withwarn["clauses_search_indexed"] == without["clauses_search_indexed"]
        assert withwarn["extraction_error"] is None and without["extraction_error"] is None
        assert len(recorder.index_calls) == clean_calls + 1
        assert len(recorder.index_calls[-1]["clauses"]) == len(clean_indexed)
        assert warn_progress["status"] == clean_progress["status"] == "completed"

        # The damaged text reached storage exactly as extracted. The detector
        # reports; it never rewrites.
        indexed_texts = [c.text for c in recorder.index_calls[-1]["clauses"]]
        assert _INTERLEAVED in indexed_texts

    async def test_the_counts_never_go_backwards(self, app_and_recorder, monkeypatch):
        """Polled repeatedly across a whole upload, no figure ever decreases.

        A count that falls is the reading a reader cannot interpret: it says the
        work undid itself. Stage position and both counters are checked together
        because a stage that advanced while a count reset would be just as
        unreadable as either alone.
        """
        app, _ = app_and_recorder
        started, release = asyncio.Event(), asyncio.Event()
        loop = asyncio.get_running_loop()

        def _barrier():
            loop.call_soon_threadsafe(started.set)
            while not release.is_set():
                time.sleep(0.01)

        _stub_parse(monkeypatch, "One sufficiently long clause of ordinary policy text.", before=_barrier)

        readings: list[dict[str, Any]] = []
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            task = asyncio.create_task(
                client.post(
                    "/api/documents/upload",
                    params={"title": "mono", "owner": "tester", "operation_id": "op-mono"},
                    files={"file": ("mono.pdf", _pdf_bytes("m"), "application/pdf")},
                )
            )
            await asyncio.wait_for(started.wait(), timeout=10)
            for _ in range(3):
                readings.append(
                    (await client.get("/api/documents/upload-progress/op-mono")).json()
                )
            release.set()
            await asyncio.wait_for(task, timeout=30)
            for _ in range(2):
                readings.append(
                    (await client.get("/api/documents/upload-progress/op-mono")).json()
                )

        def _seq(field: str) -> list[int]:
            return [r[field] for r in readings if r.get(field) is not None]

        for field in ("stage_index", "clause_count", "indexed_count"):
            values = _seq(field)
            assert values == sorted(values), f"{field} went backwards: {values}"

    async def test_watching_a_successful_upload_does_not_change_it(
        self, app_and_recorder, monkeypatch
    ):
        """The control for this whole class, on the success path.

        The earlier version of this proof used a document that failed to parse,
        so it compared two identical failures. This compares two identical
        successes, including what was handed to the search index.
        """
        app, recorder = app_and_recorder
        texts = ("A clause of ordinary length and content.", _INTERLEAVED)

        _stub_parse(monkeypatch, *texts)
        watched, _ = await self._watch(app, title="a", operation_id="op-a", texts=None)

        _stub_parse(monkeypatch, *texts)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unwatched_response = await client.post(
                "/api/documents/upload",
                params={"title": "b", "owner": "tester"},
                files={"file": ("b.pdf", _pdf_bytes("b"), "application/pdf")},
            )
        unwatched = unwatched_response.json()

        def _comparable(body: dict) -> dict:
            # Ids and storage paths differ by construction. So does
            # `content_hash`: the two uploads must carry different bytes or the
            # second would be refused as a duplicate before it ran, which would
            # test nothing. What must not differ is everything describing what
            # the upload *did* — and the clause texts handed to the index are
            # compared separately below, which is the stronger of the two checks.
            return {
                k: v
                for k, v in body.items()
                if k not in {"document_id", "document_version_id", "storage_path", "content_hash"}
            }

        assert _comparable(watched) == _comparable(unwatched)
        assert len(recorder.index_calls) == 2
        first, second = recorder.index_calls
        assert [c.text for c in first["clauses"]] == [c.text for c in second["clauses"]]
        assert first["content_hash"] != second["content_hash"]
