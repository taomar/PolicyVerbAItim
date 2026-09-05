"""A search result carries only what the code that reads it actually reads.

WHY THIS FILE EXISTS

`select` is the width of the wire. Azure AI Search returns every field a query
names for every hit it returns, so a field nobody reads is paid for on every
result of every request — and this module's four queries return up to 40, 120 and
200 documents each. The single shared list they used to share carried `body` on
rule hits, which is a verbatim second copy of the `retrieval_text` the same hit
already carries, plus clause numbers, a status and a projection profile no code
path reads at all.

Narrowing a `select` is exactly as dangerous as it is cheap: it is invisible
until a downstream read returns `None`, and a `None` in this module means "no
version", "no heading", "no projection" — all of which have honest meanings that
a missing field would silently impersonate. So there are two kinds of test here
and both are needed:

  * the **field lists** are pinned by value, so widening or narrowing one is a
    visible change to a named contract rather than an edit inside a function; and
  * the **behaviour** is exercised over hits that carry *only* the narrowed
    fields, so a consumer that still needs a dropped field fails here rather than
    in production.

Nothing here names a corpus: every provision key, heading and sentence is
invented.
"""
from __future__ import annotations

import asyncio

import pytest

from policy_platform.infrastructure.assistants import ai_case_project
from policy_platform.infrastructure.search.policy_index import (
    CONTENT_TYPE_POLICY,
    CONTENT_TYPE_RULE,
    policy_document_id,
)

_PV = "11111111-1111-4111-8111-111111111111"


def _run(coro):
    """Drive one coroutine to completion.

    Used rather than the anyio plugin because exactly one test here is async and
    the rest are pure; opting the module in would make every future test in it
    async by default, which is not the shape these checks want.
    """

    return asyncio.run(coro)


def _fields(select: str) -> list[str]:
    return [part for part in select.split(",") if part]


# ── the four lists, pinned by value ──────────────────────────────────


class TestTheSelectListsAreNamedContracts:
    def test_retrieval_only_policy_selection_asks_for_identity_and_version(self) -> None:
        """`/policies` ranks and returns records; it expands no heading coverage."""

        assert ai_case_project._POLICY_RETRIEVAL_SELECT == (
            "id,policy_id,document_id,document_version,content_type"
        )

    def test_decision_policy_selection_adds_the_headings_and_one_text_field(self) -> None:
        """Coverage expansion reads headings to admit, and body to recognise."""

        assert ai_case_project._POLICY_DECISION_SELECT == (
            "id,policy_id,document_id,document_version,content_type,"
            "section_heading,heading,body"
        )

    def test_rule_discovery_asks_for_the_rule_its_parents_and_one_projection(self) -> None:
        assert ai_case_project._RULE_DISCOVERY_SELECT == (
            "id,policy_id,document_id,document_version,content_type,"
            "rule_id,parent_document_id,provision_key,retrieval_text"
        )

    def test_scoped_rule_ranking_asks_for_the_least_of_the_four(self) -> None:
        """It is already scoped to named provisions by its filter."""

        assert ai_case_project._RULE_RANKING_SELECT == (
            "id,content_type,rule_id,provision_key,retrieval_text"
        )

    def test_no_rule_query_asks_for_body_beside_retrieval_text(self) -> None:
        """The duplicate that made this worth doing.

        `build_rule_document` writes the same string into `body` and into
        `retrieval_text`. Selecting both doubles the text of every rule hit and
        buys nothing: the request-side selection scores `retrieval_text`.
        """

        for select in (
            ai_case_project._RULE_DISCOVERY_SELECT,
            ai_case_project._RULE_RANKING_SELECT,
        ):
            fields = _fields(select)
            assert "retrieval_text" in fields
            assert "body" not in fields, "a rule hit would carry its own text twice"

    def test_the_stale_version_guard_can_still_be_asked_of_every_discovery_hit(self) -> None:
        """The one field whose absence would be indistinguishable from a match.

        `_answer_project_scope` compares `document_version` on every discovery
        hit against the active published version. A hit that did not carry it
        would compare `None` against the version, drop out of `current_*_hits`,
        and the retrieval would report a stale index for a perfectly current one.
        """

        for select in (
            ai_case_project._POLICY_RETRIEVAL_SELECT,
            ai_case_project._POLICY_DECISION_SELECT,
            ai_case_project._RULE_DISCOVERY_SELECT,
        ):
            assert "document_version" in _fields(select)

    def test_nothing_asks_for_a_field_no_reader_reads(self) -> None:
        """The four fields the shared list carried and nothing consumed.

        Named individually rather than asserted as a set difference, because the
        point is that each was checked: `clause_id` and `clause_number` are empty
        strings on every document this index holds, `status` is the constant
        `published`, and `projection_profile` is a filter clause, never a read.
        """

        for select in (
            ai_case_project._POLICY_RETRIEVAL_SELECT,
            ai_case_project._POLICY_DECISION_SELECT,
            ai_case_project._RULE_DISCOVERY_SELECT,
            ai_case_project._RULE_RANKING_SELECT,
        ):
            fields = _fields(select)
            for absent in ("clause_id", "clause_number", "status", "projection_profile"):
                assert absent not in fields


# ── the behaviour, over hits carrying only the narrowed fields ───────


def _narrow_policy_hit(
    provision_key: str,
    *,
    score: float,
    reranker: float | None = None,
    heading: str | None = None,
    body: str = "",
    version: str = _PV,
) -> dict:
    """A policy hit carrying the decision select's fields and no others."""

    hit = {
        "id": policy_document_id(policy_version_id=version, provision_key=provision_key),
        "policy_id": provision_key,
        "document_id": "a-project",
        "document_version": version,
        "content_type": CONTENT_TYPE_POLICY,
        "section_heading": heading or "",
        "heading": heading or "",
        "body": body,
        "@search.score": score,
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


def _narrow_rule_hit(
    provision_key: str,
    rule_id: str,
    *,
    score: float,
    reranker: float | None = None,
    text: str = "",
    version: str = _PV,
) -> dict:
    """A rule hit carrying the discovery select's fields and no others."""

    hit = {
        "id": f"rule-{rule_id}",
        "policy_id": provision_key,
        "document_id": "a-project",
        "document_version": version,
        "content_type": CONTENT_TYPE_RULE,
        "rule_id": rule_id,
        "parent_document_id": policy_document_id(
            policy_version_id=version, provision_key=provision_key
        ),
        "provision_key": provision_key,
        "retrieval_text": text,
        "@search.score": score,
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


class TestTheNarrowedHitsStillCarryTheSelection:
    def test_a_rule_document_is_still_recognised_as_one(self) -> None:
        """`is_rule_hit` reads the document, not the query that returned it."""

        assert ai_case_project.is_rule_hit(_narrow_rule_hit("P", "R-1", score=1.0))
        assert not ai_case_project.is_rule_hit(_narrow_policy_hit("P", score=1.0))

    def test_the_semantic_cut_ranks_and_selects_from_the_narrowed_policy_hits(self) -> None:
        """The retrieval-only path, which carries no heading and no body at all."""

        hits = [
            {
                "id": policy_document_id(policy_version_id=_PV, provision_key=key),
                "policy_id": key,
                "document_id": "a-project",
                "document_version": _PV,
                "content_type": CONTENT_TYPE_POLICY,
                "@search.score": score,
                "@search.rerankerScore": reranker,
            }
            for key, score, reranker in (
                ("HIGH", 0.9, 3.0),
                ("MID", 0.5, 2.9),
                ("LOW", 0.1, 1.0),
            )
        ]

        selected, precision = ai_case_project.select_semantic_policy_hits(hits)

        assert [hit["policy_id"] for hit in selected] == ["HIGH", "MID"]
        assert precision["semantic_candidates"] == 3
        assert precision["semantic_selected"] == 2

    def test_a_rule_only_parent_is_still_rescued_from_a_narrowed_rule_hit(self) -> None:
        """The one place a policy hit is *synthesised* from a rule hit.

        It reads `policy_id`, `document_id` and `document_version` off the rule,
        which is why the rule discovery select keeps all three even though the
        rule's own ranking never touches them.
        """

        policy_hits = [
            _narrow_policy_hit("SEEN", score=0.9, reranker=3.0),
            _narrow_policy_hit("ALSO", score=0.4, reranker=1.0),
        ]
        rule_hits = [_narrow_rule_hit("HIDDEN", "R-9", score=0.8, reranker=9.0)]

        selected, ranked, by_parent, precision = ai_case_project.select_decision_policy_hits(
            policy_hits, rule_hits
        )

        rescued = [hit for hit in selected if hit.get("elevated_by_rule")]
        assert len(rescued) == 1
        assert rescued[0]["policy_id"] == "HIDDEN"
        assert rescued[0]["document_version"] == _PV
        assert rescued[0]["id"] == policy_document_id(
            policy_version_id=_PV, provision_key="HIDDEN"
        )
        assert precision["rule_rescued_policies"] == 1
        assert set(by_parent) == {rescued[0]["id"]}
        assert {str(hit["id"]) for hit in ranked} >= {rescued[0]["id"]}

    def test_heading_coverage_still_expands_from_the_decision_hits_alone(self) -> None:
        """Expansion reads `section_heading`, `heading` and `body`, and no more."""

        selected = [
            _narrow_policy_hit(
                "FIRST",
                score=0.9,
                reranker=3.0,
                heading="Vessel berthing tariffs",
                body="A vessel occupying a berth is charged the standard tariff.",
            )
        ]
        other = _narrow_policy_hit(
            "SECOND",
            score=0.5,
            reranker=2.5,
            heading="Crew shore leave entitlement",
            body="A crew member may take shore leave once the vessel is secured.",
        )

        expanded, added = ai_case_project.expand_policy_query_coverage(
            selected,
            [*selected, other],
            scenario="what shore leave does a crew member get while berthed",
        )

        assert added == 1
        assert [hit["policy_id"] for hit in expanded] == ["FIRST", "SECOND"]

    def test_the_scoped_ranking_reads_only_provision_rule_and_projection(self) -> None:
        """The narrowest select, exercised through the function that consumes it.

        The scoped hits below carry the ranking select's five fields and nothing
        else — no version, no parent, no policy id — because the scoped query is
        already restricted to named provisions of one project by its filter.
        """

        scoped = [
            {
                "id": f"rule-{rule_id}",
                "content_type": CONTENT_TYPE_RULE,
                "rule_id": rule_id,
                "provision_key": "SCHEDULE",
                "retrieval_text": text,
            }
            for rule_id, text in (("R-2", "second row"), ("R-7", "seventh row"))
        ]

        class _Scoped:
            async def vector_search(self, index: str, **kwargs) -> list[dict]:
                assert kwargs["select"] == ai_case_project._RULE_RANKING_SELECT
                return scoped

        entry = {"provision_key": "SCHEDULE"}
        candidate = {
            "search_document_id": policy_document_id(
                policy_version_id=_PV, provision_key="SCHEDULE"
            ),
            "payload": {
                "rules": [
                    {"rule_id": f"R-{n}"}
                    for n in range(ai_case_project.LARGE_POLICY_RULE_THRESHOLD + 2)
                ]
            },
        }

        class _Readiness:
            profile = "a-profile"

        ranks, texts, state = _run(
            ai_case_project._rank_rules_for_retained(
                _Scoped(),
                "an-index",
                policy_set_key="a-project",
                scenario="a question",
                vector=None,
                readiness=_Readiness(),
                retained=[entry],
                candidates_by_entry={id(entry): candidate},
                discovery_hits={},
                rule_index_state=ai_case_project.RULE_INDEX_MATCHED,
            )
        )

        assert ranks["SCHEDULE"] == {"R-2": 0, "R-7": 1}
        assert texts["SCHEDULE"] == {"R-2": "second row", "R-7": "seventh row"}
        assert state == ai_case_project.RULE_INDEX_MATCHED
