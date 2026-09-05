"""A projection is checked against the record it renders, or it is not matched.

WHAT THIS FILE HOLDS

A corpus that was *transported* successfully is not a corpus that is *faithful*.
A rendering call that returned, an embedding that returned and an upload that was
acknowledged are facts about carriage; none of them is a fact about meaning. The
gap between the two is the whole reason this gate exists, and it is a quiet gap:
a substituted rendering is a well-formed document of the right shape, in the
right index, under the right profile, and it retrieves. It is simply about
something else.

So this file asserts the claim the gate is for — **a projection that is not a
rendering of its source is caught, and one that is is not** — and the three
properties that make the claim worth anything:

  * **Per document, not per corpus.** A mean over a schedule of good rows would
    absorb the one row that is about something else entirely, and that row is
    precisely the one a question about it would retrieve. Any one pair below the
    floor fails the corpus, and the finding names the document.
  * **The semantic half earns its place.** The deterministic checks cannot see a
    substitution that preserves every number and identifier. The corruption in
    `test_a_substituted_rendering_is_caught_when_nothing_deterministic_can_see_it`
    passes every structural check there is, and is still refused.
  * **"Could not check" is never "checked".** A validation nobody could perform
    is exactly as much evidence as one that failed, and neither opens the gate.

WHAT THE EMBEDDING STUB IS, AND IS NOT

`_TokenSpaceClient` is a deterministic, offline stand-in: a bag-of-tokens vector,
so identical text scores 1.0 and disjoint vocabulary scores ~0. It stands in for
a multilingual embedding and makes no claim to behave like one. What is under
test here is the **gate's logic** — whether a low-scoring pair is detected,
attributed to its document and allowed to fail the corpus — and not the quality
of any real embedding, which a stub cannot speak to and which this file therefore
never asserts.

NOTHING HERE NAMES A DOMAIN

The fixtures are a mooring fee, a kennel inspection and a stationery threshold.
What is asserted is the relationship between a record, its projection and what
the gate concludes, which must hold for any governance corpus.
"""
from __future__ import annotations

import asyncio
import os
import re
import zlib

import pytest

os.environ.setdefault("DATABASE_URL", "******localhost:5433/test")
os.environ.setdefault("ALEMBIC_DATABASE_URL", "******localhost:5433/test")

from policy_platform.infrastructure.projection.policy_rule_slice import (  # noqa: E402
    LARGE_POLICY_RULE_THRESHOLD,
    RULE_INDEX_SCOPE_ALL,
    RULE_INDEX_SCOPE_LARGE_POLICY,
    rule_documents_expected,
)
from policy_platform.infrastructure.quality.projection_faithfulness import (  # noqa: E402
    FINDING_AUTHORITATIVE_RECORD_EMBEDDED,
    FINDING_DOCUMENT_MISSING,
    FINDING_DOCUMENT_REPEATED,
    FINDING_DOCUMENT_UNEXPECTED,
    FINDING_EMBEDDING_COUNT_MISMATCH,
    FINDING_EMBEDDING_UNAVAILABLE,
    FINDING_PARENT_LINK_MISSING,
    FINDING_PROFILE_MISMATCH,
    FINDING_PROJECTED_TEXT_EMPTY,
    FINDING_RULE_DOCUMENTS_MISSING,
    FINDING_RULE_DOCUMENTS_UNEXPECTED,
    FINDING_RULE_INDEX_SCOPE_UNKNOWN,
    FINDING_SIMILARITY_BELOW_FLOOR,
    FINDING_VERSION_MISMATCH,
    PROJECTION_QUALITY_PROFILE,
    QUALITY_FAILED,
    QUALITY_PASSED,
    QUALITY_UNAVAILABLE,
    ProjectedRecord,
    known_quality_profile,
    quality_profile,
    validate_projection,
)

_PROFILE = "policy-english-projection-v1"
_VERSION = "22222222-2222-4222-8222-222222222222"


def _run(coro):
    return asyncio.run(coro)


# ── a deterministic stand-in for a multilingual embedding ────────────


_BUCKETS = 512


def _vector(text: str) -> list[float]:
    """A bag-of-tokens vector, stable across processes.

    `zlib.crc32` rather than `hash`, because `hash` on a str is salted per
    process: a test whose pass depended on it would pass and fail on the same
    code for reasons no one could reproduce.
    """

    buckets = [0.0] * _BUCKETS
    for token in re.findall(r"[a-z]+", text.lower()):
        buckets[zlib.crc32(token.encode()) % _BUCKETS] += 1.0
    return buckets


class _TokenSpaceClient:
    """Embeds by vocabulary overlap. Identical text scores 1.0."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        return [_vector(text) for text in texts]


class _MiscountingClient:
    """Returns a reply that cannot be aligned with what it was given."""

    async def embed(self, texts):
        return [_vector(text) for text in texts][:-1]


class _RefusingClient:
    async def embed(self, texts):
        raise RuntimeError("the deployment refused")


# ── the corpus under test ────────────────────────────────────────────


#: Deliberately digit-free. Numbers and identifiers are what the deterministic
#: preservation check can see, so a corpus without them is the one that isolates
#: the semantic half: anything caught here was caught by meaning alone.
_PARENT_TEXT = (
    "A vessel occupying a berth beyond the permitted period owes a mooring fee "
    "to the harbour authority for each further period begun."
)
_RULE_TEXTS = {
    "rule-a": (
        "A kennel operator must admit an inspector to any part of the premises "
        "where animals are kept, at any reasonable hour."
    ),
    "rule-b": (
        "Stationery ordered above the departmental threshold requires written "
        "approval from the head of procurement before the order is placed."
    ),
}

_PARENT_ID = "doc-parent"


def _documents(*, profile: str = _PROFILE, overrides: dict | None = None) -> list[dict]:
    """The set an untouched build of the corpus above would have produced."""

    docs = [
        {
            "id": _PARENT_ID,
            "policy_version_id": _VERSION,
            "projection_profile": profile,
            "content_type": "policy",
            "parent_document_id": None,
            "retrieval_text": _PARENT_TEXT,
        }
    ]
    for key, text in _RULE_TEXTS.items():
        docs.append(
            {
                "id": f"doc-{key}",
                "policy_version_id": _VERSION,
                "projection_profile": profile,
                "content_type": "rule",
                "parent_document_id": _PARENT_ID,
                "retrieval_text": text,
            }
        )
    for document in docs:
        document.update((overrides or {}).get(str(document["id"]), {}))
    return docs


def _records(
    *,
    rule_count: int = LARGE_POLICY_RULE_THRESHOLD + 1,
    expected_rule_documents: int | None = None,
) -> list[ProjectedRecord]:
    records = [
        ProjectedRecord(
            document_id=_PARENT_ID,
            policy_version_id=_VERSION,
            source_text=_PARENT_TEXT,
            provision_rule_count=rule_count,
            # Defaults to the number of children this fixture actually builds, so
            # the ordinary corpus is internally consistent. Override it to state
            # a provision that should have had more documents than it has —
            # which a zero-versus-nonzero coverage test cannot express at all.
            expected_rule_documents=(
                len(_RULE_TEXTS) if expected_rule_documents is None else expected_rule_documents
            ),
        )
    ]
    for key, text in _RULE_TEXTS.items():
        records.append(
            ProjectedRecord(
                document_id=f"doc-{key}",
                policy_version_id=_VERSION,
                source_text=text,
                parent_document_id=_PARENT_ID,
            )
        )
    return records


def _validate(*, documents=None, records=None, client=None, **kwargs):
    return _run(
        validate_projection(
            records=_records() if records is None else records,
            documents=_documents() if documents is None else documents,
            expected_profile=_PROFILE,
            openai_client=_TokenSpaceClient() if client is None else client,
            **kwargs,
        )
    )


def _codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


# ── the claim ────────────────────────────────────────────────────────


class TestAnUnmodifiedProjectionPasses:
    def test_a_faithful_corpus_passes_with_no_findings(self) -> None:
        """The control. Without it, every failing assertion below is worthless:
        a gate that refused everything would satisfy them all."""

        report = _validate()

        assert report.state == QUALITY_PASSED
        assert report.passed is True
        assert report.findings == ()
        assert report.structural_findings == 0
        assert report.below_floor == 0
        assert report.checked_documents == len(_RULE_TEXTS) + 1
        assert report.minimum_similarity == pytest.approx(1.0)
        assert report.mean_similarity == pytest.approx(1.0)

    def test_an_empty_corpus_passes_because_nothing_in_it_can_be_wrong(self) -> None:
        """A project with no published policies is a coherent thing to have, and
        it is not a validation failure. Refusing it would make "no policies yet"
        indistinguishable from "the corpus is corrupt"."""

        report = _validate(documents=[], records=[])

        assert report.state == QUALITY_PASSED
        assert report.checked_documents == 0
        assert report.minimum_similarity is None


class TestASeededCorruptionIsCaught:
    def test_a_substituted_rendering_is_caught_when_nothing_deterministic_can_see_it(
        self,
    ) -> None:
        """THE CENTRAL CASE.

        One rule document carries a rendering of a *different* rule. The document
        is well-formed, under the right profile, for the right version, linked to
        the right parent, non-empty, and carries no number or identifier for the
        preservation check to find missing. Every deterministic check passes. It
        is still refused, and it is refused by meaning."""

        documents = _documents(
            overrides={"doc-rule-a": {"retrieval_text": _RULE_TEXTS["rule-b"]}}
        )
        report = _validate(documents=documents)

        assert report.state == QUALITY_FAILED
        assert report.passed is False
        # Proven by the semantic half alone: nothing structural fired.
        assert report.structural_findings == 0
        assert _codes(report) == {FINDING_SIMILARITY_BELOW_FLOOR}
        assert report.below_floor == 1

    def test_the_finding_names_the_rule_document_and_not_its_policy(self) -> None:
        """Per-rule, which is the whole point. A policy-level score would hide
        exactly the row-level substitution that citation-integrity checks cannot
        see — the parent is untouched and would report healthy."""

        documents = _documents(
            overrides={"doc-rule-a": {"retrieval_text": _RULE_TEXTS["rule-b"]}}
        )
        report = _validate(documents=documents)

        named = [f.document_id for f in report.findings if f.code == FINDING_SIMILARITY_BELOW_FLOOR]
        assert named == ["doc-rule-a"]
        assert _PARENT_ID not in named

    def test_one_bad_row_fails_the_corpus_rather_than_being_averaged_away(self) -> None:
        """Any one pair below the floor fails it. Two faithful rows either side
        of a substituted one must not carry it."""

        documents = _documents(
            overrides={"doc-rule-a": {"retrieval_text": _RULE_TEXTS["rule-b"]}}
        )
        report = _validate(documents=documents)

        assert report.state == QUALITY_FAILED
        # The mean is still high — which is precisely why it is not the test.
        assert report.mean_similarity is not None
        assert report.mean_similarity > quality_profile().minimum_pair_similarity
        assert report.minimum_similarity is not None
        assert report.minimum_similarity < quality_profile().minimum_pair_similarity

    def test_every_pair_is_scored_even_once_one_has_already_failed(self) -> None:
        """A report that stopped at the first finding would send an operator
        round a loop of one repair per run against a corpus of thousands."""

        documents = _documents(
            overrides={"doc-rule-a": {"retrieval_text": _RULE_TEXTS["rule-b"]}}
        )
        report = _validate(documents=documents)

        assert report.checked_documents == len(_RULE_TEXTS) + 1


class TestTheDeterministicHalf:
    """The checks that need no model, each seeded on its own."""

    def test_a_document_the_build_expected_and_the_index_does_not_hold(self) -> None:
        documents = [d for d in _documents() if d["id"] != "doc-rule-b"]
        report = _validate(documents=documents)

        assert report.state == QUALITY_FAILED
        assert FINDING_DOCUMENT_MISSING in _codes(report)

    def test_a_document_the_index_holds_that_the_build_did_not_expect(self) -> None:
        documents = _documents()
        documents.append(
            {
                "id": "doc-left-over",
                "policy_version_id": _VERSION,
                "projection_profile": _PROFILE,
                "parent_document_id": None,
                "retrieval_text": _PARENT_TEXT,
            }
        )
        report = _validate(documents=documents)

        assert FINDING_DOCUMENT_UNEXPECTED in _codes(report)

    def test_one_key_twice_is_a_corpus_short_by_one(self) -> None:
        documents = _documents()
        documents.append(dict(documents[1]))
        report = _validate(documents=documents)

        assert FINDING_DOCUMENT_REPEATED in _codes(report)

    def test_a_rendering_under_a_superseded_contract(self) -> None:
        documents = _documents(
            overrides={"doc-rule-a": {"projection_profile": "policy-english-projection-v0"}}
        )
        report = _validate(documents=documents)

        assert FINDING_PROFILE_MISMATCH in _codes(report)

    def test_a_document_built_for_another_version(self) -> None:
        documents = _documents(
            overrides={"doc-rule-a": {"policy_version_id": "33333333-3333-4333-8333-333333333333"}}
        )
        report = _validate(documents=documents)

        assert FINDING_VERSION_MISMATCH in _codes(report)

    def test_a_rule_document_whose_parent_never_landed(self) -> None:
        documents = _documents(overrides={"doc-rule-a": {"parent_document_id": "doc-absent"}})
        report = _validate(documents=documents)

        assert FINDING_PARENT_LINK_MISSING in _codes(report)

    def test_an_indexed_document_with_no_retrieval_text(self) -> None:
        documents = _documents(overrides={"doc-rule-a": {"retrieval_text": "   "}})
        report = _validate(documents=documents)

        assert FINDING_PROJECTED_TEXT_EMPTY in _codes(report)

    def test_the_index_may_not_become_a_second_copy_of_the_record(self) -> None:
        """An index document holds identifiers, counts, headings, retrieval text
        and a vector. A mapping is the shape of the authoritative record, and a
        citation must resolve to one place, not two."""

        documents = _documents(
            overrides={"doc-rule-a": {"spans": [{"text": "the source sentence"}]}}
        )
        report = _validate(documents=documents)

        assert FINDING_AUTHORITATIVE_RECORD_EMBEDDED in _codes(report)

    def test_a_schedule_whose_rows_got_no_documents_of_their_own(self) -> None:
        """Complete by count, unreachable in exactly the part that needed the
        split."""

        report = _validate(
            documents=[d for d in _documents() if d["parent_document_id"] is None],
            records=[r for r in _records() if r.parent_document_id is None],
        )

        assert FINDING_RULE_DOCUMENTS_MISSING in _codes(report)

    def test_a_provision_small_enough_to_read_whole_carrying_rule_documents(self) -> None:
        report = _validate(records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD))

        assert FINDING_RULE_DOCUMENTS_UNEXPECTED in _codes(report)


class TestRuleCoverageIsJudgedAgainstTheScopeTheBuildUsed:
    """Which provisions should have rule documents depends on the contract.

    THE DEFECT THIS PREVENTS, WHICH ALREADY HAPPENED

    The build moved from `large_policy_rules_v1` — a document per rule only for
    provisions past the threshold — to `all_published_rules_v1`, where every
    published rule has one, because a rule with no document cannot be found by a
    rule query at all. The quality check went on enforcing the older contract.

    Nothing failed for weeks, because no rebuild got far enough to be validated.
    The first one that did was failed 36 times, each finding correctly reporting
    that a small provision had rule documents — against an expectation the build
    had been deliberately changed to stop meeting. The corpus was right and the
    judge was out of date.

    So the expectation is now derived from the scope, by the same function the
    build decides with, and every case below is stated for both scopes. A test
    that only checked one would have passed throughout the entire drift.
    """

    def _parent_only(self, *, rule_count: int):
        records = [r for r in _records(rule_count=rule_count) if r.parent_document_id is None]
        documents = [d for d in _documents() if d["parent_document_id"] is None]
        return {"records": records, "documents": documents}

    def test_a_small_provision_with_rule_documents_passes_under_all(self) -> None:
        """The exact corpus that was failed 36 times. Under the scope it was
        built to, it is correct."""

        report = _validate(
            records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )

        assert FINDING_RULE_DOCUMENTS_UNEXPECTED not in _codes(report)
        assert report.state == QUALITY_PASSED

    def test_the_same_corpus_is_still_refused_under_the_legacy_scope(self) -> None:
        """The legacy control, unweakened. The old contract still means what it
        meant; this change did not delete it, it stopped applying it to corpora
        that were never built under it."""

        report = _validate(
            records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope=RULE_INDEX_SCOPE_LARGE_POLICY,
        )

        assert FINDING_RULE_DOCUMENTS_UNEXPECTED in _codes(report)

    def test_a_small_provision_without_rule_documents_is_refused_under_all(self) -> None:
        """The other direction, and the reason the scope moved. Under `all`, a
        small provision's rules must be individually findable; a corpus that
        omits them is complete by count and silent where it matters."""

        report = _validate(
            **self._parent_only(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )

        assert FINDING_RULE_DOCUMENTS_MISSING in _codes(report)

    def test_that_same_omission_is_correct_under_the_legacy_scope(self) -> None:
        report = _validate(
            **self._parent_only(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope=RULE_INDEX_SCOPE_LARGE_POLICY,
        )

        assert FINDING_RULE_DOCUMENTS_MISSING not in _codes(report)

    def test_a_large_provision_without_rule_documents_is_refused_under_both(self) -> None:
        """The case both contracts agree on, which is what makes the two tests
        above a distinction rather than a disagreement."""

        for scope in (RULE_INDEX_SCOPE_ALL, RULE_INDEX_SCOPE_LARGE_POLICY):
            report = _validate(
                **self._parent_only(rule_count=LARGE_POLICY_RULE_THRESHOLD + 1),
                rule_index_scope=scope,
            )

            assert FINDING_RULE_DOCUMENTS_MISSING in _codes(report), scope

    def test_a_provision_with_no_rules_at_all_needs_none_under_either(self) -> None:
        for scope in (RULE_INDEX_SCOPE_ALL, RULE_INDEX_SCOPE_LARGE_POLICY):
            report = _validate(**self._parent_only(rule_count=0), rule_index_scope=scope)

            assert FINDING_RULE_DOCUMENTS_MISSING not in _codes(report), scope
            assert FINDING_RULE_DOCUMENTS_UNEXPECTED not in _codes(report), scope

    def test_an_unknown_scope_is_refused_rather_than_guessed(self) -> None:
        """Neither answer is safe to assume. Reading an unknown scope as `all`
        would bless any corpus at all; reading it as legacy would condemn a
        correct one. A validation that cannot say which contract applies has not
        validated, and says so."""

        report = _validate(
            records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope="some_future_scope_v9",
        )

        assert FINDING_RULE_INDEX_SCOPE_UNKNOWN in _codes(report)
        assert report.passed is False

    def test_an_empty_scope_is_not_read_as_permission(self) -> None:
        report = _validate(
            records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD),
            rule_index_scope="",
        )

        assert FINDING_RULE_INDEX_SCOPE_UNKNOWN in _codes(report)

    def test_the_default_is_legacy_so_an_unstamped_corpus_keeps_its_own_contract(
        self,
    ) -> None:
        """A manifest written before the scope field existed carries none. It was
        built when legacy was the only contract, so legacy is what it must be
        judged by — and defaulting the other way would silently pass corpora
        nobody ever checked."""

        report = _validate(records=_records(rule_count=LARGE_POLICY_RULE_THRESHOLD))

        assert FINDING_RULE_DOCUMENTS_UNEXPECTED in _codes(report)

    def test_the_expectation_comes_from_the_shared_function_the_build_decides_with(
        self,
    ) -> None:
        """The anti-drift claim itself, stated as an assertion rather than a hope.

        If someone reintroduces a private threshold here, this fails: the two
        sides would once again be free to disagree, which is the whole defect.
        """

        assert rule_documents_expected(1, scope=RULE_INDEX_SCOPE_ALL) is True
        assert rule_documents_expected(0, scope=RULE_INDEX_SCOPE_ALL) is False
        assert (
            rule_documents_expected(
                LARGE_POLICY_RULE_THRESHOLD, scope=RULE_INDEX_SCOPE_LARGE_POLICY
            )
            is False
        )
        assert (
            rule_documents_expected(
                LARGE_POLICY_RULE_THRESHOLD + 1, scope=RULE_INDEX_SCOPE_LARGE_POLICY
            )
            is True
        )
        with pytest.raises(ValueError):
            rule_documents_expected(1, scope="not_a_scope")

    def test_the_build_selects_rules_through_that_same_function(self) -> None:
        """Gap this closed: the build had its own copy of the branch.

        `indexable_rules` is the build's side of the decision. Driving it through
        the same helper the validator uses is what makes "they cannot disagree" a
        fact rather than a comment, so it is asserted from the build's side too.
        """

        from policy_platform.infrastructure.search.policy_index import indexable_rules

        small = {"rules": [{"rule_id": f"r{i}"} for i in range(3)]}
        large = {"rules": [{"rule_id": f"r{i}"} for i in range(LARGE_POLICY_RULE_THRESHOLD + 1)]}

        assert len(indexable_rules(small, scope=RULE_INDEX_SCOPE_ALL)) == 3
        assert indexable_rules(small, scope=RULE_INDEX_SCOPE_LARGE_POLICY) == []
        assert len(indexable_rules(large, scope=RULE_INDEX_SCOPE_LARGE_POLICY)) == (
            LARGE_POLICY_RULE_THRESHOLD + 1
        )

    def test_changing_the_shared_helper_moves_both_sides_together(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The mutation control for the shared decision.

        With the helper forced to "never", the build selects no rules AND the
        validator stops expecting any — both sides move, which is the property
        that stops one drifting from the other. If either had kept a private
        copy, one of these two assertions would fail.
        """

        from policy_platform.infrastructure.search import policy_index as build_side
        from policy_platform.infrastructure.quality import projection_faithfulness as judge

        monkeypatch.setattr(build_side, "rule_documents_expected", lambda *a, **k: False)
        monkeypatch.setattr(judge, "rule_documents_expected", lambda *a, **k: False)

        large = {"rules": [{"rule_id": f"r{i}"} for i in range(LARGE_POLICY_RULE_THRESHOLD + 1)]}
        assert build_side.indexable_rules(large, scope=RULE_INDEX_SCOPE_ALL) == []

        report = _validate(rule_index_scope=RULE_INDEX_SCOPE_ALL)
        assert FINDING_RULE_DOCUMENTS_UNEXPECTED in _codes(report), (
            "the validator kept expecting rule documents after the shared decision said none"
        )


class TestRuleCoverageIsCountedExactly:
    """"Some" is not coverage. A provision short by fifteen rows is not healthy.

    The earlier version of this check asked only whether a provision had any
    rule documents at all. Under `all_published_rules_v1` a sixteen-rule
    provision carrying one child passed it; under the legacy scope a
    seventeen-rule provision carrying one child passed it too. In both cases the
    rows that could not surface were exactly the rows the split exists for, and
    the corpus was complete by document count while being unreachable in the
    part that mattered.
    """

    def test_a_provision_short_of_its_rule_documents_is_refused_under_all(self) -> None:
        report = _validate(
            records=_records(rule_count=8, expected_rule_documents=8),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )

        assert FINDING_RULE_DOCUMENTS_MISSING in _codes(report)

    def test_a_provision_short_of_its_rule_documents_is_refused_under_legacy(self) -> None:
        report = _validate(
            records=_records(
                rule_count=LARGE_POLICY_RULE_THRESHOLD + 5,
                expected_rule_documents=LARGE_POLICY_RULE_THRESHOLD + 5,
            ),
            rule_index_scope=RULE_INDEX_SCOPE_LARGE_POLICY,
        )

        assert FINDING_RULE_DOCUMENTS_MISSING in _codes(report)

    def test_a_provision_carrying_more_than_it_should_is_refused(self) -> None:
        report = _validate(
            records=_records(rule_count=8, expected_rule_documents=1),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )

        assert FINDING_RULE_DOCUMENTS_UNEXPECTED in _codes(report)

    def test_the_exact_count_passes_in_both_scopes(self) -> None:
        """The control. Without it every assertion above would be satisfied by a
        check that simply refused everything."""

        under_all = _validate(
            records=_records(rule_count=len(_RULE_TEXTS), expected_rule_documents=len(_RULE_TEXTS)),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )
        assert under_all.state == QUALITY_PASSED

        under_legacy = _validate(
            records=_records(
                rule_count=LARGE_POLICY_RULE_THRESHOLD + 1,
                expected_rule_documents=len(_RULE_TEXTS),
            ),
            rule_index_scope=RULE_INDEX_SCOPE_LARGE_POLICY,
        )
        assert under_legacy.state == QUALITY_PASSED

    def test_a_rule_without_an_id_does_not_read_as_a_missing_document(self) -> None:
        """A rule with no id gets no document, legitimately. The expectation is
        the count the build made eligible, not the count of rules, or every such
        provision would be reported permanently short."""

        report = _validate(
            records=_records(rule_count=len(_RULE_TEXTS) + 1, expected_rule_documents=len(_RULE_TEXTS)),
            rule_index_scope=RULE_INDEX_SCOPE_ALL,
        )

        assert FINDING_RULE_DOCUMENTS_MISSING not in _codes(report)
        assert FINDING_RULE_DOCUMENTS_UNEXPECTED not in _codes(report)

    def test_the_manifest_is_excluded_rather_than_counted_as_a_stray(self) -> None:
        """It is the statement *about* the content, so counting it would make
        every corpus one document larger than itself."""

        documents = _documents()
        documents.append(
            {
                "id": "doc-manifest",
                "policy_version_id": _VERSION,
                "projection_profile": _PROFILE,
                "parent_document_id": None,
                "retrieval_text": "",
            }
        )
        report = _validate(documents=documents, ignore_document_ids=("doc-manifest",))

        assert report.state == QUALITY_PASSED
        assert report.findings == ()


class TestCouldNotCheckIsNeverChecked:
    def test_no_embedding_deployment_is_unavailable_and_not_a_pass(self) -> None:
        report = _run(
            validate_projection(
                records=_records(),
                documents=_documents(),
                expected_profile=_PROFILE,
                openai_client=None,
            )
        )

        assert report.state == QUALITY_UNAVAILABLE
        assert report.passed is False
        assert _codes(report) == {FINDING_EMBEDDING_UNAVAILABLE}

    def test_a_service_that_refused_is_unavailable_and_not_a_pass(self) -> None:
        report = _validate(client=_RefusingClient())

        assert report.state == QUALITY_UNAVAILABLE
        assert report.passed is False
        assert FINDING_EMBEDDING_UNAVAILABLE in _codes(report)

    def test_a_reply_that_cannot_be_aligned_fails_closed(self) -> None:
        """No pair in that batch can be attributed, so every one of them is a
        finding rather than a best guess at which survived."""

        report = _validate(client=_MiscountingClient())

        assert report.state == QUALITY_UNAVAILABLE
        assert _codes(report) == {FINDING_EMBEDDING_COUNT_MISMATCH}
        assert report.checked_documents == 0

    def test_a_proven_failure_outranks_a_missing_check(self) -> None:
        """A corpus whose set is wrong is failed on evidence and stays failed
        whether or not the embeddings arrived. Reporting `unavailable` would send
        an operator to fix a deployment instead of rebuilding a corpus."""

        documents = [d for d in _documents() if d["id"] != "doc-rule-b"]
        report = _run(
            validate_projection(
                records=_records(),
                documents=documents,
                expected_profile=_PROFILE,
                openai_client=_RefusingClient(),
            )
        )

        assert report.state == QUALITY_FAILED


class TestTheReportCarriesNoText:
    def test_no_field_of_the_payload_holds_a_word_of_the_corpus(self) -> None:
        """A finding names a document by a key this platform generated. The one
        way this gate could leak policy text is a field that can hold prose, so
        the assertion is over the whole serialised payload."""

        documents = _documents(
            overrides={"doc-rule-a": {"retrieval_text": _RULE_TEXTS["rule-b"]}}
        )
        report = _validate(documents=documents)
        payload = repr(report.as_payload())

        for text in (_PARENT_TEXT, *_RULE_TEXTS.values()):
            for word in ("vessel", "kennel", "stationery", "harbour", "inspector"):
                assert word not in payload.lower(), f"{word!r} reached the report"
            assert text not in payload

    def test_the_payload_carries_the_verdict_the_gate_is_read_for(self) -> None:
        report = _validate()
        payload = report.as_payload()

        assert set(payload) == {
            "state",
            "profile",
            "checked_documents",
            "structural_findings",
            "below_floor",
            "minimum_similarity",
            "mean_similarity",
            "validated_at",
            "findings",
        }
        assert payload["profile"] == PROJECTION_QUALITY_PROFILE


class TestTheProfileIsAName:
    def test_a_profile_this_build_does_not_carry_is_refused_rather_than_defaulted(
        self,
    ) -> None:
        """Falling back would mean validating under one statement of quality
        while recording another, which is the one way this could lie."""

        assert known_quality_profile(PROJECTION_QUALITY_PROFILE) is True
        assert known_quality_profile("policy-projection-quality-v99") is False
        assert known_quality_profile(None) is False

        with pytest.raises(ValueError):
            quality_profile("policy-projection-quality-v99")

    def test_the_verdict_records_the_profile_it_was_reached_under(self) -> None:
        report = _validate()

        assert report.profile == PROJECTION_QUALITY_PROFILE
