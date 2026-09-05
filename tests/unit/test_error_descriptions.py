from __future__ import annotations

import httpx
import pytest

from policy_platform.infrastructure.errors import describe_exception


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout(""),
        httpx.ConnectTimeout(""),
        httpx.WriteTimeout(""),
        httpx.PoolTimeout(""),
        httpx.RemoteProtocolError(""),
        httpx.ReadError(""),
        TimeoutError(),
        OSError(),
    ],
)
def test_a_message_less_exception_is_still_described(exc):
    """These are the exceptions that read as silence.

    Every one of them stringifies to `''`. That is not a quirk to work around,
    it is the design: their meaning is carried by the type, not the message. So
    `str(exc)` on any of them produces a record that says a failure happened and
    declines to say what - which is exactly how a real rebuild came to record
    `status=failed` beside `error=''` and cost hours of investigation into a
    process death that had not occurred.
    """

    assert str(exc) == "", "premise check: this exception is expected to be message-less"

    described = describe_exception(exc)

    assert described.strip(), "a message-less exception was described as nothing"
    assert type(exc).__name__ in described, (
        f"the description must name the failure; got {described!r}"
    )


def test_an_exception_that_speaks_is_quoted_not_relabelled():
    """The control: the helper is not simply replacing everything with a type name.

    When an exception does carry a message, that message is the most specific
    thing available and substituting a type name for it would lose information -
    turning a fix that improves the record into one that degrades it.
    """

    described = describe_exception(RuntimeError("index definition rejected: bad field 'x'"))

    assert described == "index definition rejected: bad field 'x'"


def test_a_whitespace_only_message_counts_as_silence():
    """Whitespace is not an explanation, and it renders identically to none."""

    described = describe_exception(RuntimeError("   \n  "))

    assert described.strip()
    assert "RuntimeError" in described


def test_a_missing_exception_is_not_rendered_as_the_word_none():
    """Retry loops hold their last failure in an optional and render it at the end.

    ``str(None)`` is "None": non-empty, so it passes any is-it-blank check, and
    still says nothing. That is the same failure this module exists to prevent.
    """

    described = describe_exception(None)

    assert described.strip()
    assert described != "None"
    assert "no exception" in described.lower(), (
        f"expected an explicit statement that nothing was recorded; actual: {described!r}"
    )
