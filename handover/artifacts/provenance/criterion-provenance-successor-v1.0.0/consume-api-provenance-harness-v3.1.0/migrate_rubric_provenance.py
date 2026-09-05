#!/usr/bin/env python3
"""Create provenance-aware rubric/manifest v2 from hash-pinned v1 inputs."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from rubric_provenance import (
    RUBRIC_SCHEMA_VERSION,
    canonical_json_bytes,
    resolve_json_pointer,
    resolve_text_pointer,
    sha256_bytes,
    sha256_file,
)


EXPECTED_RUBRIC_V1_SHA256 = (
    "4024170d23f22c423d5b03236874f1ad88cf5cf23db287be39ac819a8050d9cc"
)
EXPECTED_MANIFEST_V1_SHA256 = (
    "f0eb6d32e89a96e4d59cdbda8dbf4e7592ac72cc2228be1f67f894bc0ea8fff3"
)
EXPECTED_SOURCE_SHA256 = (
    "01171368268bfb5c9e8bac8b8852f5bb67f6524624dd24154949978afa390c1c"
)
EXPECTED_AUDIT_SHA256 = (
    "a46099c8a187fbca985300097f962561c5d6c2c9b6fe4b921b03c7a436e6923a"
)
EXPECTED_AIS02_DECISION_SHA256 = (
    "21554676fd12f95a1dc9fddb044aa74da4351897e40e021d484e6698000b8912"
)
MANIFEST_SCHEMA_VERSION = "consume-api-matrix-manifest/2"
MANIFEST_VERSION = "2.0.0"
HARNESS_VERSION = "consume-api-provenance-harness/3.0.0"
RUBRIC_VERSION = "3.0.0"
MIGRATION_DOC_NAME = "RUBRIC_MIGRATION_V3.md"
OVERLAY_PATCH_SHA256 = (
    "2dfcdd21a4c6def599d0e06f55fc42e6fd5e3dd94800c49ca375a4cffdb81345"
)

AUDIT_LINES = {
    "AIS-02": "line:153-159",
    "AIS-03": "line:160-163",
    "AIS-04": "line:164-166",
    "AIS-06": "line:148-151",
    "AIS-08": "line:219-223",
    "AIS-09": "line:228-230",
}
SUPPORTED_R1 = {"AIS-02", "AIS-03", "AIS-04", "AIS-06", "AIS-08", "AIS-09"}
SUPPORTED_R9 = {"AIS-08", "AIS-09"}
SUPPORTED_MANUAL = {
    ("AIS-03", 0): "known_limitation_supported",
    ("AIS-04", 0): "validated_supported",
    ("AIS-08", 0): "validated_supported",
    ("AIS-09", 0): "validated_supported",
    ("AIS-09", 1): "validated_supported",
}
UNSUPPORTED_MANUAL = {
    ("AIS-02", 0),
    ("AIS-02", 1),
    ("AIS-06", 0),
    ("AIS-06", 1),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def snapshot_input(source: Path, destination: Path, expected_hash: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        destination.write_bytes(source.read_bytes())
    if sha256_file(destination) != expected_hash:
        raise RuntimeError(f"snapshot hash mismatch: {destination}")


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} is unavailable: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"{label} hash mismatch: expected {expected}, got {actual}"
        )


def semantic_manifest_hash(manifest: dict[str, Any]) -> str:
    normalized = copy.deepcopy(manifest)
    normalized.setdefault("hashes", {})["manifest_sha256"] = None
    return sha256_bytes(canonical_json_bytes(normalized))


def contract_hash(manifest: dict[str, Any]) -> str:
    contract = {
        "schema_version": manifest.get("schema_version"),
        "manifest_version": manifest.get("manifest_version"),
        "harness_version": manifest.get("harness_version"),
        "request_defaults": manifest.get("request_defaults"),
        "arms": manifest.get("arms"),
        "watchdog": manifest.get("watchdog"),
    }
    return sha256_bytes(canonical_json_bytes(contract))


def questions_hash(questions: list[dict[str, Any]]) -> str:
    identities = [
        {
            "rubric_id": question["rubric_id"],
            "id": question["id"],
            "project": question["project"],
            "corpus": question["corpus"],
            "classes": question["classes"],
            "exact_question": question["exact_question"],
        }
        for question in questions
    ]
    return sha256_bytes(canonical_json_bytes(identities))


def json_ref(
    source_id: str,
    document: Any,
    pointer: str,
    role: str,
) -> dict[str, str]:
    value = resolve_json_pointer(document, pointer)
    return {
        "role": role,
        "source_id": source_id,
        "pointer": pointer,
        "pointer_sha256": sha256_bytes(canonical_json_bytes(value)),
    }


def text_ref(
    source_id: str,
    text: str,
    pointer: str,
    role: str,
) -> dict[str, str]:
    value = resolve_text_pointer(text, pointer)
    return {
        "role": role,
        "source_id": source_id,
        "pointer": pointer,
        "pointer_sha256": sha256_bytes(value.encode("utf-8")),
    }


def support(
    *,
    provision_count: int,
    rule_count: int = 0,
    state: str,
    method: str,
    semantic_support: str,
    evidence_role: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "checked": True,
        "supporting_rule_count": rule_count,
        "supporting_provision_count": provision_count,
        "method": method,
        "semantic_support": semantic_support,
    }
    if semantic_support in {"human_confirmed", "human_confirmed_unsupported"}:
        result["human_confirmation"] = {
            "confirmed": True,
            "evidence_role": evidence_role,
            "confirmation_state": state,
        }
    return result


def target_dimension(name: str) -> dict[str, str]:
    return {"kind": "dimension", "dimension": name}


def target_manual(index: int) -> dict[str, Any]:
    return {"kind": "manual", "manual_index": index}


def provision_refs(
    source: dict[str, Any],
    indexes: dict[str, int],
    keys: list[str],
) -> list[dict[str, str]]:
    return [
        json_ref(
            "source_snapshot",
            source,
            f"/provisions/{indexes[key]}",
            f"normative_identity_{index + 1}",
        )
        for index, key in enumerate(keys)
    ]


def supported(
    *,
    criterion_id: str,
    applies_to: dict[str, Any],
    description: str,
    rubric_id: str,
    keys: list[str],
    source: dict[str, Any],
    indexes: dict[str, int],
    audit_text: str,
    state: str = "validated_supported",
    known_limitation: str | None = None,
) -> dict[str, Any]:
    refs = provision_refs(source, indexes, keys)
    refs.append(
        text_ref(
            "final_audit",
            audit_text,
            AUDIT_LINES[rubric_id],
            "semantic_validation",
        )
    )
    result: dict[str, Any] = {
        "criterion_id": criterion_id,
        "active": True,
        "applies_to": applies_to,
        "description": description,
        "criterion_provenance": "rule_body",
        "provenance_kind": "normative_source_body",
        "source_provision_ids": keys,
        "source_rule_ids": [],
        "evidence_refs": refs,
        "validation_state": state,
        "corpus_support": support(
            provision_count=len(keys),
            state=state,
            method="human_confirmed_source_body_from_final_38_call_audit",
            semantic_support="human_confirmed",
            evidence_role="semantic_validation",
        ),
    }
    if known_limitation:
        result["known_limitation"] = known_limitation
    return result


def unsupported(
    *,
    criterion_id: str,
    applies_to: dict[str, Any],
    description: str,
    rubric_id: str,
    keys: list[str],
    source: dict[str, Any],
    indexes: dict[str, int],
    audit_text: str,
) -> dict[str, Any]:
    refs = provision_refs(source, indexes, keys)
    refs.append(
        text_ref(
            "final_audit",
            audit_text,
            AUDIT_LINES[rubric_id],
            "semantic_validation",
        )
    )
    return {
        "criterion_id": criterion_id,
        "active": False,
        "applies_to": applies_to,
        "description": description,
        "criterion_provenance": "question_only",
        "provenance_kind": "unsupported_expectation",
        "source_provision_ids": keys,
        "source_rule_ids": [],
        "evidence_refs": refs,
        "validation_state": "validated_unsupported",
        "corpus_support": support(
            provision_count=0,
            state="validated_unsupported",
            method="human_confirmed_source_body_reconciliation",
            semantic_support="human_confirmed_unsupported",
            evidence_role="semantic_validation",
        ),
    }


def unverified(
    *,
    criterion_id: str,
    applies_to: dict[str, Any],
    description: str,
    question_index: int,
    pointer_suffix: str,
    rubric_v1: dict[str, Any],
    keys: list[str],
    source: dict[str, Any],
    indexes: dict[str, int],
    provenance: str,
) -> dict[str, Any]:
    refs: list[dict[str, str]] = []
    source_ids = keys if provenance == "heading_path" else []
    if source_ids:
        refs.extend(provision_refs(source, indexes, source_ids))
    refs.append(
        json_ref(
            "rubric_v1",
            rubric_v1,
            f"/questions/{question_index}/{pointer_suffix}",
            "frozen_expectation",
        )
    )
    return {
        "criterion_id": criterion_id,
        "active": True,
        "applies_to": applies_to,
        "description": description,
        "criterion_provenance": provenance,
        "provenance_kind": (
            "heading_derived" if provenance == "heading_path" else "question_inferred"
        ),
        "source_provision_ids": source_ids,
        "source_rule_ids": [],
        "evidence_refs": refs,
        "validation_state": "unverified",
        "corpus_support": support(
            provision_count=0,
            state="unverified",
            method=(
                "structural_heading_only"
                if provenance == "heading_path"
                else "question_or_rubric_only"
            ),
            semantic_support="not_applicable",
        ),
    }


def supported_ais02_r3(
    *,
    question_index: int,
    keys: list[str],
    rubric_v1: dict[str, Any],
    source: dict[str, Any],
    indexes: dict[str, int],
    decision: dict[str, Any],
) -> dict[str, Any]:
    rule_ids = [rule["rule_id"] for rule in decision["served_rules"]]
    refs = provision_refs(source, indexes, keys)
    refs.extend(
        [
            json_ref(
                "rubric_v1",
                rubric_v1,
                f"/questions/{question_index}/expected_tracks",
                "frozen_expectation",
            ),
            json_ref(
                "ais02_semantic_decision",
                decision,
                "",
                "semantic_validation",
            ),
        ]
    )
    return {
        "criterion_id": "AIS-02:R3",
        "active": True,
        "applies_to": target_dimension("R3"),
        "description": (
            "A settled entitlement does not authorize immediate execution when "
            "the normative source is silent on present approval."
        ),
        "criterion_provenance": "rule_body",
        "provenance_kind": "normative_source_body",
        "source_provision_ids": keys,
        "source_rule_ids": rule_ids,
        "evidence_refs": refs,
        "validation_state": "validated_supported",
        "corpus_support": support(
            provision_count=len(keys),
            rule_count=len(rule_ids),
            state="validated_supported",
            method="human_confirmed_entitlement_execution_boundary",
            semantic_support="human_confirmed",
            evidence_role="semantic_validation",
        ),
    }


def build_criteria(
    rubric_v1: dict[str, Any],
    source: dict[str, Any],
    audit_text: str,
    ais02_decision: dict[str, Any],
) -> list[dict[str, Any]]:
    indexes = {
        provision["provision_key"]: index
        for index, provision in enumerate(source["provisions"])
    }
    questions = copy.deepcopy(rubric_v1["questions"])
    for question_index, question in enumerate(questions):
        rubric_id = question["rubric_id"]
        keys = list(question["expected_evidence"]["required"])
        if rubric_id == "AIS-03":
            question["manual_criteria"][0] = (
                "The source occurrence ordinal must remain associated with its "
                "consequence through extracted and served evidence."
            )
        criteria: list[dict[str, Any]] = []

        if rubric_id in SUPPORTED_R1:
            criteria.append(
                supported(
                    criterion_id=f"{rubric_id}:R1",
                    applies_to=target_dimension("R1"),
                    description="All required normative provisions are served and cited.",
                    rubric_id=rubric_id,
                    keys=keys,
                    source=source,
                    indexes=indexes,
                    audit_text=audit_text,
                )
            )
        else:
            criteria.append(
                unverified(
                    criterion_id=f"{rubric_id}:R1",
                    applies_to=target_dimension("R1"),
                    description="All declared expected provisions are served and cited.",
                    question_index=question_index,
                    pointer_suffix="expected_evidence",
                    rubric_v1=rubric_v1,
                    keys=keys,
                    source=source,
                    indexes=indexes,
                    provenance="heading_path" if keys else "question_only",
                )
            )

        if rubric_id == "AIS-02":
            criteria.append(
                supported_ais02_r3(
                    question_index=question_index,
                    keys=keys,
                    rubric_v1=rubric_v1,
                    source=source,
                    indexes=indexes,
                    decision=ais02_decision,
                )
            )
        elif rubric_id == "AIS-03":
            criteria.append(
                supported(
                    criterion_id="AIS-03:R3",
                    applies_to=target_dimension("R3"),
                    description=(
                        "The first-occurrence consequence is answerable only when "
                        "source ordinality survives into served evidence."
                    ),
                    rubric_id=rubric_id,
                    keys=keys,
                    source=source,
                    indexes=indexes,
                    audit_text=audit_text,
                    state="known_limitation_supported",
                    known_limitation=(
                        "The source has occurrence columns; the frozen served rule "
                        "loses their associations."
                    ),
                )
            )
        else:
            criteria.append(
                unverified(
                    criterion_id=f"{rubric_id}:R3",
                    applies_to=target_dimension("R3"),
                    description="Observed answer tracks match the declared expected set.",
                    question_index=question_index,
                    pointer_suffix="expected_tracks",
                    rubric_v1=rubric_v1,
                    keys=[],
                    source=source,
                    indexes=indexes,
                    provenance="question_only",
                )
            )

        criteria.append(
            unverified(
                criterion_id=f"{rubric_id}:R4",
                applies_to=target_dimension("R4"),
                description="Verdict missing-information fields are internally consistent.",
                question_index=question_index,
                pointer_suffix="expected_tracks",
                rubric_v1=rubric_v1,
                keys=[],
                source=source,
                indexes=indexes,
                provenance="question_only",
            )
        )
        criteria.append(
            unverified(
                criterion_id=f"{rubric_id}:R5",
                applies_to=target_dimension("R5"),
                description="Irrelevant questions are refused safely.",
                question_index=question_index,
                pointer_suffix="irrelevant",
                rubric_v1=rubric_v1,
                keys=[],
                source=source,
                indexes=indexes,
                provenance="question_only",
            )
        )
        if rubric_id in SUPPORTED_R9:
            criteria.append(
                supported(
                    criterion_id=f"{rubric_id}:R9",
                    applies_to=target_dimension("R9"),
                    description="Every required authority for a multi-part question is used.",
                    rubric_id=rubric_id,
                    keys=keys,
                    source=source,
                    indexes=indexes,
                    audit_text=audit_text,
                )
            )
        else:
            criteria.append(
                unverified(
                    criterion_id=f"{rubric_id}:R9",
                    applies_to=target_dimension("R9"),
                    description="All declared composition authorities are present.",
                    question_index=question_index,
                    pointer_suffix="expected_evidence",
                    rubric_v1=rubric_v1,
                    keys=keys,
                    source=source,
                    indexes=indexes,
                    provenance="question_only",
                )
            )

        for manual_index, manual_text in enumerate(question["manual_criteria"]):
            pair = (rubric_id, manual_index)
            criterion_id = f"{rubric_id}:manual-{manual_index + 1}"
            if pair in UNSUPPORTED_MANUAL:
                criteria.append(
                    unsupported(
                        criterion_id=criterion_id,
                        applies_to=target_manual(manual_index),
                        description=manual_text,
                        rubric_id=rubric_id,
                        keys=keys,
                        source=source,
                        indexes=indexes,
                        audit_text=audit_text,
                    )
                )
            elif pair in SUPPORTED_MANUAL:
                criteria.append(
                    supported(
                        criterion_id=criterion_id,
                        applies_to=target_manual(manual_index),
                        description=manual_text,
                        rubric_id=rubric_id,
                        keys=keys,
                        source=source,
                        indexes=indexes,
                        audit_text=audit_text,
                        state=SUPPORTED_MANUAL[pair],
                        known_limitation=(
                            "The source table has explicit occurrence columns, but "
                            "the frozen served rule loses their associations."
                            if rubric_id == "AIS-03"
                            else None
                        ),
                    )
                )
            else:
                criteria.append(
                    unverified(
                        criterion_id=criterion_id,
                        applies_to=target_manual(manual_index),
                        description=manual_text,
                        question_index=question_index,
                        pointer_suffix=f"manual_criteria/{manual_index}",
                        rubric_v1=rubric_v1,
                        keys=[],
                        source=source,
                        indexes=indexes,
                        provenance="question_only",
                    )
                )
        question["criteria"] = criteria
    return questions


def build_rubric(
    rubric_v1: dict[str, Any],
    source: dict[str, Any],
    audit_text: str,
    ais02_decision: dict[str, Any],
    migration_doc: Path,
) -> dict[str, Any]:
    result = copy.deepcopy(rubric_v1)
    result["schema_version"] = RUBRIC_SCHEMA_VERSION
    result["rubric_version"] = RUBRIC_VERSION
    result["compatible_harness_version"] = HARNESS_VERSION
    result["status"] = "controlled_adoption_ready"
    result["source_markdown"] = {
        "path": migration_doc.name,
        "sha256": sha256_file(migration_doc),
    }
    result["corpus_topic_map"] = {
        "path": "evidence/source.snapshot.json",
        "sha256": EXPECTED_SOURCE_SHA256,
    }
    result["evidence_sources"] = [
        {
            "id": "rubric_v1",
            "path": "evidence/rubric-v1.snapshot.json",
            "sha256": EXPECTED_RUBRIC_V1_SHA256,
            "type": "json",
        },
        {
            "id": "source_snapshot",
            "path": "evidence/source.snapshot.json",
            "sha256": EXPECTED_SOURCE_SHA256,
            "type": "json",
        },
        {
            "id": "final_audit",
            "path": "evidence/ACTIONABLE_POLICY_FAILURE_AUDIT.md",
            "sha256": EXPECTED_AUDIT_SHA256,
            "type": "text",
        },
        {
            "id": "ais02_semantic_decision",
            "path": "evidence/AIS02_SEMANTIC_DECISION.json",
            "sha256": EXPECTED_AIS02_DECISION_SHA256,
            "type": "json",
        },
    ]
    result["provenance_migration"] = {
        "base_rubric_sha256": EXPECTED_RUBRIC_V1_SHA256,
        "base_manifest_sha256": EXPECTED_MANIFEST_V1_SHA256,
        "overlay_patch_sha256": OVERLAY_PATCH_SHA256,
        "predecessor_rubric_schema_version": "consume-api-evaluation-rubric/2",
        "invariant": (
            "Only active body/rule-derived criteria with validated non-zero "
            "source-bound support may produce product failures."
        ),
        "unsupported_observations": "preserve_as_rubric_error",
        "naive_keyword_absence_is_semantic_proof": False,
    }
    result["historical_replay"] = {
        "label": "old_rubric_replay_non_equivalent",
        "comparison_valid": False,
        "causal_regression_claim_allowed": False,
        "ais_like_for_like": "7/8 = 87.5%",
        "new_A_C_replay": "42/48 = 87.5%",
        "limits": [
            "old heading-substring rubric differs from provenance-aware scoring",
            "scenario and repetition denominators differ",
            "cross-era model/index identity is unavailable",
            "B/D/F are excluded from actionable target-rule conclusions",
        ],
        "corrected_failure_population": {
            "product_fail": 27,
            "rubric_error": 11,
            "unresolved": 0
        },
    }
    result["questions"] = build_criteria(
        rubric_v1,
        source,
        audit_text,
        ais02_decision,
    )
    return result


def build_manifest(
    manifest_v1: dict[str, Any],
    rubric_path: Path,
) -> dict[str, Any]:
    result = copy.deepcopy(manifest_v1)
    result["schema_version"] = MANIFEST_SCHEMA_VERSION
    result["manifest_version"] = MANIFEST_VERSION
    result["harness_version"] = HARNESS_VERSION
    result["status"] = "offline_ready_provenance_guarded_execution_disabled"
    result["rubric"]["status"] = "provenance_guarded_new_version"
    result["rubric"]["version"] = RUBRIC_VERSION
    result["rubric"]["path"] = rubric_path.name
    result["rubric"]["source_markdown_path"] = MIGRATION_DOC_NAME
    result["rubric"]["source_markdown_sha256"] = sha256_file(
        rubric_path.parent / MIGRATION_DOC_NAME
    )
    result["source_snapshot"]["path"] = "evidence/source.snapshot.json"
    result["gates"]["rubric_provenance_validated"] = True
    rubric = load_json(rubric_path)
    result["hashes"]["rubric_sha256"] = sha256_file(rubric_path)
    result["hashes"]["source_snapshot_sha256"] = EXPECTED_SOURCE_SHA256
    result["hashes"]["contract_sha256"] = contract_hash(result)
    result["hashes"]["questions_sha256"] = questions_hash(rubric["questions"])
    result["hashes"]["manifest_sha256"] = None
    result["hashes"]["manifest_sha256"] = semantic_manifest_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rubric-in", type=Path, required=True)
    parser.add_argument("--manifest-in", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--ais02-decision", type=Path, required=True)
    parser.add_argument("--migration-doc", type=Path, required=True)
    parser.add_argument("--rubric-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()

    require_hash(args.rubric_in, EXPECTED_RUBRIC_V1_SHA256, "rubric v1")
    require_hash(args.manifest_in, EXPECTED_MANIFEST_V1_SHA256, "manifest v1")
    require_hash(args.source, EXPECTED_SOURCE_SHA256, "source snapshot")
    require_hash(args.audit, EXPECTED_AUDIT_SHA256, "final audit")
    require_hash(
        args.ais02_decision,
        EXPECTED_AIS02_DECISION_SHA256,
        "AIS-02 semantic decision",
    )
    if not args.migration_doc.is_file():
        raise RuntimeError(f"migration document is unavailable: {args.migration_doc}")

    rubric_v1 = load_json(args.rubric_in)
    source = load_json(args.source)
    audit_text = args.audit.read_text(encoding="utf-8")
    ais02_decision = load_json(args.ais02_decision)
    evidence_dir = args.rubric_out.parent / "evidence"
    snapshot_input(
        args.rubric_in,
        evidence_dir / "rubric-v1.snapshot.json",
        EXPECTED_RUBRIC_V1_SHA256,
    )
    snapshot_input(
        args.manifest_in,
        evidence_dir / "manifest-v1.snapshot.json",
        EXPECTED_MANIFEST_V1_SHA256,
    )
    snapshot_input(
        args.source,
        evidence_dir / "source.snapshot.json",
        EXPECTED_SOURCE_SHA256,
    )
    snapshot_input(
        args.audit,
        evidence_dir / "ACTIONABLE_POLICY_FAILURE_AUDIT.md",
        EXPECTED_AUDIT_SHA256,
    )
    snapshot_input(
        args.ais02_decision,
        evidence_dir / "AIS02_SEMANTIC_DECISION.json",
        EXPECTED_AIS02_DECISION_SHA256,
    )
    rubric = build_rubric(
        rubric_v1,
        source,
        audit_text,
        ais02_decision,
        args.migration_doc,
    )
    write_json(args.rubric_out, rubric)
    manifest = build_manifest(load_json(args.manifest_in), args.rubric_out)
    write_json(args.manifest_out, manifest)
    print(
        json.dumps(
            {
                "status": "migrated",
                "rubric_out": str(args.rubric_out),
                "rubric_sha256": sha256_file(args.rubric_out),
                "manifest_out": str(args.manifest_out),
                "manifest_sha256": sha256_file(args.manifest_out),
                "source_inputs_modified": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
