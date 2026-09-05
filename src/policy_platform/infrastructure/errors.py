"""Rendering an exception as something a person can act on.

One rule, in one place, because it is a rule about *recording* failures rather
than about any particular subsystem that has them.
"""
from __future__ import annotations


def describe_exception(exc: BaseException | None) -> str:
    """A description of ``exc`` that is never empty.

    WHY THIS EXISTS, AND IT IS NOT DEFENSIVENESS

    ``str(exc)`` is empty for a whole family of real failures. Every httpx
    transport and timeout class — ``ReadTimeout``, ``ConnectTimeout``,
    ``WriteTimeout``, ``PoolTimeout``, ``RemoteProtocolError``, ``ReadError`` —
    carries its meaning in its *type* and is routinely raised with no message at
    all, as do bare ``TimeoutError`` and ``OSError``. Rendering one of those with
    ``str()`` yields ``""``.

    An empty string is not a small loss of detail. Recorded as the reason a build
    failed it is indistinguishable from no reason having been recorded, which
    reads as "the process died before it could say anything" — a different
    diagnosis, pointing at a different repair, and one that costs hours to
    disprove. This has already happened here: an index rebuild recorded
    ``error=''`` and the emptiness itself became the thing to investigate.

    So the type is used when the message is absent. A caller that records what
    this returns can state, as an invariant, that a recorded failure always names
    something.

    ``None`` is accepted because retry loops hold their last failure in an
    optional and have to render it at the end. It is not passed through to
    ``str()``: that would yield the literal ``"None"``, which is non-empty and
    still says nothing — the exact failure this function exists to prevent,
    wearing a different disguise.
    """

    if exc is None:
        return "no exception was recorded"
    text = str(exc).strip()
    if text:
        return text
    return f"{type(exc).__module__}.{type(exc).__qualname__} (no message)"
