#!/usr/bin/env python3
"""Build and validate the first normative-provenance overlay without source mutation."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BUNDLE = Path(
    r"C:\Users\taomar\.copilot\session-state"
    r"\135cb788-7072-4c5f-84d0-7458aba79def"
    r"\files\consume-api-provenance-harness-v3.0.0"
)
RUN_ROOT = Path(
    r"C:\Users\taomar\.copilot\session-state"
    r"\b9e79289-63de-4596-8a76-88064fb51cf8"
    r"\files\consume-api-matrix-ais\runs\consume-api-ais-six-arm-20260904"
)
AIS_SOURCE_SNAPSHOT = RUN_ROOT.parent.parent / "source-snapshot.ais.json"
OUTPUT_DIR = Path(__file__).resolve().parent

EXPECTED_BUNDLE_SHA256 = (
    "fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c"
)
EXPECTED_RUBRIC_SHA256 = (
    "6bd271a45d466ed048427a32ea2c7143bc23b3376e9ea06627f7239c481d7c58"
)
EXPECTED_BUNDLE_SOURCE_SHA256 = (
    "01171368268bfb5c9e8bac8b8852f5bb67f6524624dd24154949978afa390c1c"
)
EXPECTED_AIS_SOURCE_SHA256 = (
    "95df2a9538bb5090a5ab652a57b5f7f29e614ea7b2da2343203c05a903cd4718"
)
EXPECTED_SOURCE_DOCUMENT_SHA256 = (
    "a4ab80af24640509976881a36b76895b474558f3cb5a1b4fa564d0bf7faf07e9"
)

CLASSIFICATIONS = (
    "mechanically_source_supported",
    "semantic_support_pending_human_confirmation",
    "unsupported_or_contradicted_rubric",
    "structural_harness_non_product_law",
    "unavailable_evidence",
    "product_decision_required",
)

STRUCTURAL_REASONS = {
    "R4": (
        "Internal consistency of verdict metadata is a harness and API-contract "
        "invariant, not a product-law proposition."
    ),
    "R5": (
        "Safe refusal of irrelevant questions is a platform safety behavior, not "
        "a norm in the policy corpus."
    ),
    "R9": (
        "For this single-authority question, composition completeness is a "
        "harness source-selection check rather than an independent product-law norm."
    ),
}
PRODUCT_DECISION_REASON = (
    "Whether the API must expose the declared answer-track statuses is a product "
    "contract choice; normative policy text cannot determine response-shape semantics."
)

EVIDENCE_SPECS = {
    "annual": {
        "source_id": "ais_e_annual_vacation_r1",
        "question_id": "ais-annual-vacation",
        "response_name": "E__ais-annual-vacation__r1.decoded",
        "record_name": "E__ais-annual-vacation__r1.json",
        "pointer": "/policies/0/payload",
        "provision_id": "ab87a692f3a20e95c545a0ce7718ba61",
    },
    "sick": {
        "source_id": "ais_e_sick_surgery_r1",
        "question_id": "ais-sick-surgery",
        "response_name": "E__ais-sick-surgery__r1.decoded",
        "record_name": "E__ais-sick-surgery__r1.json",
        "pointer": "/policies/0/payload",
        "provision_id": "28334f1a0b3c389682647d43c89d554f",
    },
    "maternity": {
        "source_id": "ais_e_maternity_leave_r1",
        "question_id": "ais-maternity-leave",
        "response_name": "E__ais-maternity-leave__r1.decoded",
        "record_name": "E__ais-maternity-leave__r1.json",
        "pointer": "/policies/0/payload",
        "provision_id": "01309aeb409607211e4115e044bd8ac3",
    },
    "overtime": {
        "source_id": "ais_e_overtime_weekend_r1",
        "question_id": "ais-overtime-weekend",
        "response_name": "E__ais-overtime-weekend__r1.decoded",
        "record_name": "E__ais-overtime-weekend__r1.json",
        "pointer": "/policies/0/payload",
        "provision_id": "4094ad6b422dbb097ec11368c525b5a6",
    },
    "tuition": {
        "source_id": "ais_e_tuition_child_r1",
        "question_id": "ais-tuition-child",
        "response_name": "E__ais-tuition-child__r1.decoded",
        "record_name": "E__ais-tuition-child__r1.json",
        "pointer": "/policies/0/payload",
        "provision_id": "77ec032421fdcfc11ed1dd2fb6ee7ae4",
    },
}

MECHANICAL = {
    "AIS-01:R1": {
        "evidence": "annual",
        "provenance_kind": "normative_source_body",
        "reason": (
            "The hash-bound retrieval payload contains the declared annual-leave "
            "provision and its complete rule set; authority identity is mechanical."
        ),
    },
    "AIS-05:R1": {
        "evidence": "maternity",
        "provenance_kind": "normative_source_body",
        "reason": (
            "The hash-bound retrieval payload contains the declared maternity "
            "provision and its complete rule set; authority identity is mechanical."
        ),
    },
    "AIS-07:R1": {
        "evidence": "tuition",
        "provenance_kind": "normative_source_body",
        "reason": (
            "The hash-bound retrieval payload contains the declared tuition "
            "provision and its complete rule set; authority identity is mechanical."
        ),
    },
    "AIS-07:manual-1": {
        "evidence": "tuition",
        "provenance_kind": "normative_rule_body",
        "rule_ids": ["AI-c3c7e28449"],
        "reason": (
            "The hash-bound tuition provision and its sole rule establish the "
            "required subject-matter authority, so omission is mechanically testable."
        ),
    },
}

SEMANTIC_PENDING = {
    "AIS-02:manual-1": {
        "evidence": "sick",
        "rule_ids": ["AI-7336476841", "AI-b4226cc420"],
        "candidate_outcome": "unsupported_or_contradicted_rubric",
        "reason": (
            "The body and rules place report submission after return, suggesting "
            "that a current-certificate prerequisite is unsupported; the temporal "
            "interpretation requires human confirmation."
        ),
    },
    "AIS-02:manual-2": {
        "evidence": "sick",
        "rule_ids": ["AI-7336476841", "AI-b4226cc420"],
        "candidate_outcome": "unsupported_or_contradicted_rubric",
        "reason": (
            "The body and rules separate sick-leave entitlement from post-return "
            "report submission, suggesting the certificate-based failure rule is "
            "unsupported; the interpretation requires human confirmation."
        ),
    },
    "AIS-06:manual-1": {
        "evidence": "overtime",
        "rule_ids": ["AI-5dca015982", "AI-ca3d9b8901"],
        "candidate_outcome": "unsupported_or_contradicted_rubric",
        "reason": (
            "The body and rules assign approval and control to named authorities "
            "without encoding a documentary form, suggesting the written-approval "
            "criterion is unsupported; human confirmation is required."
        ),
    },
    "AIS-06:manual-2": {
        "evidence": "overtime",
        "rule_ids": ["AI-5dca015982", "AI-ca3d9b8901"],
        "candidate_outcome": "unsupported_or_contradicted_rubric",
        "reason": (
            "The normative requirement concerns approval and control rather than "
            "a written instrument, suggesting this automatic failure rule is "
            "unsupported; human confirmation is required."
        ),
    },
}

PRODUCT_DECISIONS = {
    "AIS-01:R3",
    "AIS-04:R3",
    "AIS-05:R3",
    "AIS-06:R3",
    "AIS-07:R3",
    "AIS-08:R3",
}

SPECIAL_STRUCTURAL = {
    "AIS-01:manual-1": (
        "This checks consistency between supplied case facts and missing-information "
        "output; policy rules inform the evaluation but the criterion is a harness invariant."
    ),
    "AIS-05:manual-1": (
        "This requires any claimed submission duty to be citation-grounded; it is "
        "a non-fabrication and evidence-accounting invariant, not an independent policy norm."
    ),
}


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def criterion_classification(criterion_id: str) -> tuple[str, str]:
    if criterion_id in MECHANICAL:
        return "mechanically_source_supported", MECHANICAL[criterion_id]["reason"]
    if criterion_id in SEMANTIC_PENDING:
        return (
            "semantic_support_pending_human_confirmation",
            SEMANTIC_PENDING[criterion_id]["reason"],
        )
    if criterion_id in PRODUCT_DECISIONS:
        return "product_decision_required", PRODUCT_DECISION_REASON
    if criterion_id in SPECIAL_STRUCTURAL:
        return "structural_harness_non_product_law", SPECIAL_STRUCTURAL[criterion_id]
    suffix = criterion_id.rsplit(":", 1)[-1]
    if suffix in STRUCTURAL_REASONS:
        return "structural_harness_non_product_law", STRUCTURAL_REASONS[suffix]
    raise AssertionError(f"criterion has no classification: {criterion_id}")


def compute_bundle_hash(inventory: dict[str, Any]) -> str:
    records = []
    canonical_entries = sorted(
        (entry for entry in inventory["files"] if entry["canonical_payload"]),
        key=lambda entry: entry["path"].encode("utf-8"),
    )
    for entry in canonical_entries:
        actual = sha256_file(BUNDLE / Path(entry["path"]))
        if actual != entry["sha256"]:
            raise AssertionError(f"bundle file hash mismatch: {entry['path']}")
        records.append(f"{entry['path']}\0{actual}\n".encode("utf-8"))
    return sha256_bytes(b"".join(records))


def load_evidence() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    loaded: dict[str, Any] = {}
    attestations: list[dict[str, Any]] = []
    ais_source_hash = sha256_file(AIS_SOURCE_SNAPSHOT)
    if ais_source_hash != EXPECTED_AIS_SOURCE_SHA256:
        raise AssertionError("AIS source snapshot hash mismatch")

    for key, spec in EVIDENCE_SPECS.items():
        response_path = RUN_ROOT / "responses" / spec["response_name"]
        record_path = RUN_ROOT / "records" / spec["record_name"]
        response_hash = sha256_file(response_path)
        record_hash = sha256_file(record_path)
        response = load_json(response_path)
        record = load_json(record_path)
        expected_job_id = spec["record_name"][:-5]
        if record["job_id"] != expected_job_id:
            raise AssertionError(f"record job mismatch: {record_path}")
        if record["question"]["id"] != spec["question_id"]:
            raise AssertionError(f"record question mismatch: {record_path}")
        if record["response"]["decoded_body_sha256"] != response_hash:
            raise AssertionError(f"record response hash mismatch: {record_path}")
        if record["provenance"]["source_snapshot_sha256"] != ais_source_hash:
            raise AssertionError(f"record source snapshot mismatch: {record_path}")

        pointed = resolve_pointer(response, spec["pointer"])
        pointer_hash = sha256_bytes(canonical_json_bytes(pointed))
        if pointed["envelope"]["provision_key"] != spec["provision_id"]:
            raise AssertionError(f"provision mismatch: {response_path}")
        rule_ids = [rule["rule_id"] for rule in pointed["rules"]]
        if len(rule_ids) != len(set(rule_ids)):
            raise AssertionError(f"duplicate rule IDs: {response_path}")
        source_document_hashes = sorted(
            {
                span["source_hash"]
                for span in pointed["spans"].values()
                if span.get("source_hash")
            }
        )
        if source_document_hashes != [EXPECTED_SOURCE_DOCUMENT_SHA256]:
            raise AssertionError(f"unexpected source document hash: {response_path}")

        rule_attestations = []
        for index, rule in enumerate(pointed["rules"]):
            rule_pointer = f"{spec['pointer']}/rules/{index}"
            rule_attestations.append(
                {
                    "rule_id": rule["rule_id"],
                    "pointer": rule_pointer,
                    "pointer_sha256": sha256_bytes(canonical_json_bytes(rule)),
                    "source_span_ids": list(rule.get("evidence_refs") or []),
                }
            )
        span_attestations = []
        for span_id, span in sorted(pointed["spans"].items()):
            span_pointer = f"{spec['pointer']}/spans/{span_id}"
            span_attestations.append(
                {
                    "span_id": span_id,
                    "pointer": span_pointer,
                    "pointer_sha256": sha256_bytes(canonical_json_bytes(span)),
                    "source_document_sha256": span.get("source_hash"),
                }
            )

        loaded[key] = {
            "spec": spec,
            "path": response_path,
            "file_sha256": response_hash,
            "pointer_sha256": pointer_hash,
            "payload": pointed,
            "rule_ids": rule_ids,
        }
        attestations.append(
            {
                "key": key,
                "source_id": spec["source_id"],
                "question_id": spec["question_id"],
                "response_path": str(response_path),
                "response_file_sha256": response_hash,
                "record_path": str(record_path),
                "record_file_sha256": record_hash,
                "record_response_hash_matches": True,
                "record_source_snapshot_hash_matches": True,
                "pointer": spec["pointer"],
                "pointer_sha256": pointer_hash,
                "source_provision_id": spec["provision_id"],
                "source_rule_ids": rule_ids,
                "embedded_source_document_sha256s": source_document_hashes,
                "rules": rule_attestations,
                "spans": span_attestations,
            }
        )
    return loaded, attestations


def evidence_ref(evidence: dict[str, Any], role: str = "normative_policy_payload") -> dict[str, str]:
    return {
        "role": role,
        "source_id": evidence["spec"]["source_id"],
        "pointer": evidence["spec"]["pointer"],
        "pointer_sha256": evidence["pointer_sha256"],
    }


def make_replacement(
    original: dict[str, Any],
    mechanical: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(original)
    rule_ids = mechanical.get("rule_ids", evidence["rule_ids"])
    if not set(rule_ids).issubset(evidence["rule_ids"]):
        raise AssertionError(f"unbound mechanical rule IDs: {original['criterion_id']}")
    result.update(
        {
            "active": True,
            "criterion_provenance": "rule_body",
            "provenance_kind": mechanical["provenance_kind"],
            "source_provision_ids": [evidence["spec"]["provision_id"]],
            "source_rule_ids": rule_ids,
            "evidence_refs": [evidence_ref(evidence)],
            "validation_state": "validated_supported",
            "corpus_support": {
                "checked": True,
                "supporting_rule_count": len(rule_ids),
                "supporting_provision_count": 1,
                "method": "mechanical_hash_bound_normative_payload_identity",
                "semantic_support": "mechanically_proven",
            },
        }
    )
    return result


def validate_overlay_shape(overlay: dict[str, Any], expected_ids: list[str]) -> None:
    required = {
        "schema_version",
        "batch",
        "base_bundle",
        "slice_contract",
        "classification_vocabulary",
        "evidence_sources",
        "operations",
        "expected_post_merge",
        "invariants",
    }
    if set(overlay) != required:
        raise AssertionError("overlay top-level schema mismatch")
    if overlay["schema_version"] != "consume-api-normative-provenance-overlay/1":
        raise AssertionError("overlay schema version mismatch")
    operations = overlay["operations"]
    operation_ids = [item["criterion_id"] for item in operations]
    if operation_ids != expected_ids:
        raise AssertionError("overlay operation membership/order mismatch")
    if len(operation_ids) != len(set(operation_ids)):
        raise AssertionError("overlay contains duplicate criterion IDs")
    if set(overlay["classification_vocabulary"]) != set(CLASSIFICATIONS):
        raise AssertionError("overlay classification vocabulary mismatch")
    for item in operations:
        if item["classification"] not in CLASSIFICATIONS:
            raise AssertionError(f"unknown classification: {item['criterion_id']}")
        if item["action"] == "replace_criterion_provenance":
            replacement = item.get("replacement")
            if not isinstance(replacement, dict):
                raise AssertionError(f"replacement missing: {item['criterion_id']}")
            if replacement["criterion_id"] != item["criterion_id"]:
                raise AssertionError(f"replacement ID mismatch: {item['criterion_id']}")
        elif item["action"] != "retain_unscorable":
            raise AssertionError(f"unknown operation: {item['criterion_id']}")


def main() -> None:
    sys.path.insert(0, str(BUNDLE))
    import rubric_provenance  # noqa: PLC0415

    inventory = load_json(BUNDLE / "FILE_INVENTORY.json")
    bundle_hash = compute_bundle_hash(inventory)
    if bundle_hash != EXPECTED_BUNDLE_SHA256:
        raise AssertionError("canonical bundle hash mismatch")
    rubric_path = BUNDLE / "evaluation-rubric.json"
    if sha256_file(rubric_path) != EXPECTED_RUBRIC_SHA256:
        raise AssertionError("canonical rubric hash mismatch")
    if (
        sha256_file(BUNDLE / "evidence" / "source.snapshot.json")
        != EXPECTED_BUNDLE_SOURCE_SHA256
    ):
        raise AssertionError("canonical source snapshot hash mismatch")

    rubric = load_json(rubric_path)
    preflight = rubric_provenance.validate_rubric_provenance(rubric, rubric_path)
    unscorable_ids = sorted(
        finding["criterion_id"]
        for finding in preflight["rubric_findings"]
        if finding["disposition"] in {"unscorable", "unresolved"}
    )
    if len(unscorable_ids) != 113:
        raise AssertionError(f"expected 113 unscorable criteria, got {len(unscorable_ids)}")
    owned_ids = unscorable_ids[:38]
    if len(owned_ids) != 38:
        raise AssertionError("owned slice length mismatch")
    owned_ids_hash = sha256_bytes(canonical_json_bytes(owned_ids))

    criteria_by_id = {
        criterion["criterion_id"]: (question, criterion)
        for question in rubric["questions"]
        for criterion in question["criteria"]
    }
    evidence, evidence_attestations = load_evidence()

    operations = []
    ledger_rows = []
    for index, criterion_id in enumerate(owned_ids, start=1):
        question, original = criteria_by_id[criterion_id]
        classification, reason = criterion_classification(criterion_id)
        operation: dict[str, Any] = {
            "criterion_id": criterion_id,
            "classification": classification,
        }
        ledger_evidence: list[dict[str, Any]] = []
        candidate_outcome = None
        if criterion_id in MECHANICAL:
            mechanical = MECHANICAL[criterion_id]
            source = evidence[mechanical["evidence"]]
            replacement = make_replacement(original, mechanical, source)
            operation.update(
                {
                    "action": "replace_criterion_provenance",
                    "evidence_source_ids": [source["spec"]["source_id"]],
                    "replacement": replacement,
                }
            )
            ledger_evidence.append(
                {
                    "source_id": source["spec"]["source_id"],
                    "source_provision_ids": replacement["source_provision_ids"],
                    "source_rule_ids": replacement["source_rule_ids"],
                    "pointer": source["spec"]["pointer"],
                    "pointer_sha256": source["pointer_sha256"],
                    "source_file_sha256": source["file_sha256"],
                }
            )
            human_confirmation = "not_required_mechanical"
        elif criterion_id in SEMANTIC_PENDING:
            pending = SEMANTIC_PENDING[criterion_id]
            source = evidence[pending["evidence"]]
            if not set(pending["rule_ids"]).issubset(source["rule_ids"]):
                raise AssertionError(f"pending rule IDs are unbound: {criterion_id}")
            operation.update(
                {
                    "action": "retain_unscorable",
                    "review_evidence": [
                        {
                            "source_id": source["spec"]["source_id"],
                            "source_provision_ids": [source["spec"]["provision_id"]],
                            "source_rule_ids": pending["rule_ids"],
                            "pointer": source["spec"]["pointer"],
                            "pointer_sha256": source["pointer_sha256"],
                            "source_file_sha256": source["file_sha256"],
                        }
                    ],
                    "candidate_outcome": pending["candidate_outcome"],
                    "human_confirmation": "required_not_provided",
                }
            )
            ledger_evidence = copy.deepcopy(operation["review_evidence"])
            candidate_outcome = pending["candidate_outcome"]
            human_confirmation = "required_not_provided"
        else:
            operation.update(
                {
                    "action": "retain_unscorable",
                    "human_confirmation": "not_applicable",
                }
            )
            human_confirmation = "not_applicable"
        operations.append(operation)
        ledger_rows.append(
            {
                "slice_index": index,
                "criterion_id": criterion_id,
                "rubric_id": question["rubric_id"],
                "question_id": question["id"],
                "current": {
                    "active": original["active"],
                    "criterion_provenance": original["criterion_provenance"],
                    "provenance_kind": original["provenance_kind"],
                    "validation_state": original["validation_state"],
                },
                "classification": classification,
                "action": operation["action"],
                "bounded_rationale": reason,
                "evidence": ledger_evidence,
                "candidate_outcome": candidate_outcome,
                "human_confirmation": human_confirmation,
            }
        )
        if index in {10, 20, 30, 38}:
            print(f"CHECKPOINT {index}/38")

    source_ids_needed = sorted(
        {
            source_id
            for operation in operations
            for source_id in operation.get("evidence_source_ids", [])
        }
    )
    evidence_sources = []
    for source_id in source_ids_needed:
        source = next(
            item
            for item in evidence.values()
            if item["spec"]["source_id"] == source_id
        )
        evidence_sources.append(
            {
                "id": source_id,
                "path": str(source["path"]),
                "sha256": source["file_sha256"],
                "type": "json",
            }
        )

    counts = Counter(row["classification"] for row in ledger_rows)
    counts_complete = {name: counts.get(name, 0) for name in CLASSIFICATIONS}
    overlay = {
        "schema_version": "consume-api-normative-provenance-overlay/1",
        "batch": {
            "id": "batch-1",
            "owner_slice": {"start_inclusive": 1, "end_inclusive": 38},
            "criterion_count": 38,
        },
        "base_bundle": {
            "path": str(BUNDLE),
            "canonical_payload_sha256": bundle_hash,
            "rubric_sha256": EXPECTED_RUBRIC_SHA256,
            "bundle_source_snapshot_sha256": EXPECTED_BUNDLE_SOURCE_SHA256,
        },
        "slice_contract": {
            "filter": "preflight disposition in {unscorable, unresolved}",
            "sort": "criterion_id ordinal ascending",
            "total_asserted": 113,
            "first_owned_id": owned_ids[0],
            "last_owned_id": owned_ids[-1],
            "owned_ids_sha256": owned_ids_hash,
            "owned_ids": owned_ids,
        },
        "classification_vocabulary": list(CLASSIFICATIONS),
        "evidence_sources": evidence_sources,
        "operations": operations,
        "expected_post_merge": {
            "criterion_total": 128,
            "scorable": 19,
            "unscorable_or_unresolved": 109,
            "batch_upgraded_to_scorable": counts_complete[
                "mechanically_source_supported"
            ],
            "batch_retained_unscorable": 38
            - counts_complete["mechanically_source_supported"],
        },
        "invariants": [
            "No criterion outside sorted unscorable slice indices 1-38 is modified.",
            "Only mechanically source-supported criteria are upgraded to scorable.",
            "AI review is never represented as human confirmation.",
            "No confidential normative body text is copied into this overlay.",
            "Execution remains disabled and no production guard logic is changed.",
        ],
    }
    validate_overlay_shape(overlay, owned_ids)

    merged = copy.deepcopy(rubric)
    existing_source_ids = {item["id"] for item in merged["evidence_sources"]}
    for source in evidence_sources:
        if source["id"] in existing_source_ids:
            raise AssertionError(f"evidence source ID collision: {source['id']}")
        merged["evidence_sources"].append(source)
    replacements = {
        operation["criterion_id"]: operation["replacement"]
        for operation in operations
        if operation["action"] == "replace_criterion_provenance"
    }
    for question in merged["questions"]:
        question["criteria"] = [
            replacements.get(criterion["criterion_id"], criterion)
            for criterion in question["criteria"]
        ]
    merged_preflight = rubric_provenance.validate_rubric_provenance(
        merged,
        rubric_path,
    )
    merged_findings = [
        finding
        for finding in merged_preflight["rubric_findings"]
        if finding["disposition"] in {"unscorable", "unresolved"}
    ]
    if merged_preflight["criterion_count"] != 128:
        raise AssertionError("post-merge criterion count mismatch")
    if len(merged_findings) != 109:
        raise AssertionError("post-merge finding count mismatch")

    overlay_path = OUTPUT_DIR / "criterion-provenance-batch1-overlay.json"
    ledger_path = OUTPUT_DIR / "criterion-provenance-batch1-ledger.json"
    attestation_path = (
        OUTPUT_DIR / "criterion-provenance-batch1-source-attestations.json"
    )
    validation_path = OUTPUT_DIR / "criterion-provenance-batch1-validation.json"
    merge_path = OUTPUT_DIR / "criterion-provenance-batch1-MERGE.md"

    ledger = {
        "schema_version": "consume-api-normative-provenance-ledger/1",
        "batch_id": "batch-1",
        "criterion_count": 38,
        "classification_counts": counts_complete,
        "criteria": ledger_rows,
        "confidential_source_text_included": False,
    }
    attestations = {
        "schema_version": "consume-api-source-hash-attestations/1",
        "batch_id": "batch-1",
        "canonical_bundle": {
            "declared_sha256": EXPECTED_BUNDLE_SHA256,
            "recomputed_sha256": bundle_hash,
            "match": True,
        },
        "canonical_harness_inputs": [
            {
                "path": str(rubric_path),
                "sha256": EXPECTED_RUBRIC_SHA256,
            },
            {
                "path": str(BUNDLE / "evidence" / "source.snapshot.json"),
                "sha256": EXPECTED_BUNDLE_SOURCE_SHA256,
            },
            {
                "path": str(AIS_SOURCE_SNAPSHOT),
                "sha256": EXPECTED_AIS_SOURCE_SHA256,
            },
        ],
        "normative_evidence": evidence_attestations,
        "source_document_file_available": False,
        "embedded_source_document_sha256": EXPECTED_SOURCE_DOCUMENT_SHA256,
        "confidential_source_text_included": False,
    }
    merge_text = f"""# Batch 1 provenance merge instructions

This overlay owns only sorted unscorable criterion indices **1-38** from the
canonical 113-item preflight set. Apply it only to a secured local copy of the
v3.0.0 harness; do not edit the authoritative bundle.

1. Verify the canonical bundle payload hash is `{EXPECTED_BUNDLE_SHA256}` and
   the rubric hash is `{EXPECTED_RUBRIC_SHA256}`.
2. Verify every source and pointer hash in
   `criterion-provenance-batch1-source-attestations.json`.
3. Add the three `evidence_sources` from the overlay. Preserve the exact bytes
   and SHA-256 if a secure local staging path replaces an absolute path.
4. Apply only the four `replace_criterion_provenance` operations. Do not apply
   changes to any criterion outside the overlay's exact `owned_ids`.
5. Keep all `retain_unscorable` operations fail-closed. Four need independent
   human semantic confirmation, six require product contract decisions, and
   twenty-four are structural/harness criteria rather than product-law criteria.
6. Do not treat any AI-generated review, audit, or ledger as human confirmation.
7. Run `validate_rubric_provenance` after merging. With only this batch applied,
   expect 128 total criteria, 19 scorable, and 109 unscorable/unresolved findings.
8. Preserve execution-disabled gates. Do not add criterion IDs, benchmark names,
   or corpus-specific branches to production guard logic.

The overlay and ledger contain no normative source quotations. They carry only
bounded rationale, identifiers, pointers, and hashes.
"""

    non_source_serialized = "\n".join(
        (
            json.dumps(overlay, ensure_ascii=False, sort_keys=True),
            json.dumps(ledger, ensure_ascii=False, sort_keys=True),
            json.dumps(attestations, ensure_ascii=False, sort_keys=True),
            merge_text,
        )
    )
    source_texts = {
        span["text"]
        for item in evidence.values()
        for span in item["payload"]["spans"].values()
        if isinstance(span.get("text"), str) and span["text"]
    }
    leaked_texts = sorted(text for text in source_texts if text in non_source_serialized)
    if leaked_texts:
        raise AssertionError("normative source text leaked into batch artifacts")

    write_json(overlay_path, overlay)
    write_json(ledger_path, ledger)
    write_json(attestation_path, attestations)
    merge_path.write_text(merge_text, encoding="utf-8", newline="\n")

    artifact_hashes = {
        path.name: sha256_file(path)
        for path in (overlay_path, ledger_path, attestation_path, merge_path)
    }
    if compute_bundle_hash(inventory) != bundle_hash:
        raise AssertionError("canonical bundle changed during batch generation")
    evidence_after, _ = load_evidence()
    for key, item in evidence.items():
        if evidence_after[key]["file_sha256"] != item["file_sha256"]:
            raise AssertionError(f"normative evidence changed during generation: {key}")
    validation = {
        "schema_version": "consume-api-normative-provenance-validation/1",
        "batch_id": "batch-1",
        "status": "passed_with_fail_closed_blockers",
        "checks": {
            "canonical_bundle_hash": True,
            "canonical_rubric_hash": True,
            "canonical_source_snapshot_hash": True,
            "deterministic_unscorable_total_exactly_113": True,
            "owned_slice_exactly_indices_1_through_38": True,
            "owned_slice_id_hash_recomputed": True,
            "no_duplicate_criterion_ids": True,
            "no_out_of_slice_operations": True,
            "overlay_schema_valid": True,
            "all_source_file_hashes_match_records": True,
            "all_json_pointers_resolve": True,
            "all_pointer_hashes_recompute": True,
            "all_source_and_rule_ids_bound_by_hashed_evidence": True,
            "merged_rubric_provenance_schema_valid": True,
            "merged_preflight_counts_match": True,
            "confidential_source_text_absent": True,
            "ai_review_not_marked_as_human_confirmation": True,
            "benchmark_specific_production_guard_logic_added": False,
            "repository_or_canonical_bundle_mutated": False,
        },
        "counts": {
            "base_criteria": 128,
            "base_scorable": 15,
            "base_unscorable_or_unresolved": 113,
            "slice_criteria": 38,
            "slice_first_id": owned_ids[0],
            "slice_last_id": owned_ids[-1],
            "slice_ids_sha256": owned_ids_hash,
            "classification_counts": counts_complete,
            "post_merge_scorable": 19,
            "post_merge_unscorable_or_unresolved": 109,
        },
        "blockers": [
            {
                "kind": "human_confirmation_required",
                "count": counts_complete[
                    "semantic_support_pending_human_confirmation"
                ],
                "criterion_ids": sorted(SEMANTIC_PENDING),
                "effect": "retain_unscorable",
            },
            {
                "kind": "product_decision_required",
                "count": counts_complete["product_decision_required"],
                "criterion_ids": sorted(PRODUCT_DECISIONS),
                "effect": "retain_unscorable",
            },
            {
                "kind": "structural_harness_non_product_law",
                "count": counts_complete["structural_harness_non_product_law"],
                "criterion_ids": sorted(
                    row["criterion_id"]
                    for row in ledger_rows
                    if row["classification"]
                    == "structural_harness_non_product_law"
                ),
                "effect": "retain_unscorable_or_move_to_non_product_validation",
            },
            {
                "kind": "portable_evidence_staging",
                "count": len(evidence_sources),
                "effect": (
                    "Absolute hash-pinned local evidence paths must remain available "
                    "or be securely staged byte-identically before merge."
                ),
            },
        ],
        "artifact_hashes": artifact_hashes,
        "production_guard_files_changed": [],
    }
    write_json(validation_path, validation)
    print(json.dumps(validation["counts"], indent=2))
    print(f"VALIDATION {validation['status']}")


if __name__ == "__main__":
    main()
