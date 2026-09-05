"""The retrieval route answers in the shape the mode asked for.

WHY THIS FILE EXISTS SEPARATELY FROM THE MODEL TESTS

The contract tests beside this one construct envelopes directly. That proved the
*types* could not carry each other's field, and it proved nothing about the
route: a router can import the wrong response model, annotate the wrong return
type, or publish the wrong schema, and every model-level test still passes while
a real POST returns 500.

That is not hypothetical — it is exactly what happened. `policy_case_decision`
was returning `RuleRetrievalEnvelope` while the router still declared
`response_model=PolicyRetrievalEnvelope`, so FastAPI's response validation
rejected it with a `schema_version` literal error and `rules` extra_forbidden,
and rule-mode retrieval was a 500 with an OpenAPI schema that only ever
described the policy shape.

So these tests cross the router boundary. They send a real request and read a
real response body.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from policy_platform.api.authz import Principal, require_authenticated_principal
from policy_platform.api.roles import VIEWER
from policy_platform.api.routers import policy_decisions
from policy_platform.application import policy_case_decision
from policy_platform.contracts.policy_retrieval import (
    PolicyRetrievalEnvelope,
    RuleRetrievalEnvelope,
)


def _language() -> dict:
    return {
        "source_language": "en",
        "processing_language": "en",
        "response_language": "en",
        "boundary_state": "same_language",
        "output_rendering_state": "not_required",
        "guidance_rendering_state": "not_required",
        "input_translation_profile": "none",
        "processing_scenario": "a question",
        "processing_scenario_hash": "h" * 64,
    }


def _common() -> dict:
    return {
        "correlation_id": "correlation-1",
        "policy_set": {"id": "set-1", "key": "a-project", "name": "A project"},
        "query": {"scenario": "a question", "scenario_hash": "h" * 64},
        "retrieval": {"status": "narrowed"},
        "size": {"combined_chars": 10, "budget_chars": 200000, "oversize": False},
        "language": _language(),
        "token_usage": {
            "calls": 0,
            "calls_without_usage": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "latency_ms": 1,
    }


class _PolicySet:
    id = "set-1"
    key = "a-project"
    name = "A project"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """A real app with the real router, and only the data layer stubbed.

    Authentication and the session dependency are overridden because neither is
    what this file is about; the router, its response model and its serialisation
    are the real ones, because they are exactly what was broken.
    """

    app = FastAPI()
    app.include_router(policy_decisions.router)
    app.dependency_overrides[require_authenticated_principal] = lambda: Principal(
        identity="tester", role=VIEWER, source="development"
    )
    app.dependency_overrides[policy_decisions.get_session] = lambda: None

    class _Repo:
        def __init__(self, _session) -> None:
            pass

        async def get_by_key(self, key: str):
            return _PolicySet() if key == "a-project" else None

    monkeypatch.setattr(policy_decisions, "PolicySetRepository", _Repo)

    async def _retrieve(session, *, policy_set, scenario, correlation_id, rule_retrieval=False):
        if rule_retrieval:
            return RuleRetrievalEnvelope(
                **_common(),
                rules=[
                    {
                        "rule_id": "R-1",
                        "source": {
                            "provision_key": "4.1",
                            "heading_path": ["4", "4.1 Faulty equipment"],
                        },
                        "match": {
                            "best_rank": 0,
                            "best_score": 2.51,
                            "score_kind": "semantic_reranker_v1",
                            "semantic_score": 2.51,
                            "admitted_as": "matched",
                        },
                        "rule": {"rule_id": "R-1", "text": "The rule's own terms."},
                    }
                ],
            )
        return PolicyRetrievalEnvelope(
            **_common(),
            policies=[
                {
                    "policy": {"provision_key": "4.1", "heading_path": ["4", "4.1"]},
                    "match": {"best_rank": 0, "best_score": 2.51},
                    "payload": {"provision_key": "4.1", "rules": []},
                }
            ],
        )

    monkeypatch.setattr(policy_case_decision, "retrieve_project_policies", _retrieve)
    monkeypatch.setattr(policy_decisions, "retrieve_project_policies", _retrieve)

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _post(client, *, rule_retrieval: bool):
    return await client.post(
        "/api/policy-decisions/a-project/policies",
        json={"scenario": "a question", "rule_retrieval": rule_retrieval},
    )


async def test_rule_mode_returns_200_with_rules_and_no_policies(client) -> None:
    """The request that was a 500. Body read, not just status."""

    async with client:
        response = await _post(client, rule_retrieval=True)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "rule_retrieval_v1"
    assert "policies" not in body
    assert [record["rule_id"] for record in body["rules"]] == ["R-1"]
    # A rule carries its source for citation and none of the provision's content.
    assert body["rules"][0]["source"]["provision_key"] == "4.1"
    assert "payload" not in body["rules"][0]
    assert "policy" not in body["rules"][0]


async def test_policy_mode_returns_200_with_policies_and_no_rules(client) -> None:
    """The control. Policy mode must be untouched by the rule work."""

    async with client:
        response = await _post(client, rule_retrieval=False)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "policy_retrieval_v1"
    assert "rules" not in body
    assert body["policies"][0]["policy"]["provision_key"] == "4.1"


async def test_omitting_the_field_answers_in_policy_mode(client) -> None:
    """The default does not move, checked over the wire rather than assumed."""

    async with client:
        response = await client.post(
            "/api/policy-decisions/a-project/policies",
            json={"scenario": "a question"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["schema_version"] == "policy_retrieval_v1"


async def test_the_two_modes_are_distinguishable_from_the_body_alone(client) -> None:
    """An A/B caller holds only the response, so the mode must be readable in it."""

    async with client:
        rule_body = (await _post(client, rule_retrieval=True)).json()
        policy_body = (await _post(client, rule_retrieval=False)).json()

    assert rule_body["schema_version"] != policy_body["schema_version"]
    assert set(rule_body) - set(policy_body) == {"rules"}
    assert set(policy_body) - set(rule_body) == {"policies"}


async def test_the_published_schema_describes_both_shapes(client) -> None:
    """OpenAPI described only the policy shape while rule mode was broken.

    A generated client is built from this document, so a schema that omits the
    rule shape produces callers that cannot represent a rule-mode response —
    which is the same silent misreport one layer further out.
    """

    async with client:
        document = (await client.get("/openapi.json")).json()

    schemas = document["components"]["schemas"]
    assert "RuleRetrievalEnvelope" in schemas
    assert "PolicyRetrievalEnvelope" in schemas
    assert "RetrievedRuleRecord" in schemas
    assert "rules" not in schemas["PolicyRetrievalEnvelope"]["properties"]
    assert "policies" not in schemas["RuleRetrievalEnvelope"]["properties"]
