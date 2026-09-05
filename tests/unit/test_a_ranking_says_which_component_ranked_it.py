"""A ranking says which component produced it, or says that one was absent.

WHY THIS FILE EXISTS

The service returns one number per hit, and that number means four different
things depending on what the request asked for. A score recorded without which
of the four it was cannot be compared against anything later, and "the ranking
changed" cannot be told apart from "the question changed". So the record has to
carry the distinction, and this file is the proof that it does — for each of the
four arrangements separately, and for the case where a component that was asked
for did not arrive.

The second half is what the record may **not** carry. Retrieval sees the
question a person asked, the text of the records that answered it, the identity
of the index those records live in, and the credential used to reach it. None of
those may reach a log line, and a test that only checked the fields it expected
would never notice one that arrived by accident. So the sensitivity check works
the other way round: it puts a distinctive marker into every one of those
inputs, runs a real retrieval through the client, and searches the entire
captured output for each marker.

Nothing here names a corpus. Every index, field, key, question and sentence
below is invented, and the behaviour is asserted over structure — a count, a
position, a hash — rather than over anything a document could say.
"""
from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from policy_platform.contracts.canonical import canonical_hash
from policy_platform.infrastructure.search import ranking_telemetry, search_client
from policy_platform.infrastructure.search.ranking_telemetry import (
    ABSENT_FUSED,
    ABSENT_NO_RESULTS,
    ABSENT_NOT_REQUESTED,
    ABSENT_NOT_RETURNED,
    ABSENT_SINGLE_COMPONENT,
    COMPONENT_FUSION,
    COMPONENT_LEXICAL,
    COMPONENT_SEMANTIC,
    COMPONENT_VECTOR,
    MODE_FILTER_ONLY,
    OUTCOME_FAULTED,
    OUTCOME_RANKED,
    OUTCOME_REFUSED,
)
from policy_platform.infrastructure.search.search_client import (
    AzureSearchClient,
    AzureSearchError,
)

_INDEX = "an-index"
_FILTER = "set_key eq 'a-scope' and content_type eq 'a-kind'"
_SELECT = "id,set_key,content_type,retrieval_text"


def _run(coro):
    """Drive one coroutine to completion, as the sibling client tests do."""

    return asyncio.run(coro)


def _settings(*, enabled: bool = True):
    return SimpleNamespace(
        search_enabled=enabled,
        azure_search_endpoint="https://search.example",
        azure_search_api_key="key",
        azure_search_api_version="2025-09-01",
    )


class _Transport:
    """One POST, answered from a scripted list, recording what it was sent."""

    def __init__(self, responses, calls):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def post(self, url, *, headers=None, json=None):
        self._calls.append((url, json))
        answer = self._responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _response(status: int, body: dict | str = "") -> httpx.Response:
    content = body if isinstance(body, str) else httpx.Response(200, json=body).content
    return httpx.Response(
        status, content=content, request=httpx.Request("POST", "https://search.example")
    )


def _hit(identifier: str, *, score=None, semantic=None, text: str = "") -> dict:
    hit = {"id": identifier, "retrieval_text": text}
    if score is not None:
        hit["@search.score"] = score
    if semantic is not None:
        hit["@search.rerankerScore"] = semantic
    return hit


def _events(caplog) -> list[dict]:
    """The ranking records, parsed. Warnings and other loggers are not these."""

    parsed = []
    prefix = f"{ranking_telemetry.RANKING_EVENT} "
    for record in caplog.records:
        if record.name != ranking_telemetry.__name__ or record.levelno != logging.INFO:
            continue
        message = record.getMessage()
        if message.startswith(prefix):
            parsed.append(json.loads(message[len(prefix) :]))
    return parsed


def _search(
    monkeypatch,
    caplog,
    *,
    responses,
    query_text: str = "a question about a thing",
    vector=None,
    semantic_configuration: str | None = None,
    top: int = 6,
    index: str = _INDEX,
    filter_expr: str | None = _FILTER,
    select: str | None = _SELECT,
    policy_ids=None,
    settings=None,
):
    """Run one retrieval against a scripted transport, capturing its records."""

    calls: list[tuple[str, dict | None]] = []
    monkeypatch.setattr(
        search_client.httpx, "AsyncClient", lambda **_kw: _Transport(list(responses), calls)
    )
    caplog.set_level(logging.INFO, logger=ranking_telemetry.__name__)
    client = AzureSearchClient(settings or _settings())
    result = _run(
        client.vector_search(
            index,
            query_text=query_text,
            vector=vector,
            policy_ids=policy_ids,
            top=top,
            filter_expr=filter_expr,
            select=select,
            semantic_configuration=semantic_configuration,
        )
    )
    return result, calls


def _component(event: dict, name: str) -> dict:
    return event["components"][name]


# ── the contract, pinned by value ────────────────────────────────────


class TestTheEventIsANamedContract:
    def test_the_prefix_and_the_logger_are_stable(self) -> None:
        """Both are how an operator selects these lines out of a stream."""

        assert ranking_telemetry.RANKING_EVENT == "search.ranking_components"
        assert ranking_telemetry.__name__ == (
            "policy_platform.infrastructure.search.ranking_telemetry"
        )

    def test_the_attributes_are_named_rather_than_whatever_the_code_emits(self) -> None:
        assert ranking_telemetry.RANKING_EVENT_ATTRIBUTES == (
            "outcome",
            "mode",
            "semantic_requested",
            "requested_top",
            "results",
            "semantic_reorder",
            "status_code",
            "fault",
            "index_projection_hash",
            "retrieval_scope_hash",
            "projection_fields",
            "filter_fields",
            "components",
        )
        assert ranking_telemetry.COMPONENT_ATTRIBUTES == (
            "observed",
            "absent_reason",
            "ranked",
            "best_score",
            "worst_score",
            "scores",
        )

    def test_the_four_components_are_the_whole_vocabulary(self) -> None:
        assert ranking_telemetry.RANKING_COMPONENTS == (
            COMPONENT_LEXICAL,
            COMPONENT_VECTOR,
            COMPONENT_FUSION,
            COMPONENT_SEMANTIC,
        )

    def test_an_emitted_body_carries_exactly_the_named_attributes(
        self, monkeypatch, caplog
    ) -> None:
        """Neither more nor fewer, at both levels.

        A record that grew a field nobody declared is how content leaks into a
        log; a record that lost one is how a dashboard starts reading `None` as
        a measurement.
        """

        _search(
            monkeypatch,
            caplog,
            responses=[_response(200, {"value": [_hit("one", score=1.5)]})],
        )

        event = _events(caplog)[0]
        assert tuple(sorted(event)) == tuple(sorted(ranking_telemetry.RANKING_EVENT_ATTRIBUTES))
        assert tuple(sorted(event["components"])) == tuple(
            sorted(ranking_telemetry.RANKING_COMPONENTS)
        )
        for block in event["components"].values():
            assert tuple(sorted(block)) == tuple(sorted(ranking_telemetry.COMPONENT_ATTRIBUTES))


# ── each of the four arrangements, observed as itself ────────────────


class TestEachComponentIsObservedAsItself:
    def test_a_text_query_alone_is_recorded_as_a_lexical_ranking(
        self, monkeypatch, caplog
    ) -> None:
        _search(
            monkeypatch,
            caplog,
            responses=[
                _response(
                    200,
                    {"value": [_hit("one", score=4.0), _hit("two", score=1.25)]},
                )
            ],
        )

        event = _events(caplog)[0]
        assert event["outcome"] == OUTCOME_RANKED
        assert event["mode"] == COMPONENT_LEXICAL
        assert event["results"] == 2
        lexical = _component(event, COMPONENT_LEXICAL)
        assert lexical["observed"] is True
        assert lexical["ranked"] == 2
        assert lexical["best_score"] == 4.0
        assert lexical["worst_score"] == 1.25
        assert lexical["scores"] == [4.0, 1.25]
        assert _component(event, COMPONENT_VECTOR)["absent_reason"] == ABSENT_NOT_REQUESTED
        assert _component(event, COMPONENT_FUSION)["absent_reason"] == ABSENT_SINGLE_COMPONENT
        assert _component(event, COMPONENT_SEMANTIC)["absent_reason"] == ABSENT_NOT_REQUESTED

    def test_a_vector_against_a_match_all_is_recorded_as_a_vector_ranking(
        self, monkeypatch, caplog
    ) -> None:
        """A wildcard asked no lexical question, and is not reported as one."""

        _search(
            monkeypatch,
            caplog,
            query_text="*",
            vector=[0.5, 0.25],
            responses=[_response(200, {"value": [_hit("one", score=0.8)]})],
        )

        event = _events(caplog)[0]
        assert event["mode"] == COMPONENT_VECTOR
        assert _component(event, COMPONENT_VECTOR)["observed"] is True
        assert _component(event, COMPONENT_VECTOR)["scores"] == [0.8]
        assert _component(event, COMPONENT_LEXICAL)["absent_reason"] == ABSENT_NOT_REQUESTED
        assert _component(event, COMPONENT_FUSION)["absent_reason"] == ABSENT_SINGLE_COMPONENT

    def test_a_request_that_asks_no_ranked_question_says_so(
        self, monkeypatch, caplog
    ) -> None:
        """Narrowed by its filter alone — a mode, not a missing measurement."""

        _search(
            monkeypatch,
            caplog,
            query_text="   ",
            responses=[_response(200, {"value": [_hit("one", score=1.0)]})],
        )

        event = _events(caplog)[0]
        assert event["mode"] == MODE_FILTER_ONLY
        for name in (COMPONENT_LEXICAL, COMPONENT_VECTOR, COMPONENT_FUSION):
            assert _component(event, name)["absent_reason"] == ABSENT_NOT_REQUESTED

    def test_text_and_vector_together_are_recorded_as_one_fused_ranking(
        self, monkeypatch, caplog
    ) -> None:
        """And the two scores that went into it are absent, not invented.

        This is the case the whole file exists for: the service returns a single
        fused number, so a record claiming a lexical score here would be a
        number nobody measured.
        """

        _search(
            monkeypatch,
            caplog,
            vector=[0.5, 0.25],
            responses=[
                _response(200, {"value": [_hit("one", score=0.03), _hit("two", score=0.01)]})
            ],
        )

        event = _events(caplog)[0]
        assert event["mode"] == COMPONENT_FUSION
        fusion = _component(event, COMPONENT_FUSION)
        assert fusion["observed"] is True
        assert fusion["ranked"] == 2
        assert fusion["scores"] == [0.03, 0.01]
        for name in (COMPONENT_LEXICAL, COMPONENT_VECTOR):
            block = _component(event, name)
            assert block["observed"] is False
            assert block["absent_reason"] == ABSENT_FUSED
            assert block["best_score"] is None
            assert block["scores"] == []

    def test_a_semantic_configuration_is_recorded_beside_the_base_ranking(
        self, monkeypatch, caplog
    ) -> None:
        """Two components, two sets of numbers, neither standing in for the other."""

        _search(
            monkeypatch,
            caplog,
            vector=[0.5],
            semantic_configuration="a-configuration",
            responses=[
                _response(
                    200,
                    {
                        "value": [
                            _hit("one", score=0.03, semantic=2.5),
                            _hit("two", score=0.01, semantic=1.5),
                        ]
                    },
                )
            ],
        )

        event = _events(caplog)[0]
        assert event["semantic_requested"] is True
        assert _component(event, COMPONENT_FUSION)["scores"] == [0.03, 0.01]
        semantic = _component(event, COMPONENT_SEMANTIC)
        assert semantic["observed"] is True
        assert semantic["ranked"] == 2
        assert semantic["best_score"] == 2.5
        assert semantic["worst_score"] == 1.5

    def test_only_the_head_of_a_long_ranking_is_reported_individually(
        self, monkeypatch, caplog
    ) -> None:
        """The counts and extremes still cover the whole set."""

        depth = ranking_telemetry.OBSERVED_SCORE_DEPTH
        hits = [_hit(f"h{n}", score=float(depth * 2 - n)) for n in range(depth * 2)]
        _search(monkeypatch, caplog, top=depth * 2, responses=[_response(200, {"value": hits})])

        lexical = _component(_events(caplog)[0], COMPONENT_LEXICAL)
        assert lexical["ranked"] == depth * 2
        assert len(lexical["scores"]) == depth
        assert lexical["best_score"] == float(depth * 2)
        assert lexical["worst_score"] == 1.0


# ── absence, said explicitly and never fabricated ────────────────────


class TestAnAbsentComponentSaysWhyItIsAbsent:
    def test_a_reranker_that_was_asked_for_and_did_not_arrive_is_the_loud_case(
        self, monkeypatch, caplog
    ) -> None:
        """Distinct from "not requested" and from "no results" on purpose.

        A semantic configuration that silently stopped applying looks exactly
        like a corpus that got worse. This is the one reason that tells them
        apart.
        """

        _search(
            monkeypatch,
            caplog,
            semantic_configuration="a-configuration",
            responses=[_response(200, {"value": [_hit("one", score=1.0)]})],
        )

        semantic = _component(_events(caplog)[0], COMPONENT_SEMANTIC)
        assert semantic["observed"] is False
        assert semantic["absent_reason"] == ABSENT_NOT_RETURNED
        assert semantic["ranked"] == 0
        assert semantic["best_score"] is None

    def test_an_empty_result_is_no_results_and_never_an_empty_ranking(
        self, monkeypatch, caplog
    ) -> None:
        _search(
            monkeypatch,
            caplog,
            vector=[0.5],
            semantic_configuration="a-configuration",
            responses=[_response(200, {"value": []})],
        )

        event = _events(caplog)[0]
        assert event["results"] == 0
        assert event["semantic_reorder"] is None
        for name in (COMPONENT_FUSION, COMPONENT_SEMANTIC):
            assert _component(event, name)["absent_reason"] == ABSENT_NO_RESULTS
        for name in (COMPONENT_LEXICAL, COMPONENT_VECTOR):
            assert _component(event, name)["absent_reason"] == ABSENT_FUSED

    def test_fusion_over_a_single_component_could_not_have_happened(self) -> None:
        """A different absence from "not requested": one component *did* rank."""

        observation = ranking_telemetry.observe_ranking(
            query_text="a question",
            vector_present=False,
            semantic_configuration=None,
            requested_top=6,
            hits=[_hit("one", score=1.0)],
            projection=_identity(),
        )

        blocks = {block.component: block for block in observation.components}
        assert blocks[COMPONENT_FUSION].absent_reason == ABSENT_SINGLE_COMPONENT
        assert blocks[COMPONENT_LEXICAL].observed is True

    def test_a_flag_in_a_score_field_is_not_a_ranking_of_one(self) -> None:
        """`bool` is a subclass of `int`, and that is how a flag becomes a score."""

        observation = ranking_telemetry.observe_ranking(
            query_text="a question",
            vector_present=False,
            semantic_configuration=None,
            requested_top=6,
            hits=[{"id": "one", "@search.score": True}],
            projection=_identity(),
        )

        blocks = {block.component: block for block in observation.components}
        assert blocks[COMPONENT_LEXICAL].observed is False
        assert blocks[COMPONENT_LEXICAL].absent_reason == ABSENT_NOT_RETURNED

    def test_a_run_that_got_no_answer_is_not_reported_as_an_empty_ranking(self) -> None:
        observation = ranking_telemetry.observe_ranking(
            query_text="a question",
            vector_present=False,
            semantic_configuration=None,
            requested_top=6,
            hits=None,
            projection=_identity(),
            outcome=OUTCOME_FAULTED,
            fault="ReadTimeout",
        )

        blocks = {block.component: block for block in observation.components}
        assert observation.outcome == OUTCOME_FAULTED
        assert blocks[COMPONENT_LEXICAL].absent_reason == ABSENT_NO_RESULTS

    def test_every_reason_this_module_declares_is_one_something_can_produce(self) -> None:
        """A reason nothing can emit is a diagnosis nobody will ever read.

        The first draft of this module carried exactly such a constant: fusion
        was only ever "requested" when it had already happened, so the reason
        that explains a *single-component* request could not be reached. Nothing
        asserted about the reasons it did produce would have found that. This
        walks the arrangements instead and insists the five are covered.
        """

        arrangements = (
            # query text, vector, semantic configuration, hits
            ("a question", False, None, [_hit("one", score=1.0)]),
            ("*", True, None, [_hit("one", score=1.0)]),
            ("a question", True, "a-configuration", [_hit("one", score=1.0, semantic=2.0)]),
            ("a question", True, "a-configuration", []),
            ("a question", False, "a-configuration", [_hit("one", score=1.0)]),
            ("   ", False, None, [_hit("one", score=1.0)]),
        )

        produced = set()
        for query_text, vector_present, configuration, hits in arrangements:
            observation = ranking_telemetry.observe_ranking(
                query_text=query_text,
                vector_present=vector_present,
                semantic_configuration=configuration,
                requested_top=6,
                hits=hits,
                projection=_identity(),
            )
            produced.update(
                block.absent_reason
                for block in observation.components
                if block.absent_reason is not None
            )

        assert produced == {
            ABSENT_NOT_REQUESTED,
            ABSENT_FUSED,
            ABSENT_SINGLE_COMPONENT,
            ABSENT_NO_RESULTS,
            ABSENT_NOT_RETURNED,
        }


# ── how far the reranker moved the order ─────────────────────────────


class TestTheReorderIsPurelyPositional:
    def _reorder(self, pairs) -> int | None:
        observation = ranking_telemetry.observe_ranking(
            query_text="a question",
            vector_present=False,
            semantic_configuration="a-configuration",
            requested_top=6,
            hits=[
                _hit(f"h{n}", score=base, semantic=semantic)
                for n, (base, semantic) in enumerate(pairs)
            ],
            projection=_identity(),
        )
        return observation.semantic_reorder

    def test_an_order_the_reranker_agreed_with_is_zero(self) -> None:
        assert self._reorder([(9.0, 3.0), (5.0, 2.0), (1.0, 1.0)]) == 0

    def test_a_reranker_that_moved_everything_says_how_many_positions(self) -> None:
        assert self._reorder([(1.0, 3.0), (5.0, 2.0), (9.0, 1.0)]) == 2

    def test_an_unanswerable_question_is_absent_rather_than_zero(self) -> None:
        """Zero would claim an agreement that was never tested."""

        assert self._reorder([(9.0, 3.0)]) is None
        assert self._reorder([]) is None

    def test_an_equal_pair_is_never_reported_as_a_reordering(self) -> None:
        assert self._reorder([(5.0, 3.0), (5.0, 2.0)]) == 0


# ── the projection identity ──────────────────────────────────────────


def _identity(**overrides):
    arguments = {
        "index": _INDEX,
        "select": _SELECT,
        "filter_expr": _FILTER,
        "vector_field": None,
        "semantic_configuration": None,
    }
    arguments.update(overrides)
    return ranking_telemetry.projection_identity(**arguments)


class TestTheProjectionHashIsCanonicalAndDeterministic:
    def test_the_same_projection_hashes_the_same_way_every_time(self) -> None:
        first = _identity()
        second = _identity()

        assert first.index_projection_hash == second.index_projection_hash
        assert first.retrieval_scope_hash == second.retrieval_scope_hash
        assert len(first.index_projection_hash) == 64

    def test_exactly_the_documented_structural_fields_enter_the_contract_hash(self) -> None:
        """Recomputed here from the four inputs the module documents.

        Pinning the recipe rather than a digest: a digest pinned by value says
        only that today equals today, while this says *what was hashed*, which
        is the claim the module actually makes.
        """

        identity = _identity(vector_field="a-vector-field", semantic_configuration="a-config")

        assert identity.index_projection_hash == canonical_hash(
            {
                "select": ["id", "set_key", "content_type", "retrieval_text"],
                "vector_field": "a-vector-field",
                "semantic_configuration": "a-config",
                "filter_fields": ["content_type", "set_key"],
            }
        )
        assert identity.projection_fields == 4
        assert identity.filter_fields == 2

    def test_exactly_the_index_and_the_filter_enter_the_scope_hash(self) -> None:
        assert _identity().retrieval_scope_hash == canonical_hash(
            {"index": _INDEX, "filter": _FILTER}
        )

    def test_the_order_of_the_selected_fields_is_part_of_the_contract(self) -> None:
        """`select` is the shape of the answer, and a reordering is a change."""

        assert (
            _identity(select="id,set_key").index_projection_hash
            != _identity(select="set_key,id").index_projection_hash
        )

    def test_two_scopes_of_one_contract_agree_on_the_contract_and_differ_on_the_scope(
        self,
    ) -> None:
        """The property that makes the contract hash comparable across projects."""

        one = _identity(filter_expr="set_key eq 'first' and content_type eq 'a-kind'")
        two = _identity(filter_expr="set_key eq 'second' and content_type eq 'a-kind'")

        assert one.index_projection_hash == two.index_projection_hash
        assert one.retrieval_scope_hash != two.retrieval_scope_hash

    def test_a_different_index_is_a_different_scope_and_the_same_contract(self) -> None:
        other = _identity(index="another-index")

        assert other.index_projection_hash == _identity().index_projection_hash
        assert other.retrieval_scope_hash != _identity().retrieval_scope_hash

    def test_neither_hash_moves_with_the_question_or_the_depth(
        self, monkeypatch, caplog
    ) -> None:
        """The two inputs deliberately excluded, proved excluded end to end."""

        _search(
            monkeypatch,
            caplog,
            query_text="one question",
            top=6,
            responses=[_response(200, {"value": []})],
        )
        _search(
            monkeypatch,
            caplog,
            query_text="an entirely different question",
            top=40,
            responses=[_response(200, {"value": []})],
        )

        first, second = _events(caplog)
        assert first["index_projection_hash"] == second["index_projection_hash"]
        assert first["retrieval_scope_hash"] == second["retrieval_scope_hash"]
        assert (first["requested_top"], second["requested_top"]) == (6, 40)

    def test_a_filter_gives_up_its_field_names_and_never_its_values(self) -> None:
        """The safety property the structural half of the hash rests on."""

        names = ranking_telemetry.filter_field_names(
            "set_key eq 'a-value' and search.in(other_key, 'x,y', ',') "
            "and (rank_position ge 3 or rank_position le 9)"
        )

        assert names == ("other_key", "rank_position", "set_key")
        assert not [name for name in names if name in ("a-value", "x", "y")]

    def test_an_unparsed_filter_contributes_no_name_rather_than_a_value(self) -> None:
        """Saying less is the smaller loss; saying a value is the one that matters."""

        assert ranking_telemetry.filter_field_names("search.ismatch('a-phrase', 'a-field')") == ()
        assert ranking_telemetry.filter_field_names(None) == ()

    def test_a_filterless_query_still_has_a_scope_and_an_empty_field_count(self) -> None:
        identity = _identity(filter_expr=None)

        assert identity.filter_fields == 0
        assert identity.retrieval_scope_hash == canonical_hash({"index": _INDEX, "filter": None})


# ── what may never be said ───────────────────────────────────────────


class TestNothingSensitiveIsEmitted:
    def test_no_marker_planted_in_any_sensitive_input_reaches_the_log(
        self, monkeypatch, caplog
    ) -> None:
        """Searched for the other way round, so an accidental field is caught too.

        Each marker goes into one input a retrieval genuinely sees. The whole
        captured output is then searched for every one of them — which catches a
        field nobody thought to assert about, and that is the failure mode a
        list of expected keys cannot see.
        """

        markers = {
            "question": "marker-query-text",
            "index": "marker-index-name",
            "scope": "marker-scope-value",
            "credential": "marker-api-key",
            "record": "marker-record-identifier",
            "content": "marker-document-body",
            "endpoint": "marker-endpoint-host",
        }
        settings = SimpleNamespace(
            search_enabled=True,
            azure_search_endpoint=f"https://{markers['endpoint']}.example",
            azure_search_api_key=markers["credential"],
            azure_search_api_version="2025-09-01",
        )

        _search(
            monkeypatch,
            caplog,
            settings=settings,
            index=markers["index"],
            query_text=markers["question"],
            filter_expr=f"set_key eq '{markers['scope']}'",
            policy_ids=[markers["scope"]],
            vector=[0.5, 0.25],
            semantic_configuration="a-configuration",
            responses=[
                _response(
                    200,
                    {
                        "value": [
                            _hit(
                                markers["record"],
                                score=1.0,
                                semantic=2.0,
                                text=markers["content"],
                            )
                        ]
                    },
                )
            ],
        )

        emitted = "\n".join(record.getMessage() for record in caplog.records)
        assert emitted, "the retrieval emitted nothing, so this check proved nothing"
        for name, marker in markers.items():
            assert marker not in emitted, f"the {name} reached a log line"

    def test_a_transport_message_is_never_quoted_only_its_type(
        self, monkeypatch, caplog
    ) -> None:
        """Transport messages routinely carry the endpoint that was unreachable."""

        with pytest.raises(httpx.ConnectTimeout):
            _search(
                monkeypatch,
                caplog,
                responses=[httpx.ConnectTimeout("https://marker-host.example/?key=marker-key")],
            )

        event = _events(caplog)[0]
        emitted = "\n".join(record.getMessage() for record in caplog.records)
        assert event["fault"] == "ConnectTimeout"
        assert "marker-host" not in emitted
        assert "marker-key" not in emitted

    def test_the_scores_are_the_only_measurement_that_travels(
        self, monkeypatch, caplog
    ) -> None:
        """A relevance score names nothing and quotes nothing; a hit's fields do."""

        _search(
            monkeypatch,
            caplog,
            responses=[
                _response(
                    200,
                    {"value": [_hit("a-record", score=7.5, text="a sentence from a record")]}
                )
            ],
        )

        event = _events(caplog)[0]
        assert _component(event, COMPONENT_LEXICAL)["scores"] == [7.5]
        assert "a-record" not in json.dumps(event)
        assert "a sentence" not in json.dumps(event)


# ── and the retrieval itself, unchanged ──────────────────────────────


class TestTheRetrievalIsUnchanged:
    def test_the_request_body_is_what_it_always_was(self, monkeypatch, caplog) -> None:
        """Pinned by value: observing a query may not alter the query."""

        _, calls = _search(
            monkeypatch,
            caplog,
            query_text="a question",
            vector=[0.5, 0.25],
            top=3,
            policy_ids=["one-id"],
            semantic_configuration="a-configuration",
            responses=[_response(200, {"value": []})],
        )

        url, body = calls[0]
        assert url == f"https://search.example/indexes/{_INDEX}/docs/search?api-version=2025-09-01"
        assert body == {
            "search": "a question",
            "top": 3,
            "select": _SELECT,
            "vectorQueries": [
                {"kind": "vector", "vector": [0.5, 0.25], "fields": "body_vector", "k": 3}
            ],
            "queryType": "semantic",
            "semanticConfiguration": "a-configuration",
            "filter": f"policy_id eq 'one-id' and ({_FILTER})",
        }

    def test_the_hits_come_back_in_the_order_the_service_sent_them(
        self, monkeypatch, caplog
    ) -> None:
        """Deliberately not in score order, so a sort introduced here would show."""

        value = [
            _hit("first", score=1.0, semantic=1.0),
            _hit("second", score=9.0, semantic=9.0),
            _hit("third", score=5.0, semantic=5.0),
        ]
        result, _ = _search(
            monkeypatch,
            caplog,
            semantic_configuration="a-configuration",
            responses=[_response(200, {"value": value})],
        )

        assert [hit["id"] for hit in result] == ["first", "second", "third"]
        assert result == value

    def test_a_hit_is_handed_back_exactly_as_it_arrived(self, monkeypatch, caplog) -> None:
        """No field added, none removed, none rewritten by the act of reading it."""

        result, _ = _search(
            monkeypatch,
            caplog,
            responses=[
                _response(200, {"value": [_hit("one", score=1.0, semantic=2.0, text="text")]})
            ],
        )

        assert result == [
            {
                "id": "one",
                "retrieval_text": "text",
                "@search.score": 1.0,
                "@search.rerankerScore": 2.0,
            }
        ]

    def test_a_response_without_a_value_still_returns_the_empty_list(
        self, monkeypatch, caplog
    ) -> None:
        result, _ = _search(monkeypatch, caplog, responses=[_response(200, {})])

        assert result == []
        assert _events(caplog)[0]["results"] == 0


# ── failure, propagated exactly as before ────────────────────────────


class TestAFailureIsStillAFailure:
    def test_an_error_status_raises_the_message_it_always_raised(
        self, monkeypatch, caplog
    ) -> None:
        with pytest.raises(AzureSearchError, match=r"query failed \(503\)"):
            _search(monkeypatch, caplog, responses=[_response(503, "unavailable")])

        event = _events(caplog)[0]
        assert event["outcome"] == OUTCOME_REFUSED
        assert event["status_code"] == 503
        assert event["results"] == 0
        assert event["fault"] is None

    def test_a_transport_fault_propagates_unaltered(self, monkeypatch, caplog) -> None:
        """The same exception object, not one wrapped by the observation."""

        fault = httpx.ReadTimeout("")
        with pytest.raises(httpx.ReadTimeout) as raised:
            _search(monkeypatch, caplog, responses=[fault])

        assert raised.value is fault
        assert _events(caplog)[0]["outcome"] == OUTCOME_FAULTED

    def test_one_retrieval_emits_exactly_one_record_on_every_outcome(
        self, monkeypatch, caplog
    ) -> None:
        """A duplicated line would double every count read off these."""

        _search(monkeypatch, caplog, responses=[_response(200, {"value": []})])
        with pytest.raises(AzureSearchError):
            _search(monkeypatch, caplog, responses=[_response(500, "no")])
        with pytest.raises(httpx.ReadTimeout):
            _search(monkeypatch, caplog, responses=[httpx.ReadTimeout("")])

        assert [event["outcome"] for event in _events(caplog)] == [
            OUTCOME_RANKED,
            OUTCOME_REFUSED,
            OUTCOME_FAULTED,
        ]

    def test_an_unconfigured_resource_still_refuses_before_anything_is_recorded(
        self, monkeypatch, caplog
    ) -> None:
        caplog.set_level(logging.INFO, logger=ranking_telemetry.__name__)
        client = AzureSearchClient(_settings(enabled=False))

        with pytest.raises(AzureSearchError, match="not configured"):
            _run(client.vector_search(_INDEX, query_text="a question", vector=None))

        assert _events(caplog) == []

    def test_a_broken_observation_never_becomes_a_failed_retrieval(
        self, monkeypatch, caplog
    ) -> None:
        """The containment this is all worthless without.

        A retrieval that succeeded must not be turned into a request that failed
        because somebody added a measurement to it — and the fact that the
        measurement broke must itself be visible rather than swallowed.
        """

        def _explode(**_kwargs):
            raise RuntimeError("the observation itself is broken")

        monkeypatch.setattr(ranking_telemetry, "observe_ranking", _explode)

        result, _ = _search(
            monkeypatch,
            caplog,
            responses=[_response(200, {"value": [_hit("one", score=1.0)]})],
        )

        assert [hit["id"] for hit in result] == ["one"]
        assert _events(caplog) == []
        assert any(
            "could not be emitted" in record.getMessage()
            and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_a_logging_handler_that_raises_is_contained_too(self, monkeypatch, caplog) -> None:
        """Otherwise the guard re-raises through the thing it was guarding."""

        def _explode(*_args, **_kwargs):
            raise RuntimeError("the log itself is broken")

        monkeypatch.setattr(ranking_telemetry.logger, "info", _explode)
        monkeypatch.setattr(ranking_telemetry.logger, "warning", _explode)

        result, _ = _search(
            monkeypatch,
            caplog,
            responses=[_response(200, {"value": [_hit("one", score=1.0)]})],
        )

        assert [hit["id"] for hit in result] == ["one"]
