"""Rule retrieval is a mode a caller asks for, never one they are given.

WHY THIS FILE EXISTS

`rule_retrieval` changes both the unit of discovery and the unit of delivery.
Instead of ranking and returning policy records, it ranks rules and gives the
gather only those rule records, their source-provision identifiers, and the
spans and facts each rule references. It never expands a rule back to its parent
policy.

So four properties are held here, and each one is a defect that was designed
against rather than a description of the code:

  * **the default does not move.** Every request that omits the field, and every
    request that sends `false`, runs the retrieval that ran before this existed —
    including its idempotency binding, which must hash byte-identically to keys
    issued before the field was added;
  * **the evidence unit stays a rule.** No parent grouping, policy body, policy
    fallback, or policy counter enters the rule-native retrieval block;
  * **an unready corpus is refused, not approximated.** A rule-first query over
    an index that holds documents only for large provisions returns *silence*
    about every small provision, and silence reads exactly like "nothing here
    bears on your question"; and
  * **recall stays inside the rule contract.** Explicit neighbour rules can be
    admitted, within the same 12-rule and 40,000-byte limits, and every omission
    is named.

Nothing here names a corpus.
"""
from __future__ import annotations

import asyncio

import pytest

from policy_platform.contracts.case_decision import request_hash
from policy_platform.infrastructure.assistants import ai_case_project
from policy_platform.infrastructure.projection.policy_rule_slice import (
    LARGE_POLICY_RULE_THRESHOLD,
)
from policy_platform.infrastructure.search.policy_index import (
    CONTENT_TYPE_POLICY,
    CONTENT_TYPE_RULE,
    RULE_INDEX_SCOPE_ALL,
    RULE_INDEX_SCOPE_LARGE_POLICY,
    policy_document_id,
    policy_rule_content_filter,
    read_rule_index_scope,
)

_PV = "11111111-1111-4111-8111-111111111111"


def _run(coro):
    return asyncio.run(coro)


def _parent(provision_key: str) -> str:
    return policy_document_id(policy_version_id=_PV, provision_key=provision_key)


def _policy_hit(provision_key: str, *, score: float, reranker: float | None = None) -> dict:
    hit = {
        "id": _parent(provision_key),
        "policy_id": provision_key,
        "document_id": "a-project",
        "document_version": _PV,
        "content_type": CONTENT_TYPE_POLICY,
        "@search.score": score,
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


def _rule_hit(provision_key: str, rule_id: str, *, reranker: float | None = None) -> dict:
    hit = {
        "id": f"rule-{rule_id}",
        "policy_id": provision_key,
        "document_id": "a-project",
        "document_version": _PV,
        "content_type": CONTENT_TYPE_RULE,
        "rule_id": rule_id,
        "parent_document_id": _parent(provision_key),
        "provision_key": provision_key,
        "retrieval_text": f"{provision_key} {rule_id}",
    }
    if reranker is not None:
        hit["@search.rerankerScore"] = reranker
    return hit


# ── the default does not move ────────────────────────────────────────


class TestTheDefaultIsUnchanged:
    def test_omitting_the_field_hashes_exactly_as_it_did_before_it_existed(self) -> None:
        """The compatibility story, stated as the only thing that matters.

        A key issued before `rule_retrieval` existed was bound to a preimage with
        no such member. Writing `false` into it would change the hash of every
        such request and turn a legitimate retry into a `409` for callers who
        never sent the field at all.
        """

        without = request_hash(
            policy_set_key="a-project",
            scenario="a question",
            provision_id=None,
            reasoning_effort="medium",
        )
        explicit_false = request_hash(
            policy_set_key="a-project",
            scenario="a question",
            provision_id=None,
            reasoning_effort="medium",
            rule_retrieval=False,
        )

        assert without == explicit_false

    def test_asking_for_rule_retrieval_is_a_different_request(self) -> None:
        """Two requests differing only in it must conflict on one key, never replay.

        It selects which policies are retrieved and which of their rules are
        read. Replaying one against the other would hand a caller an answer
        produced by a mode they did not ask for.
        """

        policy_mode = request_hash(
            policy_set_key="a-project",
            scenario="a question",
            provision_id=None,
            reasoning_effort="medium",
        )
        rule_mode = request_hash(
            policy_set_key="a-project",
            scenario="a question",
            provision_id=None,
            reasoning_effort="medium",
            rule_retrieval=True,
        )

        assert policy_mode != rule_mode

    def test_the_default_rule_query_selects_exactly_the_older_corpus(self) -> None:
        """Now that every published rule has a document, the predicate is the guard.

        Policy mode asks for rule documents of provisions above the threshold and
        no others — the set the index held before the build's scope widened — so
        its results are what they always were.
        """

        default = policy_rule_content_filter(
            "a-project", projection_profile="p-1", large_policies_only=True
        )
        rule_mode = policy_rule_content_filter(
            "a-project", projection_profile="p-1", large_policies_only=False
        )

        assert f"rule_count gt {LARGE_POLICY_RULE_THRESHOLD}" in default
        assert "rule_count" not in rule_mode
        assert f"content_type eq '{CONTENT_TYPE_RULE}'" in default
        assert f"content_type eq '{CONTENT_TYPE_RULE}'" in rule_mode
        # Additive, never a different question.
        assert rule_mode in default

    def test_policy_mode_still_reports_itself_as_the_mode_that_ran(self) -> None:
        """Named rather than implied, so "policy mode ran" is on the record."""

        block = ai_case_project._retrieval_block(
            ai_case_project.RETRIEVAL_NARROWED,
            considered=[],
            retained=[],
            discarded=[],
            excluded=[],
            policies_retrieved=0,
        )

        assert block["retrieval_mode"] == ai_case_project.RETRIEVAL_MODE_POLICY
        # And the rule-mode counters are absent, not null: a cap of three
        # reported on a policy-mode retrieval would name a bound nothing applied.
        assert "rule_mode_parent_cap" not in block


# ── policy-mode selection remains independently covered ──────────────


# ── how many, and the budget that must not be the answer ─────────────



class TestTheCutIsOnTheRecord:
    def test_rule_parent_scoring_is_never_labelled_as_the_hybrid_fusion(self) -> None:
        """It aggregates one ranking; RRF over hybrid and semantic fuses two.

        Reporting the fusion's name here would claim two channels were combined
        where one was aggregated, which is exactly the kind of claim a receipt
        exists to make checkable.
        """

        assert (
            ai_case_project.DIRECT_POLICY_ORDER_RULE
            != ai_case_project.DIRECT_POLICY_ORDER_RRF
        )
        assert (
            ai_case_project.DIRECT_POLICY_ORDER_RULE
            not in {
                ai_case_project.DIRECT_POLICY_ORDER_SEMANTIC,
                ai_case_project.DIRECT_POLICY_ORDER_HYBRID,
            }
        )

    def test_every_order_whose_count_came_from_a_cut_can_reach_coverage_expansion(
        self,
    ) -> None:
        """The divergence this fixes, stated as the property rather than the list.

        Coverage expansion spends budget a cut left unspent. Rule mode makes a
        cut and was silently absent from the gate, so its unspent budget was
        never offered to a policy whose heading named a term the cut missed.

        The gate now reads that property directly, so this asserts the property:
        eligibility follows from *a cut having been applied and budget remaining*,
        for every ordering, including any added after this was written. Naming
        orders here would reintroduce the list the defect lived in.
        """

        cut_with_room = {"semantic_elbow_applied": True}
        assert ai_case_project.coverage_expansion_is_eligible(cut_with_room, 1)

        # No cut: the whole pool was kept, so there is no unspent budget.
        assert not ai_case_project.coverage_expansion_is_eligible(
            {"semantic_elbow_applied": False}, 1
        )

        # A cut, but the budget is already spent: nothing to expand into.
        assert not ai_case_project.coverage_expansion_is_eligible(
            cut_with_room, ai_case_project.RETRIEVAL_POLICY_BUDGET
        )


# ── an unready corpus is refused, not approximated ───────────────────


class _Manifest:
    """A search double answering the one manifest probe rule mode makes."""

    def __init__(self, scope: str | None) -> None:
        self._scope = scope
        self.calls: list[dict] = []

    async def find_documents_by_filter(self, index, *, filter_expr, select, page_size=200):
        self.calls.append({"filter": filter_expr, "select": select})
        document = {"id": "manifest-1"}
        if self._scope is not None:
            document["rule_index_scope"] = self._scope
        return [document]


class TestReadinessIsAskedAndRefused:
    def test_a_corpus_built_under_the_older_scope_reports_it(self) -> None:
        search = _Manifest(RULE_INDEX_SCOPE_LARGE_POLICY)

        scope = _run(
            read_rule_index_scope(
                search, "an-index", policy_set_key="a-project", projection_profile="p-1"
            )
        )

        assert scope == RULE_INDEX_SCOPE_LARGE_POLICY
        assert "content_type eq 'manifest'" in search.calls[0]["filter"]
        assert "projection_profile eq 'p-1'" in search.calls[0]["filter"]

    def test_a_manifest_written_before_the_scope_existed_reports_nothing(self) -> None:
        """Absent is the honest answer, and it is what the refusal turns on."""

        scope = _run(
            read_rule_index_scope(
                _Manifest(None),
                "an-index",
                policy_set_key="a-project",
                projection_profile="p-1",
            )
        )

        assert scope is None

    def test_a_corpus_holding_every_rule_reports_the_current_scope(self) -> None:
        """The control: the probe must be able to say yes, or it refuses everything."""

        scope = _run(
            read_rule_index_scope(
                _Manifest(RULE_INDEX_SCOPE_ALL),
                "an-index",
                policy_set_key="a-project",
                projection_profile="p-1",
            )
        )

        assert scope == RULE_INDEX_SCOPE_ALL

    def test_the_refusal_names_the_state_and_the_repair(self) -> None:
        error = ai_case_project.RuleIndexNotReady(
            RULE_INDEX_SCOPE_LARGE_POLICY, "the message the caller reads"
        )

        assert error.code == ai_case_project.RETRIEVAL_RULE_INDEX_NOT_READY
        assert error.scope == RULE_INDEX_SCOPE_LARGE_POLICY
        # It is a `RuntimeError`, so the decision path's existing handler chain
        # closes a reservation rather than leaking a 500 — but it is caught
        # before that handler, which is what makes the code specific.
        assert isinstance(error, RuntimeError)

    def test_the_refusal_is_not_a_retrieval_status_that_could_be_returned(self) -> None:
        """It is raised, like the projection refusal, and for the same reason.

        A returned status would mean a `200` carrying an empty selection, which
        is what "no rule bears on your question" also looks like.
        """

        statuses = {
            value
            for name, value in vars(ai_case_project).items()
            if name.startswith("RETRIEVAL_") and isinstance(value, str)
        }
        assert ai_case_project.RETRIEVAL_RULE_INDEX_NOT_READY in statuses
        assert ai_case_project.RETRIEVAL_RULE_INDEX_NOT_READY not in {
            ai_case_project.RETRIEVAL_NARROWED,
            ai_case_project.RETRIEVAL_NOT_NARROWED,
            ai_case_project.RETRIEVAL_NO_MATCH,
        }


# ── the disclosure ───────────────────────────────────────────────────


class TestTheModeIsDisclosed:
    def test_rule_mode_reports_its_own_counters_and_names_its_method(self) -> None:
        block = ai_case_project._retrieval_block(
            ai_case_project.RETRIEVAL_NARROWED,
            considered=[],
            retained=[],
            discarded=[],
            excluded=[],
            policies_retrieved=0,
            retrieval_method=ai_case_project.RULE_RETRIEVAL_METHOD,
            retrieval_mode=ai_case_project.RETRIEVAL_MODE_RULE,
            rule_mode_rule_hits=40,
            retrieval_strategy=ai_case_project.RULE_ONLY_STRATEGY,
            rules_selected=3,
            rules_grounded=2,
            rules_omitted=[
                {
                    "rule_id": "R-3",
                    "reason": ai_case_project.RULE_OMITTED_OVER_BUDGET_BYTES,
                }
            ],
            rule_grounding_bytes=30_000,
            rule_grounding_budget_bytes=(
                ai_case_project.RULE_GROUNDING_BUDGET_BYTES
            ),
        )

        assert block["retrieval_mode"] == ai_case_project.RETRIEVAL_MODE_RULE
        assert block["method"] == ai_case_project.RULE_RETRIEVAL_METHOD
        assert block["retrieval_strategy"] == ai_case_project.RULE_ONLY_STRATEGY
        assert block["rules_selected"] == 3
        assert block["rules_grounded"] == 2
        assert block["rule_grounding_bytes"] == 30_000
        assert block["rules_omitted"][0]["rule_id"] == "R-3"
        assert not [name for name in block if "policy" in name or "parent" in name]

    def test_the_two_modes_never_report_the_same_method(self) -> None:
        methods = {
            ai_case_project.RETRIEVAL_METHOD,
            ai_case_project.LIGHT_RETRIEVAL_METHOD,
            ai_case_project.RULE_RETRIEVAL_METHOD,
            ai_case_project.LIGHT_RULE_RETRIEVAL_METHOD,
        }
        assert len(methods) == 4


# ── the threshold is untouched ───────────────────────────────────────


def test_policy_mode_still_reads_a_small_policy_whole() -> None:
    """The established policy-mode slicing threshold remains unchanged.

    The rule that a provision of fifteen rules or fewer is one governing
    statement, read whole, is a property of `select_rules_for_scenario` and is
    still used by policy retrieval. Rule mode no longer calls this parent-policy
    selector at all.
    """

    from policy_platform.infrastructure.projection import policy_rule_slice

    payload = {
        "envelope": {"provision_key": "SMALL"},
        "spans": {},
        "facts": {},
        "rules": [{"rule_id": f"R-{index}"} for index in range(LARGE_POLICY_RULE_THRESHOLD)],
    }

    selected, selection = policy_rule_slice.select_rules_for_scenario(
        payload,
        policy={"provision_key": "SMALL"},
        scenario="a question",
        rule_hits={"R-3": 0},
        rule_index_state=ai_case_project.RULE_INDEX_MATCHED,
    )

    assert selected is payload, "an ordinary provision's record is untouched"
    assert selection["sliced"] is False
    assert selection["selected_rules"] == LARGE_POLICY_RULE_THRESHOLD


def test_the_threshold_constant_is_where_it_was() -> None:
    """Pinned, because this work was explicitly not allowed to move it."""

    assert LARGE_POLICY_RULE_THRESHOLD == 15


# ── the mode, driven through the retrieval it selects ────────────────


class _Settings:
    ai_enabled = True
    azure_openai_deployment = "slow"
    azure_openai_secondary_deployment = "fast"
    search_enabled = True
    azure_search_authoring_index = "policy-authoring"


class _PolicySet:
    def __init__(self, id_: str, key: str) -> None:
        self.id = id_
        self.key = key


class _RecordingSearch:
    """A search double that records what was asked and of which corpus.

    It answers the readiness probe the way the shared stub does — a manifest id
    for the manifest filter and nothing for anything else — so the retrieval
    reaches the queries this test is about.
    """

    scope: str | None = RULE_INDEX_SCOPE_ALL

    def __init__(self, settings=None) -> None:
        type(self).instance = self
        self.searches: list[dict] = []
        self.manifest_reads: list[dict] = []

    async def index_exists(self, *a, **k) -> bool:
        return True

    async def find_ids_by_filter(self, index, *, filter_expr, page_size=1000) -> list[str]:
        from tests.fixtures.search_stubs import manifest_ids

        return manifest_ids(filter_expr)

    async def find_documents_by_filter(self, index, *, filter_expr, select, page_size=200):
        self.manifest_reads.append({"filter": filter_expr, "select": select})
        document = {"id": "manifest-1"}
        if type(self).scope is not None:
            document["rule_index_scope"] = type(self).scope
        return [document]

    async def vector_search(self, index, **kwargs) -> list[dict]:
        self.searches.append(kwargs)
        if kwargs.get("filter_expr", "").find(f"content_type eq '{CONTENT_TYPE_RULE}'") >= 0:
            return [_rule_hit("A", "R-1", reranker=3.0)]
        return [_policy_hit("A", score=0.8, reranker=3.0)]


def _project(monkeypatch) -> None:
    """One published policy, its scope load and its payload stubbed."""

    payload = {
        "projection": "grounding_projection_v1",
        "representation": "canonical",
        "envelope": {
            "provision_id": "prov-a",
            "provision_key": "A",
            "heading_path": ["A heading"],
            "policy_version_id": _PV,
        },
        "spans": {},
        "facts": {},
        "rules": [{"rule_id": "R-1", "required_facts": [], "evidence_refs": []}],
    }
    scope = {
        "has_published_version": True,
        "active_version_id": _PV,
        "active_version_number": 2,
        "candidates": [
            {
                "provision_id": "prov-a",
                "provision_key": "A",
                "heading_path": ["A heading"],
                "rules": 1,
                "policy_version_id": _PV,
                "search_document_id": _parent("A"),
                "payload": payload,
            }
        ],
        "excluded": [],
    }

    async def _load(session, policy_set_id):
        return scope

    monkeypatch.setattr(ai_case_project, "load_project_scope", _load)
    monkeypatch.setattr(ai_case_project, "AzureSearchClient", _RecordingSearch)
    monkeypatch.setattr(ai_case_project, "get_settings", lambda: _Settings())


class TestTheModeReachesTheQueries:
    def test_the_default_asks_no_manifest_scope_question_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rule mode's readiness probe is one extra round trip, and only its own.

        A default request must cost exactly what it cost before: the same probes,
        the same searches, the same wall clock.
        """

        _project(monkeypatch)
        _RecordingSearch.scope = RULE_INDEX_SCOPE_ALL

        response = _run(
            ai_case_project.retrieve_project_policies(
                object(), policy_set=_PolicySet("set-1", "xx"), scenario="a question"
            )
        )

        search = _RecordingSearch.instance
        assert search.manifest_reads == []
        assert response["retrieval"]["retrieval_mode"] == ai_case_project.RETRIEVAL_MODE_POLICY
        assert response["retrieval"]["method"] == ai_case_project.LIGHT_RETRIEVAL_METHOD
        # And the light path still makes exactly one search, over policies.
        assert len(search.searches) == 1
        assert f"content_type eq '{CONTENT_TYPE_POLICY}'" in search.searches[0]["filter_expr"]

    def test_rule_mode_over_an_older_corpus_refuses_and_searches_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The refusal, and the proof it happened *before* any query was made.

        A refusal that still ran the query would have paid for the answer it
        then declined to trust, and — worse — a caller reading a log would see a
        rule query that returned almost nothing and conclude the corpus was thin.
        """

        _project(monkeypatch)
        _RecordingSearch.scope = RULE_INDEX_SCOPE_LARGE_POLICY

        with pytest.raises(ai_case_project.RuleIndexNotReady) as raised:
            _run(
                ai_case_project.retrieve_project_policies(
                    object(),
                    policy_set=_PolicySet("set-1", "xx"),
                    scenario="a question",
                    rule_retrieval=True,
                )
            )

        assert raised.value.scope == RULE_INDEX_SCOPE_LARGE_POLICY
        assert raised.value.code == ai_case_project.RETRIEVAL_RULE_INDEX_NOT_READY
        assert RULE_INDEX_SCOPE_ALL in str(raised.value)
        assert _RecordingSearch.instance.searches == []

    def test_a_corpus_without_a_recorded_scope_is_refused_the_same_way(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(monkeypatch)
        _RecordingSearch.scope = None

        with pytest.raises(ai_case_project.RuleIndexNotReady) as raised:
            _run(
                ai_case_project.retrieve_project_policies(
                    object(),
                    policy_set=_PolicySet("set-1", "xx"),
                    scenario="a question",
                    rule_retrieval=True,
                )
            )

        assert raised.value.scope is None
        assert _RecordingSearch.instance.searches == []

    def test_a_rule_search_outage_is_not_reported_as_no_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(monkeypatch)
        _RecordingSearch.scope = RULE_INDEX_SCOPE_ALL

        class _RuleSearchOutage(_RecordingSearch):
            async def vector_search(self, index, **kwargs) -> list[dict]:
                self.searches.append(kwargs)
                raise RuntimeError("search unavailable")

        monkeypatch.setattr(
            ai_case_project, "AzureSearchClient", _RuleSearchOutage
        )

        with pytest.raises(RuntimeError, match="no policy retrieval was substituted"):
            _run(
                ai_case_project.retrieve_project_policies(
                    object(),
                    policy_set=_PolicySet("set-1", "xx"),
                    scenario="a question",
                    rule_retrieval=True,
                )
            )

        assert len(_RuleSearchOutage.instance.searches) == 1

    def test_an_index_whose_schema_predates_the_field_is_unreadiness_not_an_outage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The live case, and the one that would otherwise read as a search fault.

        An index built before this field existed does not carry it in its
        *schema*, and a `select` naming an unknown field is refused by the
        service. That is exactly the corpus state the probe exists to detect and
        exactly the same repair, so it is reported as unreadiness — and it cannot
        be confused with an outage, because the existence and readiness probes
        already succeeded on this call.
        """

        _project(monkeypatch)

        class _OldSchema(_RecordingSearch):
            async def find_documents_by_filter(self, index, *, filter_expr, select, page_size=200):
                raise RuntimeError(
                    f"Azure Search query failed (400): Could not find a property named "
                    f"'rule_index_scope' — {select}"
                )

        monkeypatch.setattr(ai_case_project, "AzureSearchClient", _OldSchema)

        with pytest.raises(ai_case_project.RuleIndexNotReady) as raised:
            _run(
                ai_case_project.retrieve_project_policies(
                    object(),
                    policy_set=_PolicySet("set-1", "xx"),
                    scenario="a question",
                    rule_retrieval=True,
                )
            )

        assert raised.value.scope is None
        assert "Rebuild the policy index" in str(raised.value)
        assert _RecordingSearch.instance.searches == []

# ── a score is named on the scale it was measured on ─────────────────


def _candidate(provision_key: str) -> dict:
    return {
        "provision_id": f"pid-{provision_key}",
        "provision_key": provision_key,
        "heading_path": [provision_key],
        "rules": 1,
        "search_document_id": _parent(provision_key),
    }


class TestAScoreIsNamedOnTheScaleItWasMeasuredOn:
    """`best_score` was four different quantities under one field name.

    A receipt reported `semantic_cutoff_score: 2.0964` beside `best_score:
    0.0331` and invited a reader to relate them. They are a reranker score and
    an RRF sum: not comparable, and not comparable *within one receipt*, which
    is what makes it a disclosure defect rather than a presentation preference.
    Naming the quantity moves no selection.
    """

    def test_a_policy_rescued_by_its_rules_is_not_labelled_a_document_score(self) -> None:
        """The same conflation reached by the other route.

        A rule-rescued policy carries a maximum over its child rules' scores.
        That is on the reranker scale, which is exactly why calling it the
        semantic document kind would be wrong: a reader would compare a maximum
        over `k` against a cutoff calibrated on one.
        """

        policy_hits = [
            _policy_hit("DIRECT", score=0.9, reranker=3.0),
            _policy_hit("OTHER", score=0.4, reranker=0.5),
        ]
        rule_hits = [
            _rule_hit("HIDDEN", "R-1", reranker=3.9),
            _rule_hit("HIDDEN", "R-2", reranker=3.4),
        ]

        selected, _ranked, _by_parent, _precision = (
            ai_case_project.select_decision_policy_hits(policy_hits, rule_hits)
        )

        rescued = next(hit for hit in selected if hit.get("elevated_by_rule"))
        disclosure = ai_case_project._score_disclosure(rescued)
        assert disclosure["best_score_kind"] == ai_case_project.BEST_SCORE_KIND_RULE_MAX_SEMANTIC
        assert disclosure["best_score_kind"] != ai_case_project.BEST_SCORE_KIND_SEMANTIC
        assert disclosure["rule_max_semantic_score"] == pytest.approx(3.9)
        assert disclosure["rule_hits_counted"] == 2

class TestTheDisclosureCannotBeSilentlyDropped:
    """The failure mode that made the first attempt at this invisible.

    `PolicyRef` takes Pydantic's default `extra='ignore'`, so a producer key
    with no matching contract field is dropped with no error at all. A
    disclosure can therefore be computed, projected, and silently discarded, and
    every test that only looked at the producer would still pass. These are the
    tests that fail instead.
    """

    def test_no_disclosure_field_is_lost_between_the_decider_and_the_contract(self) -> None:
        from policy_platform.contracts.case_decision import ScoreDisclosureRef

        produced = set(ai_case_project._score_disclosure({"score_kind": "anything"}))
        assert produced == set(ScoreDisclosureRef.model_fields)
        # The empty case reports the same names rather than an empty mapping, so
        # "nothing was measured" and "the field does not exist" stay distinct.
        assert set(ai_case_project._score_disclosure(None)) == produced

    def test_the_projection_carries_the_disclosure_it_was_given(self) -> None:
        from policy_platform.application.policy_case_decision import _policy_ref

        entry = {
            "provision_id": "pid",
            "provision_key": "A",
            "heading_path": ["A"],
            "rules": 1,
            "retained": True,
            "best_rank": 0,
            "best_score": 0.0331,
            "score_disclosure": {
                "best_score_kind": ai_case_project.BEST_SCORE_KIND_POLICY_RRF,
                "semantic_score": 2.0964,
                "rule_lead_semantic_score": None,
                "rule_max_semantic_score": None,
                "rule_hits_counted": None,
            },
        }

        ref = _policy_ref(entry)
        assert ref.score_disclosure is not None
        assert ref.score_disclosure.best_score_kind == ai_case_project.BEST_SCORE_KIND_POLICY_RRF
        assert ref.score_disclosure.semantic_score == pytest.approx(2.0964)
        # A reference that records no retrieval verdict — a citation names a
        # policy, it does not rank one — carries nothing rather than a model of
        # nulls that would read as "measured, and found empty".
        assert _policy_ref({"provision_key": "B", "heading_path": []}).score_disclosure is None

class TestNamingAScoreChangesNoSelection:
    def test_policy_mode_flat_default_is_unchanged(self) -> None:
        """The control. Policy mode's recall bias is deliberate, not an oversight.

        Without this, a test suite that narrows rule mode could narrow policy
        mode too and report the result as an improvement.
        """

        flat = [
            _policy_hit("A", score=0.9, reranker=1.02),
            _policy_hit("B", score=0.8, reranker=1.01),
            _policy_hit("C", score=0.7, reranker=1.00),
        ]

        selected, evidence = ai_case_project.select_semantic_policy_hits(flat)

        assert len(selected) == 3
        assert evidence["semantic_selected"] == 3
