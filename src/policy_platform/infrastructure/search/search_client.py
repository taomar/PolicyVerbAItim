"""Thin async Azure AI Search client (direct httpx REST calls, no SDK dependency).

Talks to Azure AI Search directly. Most existing callers use the two shared
indexes (`policy-authoring`, `policy-evidence`) and only read/write documents.
Per-project policy indexes additionally use the management endpoints below.
See `infrastructure/search/indexing.py` for the scoping strategy that keeps
shared-index writes/reads isolated from the resource's pre-existing unrelated
data.
"""
from __future__ import annotations

import asyncio
import logging
import random

import httpx

from policy_platform.infrastructure.errors import describe_exception
from policy_platform.infrastructure.settings import Settings, get_settings

logger = logging.getLogger(__name__)

class AzureSearchError(RuntimeError):
    """Raised when a call to Azure AI Search fails or the resource isn't configured."""


#: Retried because they describe a service that is momentarily unable, not a
#: request that is wrong. A 4xx outside this set is a defect in what we sent —
#: a malformed document, a stale key, an index that does not exist — and
#: retrying it burns time while hiding the error that would have explained it.
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

#: Mirrors `openai_client`, deliberately. The render path has survived this
#: workload for months on these numbers; the upload path had none at all, and
#: inventing different ones here would only mean two behaviours to reason about.
_MAX_ATTEMPTS = 4
_BACKOFF_BASE_SECONDS = 2.0
_BACKOFF_CAP_SECONDS = 20.0


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    """Seconds to wait before attempt `attempt` (1-based, so the first wait is 0)."""

    if retry_after:
        try:
            return min(float(retry_after), _BACKOFF_CAP_SECONDS)
        except ValueError:
            pass  # A date-formatted Retry-After; fall through to our own backoff.
    ceiling = min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _BACKOFF_CAP_SECONDS)
    return random.uniform(0, ceiling)


async def _send_with_retry(
    method: str,
    url: str,
    *,
    headers: dict,
    json: dict | None = None,
    timeout: float,
    label: str,
) -> httpx.Response:
    """Send one Search request, retrying transport failures and busy responses.

    Every operation routed through here is idempotent — `mergeOrUpload`,
    delete-by-key, PUT create-or-replace, and reads — so a retry can at worst
    repeat work, never corrupt it.

    This exists because of a specific, measured failure: a 36-minute index
    rebuild rendered and embedded all 318 documents, uploaded the first batch of
    50, and then lost the whole run to a single transport blip on batch 2. The
    expensive work was already done and correct; there was no second attempt
    because there was no retry anywhere on this path, and the exception carried
    no message, so the recorded reason was the empty string. One momentary
    network fault discarded half an hour of model calls.

    The failure is raised as `AzureSearchError` with a described cause, never a
    bare re-raise, because httpx's timeout and transport exceptions stringify to
    `''` and an empty reason is indistinguishable from no reason.
    """

    last_error: Exception | None = None
    last_response: httpx.Response | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        if attempt > 1:
            retry_after = (
                last_response.headers.get("Retry-After") if last_response is not None else None
            )
            await asyncio.sleep(_retry_delay(attempt - 1, retry_after))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Dispatched by verb rather than `client.request(...)` to keep the
                # exact call shape this module has always used, which is the seam
                # the existing tests substitute against.
                send = getattr(client, method.lower())
                if json is None:
                    resp = await send(url, headers=headers)
                else:
                    resp = await send(url, headers=headers, json=json)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            last_response = None
            logger.warning(
                "Azure Search %s attempt %s/%s failed in transport: %s",
                label,
                attempt,
                _MAX_ATTEMPTS,
                describe_exception(exc),
            )
            continue

        if resp.status_code in _RETRYABLE_STATUSES and attempt < _MAX_ATTEMPTS:
            last_response = resp
            last_error = None
            logger.warning(
                "Azure Search %s attempt %s/%s returned %s; retrying",
                label,
                attempt,
                _MAX_ATTEMPTS,
                resp.status_code,
            )
            continue

        return resp

    if last_response is not None:
        return last_response
    raise AzureSearchError(
        f"Azure Search {label} failed after {_MAX_ATTEMPTS} attempts: "
        f"{describe_exception(last_error) if last_error else 'no response'}"
    )


class AzureSearchClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self._settings.search_enabled

    def _require_enabled(self) -> Settings:
        if not self.enabled:
            raise AzureSearchError("Azure AI Search is not configured (missing endpoint/api key in .env)")
        return self._settings

    def _headers(self) -> dict:
        return {"api-key": self._settings.azure_search_api_key, "Content-Type": "application/json"}

    async def create_index(self, definition: dict) -> dict:
        """Create or replace an index definition by name (Azure Search PUT semantics)."""

        settings = self._require_enabled()
        name = definition.get("name")
        if not isinstance(name, str) or not name.strip():
            raise AzureSearchError("Azure Search index definition must include a non-empty name")
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{name}"
            f"?api-version={settings.azure_search_api_version}"
        )
        resp = await _send_with_retry(
            "PUT", url, headers=self._headers(), json=definition, timeout=60.0, label="index create"
        )
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search index create failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json()

    async def delete_index(self, name: str) -> bool:
        """Delete an index by name. An index that is already absent is success."""

        settings = self._require_enabled()
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{name}"
            f"?api-version={settings.azure_search_api_version}"
        )
        resp = await _send_with_retry(
            "DELETE", url, headers=self._headers(), timeout=60.0, label="index delete"
        )
        if resp.status_code == 404:
            return False
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search index delete failed ({resp.status_code}): {resp.text[:500]}")
        return True

    async def index_exists(self, name: str) -> bool:
        """Return whether an index exists."""

        settings = self._require_enabled()
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{name}"
            f"?api-version={settings.azure_search_api_version}"
        )
        resp = await _send_with_retry(
            "GET", url, headers=self._headers(), timeout=30.0, label="index lookup"
        )
        if resp.status_code == 404:
            return False
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search index lookup failed ({resp.status_code}): {resp.text[:500]}")
        return True

    async def upload_documents(self, index: str, documents: list[dict]) -> dict:
        """mergeOrUpload a batch of documents (safe to call repeatedly/idempotently)."""

        settings = self._require_enabled()
        if not documents:
            return {"value": []}
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{index}/docs/index"
            f"?api-version={settings.azure_search_api_version}"
        )
        body = {"value": [{"@search.action": "mergeOrUpload", **doc} for doc in documents]}
        resp = await _send_with_retry(
            "POST", url, headers=self._headers(), json=body, timeout=60.0, label="upload"
        )
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search upload failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json()

    async def find_ids_by_filter(self, index: str, *, filter_expr: str, page_size: int = 1000) -> list[str]:
        """Return every document `id` matching an OData filter (paged). Used to locate
        stale documents (e.g. from a superseded clause-extraction run) that need
        deleting before re-indexing a corrected replacement set."""

        settings = self._require_enabled()
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{index}/docs/search"
            f"?api-version={settings.azure_search_api_version}"
        )
        ids: list[str] = []
        skip = 0
        while True:
            body = {"search": "*", "filter": filter_expr, "select": "id", "top": page_size, "skip": skip}
            resp = await _send_with_retry(
                "POST", url, headers=self._headers(), json=body, timeout=30.0, label="id query"
            )
            if resp.status_code >= 400:
                raise AzureSearchError(f"Azure Search query failed ({resp.status_code}): {resp.text[:500]}")
            batch = resp.json().get("value", [])
            ids.extend(doc["id"] for doc in batch)
            if len(batch) < page_size:
                break
            skip += page_size
        return ids

    async def find_documents_by_filter(
        self,
        index: str,
        *,
        filter_expr: str,
        select: str,
        page_size: int = 200,
    ) -> list[dict]:
        """Return every document matching an OData filter, with named fields, paged.

        The sibling of :meth:`find_ids_by_filter`, and it exists for one caller:
        validating a projection that is *already built* means reading what the
        index actually holds rather than what a build believed it wrote. Ids
        alone cannot answer that — the question is whether each document's
        retrieval text is a rendering of the record it names, so the text and the
        identifying fields have to come back with it.

        ``select`` is required rather than defaulted. A validation reads a few
        named fields over a whole corpus, and a lookup that silently returned
        every retrievable field would move megabytes to answer a question about
        kilobytes.
        """

        settings = self._require_enabled()
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{index}/docs/search"
            f"?api-version={settings.azure_search_api_version}"
        )
        documents: list[dict] = []
        skip = 0
        while True:
            body = {
                "search": "*",
                "filter": filter_expr,
                "select": select,
                "top": page_size,
                "skip": skip,
            }
            resp = await _send_with_retry(
                "POST", url, headers=self._headers(), json=body, timeout=60.0, label="document query"
            )
            if resp.status_code >= 400:
                raise AzureSearchError(
                    f"Azure Search query failed ({resp.status_code}): {resp.text[:500]}"
                )
            batch = resp.json().get("value", [])
            documents.extend(batch)
            if len(batch) < page_size:
                break
            skip += page_size
        return documents

    async def delete_documents(self, index: str, ids: list[str]) -> dict:
        """Delete documents by key. Safe to call with an empty list."""

        settings = self._require_enabled()
        if not ids:
            return {"value": []}
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{index}/docs/index"
            f"?api-version={settings.azure_search_api_version}"
        )
        body = {"value": [{"@search.action": "delete", "id": doc_id} for doc_id in ids]}
        resp = await _send_with_retry(
            "POST", url, headers=self._headers(), json=body, timeout=60.0, label="delete"
        )
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search delete failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json()

    async def vector_search(
        self,
        index: str,
        *,
        query_text: str,
        vector: list[float] | None,
        policy_ids: list[str] | None = None,
        top: int = 6,
        filter_expr: str | None = None,
        select: str | None = None,
        semantic_configuration: str | None = None,
    ) -> list[dict]:
        """Keyword/semantic search, optionally augmented by a query vector.

        ``filter_expr`` is an OData expression composed by the caller — the
        per-project index needs to scope a query to one *kind* of document and to
        one projection profile, and the expression that does that belongs with
        the schema that names those fields (`search/policy_index.py`), not here.
        It is combined with ``policy_ids`` by conjunction when both are given, so
        neither can widen the other.

        ``select`` overrides the returned field list for callers that need fields
        outside the shared default — a rule document's `rule_id`, its ordinal and
        its parent. Left absent, every existing caller gets the field list it
        always got.

        ``vector=None`` deliberately omits ``vectorQueries``. Retrieval-only
        policy selection uses Azure's semantic reranker over the English corpus
        projection and does not pay for an embedding that produced the same live
        order. Decision retrieval still supplies a vector and remains hybrid.
        """

        settings = self._require_enabled()
        url = (
            f"{settings.azure_search_endpoint.rstrip('/')}/indexes/{index}/docs/search"
            f"?api-version={settings.azure_search_api_version}"
        )
        body: dict = {
            "search": query_text,
            "top": top,
            "select": select
            or (
                "id,policy_id,document_id,document_version,clause_id,clause_number,"
                "section_heading,heading,body,status"
            ),
        }
        if vector is not None:
            body["vectorQueries"] = [
                {"kind": "vector", "vector": vector, "fields": "body_vector", "k": top}
            ]
        if semantic_configuration:
            body["queryType"] = "semantic"
            body["semanticConfiguration"] = semantic_configuration
        clauses: list[str] = []
        if policy_ids:
            if len(policy_ids) == 1:
                clauses.append(f"policy_id eq '{policy_ids[0]}'")
            else:
                # search.in expects a plain delimiter-separated value list (no quoting
                # per-value); safe here since our policy_ids are UUIDs (no commas/pipes).
                id_list = ",".join(policy_ids)
                clauses.append(f"search.in(policy_id, '{id_list}', ',')")
        if filter_expr:
            clauses.append(f"({filter_expr})")
        if clauses:
            body["filter"] = " and ".join(clauses)
        # Deliberately NOT routed through `_send_with_retry`, unlike every other
        # call in this client. This is the serving path: a user is waiting on it,
        # and silently turning one 30-second failure into up to four changes what
        # a timeout *means* to the caller above. The build path has no such
        # caller — it is a background job where a retry costs seconds and a
        # non-retry costs half an hour — which is why the two differ. Revisit
        # only with a decision about serving latency, not as tidying.
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise AzureSearchError(f"Azure Search query failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json().get("value", [])
