"""Live progress for an in-flight document upload.

Why this module exists
----------------------
`upload_document` does five distinct things in one request: it stores the file,
reads the whole document, checks the extracted text for ingestion problems,
saves the clauses, and indexes them for search. On a real policy document the
reading alone runs well past a minute. All of that knowledge — which stage, how
many clauses, how many warnings — existed only in local variables and died with
the call, because the HTTP response is the single output channel and it does not
exist until every stage has finished. The page could show a spinner and an
elapsed clock, and nothing else: a reviewer could not tell a slow parse from a
hung one, or know whether the wait was in the parser or in the search index.

This is the same boundary `extraction_progress` draws for AI extraction, built
the same way and for the same reason: the router publishes what it is doing, the
API reads it back, and neither learns about the other.

TRUTHFUL, OR ABSENT
-------------------
Every number here is one the upload actually knows. There is deliberately no
percentage-of-total, because the request has no denominator until the parse ends
— the clause count is unknown until the document has been read. A stage the
caller cannot measure publishes no figure at all and the reader shows
indeterminate motion, which is honest, rather than a bar interpolated from
elapsed time, which is a guess presented as a measurement.

The stage sequence is fixed and ordered, so "step N of M" is exactly true even
while no stage has a count of its own.

NO POLICY TEXT
--------------
Counts, stage names, timestamps and a failure description. Never a clause, a
title, a filename's contents, a diagnostic's detail or anything derived from the
document's words. The record is served to the browser and written to logs, and a
progress readout is not a place customer wording should reach.

Why in-memory
-------------
Observation telemetry, not a source of truth. The authoritative record of an
upload is the committed `DocumentVersion` and its clauses; losing progress has no
correctness consequence — worst case the panel falls back to the elapsed clock,
which is exactly the previous behaviour.

KNOWN LIMITATION (accepted, deliberate, same as `extraction_progress`): the
registry is per-process, so a poll served by a different uvicorn worker than the
one running the upload sees nothing. Fixing that needs a shared store and should
wait until multi-worker deployment is real.

INVARIANT: reporting must never change an upload's outcome. Every function here
is total — it does not raise, validate, or return anything a caller branches on.
A progress bug must not be able to fail an upload.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Final

from policy_platform.infrastructure.errors import describe_exception

__all__ = [
    "STAGES",
    "UploadProgress",
    "clear",
    "fail",
    "finish",
    "get",
    "start",
    "stage",
    "update",
]

#: Uploads older than this are dropped on the next write. A finished upload is
#: kept briefly so the panel's last poll shows the terminal state rather than
#: the record vanishing mid-animation.
_RETENTION_SECONDS: Final[int] = 10 * 60

#: The ordered pipeline, as stable keys. The reader turns these into labels, so
#: wording can change without breaking a client, and "step N of M" is computed
#: from this tuple rather than hard-coded in two places.
#:
#: `storing` is first because the bytes have already arrived by the time the
#: handler runs — the browser's own upload is a separate phase the client times
#: for itself, since only the transport knows how much of the body has been sent.
STAGES: Final[tuple[str, ...]] = (
    "storing",
    "reading",
    "checking",
    "saving",
    "indexing",
)


@dataclass
class UploadProgress:
    """One upload's ordered stage, its known counts and its terminal state."""

    operation_id: str
    #: "running", "completed" or "failed". Only `finish` and `fail` write the
    #: terminal two, so a reader can stop polling on them without guessing.
    status: str = "running"
    #: Which of `STAGES` is happening now. Kept as a key, not a sentence.
    stage: str = STAGES[0]
    #: Size of the received body. Known before any work starts, and the one
    #: figure that says whether a long read is a big document or a stuck one.
    file_bytes: int = 0
    #: Counts, each `None` until the stage that produces it has run. `None` is
    #: load-bearing and distinct from 0: "not known yet" and "none found" are
    #: different facts, and a reader that showed both as 0 would report a
    #: document with no clauses identically to one that has not been read.
    clause_count: int | None = None
    indexed_count: int | None = None
    warning_count: int | None = None
    #: True once a residual-interleaving warning is among them, so the panel can
    #: name the finding while the upload carries on. Informational only: nothing
    #: in this module or its callers branches on it.
    has_interleaved_warning: bool = False
    #: Set when the document could not be read. The upload still succeeds and
    #: still stores the version — this records that extraction did not.
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["stages"] = list(STAGES)
        # 1-based, so the client renders "step 2 of 5" without knowing the
        # tuple's indexing. An unrecognised stage yields 0, which reads as
        # "not one of the known steps" rather than silently pointing at the
        # first one.
        payload["stage_index"] = (
            STAGES.index(self.stage) + 1 if self.stage in STAGES else 0
        )
        payload["stage_total"] = len(STAGES)
        payload["elapsed_seconds"] = round(time.time() - self.started_at, 1)
        return payload


#: operation_id -> latest record. Keyed by an id the *client* generates and
#: sends with the POST, because the client cannot learn any server-side id until
#: the response arrives — which is after the work it wanted to watch has ended.
_UPLOADS: dict[str, UploadProgress] = {}


def _prune() -> None:
    cutoff = time.time() - _RETENTION_SECONDS
    for key in [k for k, v in _UPLOADS.items() if v.updated_at < cutoff]:
        _UPLOADS.pop(key, None)


def start(operation_id: str, *, file_bytes: int) -> None:
    """Begin (or restart) tracking one upload."""

    if not operation_id:
        return
    _prune()
    _UPLOADS[operation_id] = UploadProgress(
        operation_id=operation_id, file_bytes=file_bytes
    )


def stage(operation_id: str, name: str) -> None:
    """Move to a named stage. Unknown ids and unknown stages are ignored."""

    record = _UPLOADS.get(operation_id)
    if record is None or name not in STAGES:
        return
    record.stage = name
    record.updated_at = time.time()


def update(operation_id: str, **changes) -> None:
    """Set known counters. Unknown keys and unknown ids are ignored.

    Deliberately assignment rather than accumulation: each of these is a total
    the upload has just measured, not a delta, so setting it twice with the same
    value is harmless and a retry cannot double a count.
    """

    record = _UPLOADS.get(operation_id)
    if record is None:
        return
    for key, value in changes.items():
        if hasattr(record, key):
            setattr(record, key, value)
    record.updated_at = time.time()


def finish(operation_id: str) -> None:
    """Record success. Retained briefly so the last poll sees the outcome."""

    record = _UPLOADS.get(operation_id)
    if record is None:
        return
    record.status = "completed"
    record.updated_at = time.time()


def fail(operation_id: str, error: str) -> None:
    """Record that reading the document did not complete, and why.

    The caller passes a description produced by `describe_exception`, so an
    exception whose ``str()`` is empty still records something a reader can act
    on rather than an empty string that looks like no error at all.
    """

    record = _UPLOADS.get(operation_id)
    if record is None:
        return
    record.status = "failed"
    record.error = error
    record.updated_at = time.time()


def get(operation_id: str) -> dict | None:
    record = _UPLOADS.get(operation_id)
    return record.as_dict() if record else None


@contextmanager
def tracking(operation_id: str, *, file_bytes: int) -> Iterator[None]:
    """Track one upload, and guarantee the record ends in a terminal state.

    WHY THIS IS A CONTEXT MANAGER AND NOT A PAIR OF CALLS

    The handler has many exits after tracking begins: a storage write that
    fails, a database flush that fails, a commit that fails, a client that
    disconnects mid-parse, or any exception nobody has thought of yet. With
    `start` and `finish` written as two ordinary calls, every one of those exits
    leaves a record saying `running` — and because finished records are retained
    for several minutes so the last poll can read them, the page goes on
    reporting "step 1 of 5, reading" for an upload that failed and returned
    minutes ago. That is precisely the defect this surface exists to remove: a
    display that says work is happening when it is not.

    Wrapping the region makes terminality structural instead of remembered. A
    statement added to the handler later is inside the guard by construction, so
    the hole cannot be reopened by an edit that simply forgets.

    IT DOES NOT CHANGE THE OUTCOME

    The exception is never swallowed — it is recorded and re-raised — so the
    HTTP result is exactly what it would have been without tracking. On a clean
    exit the record is only completed if it is still running: a handler that has
    already called `fail` (extraction failed, but the version is stored and
    returned anyway) keeps that verdict rather than having it overwritten with
    success.
    """

    start(operation_id, file_bytes=file_bytes)
    try:
        yield
    except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
        # `BaseException` deliberately: a cancelled request — the reviewer closed
        # the tab during a long parse — is one of the ways an upload really ends,
        # and it must not be the one that leaves a record running forever.
        record = _UPLOADS.get(operation_id)
        if record is not None and record.status == "running":
            fail(operation_id, describe_exception(exc))
        raise
    else:
        record = _UPLOADS.get(operation_id)
        if record is not None and record.status == "running":
            finish(operation_id)


def clear() -> None:
    """Test hook — drop all tracked uploads."""

    _UPLOADS.clear()
