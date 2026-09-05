from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from docx import Document


BUNDLE = Path(
    r"C:\Users\taomar\.copilot\session-state\135cb788-7072-4c5f-84d0-7458aba79def"
    r"\files\consume-api-provenance-harness-v3.0.0"
)
OUTPUT_DIR = Path(
    r"C:\Users\taomar\.copilot\session-state\bfcad3f2-6146-4d34-ac69-467da06af678"
    r"\files"
)
RUBRIC_PATH = BUNDLE / "evaluation-rubric.json"
SOURCE_SNAPSHOT_PATH = BUNDLE / "evidence" / "source.snapshot.json"
HW_DOCUMENT_PATH = Path(
    r"C:\Users\taomar\Downloads\policy-extractor-local-oversight\repository\data"
    r"\documents\89e29071-ba86-419f-83eb-549c795db172_v1_"
    r"Workplace-Hardware-Provisioning-Policy-v3.3.docx"
)
HW_RULE_RECEIPT_PATH = Path(
    r"C:\Users\taomar\.copilot\session-state\8437f3da-491a-4139-b979-8b00996c8953"
    r"\files\runs\case-hw-policy-rule.json"
)

BUNDLE_SHA256 = "fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c"
RUBRIC_SHA256 = "6bd271a45d466ed048427a32ea2c7143bc23b3376e9ea06627f7239c481d7c58"
SOURCE_SNAPSHOT_SHA256 = (
    "01171368268bfb5c9e8bac8b8852f5bb67f6524624dd24154949978afa390c1c"
)
HW_DOCUMENT_SHA256 = (
    "458475a5e720be25498823fccd388f79747b62f90ec46b2cda525e73fbf6e934"
)
HW_RULE_RECEIPT_SHA256 = (
    "8c3c0e613e668f8644450a6e144836b93b5ea96bba55ba97c53e767ada434689"
)

ATTESTATION_NAME = "normative-provenance-batch2.source-attestations.json"
LEDGER_NAME = "normative-provenance-batch2.ledger.json"
OVERLAY_NAME = "normative-provenance-batch2.overlay.json"
VALIDATION_NAME = "normative-provenance-batch2.validation.json"
MERGE_NAME = "normative-provenance-batch2.MERGE.md"
ATTESTATION_SOURCE_ID = "normative_batch2_source_attestations"

STRUCTURAL = {
    "AIS-08:manual-2",
    "AIS-09:R3",
    "AIS-09:R4",
    "AIS-09:R5",
    "AIS-10:R1",
    "AIS-10:R3",
    "AIS-10:R4",
    "AIS-10:R9",
    "HW-01:R3",
    "HW-01:R4",
    "HW-01:R5",
    "HW-01:manual-1",
    "HW-02:R3",
    "HW-02:R4",
    "HW-02:R5",
    "HW-03:R3",
    "HW-03:R4",
    "HW-03:R5",
    "HW-04:R3",
    "HW-04:R4",
    "HW-04:R5",
    "HW-05:R3",
    "HW-05:R4",
}
PRODUCT_DECISION = {
    "AIS-10:R5",
    "AIS-10:manual-1",
}
CONTRADICTED = {
    "HW-03:manual-1",
}
SEMANTIC_PENDING = {
    "HW-01:R1",
    "HW-01:R9",
    "HW-02:R1",
    "HW-02:R9",
    "HW-02:manual-1",
    "HW-02:manual-2",
    "HW-03:R1",
    "HW-03:R9",
    "HW-04:R1",
    "HW-04:R9",
    "HW-04:manual-1",
    "HW-05:R1",
}

PROVISION_FOR = {
    "HW-01:R1": "230ef0dbd6d412b2007b01babc0a74a9",
    "HW-01:R9": "230ef0dbd6d412b2007b01babc0a74a9",
    "HW-02:R1": "ebb9290859d9fe10ab4a13e486482699",
    "HW-02:R9": "ebb9290859d9fe10ab4a13e486482699",
    "HW-02:manual-1": "ebb9290859d9fe10ab4a13e486482699",
    "HW-02:manual-2": "ebb9290859d9fe10ab4a13e486482699",
    "HW-03:R1": "81edaa293982adfdd04cb864640ba76d",
    "HW-03:R9": "81edaa293982adfdd04cb864640ba76d",
    "HW-03:manual-1": "81edaa293982adfdd04cb864640ba76d",
    "HW-04:R1": "2499ce756c30f34b1da6e16171bded61",
    "HW-04:R9": "2499ce756c30f34b1da6e16171bded61",
    "HW-04:manual-1": "2499ce756c30f34b1da6e16171bded61",
    "HW-05:R1": "22daced0bf9d5768c63eb83f1cc7df60",
}

PROVISION_SPECS = [
    {
        "source_provision_id": "230ef0dbd6d412b2007b01babc0a74a9",
        "source_snapshot_index": 48,
        "paragraph_start": 33,
        "paragraph_end": 34,
        "rule_considered_index": 6,
        "bounded_description": (
            "Standard device refresh interval, transition rule, and early-replacement boundary."
        ),
    },
    {
        "source_provision_id": "ebb9290859d9fe10ab4a13e486482699",
        "source_snapshot_index": 55,
        "paragraph_start": 49,
        "paragraph_end": 50,
        "rule_considered_index": 54,
        "bounded_description": (
            "Loss and theft reporting, security handling, external-theft documentation, "
            "and replacement prerequisites."
        ),
    },
    {
        "source_provision_id": "81edaa293982adfdd04cb864640ba76d",
        "source_snapshot_index": 81,
        "paragraph_start": 118,
        "paragraph_end": 119,
        "rule_considered_index": 24,
        "bounded_description": (
            "Personal-device restrictions, approved virtual-desktop exception, and "
            "continued organizational-device entitlement."
        ),
    },
    {
        "source_provision_id": "2499ce756c30f34b1da6e16171bded61",
        "source_snapshot_index": 80,
        "paragraph_start": 115,
        "paragraph_end": 115,
        "rule_considered_index": 7,
        "bounded_description": (
            "Short-contractor loan-stock treatment and refresh exclusion."
        ),
    },
    {
        "source_provision_id": "22daced0bf9d5768c63eb83f1cc7df60",
        "source_snapshot_index": 68,
        "paragraph_start": 83,
        "paragraph_end": 84,
        "rule_considered_index": 5,
        "bounded_description": (
            "Workplace-adjustment priority, approval basis, and overrides of ordinary "
            "financial, entitlement, and refresh limits."
        ),
    },
]

RATIONALES = {
    "AIS-08:manual-2": (
        "Whether an information request may produce a reached verdict is an API/evaluator "
        "track contract, not a rule in the employee handbook."
    ),
    "AIS-09:R3": (
        "Allowed answer-track states are evaluator contract metadata rather than product law."
    ),
    "AIS-09:R4": (
        "Internal consistency of missing-information fields is response integrity, not "
        "normative policy."
    ),
    "AIS-09:R5": (
        "Relevance/refusal handling is a harness classification concern and this question is "
        "declared relevant."
    ),
    "AIS-10:R1": (
        "An out-of-domain control with no expected policy evidence is a citation-integrity "
        "test, not a product-law criterion."
    ),
    "AIS-10:R3": (
        "Allowed response-track states for an out-of-domain control are harness behavior."
    ),
    "AIS-10:R4": (
        "Internal consistency of missing-information fields is response integrity."
    ),
    "AIS-10:R5": (
        "The normative corpus cannot decide how the API should refuse an out-of-domain "
        "question; an explicit product contract is required."
    ),
    "AIS-10:R9": (
        "An out-of-domain control with no composition authorities is a harness integrity "
        "check, not product law."
    ),
    "AIS-10:manual-1": (
        "The exact empty-response shape for an out-of-domain question requires an explicit "
        "API/product decision."
    ),
    "HW-01:R1": (
        "The identified clause directly governs device-age refresh eligibility, but the "
        "question-to-clause semantic binding still requires human confirmation."
    ),
    "HW-01:R3": (
        "Allowed answer-track states are evaluator contract metadata."
    ),
    "HW-01:R4": (
        "Missing-information field consistency is response integrity."
    ),
    "HW-01:R5": (
        "Relevance/refusal handling is harness behavior and this question is declared relevant."
    ),
    "HW-01:R9": (
        "The identified clause is the apparent primary composition authority; completeness "
        "of the authority set remains a semantic human-review decision."
    ),
    "HW-01:manual-1": (
        "Treating two unevaluated tracks as failure is evaluator coverage policy."
    ),
    "HW-02:R1": (
        "The identified clause governs the stated theft scenario, but semantic confirmation "
        "must be supplied by a human reviewer."
    ),
    "HW-02:R3": (
        "Allowed answer-track states are evaluator contract metadata."
    ),
    "HW-02:R4": (
        "Missing-information field consistency is response integrity."
    ),
    "HW-02:R5": (
        "Relevance/refusal handling is harness behavior and this question is declared relevant."
    ),
    "HW-02:R9": (
        "The identified clause is the apparent primary composition authority; completeness "
        "of the authority set remains semantic."
    ),
    "HW-02:manual-1": (
        "The identified clause makes reporting and notification prerequisites, but AI review "
        "is not human semantic confirmation."
    ),
    "HW-02:manual-2": (
        "The identified clause states pre-release safeguards and documentation, but a human "
        "must confirm the rubric outcome mapping."
    ),
    "HW-03:R1": (
        "The identified clause governs personal-device use for organizational data, but the "
        "question-to-clause semantic binding remains pending human confirmation."
    ),
    "HW-03:R3": (
        "Allowed answer-track states are evaluator contract metadata."
    ),
    "HW-03:R4": (
        "Missing-information field consistency is response integrity."
    ),
    "HW-03:R5": (
        "Relevance/refusal handling is harness behavior and this question is declared relevant."
    ),
    "HW-03:R9": (
        "The identified clause is the apparent primary composition authority; completeness "
        "of the authority set remains semantic."
    ),
    "HW-03:manual-1": (
        "The source permits a constrained approved-virtual-desktop route, so rejecting every "
        "permission-granting answer is overbroad."
    ),
    "HW-04:R1": (
        "The identified clause directly governs shorter contractor engagements, but semantic "
        "confirmation must be supplied by a human reviewer."
    ),
    "HW-04:R3": (
        "Allowed answer-track states are evaluator contract metadata."
    ),
    "HW-04:R4": (
        "Missing-information field consistency is response integrity."
    ),
    "HW-04:R5": (
        "Relevance/refusal handling is harness behavior and this question is declared relevant."
    ),
    "HW-04:R9": (
        "The identified clause is the apparent primary composition authority; completeness "
        "of the authority set remains semantic."
    ),
    "HW-04:manual-1": (
        "The identified clause is the direct short-engagement authority, but making its "
        "citation mandatory for every answered verdict requires human semantic confirmation."
    ),
    "HW-05:R1": (
        "The identified clause governs adjustment priority, approvals, and overrides, but "
        "the semantic binding still requires human confirmation."
    ),
    "HW-05:R3": (
        "Allowed answer-track states are evaluator contract metadata."
    ),
    "HW-05:R4": (
        "Missing-information field consistency is response integrity."
    ),
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
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
        json.dumps(value, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def resolve_pointer(document: Any, pointer: str) -> Any:
    current = document
    if pointer == "":
        return current
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def require_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"hash mismatch for {path}: expected {expected}, got {actual}")


def verify_bundle_payload() -> None:
    inventory = load_json(BUNDLE / "FILE_INVENTORY.json")
    records = []
    total_bytes = 0
    for item in inventory["files"]:
        path = BUNDLE / Path(item["path"].replace("/", "\\"))
        require_hash(path, item["sha256"])
        if item["canonical_payload"]:
            records.append(f"{item['path']}\0{item['sha256']}\n")
            total_bytes += item["bytes"]
    digest = sha256_bytes("".join(sorted(records)).encode("utf-8"))
    if digest != BUNDLE_SHA256:
        raise RuntimeError(f"bundle payload mismatch: {digest}")
    if len(records) != 35 or total_bytes != 1126517:
        raise RuntimeError("bundle payload count or byte total differs")


def canonical_findings(
    rubric: dict[str, Any], rubric_path: Path
) -> tuple[list[tuple[str, dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    sys.path.insert(0, str(BUNDLE))
    from rubric_provenance import validate_rubric_provenance

    preflight = validate_rubric_provenance(rubric, rubric_path)
    findings = {item["criterion_id"] for item in preflight["rubric_findings"]}
    flattened = []
    for question in rubric["questions"]:
        for criterion in question["criteria"]:
            if criterion["criterion_id"] in findings:
                flattened.append((criterion["criterion_id"], question, criterion))
    flattened.sort(key=lambda item: item[0])
    if len(flattened) != 113:
        raise RuntimeError(f"expected 113 findings, got {len(flattened)}")
    return flattened, preflight


def build_attestations() -> dict[str, Any]:
    source_snapshot = load_json(SOURCE_SNAPSHOT_PATH)
    rule_receipt = load_json(HW_RULE_RECEIPT_PATH)
    document = Document(HW_DOCUMENT_PATH)
    provisions = []
    for spec in PROVISION_SPECS:
        source_pointer = f"/provisions/{spec['source_snapshot_index']}"
        source_identity = resolve_pointer(source_snapshot, source_pointer)
        if source_identity["provision_key"] != spec["source_provision_id"]:
            raise RuntimeError(f"source snapshot index drift for {source_pointer}")
        body = "\n".join(
            document.paragraphs[index].text
            for index in range(
                spec["paragraph_start"], spec["paragraph_end"] + 1
            )
        )
        if not body.strip():
            raise RuntimeError(f"empty body range for {spec['source_provision_id']}")
        rule_pointer = f"/considered/{spec['rule_considered_index']}"
        rule_metadata = resolve_pointer(rule_receipt, rule_pointer)
        if rule_metadata["provision_key"] != spec["source_provision_id"]:
            raise RuntimeError(f"rule receipt index drift for {rule_pointer}")
        rule_selection = rule_metadata.get("rule_selection") or {}
        provisions.append(
            {
                "source_provision_id": spec["source_provision_id"],
                "project": "hw-policy",
                "heading_path": source_identity["heading_path_json"],
                "bounded_description": spec["bounded_description"],
                "source_snapshot_evidence": {
                    "path": str(SOURCE_SNAPSHOT_PATH),
                    "file_sha256": SOURCE_SNAPSHOT_SHA256,
                    "pointer": source_pointer,
                    "pointer_sha256": sha256_bytes(
                        canonical_json_bytes(source_identity)
                    ),
                },
                "normative_body_evidence": {
                    "path": str(HW_DOCUMENT_PATH),
                    "file_sha256": HW_DOCUMENT_SHA256,
                    "locator": {
                        "kind": "docx_paragraph_range",
                        "paragraph_index_base": 0,
                        "start_inclusive": spec["paragraph_start"],
                        "end_inclusive": spec["paragraph_end"],
                    },
                    "body_hash_canonicalization": (
                        "exact python-docx paragraph.text joined with LF; UTF-8 SHA-256"
                    ),
                    "body_sha256": sha256_bytes(body.encode("utf-8")),
                    "body_utf8_bytes": len(body.encode("utf-8")),
                    "body_text_copied": False,
                },
                "rule_metadata_evidence": {
                    "path": str(HW_RULE_RECEIPT_PATH),
                    "file_sha256": HW_RULE_RECEIPT_SHA256,
                    "pointer": rule_pointer,
                    "pointer_sha256": sha256_bytes(
                        canonical_json_bytes(rule_metadata)
                    ),
                    "rule_count": rule_metadata["rules"],
                    "selected_rule_ids": rule_selection.get(
                        "selected_rule_ids", []
                    ),
                    "rule_bodies_available_at_pointer": False,
                    "scope": "identity_and_count_only",
                },
            }
        )
    return {
        "schema_version": "consume-api-normative-source-hash-attestations/1",
        "quote_free": True,
        "authoritative_bundle_sha256": BUNDLE_SHA256,
        "source_documents": [
            {
                "id": "hw_policy_v3_3_local_document",
                "path": str(HW_DOCUMENT_PATH),
                "sha256": HW_DOCUMENT_SHA256,
                "bytes": HW_DOCUMENT_PATH.stat().st_size,
                "read_only": True,
            }
        ],
        "rule_artifacts": [
            {
                "id": "hw_policy_frozen_rule_receipt",
                "path": str(HW_RULE_RECEIPT_PATH),
                "sha256": HW_RULE_RECEIPT_SHA256,
                "bytes": HW_RULE_RECEIPT_PATH.stat().st_size,
                "read_only": True,
                "limitation": (
                    "The receipt exposes provision-level rule counts and selected IDs only "
                    "for retained provisions; it is not a complete rule-body export."
                ),
            }
        ],
        "provisions": provisions,
    }


def classification_for(criterion_id: str) -> str:
    if criterion_id in STRUCTURAL:
        return "structural_harness_not_product_law"
    if criterion_id in PRODUCT_DECISION:
        return "product_decision_required"
    if criterion_id in CONTRADICTED:
        return "unsupported_or_contradicted_rubric"
    if criterion_id in SEMANTIC_PENDING:
        return "semantic_support_pending_human_confirmation"
    raise KeyError(criterion_id)


def recommended_action(classification: str) -> str:
    return {
        "structural_harness_not_product_law": (
            "Keep fail-closed in the product-law rubric and route to a separate "
            "contract/integrity validation layer."
        ),
        "product_decision_required": (
            "Keep fail-closed until an authoritative API/product contract defines "
            "out-of-domain behavior."
        ),
        "unsupported_or_contradicted_rubric": (
            "Keep fail-closed; a human reviewer must rewrite or withdraw the overbroad "
            "criterion before any unsupported state is confirmed."
        ),
        "semantic_support_pending_human_confirmation": (
            "Attach the hash-bound source-body provenance as unresolved semantics; a human "
            "reviewer must confirm support before scorable status."
        ),
    }[classification]


def candidate_fields(
    criterion: dict[str, Any],
    classification: str,
    attestation_index: dict[str, int],
    attestations: dict[str, Any],
) -> dict[str, Any] | None:
    if classification not in {
        "semantic_support_pending_human_confirmation",
        "unsupported_or_contradicted_rubric",
    }:
        return None
    provision_id = PROVISION_FOR[criterion["criterion_id"]]
    pointer = f"/provisions/{attestation_index[provision_id]}"
    pointed = resolve_pointer(attestations, pointer)
    refs = copy.deepcopy(criterion["evidence_refs"])
    refs.append(
        {
            "role": "batch2_normative_body_attestation",
            "source_id": ATTESTATION_SOURCE_ID,
            "pointer": pointer,
            "pointer_sha256": sha256_bytes(canonical_json_bytes(pointed)),
        }
    )
    return {
        "criterion_provenance": "rule_body",
        "provenance_kind": "normative_source_body",
        "source_provision_ids": [provision_id],
        "source_rule_ids": [],
        "evidence_refs": refs,
        "validation_state": "unresolved_semantics",
        "corpus_support": {
            "checked": True,
            "supporting_rule_count": 0,
            "supporting_provision_count": 1,
            "method": (
                "hash_attested_local_normative_body_ai_review_pending_explicit_"
                "human_confirmation"
            ),
            "semantic_support": "not_applicable",
        },
    }


def build_records(
    selection: list[tuple[str, dict[str, Any], dict[str, Any]]],
    attestations: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attestation_index = {
        item["source_provision_id"]: index
        for index, item in enumerate(attestations["provisions"])
    }
    ledger_records = []
    overlay_updates = []
    for absolute_index, (criterion_id, question, criterion) in enumerate(
        selection, 39
    ):
        classification = classification_for(criterion_id)
        provision_id = PROVISION_FOR.get(criterion_id)
        evidence = None
        if provision_id is not None:
            pointer = f"/provisions/{attestation_index[provision_id]}"
            evidence = {
                "source_id": ATTESTATION_SOURCE_ID,
                "pointer": pointer,
                "pointer_sha256": sha256_bytes(
                    canonical_json_bytes(resolve_pointer(attestations, pointer))
                ),
                "source_provision_ids": [provision_id],
                "source_rule_ids": [],
            }
        candidate = candidate_fields(
            criterion, classification, attestation_index, attestations
        )
        blocker = {
            "structural_harness_not_product_law": (
                "Wrong scoring boundary; normative source cannot support a response-contract "
                "or evaluator-integrity rule."
            ),
            "product_decision_required": (
                "No authoritative product contract defines the requested out-of-domain "
                "response behavior."
            ),
            "unsupported_or_contradicted_rubric": (
                "Source permits a constrained path that the blanket criterion rejects; "
                "human reconciliation is required."
            ),
            "semantic_support_pending_human_confirmation": (
                "AI source review is not human confirmation under the canonical provenance "
                "contract."
            ),
        }[classification]
        record = {
            "absolute_unscorable_index": absolute_index,
            "criterion_id": criterion_id,
            "question_id": question["id"],
            "rubric_id": question["rubric_id"],
            "project": question["project"],
            "classification": classification,
            "scorable_after_batch": False,
            "current_state": {
                "criterion_provenance": criterion["criterion_provenance"],
                "provenance_kind": criterion["provenance_kind"],
                "validation_state": criterion["validation_state"],
            },
            "normative_evidence": evidence,
            "bounded_rationale": RATIONALES[criterion_id],
            "blocker": blocker,
            "recommended_action": recommended_action(classification),
            "candidate_rubric_fields": candidate,
            "human_confirmation_recorded": False,
        }
        ledger_records.append(record)
        overlay_updates.append(
            {
                "criterion_id": criterion_id,
                "question_id": question["id"],
                "classification": classification,
                "scorable": False,
                "normative_evidence": evidence,
                "candidate_rubric_fields": candidate,
                "recommended_action": record["recommended_action"],
            }
        )
    return ledger_records, overlay_updates


def apply_candidates_and_validate(
    rubric: dict[str, Any],
    overlay_updates: list[dict[str, Any]],
    attestation_path: Path,
    attestation_sha256: str,
) -> dict[str, Any]:
    merged = copy.deepcopy(rubric)
    merged["evidence_sources"].append(
        {
            "id": ATTESTATION_SOURCE_ID,
            "path": str(attestation_path),
            "sha256": attestation_sha256,
            "type": "json",
        }
    )
    updates = {
        item["criterion_id"]: item["candidate_rubric_fields"]
        for item in overlay_updates
        if item["candidate_rubric_fields"] is not None
    }
    for question in merged["questions"]:
        for criterion in question["criteria"]:
            candidate = updates.get(criterion["criterion_id"])
            if candidate:
                criterion.update(copy.deepcopy(candidate))
    sys.path.insert(0, str(BUNDLE))
    from rubric_provenance import validate_rubric_provenance

    return validate_rubric_provenance(merged, RUBRIC_PATH)


def validate_generated(
    selected_ids: list[str],
    attestations: dict[str, Any],
    ledger: dict[str, Any],
    overlay: dict[str, Any],
) -> None:
    required_overlay = {
        "schema_version",
        "authoritative_bundle",
        "selection",
        "evidence_sources",
        "classification_counts",
        "criterion_updates",
        "invariants",
    }
    required_ledger = {
        "schema_version",
        "selection",
        "classification_counts",
        "criteria",
    }
    if set(overlay) != required_overlay or set(ledger) != required_ledger:
        raise RuntimeError("generated artifact schema keys differ")
    overlay_ids = [item["criterion_id"] for item in overlay["criterion_updates"]]
    ledger_ids = [item["criterion_id"] for item in ledger["criteria"]]
    if overlay_ids != selected_ids or ledger_ids != selected_ids:
        raise RuntimeError("generated artifact slice membership differs")
    if len(set(overlay_ids)) != 38:
        raise RuntimeError("duplicate criterion IDs")
    valid_classes = {
        "mechanically_source_supported",
        "semantic_support_pending_human_confirmation",
        "unsupported_or_contradicted_rubric",
        "structural_harness_not_product_law",
        "unavailable_evidence",
        "product_decision_required",
    }
    for item in ledger["criteria"]:
        if item["classification"] not in valid_classes:
            raise RuntimeError("unknown classification")
        if item["scorable_after_batch"] is not False:
            raise RuntimeError("batch made a criterion scorable")
        if item["human_confirmation_recorded"] is not False:
            raise RuntimeError("AI review was recorded as human confirmation")
        evidence = item["normative_evidence"]
        if evidence is not None:
            pointed = resolve_pointer(attestations, evidence["pointer"])
            actual = sha256_bytes(canonical_json_bytes(pointed))
            if actual != evidence["pointer_sha256"]:
                raise RuntimeError(f"attestation pointer mismatch for {item['criterion_id']}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    verify_bundle_payload()
    require_hash(RUBRIC_PATH, RUBRIC_SHA256)
    require_hash(SOURCE_SNAPSHOT_PATH, SOURCE_SNAPSHOT_SHA256)
    require_hash(HW_DOCUMENT_PATH, HW_DOCUMENT_SHA256)
    require_hash(HW_RULE_RECEIPT_PATH, HW_RULE_RECEIPT_SHA256)
    source_hashes_before = {
        str(path): sha256_file(path)
        for path in (
            RUBRIC_PATH,
            SOURCE_SNAPSHOT_PATH,
            HW_DOCUMENT_PATH,
            HW_RULE_RECEIPT_PATH,
        )
    }

    rubric = load_json(RUBRIC_PATH)
    all_findings, canonical_preflight = canonical_findings(rubric, RUBRIC_PATH)
    selection = all_findings[39:77]
    selected_ids = [item[0] for item in selection]
    if len(selected_ids) != 38:
        raise RuntimeError("slice must contain exactly 38 criteria")

    partitions = STRUCTURAL | PRODUCT_DECISION | CONTRADICTED | SEMANTIC_PENDING
    if partitions != set(selected_ids):
        missing = sorted(set(selected_ids) - partitions)
        extra = sorted(partitions - set(selected_ids))
        raise RuntimeError(f"classification partition mismatch: missing={missing}, extra={extra}")
    if sum(
        len(group)
        for group in (STRUCTURAL, PRODUCT_DECISION, CONTRADICTED, SEMANTIC_PENDING)
    ) != 38:
        raise RuntimeError("classification groups overlap")
    if set(PROVISION_FOR) != SEMANTIC_PENDING | CONTRADICTED:
        raise RuntimeError("provision mapping coverage differs")
    if set(RATIONALES) != set(selected_ids):
        raise RuntimeError("rationale coverage differs")

    attestations = build_attestations()
    attestation_path = OUTPUT_DIR / ATTESTATION_NAME
    write_json(attestation_path, attestations)
    attestation_sha256 = sha256_file(attestation_path)

    ledger_records, overlay_updates = build_records(selection, attestations)
    counts = dict(sorted(Counter(
        item["classification"] for item in ledger_records
    ).items()))
    selected_ids_sha256 = sha256_bytes(canonical_json_bytes(selected_ids))
    selection_metadata = {
        "filter": "canonical provenance preflight rubric_findings",
        "sort": "stable criterion_id ascending",
        "total_unscorable_or_unresolved": 113,
        "slice_start_index_zero_based": 39,
        "slice_end_index_zero_based_inclusive": 76,
        "selected_count": 38,
        "first_criterion_id": selected_ids[0],
        "last_criterion_id": selected_ids[-1],
        "selected_ids_sha256": selected_ids_sha256,
    }
    ledger = {
        "schema_version": "consume-api-normative-provenance-ledger/1",
        "selection": selection_metadata,
        "classification_counts": counts,
        "criteria": ledger_records,
    }
    overlay = {
        "schema_version": "consume-api-normative-provenance-overlay/1",
        "authoritative_bundle": {
            "path": str(BUNDLE),
            "canonical_payload_sha256": BUNDLE_SHA256,
            "rubric_path": str(RUBRIC_PATH),
            "rubric_sha256": RUBRIC_SHA256,
        },
        "selection": selection_metadata,
        "evidence_sources": [
            {
                "id": ATTESTATION_SOURCE_ID,
                "path": ATTESTATION_NAME,
                "sha256": attestation_sha256,
                "type": "json",
            }
        ],
        "classification_counts": counts,
        "criterion_updates": overlay_updates,
        "invariants": {
            "human_confirmation_recorded": False,
            "criteria_made_scorable": 0,
            "outside_slice_updates": 0,
            "production_guard_modified": False,
        },
    }
    validate_generated(selected_ids, attestations, ledger, overlay)

    ledger_path = OUTPUT_DIR / LEDGER_NAME
    overlay_path = OUTPUT_DIR / OVERLAY_NAME
    write_json(ledger_path, ledger)
    write_json(overlay_path, overlay)

    candidate_preflight = apply_candidates_and_validate(
        rubric, overlay_updates, attestation_path, attestation_sha256
    )
    candidate_dispositions = Counter(
        item["disposition"] for item in candidate_preflight["rubric_findings"]
    )
    if candidate_preflight["criterion_count"] != 128:
        raise RuntimeError("candidate overlay changed criterion count")
    if len(candidate_preflight["rubric_findings"]) != 113:
        raise RuntimeError("candidate overlay changed finding count")
    if candidate_dispositions["unresolved"] != 13:
        raise RuntimeError("candidate overlay unresolved count differs")

    merge_text = f"""# Normative Provenance Batch 2 Merge Instructions

## Scope

- Authoritative bundle payload SHA-256: `{BUNDLE_SHA256}`
- Deterministic finding population: `113`
- Owned zero-based slice: `39..76` inclusive
- Owned criteria: `38`
- First/last IDs: `{selected_ids[0]}` / `{selected_ids[-1]}`
- Selected-ID-list SHA-256: `{selected_ids_sha256}`

Do not apply this overlay to any criterion outside the owned ID list. The canonical
bundle, frozen source snapshot, local source document, frozen rule receipt, repository,
live services, and production guard were not modified.

## Merge

1. Verify the hashes in `{ATTESTATION_NAME}` against the read-only local artifacts.
2. Copy `{ATTESTATION_NAME}` into the successor rubric evidence directory and register
   it as JSON evidence source `{ATTESTATION_SOURCE_ID}` using SHA-256
   `{attestation_sha256}`.
3. Read `{OVERLAY_NAME}` and match updates by exact `criterion_id`; never merge by
   position alone.
4. For the 13 records with `candidate_rubric_fields`, apply those fields only as
   `unresolved_semantics`. This adds source-body identities and hash-bound pointers but
   does not make any criterion scorable.
5. Keep the 23 structural/harness records outside product-law failure attribution.
   They may be retained fail-closed for auditability or migrated to a separate response
   contract/integrity suite in a new rubric version.
6. Keep the 2 product-decision records fail-closed until an authoritative API contract
   defines out-of-domain behavior.
7. Keep `HW-03:manual-1` fail-closed. The current blanket expectation conflicts with
   the source's constrained approved-channel allowance; a human reviewer must rewrite
   or withdraw it.
8. Human review must be recorded in a separate hash-bound artifact. This AI-authored
   ledger is not human confirmation. Only after that review may the canonical
   `human_confirmation` structure and a scorable validation state be added.
9. Run canonical provenance validation after merge. Expected pre-human-review result:
   128 criteria, 113 findings, 13 unresolved, 100 unscorable, and no increase in
   scorable criteria.

## Rule evidence limitation

The frozen rule receipt exposes provision-level rule counts for all five HW clauses
and selected rule IDs for only one retained clause. It does not expose complete
rule-body evidence for this slice. The candidate provenance therefore uses
`normative_source_body`, not `normative_rule_body`, and records no source rule IDs.
"""
    merge_path = OUTPUT_DIR / MERGE_NAME
    merge_path.write_text(merge_text, encoding="utf-8", newline="\n")

    source_hashes_after = {
        path: sha256_file(Path(path)) for path in source_hashes_before
    }
    if source_hashes_after != source_hashes_before:
        raise RuntimeError("read-only source artifact changed during generation")

    artifact_hashes = {
        name: sha256_file(OUTPUT_DIR / name)
        for name in (ATTESTATION_NAME, LEDGER_NAME, OVERLAY_NAME, MERGE_NAME)
    }
    validation = {
        "schema_version": "consume-api-normative-provenance-validation/1",
        "status": "passed_with_human_and_rule_body_blockers",
        "authoritative_inputs": {
            "bundle_payload_sha256": BUNDLE_SHA256,
            "rubric_sha256": RUBRIC_SHA256,
            "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
            "hw_document_sha256": HW_DOCUMENT_SHA256,
            "hw_rule_receipt_sha256": HW_RULE_RECEIPT_SHA256,
        },
        "selection_validation": {
            "canonical_criterion_count": canonical_preflight["criterion_count"],
            "canonical_finding_count": len(canonical_preflight["rubric_findings"]),
            "expected_finding_count": 113,
            "selected_count": len(selected_ids),
            "selected_ids_sha256": selected_ids_sha256,
            "first_criterion_id": selected_ids[0],
            "last_criterion_id": selected_ids[-1],
            "duplicate_ids": 0,
            "outside_slice_updates": 0,
            "passed": True,
        },
        "pointer_and_hash_validation": {
            "attested_provisions": len(attestations["provisions"]),
            "source_snapshot_pointers_verified": len(attestations["provisions"]),
            "normative_body_hashes_verified": len(attestations["provisions"]),
            "rule_metadata_pointers_verified": len(attestations["provisions"]),
            "overlay_attestation_pointers_verified": len(PROVISION_FOR),
            "passed": True,
        },
        "schema_validation": {
            "overlay_schema": "passed",
            "ledger_schema": "passed",
            "attestation_schema": "passed",
            "canonical_rubric_schema_after_candidate_merge": "passed",
            "candidate_criterion_count": candidate_preflight["criterion_count"],
            "candidate_finding_count": len(candidate_preflight["rubric_findings"]),
            "candidate_dispositions": dict(sorted(candidate_dispositions.items())),
        },
        "classification_counts": counts,
        "safety_validation": {
            "criteria_made_scorable": 0,
            "human_confirmation_claims": 0,
            "benchmark_specific_production_guard_logic_added": False,
            "canonical_bundle_modified": False,
            "repository_modified": False,
            "source_artifacts_modified": False,
            "live_network_api_model_database_search_azure_operations": 0,
        },
        "source_nonmutation": {
            "before": source_hashes_before,
            "after": source_hashes_after,
            "passed": True,
        },
        "artifact_hashes": artifact_hashes,
        "blockers": [
            {
                "kind": "human_confirmation_required",
                "criterion_count": len(SEMANTIC_PENDING),
                "detail": (
                    "Source bodies are hash-bound and semantically reviewed, but AI review "
                    "is not human confirmation."
                ),
            },
            {
                "kind": "rubric_reconciliation_required",
                "criterion_count": len(CONTRADICTED),
                "detail": (
                    "One blanket BYOD expectation conflicts with a constrained allowance."
                ),
            },
            {
                "kind": "product_contract_required",
                "criterion_count": len(PRODUCT_DECISION),
                "detail": (
                    "Out-of-domain refusal and empty-response shape are not settled by "
                    "normative policy."
                ),
            },
            {
                "kind": "complete_rule_body_export_unavailable",
                "criterion_count": len(PROVISION_SPECS),
                "detail": (
                    "Frozen rule metadata is incomplete for semantic rule-body validation; "
                    "source-body provenance is used instead."
                ),
            },
        ],
    }
    write_json(OUTPUT_DIR / VALIDATION_NAME, validation)

    print(json.dumps(
        {
            "status": validation["status"],
            "selected": len(selected_ids),
            "classification_counts": counts,
            "candidate_dispositions": dict(sorted(candidate_dispositions.items())),
            "artifact_hashes": {
                **artifact_hashes,
                VALIDATION_NAME: sha256_file(OUTPUT_DIR / VALIDATION_NAME),
            },
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
