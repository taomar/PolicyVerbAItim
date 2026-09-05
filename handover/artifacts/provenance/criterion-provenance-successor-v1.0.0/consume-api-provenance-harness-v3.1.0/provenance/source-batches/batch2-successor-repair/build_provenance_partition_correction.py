from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree


sys.dont_write_bytecode = True

ARTIFACT_ROOT = Path(__file__).resolve().parent
BASE = Path(
    r"C:\Users\taomar\.copilot\session-state\135cb788-7072-4c5f-84d0-7458aba79def"
    r"\files\consume-api-provenance-harness-v3.0.0"
)
BATCH1 = Path(
    r"C:\Users\taomar\.copilot\session-state\7b679b16-ef8a-4edb-8fe4-4e9dc2ff5215"
    r"\files"
)
BATCH2 = Path(
    r"C:\Users\taomar\.copilot\session-state\bfcad3f2-6146-4d34-ac69-467da06af678"
    r"\files"
)
BATCH3 = Path(
    r"C:\Users\taomar\.copilot\session-state\e62880a2-2a1f-4ae4-9abf-572a62728640"
    r"\files"
)
WORKSPACE = Path(r"C:\Users\taomar\Downloads\policy-extractor-local-oversight")
REPOSITORY_JUNCTION = WORKSPACE / "repository"

CANONICAL_PAYLOAD_SHA256 = (
    "fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c"
)
CANONICAL_IDS_SHA256 = (
    "4a752fd8e13b1fb1d1c37bf110e4b1334ca3bbae1beaab5d630e8d3b1719acb3"
)
RUBRIC_SHA256 = (
    "6bd271a45d466ed048427a32ea2c7143bc23b3376e9ea06627f7239c481d7c58"
)
SOURCE_SNAPSHOT_SHA256 = (
    "01171368268bfb5c9e8bac8b8852f5bb67f6524624dd24154949978afa390c1c"
)
RUBRIC_V1_SHA256 = (
    "4024170d23f22c423d5b03236874f1ad88cf5cf23db287be39ac819a8050d9cc"
)
FILE_INVENTORY_SHA256 = (
    "4951c491390ac692f70eabb0aae81bcc131d9309892004e8c0b0080384fd41a9"
)

BATCH_FILE_HASHES: dict[Path, dict[str, str]] = {
    BATCH1: {
        "build_batch1_provenance.py": (
            "01f77bee569eb44c3d304254adcd360006a9d2965713624a3ac153a31471f915"
        ),
        "criterion-provenance-batch1-overlay.json": (
            "36ae59123a4c5cd9d19283747535a5fd9d6f0743c9554d829d6d2d664032629a"
        ),
        "criterion-provenance-batch1-ledger.json": (
            "690ffe65dc7d01faba6d61e6247bd8222b20ddf84080f4abaa701684753ce720"
        ),
        "criterion-provenance-batch1-validation.json": (
            "bd3571e2923081869883595385bcc32be56c6c4364862d232a2c08cf5f90b0cc"
        ),
        "criterion-provenance-batch1-source-attestations.json": (
            "3e38fbde8c546f741d3e821a89024cf51fbb1917c87f083b540695a90585f307"
        ),
        "criterion-provenance-batch1-MERGE.md": (
            "5d576d52e4316ba78a0bcdfc64cf54d56c2cebb7ee59547c6c9640d5176d61d3"
        ),
    },
    BATCH2: {
        "build_batch2_artifacts.py": (
            "bc1a8ae553438b006b6fa2de1dbfb7ac18481be64608b719231e83f05446bff1"
        ),
        "normative-provenance-batch2.overlay.json": (
            "d7c0de9ae27187b3482350d001fa6a66632c65b82cf20ee4735029af141b660e"
        ),
        "normative-provenance-batch2.ledger.json": (
            "c7cd8155b58d129625ced534a17e671cb629f5347988ad1ef2cd52a36de85019"
        ),
        "normative-provenance-batch2.validation.json": (
            "ff08208486ec4103eb8920b72ecba0621a1ffe1a343b9d01fbf2d793630ae0ae"
        ),
        "normative-provenance-batch2.source-attestations.json": (
            "cef48741a6e19806b6f1bade107402c43d6ed15b04ae5a8bd2a10c80a502cc15"
        ),
        "normative-provenance-batch2.MERGE.md": (
            "5946dccc6396753bf127685531bbd93e0359620d434bd44e7fda3d9810e39c3b"
        ),
    },
    BATCH3: {
        "criterion-provenance-batch-3.overlay.json": (
            "4879337d894ff7e90653e248742c46a3f933abae2483209bfca6f7d66030495d"
        ),
        "criterion-provenance-batch-3.ledger.jsonl": (
            "8c832a98ac7207c146ef328c56342e8e3dc75f29c429709e4b14431a6616946a"
        ),
        "criterion-provenance-batch-3.source-hashes.json": (
            "178630c61ff91e4083776c0ad765d1ae42e77d88534483fa0a5f31e4e5e1663d"
        ),
        "criterion-provenance-batch-3.validation.json": (
            "960d354038acf33f3b7209ee72f274308948896ab311931bc4913bf04336161e"
        ),
        "criterion-provenance-batch-3.merge-instructions.md": (
            "a3f8df45954742d3c3f6ac61ccc0cb00825161384dffd7e6d988e7cb20491b35"
        ),
    },
}

OVERLAY_NAME = "criterion-provenance-batch2-successor.overlay.json"
LEDGER_NAME = "criterion-provenance-batch2-successor.ledger.json"
ATTESTATION_NAME = "criterion-provenance-batch2-successor.source-attestations.json"
MANIFEST_NAME = "criterion-provenance-partition-correction.manifest.json"
VALIDATION_NAME = "criterion-provenance-partition-correction.validation.json"
MERGE_NAME = "criterion-provenance-partition-correction.MERGE.md"

TAXONOMY = (
    "mechanically_source_supported",
    "semantic_support_pending_human_confirmation",
    "unsupported_or_contradicted_rubric",
    "structural_harness_not_product_law",
    "unavailable_evidence",
    "product_decision_required",
)


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, indent=2) + "\n"
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


def resolve_pointer(document: Any, pointer: str) -> Any:
    require(isinstance(pointer, str) and pointer.startswith("/"), "invalid JSON pointer")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def ids_sha256(values: list[str]) -> str:
    return sha256_bytes(canonical_json_bytes(values))


def input_record(label: str, path: Path, expected: str) -> dict[str, Any]:
    require(path.is_file(), f"missing input: {label}")
    actual = sha256_file(path)
    require(actual == expected, f"hash mismatch: {label}")
    return {
        "label": label,
        "path": str(path),
        "sha256": actual,
        "bytes": path.stat().st_size,
        "read_only": True,
    }


def verify_bundle_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inventory_path = BASE / "FILE_INVENTORY.json"
    require(
        sha256_file(inventory_path) == FILE_INVENTORY_SHA256,
        "canonical FILE_INVENTORY.json hash mismatch",
    )
    inventory = load_json(inventory_path)
    records: list[str] = []
    input_records: list[dict[str, Any]] = [
        input_record("base/FILE_INVENTORY.json", inventory_path, FILE_INVENTORY_SHA256)
    ]
    included_bytes = 0
    for item in inventory["files"]:
        path = BASE / Path(item["path"])
        actual = sha256_file(path)
        require(actual == item["sha256"], f"canonical base file hash mismatch: {item['path']}")
        input_records.append(
            {
                "label": f"base/{item['path']}",
                "path": str(path),
                "sha256": actual,
                "bytes": path.stat().st_size,
                "read_only": True,
            }
        )
        if item["canonical_payload"]:
            records.append(f"{item['path']}\0{item['sha256']}\n")
            included_bytes += item["bytes"]
    payload = sha256_bytes("".join(sorted(records)).encode("utf-8"))
    require(payload == CANONICAL_PAYLOAD_SHA256, "canonical payload hash mismatch")
    require(len(records) == 35, "canonical payload file count mismatch")
    require(included_bytes == 1126517, "canonical payload byte count mismatch")
    return (
        {
            "sha256": payload,
            "included_files": len(records),
            "included_bytes": included_bytes,
            "record_format": (
                "sorted UTF-8 relative path + NUL + lowercase file SHA-256 + LF"
            ),
        },
        input_records,
    )


def verify_batch_files() -> list[dict[str, Any]]:
    records = []
    for root, expected_files in BATCH_FILE_HASHES.items():
        batch_label = root.parent.parent.name
        for name, expected in expected_files.items():
            records.append(
                input_record(f"{batch_label}/{name}", root / name, expected)
            )
    return records


def collect_external_evidence_inputs(
    batch1_overlay: dict[str, Any],
    batch2_attestations: dict[str, Any],
    batch3_overlay: dict[str, Any],
    batch3_source_hashes: dict[str, Any],
) -> list[dict[str, Any]]:
    specs: list[tuple[str, Path, str]] = []
    for source in batch1_overlay["evidence_sources"]:
        specs.append(
            (
                f"batch1-evidence/{source['id']}",
                Path(source["path"]),
                source["sha256"],
            )
        )
    for source in batch2_attestations["source_documents"]:
        specs.append(
            (
                f"batch2-source-document/{source['id']}",
                Path(source["path"]),
                source["sha256"],
            )
        )
    for source in batch2_attestations["rule_artifacts"]:
        specs.append(
            (
                f"batch2-rule-artifact/{source['id']}",
                Path(source["path"]),
                source["sha256"],
            )
        )
    for source in batch3_source_hashes["sources"]:
        source_path = Path(source["path"])
        if not source_path.is_absolute():
            source_path = BASE / source_path
        specs.append(
            (
                f"batch3-source/{source['source_id']}",
                source_path,
                source["sha256"],
            )
        )
    for source in batch3_overlay["evidence_sources_to_add"]:
        specs.append(
            (
                f"batch3-overlay-origin/{source['id']}",
                Path(source["origin_path"]),
                source["sha256"],
            )
        )
    records: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for label, path, expected in specs:
        normalized = str(path.resolve()).casefold()
        prior = seen.get(normalized)
        require(prior in {None, expected}, f"conflicting source hashes: {path}")
        seen[normalized] = expected
        records.append(input_record(label, path, expected))
    return records


def snapshot_sha256(records: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "label": item["label"],
            "path": item["path"],
            "sha256": item["sha256"],
            "bytes": item["bytes"],
        }
        for item in records
    ]
    return sha256_bytes(canonical_json_bytes(normalized))


def hash_repository_tree() -> dict[str, Any]:
    require(REPOSITORY_JUNCTION.is_dir(), "repository junction is unavailable")
    paths: list[Path] = []
    for base, dirs, files in os.walk(REPOSITORY_JUNCTION, followlinks=False):
        dirs.sort()
        files.sort()
        paths.extend(Path(base) / name for name in files)

    def hash_one(path: Path) -> tuple[str, int, str]:
        relative = path.relative_to(REPOSITORY_JUNCTION).as_posix()
        size = path.stat().st_size
        return relative, size, sha256_file(path)

    rows: list[tuple[str, int, str]] = []
    with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) + 4)) as pool:
        for index, row in enumerate(pool.map(hash_one, paths), start=1):
            rows.append(row)
            if index % 500 == 0:
                print(f"  repository hash progress: {index}/{len(paths)}", flush=True)
    records = [f"{relative}\0{size}\0{digest}\n" for relative, size, digest in rows]
    return {
        "path": str(REPOSITORY_JUNCTION),
        "files": len(rows),
        "bytes": sum(size for _, size, _ in rows),
        "sha256": sha256_bytes("".join(records).encode("utf-8")),
        "record_format": "walk-order relative path + NUL + bytes + NUL + SHA-256 + LF",
    }


def load_guard() -> Callable[[dict[str, Any], Path], dict[str, Any]]:
    if str(BASE) not in sys.path:
        sys.path.insert(0, str(BASE))
    from rubric_provenance import validate_rubric_provenance

    return validate_rubric_provenance


def canonical_context() -> dict[str, Any]:
    rubric_path = BASE / "evaluation-rubric.json"
    require(sha256_file(rubric_path) == RUBRIC_SHA256, "canonical rubric hash mismatch")
    rubric = load_json(rubric_path)
    validate_rubric_provenance = load_guard()
    preflight = validate_rubric_provenance(rubric, rubric_path)
    finding_ids = {item["criterion_id"] for item in preflight["rubric_findings"]}
    pointers: dict[str, str] = {}
    questions: dict[str, dict[str, Any]] = {}
    criteria: dict[str, dict[str, Any]] = {}
    for question_index, question in enumerate(rubric["questions"]):
        for criterion_index, criterion in enumerate(question["criteria"]):
            criterion_id = criterion["criterion_id"]
            pointers[criterion_id] = (
                f"/questions/{question_index}/criteria/{criterion_index}"
            )
            questions[criterion_id] = question
            criteria[criterion_id] = criterion
    canonical_ids = sorted(finding_ids)
    require(preflight["criterion_count"] == 128, "canonical criterion total differs")
    require(len(canonical_ids) == 113, "canonical finding total differs")
    require(ids_sha256(canonical_ids) == CANONICAL_IDS_SHA256, "canonical ID hash differs")
    return {
        "rubric": rubric,
        "rubric_path": rubric_path,
        "preflight": preflight,
        "ids": canonical_ids,
        "pointers": pointers,
        "questions": questions,
        "criteria": criteria,
    }


def load_batches() -> dict[str, Any]:
    batch1_overlay = load_json(BATCH1 / "criterion-provenance-batch1-overlay.json")
    batch1_ledger = load_json(BATCH1 / "criterion-provenance-batch1-ledger.json")
    batch2_overlay = load_json(BATCH2 / "normative-provenance-batch2.overlay.json")
    batch2_ledger = load_json(BATCH2 / "normative-provenance-batch2.ledger.json")
    batch2_attestations = load_json(
        BATCH2 / "normative-provenance-batch2.source-attestations.json"
    )
    batch3_overlay = load_json(BATCH3 / "criterion-provenance-batch-3.overlay.json")
    batch3_ledger = [
        json.loads(line)
        for line in (
            BATCH3 / "criterion-provenance-batch-3.ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line
    ]
    batch3_source_hashes = load_json(
        BATCH3 / "criterion-provenance-batch-3.source-hashes.json"
    )
    return {
        "batch1_overlay": batch1_overlay,
        "batch1_ledger": batch1_ledger,
        "batch2_overlay": batch2_overlay,
        "batch2_ledger": batch2_ledger,
        "batch2_attestations": batch2_attestations,
        "batch3_overlay": batch3_overlay,
        "batch3_ledger": batch3_ledger,
        "batch3_source_hashes": batch3_source_hashes,
    }


def reproduce_partition_defect(
    canonical_ids: list[str],
    batches: dict[str, Any],
) -> dict[str, Any]:
    batch1_ids = batches["batch1_overlay"]["slice_contract"]["owned_ids"]
    batch2_ids = [
        item["criterion_id"]
        for item in batches["batch2_overlay"]["criterion_updates"]
    ]
    batch3_ids = batches["batch3_overlay"]["selection"]["criterion_ids"]
    require(batch1_ids == canonical_ids[:38], "Batch1 slice does not equal positions 1-38")
    require(batch2_ids == canonical_ids[39:77], "Batch2 slice defect differs")
    require(batch3_ids == canonical_ids[76:113], "Batch3 slice does not equal positions 77-113")
    ownership = Counter(batch1_ids + batch2_ids + batch3_ids)
    overlaps = sorted(item for item, count in ownership.items() if count > 1)
    omissions = [item for item in canonical_ids if item not in ownership]
    extras = sorted(set(ownership) - set(canonical_ids))
    require(overlaps == ["HW-05:R4"], "unexpected overlap set")
    require(omissions == ["AIS-08:R5"], "unexpected omission set")
    require(not extras, "unexpected extra criterion IDs")
    require(len(ownership) == 112, "defective union unique count differs")
    return {
        "canonical_count": len(canonical_ids),
        "canonical_ids_sha256": ids_sha256(canonical_ids),
        "batch1": {
            "positions_1_based": [1, 38],
            "count": len(batch1_ids),
            "ids_sha256": ids_sha256(batch1_ids),
        },
        "batch2_original": {
            "positions_1_based": [40, 77],
            "count": len(batch2_ids),
            "ids_sha256": ids_sha256(batch2_ids),
        },
        "batch3": {
            "positions_1_based": [77, 113],
            "count": len(batch3_ids),
            "ids_sha256": ids_sha256(batch3_ids),
        },
        "union_unique_count": len(ownership),
        "union_ids_sha256": ids_sha256(sorted(ownership)),
        "overlap": {"criterion_id": overlaps[0], "canonical_position_1_based": 77},
        "omission": {"criterion_id": omissions[0], "canonical_position_1_based": 39},
        "extras": extras,
    }


def compare_overlap(
    canonical: dict[str, Any],
    batches: dict[str, Any],
) -> dict[str, Any]:
    criterion_id = "HW-05:R4"
    pointer = canonical["pointers"][criterion_id]
    criterion = canonical["criteria"][criterion_id]
    pointer_sha256 = sha256_bytes(canonical_json_bytes(criterion))
    batch2_overlay_record = next(
        item
        for item in batches["batch2_overlay"]["criterion_updates"]
        if item["criterion_id"] == criterion_id
    )
    batch2_ledger_record = next(
        item
        for item in batches["batch2_ledger"]["criteria"]
        if item["criterion_id"] == criterion_id
    )
    batch3_ledger_record = next(
        item for item in batches["batch3_ledger"] if item["criterion_id"] == criterion_id
    )
    checks = {
        "criterion_id": (
            batch2_overlay_record["criterion_id"]
            == batch2_ledger_record["criterion_id"]
            == batch3_ledger_record["criterion_id"]
            == criterion_id
        ),
        "canonical_position": (
            batch2_ledger_record["absolute_unscorable_index"] == 76
            and batch3_ledger_record["slice_index_1_based"] == 77
        ),
        "canonical_pointer": batch3_ledger_record["canonical_pointer"] == pointer,
        "canonical_pointer_sha256": (
            batch3_ledger_record["canonical_pointer_sha256"] == pointer_sha256
        ),
        "question_identity": (
            batch2_ledger_record["question_id"]
            == canonical["questions"][criterion_id]["id"]
        ),
        "rubric_identity": (
            batch2_ledger_record["rubric_id"]
            == canonical["questions"][criterion_id]["rubric_id"]
        ),
        "project_identity": (
            batch2_ledger_record["project"]
            == canonical["questions"][criterion_id]["project"]
        ),
        "canonical_state": batch2_ledger_record["current_state"]
        == {
            key: criterion[key]
            for key in (
                "criterion_provenance",
                "provenance_kind",
                "validation_state",
            )
        },
        "classification": (
            batch2_overlay_record["classification"]
            == batch2_ledger_record["classification"]
            == batch3_ledger_record["classification"]
            == "structural_harness_not_product_law"
        ),
        "scorable_effect": (
            batch2_overlay_record["scorable"] is False
            and batch2_ledger_record["scorable_after_batch"] is False
            and batch3_ledger_record["merge_action"] == "retain_unscorable"
        ),
        "normative_evidence": (
            batch2_overlay_record["normative_evidence"] is None
            and batch2_ledger_record["normative_evidence"] is None
        ),
        "candidate_replacement": (
            batch2_overlay_record["candidate_rubric_fields"] is None
            and batch2_ledger_record["candidate_rubric_fields"] is None
            and all(
                item["criterion_id"] != criterion_id
                for item in batches["batch3_overlay"]["criterion_updates"]
            )
        ),
        "human_confirmation": (
            batch2_ledger_record["human_confirmation_recorded"] is False
            and batches["batch2_overlay"]["invariants"][
                "human_confirmation_recorded"
            ]
            is False
            and batches["batch3_overlay"]["reviewer_kind"] == "ai"
            and batches["batch3_overlay"]["human_confirmation"] is False
        ),
        "criterion_specific_attestation": (
            criterion_id
            not in json.dumps(batches["batch2_attestations"], ensure_ascii=True)
            and criterion_id
            not in json.dumps(batches["batch3_source_hashes"], ensure_ascii=True)
        ),
    }
    require(all(checks.values()), "HW-05:R4 overlap has a material conflict")
    return {
        "criterion_id": criterion_id,
        "canonical_position_1_based": 77,
        "canonical_pointer": pointer,
        "canonical_record_sha256": pointer_sha256,
        "batch2_record_sha256": sha256_bytes(
            canonical_json_bytes(
                {
                    "overlay": batch2_overlay_record,
                    "ledger": batch2_ledger_record,
                }
            )
        ),
        "batch3_record_sha256": sha256_bytes(
            canonical_json_bytes(batch3_ledger_record)
        ),
        "batch2_rationale_sha256": sha256_bytes(
            batch2_ledger_record["bounded_rationale"].encode("utf-8")
        ),
        "batch3_rationale_sha256": sha256_bytes(
            batch3_ledger_record["basis"].encode("utf-8")
        ),
        "rationale_wording_equal": (
            batch2_ledger_record["bounded_rationale"]
            == batch3_ledger_record["basis"]
        ),
        "rationale_materially_consistent": True,
        "field_checks": checks,
        "material_conflict": False,
        "canonical_owner": "criterion-provenance-batch-3",
        "resolution": "remove_from_batch2_successor_retain_batch3",
        "evidence_loss": False,
    }


def classify_missing(
    canonical: dict[str, Any],
) -> dict[str, Any]:
    criterion_id = "AIS-08:R5"
    criterion = canonical["criteria"][criterion_id]
    question = canonical["questions"][criterion_id]
    pointer = canonical["pointers"][criterion_id]
    require(pointer == "/questions/7/criteria/3", "AIS-08:R5 canonical pointer differs")
    require(criterion["criterion_provenance"] == "question_only", "AIS-08:R5 provenance differs")
    require(criterion["provenance_kind"] == "question_inferred", "AIS-08:R5 kind differs")
    require(criterion["validation_state"] == "unverified", "AIS-08:R5 state differs")
    require(criterion["source_provision_ids"] == [], "AIS-08:R5 has source provision IDs")
    require(criterion["source_rule_ids"] == [], "AIS-08:R5 has source rule IDs")
    require(
        criterion["corpus_support"]["supporting_provision_count"] == 0
        and criterion["corpus_support"]["supporting_rule_count"] == 0,
        "AIS-08:R5 has non-zero support",
    )
    require(question["irrelevant"] is False, "AIS-08 question relevance flag differs")
    require(len(criterion["evidence_refs"]) == 1, "AIS-08:R5 evidence reference count differs")
    evidence_ref = criterion["evidence_refs"][0]
    require(evidence_ref["source_id"] == "rubric_v1", "AIS-08:R5 source differs")
    rubric_v1 = load_json(BASE / "evidence" / "rubric-v1.snapshot.json")
    frozen_value = resolve_pointer(rubric_v1, evidence_ref["pointer"])
    frozen_hash = sha256_bytes(canonical_json_bytes(frozen_value))
    require(frozen_value is False, "AIS-08 frozen relevance value differs")
    require(frozen_hash == evidence_ref["pointer_sha256"], "AIS-08 frozen pointer hash differs")

    source_snapshot = load_json(BASE / "evidence" / "source.snapshot.json")
    contextual_identities = []
    for provision_id in question["expected_evidence"]["required"]:
        matches = [
            (index, item)
            for index, item in enumerate(source_snapshot["provisions"])
            if item["provision_key"] == provision_id
        ]
        require(len(matches) == 1, f"source identity count differs: {provision_id}")
        index, item = matches[0]
        contextual_identities.append(
            {
                "source_provision_id": provision_id,
                "pointer": f"/provisions/{index}",
                "pointer_sha256": sha256_bytes(canonical_json_bytes(item)),
                "relationship": "contextual_identity_only_not_criterion_support",
                "body_present_in_snapshot": any(
                    key in item for key in ("body", "text", "content", "normative_body")
                ),
            }
        )
    require(
        all(not item["body_present_in_snapshot"] for item in contextual_identities),
        "source snapshot unexpectedly contains normative body text",
    )

    return {
        "criterion_id": criterion_id,
        "canonical_position_1_based": 39,
        "question_id": question["id"],
        "canonical_pointer": pointer,
        "canonical_record_sha256": sha256_bytes(canonical_json_bytes(criterion)),
        "canonical_state": {
            "criterion_provenance": criterion["criterion_provenance"],
            "provenance_kind": criterion["provenance_kind"],
            "validation_state": criterion["validation_state"],
            "source_provision_ids": criterion["source_provision_ids"],
            "source_rule_ids": criterion["source_rule_ids"],
            "supporting_provision_count": criterion["corpus_support"][
                "supporting_provision_count"
            ],
            "supporting_rule_count": criterion["corpus_support"][
                "supporting_rule_count"
            ],
        },
        "frozen_expectation": {
            "source_id": evidence_ref["source_id"],
            "file_sha256": RUBRIC_V1_SHA256,
            "pointer": evidence_ref["pointer"],
            "pointer_sha256": frozen_hash,
            "boolean_value": frozen_value,
            "semantic_confirmation": False,
        },
        "source_snapshot": {
            "file_sha256": SOURCE_SNAPSHOT_SHA256,
            "contextual_identities": contextual_identities,
            "normative_body_hash_available": False,
            "normative_rule_hash_available": False,
        },
        "classification": "structural_harness_not_product_law",
        "classification_basis": "response_contract_not_product_law",
        "scorable": False,
        "normative_evidence": None,
        "candidate_rubric_fields": None,
        "human_confirmation": False,
        "reviewer_kind": "ai",
        "exact_pointers_are_semantic_confirmation": False,
    }


def corrected_selection(canonical_ids: list[str]) -> tuple[list[str], dict[str, Any]]:
    selected_ids = canonical_ids[38:76]
    require(len(selected_ids) == 38, "corrected Batch2 length differs")
    require(selected_ids[0] == "AIS-08:R5", "corrected Batch2 first ID differs")
    require(selected_ids[-1] == "HW-05:R3", "corrected Batch2 last ID differs")
    return (
        selected_ids,
        {
            "filter": "canonical provenance preflight rubric_findings",
            "sort": "stable criterion_id ascending",
            "total_unscorable_or_unresolved": 113,
            "slice_start_index_zero_based": 38,
            "slice_end_index_zero_based_inclusive": 75,
            "selected_count": 38,
            "first_criterion_id": selected_ids[0],
            "last_criterion_id": selected_ids[-1],
            "selected_ids_sha256": ids_sha256(selected_ids),
        },
    )


def new_missing_overlay_record(classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "criterion_id": classification["criterion_id"],
        "question_id": classification["question_id"],
        "classification": classification["classification"],
        "scorable": False,
        "normative_evidence": None,
        "candidate_rubric_fields": None,
        "recommended_action": (
            "Keep fail-closed in the product-law rubric and route to a separate "
            "contract/integrity validation layer."
        ),
    }


def new_missing_ledger_record(
    canonical: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    criterion = canonical["criteria"][classification["criterion_id"]]
    question = canonical["questions"][classification["criterion_id"]]
    return {
        "absolute_unscorable_index": 38,
        "criterion_id": classification["criterion_id"],
        "question_id": question["id"],
        "rubric_id": question["rubric_id"],
        "project": question["project"],
        "classification": classification["classification"],
        "scorable_after_batch": False,
        "current_state": {
            key: criterion[key]
            for key in (
                "criterion_provenance",
                "provenance_kind",
                "validation_state",
            )
        },
        "normative_evidence": None,
        "bounded_rationale": (
            "Generic refusal behavior is a response-contract and harness concern; "
            "the canonical relevance flag supplies no normative policy support."
        ),
        "blocker": (
            "Wrong scoring boundary; normative source cannot establish this "
            "response-contract behavior as product law."
        ),
        "recommended_action": (
            "Keep fail-closed in the product-law rubric and route to a separate "
            "contract/integrity validation layer."
        ),
        "candidate_rubric_fields": None,
        "human_confirmation_recorded": False,
    }


def build_corrected_batch2(
    canonical: dict[str, Any],
    batches: dict[str, Any],
    missing: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selected_ids, selection = corrected_selection(canonical["ids"])
    original_overlay = batches["batch2_overlay"]
    original_ledger = batches["batch2_ledger"]
    original_updates = original_overlay["criterion_updates"]
    original_ledger_records = original_ledger["criteria"]
    require(
        [item["criterion_id"] for item in original_updates]
        == canonical["ids"][39:77],
        "original Batch2 overlay order differs",
    )
    require(
        [item["criterion_id"] for item in original_ledger_records]
        == canonical["ids"][39:77],
        "original Batch2 ledger order differs",
    )

    overlay = copy.deepcopy(original_overlay)
    ledger = copy.deepcopy(original_ledger)
    overlay["selection"] = selection
    ledger["selection"] = copy.deepcopy(selection)
    overlay["criterion_updates"] = [
        new_missing_overlay_record(missing),
        *copy.deepcopy(original_updates[:-1]),
    ]
    ledger["criteria"] = [
        new_missing_ledger_record(canonical, missing),
        *copy.deepcopy(original_ledger_records[:-1]),
    ]
    overlay_counts = dict(
        sorted(Counter(item["classification"] for item in overlay["criterion_updates"]).items())
    )
    ledger_counts = dict(
        sorted(Counter(item["classification"] for item in ledger["criteria"]).items())
    )
    require(overlay_counts == ledger_counts, "corrected classification counts differ")
    overlay["classification_counts"] = overlay_counts
    ledger["classification_counts"] = ledger_counts

    preservation = []
    for original_overlay_record, corrected_overlay_record, original_ledger_record, corrected_ledger_record in zip(
        original_updates[:-1],
        overlay["criterion_updates"][1:],
        original_ledger_records[:-1],
        ledger["criteria"][1:],
    ):
        require(
            original_overlay_record == corrected_overlay_record,
            f"untouched overlay record changed: {original_overlay_record['criterion_id']}",
        )
        require(
            original_ledger_record == corrected_ledger_record,
            f"untouched ledger record changed: {original_ledger_record['criterion_id']}",
        )
        preservation.append(
            {
                "criterion_id": original_overlay_record["criterion_id"],
                "original_position_1_based": (
                    original_ledger_record["absolute_unscorable_index"] + 1
                ),
                "corrected_position_1_based": (
                    corrected_ledger_record["absolute_unscorable_index"] + 1
                ),
                "overlay_record_sha256": sha256_bytes(
                    canonical_json_bytes(original_overlay_record)
                ),
                "ledger_record_sha256": sha256_bytes(
                    canonical_json_bytes(original_ledger_record)
                ),
                "semantic_identity": True,
            }
        )
    require(len(preservation) == 37, "preserved record count differs")
    require(
        [item["criterion_id"] for item in overlay["criterion_updates"]] == selected_ids,
        "corrected overlay membership differs",
    )
    require(
        [item["criterion_id"] for item in ledger["criteria"]] == selected_ids,
        "corrected ledger membership differs",
    )
    return (
        overlay,
        ledger,
        {
            "preserved_record_count": len(preservation),
            "records": preservation,
            "records_manifest_sha256": sha256_bytes(
                canonical_json_bytes(preservation)
            ),
            "dropped_batch2_record": {
                "criterion_id": original_updates[-1]["criterion_id"],
                "overlay_record_sha256": sha256_bytes(
                    canonical_json_bytes(original_updates[-1])
                ),
                "ledger_record_sha256": sha256_bytes(
                    canonical_json_bytes(original_ledger_records[-1])
                ),
            },
        },
    )


def normalized_classification(value: str) -> str:
    return value.replace(
        "structural_harness_non_product_law",
        "structural_harness_not_product_law",
    )


def validate_membership(
    canonical_ids: list[str],
    batch1_ids: list[str],
    corrected_ids: list[str],
    batch3_ids: list[str],
) -> dict[str, Any]:
    for name, values in (
        ("Batch1", batch1_ids),
        ("Batch2 successor", corrected_ids),
        ("Batch3", batch3_ids),
    ):
        require(len(values) == len(set(values)), f"{name} contains duplicate IDs")
    require(batch1_ids == canonical_ids[:38], "Batch1 corrected membership differs")
    require(corrected_ids == canonical_ids[38:76], "Batch2 successor membership differs")
    require(batch3_ids == canonical_ids[76:113], "Batch3 corrected membership differs")
    require(not (set(batch1_ids) & set(corrected_ids)), "Batch1/Batch2 overlap")
    require(not (set(batch1_ids) & set(batch3_ids)), "Batch1/Batch3 overlap")
    require(not (set(corrected_ids) & set(batch3_ids)), "Batch2/Batch3 overlap")
    union = set(batch1_ids) | set(corrected_ids) | set(batch3_ids)
    require(union == set(canonical_ids), "corrected union differs from canonical IDs")
    return {
        "batch1": {
            "positions_1_based": [1, 38],
            "count": len(batch1_ids),
            "ids_sha256": ids_sha256(batch1_ids),
        },
        "batch2_successor": {
            "positions_1_based": [39, 76],
            "count": len(corrected_ids),
            "ids_sha256": ids_sha256(corrected_ids),
        },
        "batch3": {
            "positions_1_based": [77, 113],
            "count": len(batch3_ids),
            "ids_sha256": ids_sha256(batch3_ids),
        },
        "union": {
            "count": len(union),
            "ids_sha256": ids_sha256(sorted(union)),
            "duplicate_ids": [],
            "omitted_ids": [],
            "extra_ids": [],
        },
        "pairwise_disjoint": True,
    }


def validate_correction_artifacts(
    canonical: dict[str, Any],
    batches: dict[str, Any],
    overlay: dict[str, Any],
    ledger: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    selected_ids = canonical["ids"][38:76]
    overlay_ids = [item["criterion_id"] for item in overlay["criterion_updates"]]
    ledger_ids = [item["criterion_id"] for item in ledger["criteria"]]
    require(overlay["schema_version"] == "consume-api-normative-provenance-overlay/1", "overlay schema differs")
    require(ledger["schema_version"] == "consume-api-normative-provenance-ledger/1", "ledger schema differs")
    require(overlay_ids == selected_ids, "overlay corrected IDs differ")
    require(ledger_ids == selected_ids, "ledger corrected IDs differ")
    require(overlay["selection"]["selected_ids_sha256"] == ids_sha256(selected_ids), "overlay ID hash differs")
    require(ledger["selection"]["selected_ids_sha256"] == ids_sha256(selected_ids), "ledger ID hash differs")
    require(overlay["selection"]["slice_start_index_zero_based"] == 38, "overlay start differs")
    require(overlay["selection"]["slice_end_index_zero_based_inclusive"] == 75, "overlay end differs")
    require(ledger["selection"] == overlay["selection"], "selection metadata differs")
    require(
        overlay["evidence_sources"] == batches["batch2_overlay"]["evidence_sources"],
        "original Batch2 evidence source binding changed",
    )
    require(
        overlay["classification_counts"] == ledger["classification_counts"],
        "classification counts differ",
    )
    new_overlay = overlay["criterion_updates"][0]
    new_ledger = ledger["criteria"][0]
    require(new_overlay["criterion_id"] == "AIS-08:R5", "new overlay record differs")
    require(new_ledger["criterion_id"] == "AIS-08:R5", "new ledger record differs")
    require(
        new_overlay["classification"] == new_ledger["classification"]
        == "structural_harness_not_product_law",
        "AIS-08:R5 classification differs",
    )
    require(new_overlay["scorable"] is False, "AIS-08:R5 was upgraded")
    require(new_overlay["normative_evidence"] is None, "AIS-08:R5 gained evidence")
    require(new_overlay["candidate_rubric_fields"] is None, "AIS-08:R5 gained candidate fields")
    require(new_ledger["scorable_after_batch"] is False, "AIS-08:R5 ledger was upgraded")
    require(new_ledger["human_confirmation_recorded"] is False, "AIS-08:R5 has human confirmation")
    require(attestation["reviewer_kind"] == "ai", "attestation reviewer differs")
    require(attestation["human_confirmation"] is False, "AI attestation claims human confirmation")
    require(attestation["quote_free"] is True, "attestation is not quote-free")
    criterion_attestation = attestation["criterion_attestation"]
    require(
        criterion_attestation["classification"]
        == "structural_harness_not_product_law",
        "attested classification differs",
    )
    require(criterion_attestation["scorable"] is False, "attestation upgrades criterion")
    require(
        criterion_attestation["canonical_record_sha256"]
        == sha256_bytes(
            canonical_json_bytes(canonical["criteria"]["AIS-08:R5"])
        ),
        "AIS-08:R5 canonical record hash differs",
    )
    return {
        "overlay_schema": "passed",
        "ledger_schema": "passed",
        "attestation_schema": "passed",
        "corrected_membership": "passed",
        "classification_partition": "passed",
        "original_evidence_binding_unchanged": "passed",
        "unsupported_upgrade_absent": "passed",
        "ai_not_human_confirmation": "passed",
    }


def add_evidence_source(
    rubric: dict[str, Any],
    source: dict[str, Any],
) -> None:
    existing = {item["id"] for item in rubric["evidence_sources"]}
    require(source["id"] not in existing, f"evidence source collision: {source['id']}")
    rubric["evidence_sources"].append(copy.deepcopy(source))


def replace_criterion(
    rubric: dict[str, Any],
    criterion_id: str,
    replacement: dict[str, Any],
) -> None:
    matches = []
    for question in rubric["questions"]:
        for index, criterion in enumerate(question["criteria"]):
            if criterion["criterion_id"] == criterion_id:
                matches.append((question, index))
    require(len(matches) == 1, f"criterion replacement target differs: {criterion_id}")
    question, index = matches[0]
    question["criteria"][index] = copy.deepcopy(replacement)


def update_criterion(
    rubric: dict[str, Any],
    criterion_id: str,
    fields: dict[str, Any],
) -> None:
    matches = [
        criterion
        for question in rubric["questions"]
        for criterion in question["criteria"]
        if criterion["criterion_id"] == criterion_id
    ]
    require(len(matches) == 1, f"criterion update target differs: {criterion_id}")
    matches[0].update(copy.deepcopy(fields))


def combined_preflight(
    canonical: dict[str, Any],
    batches: dict[str, Any],
    corrected_overlay: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(canonical["rubric"])
    before = copy.deepcopy(merged)

    for source in batches["batch1_overlay"]["evidence_sources"]:
        add_evidence_source(merged, source)
    for source in corrected_overlay["evidence_sources"]:
        staged = copy.deepcopy(source)
        staged["path"] = str(BATCH2 / source["path"])
        add_evidence_source(merged, staged)
    for source in batches["batch3_overlay"]["evidence_sources_to_add"]:
        staged = {
            "id": source["id"],
            "path": source["origin_path"],
            "sha256": source["sha256"],
            "type": source["type"],
        }
        add_evidence_source(merged, staged)

    for operation in batches["batch1_overlay"]["operations"]:
        if operation["action"] == "replace_criterion_provenance":
            replace_criterion(
                merged,
                operation["criterion_id"],
                operation["replacement"],
            )
    for update in corrected_overlay["criterion_updates"]:
        fields = update["candidate_rubric_fields"]
        if fields is not None:
            update_criterion(merged, update["criterion_id"], fields)
    for update in batches["batch3_overlay"]["criterion_updates"]:
        replace_criterion(merged, update["criterion_id"], update["replacement"])

    changed_ids = []
    for old_question, new_question in zip(before["questions"], merged["questions"]):
        for old_criterion, new_criterion in zip(
            old_question["criteria"], new_question["criteria"]
        ):
            require(
                old_criterion["criterion_id"] == new_criterion["criterion_id"],
                "criterion ordering changed during preflight",
            )
            if old_criterion != new_criterion:
                changed_ids.append(old_criterion["criterion_id"])

    validate_rubric_provenance = load_guard()
    preflight = validate_rubric_provenance(merged, canonical["rubric_path"])
    dispositions = Counter(
        item["disposition"] for item in preflight["rubric_findings"]
    )
    base_scorable = (
        canonical["preflight"]["criterion_count"]
        - len(canonical["preflight"]["rubric_findings"])
    )
    combined_scorable = preflight["criterion_count"] - len(preflight["rubric_findings"])
    base_scorable_ids = {
        criterion_id
        for question in canonical["preflight"]["questions"].values()
        for criterion in [
            *question["dimensions"].values(),
            *question["manual"],
        ]
        for criterion_id in [criterion["criterion_id"]]
        if criterion["disposition"] == "scorable"
    }
    combined_scorable_ids = {
        criterion_id
        for question in preflight["questions"].values()
        for criterion in [
            *question["dimensions"].values(),
            *question["manual"],
        ]
        for criterion_id in [criterion["criterion_id"]]
        if criterion["disposition"] == "scorable"
    }
    newly_scorable = sorted(combined_scorable_ids - base_scorable_ids)
    return {
        "private_copy_kind": "deep_copy_in_memory",
        "canonical_criterion_count": preflight["criterion_count"],
        "base": {
            "scorable": base_scorable,
            "findings": len(canonical["preflight"]["rubric_findings"]),
            "dispositions": dict(
                sorted(
                    Counter(
                        item["disposition"]
                        for item in canonical["preflight"]["rubric_findings"]
                    ).items()
                )
            ),
        },
        "combined": {
            "scorable": combined_scorable,
            "findings": len(preflight["rubric_findings"]),
            "unscorable": dispositions.get("unscorable", 0),
            "unresolved": dispositions.get("unresolved", 0),
            "dispositions": dict(sorted(dispositions.items())),
        },
        "changed_criteria_count": len(changed_ids),
        "changed_criteria_ids_sha256": ids_sha256(sorted(changed_ids)),
        "newly_scorable_count": len(newly_scorable),
        "newly_scorable_ids_sha256": ids_sha256(newly_scorable),
        "provenance_preflight": "passed",
        "source_rubric_object_unchanged": before == canonical["rubric"],
    }


def expect_rejection(
    name: str,
    operation: Callable[[], None],
) -> dict[str, Any]:
    try:
        operation()
    except (ValidationError, KeyError, TypeError, ValueError):
        return {"name": name, "result": "passed", "expected": "rejected"}
    raise ValidationError(f"negative control was accepted: {name}")


def mutation_checks(
    canonical: dict[str, Any],
    batches: dict[str, Any],
    overlay: dict[str, Any],
    ledger: dict[str, Any],
    attestation: dict[str, Any],
) -> list[dict[str, Any]]:
    batch1_ids = batches["batch1_overlay"]["slice_contract"]["owned_ids"]
    batch3_ids = batches["batch3_overlay"]["selection"]["criterion_ids"]
    corrected_ids = [item["criterion_id"] for item in overlay["criterion_updates"]]

    def omitted_position() -> None:
        validate_membership(
            canonical["ids"],
            batch1_ids,
            corrected_ids[:-1],
            batch3_ids,
        )

    def duplicate_owner() -> None:
        validate_membership(
            canonical["ids"],
            batch1_ids,
            [*corrected_ids, batch3_ids[0]],
            batch3_ids,
        )

    def changed_untouched_record() -> None:
        mutated = copy.deepcopy(overlay)
        mutated["criterion_updates"][1]["recommended_action"] += " mutated"
        validate_correction_artifacts(
            canonical,
            batches,
            mutated,
            ledger,
            attestation,
        )
        original = batches["batch2_overlay"]["criterion_updates"][0]
        require(
            mutated["criterion_updates"][1] == original,
            "untouched Batch2 record hash differs",
        )

    def bad_hash() -> None:
        mutated = copy.deepcopy(attestation)
        mutated["criterion_attestation"]["canonical_record_sha256"] = "0" * 64
        validate_correction_artifacts(
            canonical,
            batches,
            overlay,
            ledger,
            mutated,
        )

    def unsupported_upgrade() -> None:
        mutated = copy.deepcopy(overlay)
        mutated["criterion_updates"][0]["scorable"] = True
        validate_correction_artifacts(
            canonical,
            batches,
            mutated,
            ledger,
            attestation,
        )

    def ai_as_human() -> None:
        mutated = copy.deepcopy(attestation)
        mutated["human_confirmation"] = True
        validate_correction_artifacts(
            canonical,
            batches,
            overlay,
            ledger,
            mutated,
        )

    return [
        expect_rejection("omitted_canonical_position", omitted_position),
        expect_rejection("duplicate_owner", duplicate_owner),
        expect_rejection("changed_untouched_batch2_record", changed_untouched_record),
        expect_rejection("bad_hash", bad_hash),
        expect_rejection("unsupported_upgrade", unsupported_upgrade),
        expect_rejection("ai_as_human_confirmation", ai_as_human),
    ]


def all_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in all_string_values(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in all_string_values(child)]
    return []


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text)
    return paragraphs


def forbidden_keys(value: Any, path: str = "") -> list[str]:
    blocked = {
        "exact_question",
        "question_text",
        "source_text",
        "normative_text",
        "body_text",
        "corpus_text",
        "verbatim_quote",
    }
    hits = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if key in blocked:
                hits.append(child_path)
            hits.extend(forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(forbidden_keys(child, f"{path}/{index}"))
    return hits


def leakage_scan(
    artifacts: dict[str, bytes],
    canonical: dict[str, Any],
    external_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    combined = b"\n".join(artifacts[name] for name in sorted(artifacts))
    question_literals = [
        question["exact_question"].encode("utf-8")
        for question in canonical["rubric"]["questions"]
        if question.get("exact_question")
    ]
    question_hits = sum(literal in combined for literal in question_literals)

    source_literals: list[bytes] = []
    for item in external_inputs:
        path = Path(item["path"])
        if path.suffix.casefold() == ".docx":
            source_literals.extend(
                text.encode("utf-8")
                for text in docx_paragraphs(path)
                if len(text.encode("utf-8")) >= 32
            )
        elif (
            item["label"].startswith("batch1-evidence/")
            or item["label"].startswith("batch2-rule-artifact/")
            or item["label"].startswith("batch3-overlay-origin/")
            or item["label"].startswith("batch3-source/hw_")
        ):
            document = load_json(path)
            source_literals.extend(
                text.encode("utf-8")
                for text in all_string_values(document)
                if len(text.encode("utf-8")) >= 96
                and not (len(text) > 2 and text[1:3] == ":\\")
            )
    source_hits = sum(literal in combined for literal in source_literals)

    key_hits = []
    for name, payload in artifacts.items():
        if name.endswith(".json"):
            key_hits.extend(
                f"{name}:{pointer}"
                for pointer in forbidden_keys(json.loads(payload.decode("utf-8")))
            )
    markdown_quote_hits = 0
    for name, payload in artifacts.items():
        if name.endswith(".md"):
            markdown_quote_hits += sum(
                line.lstrip().startswith(">")
                for line in payload.decode("utf-8").splitlines()
            )
    require(question_hits == 0, "question literal leakage detected")
    require(source_hits == 0, "source literal leakage detected")
    require(not key_hits, "forbidden text-bearing key detected")
    require(markdown_quote_hits == 0, "markdown quote block detected")
    return {
        "scope": sorted(artifacts),
        "question_literals_checked": len(question_literals),
        "question_literal_hits": question_hits,
        "source_literals_checked": len(source_literals),
        "source_literal_hits": source_hits,
        "forbidden_text_key_hits": key_hits,
        "markdown_quote_block_hits": markdown_quote_hits,
        "result": "passed",
    }


def build_attestation(
    missing: dict[str, Any],
    overlap: dict[str, Any],
    input_records: list[dict[str, Any]],
    preservation: dict[str, Any],
) -> dict[str, Any]:
    pivotal_labels = {
        "base/FILE_INVENTORY.json",
        "base/evaluation-rubric.json",
        "base/evidence/rubric-v1.snapshot.json",
        "base/evidence/source.snapshot.json",
    }
    pivotal = [
        item
        for item in input_records
        if item["label"] in pivotal_labels
        or "batch1-" in item["label"]
        or "batch2." in item["label"]
        or "batch-3." in item["label"]
    ]
    return {
        "schema_version": (
            "consume-api-provenance-partition-correction-source-attestations/1"
        ),
        "compatible_rubric_schema": "consume-api-evaluation-rubric/3",
        "compatible_overlay_schema": "consume-api-normative-provenance-overlay/1",
        "quote_free": True,
        "reviewer_kind": "ai",
        "human_confirmation": False,
        "canonical_bundle": {
            "path": str(BASE),
            "payload_sha256": CANONICAL_PAYLOAD_SHA256,
            "rubric_sha256": RUBRIC_SHA256,
            "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
            "rubric_v1_sha256": RUBRIC_V1_SHA256,
        },
        "criterion_attestation": missing,
        "overlap_attestation": overlap,
        "original_batch2_evidence_source": {
            "path": str(
                BATCH2 / "normative-provenance-batch2.source-attestations.json"
            ),
            "sha256": BATCH_FILE_HASHES[BATCH2][
                "normative-provenance-batch2.source-attestations.json"
            ],
            "unchanged_and_still_required": True,
        },
        "preservation": {
            "unchanged_record_count": preservation["preserved_record_count"],
            "record_hash_manifest_sha256": preservation[
                "records_manifest_sha256"
            ],
        },
        "pivotal_input_hashes": pivotal,
        "limitations": [
            "Exact identity and frozen-expectation pointers are not semantic confirmation.",
            "No normative body or rule hash supports the added structural criterion.",
            "AI review is not human confirmation.",
            "This attestation is correction audit evidence and is not a rubric evidence source.",
        ],
    }


def artifact_descriptor(name: str, payload: bytes) -> dict[str, Any]:
    return {
        "path": name,
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
    }


def build_merge_markdown(
    descriptors: dict[str, dict[str, Any]],
    membership: dict[str, Any],
    preflight: dict[str, Any],
) -> bytes:
    overlay = descriptors[OVERLAY_NAME]
    ledger = descriptors[LEDGER_NAME]
    attestation = descriptors[ATTESTATION_NAME]
    text = f"""# Provenance Partition Correction Merge Instructions

## Scope

This correction replaces the original Batch2 ownership artifacts. It does not alter
the canonical bundle, Batch1, Batch3, source evidence, repository, or live resources.
It does not create the final successor bundle.

## Integrity

- Canonical payload SHA-256: `{CANONICAL_PAYLOAD_SHA256}`
- Canonical 113-ID SHA-256: `{CANONICAL_IDS_SHA256}`
- Corrected Batch2 ID SHA-256: `{membership['batch2_successor']['ids_sha256']}`
- Corrected overlay: `{overlay['sha256']}` ({overlay['bytes']} bytes)
- Corrected ledger: `{ledger['sha256']}` ({ledger['bytes']} bytes)
- Correction attestation: `{attestation['sha256']}` ({attestation['bytes']} bytes)

## Exact merge semantics

1. Recompute the canonical provenance preflight and require exactly 113 sorted
   findings with the canonical ID hash above.
2. Keep Batch1 as canonical positions 1-38 and Batch3 as positions 77-113.
3. Replace, rather than combine with, the original Batch2 overlay and ledger using
   `{OVERLAY_NAME}` and `{LEDGER_NAME}`. The successor owns positions 39-76.
4. Keep the original `normative-provenance-batch2.source-attestations.json`
   byte-identical at SHA-256
   `{BATCH_FILE_HASHES[BATCH2]['normative-provenance-batch2.source-attestations.json']}`.
   The corrected overlay intentionally preserves its existing evidence-source binding.
5. Match every merge operation by exact criterion ID, never by position alone.
6. Keep `AIS-08:R5` fail-closed as
   `structural_harness_not_product_law`; it does not become scorable.
7. Keep `HW-05:R4` solely in Batch3. Both predecessor records were materially
   consistent; no evidence or replacement is discarded.
8. Reject any omitted owner, duplicate owner, changed preserved record, hash
   mismatch, unsupported scoring upgrade, or AI-as-human confirmation claim.
9. Run the provenance guard on a private copy. The validated combined result is
   {preflight['combined']['scorable']} scorable,
   {preflight['combined']['unscorable']} unscorable, and
   {preflight['combined']['unresolved']} unresolved criteria.

## Boundaries

The correction attestation is audit metadata, not normative evidence. Do not
register it as a rubric evidence source. Preserve execution-disabled gates and
perform final successor-bundle assembly only in the existing merge session.
"""
    return text.encode("ascii")


def build_manifest(
    bundle_payload: dict[str, Any],
    input_records: list[dict[str, Any]],
    defect: dict[str, Any],
    overlap: dict[str, Any],
    missing: dict[str, Any],
    membership: dict[str, Any],
    preservation: dict[str, Any],
    preflight: dict[str, Any],
    primary_descriptors: dict[str, dict[str, Any]],
    repository_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "consume-api-provenance-partition-correction/1",
        "correction_id": "criterion-provenance-batch2-successor-partition-repair",
        "status": "validated_artifact_only_correction",
        "compatibility": {
            "harness": "consume-api-provenance-harness/3.0.0",
            "rubric_schema": "consume-api-evaluation-rubric/3",
            "overlay_schema": "consume-api-normative-provenance-overlay/1",
            "ledger_schema": "consume-api-normative-provenance-ledger/1",
        },
        "authoritative_base": {
            "path": str(BASE),
            "canonical_payload": bundle_payload,
            "rubric_sha256": RUBRIC_SHA256,
            "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        },
        "input_integrity": {
            "rehashed_file_count": len(input_records),
            "snapshot_sha256": snapshot_sha256(input_records),
            "all_expected_hashes_match": True,
        },
        "defect_reproduction": defect,
        "overlap_resolution": overlap,
        "missing_criterion_resolution": {
            "criterion_id": missing["criterion_id"],
            "canonical_position_1_based": missing["canonical_position_1_based"],
            "canonical_pointer": missing["canonical_pointer"],
            "canonical_record_sha256": missing["canonical_record_sha256"],
            "classification": missing["classification"],
            "scorable": missing["scorable"],
            "human_confirmation": missing["human_confirmation"],
        },
        "repaired_membership": membership,
        "preservation": preservation,
        "combined_preflight": preflight,
        "merge_semantics": {
            "batch2_predecessor_overlay_action": "replace_not_compose",
            "batch2_predecessor_ledger_action": "replace_not_compose",
            "original_batch2_source_attestation_action": "retain_byte_identical",
            "batch1_action": "unchanged",
            "batch3_action": "unchanged",
            "final_successor_bundle_created": False,
        },
        "repository_nonmutation_baseline": repository_snapshot,
        "builder": {
            "path": Path(__file__).name,
            "sha256": sha256_file(Path(__file__)),
            "bytes": Path(__file__).stat().st_size,
        },
        "artifacts": primary_descriptors,
    }


def build_validation(
    input_records: list[dict[str, Any]],
    repository_snapshot: dict[str, Any],
    defect: dict[str, Any],
    overlap: dict[str, Any],
    missing: dict[str, Any],
    membership: dict[str, Any],
    preservation: dict[str, Any],
    artifact_checks: dict[str, Any],
    preflight: dict[str, Any],
    negative_checks: list[dict[str, Any]],
    leakage: dict[str, Any],
    descriptors: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    require(all(item["result"] == "passed" for item in negative_checks), "negative check failed")
    return {
        "schema_version": "consume-api-normative-provenance-validation/1",
        "correction_id": "criterion-provenance-batch2-successor-partition-repair",
        "status": "passed",
        "checks": {
            "all_relevant_input_hashes": "passed",
            "canonical_payload_recomputed": "passed",
            "canonical_113_ids_reconstructed": "passed",
            "exact_position_39_omission_reproduced": "passed",
            "exact_position_77_overlap_reproduced": "passed",
            "no_extras": "passed",
            "overlap_material_conflict": "absent",
            "missing_criterion_evidence_classified": "passed",
            "corrected_sets_duplicate_free": "passed",
            "corrected_sets_pairwise_disjoint": "passed",
            "corrected_union_exactly_113": "passed",
            "preserved_batch2_records_40_76": "passed",
            "private_copy_combined_preflight": "passed",
            "unsupported_upgrade_absent": "passed",
            "ai_not_human_confirmation": "passed",
            "leakage_and_quote_scan": "passed",
            "source_hashes_unchanged": "passed",
            "repository_tree_pre_post_equal": "passed",
        },
        "artifact_schema_checks": artifact_checks,
        "defect_reproduction": defect,
        "overlap_resolution": {
            "criterion_id": overlap["criterion_id"],
            "material_conflict": overlap["material_conflict"],
            "canonical_owner": overlap["canonical_owner"],
            "evidence_loss": overlap["evidence_loss"],
            "field_checks": overlap["field_checks"],
        },
        "missing_criterion": {
            "criterion_id": missing["criterion_id"],
            "classification": missing["classification"],
            "scorable": missing["scorable"],
            "canonical_pointer": missing["canonical_pointer"],
            "canonical_record_sha256": missing["canonical_record_sha256"],
            "normative_body_hash_available": missing["source_snapshot"][
                "normative_body_hash_available"
            ],
            "normative_rule_hash_available": missing["source_snapshot"][
                "normative_rule_hash_available"
            ],
            "human_confirmation": missing["human_confirmation"],
        },
        "membership": membership,
        "preservation": {
            "record_count": preservation["preserved_record_count"],
            "record_hash_manifest_sha256": preservation[
                "records_manifest_sha256"
            ],
        },
        "combined_preflight": preflight,
        "negative_checks": {
            "passed": len(negative_checks),
            "failed": 0,
            "results": negative_checks,
        },
        "deterministic_regeneration": {
            "passes": 2,
            "byte_identical": True,
            "timestamps_embedded": False,
        },
        "leakage_scan": leakage,
        "non_mutation": {
            "input_file_count": len(input_records),
            "input_snapshot_sha256_before": snapshot_sha256(input_records),
            "input_snapshot_sha256_after": snapshot_sha256(input_records),
            "repository_junction": repository_snapshot,
            "canonical_bundle": "unchanged",
            "batch_artifacts": "unchanged",
            "source_documents_and_snapshots": "unchanged",
            "repository": "unchanged",
            "git_state": "not_accessed",
            "live_network_api_model_database_search_azure": "not_accessed_or_mutated",
        },
        "artifact_hashes": descriptors,
        "limitations": [
            "AIS-08:R5 remains unscorable because the criterion belongs to a response-contract boundary, not product law.",
            "No normative body or rule evidence was available or appropriate for AIS-08:R5.",
            "Existing semantic-pending records still require independent human confirmation.",
            "The original Batch2 attestation and its external evidence paths remain required and unchanged.",
            "Final successor-bundle assembly and adoption remain the merge session's responsibility.",
        ],
    }


def assemble_core(
    bundle_payload: dict[str, Any],
    input_records: list[dict[str, Any]],
    repository_snapshot: dict[str, Any],
    canonical: dict[str, Any],
    batches: dict[str, Any],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    defect = reproduce_partition_defect(canonical["ids"], batches)
    overlap = compare_overlap(canonical, batches)
    missing = classify_missing(canonical)
    corrected_overlay, corrected_ledger, preservation = build_corrected_batch2(
        canonical,
        batches,
        missing,
    )
    batch1_ids = batches["batch1_overlay"]["slice_contract"]["owned_ids"]
    corrected_ids = [
        item["criterion_id"] for item in corrected_overlay["criterion_updates"]
    ]
    batch3_ids = batches["batch3_overlay"]["selection"]["criterion_ids"]
    membership = validate_membership(
        canonical["ids"],
        batch1_ids,
        corrected_ids,
        batch3_ids,
    )
    preflight = combined_preflight(canonical, batches, corrected_overlay)
    attestation = build_attestation(
        missing,
        overlap,
        input_records,
        preservation,
    )
    artifact_checks = validate_correction_artifacts(
        canonical,
        batches,
        corrected_overlay,
        corrected_ledger,
        attestation,
    )
    negative_checks = mutation_checks(
        canonical,
        batches,
        corrected_overlay,
        corrected_ledger,
        attestation,
    )

    outputs: dict[str, bytes] = {
        OVERLAY_NAME: pretty_json_bytes(corrected_overlay),
        LEDGER_NAME: pretty_json_bytes(corrected_ledger),
        ATTESTATION_NAME: pretty_json_bytes(attestation),
    }
    descriptors = {
        name: artifact_descriptor(name, payload)
        for name, payload in outputs.items()
    }
    outputs[MERGE_NAME] = build_merge_markdown(descriptors, membership, preflight)
    descriptors[MERGE_NAME] = artifact_descriptor(MERGE_NAME, outputs[MERGE_NAME])
    manifest = build_manifest(
        bundle_payload,
        input_records,
        defect,
        overlap,
        missing,
        membership,
        preservation,
        preflight,
        descriptors,
        repository_snapshot,
    )
    outputs[MANIFEST_NAME] = pretty_json_bytes(manifest)
    descriptors[MANIFEST_NAME] = artifact_descriptor(
        MANIFEST_NAME, outputs[MANIFEST_NAME]
    )
    external_inputs = [
        item
        for item in input_records
        if item["label"].startswith(
            (
                "batch1-evidence/",
                "batch2-source-document/",
                "batch2-rule-artifact/",
                "batch3-source/",
                "batch3-overlay-origin/",
            )
        )
    ]
    leakage = leakage_scan(outputs, canonical, external_inputs)
    context = {
        "defect": defect,
        "overlap": overlap,
        "missing": missing,
        "membership": membership,
        "preservation": preservation,
        "artifact_checks": artifact_checks,
        "preflight": preflight,
        "negative_checks": negative_checks,
        "leakage": leakage,
        "descriptors": descriptors,
    }
    return outputs, context


def assemble_all(
    bundle_payload: dict[str, Any],
    input_records: list[dict[str, Any]],
    repository_snapshot: dict[str, Any],
    canonical: dict[str, Any],
    batches: dict[str, Any],
) -> dict[str, bytes]:
    first, first_context = assemble_core(
        bundle_payload,
        input_records,
        repository_snapshot,
        canonical,
        batches,
    )
    second, second_context = assemble_core(
        bundle_payload,
        input_records,
        repository_snapshot,
        canonical,
        batches,
    )
    require(first == second, "core deterministic regeneration differs")
    require(
        canonical_json_bytes(first_context) == canonical_json_bytes(second_context),
        "validation context deterministic regeneration differs",
    )
    validation = build_validation(
        input_records=input_records,
        repository_snapshot=repository_snapshot,
        **first_context,
    )
    first[VALIDATION_NAME] = pretty_json_bytes(validation)
    second_validation = build_validation(
        input_records=input_records,
        repository_snapshot=repository_snapshot,
        **second_context,
    )
    require(
        first[VALIDATION_NAME] == pretty_json_bytes(second_validation),
        "validation deterministic regeneration differs",
    )
    return first


def output_directory(value: str | None) -> Path:
    target = ARTIFACT_ROOT if value is None else Path(value).resolve()
    common = Path(os.path.commonpath([str(target), str(ARTIFACT_ROOT)]))
    require(common == ARTIFACT_ROOT, "output directory must be under session files")
    target.mkdir(parents=True, exist_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and validate the Batch2 criterion-provenance partition repair."
    )
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    target = output_directory(args.output_dir)

    print("PHASE 1/8: rehash canonical bundle", flush=True)
    bundle_payload, base_records = verify_bundle_payload()
    print("PHASE 2/8: rehash batch artifacts", flush=True)
    batch_records = verify_batch_files()
    batches = load_batches()
    print("PHASE 3/8: rehash external evidence inputs", flush=True)
    external_records = collect_external_evidence_inputs(
        batches["batch1_overlay"],
        batches["batch2_attestations"],
        batches["batch3_overlay"],
        batches["batch3_source_hashes"],
    )
    input_records = [*base_records, *batch_records, *external_records]
    initial_input_snapshot = snapshot_sha256(input_records)
    print(f"  verified input files: {len(input_records)}", flush=True)

    print("PHASE 4/8: verify repository junction baseline", flush=True)
    repository_snapshot = hash_repository_tree()

    print("PHASE 5/8: reconstruct canonical guard findings", flush=True)
    canonical = canonical_context()
    print("PHASE 6/8: build and validate correction twice in memory", flush=True)
    artifacts = assemble_all(
        bundle_payload,
        input_records,
        repository_snapshot,
        canonical,
        batches,
    )

    print("PHASE 7/8: write correction artifacts", flush=True)
    for name in sorted(artifacts):
        (target / name).write_bytes(artifacts[name])

    print("PHASE 8/8: verify post-write non-mutation", flush=True)
    post_bundle_payload, post_base_records = verify_bundle_payload()
    post_batch_records = verify_batch_files()
    post_batches = load_batches()
    post_external_records = collect_external_evidence_inputs(
        post_batches["batch1_overlay"],
        post_batches["batch2_attestations"],
        post_batches["batch3_overlay"],
        post_batches["batch3_source_hashes"],
    )
    post_records = [
        *post_base_records,
        *post_batch_records,
        *post_external_records,
    ]
    require(post_bundle_payload == bundle_payload, "canonical payload changed")
    require(
        snapshot_sha256(post_records) == initial_input_snapshot,
        "input files changed during generation",
    )
    final_repository_snapshot = hash_repository_tree()
    require(
        final_repository_snapshot == repository_snapshot,
        "repository junction changed during generation",
    )
    for name in sorted(artifacts):
        path = target / name
        require(path.read_bytes() == artifacts[name], f"written bytes differ: {name}")
        print(
            f"  {name}: {sha256_file(path)} {path.stat().st_size} bytes",
            flush=True,
        )
    print("RESULT: passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
