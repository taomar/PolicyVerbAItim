"""Per-project Azure AI Search index for case-to-policy retrieval.

One index per project, holding only published policies at the latest approved
version. That restriction is what makes it cheap to keep correct: edits,
approvals, rejections, supersessions and re-extractions all act on *candidates*,
so they cannot change what is indexed. Exactly two events can, and both are
wired — publishing rebuilds a project's index (`candidate_rules.publish`), and
deleting the project drops it (`policy_set_teardown`). A manual rebuild endpoint
is the repair path when a best-effort build did not complete.

Input shape for one policy
--------------------------
`build_policy_document` consumes a `grounding_projection_v1` dict, produced by
`projection/published_case_payload.py` from the active approved version. The
fields it reads:

```
{
    "policy_version_id": "published version id",
    "version_number": 3,
    "provision_key": "stable policy key across versions",
    "heading_path": ["Handbook", "Leave"],
    "rules": [
        {
            "id": "rule id",
            "title": "optional generated/display title",
            "statement": "verbatim or compact rule statement",
            "conditions": ["when text", {"text": "when text"}],
            "effects": ["then text", {"text": "then text"}],
        }
    ],
}
```

The index stores ids, counts, headings, retrieval text and embeddings. It does
not store the light JSON payload: PostgreSQL remains the source of truth and the
payload is rebuilt at evaluation time, so the index can never become a second
authority on what a policy says.

THREE KINDS OF DOCUMENT, ONE INDEX
----------------------------------
The index holds three content types, told apart by the filterable `content_type`
field so one schema serves all three and a query says which it wants:

  * `policy`   — one per published provision, as it always was.
  * `rule`     — one per authoritative rule, emitted **only** for a provision
                 holding more than `LARGE_POLICY_RULE_THRESHOLD` rules. Below
                 that a provision reads as one governing statement and its own
                 document already carries it; above it the provision is a
                 schedule of independent rows, and a row past the policy
                 document's retrieval-text ceiling was previously unreachable —
                 it could not surface, so it could not elevate the provision
                 that holds it. A rule document is how it now can.
  * `manifest` — exactly one per project, and the only document that says
                 whether the other two may be matched against. See below.

WHY THE RETRIEVAL TEXT IS ENGLISH, AND WHY IT IS NOT THE POLICY
---------------------------------------------------------------
A query and the text it is scored against must be in one language or the match
is not a match. The request side reduces every question to the processing
language before anything retrieves, so the corpus side renders each policy's and
each rule's *retrieval text* to the same language at publish time and indexes
that. The rendering is a **projection**: non-authoritative, never served as
policy content, never shown as evidence, never exported, and never what a
citation resolves to. The original verbatim spans stay in PostgreSQL, untouched
and unindexed for matching, and remain the only thing a citation can reach.

Every document carries the `projection_profile` it was rendered under, so a
corpus rendered under a superseded contract is detectable rather than silently
matched against.

THE MANIFEST, AND WHY READINESS IS A DOCUMENT
---------------------------------------------
A rebuild that uploads four fifths of a corpus leaves an index that answers
queries — confidently, from four fifths of the policies. Nothing in the document
set can say that, because each document that *did* upload is individually
correct. So readiness is written down: the manifest is set to `incomplete`
before anything is uploaded and moved to `ready` only once every expected policy
and rule document has been accepted. Retrieval reads it first and refuses when it
is not ready, which is why a half-built projection cannot be matched against.
Rollback is a rebuild from the authoritative database; there is nothing to
un-upload and nothing to re-extract.

Two mechanisms, one index
-------------------------
This module records what the app last built (`policy_index_states`, read by
`read_policy_index_state` and interpreted by `policy_index_freshness`).
`ai_case_project` probes Azure live when a case is actually run. They answer
different questions and may legitimately disagree — an index deleted out of band
leaves the record reading current — so they are kept apart on purpose. What they
do share is written once here: `policy_index_name`, `policy_document_id` and
`policy_index_filter`.

Vector/semantic configuration note
----------------------------------
The repository contains the field used by the existing authoring index
(`body_vector`) and the embedding dimension setting, but not the live authoring
index schema. The definition below therefore uses the same vector field name and
the configured embedding dimension, with the 2025-09-01 REST field names
(`dimensions`, `vectorSearchProfile`), a standard HNSW cosine profile and a
semantic configuration over heading/retrieval text. If the live authoring index
uses different profile names, that cannot be determined from this repo alone.
"""
from __future__ import annotations

import hashlib
from json import JSONDecodeError
import logging
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_platform.domain.models import PolicyIndexBuild, PolicyIndexState
from policy_platform.infrastructure.ai.openai_client import AzureOpenAIClient
from policy_platform.infrastructure.assistants.ai_case_language import (
    ENGLISH_PROJECTION_PROFILE,
    EnglishProjectionReadiness,
    INDEX_PROJECTION_UNAVAILABLE,
    PROCESSING_LANGUAGE,
)
from policy_platform.infrastructure.errors import describe_exception
from policy_platform.infrastructure.ingestion.mixed_script_text import (
    INTERLEAVED_TEXT_CODE,
    interleaved_tokens,
)
from policy_platform.infrastructure.projection.policy_rule_slice import (
    LARGE_POLICY_RULE_THRESHOLD,
    RULE_INDEX_SCOPE_ALL as _RULE_INDEX_SCOPE_ALL,
    RULE_INDEX_SCOPE_LARGE_POLICY as _RULE_INDEX_SCOPE_LARGE_POLICY,
    rule_documents_expected,
    rule_text,
    rule_text_parts,
)
from policy_platform.infrastructure.quality.projection_faithfulness import (
    FINDING_EMBEDDING_UNAVAILABLE,
    PROJECTION_QUALITY_PROFILE,
    ProjectedRecord,
    ProjectionQualityReport,
    QUALITY_PASSED,
    known_quality_profile,
    quality_profile as resolve_quality_profile,
    unvalidated_report,
    validate_projection,
)
from policy_platform.infrastructure.search.english_projection import (
    EnglishProjectionError,
    project_texts_to_english,
)
from policy_platform.infrastructure.search.policy_index_build_progress import (
    NULL_PROGRESS,
    BuildProgress,
    RecordedBuildProgress,
    acquire_build_slot,
    finish_build,
    latest_state_status_for,
    new_operation_id,
    record_deferred_build,
    running_build,
)
from policy_platform.infrastructure.search.search_client import AzureSearchClient
from policy_platform.infrastructure.settings import Settings, get_settings

logger = logging.getLogger(__name__)

POLICY_INDEX_PREFIX = "policy-cases-"
_NAME_DIGEST_CHARS = 16
_MAX_INDEX_NAME_LENGTH = 128
#: The most retrieval text one *policy* document carries. It is a bound on what
#: one embedding can meaningfully represent, not a claim about the policy: a
#: single vector over a 188,000-character schedule says almost nothing about any
#: one of its rows. Raising it would not repair that. What repairs it is the rule
#: document — a row past this ceiling now has its own document, its own vector
#: and its own rank, and surfaces the provision that holds it. Provisions at or
#: under `LARGE_POLICY_RULE_THRESHOLD` are comfortably inside this ceiling, which
#: is why the threshold is where rule documents begin.
_MAX_RETRIEVAL_TEXT_CHARS = 12_000
#: The most retrieval text one *rule* document carries. A rule that is longer
#: than this is one passage, not a schedule, so there is nothing below it to
#: split into; the tail is not matched and the rule is still reachable by its
#: opening, its structured terms and its parent policy document.
_MAX_RULE_TEXT_CHARS = 8_000
_VECTOR_PROFILE = "policy-cases-vector-profile"
_VECTOR_ALGORITHM = "policy-cases-hnsw"
_SEMANTIC_CONFIG = "policy-cases-semantic"
POLICY_SEMANTIC_CONFIG = _SEMANTIC_CONFIG

#: What a document in this index is. Filterable, so a query asks for one kind
#: and never has to tell them apart after the fact.
CONTENT_TYPE_POLICY = "policy"
CONTENT_TYPE_RULE = "rule"
CONTENT_TYPE_MANIFEST = "manifest"

#: Whether every document a rebuild expected actually landed. `incomplete` is
#: written first and is what a crashed or partially-rejected rebuild leaves
#: behind, so the failure state is the one that survives an interruption.
#:
#: It answers **completeness only**. Whether what landed is a faithful rendering
#: of the record it names is a second, independent claim, carried in the
#: manifest's quality fields and validated by
#: `quality/projection_faithfulness`. Keeping them apart is deliberate: a corpus
#: can be complete and unfaithful, and a single flag conflating the two would
#: let a successful upload vouch for a rendering nobody checked.
MANIFEST_READY = "ready"
MANIFEST_INCOMPLETE = "incomplete"

#: WHICH RULES A BUILD GIVES THEIR OWN DOCUMENT, NAMED SO A READER CAN BE ASKED.
#:
#: `large_policy_rules_v1` is what every corpus built before this constant
#: existed holds: a document per rule for provisions above
#: `LARGE_POLICY_RULE_THRESHOLD` and none at all below it.
#:
#: `all_published_rules_v1` gives every published rule its own document. It is
#: what a rule-first retrieval needs — a rule that has no document cannot be
#: found by a rule query, whatever its parent's size — and it is a superset, so
#: it changes nothing for a reader that only wants the large-policy rows: those
#: documents carry `rule_count`, and a filter on it selects exactly the old set.
#: See `policy_rule_content_filter`.
#:
#: The scope a corpus was actually built under is written on its manifest, and
#: is absent on every manifest written before this existed. Absent is the honest
#: answer for those, and it is what a rule-first query refuses on: an index that
#: holds no document for a small policy's rules would answer a rule query with
#: silence about them, which is indistinguishable from "nothing there bears".
#: The names themselves are defined at the projection boundary, which the build
#: and the quality check both already depend on, and re-exported here so the
#: many callers that import them from this module are unaffected. They were
#: declared here once and the quality check could not see them, which is how a
#: correct corpus came to be failed 36 times.
RULE_INDEX_SCOPE_LARGE_POLICY = _RULE_INDEX_SCOPE_LARGE_POLICY
RULE_INDEX_SCOPE_ALL = _RULE_INDEX_SCOPE_ALL

#: The scope a build performed now writes and stamps.
RULE_INDEX_SCOPE = RULE_INDEX_SCOPE_ALL

#: The fields a validation reads back off a live index. Named here, with the
#: schema that declares them, because a `select` list is part of how documents
#: in this index are addressed — the same reason `policy_index_filter` lives
#: here. The vector is not among them and cannot be: it is not retrievable, and
#: a validation compares text against text.
_VALIDATION_SELECT = (
    "id,policy_version_id,parent_document_id,projection_profile,retrieval_text,content_type"
)

#: The manifest's own fields, for reading one back before annotating it. Named
#: rather than wildcarded so a field added to the schema for some other purpose
#: cannot silently start round-tripping through a validation write.
_MANIFEST_SELECT = (
    "id,policy_set_key,policy_version_id,version_number,content_type,manifest_state,"
    "projection_profile,projection_language,expected_policy_documents,"
    "expected_rule_documents,uploaded_documents,indexed_at,status,document_id,"
    "document_version,provision_key,heading_path,section_heading,heading,body,"
    "retrieval_text,rule_index_scope"
)

#: The manifest fields a rule-first query needs before it may run: which rule
#: documents this corpus actually holds. Read on its own, and only on the path
#: that asks — the default retrieval path makes no extra round trip for it.
_RULE_SCOPE_SELECT = "id,rule_index_scope"

#: How many documents one upload call carries. Azure AI Search accepts batches of
#: up to 1,000 documents or 16 MB; a policy document carries an embedding and a
#: passage of text, so the count is bounded well under the limit rather than
#: relying on the size bound being reached first.
_UPLOAD_BATCH_SIZE = 50

PolicyIndexBuildState = Literal["built", "skipped", "failed"]
PolicyIndexDropState = Literal["dropped", "skipped", "failed"]
PolicyIndexLastAttempt = Literal["built", "skipped", "failed", "never_attempted"]
PolicyIndexFreshnessState = Literal["current", "stale", "nothing_to_index", "unknown"]

# Kept as two axes because constraint 5 forbids collapsing "what happened"
# into "what is usable now": a failed attempt can leave a current index, and a
# skipped attempt says nothing about freshness.
POLICY_INDEX_LAST_BUILT = "built"
POLICY_INDEX_LAST_SKIPPED = "skipped"
POLICY_INDEX_LAST_FAILED = "failed"
POLICY_INDEX_LAST_NEVER_ATTEMPTED = "never_attempted"
POLICY_INDEX_FRESHNESS_CURRENT = "current"
POLICY_INDEX_FRESHNESS_STALE = "stale"
POLICY_INDEX_FRESHNESS_NOTHING_TO_INDEX = "nothing_to_index"
POLICY_INDEX_FRESHNESS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class PolicyIndexFreshness:
    """Freshness derived from the app's recorded build state, not Azure Search.

    This is intentionally not the same mechanism as
    `ai_case_project.py`'s live retrieval guard. The retrieval path asks Azure
    whether an index exists and whether returned hits belong to the active
    approved version: "can this query safely run right now?" This derivation
    reads `policy_index_states`: "what did the app last try to build, and does
    the last recorded successful build match the active version?" They can
    legitimately disagree if the Search index is edited or deleted out of band,
    so unifying them would make either the page-load state expensive and brittle
    or the retrieval guard blind to live drift.
    """

    last_attempt: PolicyIndexLastAttempt
    freshness: PolicyIndexFreshnessState


@dataclass(frozen=True)
class PolicyIndexBuildOutcome:
    """Structured state for best-effort policy index builds.

    `state` is the headline because a bare document count cannot distinguish
    "there were no published policies" from "Search was down and nothing was
    indexed." A failed build means publish may continue, but the caller must
    report that the grounding index may be stale or absent.

    `projection_profile` is set **only** on a build that finished — every
    expected document uploaded and the manifest moved to ready. A partial or
    failed build leaves it null, which is the same fact the manifest carries and
    the same fact the retrieval gate reads: this corpus may not be matched
    against yet.
    """

    state: PolicyIndexBuildState
    policy_set_key: str
    index_name: str
    version_number: int | None
    document_count: int
    indexed_at: str
    error: str | None = None
    policy_document_count: int = 0
    rule_document_count: int = 0
    projection_profile: str | None = None
    manifest_state: str | None = None
    #: The faithfulness verdict this build reached, when it got far enough to
    #: reach one. Null when the build failed before the corpus existed to check,
    #: which is a different fact from a corpus that was checked and refused —
    #: and both are different from one that passed. The readiness gate reads the
    #: manifest rather than this, so this is a report and never an authority.
    quality: ProjectionQualityReport | None = None


@dataclass(frozen=True)
class PolicyIndexDropOutcome:
    """Structured state for best-effort project index deletion."""

    state: PolicyIndexDropState
    policy_set_key: str
    index_name: str
    deleted: bool | None
    attempted_at: str
    error: str | None = None


def policy_index_name(policy_set_key: str) -> str:
    """Derive a valid, collision-resistant Azure Search index name for a project."""

    digest = hashlib.sha256(policy_set_key.encode("utf-8")).hexdigest()[:_NAME_DIGEST_CHARS]
    stem = re.sub(r"[^a-z0-9]+", "-", policy_set_key.lower())
    stem = re.sub(r"-{2,}", "-", stem).strip("-") or "project"

    suffix = f"-{digest}"
    available = _MAX_INDEX_NAME_LENGTH - len(POLICY_INDEX_PREFIX) - len(suffix)
    if len(stem) > available:
        stem = stem[:available].rstrip("-") or "project"
    name = f"{POLICY_INDEX_PREFIX}{stem}{suffix}"
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", name):
        raise ValueError(f"derived invalid Azure Search index name {name!r}")
    if "--" in name or len(name) > _MAX_INDEX_NAME_LENGTH:
        raise ValueError(f"derived invalid Azure Search index name {name!r}")
    return name


def policy_index_freshness(
    state: PolicyIndexState | None,
    active_version_number: int | None,
    *,
    expected_projection_profile: str | None = None,
) -> PolicyIndexFreshness:
    """Derive recorded freshness without opening a database session or probing Search.

    Staleness has two axes, and a record can be behind on either. The version is
    the older one: the index was built for a version that is no longer active.
    The **projection profile** is the second: the index was built for the right
    version but under a superseded rendering contract, so a query rendered under
    the current one is not comparable with the text it would be scored against.
    A profile mismatch is therefore stale even when the version matches — the
    repair is the same rebuild, and reporting `current` would send an operator
    looking for a problem the record can already prove.

    ``expected_projection_profile`` is optional so every existing caller keeps
    the version-only reading it already had; passing it widens the check and
    never narrows it.
    """

    if state is None:
        last_attempt: PolicyIndexLastAttempt = POLICY_INDEX_LAST_NEVER_ATTEMPTED
    else:
        last_attempt = cast(PolicyIndexLastAttempt, state.status)

    if active_version_number is None:
        return PolicyIndexFreshness(
            last_attempt=last_attempt,
            freshness=POLICY_INDEX_FRESHNESS_NOTHING_TO_INDEX,
        )
    if state is None:
        return PolicyIndexFreshness(
            last_attempt=last_attempt,
            freshness=POLICY_INDEX_FRESHNESS_STALE,
        )
    if state.status == POLICY_INDEX_LAST_SKIPPED and state.indexed_version_number is None:
        # Search was unavailable and nothing was ever indexed, so the record
        # cannot say whether an index matches the active version. `unknown` is
        # the honest answer; `stale` would assert a comparison never made.
        return PolicyIndexFreshness(
            last_attempt=last_attempt,
            freshness=POLICY_INDEX_FRESHNESS_UNKNOWN,
        )
    # A skipped attempt keeps whatever version was last indexed
    # (`record_policy_index_build_state` preserves it), so when that version is
    # known the comparison is as sound here as for a failed attempt. Returning
    # `unknown` because the last attempt was skipped would throw away a
    # staleness the record can prove.
    if state.indexed_version_number == active_version_number:
        if (
            expected_projection_profile is not None
            and getattr(state, "projection_profile", None) != expected_projection_profile
        ):
            return PolicyIndexFreshness(
                last_attempt=last_attempt,
                freshness=POLICY_INDEX_FRESHNESS_STALE,
            )
        return PolicyIndexFreshness(
            last_attempt=last_attempt,
            freshness=POLICY_INDEX_FRESHNESS_CURRENT,
        )
    return PolicyIndexFreshness(
        last_attempt=last_attempt,
        freshness=POLICY_INDEX_FRESHNESS_STALE,
    )


def policy_index_filter(
    policy_set_key: str,
    policy_version_id: str | None = None,
    *,
    content_type: str | None = None,
    projection_profile: str | None = None,
) -> str:
    """An OData filter selecting a project's documents in its policy index.

    How documents in this index are addressed lives here, with the schema that
    names the fields and the builder that writes them. Retrieval asks the same
    question when it probes whether anything is indexed, and imports this rather
    than composing `policy_set_key eq …` a second time: renaming that field, or
    finding the escaping has to handle another character, must not be a change
    that has to be remembered in two places to keep a project's documents
    matching.

    ``content_type`` narrows to policy, rule or manifest documents;
    ``projection_profile`` narrows to documents rendered under one contract.
    Both default to absent, so every existing caller still selects the whole of
    a project exactly as it did — which is what the stale-document sweep needs.
    """

    clauses = [f"policy_set_key eq {_odata_string(policy_set_key)}"]
    if policy_version_id:
        clauses.append(f"policy_version_id eq {_odata_string(policy_version_id)}")
    if content_type:
        clauses.append(f"content_type eq {_odata_string(content_type)}")
    if projection_profile:
        clauses.append(f"projection_profile eq {_odata_string(projection_profile)}")
    return " and ".join(clauses)


def policy_rule_content_filter(
    policy_set_key: str,
    *,
    projection_profile: str,
    large_policies_only: bool,
    threshold: int = LARGE_POLICY_RULE_THRESHOLD,
) -> str:
    """The filter a rule query uses, and the one knob that separates the modes.

    Both modes ask for this project's rule documents under one rendering
    contract. They differ in a single clause, and it is the clause that keeps the
    default mode's behaviour byte-for-byte what it was after the corpus started
    carrying a document for every rule:

    * ``large_policies_only=True`` adds ``rule_count gt threshold``, selecting
      exactly the documents a `large_policy_rules_v1` corpus would have held and
      no others. A rule of a small provision is simply not in the result set, the
      way it was not in the index before.
    * ``large_policies_only=False`` leaves it off, which is the rule-first mode's
      whole point: every published rule is a candidate on its own terms.

    Expressed as a predicate rather than as two corpora because it has to be
    both — one build, read two ways — and because the alternative is a second
    index whose staleness is a second thing to get wrong.
    """

    expression = policy_index_filter(
        policy_set_key,
        content_type=CONTENT_TYPE_RULE,
        projection_profile=projection_profile,
    )
    if large_policies_only:
        expression += f" and rule_count gt {int(threshold)}"
    return expression


def policy_index_ready_filter(
    policy_set_key: str,
    *,
    projection_profile: str,
    quality_profile: str = PROJECTION_QUALITY_PROFILE,
) -> str:
    """The filter that answers "may this project be matched against, right now".

    One expression, so the question is asked in one place: the project's manifest
    document, rendered under the profile the query side will use, in the `ready`
    state, and **validated as a faithful rendering under the quality profile this
    build applies**. Anything else — no manifest, a manifest under a superseded
    profile, a manifest left `incomplete` by a rebuild that did not finish, a
    manifest whose corpus was never validated, one that failed validation, or one
    validated under a different statement of what validation means — fails to
    match, and failing to match is the refusal.

    THE FOURTH CLAUSE IS NEW, AND IT IS NOT A FORMALITY

    The first three say a corpus was *built*. Only the fourth says it was checked
    against the record it was built from. Before it existed, an index became
    load-bearing on the strength of a rendering call that returned, an embedding
    call that returned and an upload that was acknowledged — none of which is
    evidence about meaning. A corpus that has not been validated therefore does
    not match here, and that is intended to include every corpus built before
    this clause existed: `quality_state` is absent on those manifests, an absent
    field satisfies no equality, and the repair is one validation run.
    """

    return (
        policy_index_filter(
            policy_set_key,
            content_type=CONTENT_TYPE_MANIFEST,
            projection_profile=projection_profile,
        )
        + f" and manifest_state eq {_odata_string(MANIFEST_READY)}"
        + f" and quality_state eq {_odata_string(QUALITY_PASSED)}"
        + f" and quality_profile eq {_odata_string(quality_profile)}"
    )


def policy_index_definition(name: str, *, vector_dimensions: int | None = None) -> dict:
    """Return the Azure AI Search schema for one project's policy index."""

    dimensions = vector_dimensions or get_settings().azure_openai_embedding_dimensions
    return {
        "name": name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True, "retrievable": True},
            {"name": "policy_set_key", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "policy_version_id", "type": "Edm.String", "filterable": True, "retrievable": True},
            {
                "name": "version_number",
                "type": "Edm.Int32",
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            {"name": "provision_key", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
            {"name": "heading_path", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "retrieval_text", "type": "Edm.String", "searchable": True, "retrievable": True},
            {
                "name": "body_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": dimensions,
                "vectorSearchProfile": _VECTOR_PROFILE,
            },
            {"name": "rule_count", "type": "Edm.Int32", "filterable": True, "sortable": True, "retrievable": True},
            # ── the rule document's own fields ──────────────────────
            # Null on a policy document and on the manifest. Filterable so a
            # query can scope to the rules of named provisions, sortable so a
            # tie can be broken by the document's own order rather than by
            # whatever order the service happened to return.
            {"name": "rule_id", "type": "Edm.String", "filterable": True, "retrievable": True},
            {
                "name": "rule_ordinal",
                "type": "Edm.Int32",
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            # The policy document this rule belongs to, by key. Carried rather
            # than derived so a rule hit can elevate its parent without the
            # reader recomputing a digest, and filterable so the parent's own
            # document and its rules can be fetched in one expression.
            {"name": "parent_document_id", "type": "Edm.String", "filterable": True, "retrievable": True},
            # ── the projection this document was rendered under ─────
            # Filterable because it is a *gate*, not a label: a query selects
            # documents rendered under the contract it was itself rendered
            # under, and a corpus under a superseded contract simply does not
            # match rather than matching badly.
            {"name": "projection_profile", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "projection_language", "type": "Edm.String", "filterable": True, "retrievable": True},
            # ── the manifest's own fields ───────────────────────────
            {"name": "manifest_state", "type": "Edm.String", "filterable": True, "retrievable": True},
            # Which rules this corpus gave their own document. Filterable for the
            # same reason `projection_profile` is: a rule-first query is only
            # answerable over a corpus that holds every rule, and a corpus built
            # under the older scope must fail to satisfy the question rather than
            # answer it thinly. Absent on every manifest written before it
            # existed, and absent is the refusal.
            {"name": "rule_index_scope", "type": "Edm.String", "filterable": True, "retrievable": True},
            {
                "name": "expected_policy_documents",
                "type": "Edm.Int32",
                "filterable": True,
                "retrievable": True,
            },
            {
                "name": "expected_rule_documents",
                "type": "Edm.Int32",
                "filterable": True,
                "retrievable": True,
            },
            {
                "name": "uploaded_documents",
                "type": "Edm.Int32",
                "filterable": True,
                "retrievable": True,
            },
            # ── whether the corpus was checked against the record ───
            # A second, independent claim from `manifest_state`, and the reason
            # they are separate fields rather than one status: a corpus can be
            # complete and unfaithful. `quality_state` is filterable because it
            # is a gate — the readiness filter requires it — and the profile
            # beside it is filterable for the same reason a rendering profile
            # is: a corpus validated under one statement of quality must not
            # satisfy a gate asking for another.
            #
            # All of them are **absent on a manifest written before validation
            # existed**, which is the whole compatibility story: an absent field
            # satisfies no equality, so those projects read as unvalidated and
            # are refused rather than grandfathered in.
            {"name": "quality_state", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "quality_profile", "type": "Edm.String", "filterable": True, "retrievable": True},
            {
                "name": "quality_checked_documents",
                "type": "Edm.Int32",
                "filterable": True,
                "retrievable": True,
            },
            {
                "name": "quality_structural_findings",
                "type": "Edm.Int32",
                "filterable": True,
                "retrievable": True,
            },
            # Scores, not text. A double rather than a string so a reader can
            # sort and threshold on them without parsing, and there is nothing
            # in either that could carry a policy sentence.
            {"name": "quality_min_similarity", "type": "Edm.Double", "retrievable": True},
            {"name": "quality_mean_similarity", "type": "Edm.Double", "retrievable": True},
            {"name": "quality_validated_at", "type": "Edm.String", "retrievable": True},
            {"name": "indexed_at", "type": "Edm.String", "retrievable": True},
            # Compatibility fields keep AzureSearchClient.vector_search usable
            # against this index without changing its live callers.
            {"name": "policy_id", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "document_id", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "document_version", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "clause_id", "type": "Edm.String", "retrievable": True},
            {"name": "clause_number", "type": "Edm.String", "retrievable": True},
            {"name": "section_heading", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "heading", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "body", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "status", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "content_type", "type": "Edm.String", "filterable": True, "retrievable": True},
        ],
        "vectorSearch": {
            "algorithms": [{"name": _VECTOR_ALGORITHM, "kind": "hnsw", "hnswParameters": {"metric": "cosine"}}],
            "profiles": [{"name": _VECTOR_PROFILE, "algorithm": _VECTOR_ALGORITHM}],
        },
        "semantic": {
            "defaultConfiguration": _SEMANTIC_CONFIG,
            "configurations": [
                {
                    "name": _SEMANTIC_CONFIG,
                    "prioritizedFields": {
                        "titleField": {"fieldName": "heading"},
                        "prioritizedContentFields": [{"fieldName": "retrieval_text"}],
                        "prioritizedKeywordsFields": [{"fieldName": "provision_key"}],
                    },
                }
            ],
        },
    }


def policy_document_id(*, policy_version_id: str, provision_key: str) -> str:
    """Stable key for one published policy in the project index."""

    digest = hashlib.sha256(f"{policy_version_id}\0{provision_key}".encode("utf-8")).hexdigest()[:24]
    return f"policy-{digest}"


def policy_rule_document_id(
    *, policy_version_id: str, provision_key: str, rule_id: str
) -> str:
    """Stable key for one published rule in the project index.

    A pure function of the version, the provision and the rule id, so the same
    corpus always produces the same key and a rebuild is an overwrite rather
    than an accumulation. It is also what makes the shrink case correct: when a
    provision falls to or below the threshold its rules stop being emitted, the
    keys they held are no longer in the live set, and the stale sweep removes
    exactly them.
    """

    digest = hashlib.sha256(
        f"{policy_version_id}\0{provision_key}\0{rule_id}".encode("utf-8")
    ).hexdigest()[:24]
    return f"rule-{digest}"


def policy_index_manifest_id(policy_set_key: str) -> str:
    """The one manifest key for a project, stable across versions and profiles.

    Deliberately not keyed by version or profile. There is exactly one answer to
    "may this project be matched against right now", and a key that varied would
    let two manifests coexist — one of them ready, for a version nobody is
    querying — which is the ambiguity the manifest exists to remove.
    """

    digest = hashlib.sha256(policy_set_key.encode("utf-8")).hexdigest()[:24]
    return f"manifest-{digest}"


def build_policy_document(
    *,
    policy_set_key: str,
    projection: dict,
    vector: Sequence[float],
    retrieval_text: str | None = None,
    projection_profile: str | None = None,
) -> dict:
    """Build one Azure Search document from one policy's grounding projection.

    ``retrieval_text`` is the English projection when one was made. It is passed
    in rather than derived here because rendering it is a call to a model, and a
    document builder that could make one would be a document builder that could
    fail halfway through a corpus. When it is absent the source-derived text is
    used and ``projection_profile`` stays null — an honest "this document was
    not projected", which the readiness gate reads as not matchable.
    """

    metadata = _projection_metadata(projection)
    policy_version_id = str(metadata["policy_version_id"])
    version_number = int(metadata["version_number"])
    provision_key = str(metadata["provision_key"])
    heading_parts = _strings(metadata.get("heading_path", []))
    rules = _projection_rules(projection)
    source_text = _retrieval_text_for_projection(projection)
    # The source is already bounded before rendering. A rendering can be longer
    # than its source, especially across languages; cutting it back to the source
    # ceiling after it passed preservation silently drops the tail and makes the
    # stored text differ from the text whose vector was embedded. Keep a supplied
    # projection exactly as rendered. Only the unprojected fallback is cut here.
    indexed_text = (
        retrieval_text.rstrip()
        if retrieval_text is not None
        else source_text[:_MAX_RETRIEVAL_TEXT_CHARS].rstrip()
    )
    heading_path = " > ".join(heading_parts)
    heading = heading_parts[-1] if heading_parts else provision_key

    return {
        "id": policy_document_id(policy_version_id=policy_version_id, provision_key=provision_key),
        "policy_set_key": policy_set_key,
        "policy_version_id": policy_version_id,
        "version_number": version_number,
        "provision_key": provision_key,
        "heading_path": heading_path,
        "retrieval_text": indexed_text,
        "body_vector": list(vector),
        "rule_count": len(rules),
        "policy_id": provision_key,
        "document_id": policy_set_key,
        "document_version": policy_version_id,
        "clause_id": "",
        "clause_number": "",
        "section_heading": heading_path,
        "heading": heading,
        "body": indexed_text,
        "status": "published",
        "content_type": CONTENT_TYPE_POLICY,
        "projection_profile": projection_profile,
        "projection_language": PROCESSING_LANGUAGE if projection_profile else None,
    }


def build_rule_document(
    *,
    policy_set_key: str,
    projection: dict,
    rule: dict,
    rule_ordinal: int,
    vector: Sequence[float],
    retrieval_text: str | None = None,
    projection_profile: str | None = None,
) -> dict:
    """Build one Azure Search document for one authoritative rule.

    It carries its parent's identity in full — the same `provision_key`,
    `policy_version_id` and `document_version` the policy document carries — for
    two reasons. A rule hit has to be attributable to the provision that holds it
    without a second lookup, and the version guard that tells a current hit from
    a superseded one reads `document_version` on every hit whatever kind it is.

    What it does **not** carry is the rule's authoritative content. The indexed
    text is the projection; the rule itself stays in PostgreSQL and is what a
    citation resolves to.
    """

    metadata = _projection_metadata(projection)
    policy_version_id = str(metadata["policy_version_id"])
    version_number = int(metadata["version_number"])
    provision_key = str(metadata["provision_key"])
    heading_parts = _strings(metadata.get("heading_path", []))
    heading_path = " > ".join(heading_parts)
    heading = heading_parts[-1] if heading_parts else provision_key
    rule_id = str(rule.get("rule_id") or "")
    source_text = rule_retrieval_source_text(projection, rule)
    indexed_text = (
        retrieval_text.rstrip()
        if retrieval_text is not None
        else source_text[:_MAX_RULE_TEXT_CHARS].rstrip()
    )

    return {
        "id": policy_rule_document_id(
            policy_version_id=policy_version_id,
            provision_key=provision_key,
            rule_id=rule_id,
        ),
        "policy_set_key": policy_set_key,
        "policy_version_id": policy_version_id,
        "version_number": version_number,
        "provision_key": provision_key,
        "heading_path": heading_path,
        "retrieval_text": indexed_text,
        "body_vector": list(vector),
        "rule_count": len(_projection_rules(projection)),
        "rule_id": rule_id,
        "rule_ordinal": rule_ordinal,
        "parent_document_id": policy_document_id(
            policy_version_id=policy_version_id, provision_key=provision_key
        ),
        "policy_id": provision_key,
        "document_id": policy_set_key,
        "document_version": policy_version_id,
        "clause_id": "",
        "clause_number": "",
        "section_heading": heading_path,
        "heading": heading,
        "body": indexed_text,
        "status": "published",
        "content_type": CONTENT_TYPE_RULE,
        "projection_profile": projection_profile,
        "projection_language": PROCESSING_LANGUAGE if projection_profile else None,
    }


def build_index_manifest_document(
    *,
    policy_set_key: str,
    policy_version_id: str | None,
    version_number: int | None,
    projection_profile: str,
    expected_policy_documents: int,
    expected_rule_documents: int,
    uploaded_documents: int,
    state: str,
    indexed_at: str,
    quality: ProjectionQualityReport | None = None,
    rule_index_scope: str = RULE_INDEX_SCOPE,
) -> dict:
    """The document that says whether this project may be matched against.

    It carries no vector and no retrieval text, so it can never surface in a
    query for policies or rules: those queries filter on `content_type`, and a
    manifest has none of the fields they select. It is read by exactly one
    question, expressed as exactly one filter — :func:`policy_index_ready_filter`.

    ``quality`` is the verdict of the faithfulness validation, and it is written
    onto the same document as completeness deliberately: the two claims are read
    by one filter in one round trip, so there is no window in which a reader can
    see one without the other. Absent when no validation was made, and absent is
    what the gate refuses on — a manifest that carried a null quality state would
    say the same thing, and this way a manifest written before validation existed
    and one written by a build that skipped it are indistinguishable, which they
    should be.

    What it never carries is a **finding**. The counts and the two scores go on;
    the itemised findings stay in the report the caller holds and the endpoint
    serves. A document in a search index is the wrong place to accumulate a list
    that grows with the size of a broken corpus.
    """

    document = {
        "id": policy_index_manifest_id(policy_set_key),
        "policy_set_key": policy_set_key,
        "policy_version_id": policy_version_id or "",
        "version_number": version_number,
        "content_type": CONTENT_TYPE_MANIFEST,
        "manifest_state": state,
        "rule_index_scope": rule_index_scope,
        "projection_profile": projection_profile,
        "projection_language": PROCESSING_LANGUAGE,
        "expected_policy_documents": expected_policy_documents,
        "expected_rule_documents": expected_rule_documents,
        "uploaded_documents": uploaded_documents,
        "indexed_at": indexed_at,
        "status": "published",
        # The compatibility fields the shared client selects. Empty rather than
        # absent so a select list that names them does not fail on this document.
        "document_id": policy_set_key,
        "document_version": policy_version_id or "",
        "provision_key": "",
        "heading_path": "",
        "section_heading": "",
        "heading": "",
        "body": "",
        "retrieval_text": "",
    }
    if quality is not None:
        document.update(
            {
                "quality_state": quality.state,
                "quality_profile": quality.profile,
                "quality_checked_documents": quality.checked_documents,
                "quality_structural_findings": quality.structural_findings,
                "quality_min_similarity": quality.minimum_similarity,
                "quality_mean_similarity": quality.mean_similarity,
                "quality_validated_at": quality.validated_at,
            }
        )
    return document


def rule_retrieval_source_text(projection: dict, rule: dict) -> str:
    """Everything about one rule a question could match, in the source language.

    Delegates to :func:`policy_rule_slice.rule_text` — the function that already
    defines that set for the request-side selection — so the corpus is indexed
    on exactly what the selection scores. Two definitions of "the rule's text"
    would be two rankings, and the fusion that combines them would be combining
    answers to two different questions.

    The heading is prepended because a rule document is read on its own, without
    the provision around it, and where a row sits is part of what it is.
    """

    return _rule_retrieval(projection, rule)[0]


def rule_retrieval_opaque_spans(
    projection: dict, rule: dict
) -> tuple[tuple[int, int], ...]:
    """Where the machine-made terms sit inside that text, as the projection recorded it.

    These are generated keys — slugs of a phrase, closed vocabularies — not
    language. Rendering them into another language is meaningless, and letting a
    renderer decide that for itself means letting it guess from shape, which
    fails on exactly the ones that read like words.

    Positions rather than words, for the reason :func:`rule_text_parts` gives:
    the same generated value can occur twice in one rule, and can also occur
    inside a sentence that merely uses the word. Only the position distinguishes
    the key this system generated from the prose that happens to spell it.
    """

    return _rule_retrieval(projection, rule)[1]


def _rule_retrieval(
    projection: dict, rule: dict
) -> tuple[str, tuple[tuple[int, int], ...]]:
    metadata = _projection_metadata(projection)
    heading = " > ".join(_strings(metadata.get("heading_path", [])))
    body, opaque = rule_text_parts(
        rule,
        spans=projection.get("spans") or {},
        facts=projection.get("facts") or {},
    )
    # The heading is prepended, so every span the body reported moves by exactly
    # the length of what now sits in front of it.
    pieces: list[str] = []
    if heading.strip():
        pieces.append(heading)
    if not body.strip():
        return " \n".join(pieces), ()
    offset = len(heading) + 2 if pieces else 0  # 2 == len(" \n")
    pieces.append(body)
    return " \n".join(pieces), tuple(
        (start + offset, end + offset) for start, end in opaque
    )


def indexable_rules(
    projection: dict,
    *,
    threshold: int = LARGE_POLICY_RULE_THRESHOLD,
    scope: str = RULE_INDEX_SCOPE,
) -> list[dict]:
    """The rules of this policy that get their own document, in document order.

    Under ``all_published_rules_v1`` that is every rule with an id. A rule with
    no document cannot be found by a rule query at all, so a retrieval whose
    primary unit is the rule needs the corpus to hold all of them — and holding
    them costs nothing to a reader that wants only the large-policy rows, because
    each document carries its provision's `rule_count` and
    :func:`policy_rule_content_filter` selects exactly that subset.

    Under ``large_policy_rules_v1`` the older rule stands, unchanged and still
    the whole rule: empty for a provision at or under the threshold, because
    below it a provision reads as one governing statement and its own document
    already carries every rule; above it the provision is a schedule whose rows
    have nothing to do with one another, and a row that cannot surface on its own
    cannot elevate the provision that holds it.
    """

    rules = _projection_rules(projection)
    # The scope-to-expectation mapping is `rule_documents_expected`, and it is
    # deliberately not restated here. This branch and the quality check's used to
    # be two copies of one rule; they drifted, and a correct corpus was failed 36
    # times before anyone noticed. One of them has to be the definition, and a
    # decision the validator must also make belongs at the boundary they share.
    if not rule_documents_expected(len(rules), scope=scope, threshold=threshold):
        return []
    return [rule for rule in rules if rule.get("rule_id")]


def build_retrieval_text(*, heading_parts: Sequence[str], rules: Sequence[dict]) -> str:
    """Compose compact match text from headings plus rule titles/statements/effects."""

    parts: list[str] = []
    parts.extend(_strings(heading_parts))
    for rule in rules:
        parts.extend(_strings([rule.get("title"), rule.get("statement")]))
        parts.extend(_text_items(rule.get("conditions")))
        parts.extend(_text_items(rule.get("effects")))
    text = " \n".join(dict.fromkeys(part.strip() for part in parts if part and part.strip()))
    return text[:_MAX_RETRIEVAL_TEXT_CHARS].rstrip()


async def rebuild_project_policy_index(
    *,
    policy_set_key: str,
    version_number: int | None,
    projections: Iterable[dict],
    settings: Settings | None = None,
    search_client: AzureSearchClient | None = None,
    openai_client: AzureOpenAIClient | None = None,
    indexed_at: datetime | None = None,
    projection_profile: str = ENGLISH_PROJECTION_PROFILE,
    quality_profile_name: str = PROJECTION_QUALITY_PROFILE,
    progress: BuildProgress = NULL_PROGRESS,
) -> PolicyIndexBuildOutcome:
    """Best-effort full rebuild of one project's published-latest policy index.

    THE ORDER IS THE CORRECTNESS ARGUMENT

    1. **Render, then embed, then write.** Both model steps happen before
       anything touches the index, so a rendering that fails costs a publish some
       time and leaves the previous index exactly as it was. Nothing is uploaded
       from a corpus that could not be rendered whole.
    2. **The manifest goes to `incomplete` first.** From this point until step 5
       the project is not matchable, which is precisely true: it is being
       rewritten. A rebuild interrupted anywhere in between leaves that state
       behind, so the failure case needs no cleanup to be correct.
    3. **Documents are uploaded and every acknowledgement is counted.** Azure AI
       Search answers a partially-rejected batch with a 207 and per-document
       statuses, which is not an error the transport can raise; a rebuild that
       trusted the call rather than the acknowledgements would mark a corpus
       ready that is missing rows.
    4. **Stale documents are removed.** Everything under this project that is
       not in the live set: superseded versions, and the rule documents of a
       provision that has shrunk to or below the threshold. The manifest is
       excluded by id — it is not a content document and deleting it would erase
       the record of what just happened.
    5. **The corpus is validated against the record it was built from,** and
       only then is the manifest moved to `ready` — and only if every expected
       document was acknowledged. A partial upload leaves it `incomplete`, the
       build is reported failed, and no profile is claimed.

    STEP 5 IS TWO CLAIMS, AND ONE OF THEM IS NEW

    Counting acknowledgements proves the corpus is **complete**. It proves
    nothing about whether what landed is a rendering of what it names — a
    rendering call that returned, an embedding call that returned and an upload
    that was acknowledged are all facts about transport. So before the manifest
    is allowed to say `ready`, `quality/projection_faithfulness` checks the set
    against the authoritative text every document was rendered from, and the
    verdict is written onto the same manifest.

    A corpus that fails leaves the manifest `incomplete` and the build reported
    failed. **Nothing is deleted.** The documents stay exactly where they are —
    they are simply unreachable, because the gate reads the manifest — so the
    evidence for a failed validation is still there to look at, and the repair
    is another rebuild rather than a restore.

    Rollback is this function run again from the authoritative database. Nothing
    here re-extracts, and nothing here is the only copy of anything.

    WHAT `progress` IS, AND WHY IT IS A PARAMETER RATHER THAN A GLOBAL

    Every stage above is knowledge that existed only in local variables and died
    with the call, because the HTTP response is the single output channel and it
    does not exist until the last stage has finished. On a real corpus the
    rendering pass alone runs for minutes, so a caller could show a spinner and
    nothing else — unable to tell a slow render from a hung one, or to say
    whether the wait was in the model or in the index.

    `progress` is where those stages are published. It defaults to a no-op, so
    every existing caller and every test that calls this function directly keeps
    working unchanged and needs no database; a caller that wants the stages
    passes a recorder. It is injected rather than reached for globally so this
    function stays a pure function of its arguments, and so a test can watch the
    exact sequence it emits by handing it a list.

    Nothing reported here is read back. There is no branch in this function on
    anything `progress` does, and none of its methods can raise — a build must not
    be able to fail because its progress could not be recorded.
    """

    settings = settings or get_settings()
    index_name = policy_index_name(policy_set_key)
    now = _timestamp(indexed_at)
    if not settings.search_enabled:
        return PolicyIndexBuildOutcome(
            state="skipped",
            policy_set_key=policy_set_key,
            index_name=index_name,
            version_number=version_number,
            document_count=0,
            indexed_at=now,
        )

    projection_list: list[dict] = []
    documents: list[dict] = []
    quality: ProjectionQualityReport | None = None
    manifest_written = False
    try:
        if not (openai_client or settings.ai_enabled):
            raise RuntimeError("Azure OpenAI embeddings are not configured")
        search_client = search_client or AzureSearchClient(settings)
        openai_client = openai_client or AzureOpenAIClient(settings)
        await progress.stage("collecting")
        projection_list = list(projections)
        await progress.count(projection_count=len(projection_list))

        documents, records = await _build_project_documents(
            policy_set_key=policy_set_key,
            projections=projection_list,
            openai_client=openai_client,
            settings=settings,
            projection_profile=projection_profile,
            progress=progress,
        )
        policy_documents = [d for d in documents if d["content_type"] == CONTENT_TYPE_POLICY]
        rule_documents = [d for d in documents if d["content_type"] == CONTENT_TYPE_RULE]
        policy_version_id = (
            str(policy_documents[0]["policy_version_id"]) if policy_documents else None
        )
        # The one honest denominator this build ever has, and it does not exist
        # until here: how many documents will be written is unknown until the
        # corpus has been rendered. Published as a count beside the
        # acknowledgements below, never as a percentage spanning the stages that
        # ran before it existed.
        await progress.count(
            expected_document_count=len(documents),
            policy_unit_count=len(policy_documents),
            rule_unit_count=len(rule_documents),
        )

        await progress.stage("indexing")
        await _create_index_accepting_empty_success(
            search_client,
            policy_index_definition(
                index_name,
                vector_dimensions=settings.azure_openai_embedding_dimensions,
            ),
        )

        def manifest(
            state: str, uploaded: int, quality: ProjectionQualityReport | None = None
        ) -> dict:
            return build_index_manifest_document(
                policy_set_key=policy_set_key,
                policy_version_id=policy_version_id,
                version_number=version_number,
                projection_profile=projection_profile,
                expected_policy_documents=len(policy_documents),
                expected_rule_documents=len(rule_documents),
                uploaded_documents=uploaded,
                state=state,
                indexed_at=now,
                quality=quality,
            )

        # THE POINT OF NO RETURN, AND THE ABORT IN FRONT OF IT.
        #
        # Moving the manifest out of `ready` is what makes this project
        # unmatchable, and it must succeed before anything else is touched. If it
        # does not, the index still carries the previous manifest saying `ready`
        # — and if this rebuild then went on to upload documents and sweep the
        # ones it did not recognise, it would leave a corpus that is half-written
        # and a manifest that says it may be read. That is the one state worse
        # than any failure here, because nothing downstream would refuse it.
        #
        # So the rebuild stops, before a single content document is written and
        # before the stale sweep runs. What is in the index is exactly what was
        # in it a moment ago: the previous corpus, and the previous manifest,
        # byte for byte. The repair is to run this again.
        if await _upload_documents_counting_acknowledgements(
            search_client, index_name, [manifest(MANIFEST_INCOMPLETE, 0)]
        ) != 1:
            raise RuntimeError(
                "the index manifest could not be moved out of the ready state, so this "
                "rebuild stopped before writing anything; the corpus that was there is "
                "the one that is there"
            )
        manifest_written = True

        await progress.stage("uploading")
        await progress.count(submitted_count=len(documents))
        acknowledged = await _upload_documents_counting_acknowledgements(
            search_client, index_name, documents
        )
        await progress.count(acknowledged_count=acknowledged)
        if acknowledged != len(documents):
            # Checked **before** the stale sweep, for the same reason the abort
            # above sits before the first write. Every acknowledgement is a
            # document that is genuinely there, and some are not — so deleting
            # the documents this build did not recognise would remove the
            # previous version's while the replacement is short. Leaving them
            # costs nothing: the manifest is `incomplete`, so none of them can be
            # reached, and the next successful rebuild sweeps them.
            #
            # Reported as a failure rather than as a smaller success: a caller
            # told "built, 61 documents" against an expected 74 has no way to
            # know the corpus is short.
            raise RuntimeError(
                f"{acknowledged} of {len(documents)} documents were accepted by Azure AI Search"
            )

        indexed_ids = await search_client.find_ids_by_filter(
            index_name,
            filter_expr=policy_index_filter(policy_set_key),
        )
        live_ids = {doc["id"] for doc in documents} | {policy_index_manifest_id(policy_set_key)}
        stale_ids = sorted(doc_id for doc_id in indexed_ids if doc_id not in live_ids)
        await progress.stage("sweeping")
        await progress.count(swept_count=len(stale_ids))
        if stale_ids:
            await search_client.delete_documents(index_name, stale_ids)

        # THE FIDELITY CHECK, BETWEEN COMPLETENESS AND READINESS.
        #
        # Here rather than earlier because the question is about what the index
        # *holds*, and here rather than later because a manifest that said
        # `ready` first — even for the moment it takes to run this — would be a
        # window in which an unvalidated corpus answers questions.
        #
        # It runs against the documents in hand rather than reading them back.
        # They are the documents the service acknowledged by key, one per
        # expected document, so re-reading them would cost a full corpus scan to
        # learn what was just proved. The alignment came out of the build with
        # them, which is the one place it is known for certain.
        await progress.stage("validating")
        quality = await validate_projection(
            records=records,
            documents=documents,
            expected_profile=projection_profile,
            openai_client=openai_client,
            profile=resolve_quality_profile(quality_profile_name),
            # The scope this build is writing onto its own manifest. Passed
            # rather than defaulted: the check judges rule-document coverage
            # against it, and a build validated under a contract other than the
            # one it was built to is not validated.
            rule_index_scope=RULE_INDEX_SCOPE,
            validated_at=indexed_at,
        )
        if not quality.passed:
            # `incomplete`, and nothing deleted. The corpus is all there and it
            # is not trustworthy, so the manifest is left saying the one thing
            # that keeps every query off it. Writing `ready` beside a failed
            # quality state would also refuse — the gate reads both — but it
            # would leave a manifest asserting a build finished when this one
            # did not, and the two facts are cheaper to keep true than to
            # explain.
            await _upload_documents_counting_acknowledgements(
                search_client,
                index_name,
                [manifest(MANIFEST_INCOMPLETE, acknowledged, quality)],
            )
            raise RuntimeError(
                "the rendered corpus did not pass projection validation under "
                f"`{quality.profile}` ({quality.state}; "
                f"{quality.structural_findings} structural finding(s), "
                f"{quality.below_floor} pair(s) below the floor, "
                f"{quality.checked_documents} document(s) scored)"
            )

        # The last write, and the only one that changes what a query may do. It
        # is counted too: a rebuild that reported `built` on the strength of a
        # ready-manifest the service rejected would leave a self-contradicting
        # pair — a record saying "current" beside a live index that refuses
        # every query, which no repeat rebuild could resolve because each one
        # would report success again.
        await progress.stage("publishing")
        if await _upload_documents_counting_acknowledgements(
            search_client, index_name, [manifest(MANIFEST_READY, acknowledged, quality)]
        ) != 1:
            raise RuntimeError(
                "the index manifest could not be marked ready, so this project's "
                "corpus stays unmatchable"
            )
        return PolicyIndexBuildOutcome(
            state="built",
            policy_set_key=policy_set_key,
            index_name=index_name,
            version_number=version_number,
            document_count=len(documents),
            indexed_at=now,
            policy_document_count=len(policy_documents),
            rule_document_count=len(rule_documents),
            projection_profile=projection_profile,
            manifest_state=MANIFEST_READY,
            quality=quality,
        )
    except Exception as exc:  # noqa: BLE001 - publish must not fail because Search did
        # `describe_exception`, never `str`. A transport failure here carries its
        # meaning in its type and nothing in its message, and recording the empty
        # message left this row saying `error=''` — which reads as "no reason was
        # recorded", i.e. as a process that died mid-build. That is a different
        # diagnosis pointing at a different repair, and it cost an investigation.
        reason = describe_exception(exc)
        logger.warning(
            "best-effort policy index rebuild failed for set %s: %s", policy_set_key, reason
        )
        return PolicyIndexBuildOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=index_name,
            version_number=version_number,
            document_count=0,
            indexed_at=now,
            error=reason,
            # No profile is claimed on a failed build, whatever was rendered.
            # The manifest is `incomplete` if it was reached at all and absent if
            # it was not, and both mean the same thing to the retrieval gate.
            projection_profile=None,
            manifest_state=MANIFEST_INCOMPLETE if manifest_written else None,
            # The verdict is reported even when it is the reason the build
            # failed — especially then. A caller told only "failed" would have to
            # rerun the whole rebuild to find out whether the corpus was short or
            # unfaithful.
            quality=quality,
        )


def _warn_about_interleaved_text(
    projection: dict, group: Sequence[tuple[str, str]]
) -> None:
    """Log which of a policy's retrieval texts were extracted out of reading order.

    The same check the portal runs when a document is loaded, run again over
    what a rebuild is about to index, so the two paths report the same class of
    finding about the same corpus rather than one of them noticing and the other
    not.

    INFORMATIONAL ONLY
    ------------------
    This raises nothing, skips nothing and rewrites nothing. Every text in
    ``group`` is rendered and indexed exactly as it would be if this function
    did not exist; the sole effect is a line in the build log. Interleaving
    comes from the source file, and the only thing that resolves it is a
    corrected PDF or DOCX uploaded as a new version — so a build that refused
    the text would withhold the corpus without bringing the fix any closer.

    Counts and keys only. The passage is policy wording and does not belong in
    a log.
    """

    affected = {key: len(found) for key, text in group if (found := interleaved_tokens(text))}
    if not affected:
        return
    # The identity lives in the projection envelope, not at the top level.
    # Reading `policy_key` from the projection itself logged "policy unknown"
    # for every finding on a live build — a real defect reported without saying
    # where it was, which is most of what makes a finding actionable.
    metadata = _projection_metadata(projection)
    logger.warning(
        "%s: policy %s has %s word(s) across %s retrieval text(s) (%s) whose letters "
        "alternate between two writing systems — the sign of side-by-side columns read "
        "across instead of down. Text left unchanged; build continues. Correct the "
        "original document and upload a new version to resolve it.",
        INTERLEAVED_TEXT_CODE,
        metadata.get("provision_key")
        or metadata.get("policy_key")
        or metadata.get("policy_id")
        or "unknown",
        sum(affected.values()),
        len(affected),
        ", ".join(sorted(affected)),
    )


async def _build_project_documents(
    *,
    policy_set_key: str,
    projections: list[dict],
    openai_client: AzureOpenAIClient,
    settings: Settings,
    projection_profile: str,
    progress: BuildProgress = NULL_PROGRESS,
) -> tuple[list[dict], list[ProjectedRecord]]:
    """Every document this project's index should hold, rendered and embedded.

    One rendering group per policy — its own retrieval text and the text of each
    rule that gets a document — because terminology has to be consistent within
    the unit the request-side relevance weighting is computed over, and two calls
    can legitimately choose two words for one term.

    A rendering failure for any policy fails the whole build. Stamping a corpus
    that is English in part would be the one thing the profile must never mean.

    IT ALSO RETURNS THE ALIGNMENT, AND THAT IS NOT A CONVENIENCE

    Beside the documents comes one :class:`ProjectedRecord` per document, naming
    the authoritative text each was rendered from. This is the only point in the
    process where that association is known for certain: an index document
    carries a rendering and no pointer back to its source, so a validation that
    ran later would have to *re-derive* which record produced which document —
    and re-deriving it from what the index holds would be asking the thing under
    test to describe itself. Carried here, the pairing is a fact of the build.

    The source text is carried **already cut** to the same ceiling the indexed
    text is cut to, so the two sides of every comparison are the two things that
    were actually meant to correspond.
    """

    documents: list[dict] = []
    records: list[ProjectedRecord] = []
    embed_inputs: list[str] = []
    pending: list[tuple[str, dict, dict | None, int, str, str]] = []

    # Rendering is one model call per policy, so the count that moves here is
    # policies rendered — not documents, which do not exist yet. It is reported
    # after each group rather than at the end because this is the longest stage
    # of the build, and a stage that publishes only when it finishes is
    # indistinguishable from one that has stopped.
    await progress.stage("rendering")
    await progress.count(rendered_count=0)
    for projection in projections:
        rules = indexable_rules(projection)
        policy_source, policy_spans = _retrieval_text_and_opaque_spans(projection)
        policy_source = policy_source[:_MAX_RETRIEVAL_TEXT_CHARS]
        group: list[tuple[str, str]] = [("policy", policy_source)]
        rule_sources: list[str] = []
        # Per item, never shared. The policy text and each rule text are
        # different documents: a key generated for one of them says nothing
        # about where the same letters appear in another, and one set spread
        # across the group is how a rule's slug ends up protecting a word in
        # the policy's prose.
        opaque_spans: dict[str, tuple[tuple[int, int], ...]] = {
            "policy": tuple(
                (start, end) for start, end in policy_spans if end <= len(policy_source)
            )
        }
        for ordinal, rule in enumerate(rules):
            rule_source = rule_retrieval_source_text(projection, rule)[:_MAX_RULE_TEXT_CHARS]
            rule_sources.append(rule_source)
            key = f"rule-{ordinal}"
            group.append((key, rule_source))
            # A span only survives if the cut above left the whole of it: half a
            # protected identifier is not one.
            opaque_spans[key] = tuple(
                (start, end)
                for start, end in rule_retrieval_opaque_spans(projection, rule)
                if end <= len(rule_source)
            )

        # The same detector the portal runs at upload, asked here of the text a
        # rebuild actually indexes. It reports and changes nothing: the group
        # below is the one that would have been rendered either way, so a build
        # with warnings and a build without do identical work. Text already in
        # the index is not revisited — a warning is about a source file, and the
        # only thing that resolves it is a corrected upload.
        _warn_about_interleaved_text(projection, group)

        rendered = await project_texts_to_english(
            group,
            settings=settings,
            openai_client=openai_client,
            opaque_spans=opaque_spans,
        )
        missing = [key for key, text in group if text.strip() and key not in rendered]
        if missing:
            raise EnglishProjectionError(
                f"{len(missing)} retrieval text(s) came back unrendered for one policy"
            )

        policy_text = rendered.get("policy", "")
        pending.append(("policy", projection, None, 0, policy_text, policy_source))
        embed_inputs.append(policy_text)
        for ordinal, rule in enumerate(rules):
            rendered_rule = rendered.get(f"rule-{ordinal}", "")
            pending.append(
                ("rule", projection, rule, ordinal, rendered_rule, rule_sources[ordinal])
            )
            embed_inputs.append(rendered_rule)
        await progress.count(rendered_count=len(pending))

    await progress.stage("embedding")
    vectors = await openai_client.embed(embed_inputs) if embed_inputs else []
    if len(vectors) != len(embed_inputs):
        raise RuntimeError(
            f"the embedding call returned {len(vectors)} vectors for {len(embed_inputs)} texts"
        )
    await progress.count(embedded_count=len(vectors))

    for (kind, projection, rule, ordinal, text, source), vector in zip(pending, vectors):
        if kind == "policy":
            document = build_policy_document(
                policy_set_key=policy_set_key,
                projection=projection,
                vector=vector,
                retrieval_text=text,
                projection_profile=projection_profile,
            )
            parent = None
        else:
            document = build_rule_document(
                policy_set_key=policy_set_key,
                projection=projection,
                rule=rule or {},
                rule_ordinal=ordinal,
                vector=vector,
                retrieval_text=text,
                projection_profile=projection_profile,
            )
            parent = str(document["parent_document_id"])
        documents.append(document)
        records.append(
            ProjectedRecord(
                document_id=str(document["id"]),
                policy_version_id=str(document["policy_version_id"]),
                source_text=source,
                parent_document_id=parent,
                provision_rule_count=len(_projection_rules(projection)),
                # Only a provision's own record carries this. It is how many rule
                # documents *this build made eligible*, which is not the rule
                # count: a rule with no id gets no document. Stating it here, from
                # the same call the build selects with, is what lets the quality
                # check compare an exact number instead of asking the far weaker
                # question of whether there are any rule documents at all.
                expected_rule_documents=(
                    len(indexable_rules(projection)) if parent is None else None
                ),
            )
        )
    return documents, records


def _document_was_accepted(item: object) -> bool:
    """Whether one entry of an index response says its document actually landed.

    Azure AI Search answers a batch with one entry per document, and a batch in
    which some failed comes back `207 Multi-Status` — which is not an error the
    transport raises. Each entry carries a boolean `status` and an HTTP
    `statusCode`; a throttled document is `429`, a document the service could not
    take right now is `503`, and both arrive inside an otherwise successful call.

    Both fields are read, and either one can refuse. `status: false` is the
    explicit refusal. A non-2xx `statusCode` is checked as well rather than
    trusted to agree with it, because the cost of the two disagreeing is a corpus
    reported complete while it is short — and the cost of reading both is
    nothing.

    An entry that is not a mapping is not an acknowledgement of anything. This
    answers only "does this entry say yes"; **which** document it says yes about
    is the caller's question, and it is asked separately below.
    """

    if not isinstance(item, dict):
        return False
    if item.get("status") is False:
        return False
    code = item.get("statusCode")
    if isinstance(code, int) and not 200 <= code < 300:
        return False
    return True


def _acknowledged_keys(response: object, submitted: set[str]) -> set[str]:
    """Which of the documents we sent this response actually acknowledges.

    Not a count — a set of keys, matched against what was sent. The difference
    matters, because everything this module guarantees about a rebuild rests on
    "every expected document landed", and a count can be reached by the wrong
    documents:

      * **Silence is not acknowledgement.** A reply with no `value`, a `value`
        that is not a list, or an empty one, acknowledges *nothing*. Treating an
        unreadable reply as a batch-sized success would be the exact inversion of
        the invariant this function exists to hold — it would let a service that
        said nothing at all stamp a corpus ready.
      * **A key we did not send is not ours.** An entry naming a document from
        another request, or a key that is absent or is not a string, says nothing
        about the batch in hand.
      * **The same key twice is one document.** A reply that repeated one
        acknowledgement would otherwise cover for another that never came.

    So the answer is the set of submitted keys that were named, once each, by an
    entry that said yes. A caller comparing `len(...)` against what it sent is
    then comparing two counts of the same things.
    """

    if not isinstance(response, dict):
        return set()
    results = response.get("value")
    if not isinstance(results, list):
        return set()

    acknowledged: set[str] = set()
    for item in results:
        if not _document_was_accepted(item):
            continue
        key = item.get("key")
        if not isinstance(key, str) or key not in submitted:
            continue
        acknowledged.add(key)
    return acknowledged


async def _upload_documents_counting_acknowledgements(
    search_client: AzureSearchClient, index_name: str, documents: list[dict]
) -> int:
    """Upload in batches and return how many documents the service actually took.

    What is counted is what came back acknowledged **by key**, never what was
    sent and never how many entries a reply happened to contain. A reply this
    function cannot read acknowledges nothing, which is what makes the
    completeness checks in the rebuild above mean what they say.

    Used for the manifest as well as for content, and deliberately: the manifest
    is the document the whole readiness design hangs on, so it is the last
    document that should be written on the strength of a 2xx alone.
    """

    acknowledged = 0
    for start in range(0, len(documents), _UPLOAD_BATCH_SIZE):
        batch = documents[start : start + _UPLOAD_BATCH_SIZE]
        submitted = {str(doc["id"]) for doc in batch}
        response = await search_client.upload_documents(index_name, batch)
        acknowledged += len(_acknowledged_keys(response, submitted))
    return acknowledged


async def read_projection_readiness(
    search_client: AzureSearchClient,
    index_name: str,
    *,
    policy_set_key: str,
    expected_profile: str = ENGLISH_PROJECTION_PROFILE,
    expected_quality_profile: str = PROJECTION_QUALITY_PROFILE,
) -> EnglishProjectionReadiness:
    """Whether this project may be matched against, asked of the live index.

    One filtered probe for the project's manifest under the expected profile in
    the `ready` state, **validated under the expected quality profile**.
    Everything else is not ready, and the ways it can be not ready are one answer
    here on purpose: no manifest (never projected), a manifest under a superseded
    profile (projected under a contract the query side no longer uses), a
    manifest left `incomplete` (a rebuild that did not finish), and a manifest
    whose corpus was never validated or failed validation are all "the corpus in
    this index cannot be matched against by a query rendered under
    `expected_profile`". A reader who could act differently on them would still
    perform the same repair — rebuild, or validate.

    TWO PROBES ON THE REFUSAL PATH, ONE ON THE READY PATH

    The gate is a single expression, and it is asked first. Only when it says no
    is a second, weaker probe made — the same manifest without the quality
    clauses — and it exists purely so the refusal can *say which* of the two
    kinds of "not ready" this is. That is a report, never a decision: the
    returned `ready` is false either way, and no caller may read
    `indexed_profile` as permission. A corpus built but unvalidated is exactly as
    unusable as one never built, and the distinction is for the person doing the
    repair.

    Deliberately a live probe rather than a read of `policy_index_states`. That
    row records what the app last *tried*; this asks what the index *holds*, and
    an index edited or dropped out of band makes those two different facts.
    """

    # A quality profile arrives here as a parameter, so it can name a statement
    # of validation this build does not carry. That is a configuration fault and
    # not a corpus state, and the two must not produce the same answer: the
    # filter below would simply match nothing, and the project would report
    # `ready=False` for as long as the name stayed wrong — sending an operator to
    # rebuild and re-validate a corpus that was never the problem. Refused here,
    # in the same terms `quality_profile` refuses an unknown name, so the
    # unanswerable question is never asked of the index.
    if not known_quality_profile(expected_quality_profile):
        raise ValueError(
            f"no such projection quality profile: {expected_quality_profile!r}"
        )

    ready = await search_client.find_ids_by_filter(
        index_name,
        filter_expr=policy_index_ready_filter(
            policy_set_key,
            projection_profile=expected_profile,
            quality_profile=expected_quality_profile,
        ),
        page_size=1,
    )
    if ready:
        return EnglishProjectionReadiness(
            profile=expected_profile,
            ready=True,
            indexed_profile=expected_profile,
            quality_profile=expected_quality_profile,
            quality_state=QUALITY_PASSED,
        )

    # The weaker probe, only now. It asks whether the corpus is built and
    # complete under this rendering contract, ignoring quality — so a `True`
    # here means the refusal above was a *validation* refusal and not a missing
    # rebuild. It changes nothing about the answer.
    built = await search_client.find_ids_by_filter(
        index_name,
        filter_expr=(
            policy_index_filter(
                policy_set_key,
                content_type=CONTENT_TYPE_MANIFEST,
                projection_profile=expected_profile,
            )
            + f" and manifest_state eq {_odata_string(MANIFEST_READY)}"
        ),
        page_size=1,
    )
    return EnglishProjectionReadiness(
        profile=expected_profile,
        ready=False,
        state=INDEX_PROJECTION_UNAVAILABLE,
        indexed_profile=expected_profile if built else None,
        quality_profile=expected_quality_profile,
        quality_state=None,
    )


async def read_rule_index_scope(
    search_client: AzureSearchClient,
    index_name: str,
    *,
    policy_set_key: str,
    projection_profile: str = ENGLISH_PROJECTION_PROFILE,
) -> str | None:
    """Which rules this project's live index actually holds documents for.

    Returns the scope stamped on the project's manifest, or ``None`` when the
    manifest carries none — which is every corpus built before the scope existed,
    and is a refusal rather than a default. A rule-first query run over a corpus
    holding rule documents only for large provisions would return silence about
    every small provision's rules, and silence is indistinguishable from "nothing
    there bears on this question". So the caller is told the corpus cannot answer
    the question it was about to ask, and the repair is one rebuild.

    Asked only on the path that needs it. The default retrieval mode reads
    nothing here and makes no extra round trip.
    """

    found = await search_client.find_documents_by_filter(
        index_name,
        filter_expr=policy_index_filter(
            policy_set_key,
            content_type=CONTENT_TYPE_MANIFEST,
            projection_profile=projection_profile,
        ),
        select=_RULE_SCOPE_SELECT,
        page_size=1,
    )
    for document in found:
        scope = document.get("rule_index_scope")
        return str(scope) if scope else None
    return None


@dataclass(frozen=True)
class PolicyIndexValidationOutcome:
    """What a validation of an already-built projection found, and what it wrote.

    Kept apart from :class:`PolicyIndexBuildOutcome` because the two are
    different acts. A build produces a corpus; a validation produces a *verdict
    about a corpus that already exists* and changes not one content document.
    Reporting one as the other would let "we checked it" and "we rebuilt it"
    read the same in a log, and they cost very different things.

    `recorded` says whether the verdict reached the manifest — the document the
    gate actually reads. A verdict that could not be written is not in force,
    however conclusive it was, and a caller that treated an unwritten `passed` as
    readiness would be claiming a state the index does not carry.
    """

    state: Literal["validated", "skipped", "failed"]
    policy_set_key: str
    index_name: str
    projection_profile: str
    recorded: bool
    validated_at: str
    quality: ProjectionQualityReport | None = None
    error: str | None = None


async def validate_project_policy_index(
    *,
    policy_set_key: str,
    projections: Iterable[dict],
    version_number: int | None = None,
    settings: Settings | None = None,
    search_client: AzureSearchClient | None = None,
    openai_client: AzureOpenAIClient | None = None,
    projection_profile: str = ENGLISH_PROJECTION_PROFILE,
    quality_profile_name: str = PROJECTION_QUALITY_PROFILE,
    validated_at: datetime | None = None,
) -> PolicyIndexValidationOutcome:
    """Check a projection that is already built, without rebuilding any of it.

    WHY THIS EXISTS SEPARATELY FROM A REBUILD

    Every corpus built before this gate existed is in the index right now,
    complete, `ready`, and unvalidated. A rebuild would validate it — and would
    also re-render every policy through a model and re-upload every document, at
    the cost and the risk of the whole pipeline, to answer a question about text
    that is already sitting there. This asks the question directly: it reads what
    the index holds, re-derives the authoritative text from PostgreSQL, and
    compares them. **No rendering call is made and no content document is
    written.**

    WHAT IT WRITES, AND IN WHICH ORDER

    One document: the manifest, carrying the verdict. It is written **before**
    anything is recorded anywhere else, because the manifest is what the gate
    reads — so the ordering makes one direction of disagreement impossible. A
    caller that records the outcome afterwards can be behind the manifest (the
    record says unvalidated while the index is validated, which under-claims and
    is refused-by-report only), and can never be ahead of it (the record claiming
    a profile the manifest lacks, which would be a readiness nobody could
    honour).

    ON FAILURE, NOTHING IS DELETED

    The manifest records `failed`, the gate stops matching against the corpus,
    and every document stays exactly where it is. Deleting them would destroy the
    evidence for the verdict and turn a reversible finding into an outage, and a
    failed validation is not proof that the *documents* are wrong — only that
    this build cannot vouch for them.

    `manifest_state` is deliberately **not** touched. Whether every expected
    document landed is a fact about a build that already happened, and a
    validation has no standing to revise it; the two claims sit side by side on
    the manifest and the gate requires both.
    """

    settings = settings or get_settings()
    index_name = policy_index_name(policy_set_key)
    now = _timestamp(validated_at)
    if not settings.search_enabled:
        return PolicyIndexValidationOutcome(
            state="skipped",
            policy_set_key=policy_set_key,
            index_name=index_name,
            projection_profile=projection_profile,
            recorded=False,
            validated_at=now,
            quality=unvalidated_report(
                profile=quality_profile_name,
                validated_at=validated_at,
                code=FINDING_EMBEDDING_UNAVAILABLE,
            ),
        )

    quality: ProjectionQualityReport | None = None
    try:
        profile = resolve_quality_profile(quality_profile_name)
        if not (openai_client or settings.ai_enabled):
            raise RuntimeError("Azure OpenAI embeddings are not configured")
        search_client = search_client or AzureSearchClient(settings)
        openai_client = openai_client or AzureOpenAIClient(settings)

        # Validation annotates a manifest built before the quality fields
        # existed. Azure Search rejects those fields until the live index schema
        # is updated, so evolve the schema before reading and writing the
        # manifest. PUT is additive for this definition and preserves documents;
        # it is the same operation a rebuild already performs, without any
        # rendering or content-document upload.
        await _create_index_accepting_empty_success(
            search_client,
            policy_index_definition(
                index_name,
                vector_dimensions=settings.azure_openai_embedding_dimensions,
            ),
        )

        records = expected_projection_records(list(projections), policy_set_key=policy_set_key)
        manifest_id = policy_index_manifest_id(policy_set_key)
        documents = await search_client.find_documents_by_filter(
            index_name,
            filter_expr=policy_index_filter(policy_set_key),
            select=_VALIDATION_SELECT,
        )
        # Read unfiltered by profile on purpose. Narrowing to the expected
        # contract would hide the very thing the coverage check is for: a
        # document under a superseded profile is not absent, it is *present and
        # excluded from every query*, and a validation that could not see it
        # would report a corpus complete that silently answers from part of
        # itself.
        live = [
            document
            for document in documents
            if str(document.get("id") or "") != manifest_id
        ]

        # The scope the corpus was *actually built under*, read off its own
        # manifest rather than assumed from what this code would write today. A
        # manifest written before the field existed carries none, and that means
        # legacy semantics — it was built when legacy was the only contract, so
        # judging it by today's would condemn a corpus that is correct for its
        # age. An unrecognised value is neither, and the check refuses it.
        recorded_scope = await read_rule_index_scope(
            search_client, index_name, policy_set_key=policy_set_key
        )

        quality = await validate_projection(
            records=records,
            documents=live,
            expected_profile=projection_profile,
            openai_client=openai_client,
            ignore_document_ids={manifest_id},
            profile=profile,
            rule_index_scope=recorded_scope or RULE_INDEX_SCOPE_LARGE_POLICY,
            validated_at=validated_at,
        )

        existing = await _read_manifest(search_client, index_name, manifest_id=manifest_id)
        if existing is None:
            # There is no manifest to annotate, so this project was never built
            # under any contract and there is nothing here to validate. Writing
            # one would be this function inventing a build record.
            return PolicyIndexValidationOutcome(
                state="failed",
                policy_set_key=policy_set_key,
                index_name=index_name,
                projection_profile=projection_profile,
                recorded=False,
                validated_at=now,
                quality=quality,
                error=(
                    "this project's index carries no manifest, so there is no built "
                    "projection to validate; rebuild it first"
                ),
            )

        annotated = dict(existing)
        annotated.update(
            {
                "quality_state": quality.state,
                "quality_profile": quality.profile,
                "quality_checked_documents": quality.checked_documents,
                "quality_structural_findings": quality.structural_findings,
                "quality_min_similarity": quality.minimum_similarity,
                "quality_mean_similarity": quality.mean_similarity,
                "quality_validated_at": quality.validated_at,
            }
        )
        recorded = await _upload_documents_counting_acknowledgements(
            search_client, index_name, [annotated]
        ) == 1
        if not recorded:
            return PolicyIndexValidationOutcome(
                state="failed",
                policy_set_key=policy_set_key,
                index_name=index_name,
                projection_profile=projection_profile,
                recorded=False,
                validated_at=now,
                quality=quality,
                error=(
                    "the validation verdict could not be written to the index manifest, "
                    "so it is not in force and this project's readiness is unchanged"
                ),
            )
        return PolicyIndexValidationOutcome(
            state="validated" if quality.passed else "failed",
            policy_set_key=policy_set_key,
            index_name=index_name,
            projection_profile=projection_profile,
            recorded=True,
            validated_at=now,
            quality=quality,
        )
    except Exception as exc:  # noqa: BLE001 - a validation reports, it does not raise upward
        logger.warning(
            "projection validation failed for set %s: %s", policy_set_key, exc
        )
        return PolicyIndexValidationOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=index_name,
            projection_profile=projection_profile,
            recorded=False,
            validated_at=now,
            quality=quality,
            error=str(exc),
        )


def expected_projection_records(
    projections: Sequence[dict], *, policy_set_key: str
) -> list[ProjectedRecord]:
    """The documents a build of these projections should have produced, and their sources.

    The same derivation the builder performs, minus the rendering and the
    embedding: the same ids, the same parents, the same rule-document decision
    and — critically — the **same character ceilings**, so what a validation
    compares against is the text that was actually handed to the renderer rather
    than a longer record the index never saw.

    It exists so a validation can be run against a corpus nobody has the build
    in memory for. It is deliberately derived from the authoritative database
    rather than from the index: asking the index which record each document came
    from would be asking the thing under test to supply the answer key.

    ``policy_set_key`` is unused in the derivation and taken anyway, because a
    caller that did not have to pass it could validate one project's index
    against another project's records and get a clean, meaningless pass.
    """

    records: list[ProjectedRecord] = []
    for projection in projections:
        metadata = _projection_metadata(projection)
        policy_version_id = str(metadata["policy_version_id"])
        provision_key = str(metadata["provision_key"])
        rules = _projection_rules(projection)
        parent_id = policy_document_id(
            policy_version_id=policy_version_id, provision_key=provision_key
        )
        records.append(
            ProjectedRecord(
                document_id=parent_id,
                policy_version_id=policy_version_id,
                source_text=_retrieval_text_for_projection(projection)[
                    :_MAX_RETRIEVAL_TEXT_CHARS
                ],
                parent_document_id=None,
                provision_rule_count=len(rules),
                # What this build would actually make eligible, so a validation
                # compares against the number of documents there should be
                # rather than against the number of rules there are.
                expected_rule_documents=len(indexable_rules(projection)),
            )
        )
        for rule in indexable_rules(projection):
            records.append(
                ProjectedRecord(
                    document_id=policy_rule_document_id(
                        policy_version_id=policy_version_id,
                        provision_key=provision_key,
                        rule_id=str(rule.get("rule_id") or ""),
                    ),
                    policy_version_id=policy_version_id,
                    source_text=rule_retrieval_source_text(projection, rule)[
                        :_MAX_RULE_TEXT_CHARS
                    ],
                    parent_document_id=parent_id,
                    provision_rule_count=len(rules),
                )
            )
    return records


async def _read_manifest(
    search_client: AzureSearchClient, index_name: str, *, manifest_id: str
) -> dict | None:
    """The project's manifest as the index holds it, or None if it has none.

    Read back whole rather than rebuilt, because a validation must not restate
    what a build claimed. Rewriting the manifest from scratch here would let this
    function invent an `expected_policy_documents` or a `version_number` from
    whatever it happened to be handed, and a validation has no standing to say
    anything about a build it did not perform. It annotates; it does not author.
    """

    found = await search_client.find_documents_by_filter(
        index_name,
        filter_expr=f"id eq {_odata_string(manifest_id)}",
        select=_MANIFEST_SELECT,
        page_size=1,
    )
    for document in found:
        if str(document.get("id") or "") == manifest_id:
            # Search decorates a result with `@`-prefixed metadata (a score, a
            # rerank). Those are the service's annotations on a *result*, not
            # fields of the document, and writing them back would be uploading a
            # document with keys the schema does not have.
            return {
                key: value
                for key, value in document.items()
                if not key.startswith("@")
            }
    return None


async def read_policy_index_state(
    session: AsyncSession, *, policy_set_id: object
) -> PolicyIndexState | None:
    """The recorded build state for one project's policy index, or None.

    None means no build was ever attempted, which is a different fact from a
    build that ran and indexed nothing — `policy_index_freshness` keeps those
    apart. Reading lives here beside the write rather than in the router so the
    two stay one boundary: a caller that wants this row does not need to know
    which table holds it.
    """

    result = await session.execute(
        select(PolicyIndexState).where(PolicyIndexState.policy_set_id == policy_set_id)
    )
    return result.scalar_one_or_none()


async def record_policy_index_build_state(
    session: AsyncSession,
    *,
    policy_set_id: object,
    outcome: PolicyIndexBuildOutcome,
) -> PolicyIndexState:
    """Persist the latest rebuild attempt without lying about stale content.

    A failed rebuild updates the attempt status and error, but deliberately keeps
    the previously indexed version/document count. That is the fact the retrieval
    path needs to tell "stale relative to the active version" from "fresh but no
    match".
    """

    result = await session.execute(
        select(PolicyIndexState).where(PolicyIndexState.policy_set_id == policy_set_id)
    )
    state = result.scalar_one_or_none()
    attempted_at = _parse_timestamp(outcome.indexed_at)
    if state is None:
        state = PolicyIndexState(
            policy_set_id=policy_set_id,
            index_name=outcome.index_name,
            document_count=0,
            status=outcome.state,
            attempted_version_number=outcome.version_number,
            attempted_at=attempted_at,
        )
        session.add(state)

    state.index_name = outcome.index_name
    state.status = outcome.state
    state.attempted_version_number = outcome.version_number
    state.attempted_at = attempted_at
    # THE INVARIANT: a row that says `failed` always says why.
    #
    # Enforced here because this is the single point every writer passes through,
    # so it holds for callers that do not exist yet. An empty string in this
    # column is worse than a vague one: it is indistinguishable from no error
    # having been recorded at all, which reads as a process that died before it
    # could speak, and sends the reader looking for a crash that never happened.
    # A build did reach this line, and saying so is the honest floor.
    if outcome.state == "failed" and not (outcome.error or "").strip():
        state.error = (
            "the build failed and raised an exception that carried no message; "
            "see the server log for the traceback"
        )
    else:
        state.error = outcome.error
    if outcome.state == "built":
        state.indexed_version_number = outcome.version_number
        state.document_count = outcome.document_count
        state.built_at = attempted_at
        # Recorded only on a build that finished. A failed or partial rebuild
        # keeps whatever profile the last complete one recorded, exactly as it
        # keeps the last indexed version, so the record can still prove the
        # index is behind rather than reporting "unknown".
        state.projection_profile = outcome.projection_profile
    elif outcome.state == "skipped" and state.indexed_version_number is None:
        state.document_count = 0
        state.built_at = None
    # The verdict is recorded whenever one was reached, on **any** outcome — a
    # failed build that failed *because* the corpus was unfaithful is precisely
    # the case a reader needs this for, and dropping it on failure would leave
    # the row saying "failed" beside a null quality state that reads as "never
    # checked". Left untouched when no verdict was reached, so an older passing
    # validation is not erased by a build that fell over before Search.
    if outcome.quality is not None:
        _record_quality(state, outcome.quality)
    return state


def record_projection_quality(
    state: PolicyIndexState, quality: ProjectionQualityReport
) -> PolicyIndexState:
    """Write a standalone validation's verdict onto the recorded index state.

    Separate from the build recorder because a validation is not a build: it
    must not touch `status`, `indexed_version_number`, `document_count` or
    `built_at`. Those describe what was last constructed, and a validation
    constructs nothing — conflating them would let "we checked the corpus" move
    a freshness reading.
    """

    return _record_quality(state, quality)


def _record_quality(
    state: PolicyIndexState, quality: ProjectionQualityReport
) -> PolicyIndexState:
    state.quality_state = quality.state
    state.quality_profile = quality.profile
    state.quality_checked_documents = quality.checked_documents
    state.quality_structural_findings = quality.structural_findings
    state.quality_min_similarity = quality.minimum_similarity
    state.quality_mean_similarity = quality.mean_similarity
    state.quality_validated_at = _parse_timestamp(quality.validated_at)
    return state


def policy_index_build_outcome_payload(outcome: PolicyIndexBuildOutcome) -> dict:
    return {
        "state": outcome.state,
        "policy_set_key": outcome.policy_set_key,
        "index_name": outcome.index_name,
        "version_number": outcome.version_number,
        "document_count": outcome.document_count,
        "indexed_at": outcome.indexed_at,
        "error": outcome.error,
        # The three facts a reader needs to tell "the index is built" from "the
        # index can be matched against": how the documents split between the two
        # content types, which rendering contract they were built under, and
        # whether the manifest says the set is complete.
        "policy_document_count": outcome.policy_document_count,
        "rule_document_count": outcome.rule_document_count,
        "projection_profile": outcome.projection_profile,
        "manifest_state": outcome.manifest_state,
        # And the fourth, which is the one the other three cannot supply:
        # whether what landed is a rendering of what it names. Null when the
        # build never got far enough to ask.
        "quality": outcome.quality.as_payload() if outcome.quality else None,
    }


def policy_index_validation_payload(outcome: PolicyIndexValidationOutcome) -> dict:
    """A validation outcome as an API payload. Counts, scores and keys only."""

    return {
        "state": outcome.state,
        "policy_set_key": outcome.policy_set_key,
        "index_name": outcome.index_name,
        "projection_profile": outcome.projection_profile,
        "recorded": outcome.recorded,
        "validated_at": outcome.validated_at,
        "error": outcome.error,
        "quality": outcome.quality.as_payload() if outcome.quality else None,
    }


def failed_policy_index_build_outcome(
    *,
    policy_set_key: str,
    version_number: int | None,
    error: str,
    indexed_at: datetime | None = None,
) -> PolicyIndexBuildOutcome:
    return PolicyIndexBuildOutcome(
        state="failed",
        policy_set_key=policy_set_key,
        index_name=policy_index_name(policy_set_key),
        version_number=version_number,
        document_count=0,
        indexed_at=_timestamp(indexed_at),
        error=error,
    )


#: The history status for a build that never ran because the slot was busy.
#: Named rather than repeated as a literal so the mapping call below reads as
#: the translation it is.
_DEFERRED_HISTORY_STATUS = "deferred"


@dataclass(frozen=True)
class TrackedPolicyIndexBuild:
    """What one attempt to build a project's index did, whether or not it ran.

    Three cases, and they are deliberately not collapsed into two:

      * it ran — `accepted` is true, `outcome` says what it produced, and `build`
        is the history row it wrote;
      * it was refused because another build holds the slot — `accepted` is
        false, `conflict` names the build that does, and `outcome` is the failed
        outcome the latest-state row records;
      * it could not even be recorded — everything is None, which happens only
        when the database refuses the history write, and a caller that must not
        fail (publish) carries on regardless.
    """

    accepted: bool
    outcome: PolicyIndexBuildOutcome | None = None
    build: PolicyIndexBuild | None = None
    #: The build holding the slot when this one was refused. Named so a caller
    #: can tell the operator *which* project is being rebuilt rather than only
    #: that something is — "try later" without saying what is running is a
    #: message nobody can act on.
    conflict: PolicyIndexBuild | None = None


async def run_tracked_policy_index_build(
    session: AsyncSession,
    *,
    policy_set_id: object,
    policy_set_key: str,
    version_number: int | None,
    load_projections: Callable[[], Awaitable[Iterable[dict]]],
    trigger: str,
    operation_id: str | None = None,
    actor: str | None = None,
    indexed_at: datetime | None = None,
) -> TrackedPolicyIndexBuild:
    """Run one index build under the global slot, reporting and recording it.

    THE ONE ENTRY POINT, AND WHY BOTH CALLERS USE IT

    Publishing rebuilds a project's index, and a manual rebuild rebuilds a
    project's index. They are the same operation started for two reasons, and
    before this they were two copies of the same six steps in two routers — which
    is how they came to differ: one recorded an actor and the other did not, and
    neither coordinated with the other at all, so a publish could start a full
    corpus render while an administrator's repair of the same project was halfway
    through rewriting its manifest.

    Everything that is true of a build is therefore decided here once: the slot,
    the stage reporting, the history row, the latest-state row, and the guarantee
    that the record ends terminal. A caller supplies only what genuinely differs
    — which project, which version, why, and who.

    THE ORDER MATTERS IN ONE PLACE

    `load_projections` is a callable rather than a list because it reads the
    whole active version out of PostgreSQL, and a build that is about to be
    refused must not pay for that. Nothing is loaded until the slot is held.

    NOTHING HERE RAISES

    Both callers are best-effort about the index — publish has already committed
    its version by the time this runs, and the repair endpoint reports a failed
    build rather than a 500. So every failure becomes a recorded outcome, and the
    exception is not re-raised. What is *not* traded away is terminality: the
    `finally` releases the slot on every exit, including a cancelled request.
    """

    operation = (operation_id or "").strip() or new_operation_id()
    moment = indexed_at or datetime.now(UTC)

    build = await acquire_build_slot(
        session,
        operation_id=operation,
        policy_set_id=policy_set_id,
        policy_set_key=policy_set_key,
        trigger=trigger,
        actor=actor,
        started_at=moment,
    )
    if build is None:
        # Refused. Nothing was started and nothing is held, so this records the
        # attempt and returns — it does not wait, retry or queue. A queue would
        # need a worker to drain it and a story for what happens when the
        # process holding it dies, and the smallest honest behaviour is to say
        # no and let the caller decide.
        active = await running_build(session)
        reason = (
            "another policy index build is already running, and only one may run at a "
            "time across this deployment because a build re-renders and re-embeds a "
            "whole corpus and then rewrites an entire search index"
        )
        deferred = await record_deferred_build(
            session,
            operation_id=operation,
            policy_set_id=policy_set_id,
            policy_set_key=policy_set_key,
            trigger=trigger,
            actor=actor,
            error=reason,
            started_at=moment,
        )
        # The single place the two status vocabularies are reconciled. The
        # history says `deferred`, because "never ran" and "ran and failed" point
        # at different repairs; the latest-state row cannot, because what it
        # reports is whether the index can be trusted and on that question the
        # two are identical. Derived through the mapping rather than written as a
        # literal here, so the correspondence is one fact in one place that a
        # test can assert on, instead of two literals that can drift apart.
        deferred_status = cast(
            PolicyIndexBuildState, latest_state_status_for(_DEFERRED_HISTORY_STATUS)
        )
        outcome = PolicyIndexBuildOutcome(
            state=deferred_status,
            policy_set_key=policy_set_key,
            index_name=policy_index_name(policy_set_key),
            version_number=version_number,
            document_count=0,
            indexed_at=_timestamp(moment),
            error=reason,
        )
        return TrackedPolicyIndexBuild(
            accepted=False, outcome=outcome, build=deferred, conflict=active
        )

    progress = RecordedBuildProgress(session=session, build_id=build.id)
    # Initialised before the guarded region so the `finally` always has a real
    # outcome to record, whatever happened. Its default is a failure that says
    # so: a build whose record was closed without any stage reaching this
    # variable did end, and did not finish, and "no outcome" must not be able to
    # read as success.
    outcome: PolicyIndexBuildOutcome = failed_policy_index_build_outcome(
        policy_set_key=policy_set_key,
        version_number=version_number,
        error="the build ended before it recorded an outcome",
        indexed_at=moment,
    )
    try:
        try:
            outcome = await rebuild_project_policy_index(
                policy_set_key=policy_set_key,
                version_number=version_number,
                projections=await load_projections(),
                indexed_at=moment,
                progress=progress,
            )
        except BaseException as exc:  # noqa: BLE001 - recorded as a failed build, see below
            # `BaseException` deliberately, and it is the same argument
            # `upload_progress.tracking` makes: a cancelled request — the
            # operator closed the tab during a long render — is one of the ways
            # a build really ends, and it must not be the one that leaves a row
            # saying `running` with the slot in it for the whole lease.
            outcome = failed_policy_index_build_outcome(
                policy_set_key=policy_set_key,
                version_number=version_number,
                error=describe_exception(exc),
                indexed_at=moment,
            )
            if not isinstance(exc, Exception):
                # A cancellation or an interpreter shutdown is not this build's
                # to swallow. The record is closed in the `finally` below before
                # it propagates, so the row is terminal and the slot is free.
                raise
    finally:
        # Terminal on every exit, including the one that re-raises. The status is
        # derived from the outcome rather than from how we got here, so a build
        # that failed inside `rebuild_project_policy_index` (which catches its
        # own exceptions and reports `failed`) and one that raised past it are
        # recorded identically.
        await finish_build(
            session,
            build.id,
            status="completed" if outcome.state == "built" else "failed",
            error=outcome.error,
            finished_at=datetime.now(UTC),
            index_name=outcome.index_name,
            version_number=outcome.version_number,
            document_count=outcome.document_count,
            policy_document_count=outcome.policy_document_count,
            rule_document_count=outcome.rule_document_count,
            projection_profile=outcome.projection_profile,
            manifest_state=outcome.manifest_state,
            **_quality_columns(outcome.quality),
        )

    return TrackedPolicyIndexBuild(accepted=True, outcome=outcome, build=build)


def _quality_columns(quality: ProjectionQualityReport | None) -> dict:
    """The verdict as history columns. Counts and scores; no finding text.

    Empty when no verdict was reached, so the row's quality columns stay NULL —
    which reads as "never checked", and is a different fact from a check that
    ran and failed.
    """

    if quality is None:
        return {}
    return {
        "quality_state": quality.state,
        "quality_profile": quality.profile,
        "quality_checked_documents": quality.checked_documents,
        "quality_structural_findings": quality.structural_findings,
        "quality_min_similarity": quality.minimum_similarity,
        "quality_mean_similarity": quality.mean_similarity,
    }


async def drop_project_policy_index(
    *,
    policy_set_key: str,
    settings: Settings | None = None,
    search_client: AzureSearchClient | None = None,
    attempted_at: datetime | None = None,
) -> PolicyIndexDropOutcome:
    """Best-effort deletion of the whole per-project policy index."""

    settings = settings or get_settings()
    index_name = policy_index_name(policy_set_key)
    now = _timestamp(attempted_at)
    if not settings.search_enabled:
        return PolicyIndexDropOutcome(
            state="skipped",
            policy_set_key=policy_set_key,
            index_name=index_name,
            deleted=None,
            attempted_at=now,
        )
    try:
        search_client = search_client or AzureSearchClient(settings)
        deleted = await search_client.delete_index(index_name)
        return PolicyIndexDropOutcome(
            state="dropped",
            policy_set_key=policy_set_key,
            index_name=index_name,
            deleted=deleted,
            attempted_at=now,
        )
    except Exception as exc:  # noqa: BLE001 - teardown must report, not hide, Search failure
        logger.warning("best-effort policy index drop failed for set %s: %s", policy_set_key, exc)
        return PolicyIndexDropOutcome(
            state="failed",
            policy_set_key=policy_set_key,
            index_name=index_name,
            deleted=None,
            attempted_at=now,
            error=str(exc),
        )


def _strings(values: object) -> list[str]:
    if isinstance(values, str):
        return [values]
    if not isinstance(values, Iterable):
        return []
    return [value for value in values if isinstance(value, str)]


def _text_items(values: object) -> list[str]:
    if isinstance(values, str):
        return [values]
    if not isinstance(values, Iterable):
        return []
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            items.append(value)
        elif isinstance(value, dict):
            items.extend(_strings([value.get("title"), value.get("statement"), value.get("text"), value.get("effect")]))
    return items


def _projection_metadata(projection: dict) -> dict:
    envelope = projection.get("envelope")
    return envelope if isinstance(envelope, dict) else projection


def _projection_rules(projection: dict) -> list[dict]:
    return [rule for rule in projection.get("rules", []) if isinstance(rule, dict)]


def _retrieval_text_for_projection(projection: dict) -> str:
    return _retrieval_text_and_opaque_spans(projection)[0]


def _retrieval_text_and_opaque_spans(
    projection: dict,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    """The policy retrieval text and the positions of its generated terms.

    Composed in one place so the text and the provenance cannot drift: a second
    function reproducing this order would be a second thing to keep in step, and
    the positions are only meaningful against the exact string this returns.

    The policy document is composed the same way a rule's is: mostly the
    document's own words, with generated fact names among them. Those names need
    the same protection through a rendering, and for the same reason -- they are
    keys, not language. The build carries the policy's own positions rather than
    borrowing a rule's, because a key generated for one rule says nothing about
    where those letters fall in the policy's prose, and treating one set as
    covering the whole group is how a rule's slug ends up protecting a word the
    policy was merely speaking.
    """

    metadata = _projection_metadata(projection)
    rules = _projection_rules(projection)
    # (text, is_machine_made). Headings, titles, statements, conditions and
    # effects are the document's words. A fact's `name` is generated by this
    # system; its `source_phrase` is what the document actually said.
    parts: list[tuple[str, bool]] = [
        (
            build_retrieval_text(
                heading_parts=_strings(metadata.get("heading_path", [])), rules=rules
            ),
            False,
        )
    ]
    spans = projection.get("spans")
    if isinstance(spans, dict):
        parts.extend(
            (text, False)
            for text in _strings(
                item.get("text") for item in spans.values() if isinstance(item, dict)
            )
        )
    facts = projection.get("facts")
    if isinstance(facts, dict):
        for item in facts.values():
            if isinstance(item, dict):
                parts.extend((text, True) for text in _strings([item.get("name")]))
                parts.extend(
                    (text, False) for text in _strings([item.get("source_phrase")])
                )

    # Reproduces `" \n".join(dict.fromkeys(part.strip() for part in parts if ...))`
    # exactly, while recording where each kept part lands. First occurrence wins
    # the position, so it also wins the provenance: the characters at that offset
    # are the ones that contributor put there.
    kept: dict[str, bool] = {}
    for text, machine in parts:
        if not text:
            continue
        stripped = text.strip()
        if not stripped or stripped in kept:
            continue
        kept[stripped] = machine

    chunks: list[str] = []
    positions: list[tuple[int, int]] = []
    cursor = 0
    for stripped, machine in kept.items():
        if chunks:
            cursor += 2  # the " \n" separator
        if machine:
            positions.append((cursor, cursor + len(stripped)))
        cursor += len(stripped)
        chunks.append(stripped)

    text = " \n".join(chunks)[:_MAX_RETRIEVAL_TEXT_CHARS].rstrip()
    # A term the cut left incomplete is not that term, so it is not protected.
    return text, tuple((start, end) for start, end in positions if end <= len(text))


async def _create_index_accepting_empty_success(search_client: AzureSearchClient, definition: dict) -> None:
    try:
        await search_client.create_index(definition)
    except JSONDecodeError:
        # The live Search service may return a 2xx with an empty body for PUT.
        # AzureSearchClient raises before JSON parsing for non-2xx responses, so
        # this only accepts the already-successful empty-response variant.
        return


def _odata_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def odata_string(value: str) -> str:
    """One value, quoted and escaped for an OData filter.

    Exported because a caller composing a clause this module does not own — the
    retrieval path scoping a rule query to named provisions — must escape it the
    same way, and a second implementation of that escaping is a second place to
    get it wrong.
    """

    return _odata_string(value)


def _timestamp(value: datetime | None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).isoformat()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
