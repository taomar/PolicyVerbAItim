"""Every literal the validator requires is withheld from the renderer.

THE INVARIANT, STATED ONCE

`preservation_failure` asks two questions of a rendering: does it still state
every number its source stated, and every identifier-shaped token. Those two
predicates define what a "literal" is here.

The rule this file pins is a relation between that definition and the protection:

    every literal the validator requires must be structurally protected by an
    exact occurrence span, and the marker standing in its place must itself be
    inert to both predicates.

Both halves are load-bearing, and each was learned from a failed build rather
than reasoned out in advance:

  * **Not protected.** A literal left in the text is a literal a renderer can
    drop. One live build lost one number out of seventy-seven and the whole
    project index failed; another lost five identifier-shaped tokens.
  * **Not inert.** A marker that answers either predicate *creates* a literal
    the source never stated, which the renderer must then reproduce exactly.
    Measured over one real corpus, a digit-bearing marker produced 2,277
    identifier tokens that existed only because a number had been protected,
    against 83 the documents themselves stated.

WHY THE CASES BELOW LOOK THE WAY THEY DO

Nothing here is shaped around the corpus that exposed the problem. The property
is a property of the mechanism, so it is stated over several unrelated invented
domains, several scripts and several identifier forms. The real failing shape
appears exactly once, as a regression case, and it is synthetic in wording — its
value is its *density*, not its subject.
"""

from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from policy_platform.infrastructure.search import english_projection
from policy_platform.infrastructure.search.english_projection import (
    EnglishProjectionError,
    _identifiers,
    _numbers,
    _OpaqueText,
    preservation_failure,
    project_texts_to_english,
    protected_literal_failure,
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


def _spans(text: str, term: str) -> list[tuple[int, int]]:
    found, start = [], text.find(term)
    while start != -1:
        found.append((start, start + len(term)))
        start = text.find(term, start + 1)
    return found


class _Echo:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def chat(self, messages, **_kwargs) -> str:
        payload = contained_payload(messages[-1]["content"])
        self.payloads.append(payload)
        return json.dumps(payload, ensure_ascii=False)

    def sent(self) -> str:
        return "\n".join(v for payload in self.payloads for v in payload.values())


#: Unrelated invented domains, several scripts, several identifier forms. None of
#: them is the corpus that exposed the defect, because the claim is not about it.
TEXTS = {
    "latin_prose_sparse": "A vessel may occupy a berth for 3 days before a fee accrues.",
    "latin_dense": "Grades 1, 2, 3 and 4 attract 10%, 20%, 30% and 40% respectively.",
    "arabic_indic": "المدة ٣٠ يوما، والحد ١٥ بالمئة، والمهلة ٧ أيام.",
    "arabic_and_latin": "الإشعار 30 يوما deduction حسم (2) يومان and 50% thereafter.",
    "cyrillic": "Срок 30 дней, штраф 15 процентов, пункт 4.2 применяется.",
    "greek": "Η προθεσμία είναι 30 ημέρες και το όριο 15 τοις εκατό.",
    "cjk": "期限は30日、上限は15パーセント、第4.2項が適用される。",
    "hebrew": "התקופה היא 30 ימים והמגבלה 15 אחוזים.",
    "identifier_hyphen": "Refer to clause AL-2024-07 and to schedule HR-88 for detail.",
    "identifier_dot": "Section 4.2.1 and reference doc.v2 apply to kennel inspections.",
    "identifier_slash": "Form A/17/b must accompany every mooring-fee appeal.",
    "identifier_underscore": "The key stationery_threshold_9 governs bulk orders.",
    "identifier_mixed_case": "Codes aB12c and XY9Z are equivalent for this purpose.",
    "dates_and_decimals": "Effective 2024-01-31 at a rate of 1.5, ceiling 1,000,000.",
    "repeated_literal": "Grade 30 and grade 30 and again grade 30 are treated alike.",
    "no_literals_at_all": "A kennel operator must admit an inspector at any reasonable hour.",
}


# --------------------------------------------------------------------------
# The invariant, over every shape above
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_a_hidden_text_states_no_literal_the_validator_would_require(name):
    """Nothing left to lose, and nothing invented to lose.

    Both directions in one assertion, because they are one property. If a
    literal survives into the hidden text the renderer can drop it; if the
    marker is itself a literal the renderer acquires an obligation the document
    never imposed.
    """

    text = TEXTS[name]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    assert _numbers(hidden) == [], f"{name}: a number reached the renderer"
    assert _identifiers(hidden) == set(), f"{name}: an identifier reached the renderer"


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_every_shape_round_trips_to_the_exact_source_characters(name):
    text = TEXTS[name]
    protector = _OpaqueText({}, texts=[text])

    assert protector.show("item", protector.hide("item", text)) == text


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_the_prose_around_the_literals_still_reaches_the_renderer(name):
    """Protection is of literals, not of the sentence. A mechanism that withheld
    the words as well would be refusing to render the corpus."""

    text = TEXTS[name]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    words = [w for w in text.split() if not any(c.isdigit() for c in w)]
    for word in words:
        assert word in hidden, f"{name}: the renderer never saw {word!r}"


def test_a_text_with_no_literals_is_left_completely_alone():
    """The control. Without it, a mechanism that replaced everything would
    satisfy every assertion above."""

    text = TEXTS["no_literals_at_all"]
    protector = _OpaqueText({}, texts=[text])

    assert protector.hide("item", text) == text
    assert protector._expected["item"] == ()


# --------------------------------------------------------------------------
# Occurrences, not spellings
# --------------------------------------------------------------------------


def test_a_repeated_literal_is_withheld_once_per_occurrence():
    text = TEXTS["repeated_literal"]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    assert len(protector._expected["item"]) == 3
    assert len(set(protector._expected["item"])) == 3, "occurrences shared a marker"
    assert protector.show("item", hidden) == text


def test_items_do_not_share_markers():
    """Two documents rendered in one call are still two documents."""

    protector = _OpaqueText({}, texts=list(TEXTS.values()))
    protector.hide("a", TEXTS["latin_dense"])
    protector.hide("b", TEXTS["latin_dense"])

    assert set(protector._expected["a"]).isdisjoint(protector._expected["b"])


# --------------------------------------------------------------------------
# Precedence: outermost wins, and nothing is protected twice
# --------------------------------------------------------------------------


def test_an_identifier_is_withheld_whole_rather_than_perforated():
    """`AL-2024-07` withheld as one span, not as `AL-<marker>-<marker>`.

    Perforating it produces a token longer than the one it replaces, which then
    depends on the renderer preserving the spacing around three pieces instead
    of copying one opaque run.
    """

    text = TEXTS["identifier_hyphen"]
    protector = _OpaqueText({}, texts=[text])
    protector.hide("item", text)
    originals = set(protector._original.values())

    assert "AL-2024-07" in originals, "the identifier was not withheld as one unit"
    assert "HR-88" in originals
    assert "2024" not in originals, "a number inside the identifier was withheld separately"


def test_a_recorded_machine_term_outranks_the_identifier_that_contains_it():
    key = "annual-leave-7"
    text = f"The {key} rule applies for 30 days."
    protector = _OpaqueText({"item": _spans(text, key)}, texts=[text])
    protector.hide("item", text)
    originals = list(protector._original.values())

    assert key in originals
    assert originals.count(key) == 1, "the recorded term was withheld more than once"
    assert "30" in originals


def test_a_literal_touching_a_recorded_term_is_still_protected():
    """Adjacent is not overlapping. Both are withheld, separately."""

    key = "clause-ref-a"
    text = f"See {key} then 30 days later."
    protector = _OpaqueText({"item": _spans(text, key)}, texts=[text])
    hidden = protector.hide("item", text)

    assert len(protector._expected["item"]) == 2
    assert protector.show("item", hidden) == text


# --------------------------------------------------------------------------
# Losing a withheld literal is refused, and reported without values
# --------------------------------------------------------------------------


def test_a_dropped_marker_is_refused_and_named_only_by_count():
    text = TEXTS["latin_dense"]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)
    marker = protector._expected["item"][0]

    reason = protected_literal_failure(hidden, hidden.replace(marker, "", 1))

    assert reason is not None
    assert "protected literal" in reason
    for value in ("10", "20", "30", "40", marker):
        assert value not in reason, f"the refusal quoted {value!r}"


def test_a_duplicated_marker_is_refused():
    text = TEXTS["latin_prose_sparse"]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    assert protected_literal_failure(hidden, hidden + " " + hidden) is not None


def test_an_intact_rendering_is_not_refused():
    """The control for the two above."""

    for text in TEXTS.values():
        protector = _OpaqueText({}, texts=[text])
        hidden = protector.hide("item", text)
        assert protected_literal_failure(hidden, hidden) is None
        assert preservation_failure(hidden, hidden) is None


def test_show_refuses_what_slipped_past_the_rendering_check():
    text = TEXTS["identifier_dot"]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)
    marker = protector._expected["item"][0]

    with pytest.raises(EnglishProjectionError):
        protector.show("item", hidden.replace(marker, marker[:-2] + "XY"))


# --------------------------------------------------------------------------
# Density: the regression case, synthetic in wording
# --------------------------------------------------------------------------


def _dense(rows: int) -> str:
    """A schedule stating many literals. Invented, and about nothing.

    Its shape — a table of numbered rows each carrying several quantities — is
    the shape that failed in production. Its subject deliberately is not.
    """

    return " ".join(
        f"{index}. | Item {index} attracts {index * 3}% or ({index}) days, ref XX-{index:03d}-B."
        for index in range(1, rows + 1)
    )


@pytest.mark.parametrize("rows", [1, 5, 20, 60])
def test_density_changes_nothing_about_the_invariant(rows):
    text = _dense(rows)
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    assert _numbers(hidden) == []
    assert _identifiers(hidden) == set()
    assert protector.show("item", hidden) == text


def test_a_dense_schedule_renders_end_to_end_and_keeps_every_literal():
    """The regression case, through the caller's own code rather than a helper."""

    text = _dense(60)
    assert len(_numbers(text)) > 77, "fixture should be denser than the live failure"

    client = _Echo()
    rendered = _run(
        project_texts_to_english([("policy", text)], settings=_settings(), openai_client=client)
    )

    # Words and order, not bytes: a text past the per-call ceiling is cut at
    # whitespace it already contains and rejoined with a newline, which is the
    # documented trade `split_for_rendering` makes. Every literal must survive
    # that exactly, which is what the next two assertions say.
    assert rendered["policy"].split() == text.split()
    assert _numbers(rendered["policy"]) == _numbers(text)
    assert _identifiers(rendered["policy"]) == _identifiers(text)
    assert "ZQKEEP" not in rendered["policy"], "a marker leaked into the indexed text"
    assert not any(char.isdigit() for char in client.sent()), (
        "a digit reached the renderer, so some literal was left exposed"
    )


# --------------------------------------------------------------------------
# Mutation controls
# --------------------------------------------------------------------------


def test_without_identifier_protection_an_identifier_is_perforated_not_withheld(monkeypatch):
    """Proves the identifier half is what keeps a code intact.

    Note what this control does *not* claim. With the number half still running,
    disabling identifier spans does not leave `AL-2024-07` sitting in the text —
    it leaves it cut into `AL-<marker>-<marker>`, which is the failure mode the
    identifier half exists to prevent: a token longer than the one it replaces,
    whose survival depends on the renderer preserving spacing around three
    pieces rather than copying one opaque run.
    """

    text = TEXTS["identifier_hyphen"]

    whole = _OpaqueText({}, texts=[text])
    whole.hide("item", text)
    assert "AL-2024-07" in set(whole._original.values())

    monkeypatch.setattr(english_projection, "_identifier_spans", lambda _text: ())
    cut = _OpaqueText({}, texts=[text])
    hidden = cut.hide("item", text)

    assert "AL-2024-07" not in set(cut._original.values()), (
        "the identifier was still withheld whole without the identifier spans"
    )
    assert "AL-" in hidden, "the identifier's letters were withheld by something else"
    assert len(cut._expected["item"]) > len(whole._expected["item"]), (
        "perforating an identifier should cost more markers than withholding it whole"
    )


def test_without_number_protection_numbers_reach_the_renderer(monkeypatch):
    monkeypatch.setattr(english_projection, "_number_spans", lambda _text: ())
    text = TEXTS["latin_dense"]
    protector = _OpaqueText({}, texts=[text])
    hidden = protector.hide("item", text)

    assert _numbers(hidden), "numbers vanished without the number spans"


def test_a_digit_bearing_marker_manufactures_identifiers(monkeypatch):
    """The measured regression, reproduced as a control.

    This is the defect that failed a live rebuild: with a digit in the marker,
    protecting a plain number creates an identifier-shaped token the source never
    stated, and the renderer is then required to reproduce it exactly.
    """

    text = _dense(20)
    protector = _OpaqueText({}, texts=[text])
    clean = protector.hide("item", text)
    assert _identifiers(clean) == set()

    monkeypatch.setattr(
        _OpaqueText,
        "_marker",
        lambda self, ordinal: f"{self._prefix}{ordinal:04d}{self._SUFFIX}",
    )
    noisy_protector = _OpaqueText({}, texts=[text])
    noisy = noisy_protector.hide("item", text)

    assert _identifiers(noisy), (
        "a digit-bearing marker no longer manufactures identifiers, so the "
        "inertness rule has stopped being load-bearing and this control is dead"
    )
    assert len(_identifiers(noisy)) > len(_identifiers(text))


# --------------------------------------------------------------------------
# When a marker is lost anyway: send a smaller call, never a repaired one
# --------------------------------------------------------------------------
#
# Withholding a literal is what stops it being dropped, and refusing a reply that
# dropped one anyway is what stops a corpus quietly losing a number. Both of
# those work. What a live rebuild showed is what happens *next*: 293 rules
# published, the index build stopping at
#
#     class=rendering_rejected batch=1 items=2 chars=1529
#
# where one value carried nineteen protected literals, the first attempt lost one
# and the second lost fourteen. The batch was retried once at the same size and
# then the whole build was abandoned — even though sending each item on its own
# is a *different* call: a shorter prompt, fewer markers for one reply to carry,
# and no neighbouring value to confuse them with.
#
# So the rule these cases pin is about the remedy, and it has a floor:
#
#     a batch whose reply kept losing a protected literal is divided, exactly as
#     an over-budget batch is; a single item that still loses one is refused —
#     never accepted, never repaired, and never described in the refusal.


class _DropsAMarkerInGroups:
    """A renderer that loses a protected literal only when asked for several.

    Not a caricature. It is the failure the live build showed: a reply that
    parses, that returns every key it was given, and that quietly omits one
    opaque run when the call carried more than one value. Alone, each item comes
    back whole — which is precisely why a smaller call is worth making.
    """

    def __init__(self, *, loses_above: int = 1) -> None:
        self.loses_above = loses_above
        #: How many values each call asked for, in order. The record the
        #: assertions read: it is the *sequence of call sizes* that says whether
        #: a batch was repeated or divided.
        self.calls: list[int] = []

    async def embed(self, texts):
        return [[0.0, 0.0, 1.0] for _ in texts]

    async def chat(self, messages, **_kwargs) -> str:
        payload = contained_payload(messages[-1]["content"])
        self.calls.append(len(payload))
        if len(payload) <= self.loses_above:
            return json.dumps(payload, ensure_ascii=False)

        damaged = dict(payload)
        key = sorted(damaged)[-1]
        damaged[key] = _without_one_marker(damaged[key])
        return json.dumps(damaged, ensure_ascii=False)


def _without_one_marker(hidden: str) -> str:
    """The same value with a single protected run deleted.

    Reaches for the marker by its stem rather than by asking the protector,
    because the stub stands where the model stands and the model is given the
    hidden text and nothing else.
    """

    found = re.search(
        f"{_OpaqueText._STEM}[A-Z]+?{_OpaqueText._SUFFIX}", hidden
    )
    assert found is not None, "the fixture text carried no protected literal to lose"
    return hidden[: found.start()] + hidden[found.end() :]


#: Two items, each stating literals, small enough that nothing here is about
#: size. What makes the first call fail is the *number of values in it*, which is
#: the only variable the split changes.
_PAIR = [
    ("first", "Grade 4 attracts 30% within 14 days under ref AL-2024-07."),
    ("second", "Schedule HR-88 sets 7 days, a 1.5 rate and a 1,000,000 ceiling."),
]


def test_a_batch_that_keeps_losing_a_marker_is_divided_rather_than_abandoned():
    """The live failure, and the behaviour that answers it.

    Two attempts at the pair — the retry the module already made — and then one
    call per item rather than a refusal. Every literal comes back, and the call
    sizes prove it was division that did it and not a third identical try.
    """

    client = _DropsAMarkerInGroups()

    rendered = _run(
        project_texts_to_english(_PAIR, settings=_settings(), openai_client=client)
    )

    assert client.calls == [2, 2, 1, 1], (
        "the pair should be attempted twice and then split into single items"
    )
    assert list(rendered) == ["first", "second"], "the split reordered the corpus"
    for key, source in _PAIR:
        assert rendered[key] == source
        assert _numbers(rendered[key]) == _numbers(source)
        assert _identifiers(rendered[key]) == _identifiers(source)
    assert "ZQKEEP" not in "".join(rendered.values()), "a marker leaked into the corpus"


def test_the_division_keeps_every_key_with_its_own_text():
    """Dividing a call must not shuffle values between keys.

    Stated over items whose literals are disjoint, so a value delivered under the
    wrong key is visible as a literal appearing where it does not belong — which
    a plain equality check on one item would not catch.
    """

    items = [
        (f"k{index}", f"Row {index} allows {index * 11} units under ref XX-{index:03d}-B.")
        for index in range(5)
    ]
    client = _DropsAMarkerInGroups()

    rendered = _run(
        project_texts_to_english(items, settings=_settings(), openai_client=client)
    )

    assert list(rendered) == [key for key, _text in items]
    for key, source in items:
        assert rendered[key] == source
    # Divided down to single items, and no call ever repeated a size it had
    # already failed at more than the two attempts the module makes.
    assert min(client.calls) == 1
    assert client.calls.count(5) == 2, "the whole batch should be tried twice, not more"


def test_a_single_item_that_still_loses_a_marker_is_refused_without_naming_it():
    """The floor. There is nothing smaller than one item, so this is a refusal.

    And the refusal says what a build report may carry: the class, the size and
    position of the call, and the name of the check that refused. Not the
    sentence, not the marker, not the literal that went missing.
    """

    client = _DropsAMarkerInGroups(loses_above=0)
    text = "A berth may be held for 9317 days at a 48.75% surcharge under ref AL-2024-07."

    with pytest.raises(EnglishProjectionError) as raised:
        _run(
            project_texts_to_english(
                [("only", text)], settings=_settings(), openai_client=client
            )
        )

    message = str(raised.value)
    assert english_projection.PROJECTION_UNFAITHFUL in message
    assert "items=1" in message and "batch=0" in message and "chars=" in message
    assert "protected literal" in message, "the refusal did not name the check that refused"
    # Not the passage, not a literal it stated, not the marker standing in for one.
    for fragment in ("berth", "surcharge", "9317", "48.75", "2024", "AL-2024-07", "ZQKEEP"):
        assert fragment not in message, f"the refusal quoted {fragment!r}"
    # The two attempts the module already made, and no third.
    assert client.calls == [1, 1]


def test_a_transport_failure_is_not_answered_by_dividing_the_batch():
    """Division answers "this call asked for too much", not "the call never landed".

    A timeout says nothing about how many markers a reply was carrying, so
    turning one failed call into several is turning one outage into a fan-out.
    The two attempts happen at the original size and stop there.
    """

    calls: list[int] = []

    class _TimesOut:
        async def embed(self, texts):
            return [[0.0, 0.0, 1.0] for _ in texts]

        async def chat(self, messages, **_kwargs):
            calls.append(len(contained_payload(messages[-1]["content"])))
            raise TimeoutError("read timed out")

    with pytest.raises(EnglishProjectionError) as raised:
        _run(project_texts_to_english(_PAIR, settings=_settings(), openai_client=_TimesOut()))

    assert english_projection.PROJECTION_TIMEOUT in str(raised.value)
    assert calls == [2, 2], "a transport failure was answered by splitting the batch"


def test_a_service_refusal_is_not_answered_by_dividing_the_batch():
    """The other half of the same control: a "no" is not a size."""

    calls: list[int] = []

    class _Refuses:
        async def embed(self, texts):
            return [[0.0, 0.0, 1.0] for _ in texts]

        async def chat(self, messages, **_kwargs):
            calls.append(len(contained_payload(messages[-1]["content"])))
            raise RuntimeError(
                'Azure OpenAI chat call failed (403): {"error": {"code": "access_denied"}}'
            )

    with pytest.raises(EnglishProjectionError) as raised:
        _run(project_texts_to_english(_PAIR, settings=_settings(), openai_client=_Refuses()))

    assert "code=access_denied" in str(raised.value)
    assert calls == [2, 2], "a service refusal was answered by splitting the batch"


def test_an_unreadable_reply_is_not_answered_by_dividing_the_batch():
    """A reply that never parsed said nothing about how many values it carried."""

    calls: list[int] = []

    class _Babbles:
        async def embed(self, texts):
            return [[0.0, 0.0, 1.0] for _ in texts]

        async def chat(self, messages, **_kwargs):
            calls.append(len(contained_payload(messages[-1]["content"])))
            return "not an object at all"

    with pytest.raises(EnglishProjectionError):
        _run(project_texts_to_english(_PAIR, settings=_settings(), openai_client=_Babbles()))

    assert calls == [2, 2], "an unreadable reply was answered by splitting the batch"


def test_a_missing_marker_is_never_restored_to_make_a_rendering_succeed():
    """The thing none of the above may quietly have become.

    Every case here ends either in text that still states every literal, or in a
    refusal. There is no third outcome in which the module puts a marker back,
    and this states that directly: what the failing renderer returns is missing a
    literal, and what reaches the caller is a refusal rather than that value with
    the literal reinstated.
    """

    client = _DropsAMarkerInGroups(loses_above=0)
    source = "The limit is 30 days and the ceiling is 15%."

    with pytest.raises(EnglishProjectionError):
        _run(
            project_texts_to_english(
                [("only", source)], settings=_settings(), openai_client=client
            )
        )

    # And the same renderer, asked for a call it does not damage, is trusted —
    # so the refusal above is about the reply, not about the fixture.
    intact = _run(
        project_texts_to_english(
            [("only", source)],
            settings=_settings(),
            openai_client=_DropsAMarkerInGroups(loses_above=1),
        )
    )
    assert intact["only"] == source

