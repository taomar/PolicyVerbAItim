"""Fail-closed provenance validation and scoring gates for rubric criteria."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


RUBRIC_SCHEMA_VERSION = "consume-api-evaluation-rubric/3"
POLICY_DIMENSIONS = ("R1", "R3", "R4", "R5", "R9")
INTEGRITY_DIMENSIONS = ("R2", "R7", "R8")
ACTIONABLE_ARMS = {"A", "C", "E"}
EXCLUDED_ARMS = {"B", "D", "F"}

CRITERION_PROVENANCE = {"rule_body", "heading_path", "question_only"}
PROVENANCE_KINDS = {
    "normative_source_body",
    "normative_rule_body",
    "heading_derived",
    "question_inferred",
    "unsupported_expectation",
}
VALIDATION_STATES = {
    "validated_supported",
    "known_limitation_supported",
    "validated_unsupported",
    "unresolved_semantics",
    "unverified",
}
SEMANTIC_SUPPORT = {
    "mechanically_proven",
    "human_confirmed",
    "human_confirmed_unsupported",
    "not_applicable",
}
SCORABLE_STATES = {"validated_supported", "known_limitation_supported"}
RESULT_PRECEDENCE = {
    "pass": 0,
    "needs_review": 1,
    "rubric_error": 2,
    "unresolved": 3,
    "fail": 4,
    "harness_error": 5,
    "excluded_non_actionable": 6,
}


class ProvenanceError(RuntimeError):
    """Raised when a rubric cannot be trusted before planning or scoring."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ProvenanceError(f"invalid JSON pointer {pointer!r}")
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise ProvenanceError(
                    f"JSON pointer {pointer!r} does not resolve"
                ) from exc
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise ProvenanceError(f"JSON pointer {pointer!r} does not resolve")
    return current


def resolve_text_pointer(text: str, pointer: str) -> str:
    if not isinstance(pointer, str) or not pointer.startswith("line:"):
        raise ProvenanceError(f"invalid text pointer {pointer!r}")
    raw_bounds = pointer[5:].split("-", 1)
    try:
        start = int(raw_bounds[0])
        end = int(raw_bounds[1]) if len(raw_bounds) == 2 else start
    except ValueError as exc:
        raise ProvenanceError(f"invalid text pointer {pointer!r}") from exc
    lines = text.splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ProvenanceError(f"text pointer {pointer!r} does not resolve")
    return "\n".join(lines[start - 1 : end])


def _collect_string_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {
            item
            for child in value
            for item in _collect_string_values(child)
        }
    if isinstance(value, dict):
        return {
            item
            for child in value.values()
            for item in _collect_string_values(child)
        }
    return set()


def _require_fields(node: dict[str, Any], fields: set[str], context: str) -> None:
    missing = sorted(fields - set(node))
    if missing:
        raise ProvenanceError(
            f"{context} is missing required field(s): {', '.join(missing)}"
        )


def _load_evidence_sources(
    rubric: dict[str, Any],
    rubric_path: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    configured = rubric.get("evidence_sources")
    if not isinstance(configured, list) or not configured:
        raise ProvenanceError("rubric must declare evidence_sources")
    loaded: dict[str, dict[str, Any]] = {}
    verified: list[dict[str, Any]] = []
    for index, source in enumerate(configured):
        context = f"evidence_sources[{index}]"
        if not isinstance(source, dict):
            raise ProvenanceError(f"{context} must be an object")
        _require_fields(source, {"id", "path", "sha256", "type"}, context)
        source_id = source["id"]
        if not isinstance(source_id, str) or not source_id or source_id in loaded:
            raise ProvenanceError(f"{context}.id must be unique and non-empty")
        if source["type"] not in {"json", "text"}:
            raise ProvenanceError(f"{context}.type is unknown")
        configured_path = Path(source["path"])
        path = (
            configured_path
            if configured_path.is_absolute()
            else rubric_path.parent / configured_path
        ).resolve()
        if not path.is_file():
            raise ProvenanceError(
                f"evidence source {source_id!r} is unavailable: {path}"
            )
        actual_hash = sha256_file(path)
        if actual_hash != source["sha256"]:
            raise ProvenanceError(
                f"evidence source {source_id!r} hash mismatch: "
                f"expected {source['sha256']}, got {actual_hash}"
            )
        content: Any
        if source["type"] == "json":
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ProvenanceError(
                    f"evidence source {source_id!r} is invalid JSON"
                ) from exc
        else:
            content = path.read_text(encoding="utf-8")
        loaded[source_id] = {
            "path": path,
            "type": source["type"],
            "content": content,
            "sha256": actual_hash,
            "configured_path": source["path"],
        }
        verified.append(
            {
                "id": source_id,
                "configured_path": source["path"],
                "resolved_path": str(path),
                "sha256": actual_hash,
                "type": source["type"],
            }
        )
    return loaded, verified


def _validate_evidence_refs(
    criterion: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    context: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    refs = criterion["evidence_refs"]
    if not isinstance(refs, list) or not refs:
        raise ProvenanceError(f"{context}.evidence_refs must be non-empty")
    verified: list[dict[str, Any]] = []
    bound_identifiers: set[str] = set()
    roles: set[str] = set()
    for index, ref in enumerate(refs):
        ref_context = f"{context}.evidence_refs[{index}]"
        if not isinstance(ref, dict):
            raise ProvenanceError(f"{ref_context} must be an object")
        _require_fields(
            ref,
            {"role", "source_id", "pointer", "pointer_sha256"},
            ref_context,
        )
        role = ref["role"]
        if not isinstance(role, str) or not role or role in roles:
            raise ProvenanceError(f"{ref_context}.role must be unique and non-empty")
        roles.add(role)
        source = sources.get(ref["source_id"])
        if source is None:
            raise ProvenanceError(
                f"{ref_context} references unknown source {ref['source_id']!r}"
            )
        if source["type"] == "json":
            pointed = resolve_json_pointer(source["content"], ref["pointer"])
            pointer_bytes = canonical_json_bytes(pointed)
            bound_identifiers.update(_collect_string_values(pointed))
        else:
            pointed = resolve_text_pointer(source["content"], ref["pointer"])
            pointer_bytes = pointed.encode("utf-8")
        actual_hash = sha256_bytes(pointer_bytes)
        if actual_hash != ref["pointer_sha256"]:
            raise ProvenanceError(
                f"{ref_context} pointer hash mismatch: "
                f"expected {ref['pointer_sha256']}, got {actual_hash}"
            )
        verified.append(copy.deepcopy(ref))
    return verified, bound_identifiers


def _criterion_disposition(
    criterion: dict[str, Any],
    verified_refs: list[dict[str, Any]],
    bound_identifiers: set[str],
    context: str,
) -> tuple[str, str | None]:
    provenance = criterion["criterion_provenance"]
    kind = criterion["provenance_kind"]
    state = criterion["validation_state"]
    support = criterion["corpus_support"]
    if provenance not in CRITERION_PROVENANCE:
        raise ProvenanceError(f"{context}.criterion_provenance is unknown")
    if kind not in PROVENANCE_KINDS:
        raise ProvenanceError(f"{context}.provenance_kind is unknown")
    if state not in VALIDATION_STATES:
        raise ProvenanceError(f"{context}.validation_state is unknown")
    expected_kinds = {
        "rule_body": {"normative_source_body", "normative_rule_body"},
        "heading_path": {"heading_derived"},
        "question_only": {"question_inferred", "unsupported_expectation"},
    }
    if kind not in expected_kinds[provenance]:
        raise ProvenanceError(
            f"{context} has inconsistent provenance kind and provenance class"
        )

    for field in ("source_provision_ids", "source_rule_ids"):
        identifiers = criterion[field]
        if not isinstance(identifiers, list) or any(
            not isinstance(value, str) or not value for value in identifiers
        ):
            raise ProvenanceError(f"{context}.{field} must contain non-empty strings")
        if len(set(identifiers)) != len(identifiers):
            raise ProvenanceError(f"{context}.{field} contains duplicates")
    source_ids = set(criterion["source_provision_ids"]) | set(
        criterion["source_rule_ids"]
    )
    if provenance == "rule_body" and not source_ids:
        raise ProvenanceError(f"{context} rule_body criterion has no source IDs")
    unbound = sorted(source_ids - bound_identifiers)
    if unbound:
        raise ProvenanceError(
            f"{context} source IDs are not bound to hashed JSON evidence: "
            f"{', '.join(unbound)}"
        )

    _require_fields(
        support,
        {
            "checked",
            "supporting_rule_count",
            "supporting_provision_count",
            "method",
            "semantic_support",
        },
        f"{context}.corpus_support",
    )
    if support["checked"] is not True:
        raise ProvenanceError(f"{context} corpus support was not checked")
    if not isinstance(support["method"], str) or not support["method"].strip():
        raise ProvenanceError(f"{context} corpus support method is empty")
    for field in ("supporting_rule_count", "supporting_provision_count"):
        value = support[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProvenanceError(f"{context}.{field} is invalid")
    semantic_support = support["semantic_support"]
    if semantic_support not in SEMANTIC_SUPPORT:
        raise ProvenanceError(f"{context}.semantic_support is unknown")
    if (
        state == "validated_unsupported"
        and semantic_support != "human_confirmed_unsupported"
    ):
        raise ProvenanceError(
            f"{context} unsupported state lacks human-confirmed reconciliation"
        )
    if state in SCORABLE_STATES and semantic_support == "human_confirmed_unsupported":
        raise ProvenanceError(f"{context} support metadata contradicts validation state")
    if semantic_support in {"human_confirmed", "human_confirmed_unsupported"}:
        confirmation = support.get("human_confirmation")
        if not isinstance(confirmation, dict):
            raise ProvenanceError(f"{context} lacks explicit human confirmation")
        _require_fields(
            confirmation,
            {"confirmed", "evidence_role", "confirmation_state"},
            f"{context}.corpus_support.human_confirmation",
        )
        if confirmation["confirmed"] is not True:
            raise ProvenanceError(f"{context} human confirmation is not affirmative")
        if confirmation["confirmation_state"] != state:
            raise ProvenanceError(f"{context} human confirmation state differs")
        if confirmation["evidence_role"] not in {
            ref["role"] for ref in verified_refs
        }:
            raise ProvenanceError(
                f"{context} human confirmation role is not a verified pointer"
            )

    if criterion.get("active") is not True:
        return "unscorable", "criterion is withdrawn but preserved for auditability"
    if provenance != "rule_body":
        return "unscorable", f"{provenance} criteria resolve to n/a"
    if state == "validated_unsupported":
        return "unscorable", "normative source does not support this expectation"
    if state == "unresolved_semantics":
        return "unresolved", "normative source does not settle this expectation"
    if state == "unverified":
        return "unscorable", "body/rule provenance has not been established"
    support_count = (
        support["supporting_rule_count"] + support["supporting_provision_count"]
    )
    if support_count == 0:
        return "unscorable", "corpus-support preflight found zero support"
    if semantic_support not in {"mechanically_proven", "human_confirmed"}:
        return "unscorable", "semantic support is not proven or human-confirmed"
    return "scorable", None


def validate_rubric_provenance(
    rubric: dict[str, Any],
    rubric_path: Path,
) -> dict[str, Any]:
    if rubric.get("schema_version") != RUBRIC_SCHEMA_VERSION:
        raise ProvenanceError(
            f"rubric schema_version must be {RUBRIC_SCHEMA_VERSION}"
        )
    sources, verified_sources = _load_evidence_sources(rubric, rubric_path)
    questions = rubric.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ProvenanceError("rubric must contain questions")

    question_results: dict[str, Any] = {}
    criteria_count = 0
    findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for question_index, question in enumerate(questions):
        question_id = question.get("id")
        context = f"questions[{question_index}]"
        if not isinstance(question_id, str) or not question_id:
            raise ProvenanceError(f"{context}.id is missing")
        criteria = question.get("criteria")
        if not isinstance(criteria, list):
            raise ProvenanceError(f"{context}.criteria is missing")
        dimensions: dict[str, Any] = {}
        manual: dict[int, Any] = {}
        for criterion_index, criterion in enumerate(criteria):
            criterion_context = f"{context}.criteria[{criterion_index}]"
            if not isinstance(criterion, dict):
                raise ProvenanceError(f"{criterion_context} must be an object")
            _require_fields(
                criterion,
                {
                    "criterion_id",
                    "active",
                    "applies_to",
                    "description",
                    "criterion_provenance",
                    "provenance_kind",
                    "source_provision_ids",
                    "source_rule_ids",
                    "evidence_refs",
                    "validation_state",
                    "corpus_support",
                },
                criterion_context,
            )
            criterion_id = criterion["criterion_id"]
            if not isinstance(criterion_id, str) or not criterion_id or criterion_id in seen_ids:
                raise ProvenanceError(
                    f"{criterion_context}.criterion_id must be unique and non-empty"
                )
            seen_ids.add(criterion_id)
            target = criterion["applies_to"]
            if not isinstance(target, dict) or target.get("kind") not in {
                "dimension",
                "manual",
            }:
                raise ProvenanceError(f"{criterion_context}.applies_to is invalid")
            verified_refs, bound_ids = _validate_evidence_refs(
                criterion, sources, criterion_context
            )
            disposition, reason = _criterion_disposition(
                criterion,
                verified_refs,
                bound_ids,
                criterion_context,
            )
            result = {
                "criterion_id": criterion_id,
                "active": criterion["active"],
                "description": criterion["description"],
                "criterion_provenance": criterion["criterion_provenance"],
                "provenance_kind": criterion["provenance_kind"],
                "source_provision_ids": criterion["source_provision_ids"],
                "source_rule_ids": criterion["source_rule_ids"],
                "validation_state": criterion["validation_state"],
                "corpus_support": criterion["corpus_support"],
                "evidence_refs": verified_refs,
                "disposition": disposition,
                "reason": reason,
                "known_limitation": criterion.get("known_limitation"),
            }
            if target["kind"] == "dimension":
                dimension_name = target.get("dimension")
                if dimension_name not in POLICY_DIMENSIONS or dimension_name in dimensions:
                    raise ProvenanceError(
                        f"{criterion_context} dimension target is invalid or duplicate"
                    )
                dimensions[dimension_name] = result
            else:
                manual_index = target.get("manual_index")
                if (
                    not isinstance(manual_index, int)
                    or isinstance(manual_index, bool)
                    or manual_index < 0
                    or manual_index in manual
                ):
                    raise ProvenanceError(
                        f"{criterion_context} manual target is invalid or duplicate"
                    )
                manual[manual_index] = result
            criteria_count += 1
            if disposition != "scorable":
                findings.append(
                    {
                        "question_id": question_id,
                        "criterion_id": criterion_id,
                        "disposition": disposition,
                        "reason": reason,
                    }
                )

        missing_dimensions = sorted(set(POLICY_DIMENSIONS) - set(dimensions))
        if missing_dimensions:
            raise ProvenanceError(
                f"{context} lacks provenance for dimensions: "
                f"{', '.join(missing_dimensions)}"
            )
        manual_criteria = question.get("manual_criteria") or []
        if set(manual) != set(range(len(manual_criteria))):
            raise ProvenanceError(
                f"{context} manual criterion provenance coverage is incomplete"
            )
        for index, text in enumerate(manual_criteria):
            if manual[index]["description"] != text:
                raise ProvenanceError(
                    f"{context}.manual_criteria[{index}] differs from provenance description"
                )
        question_results[question_id] = {
            "dimensions": dimensions,
            "manual": [manual[index] for index in sorted(manual)],
        }

    return {
        "schema_version": "consume-api-rubric-provenance-preflight/2",
        "status": "ready" if not findings else "ready_with_rubric_findings",
        "verified_sources": verified_sources,
        "criterion_count": criteria_count,
        "rubric_findings": findings,
        "questions": question_results,
        "invariant": (
            "Only active, body-derived, source-bound, supported criteria may "
            "produce product failures."
        ),
    }


def rollup_scored_results(results: list[str]) -> str:
    if not results:
        return "pass"
    unknown = sorted(set(results) - set(RESULT_PRECEDENCE))
    if unknown:
        raise ProvenanceError(f"unknown scored result(s): {', '.join(unknown)}")
    return max(results, key=lambda value: RESULT_PRECEDENCE[value])


def gate_evaluation(
    question: dict[str, Any],
    dimensions: dict[str, dict[str, str]],
    preflight: dict[str, Any],
    arm_id: str,
) -> dict[str, Any]:
    question_id = question["id"]
    provenance = preflight["questions"][question_id]
    product_failures: list[str] = []
    harness_failures = [
        name
        for name in INTEGRITY_DIMENSIONS
        if dimensions[name]["status"] == "fail"
    ]
    rubric_findings: list[str] = []
    unresolved: list[str] = []
    criterion_results: list[dict[str, Any]] = []

    for dimension_name in POLICY_DIMENSIONS:
        criterion = provenance["dimensions"][dimension_name]
        observed = dimensions[dimension_name]["status"]
        disposition = criterion["disposition"]
        if disposition == "scorable":
            classification = (
                "product_fail" if observed == "fail" else "product_pass_or_n_a"
            )
            if observed == "fail":
                product_failures.append(dimension_name)
        elif disposition == "unresolved":
            classification = (
                "unresolved" if observed == "fail" else "not_triggered"
            )
            if observed == "fail":
                unresolved.append(criterion["criterion_id"])
        else:
            classification = "rubric_error"
            if observed != "not_applicable":
                rubric_findings.append(criterion["criterion_id"])
        criterion_results.append(
            {
                "criterion_id": criterion["criterion_id"],
                "target": dimension_name,
                "observed_result_preserved": observed,
                "reported_result": (
                    observed if disposition == "scorable" else "not_applicable"
                ),
                "classification": classification,
                "charged_to_product": (
                    arm_id in ACTIONABLE_ARMS
                    and disposition == "scorable"
                    and observed == "fail"
                ),
                "provenance_disposition": disposition,
                "provenance_reason": criterion["reason"],
            }
        )

    scorable_manual = [
        criterion
        for criterion in provenance["manual"]
        if criterion["disposition"] == "scorable"
    ]
    for criterion in provenance["manual"]:
        if criterion["disposition"] == "unscorable":
            rubric_findings.append(criterion["criterion_id"])

    if arm_id in EXCLUDED_ARMS:
        scored_result = "excluded_non_actionable"
    elif harness_failures:
        scored_result = "harness_error"
    elif product_failures:
        scored_result = "fail"
    elif unresolved:
        scored_result = "unresolved"
    elif rubric_findings:
        scored_result = "rubric_error"
    elif scorable_manual:
        scored_result = "needs_review"
    else:
        scored_result = "pass"

    return {
        "scored_result": scored_result,
        "actionable_target_rule_conclusion": arm_id in ACTIONABLE_ARMS,
        "observed_dimension_failures": sorted(
            name
            for name, result in dimensions.items()
            if result["status"] == "fail"
        ),
        "product_failures": product_failures,
        "harness_failures": harness_failures,
        "rubric_findings": sorted(set(rubric_findings)),
        "unresolved_criteria": unresolved,
        "criterion_results": criterion_results,
        "manual_review_required": bool(scorable_manual),
        "manual_criteria": [
            {
                "criterion_id": criterion["criterion_id"],
                "description": criterion["description"],
                "disposition": criterion["disposition"],
                "active": criterion["active"],
            }
            for criterion in provenance["manual"]
        ],
    }


def classify_manual_decisions(
    question: dict[str, Any],
    decisions: list[dict[str, Any]],
    preflight: dict[str, Any],
    arm_id: str,
) -> dict[str, Any]:
    criteria = preflight["questions"][question["id"]]["manual"]
    if len(decisions) != len(criteria):
        raise ProvenanceError("manual decision count does not match rubric criteria")
    product_failures: list[str] = []
    rubric_findings: list[str] = []
    unresolved: list[str] = []
    results: list[dict[str, Any]] = []
    for index, (decision, criterion) in enumerate(zip(decisions, criteria)):
        if not isinstance(decision, dict):
            raise ProvenanceError(f"manual decision {index} must be an object")
        observed = decision.get("decision")
        if observed not in {"pass", "fail", "not_applicable", "unresolved"}:
            raise ProvenanceError(f"manual decision {index} has an unknown result")
        if not decision.get("evidence"):
            raise ProvenanceError(f"manual decision {index} lacks evidence")
        disposition = criterion["disposition"]
        if disposition == "scorable":
            classification = (
                "product_fail" if observed == "fail" else "product_pass_or_n_a"
            )
            if observed == "fail":
                product_failures.append(criterion["criterion_id"])
            reported = observed
        elif disposition == "unresolved":
            classification = "unresolved"
            unresolved.append(criterion["criterion_id"])
            reported = "unresolved"
        else:
            classification = "rubric_error"
            rubric_findings.append(criterion["criterion_id"])
            reported = "not_applicable"
        results.append(
            {
                "criterion_id": criterion["criterion_id"],
                "observed_result_preserved": observed,
                "reported_result": reported,
                "classification": classification,
                "charged_to_product": (
                    arm_id in ACTIONABLE_ARMS
                    and disposition == "scorable"
                    and observed == "fail"
                ),
                "evidence": decision["evidence"],
            }
        )

    if arm_id in EXCLUDED_ARMS:
        classification = "excluded_non_actionable"
    elif product_failures:
        classification = "fail"
    elif unresolved:
        classification = "unresolved"
    elif rubric_findings:
        classification = "rubric_error"
    else:
        classification = "pass"
    return {
        "classification": classification,
        "actionable_target_rule_conclusion": arm_id in ACTIONABLE_ARMS,
        "product_failure_criteria": product_failures,
        "rubric_finding_criteria": rubric_findings,
        "unresolved_criteria": unresolved,
        "criterion_results": results,
        "unsupported_observations_preserved": [
            result
            for result in results
            if result["classification"] == "rubric_error"
        ],
    }
