from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from policy_platform.infrastructure.search import search_client
from policy_platform.infrastructure.search.search_client import AzureSearchClient, AzureSearchError


def _run(coro):
    return asyncio.run(coro)


def _settings(*, enabled: bool = True):
    return SimpleNamespace(
        search_enabled=enabled,
        azure_search_endpoint="https://search.example",
        azure_search_api_key="key",
        azure_search_api_version="2025-09-01",
    )


class _Transport:
    def __init__(self, responses: list, calls: list[tuple[str, str, dict | None]]):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    def _next(self):
        """Pop the next scripted outcome.

        An `Exception` in the script is *raised* rather than returned, so a test
        can stage a transport failure — the thing that actually broke a rebuild —
        and not just an unhappy status code.
        """

        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def put(self, url, *, headers=None, json=None):
        self._calls.append(("PUT", url, json))
        return self._next()

    async def post(self, url, *, headers=None, json=None):
        self._calls.append(("POST", url, json))
        return self._next()

    async def get(self, url, *, headers=None):
        self._calls.append(("GET", url, None))
        return self._next()

    async def delete(self, url, *, headers=None):
        self._calls.append(("DELETE", url, None))
        return self._next()


async def _no_sleep(_seconds):
    """Collapse the retry backoff so the tests measure behaviour, not patience."""

    return None


def _response(status: int, body: dict | str = "") -> httpx.Response:
    content = body if isinstance(body, str) else httpx.Response(200, json=body).content
    return httpx.Response(status, content=content, request=httpx.Request("GET", "https://search.example"))


def test_create_index_puts_the_definition(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []
    monkeypatch.setattr(
        search_client.httpx,
        "AsyncClient",
        lambda **_kw: _Transport([_response(201, {"name": "policy-cases-x"})], calls),
    )

    result = _run(AzureSearchClient(_settings()).create_index({"name": "policy-cases-x", "fields": []}))

    assert result == {"name": "policy-cases-x"}
    assert calls == [
        (
            "PUT",
            "https://search.example/indexes/policy-cases-x?api-version=2025-09-01",
            {"name": "policy-cases-x", "fields": []},
        )
    ]


def test_create_index_requires_a_name():
    with pytest.raises(AzureSearchError, match="non-empty name"):
        _run(AzureSearchClient(_settings()).create_index({"fields": []}))


def test_index_exists_distinguishes_present_absent_and_error(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []
    # A 500 is retryable, so "broken" has to stay broken for every attempt before
    # the client is entitled to call it broken.
    responses = [_response(200, {"name": "present"}), _response(404)] + [
        _response(500, "boom") for _ in range(search_client._MAX_ATTEMPTS)
    ]
    monkeypatch.setattr(
        search_client.httpx,
        "AsyncClient",
        lambda **_kw: _Transport(responses, calls),
    )
    monkeypatch.setattr(search_client.asyncio, "sleep", _no_sleep)
    client = AzureSearchClient(_settings())

    assert _run(client.index_exists("present")) is True
    assert _run(client.index_exists("absent")) is False
    with pytest.raises(AzureSearchError, match="lookup failed"):
        _run(client.index_exists("broken"))
    assert len(calls) == 2 + search_client._MAX_ATTEMPTS


def test_delete_index_treats_absent_as_success(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []
    responses = [_response(204), _response(404)]
    monkeypatch.setattr(
        search_client.httpx,
        "AsyncClient",
        lambda **_kw: _Transport(responses, calls),
    )
    client = AzureSearchClient(_settings())

    assert _run(client.delete_index("present")) is True
    assert _run(client.delete_index("absent")) is False


def test_index_management_requires_search_configuration():
    client = AzureSearchClient(_settings(enabled=False))

    with pytest.raises(AzureSearchError, match="not configured"):
        _run(client.index_exists("x"))

# --- Upload resilience -------------------------------------------------------
#
# These exist because of a measured incident rather than a hypothetical. A
# rebuild of the `ais-e2e` index spent ~36 minutes rendering and embedding all
# 318 documents, uploaded the first batch of 50, and then lost the entire run to
# a single transport failure on batch 2. There was no retry anywhere on the
# upload path, and the exception carried no message, so the recorded reason was
# the empty string.


def test_upload_survives_a_transient_transport_failure(monkeypatch):
    """One blip must not discard work that already succeeded."""

    calls: list[tuple[str, str, dict | None]] = []
    responses = [
        httpx.ReadTimeout(""),  # message-less, exactly as observed in the incident
        _response(200, {"value": [{"status": True}]}),
    ]
    monkeypatch.setattr(
        search_client.httpx, "AsyncClient", lambda **_kw: _Transport(responses, calls)
    )
    monkeypatch.setattr(search_client.asyncio, "sleep", _no_sleep)
    client = AzureSearchClient(_settings())

    result = _run(client.upload_documents("idx", [{"id": "a"}]))

    assert result == {"value": [{"status": True}]}
    assert len(calls) == 2, "the failed attempt should have been retried exactly once"


def test_upload_gives_up_with_a_reason_that_is_never_empty(monkeypatch):
    """A persistent failure still fails - but it says what failed.

    `httpx.ReadTimeout("")` stringifies to `''`. Recording that empty string is
    what made the original incident read as "no reason recorded", which points a
    reader at a dead process rather than at a timeout.
    """

    calls: list[tuple[str, str, dict | None]] = []
    responses = [httpx.ReadTimeout("") for _ in range(search_client._MAX_ATTEMPTS)]
    monkeypatch.setattr(
        search_client.httpx, "AsyncClient", lambda **_kw: _Transport(responses, calls)
    )
    monkeypatch.setattr(search_client.asyncio, "sleep", _no_sleep)
    client = AzureSearchClient(_settings())

    with pytest.raises(AzureSearchError) as excinfo:
        _run(client.upload_documents("idx", [{"id": "a"}]))

    message = str(excinfo.value)
    assert message.strip(), "the recorded reason must never be empty"
    assert "ReadTimeout" in message, f"the reason must name the failure, got: {message!r}"
    assert len(calls) == search_client._MAX_ATTEMPTS


def test_upload_does_not_retry_a_rejected_document(monkeypatch):
    """The control: the retry is not simply retrying everything.

    A 400 means the request is wrong. Retrying it cannot help, and doing so would
    turn one clear error into four and delay the report of it.
    """

    calls: list[tuple[str, str, dict | None]] = []
    monkeypatch.setattr(
        search_client.httpx,
        "AsyncClient",
        lambda **_kw: _Transport([_response(400, "bad document")], calls),
    )
    monkeypatch.setattr(search_client.asyncio, "sleep", _no_sleep)
    client = AzureSearchClient(_settings())

    with pytest.raises(AzureSearchError, match="upload failed"):
        _run(client.upload_documents("idx", [{"id": "a"}]))

    assert len(calls) == 1, "a non-retryable status must be reported on the first attempt"


def test_upload_honours_a_retry_after_header(monkeypatch):
    """A throttled upload waits the interval the service asked for."""

    calls: list[tuple[str, str, dict | None]] = []
    throttled = _response(429, "slow down")
    throttled.headers["Retry-After"] = "7"
    responses = [throttled, _response(200, {"value": []})]
    slept: list[float] = []

    async def _record_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        search_client.httpx, "AsyncClient", lambda **_kw: _Transport(responses, calls)
    )
    monkeypatch.setattr(search_client.asyncio, "sleep", _record_sleep)
    client = AzureSearchClient(_settings())

    _run(client.upload_documents("idx", [{"id": "a"}]))

    assert slept == [7.0], f"expected the advertised wait to be honoured, slept {slept}"
