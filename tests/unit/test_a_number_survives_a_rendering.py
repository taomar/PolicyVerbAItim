"""A number comes back from a rendering exactly as the source wrote it.

WHY THIS FILE EXISTS

A live rebuild of a real corpus failed like this:

    class=rendering_rejected batch=45 items=1 chars=2394
    the value for key t0 was rejected: the rendering did not carry 1 of the
    77 number(s) its source states

One item states seventy-seven numbers. The renderer returned seventy-six. The
guard refused the reply, the batch could not be rendered, and the whole project
index failed to build — so the project answered nothing at all.

The guard is right and is unchanged. Governance text *is* quantities: a notice
period, a threshold, a percentage. A rendering that quietly drops one has
changed what the passage can be found by, and no amount of "please be careful"
addressed to a renderer is a control.

What changed is that the renderer is no longer given the chance. Every numeric
run is withheld before the call and the source's own characters are put back
after, by the same per-occurrence marker mechanism that already protects
machine-made keys. A model cannot drop what it never received.

WHAT THESE TESTS PIN

  * **Restoration is of characters, not values.** An Arabic-Indic ٣٠ comes back
    as ٣٠, not as 30, and 1.5 is not tidied into 1,5. The guard normalises digit
    sets when *comparing*; the text itself must be the document's own.
  * **One occurrence, one marker.** A figure stated twice is protected twice, so
    a reply that returned it once is refused rather than averaged.
  * **Numbers inside a protected term are left to that term.** A nested marker
    would corrupt the identifier it sits in.
  * **Nothing leaks.** No marker survives into the indexed text, and every
    number the source stated is in the result.
  * **The guard still refuses an unprotected loss.** `preservation_failure` is
    untouched, and the mutation control at the end proves the protection is what
    makes the dense case pass — not a weakened check.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from policy_platform.infrastructure.search import english_projection
from policy_platform.infrastructure.search.english_projection import (
    EnglishProjectionError,
    _numbers,
    _OpaqueText,
    preservation_failure,
    project_texts_to_english,
)
from tests.fixtures.search_stubs import contained_payload


def _run(coro):
    return asyncio.run(coro)


def _settings():
    return SimpleNamespace(
        search_enabled=True,
        ai_enabled=True,
        azure_openai_embedding_dimensions=3,
        azure_openai_secondary_deployment="fast",
        azure_openai_deployment="slow",
    )


class _Echo:
    """Returns what it was given, remembering what that was.

    Identity is the right stub: these tests are not about rendering quality but
    about which characters reached the renderer at all. What it was *sent* is
    the evidence, so it is kept.
    """

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def chat(self, messages, **_kwargs) -> str:
        payload = contained_payload(messages[-1]["content"])
        self.payloads.append(payload)
        return json.dumps(payload, ensure_ascii=False)

    def sent(self) -> str:
        return "\n".join(value for payload in self.payloads for value in payload.values())


class _DropsOneBareNumber:
    """A careless renderer: it loses the first number it is actually shown.

    This is the failure that was observed in production, reduced to its
    mechanism. "Bare" means a digit run that is not part of a marker — the stub
    must not corrupt the protection itself, or it would be testing the marker
    check rather than the number rule.

    Against protected text there are no bare numbers, so this renderer is an
    identity function and the projection succeeds. Against unprotected text it
    drops one, and the guard refuses. That difference is the whole claim.
    """

    def __init__(self) -> None:
        self.dropped = 0

    @staticmethod
    def _strip_one(text: str) -> tuple[str, bool]:
        for match in english_projection._DIGIT_RUN.finditer(text):
            # A marker is <prefix><digits>ZQ; skip the digits inside one.
            if text[match.end() : match.end() + 2] == "ZQ":
                continue
            return text[: match.start()] + text[match.end() :], True
        return text, False

    async def chat(self, messages, **_kwargs) -> str:
        payload = contained_payload(messages[-1]["content"])
        out = {}
        for key, value in payload.items():
            stripped, did = self._strip_one(value)
            if did:
                self.dropped += 1
            out[key] = stripped
        return json.dumps(out, ensure_ascii=False)


def _spans(text: str, term: str) -> list[tuple[int, int]]:
    found, start = [], text.find(term)
    while start != -1:
        found.append((start, start + len(term)))
        start = text.find(term, start + 1)
    return found


# --------------------------------------------------------------------------
# Restoration is of characters, not values
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Notice of 30 days applies.",
        "A rate of 1.5 percent is charged.",
        "Effective 2024-01-31 for all staff.",
        "A ceiling of 1,000,000 units.",
        "الإشعار ٣٠ يوما مطلوب.",
        "Mixed ٣٠ and 30 in one line.",
    ],
)
def test_the_source_characters_come_back_exactly(text):
    """Whatever digit set and separators the document used are what it gets back."""

    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)

    assert protector.show("policy", hidden) == text, (
        "a number was restored as something other than the characters the source wrote"
    )


def test_no_digit_of_the_source_is_shown_to_the_renderer():
    """The point of the mechanism: there is nothing left to drop."""

    text = "Within 30 days, and again within 30 days, up to 1.5 times the 2024 rate."
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)

    bare = [
        m.group()
        for m in english_projection._DIGIT_RUN.finditer(hidden)
        if hidden[m.end() : m.end() + 2] != "ZQ"
    ]
    assert bare == [], f"these numbers reached the renderer unprotected: {bare}"


def test_an_arabic_indic_number_is_not_normalised_on_the_way_back():
    """The guard compares across digit sets; the stored text is the document's own."""

    text = "المدة ٣٠ يوما."
    protector = _OpaqueText({}, texts=[text])
    restored = protector.show("policy", protector.hide("policy", text))

    assert restored == text
    assert "٣٠" in restored, "an Arabic-Indic figure was rewritten into ASCII"
    assert "30" not in restored


# --------------------------------------------------------------------------
# One occurrence, one marker
# --------------------------------------------------------------------------


def test_a_number_stated_twice_is_protected_twice():
    """A schedule naming 30 twice and a reply naming it once has lost a row."""

    text = "Grade 30 and grade 30 are treated alike."
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)

    assert hidden.count("ZQKEEP") == 2, "repeated figures shared one marker"
    assert protector.show("policy", hidden) == text


def test_a_reply_that_returned_one_of_two_markers_is_refused():
    text = "Grade 30 and grade 30 are treated alike."
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)

    markers = [tok for tok in hidden.split() if "ZQKEEP" in tok]
    collapsed = hidden.replace(markers[0], "", 1)

    with pytest.raises(EnglishProjectionError):
        protector.show("policy", collapsed)


def test_a_duplicated_number_marker_is_refused():
    text = "A ceiling of 500 units."
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)

    with pytest.raises(EnglishProjectionError):
        protector.show("policy", hidden + " " + hidden)


def test_an_altered_number_marker_is_refused():
    text = "A ceiling of 500 units."
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("policy", text)
    marker = next(tok for tok in hidden.split() if "ZQKEEP" in tok).strip(".")

    with pytest.raises(EnglishProjectionError):
        protector.show("policy", hidden.replace(marker, marker[:-2] + "XY"))


# --------------------------------------------------------------------------
# Numbers inside a protected term belong to that term
# --------------------------------------------------------------------------


def test_a_number_inside_a_recorded_term_gets_no_nested_marker():
    """The slug is protected as one unit; a marker inside it would corrupt it."""

    key = "annual-leave-7"
    text = f"The {key} rule applies for 30 days."
    protector = _OpaqueText({"policy": _spans(text, key)}, texts=[text])
    hidden = protector.hide("policy", text)

    assert hidden.count("ZQKEEP") == 2, (
        "expected one marker for the whole slug and one for the free-standing 30"
    )
    assert protector.show("policy", hidden) == text


def test_a_number_adjacent_to_a_recorded_term_is_protected_separately():
    """Touching spans are two spans, and both must survive."""

    key = "clause-ref-a"
    text = f"See {key}30 for detail."
    protector = _OpaqueText({"policy": _spans(text, key)}, texts=[text])
    hidden = protector.hide("policy", text)

    assert hidden.count("ZQKEEP") == 2, "an adjacent figure was swallowed by the term"
    assert protector.show("policy", hidden) == text


# --------------------------------------------------------------------------
# End to end: nothing leaks, and the dense case builds
# --------------------------------------------------------------------------


def _dense_text(occurrences: int = 77) -> str:
    """A neutral passage stating `occurrences` numbers.

    Deliberately synthetic and domain-free. The production failure was on one
    customer item; nothing here is shaped around that corpus, and the property
    under test — that a text stating many numbers renders at all — is a property
    of the mechanism, not of any document.
    """

    parts = [
        f"Item {index} allows {index * 3} units."
        for index in range(1, occurrences // 2 + 1)
    ]
    text = " ".join(parts)
    while len(_numbers(text)) < occurrences:
        text += f" A further {len(_numbers(text))} applies."
    return text


def test_a_dense_item_renders_and_keeps_every_number():
    """The shape of the item that failed in production, with the protection on."""

    text = _dense_text()
    source_numbers = _numbers(text)
    assert len(source_numbers) >= 77, "fixture should be at least as dense as the failure"

    client = _DropsOneBareNumber()
    rendered = _run(
        project_texts_to_english(
            [("policy", text)], settings=_settings(), openai_client=client
        )
    )

    assert client.dropped == 0, (
        "a bare number reached the renderer, so the protection did not cover the item"
    )
    assert rendered["policy"] == text
    assert _numbers(rendered["policy"]) == source_numbers
    assert "ZQKEEP" not in rendered["policy"], "a marker leaked into the indexed text"
    assert preservation_failure(text, rendered["policy"]) is None


def test_a_dense_item_is_refused_when_the_protection_is_disabled():
    """The mutation control.

    With `_number_spans` returning nothing, the numbers reach the renderer, the
    careless stub drops one, and the guard refuses — which is exactly the
    production failure. This is what shows the test above passes because of the
    protection rather than because the guard was softened: `preservation_failure`
    is the same function in both directions.
    """

    text = _dense_text()
    client = _DropsOneBareNumber()

    original = english_projection._number_spans
    english_projection._number_spans = lambda _text: ()
    try:
        with pytest.raises(EnglishProjectionError) as caught:
            _run(
                project_texts_to_english(
                    [("policy", text)], settings=_settings(), openai_client=client
                )
            )
    finally:
        english_projection._number_spans = original

    assert client.dropped > 0, "the control stub did not actually drop anything"
    assert "number(s) its source states" in str(caught.value), (
        "the refusal should still be the number guard, naming what was lost"
    )


def test_the_guard_itself_is_unchanged_for_an_unprotected_loss():
    """`preservation_failure` still refuses a missing number on its own terms."""

    assert preservation_failure("Within 30 days.", "Within days.") is not None
    assert preservation_failure("Within 30 days.", "Within 30 days.") is None
