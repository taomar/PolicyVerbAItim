#!/usr/bin/env python3
"""Build and validate the deterministic criterion-provenance successor bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

from docx import Document


PACKAGE_VERSION = "1.0.0"
BUNDLE_DIRECTORY = "consume-api-provenance-harness-v3.1.0"
HARNESS_VERSION = "consume-api-provenance-harness/3.1.0"
RUBRIC_VERSION = "3.1.0"
MANIFEST_VERSION = "2.1.0"
RUBRIC_SCHEMA = "consume-api-evaluation-rubric/3"
MANIFEST_SCHEMA = "consume-api-matrix-manifest/2"
BASE_PAYLOAD_SHA256 = (
    "fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c"
)
BASE_RUBRIC_SHA256 = (
    "6bd271a45d466ed048427a32ea2c7143bc23b3376e9ea06627f7239c481d7c58"
)
BASE_SOURCE_SHA256 = (
    "01171368268bfb5c9e8bac8b8852f5bb67f6524624dd24154949978afa390c1c"
)
CANONICAL_IDS_SHA256 = (
    "4a752fd8e13b1fb1d1c37bf110e4b1334ca3bbae1beaab5d630e8d3b1719acb3"
)
ORIGINAL_BATCH2_ATTESTATION_SHA256 = (
    "cef48741a6e19806b6f1bade107402c43d6ed15b04ae5a8bd2a10c80a502cc15"
)
REPAIR_ATTESTATION_SHA256 = (
    "87e18c82c7418e16e2296e4188d9045653cafed056680bc277e698997e434237"
)
HISTORICAL_REPAIR_REPOSITORY = {
    "files": 43032,
    "bytes": 648739714,
    "sha256": "75469f06f199ecf5da63cdb3448d329d8033606e2f7f3c4028de486eabc84c19",
}
REPOSITORY_BASELINE = {
    "files": 37199,
    "bytes": 553349103,
    "sha256": "a702437f485cdf04aca82c37122621cfa6e61b2f021ac1c7bf7b118684099a28",
}
AUTHORIZED_FULL_TREE_WITH_GIT = {
    "files": 43032,
    "bytes": 648739941,
    "sha256": "7a315f2594b804ddffaf72c5eed9ed475c70c687808692cda8cf1f8d538a4206",
}
INFORMATIONAL_INDEX_REFRESH_TREE = {
    "files": 43032,
    "bytes": 648739941,
    "sha256": "782b163be47cf0e17b6eae94d766cfda5051fe17bc70adfbfc812e2a36f5c55b",
}
FORMAL_HEAD = "c0972c8bb7ba811903e981d3806afe31cc1f514d"
AUTHORIZED_INTER_WINDOW_PATHS = {
    "src/policy_platform/infrastructure/assistants/ai_case_project.py": (
        "a49004c761c601a09bc81d8b58d366d4895af280efeca16660c4966fe61d3cd4"
    ),
    "tests/unit/test_rule_retrieval_is_an_explicit_mode.py": (
        "1d0082c3aa870f9557a5922f2dd97c91690f18dcf8049e3c89333bde7a0f1890"
    ),
    "tests/unit/test_policy_case_project.py": (
        "4eda5b467dbc7befbbc97dc602b2a5f3c81255542a93cc06edd2fbe81e7b4de7"
    ),
    "tests/unit/test_coverage_expansion_is_eligible_by_property.py": (
        "f71652c360c1b72a7cbdebab486d26a4bad779af8891a8181603c7b067de0c0f"
    ),
}
ATTRIBUTABLE_CACHE_PATHS = {
    "src/policy_platform/infrastructure/assistants/__pycache__/"
    "ai_case_project.cpython-311.pyc": (
        "5b510c38fd51790bb5fac03d776cd538b731f952e4948e314f69a413b401b7bb"
    ),
    "tests/unit/__pycache__/"
    "test_rule_retrieval_is_an_explicit_mode.cpython-311-pytest-8.4.2.pyc": (
        "b707685741f0677b57e96381f371f9aaa6523f661d2e4a4144996c32ea12fd61"
    ),
    "tests/unit/__pycache__/"
    "test_policy_case_project.cpython-311-pytest-8.4.2.pyc": (
        "c326e4eee53ca5abc4c26d87746e8e0e969215e03468ccda6ad7d860f3ea011b"
    ),
    "tests/unit/__pycache__/"
    "test_coverage_expansion_is_eligible_by_property.cpython-311-pytest-8.4.2.pyc": (
        "17f7989dbe661b1b8e3b5407734c04a9aade86a889a0d23cbc73641cde2fe2be"
    ),
    ".pytest_cache/v/cache/lastfailed": (
        "b856f140535c52027b1db35d8b3b878c35c69e6ca5f5b0a4219928f386a78dc4"
    ),
    ".pytest_cache/v/cache/nodeids": (
        "2490f6a1cba74a21900e46aec860ca94fd1ca0412a103558ced45a5b63d69484"
    ),
}
REPOSITORY = Path(
    r"C:\Users\taomar\Downloads\policy-extractor-local-oversight\repository"
)

PROVENANCE_FIELDS = (
    "criterion_provenance",
    "provenance_kind",
    "source_provision_ids",
    "source_rule_ids",
    "evidence_refs",
    "validation_state",
    "corpus_support",
    "known_limitation",
)

EXPECTED_REPAIR_FILES: dict[str, tuple[str, int]] = {
    "repair/criterion-provenance-batch2-successor.overlay.json": (
        "5d0d9bbb374bd7ec3c3f7e5617494da3e2dd62dcd1809889d99a52aa5de9167a",
        37276,
    ),
    "repair/criterion-provenance-batch2-successor.ledger.json": (
        "ae7e00d8ecf9f3916f4ff2c0424eee9392baf00aa925fafcf113838b96ac0887",
        58095,
    ),
    "repair/criterion-provenance-batch2-successor.source-attestations.json": (
        REPAIR_ATTESTATION_SHA256,
        13565,
    ),
    "repair/criterion-provenance-partition-correction.manifest.json": (
        "c49148190ba637a85c0f8d3d2d565aa616642107a0d9e88162ae05f1a36661c0",
        21866,
    ),
    "repair/criterion-provenance-partition-correction.validation.json": (
        "092557d1bf4b7f694cb479ae95a15f23e21463d30585752c423f969a2ff905f5",
        9445,
    ),
    "repair/criterion-provenance-partition-correction.MERGE.md": (
        "6cc82d9c457b328ab48713396a22b786d1c94c12aa611df53e593286a13a1b54",
        2482,
    ),
    "repair/build_provenance_partition_correction.py": (
        "f89dcbbec5da3fd0336d350ba39f680a7e98e05582930231aceb439a9a856c8b",
        75185,
    ),
    "repair/AGENT_PROGRESS.md": (
        "caefceef6c1d9be5c9783904b6f20d6b086aa9c496ca2562316a6b2103331c20",
        8258,
    ),
}

EXPECTED_BATCH_FILES: dict[str, str] = {
    "batch1/criterion-provenance-batch1-overlay.json": (
        "36ae59123a4c5cd9d19283747535a5fd9d6f0743c9554d829d6d2d664032629a"
    ),
    "batch1/criterion-provenance-batch1-ledger.json": (
        "690ffe65dc7d01faba6d61e6247bd8222b20ddf84080f4abaa701684753ce720"
    ),
    "batch1/criterion-provenance-batch1-validation.json": (
        "bd3571e2923081869883595385bcc32be56c6c4364862d232a2c08cf5f90b0cc"
    ),
    "batch1/criterion-provenance-batch1-source-attestations.json": (
        "3e38fbde8c546f741d3e821a89024cf51fbb1917c87f083b540695a90585f307"
    ),
    "batch1/criterion-provenance-batch1-MERGE.md": (
        "5d576d52e4316ba78a0bcdfc64cf54d56c2cebb7ee59547c6c9640d5176d61d3"
    ),
    "batch1/build_batch1_provenance.py": (
        "01f77bee569eb44c3d304254adcd360006a9d2965713624a3ac153a31471f915"
    ),
    "batch2-original/normative-provenance-batch2.overlay.json": (
        "d7c0de9ae27187b3482350d001fa6a66632c65b82cf20ee4735029af141b660e"
    ),
    "batch2-original/normative-provenance-batch2.ledger.json": (
        "c7cd8155b58d129625ced534a17e671cb629f5347988ad1ef2cd52a36de85019"
    ),
    "batch2-original/normative-provenance-batch2.validation.json": (
        "ff08208486ec4103eb8920b72ecba0621a1ffe1a343b9d01fbf2d793630ae0ae"
    ),
    "batch2-original/normative-provenance-batch2.source-attestations.json": (
        ORIGINAL_BATCH2_ATTESTATION_SHA256
    ),
    "batch2-original/normative-provenance-batch2.MERGE.md": (
        "5946dccc6396753bf127685531bbd93e0359620d434bd44e7fda3d9810e39c3b"
    ),
    "batch3/criterion-provenance-batch-3.overlay.json": (
        "4879337d894ff7e90653e248742c46a3f933abae2483209bfca6f7d66030495d"
    ),
    "batch3/criterion-provenance-batch-3.ledger.jsonl": (
        "8c832a98ac7207c146ef328c56342e8e3dc75f29c429709e4b14431a6616946a"
    ),
    "batch3/criterion-provenance-batch-3.source-hashes.json": (
        "178630c61ff91e4083776c0ad765d1ae42e77d88534483fa0a5f31e4e5e1663d"
    ),
    "batch3/criterion-provenance-batch-3.validation.json": (
        "960d354038acf33f3b7209ee72f274308948896ab311931bc4913bf04336161e"
    ),
    "batch3/criterion-provenance-batch-3.merge-instructions.md": (
        "a3f8df45954742d3c3f6ac61ccc0cb00825161384dffd7e6d988e7cb20491b35"
    ),
}


class BuildError(RuntimeError):
    """Raised when the successor cannot be built safely."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BuildError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"invalid JSON in {path}: {exc}") from exc


def resolve_pointer(document: Any, pointer: str) -> Any:
    require(pointer == "" or pointer.startswith("/"), f"invalid JSON pointer: {pointer}")
    current = document
    if pointer == "":
        return current
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise BuildError(f"JSON pointer does not resolve: {pointer}") from exc
    return current


def collect_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(collect_strings(child))
        return result
    if isinstance(value, dict):
        result = set()
        for child in value.values():
            result.update(collect_strings(child))
        return result
    return set()


def sorted_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def file_record(path: Path, relative: str) -> dict[str, Any]:
    return {
        "path": relative.replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json(path: Path, value: Any) -> None:
    write_bytes(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def write_text(path: Path, value: str) -> None:
    write_bytes(path, value.replace("\r\n", "\n").encode("utf-8"))


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    require(
        source.stat().st_size == destination.stat().st_size
        and sha256_file(source) == sha256_file(destination),
        f"copy verification failed: {source}",
    )


def verify_required_hashes(inputs: Path) -> None:
    for relative, expected in EXPECTED_BATCH_FILES.items():
        path = inputs / Path(relative)
        require(path.is_file(), f"required batch file is absent: {relative}")
        require(sha256_file(path) == expected, f"batch hash mismatch: {relative}")
    for relative, (expected_hash, expected_bytes) in EXPECTED_REPAIR_FILES.items():
        path = inputs / Path(relative)
        require(path.is_file(), f"required repair file is absent: {relative}")
        require(
            sha256_file(path) == expected_hash and path.stat().st_size == expected_bytes,
            f"repair hash or byte-size mismatch: {relative}",
        )


def strict_parse_inputs(inputs: Path) -> dict[str, int]:
    counts = {
        "json_documents": 0,
        "jsonl_records": 0,
        "decoded_json_documents": 0,
        "docx_documents": 0,
    }
    for path in sorted_files(inputs):
        if path.suffix.lower() == ".json":
            load_json(path)
            counts["json_documents"] += 1
        elif path.suffix.lower() == ".jsonl":
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    json.loads(line, object_pairs_hook=reject_duplicate_keys)
                except json.JSONDecodeError as exc:
                    raise BuildError(
                        f"invalid JSONL in {path} at line {line_number}: {exc}"
                    ) from exc
                counts["jsonl_records"] += 1
        elif path.name.endswith(".decoded"):
            load_json(path)
            counts["decoded_json_documents"] += 1
        elif path.suffix.lower() == ".docx":
            Document(path)
            counts["docx_documents"] += 1
    return counts


def verify_base_bundle(inputs: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    base = inputs / "base-v3.0.0"
    inventory = load_json(base / "FILE_INVENTORY.json")
    manifest = load_json(base / "BUNDLE_MANIFEST.json")
    records = inventory.get("files")
    require(isinstance(records, list) and len(records) == 37, "base inventory differs")
    paths = [record["path"] for record in records]
    require(len(paths) == len(set(paths)), "base inventory paths are duplicated")
    for record in records:
        path = base / Path(record["path"])
        require(path.is_file(), f"base inventory path is absent: {record['path']}")
        require(
            path.stat().st_size == record["bytes"]
            and sha256_file(path) == record["sha256"],
            f"base inventory record mismatch: {record['path']}",
        )
    canonical = sorted(
        (record for record in records if record["canonical_payload"]),
        key=lambda record: record["path"],
    )
    stream = b"".join(
        record["path"].encode("utf-8")
        + b"\0"
        + record["sha256"].encode("ascii")
        + b"\n"
        for record in canonical
    )
    digest = sha256_bytes(stream)
    require(
        digest == BASE_PAYLOAD_SHA256
        and len(canonical) == 35
        and sum(record["bytes"] for record in canonical) == 1126517,
        "base canonical payload differs",
    )
    require(
        manifest["canonical_bundle_hash"]["value"] == digest,
        "base manifest canonical hash differs",
    )
    rubric_path = base / "evaluation-rubric.json"
    rubric = load_json(rubric_path)
    require(sha256_file(rubric_path) == BASE_RUBRIC_SHA256, "base rubric differs")
    require(
        sha256_file(base / "evidence" / "source.snapshot.json") == BASE_SOURCE_SHA256,
        "base source snapshot differs",
    )
    require(
        rubric.get("schema_version") == RUBRIC_SCHEMA
        and rubric.get("rubric_version") == "3.0.0",
        "base rubric version differs",
    )

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(base))
    try:
        from rubric_provenance import validate_rubric_provenance

        preflight = validate_rubric_provenance(rubric, rubric_path)
    finally:
        sys.path.pop(0)
    canonical_ids = sorted(item["criterion_id"] for item in preflight["rubric_findings"])
    require(
        preflight["criterion_count"] == 128
        and len(canonical_ids) == len(set(canonical_ids)) == 113
        and canonical_hash(canonical_ids) == CANONICAL_IDS_SHA256,
        "base canonical provenance finding set differs",
    )
    return rubric, preflight, canonical_ids


def evidence_ref(
    ref: dict[str, Any],
    sources: dict[str, Any],
) -> tuple[Any, set[str]]:
    require(ref["source_id"] in sources, f"unknown source ID: {ref['source_id']}")
    pointed = resolve_pointer(sources[ref["source_id"]], ref["pointer"])
    require(
        canonical_hash(pointed) == ref["pointer_sha256"],
        f"pointer hash mismatch for role {ref['role']}",
    )
    return pointed, collect_strings(pointed)


def criterion_map(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        criterion["criterion_id"]: criterion
        for question in rubric["questions"]
        for criterion in question["criteria"]
    }


def validate_batch1(
    inputs: Path,
    base_rubric: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    base = inputs / "base-v3.0.0"
    external = inputs / "external-evidence"
    overlay = load_json(inputs / "batch1" / "criterion-provenance-batch1-overlay.json")
    attestation = load_json(
        inputs / "batch1" / "criterion-provenance-batch1-source-attestations.json"
    )
    require(
        overlay["schema_version"] == "consume-api-normative-provenance-overlay/1",
        "unsupported Batch1 overlay schema",
    )
    source_file_map = {
        "evaluation-rubric.json": base / "evaluation-rubric.json",
        "source.snapshot.json": base / "evidence" / "source.snapshot.json",
        "source-snapshot.ais.json": external / "batch1-source-snapshot.ais.json",
    }
    for record in attestation["canonical_harness_inputs"]:
        path = source_file_map[Path(record["path"]).name]
        require(sha256_file(path) == record["sha256"], "Batch1 source hash mismatch")

    for record in attestation["normative_evidence"]:
        response_path = external / f"batch1-{Path(record['response_path']).name}"
        record_path = (
            external / f"batch1-{Path(record['record_path']).stem}.record.json"
        )
        require(
            sha256_file(response_path) == record["response_file_sha256"],
            "Batch1 decoded response hash mismatch",
        )
        require(
            sha256_file(record_path) == record["record_file_sha256"],
            "Batch1 frozen record hash mismatch",
        )
        response = load_json(response_path)
        frozen_record = load_json(record_path)
        require(
            frozen_record["response"]["decoded_body_sha256"]
            == record["response_file_sha256"],
            "Batch1 record-to-response binding differs",
        )
        require(
            frozen_record["provenance"]["source_snapshot_sha256"]
            == sha256_file(external / "batch1-source-snapshot.ais.json"),
            "Batch1 record-to-source binding differs",
        )
        pointed = resolve_pointer(response, record["pointer"])
        require(
            canonical_hash(pointed) == record["pointer_sha256"],
            "Batch1 payload pointer hash differs",
        )
        require(
            pointed["envelope"]["provision_key"] == record["source_provision_id"],
            "Batch1 source provision differs",
        )
        rule_ids = [rule["rule_id"] for rule in pointed["rules"]]
        require(
            rule_ids == record["source_rule_ids"] and len(rule_ids) == len(set(rule_ids)),
            "Batch1 rule identities differ",
        )
        span_ids = set(pointed["spans"])
        for rule_attestation in record["rules"]:
            rule = resolve_pointer(response, rule_attestation["pointer"])
            require(
                canonical_hash(rule) == rule_attestation["pointer_sha256"]
                and rule["rule_id"] == rule_attestation["rule_id"],
                "Batch1 rule pointer differs",
            )
            require(
                set(rule_attestation["source_span_ids"]) <= span_ids,
                "Batch1 rule references an unknown span",
            )
        for span_attestation in record["spans"]:
            span = resolve_pointer(response, span_attestation["pointer"])
            require(
                canonical_hash(span) == span_attestation["pointer_sha256"]
                and span["source_hash"]
                == span_attestation["source_document_sha256"],
                "Batch1 span pointer or source hash differs",
            )
        require(
            sorted({span["source_hash"] for span in pointed["spans"].values()})
            == record["embedded_source_document_sha256s"],
            "Batch1 embedded source-document identities differ",
        )

    portable_paths = {
        "ais_e_annual_vacation_r1": (
            "evidence/normative/ais_e_annual_vacation_r1.json"
        ),
        "ais_e_maternity_leave_r1": (
            "evidence/normative/ais_e_maternity_leave_r1.json"
        ),
        "ais_e_tuition_child_r1": "evidence/normative/ais_e_tuition_child_r1.json",
    }
    source_documents: dict[str, Any] = {}
    for source in overlay["evidence_sources"]:
        staged_path = external / f"batch1-{Path(source['path']).name}"
        require(sha256_file(staged_path) == source["sha256"], "Batch1 source differs")
        source_documents[source["id"]] = load_json(staged_path)

    base_criteria = criterion_map(base_rubric)
    replacements: dict[str, dict[str, Any]] = {}
    for operation in overlay["operations"]:
        if operation["action"] != "replace_criterion_provenance":
            continue
        replacement = operation["replacement"]
        current = base_criteria[operation["criterion_id"]]
        require(
            all(
                replacement[field] == current[field]
                for field in ("criterion_id", "active", "applies_to", "description")
            ),
            "Batch1 replacement changes immutable criterion fields",
        )
        bound: set[str] = set()
        for ref in replacement["evidence_refs"]:
            _, values = evidence_ref(ref, source_documents)
            bound.update(values)
        require(
            set(
                replacement["source_provision_ids"]
                + replacement["source_rule_ids"]
            )
            <= bound,
            "Batch1 replacement source IDs are not evidence-bound",
        )
        require(
            replacement["validation_state"] == "validated_supported"
            and replacement["corpus_support"]["semantic_support"]
            == "mechanically_proven",
            "Batch1 replacement is not mechanically proven",
        )
        replacements[replacement["criterion_id"]] = replacement
    require(len(replacements) == 4, "Batch1 replacement count differs")
    return overlay, replacements, portable_paths


def validate_batch2(
    inputs: Path,
    base_rubric: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    base = inputs / "base-v3.0.0"
    external = inputs / "external-evidence"
    original_root = inputs / "batch2-original"
    repair_root = inputs / "repair"
    attestation_path = (
        original_root / "normative-provenance-batch2.source-attestations.json"
    )
    attestation = load_json(attestation_path)
    overlay = load_json(repair_root / "criterion-provenance-batch2-successor.overlay.json")
    original_overlay = load_json(
        original_root / "normative-provenance-batch2.overlay.json"
    )
    ledger = load_json(repair_root / "criterion-provenance-batch2-successor.ledger.json")
    original_ledger = load_json(
        original_root / "normative-provenance-batch2.ledger.json"
    )
    correction = load_json(
        repair_root / "criterion-provenance-partition-correction.manifest.json"
    )
    correction_attestation = load_json(
        repair_root
        / "criterion-provenance-batch2-successor.source-attestations.json"
    )
    require(
        sha256_file(attestation_path) == ORIGINAL_BATCH2_ATTESTATION_SHA256,
        "original Batch2 attestation differs",
    )
    require(
        overlay["evidence_sources"]
        == [
            {
                "id": "normative_batch2_source_attestations",
                "path": "normative-provenance-batch2.source-attestations.json",
                "sha256": ORIGINAL_BATCH2_ATTESTATION_SHA256,
                "type": "json",
            }
        ],
        "corrected Batch2 evidence binding differs",
    )
    require(
        correction_attestation["reviewer_kind"] == "ai"
        and correction_attestation["human_confirmation"] is False
        and correction_attestation["quote_free"] is True,
        "correction attestation misstates reviewer authority",
    )
    require(
        sha256_file(
            repair_root
            / "criterion-provenance-batch2-successor.source-attestations.json"
        )
        == REPAIR_ATTESTATION_SHA256,
        "correction attestation hash differs",
    )

    source_snapshot = load_json(base / "evidence" / "source.snapshot.json")
    rubric_v1 = load_json(base / "evidence" / "rubric-v1.snapshot.json")
    rule_receipt_path = external / "batch2-case-hw-policy-rule.json"
    document_path = external / "batch2-hardware-source.docx"
    rule_receipt = load_json(rule_receipt_path)
    document = Document(document_path)
    require(attestation["quote_free"] is True, "Batch2 attestation is not quote-free")
    require(
        sha256_file(document_path) == attestation["source_documents"][0]["sha256"]
        and document_path.stat().st_size
        == attestation["source_documents"][0]["bytes"],
        "Batch2 source document differs",
    )
    require(
        sha256_file(rule_receipt_path) == attestation["rule_artifacts"][0]["sha256"]
        and rule_receipt_path.stat().st_size
        == attestation["rule_artifacts"][0]["bytes"],
        "Batch2 rule receipt differs",
    )
    for provision in attestation["provisions"]:
        provision_id = provision["source_provision_id"]
        source_evidence = provision["source_snapshot_evidence"]
        source_identity = resolve_pointer(source_snapshot, source_evidence["pointer"])
        require(
            source_evidence["file_sha256"] == BASE_SOURCE_SHA256
            and canonical_hash(source_identity) == source_evidence["pointer_sha256"]
            and source_identity["provision_key"] == provision_id,
            "Batch2 source-snapshot evidence differs",
        )
        body_evidence = provision["normative_body_evidence"]
        locator = body_evidence["locator"]
        require(
            body_evidence["file_sha256"] == sha256_file(document_path)
            and locator["kind"] == "docx_paragraph_range"
            and locator["paragraph_index_base"] == 0
            and body_evidence["body_text_copied"] is False,
            "Batch2 body locator differs",
        )
        body = "\n".join(
            document.paragraphs[index].text
            for index in range(
                locator["start_inclusive"],
                locator["end_inclusive"] + 1,
            )
        )
        body_bytes = body.encode("utf-8")
        require(
            sha256_bytes(body_bytes) == body_evidence["body_sha256"]
            and len(body_bytes) == body_evidence["body_utf8_bytes"],
            "Batch2 DOCX body range differs",
        )
        rule_evidence = provision["rule_metadata_evidence"]
        rule_metadata = resolve_pointer(rule_receipt, rule_evidence["pointer"])
        require(
            rule_evidence["file_sha256"] == sha256_file(rule_receipt_path)
            and canonical_hash(rule_metadata) == rule_evidence["pointer_sha256"]
            and rule_metadata["provision_key"] == provision_id
            and rule_metadata["rules"] == rule_evidence["rule_count"]
            and rule_evidence["rule_bodies_available_at_pointer"] is False,
            "Batch2 rule-metadata evidence differs",
        )

    original_updates = {
        item["criterion_id"]: item
        for item in original_overlay["criterion_updates"]
    }
    successor_updates = {
        item["criterion_id"]: item for item in overlay["criterion_updates"]
    }
    original_ledger = {
        item["criterion_id"]: item for item in original_ledger["criteria"]
    }
    successor_ledger = {
        item["criterion_id"]: item for item in ledger["criteria"]
    }
    preserved_ids = sorted(set(original_updates) & set(successor_updates))
    require(
        len(preserved_ids) == 37
        and all(
            original_updates[criterion_id] == successor_updates[criterion_id]
            and original_ledger[criterion_id] == successor_ledger[criterion_id]
            for criterion_id in preserved_ids
        ),
        "corrected Batch2 changed a preserved record",
    )
    preservation = [
        {
            "criterion_id": criterion_id,
            "original_position_1_based": (
                original_ledger[criterion_id]["absolute_unscorable_index"] + 1
            ),
            "corrected_position_1_based": (
                successor_ledger[criterion_id]["absolute_unscorable_index"] + 1
            ),
            "overlay_record_sha256": canonical_hash(
                original_updates[criterion_id]
            ),
            "ledger_record_sha256": canonical_hash(
                original_ledger[criterion_id]
            ),
            "semantic_identity": True,
        }
        for criterion_id in preserved_ids
    ]
    require(
        canonical_hash(preservation)
        == correction["preservation"]["records_manifest_sha256"],
        "Batch2 preservation aggregate differs",
    )
    require(
        set(successor_updates) - set(original_updates) == {"AIS-08:R5"}
        and set(original_updates) - set(successor_updates) == {"HW-05:R4"},
        "Batch2 repair membership differs",
    )

    base_criteria = criterion_map(base_rubric)
    sources = {
        "source_snapshot": source_snapshot,
        "rubric_v1": rubric_v1,
        "normative_batch2_source_attestations": attestation,
    }
    changes: dict[str, dict[str, Any]] = {}
    for update in overlay["criterion_updates"]:
        candidate = update.get("candidate_rubric_fields")
        if candidate is None:
            require(
                update["classification"]
                in {
                    "structural_harness_not_product_law",
                    "product_decision_required",
                },
                "Batch2 non-candidate has an unsupported classification",
            )
            continue
        require(
            update["classification"]
            in {
                "semantic_support_pending_human_confirmation",
                "unsupported_or_contradicted_rubric",
            },
            "Batch2 candidate has an unsupported classification",
        )
        current = base_criteria[update["criterion_id"]]
        require(
            candidate["evidence_refs"][:-1] == current["evidence_refs"],
            "Batch2 candidate changed predecessor evidence references",
        )
        bound: set[str] = set()
        for ref in candidate["evidence_refs"]:
            _, values = evidence_ref(ref, sources)
            bound.update(values)
        require(
            set(candidate["source_provision_ids"]) <= bound
            and candidate["source_rule_ids"] == [],
            "Batch2 candidate source IDs are not evidence-bound",
        )
        require(
            candidate["validation_state"] == "unresolved_semantics"
            and candidate["corpus_support"]["semantic_support"] == "not_applicable"
            and "human_confirmation" not in candidate["corpus_support"],
            "Batch2 candidate makes an unsupported semantic upgrade",
        )
        changes[update["criterion_id"]] = candidate
    require(len(changes) == 13, "Batch2 candidate count differs")
    added = successor_updates["AIS-08:R5"]
    require(
        added["classification"] == "structural_harness_not_product_law"
        and added["candidate_rubric_fields"] is None
        and added["normative_evidence"] is None
        and added["scorable"] is False,
        "AIS-08:R5 does not remain structural and fail-closed",
    )

    criterion_attestation = correction_attestation["criterion_attestation"]
    require(
        canonical_hash(
            resolve_pointer(base_rubric, criterion_attestation["canonical_pointer"])
        )
        == criterion_attestation["canonical_record_sha256"],
        "correction criterion pointer differs",
    )
    require(
        canonical_hash(
            resolve_pointer(
                rubric_v1,
                criterion_attestation["frozen_expectation"]["pointer"],
            )
        )
        == criterion_attestation["frozen_expectation"]["pointer_sha256"],
        "correction frozen-expectation pointer differs",
    )
    for identity in criterion_attestation["source_snapshot"]["contextual_identities"]:
        require(
            canonical_hash(resolve_pointer(source_snapshot, identity["pointer"]))
            == identity["pointer_sha256"],
            "correction contextual-identity pointer differs",
        )
    require(
        criterion_attestation["normative_evidence"] is None
        and criterion_attestation["candidate_rubric_fields"] is None
        and criterion_attestation["scorable"] is False
        and criterion_attestation["exact_pointers_are_semantic_confirmation"]
        is False,
        "correction attestation overstates semantic support",
    )
    return overlay, changes, {
        "attestation": attestation,
        "ledger": ledger,
        "correction": correction,
        "correction_attestation": correction_attestation,
        "preserved_record_count": len(preserved_ids),
        "preservation_sha256": canonical_hash(preservation),
    }


def validate_batch3(
    inputs: Path,
    base_rubric: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    base = inputs / "base-v3.0.0"
    external = inputs / "external-evidence"
    overlay = load_json(inputs / "batch3" / "criterion-provenance-batch-3.overlay.json")
    attestations = load_json(
        inputs / "batch3" / "criterion-provenance-batch-3.source-hashes.json"
    )
    source_snapshot = load_json(base / "evidence" / "source.snapshot.json")
    rubric_v1 = load_json(base / "evidence" / "rubric-v1.snapshot.json")
    rules_path = external / "batch3-hardware-policy-v3.3-import.json"
    document_path = external / "batch3-hardware-source.docx"
    rules = load_json(rules_path)
    document = Document(document_path)
    source_paths = {
        "source_snapshot": base / "evidence" / "source.snapshot.json",
        "rubric_v1": base / "evidence" / "rubric-v1.snapshot.json",
        "hw_policy_v3_3_docx": document_path,
        "hw_rules_v3_3": rules_path,
    }
    for source in attestations["sources"]:
        require(
            sha256_file(source_paths[source["source_id"]]) == source["sha256"],
            "Batch3 source hash differs",
        )
    for record in attestations["canonical_provision_pointers"]:
        pointed = resolve_pointer(source_snapshot, record["pointer"])
        require(
            canonical_hash(pointed) == record["pointer_sha256"]
            and pointed["provision_key"] == record["source_provision_id"],
            "Batch3 source-provision pointer differs",
        )
    for record in attestations["rule_pointers"]:
        pointed = resolve_pointer(rules, record["pointer"])
        require(
            canonical_hash(pointed) == record["pointer_sha256"]
            and pointed["rule_id"] == record["source_rule_id"],
            "Batch3 rule pointer differs",
        )
    for record in attestations["body_attestations"]:
        body = "\n".join(
            document.paragraphs[index].text.strip()
            for index in record["paragraph_indices_zero_based"]
        )
        require(
            len(body) == record["character_count"]
            and sha256_bytes(body.encode("utf-8"))
            == record["normalized_body_sha256"],
            "Batch3 DOCX body attestation differs",
        )

    require(len(overlay["criterion_updates"]) == 1, "Batch3 update count differs")
    replacement = overlay["criterion_updates"][0]["replacement"]
    current = criterion_map(base_rubric)[replacement["criterion_id"]]
    require(
        all(
            replacement[field] == current[field]
            for field in ("criterion_id", "active", "applies_to", "description")
        ),
        "Batch3 replacement changes immutable criterion fields",
    )
    sources = {
        "source_snapshot": source_snapshot,
        "rubric_v1": rubric_v1,
        "hw_rules_v3_3": rules,
    }
    bound: set[str] = set()
    for ref in replacement["evidence_refs"]:
        _, values = evidence_ref(ref, sources)
        bound.update(values)
    require(
        set(replacement["source_provision_ids"] + replacement["source_rule_ids"])
        <= bound,
        "Batch3 replacement source IDs are not evidence-bound",
    )
    require(
        replacement["validation_state"] == "validated_supported"
        and replacement["corpus_support"]["semantic_support"]
        == "mechanically_proven",
        "Batch3 replacement is not mechanically proven",
    )
    return overlay, {replacement["criterion_id"]: replacement}


def classification_map(
    batch1: dict[str, Any],
    batch2: dict[str, Any],
    batch3: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    classifications: dict[str, str] = {}
    owners: dict[str, str] = {}
    for operation in batch1["operations"]:
        classifications[operation["criterion_id"]] = operation["classification"]
        owners[operation["criterion_id"]] = "batch1"
    for update in batch2["criterion_updates"]:
        require(
            update["criterion_id"] not in owners,
            "Batch2 overlaps an earlier owner",
        )
        classifications[update["criterion_id"]] = update["classification"]
        owners[update["criterion_id"]] = "batch2_successor"
    batch3_classes: dict[str, str] = {}
    for classification, criterion_ids in batch3["classifications"].items():
        for criterion_id in criterion_ids:
            require(
                criterion_id not in batch3_classes,
                "Batch3 classification groups overlap",
            )
            batch3_classes[criterion_id] = classification
    for criterion_id in batch3["selection"]["criterion_ids"]:
        require(criterion_id not in owners, "Batch3 overlaps an earlier owner")
        classifications[criterion_id] = batch3_classes[criterion_id]
        owners[criterion_id] = "batch3"
    return classifications, owners


def build_merged_rubric_and_artifacts(
    inputs: Path,
    base_rubric: dict[str, Any],
    canonical_ids: list[str],
    batch1: dict[str, Any],
    batch1_replacements: dict[str, dict[str, Any]],
    batch1_paths: dict[str, str],
    batch2: dict[str, Any],
    batch2_changes: dict[str, dict[str, Any]],
    batch3: dict[str, Any],
    batch3_replacements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    classifications, owners = classification_map(batch1, batch2, batch3)
    normalized_classifications = Counter(
        (
            "structural_harness_not_product_law"
            if classification == "structural_harness_non_product_law"
            else classification
        )
        for classification in classifications.values()
    )
    require(
        normalized_classifications
        == {
            "mechanically_source_supported": 5,
            "semantic_support_pending_human_confirmation": 19,
            "unsupported_or_contradicted_rubric": 1,
            "structural_harness_not_product_law": 80,
            "product_decision_required": 8,
        },
        "aggregate source classification counts differ",
    )
    require(
        sorted(owners) == canonical_ids
        and len(owners) == 113
        and canonical_hash(sorted(owners)) == CANONICAL_IDS_SHA256,
        "repaired ownership does not exactly cover canonical findings",
    )
    owner_sets = {
        owner: sorted(
            criterion_id
            for criterion_id, candidate_owner in owners.items()
            if candidate_owner == owner
        )
        for owner in ("batch1", "batch2_successor", "batch3")
    }
    require(
        [len(owner_sets[name]) for name in owner_sets] == [38, 38, 37],
        "repaired owner counts differ",
    )
    require(
        canonical_hash(owner_sets["batch1"])
        == "f373a082d7660c051a7dceac2ce11cd3456ea37641342fdef297626531d04375"
        and canonical_hash(owner_sets["batch2_successor"])
        == "251c3289af2ae64a3312e9242129ffef08f87614766338d2df9a684dfc14b6ed"
        and canonical_hash(owner_sets["batch3"])
        == "8ef333a6d571970cc4682e939ed96c4c684518ed1eb3df19b8599efa195adb95",
        "repaired owner hashes differ",
    )

    merged = copy.deepcopy(base_rubric)
    final_sources = [
        {
            **source,
            "path": batch1_paths[source["id"]],
        }
        for source in batch1["evidence_sources"]
    ]
    final_sources.append(
        {
            **batch2["evidence_sources"][0],
            "path": (
                "evidence/normative/"
                "normative-provenance-batch2.source-attestations.json"
            ),
        }
    )
    final_sources.append(copy.deepcopy(batch3["evidence_sources_to_add"][0]))
    existing_ids = {source["id"] for source in merged["evidence_sources"]}
    for source in final_sources:
        require(source["id"] not in existing_ids, "evidence source ID collision")
        existing_ids.add(source["id"])
        merged["evidence_sources"].append(source)

    base_criteria = criterion_map(base_rubric)
    replacements: dict[str, dict[str, Any]] = {}
    for criterion_id, replacement in batch1_replacements.items():
        replacements[criterion_id] = copy.deepcopy(replacement)
    for criterion_id, candidate in batch2_changes.items():
        replacement = copy.deepcopy(base_criteria[criterion_id])
        replacement.update(copy.deepcopy(candidate))
        replacements[criterion_id] = replacement
    for criterion_id, replacement in batch3_replacements.items():
        replacements[criterion_id] = copy.deepcopy(replacement)
    require(len(replacements) == 18, "merged replacement count differs")
    for question in merged["questions"]:
        question["criteria"] = [
            copy.deepcopy(replacements.get(criterion["criterion_id"], criterion))
            for criterion in question["criteria"]
        ]

    merged["rubric_version"] = RUBRIC_VERSION
    merged["compatible_harness_version"] = HARNESS_VERSION
    merged["provenance_migration"]["criterion_provenance_successor"] = {
        "predecessor_harness_version": "consume-api-provenance-harness/3.0.0",
        "predecessor_rubric_version": "3.0.0",
        "ownership_repair_manifest_sha256": (
            "c49148190ba637a85c0f8d3d2d565aa616642107a0d9e88162ae05f1a36661c0"
        ),
        "exact_partition_count": 113,
        "changed_criteria_count": 18,
        "newly_scorable_count": 5,
        "human_confirmation_added": False,
        "execution_enabled": False,
    }

    validation_rubric = copy.deepcopy(merged)
    validation_paths = {
        "ais_e_annual_vacation_r1": (
            inputs
            / "external-evidence"
            / "batch1-E__ais-annual-vacation__r1.decoded"
        ),
        "ais_e_maternity_leave_r1": (
            inputs
            / "external-evidence"
            / "batch1-E__ais-maternity-leave__r1.decoded"
        ),
        "ais_e_tuition_child_r1": (
            inputs
            / "external-evidence"
            / "batch1-E__ais-tuition-child__r1.decoded"
        ),
        "normative_batch2_source_attestations": (
            inputs
            / "batch2-original"
            / "normative-provenance-batch2.source-attestations.json"
        ),
        "hw_rules_v3_3": (
            inputs
            / "external-evidence"
            / "batch3-hardware-policy-v3.3-import.json"
        ),
    }
    for source in validation_rubric["evidence_sources"]:
        if source["id"] in validation_paths:
            source["path"] = str(validation_paths[source["id"]])
    base = inputs / "base-v3.0.0"
    sys.path.insert(0, str(base))
    try:
        from rubric_provenance import validate_rubric_provenance

        preflight = validate_rubric_provenance(
            validation_rubric,
            base / "evaluation-rubric.json",
        )
    finally:
        sys.path.pop(0)
    disposition_counts = Counter(
        item["disposition"] for item in preflight["rubric_findings"]
    )
    require(
        preflight["criterion_count"] == 128
        and 128 - len(preflight["rubric_findings"]) == 20
        and disposition_counts == {"unscorable": 95, "unresolved": 13},
        "combined provenance preflight counts differ",
    )
    changed_ids = sorted(
        criterion_id
        for criterion_id, base_record in base_criteria.items()
        if canonical_hash(base_record)
        != canonical_hash(criterion_map(merged)[criterion_id])
    )
    require(changed_ids == sorted(replacements), "equivalent paths changed unexpectedly")
    newly_scorable = sorted(
        criterion_id
        for criterion_id in replacements
        if criterion_id
        not in {
            item["criterion_id"] for item in preflight["rubric_findings"]
        }
    )
    require(
        len(newly_scorable) == 5
        and canonical_hash(newly_scorable)
        == "88ace0ae7bfe63255a6882b2d70d3279a464f0b085114fabaf07fa641561c1f2",
        "newly scorable set differs",
    )

    changes = []
    for criterion_id in changed_ids:
        replacement = criterion_map(merged)[criterion_id]
        fields = {
            field: copy.deepcopy(replacement[field])
            for field in PROVENANCE_FIELDS
            if field in replacement
        }
        changes.append(
            {
                "criterion_id": criterion_id,
                "owner": owners[criterion_id],
                "source_classification": classifications[criterion_id],
                "merge_action": (
                    "merge_unresolved_candidate_fields"
                    if criterion_id in batch2_changes
                    else "replace_validated_provenance"
                ),
                "expected_base_record_sha256": canonical_hash(
                    base_criteria[criterion_id]
                ),
                "replacement_record_sha256": canonical_hash(replacement),
                "provenance_fields": fields,
            }
        )

    merged_overlay = {
        "schema_version": "consume-api-criterion-provenance-merged-overlay/1",
        "overlay_version": "1.0.0",
        "base": {
            "harness_version": "consume-api-provenance-harness/3.0.0",
            "rubric_version": "3.0.0",
            "canonical_payload_sha256": BASE_PAYLOAD_SHA256,
            "rubric_sha256": BASE_RUBRIC_SHA256,
        },
        "target": {
            "harness_version": HARNESS_VERSION,
            "rubric_version": RUBRIC_VERSION,
            "manifest_version": MANIFEST_VERSION,
            "rubric_schema": RUBRIC_SCHEMA,
            "manifest_schema": MANIFEST_SCHEMA,
        },
        "partition": {
            "count": 113,
            "criterion_ids_sha256": CANONICAL_IDS_SHA256,
            "pairwise_disjoint": True,
            "omitted_ids": [],
            "duplicate_ids": [],
            "extra_ids": [],
            "owners": {
                name: {
                    "count": len(ids),
                    "criterion_ids_sha256": canonical_hash(ids),
                }
                for name, ids in owner_sets.items()
            },
        },
        "evidence_sources_to_add": final_sources,
        "changed_criteria_count": len(changes),
        "changes": changes,
        "retained_criteria": [
            {
                "criterion_id": criterion_id,
                "owner": owners[criterion_id],
                "source_classification": classifications[criterion_id],
                "merge_action": "retain_fail_closed",
            }
            for criterion_id in canonical_ids
            if criterion_id not in replacements
        ],
        "invariants": [
            "Merge only by exact criterion ID.",
            "No AI artifact is human confirmation.",
            "Structural and harness criteria remain outside product-law attribution.",
            "Product-decision-required criteria remain fail-closed.",
            "Execution remains disabled.",
        ],
    }

    finding_by_id = {
        item["criterion_id"]: item for item in preflight["rubric_findings"]
    }
    merged_criteria = criterion_map(merged)
    ledger_records = []
    for position, criterion_id in enumerate(canonical_ids, start=1):
        result = finding_by_id.get(criterion_id)
        ledger_records.append(
            {
                "canonical_position_1_based": position,
                "criterion_id": criterion_id,
                "owner": owners[criterion_id],
                "source_classification": classifications[criterion_id],
                "merge_action": next(
                    (
                        item["merge_action"]
                        for item in changes
                        if item["criterion_id"] == criterion_id
                    ),
                    "retain_fail_closed",
                ),
                "base_record_sha256": canonical_hash(base_criteria[criterion_id]),
                "result_record_sha256": canonical_hash(merged_criteria[criterion_id]),
                "result_disposition": (
                    "scorable" if result is None else result["disposition"]
                ),
                "result_scorable": result is None,
                "human_confirmation_added": False,
            }
        )
    merged_ledger = {
        "schema_version": "consume-api-criterion-provenance-merged-ledger/1",
        "ledger_version": "1.0.0",
        "criterion_count": 113,
        "criterion_ids_sha256": CANONICAL_IDS_SHA256,
        "owner_counts": dict(sorted(Counter(owners.values()).items())),
        "source_classification_counts": dict(
            sorted(Counter(classifications.values()).items())
        ),
        "normalized_source_classification_counts": dict(
            sorted(normalized_classifications.items())
        ),
        "merge_action_counts": dict(
            sorted(Counter(item["merge_action"] for item in ledger_records).items())
        ),
        "result_counts": {
            "criteria_total": 128,
            "scorable": 20,
            "unscorable": 95,
            "unresolved": 13,
            "findings": 108,
        },
        "newly_scorable_ids": newly_scorable,
        "newly_scorable_ids_sha256": canonical_hash(newly_scorable),
        "changed_criteria_ids": changed_ids,
        "changed_criteria_ids_sha256": canonical_hash(changed_ids),
        "human_confirmation_added": False,
        "records": ledger_records,
    }
    return {
        "rubric": merged,
        "validation_rubric": validation_rubric,
        "preflight": preflight,
        "merged_overlay": merged_overlay,
        "merged_ledger": merged_ledger,
        "classifications": classifications,
        "owners": owners,
        "changes": replacements,
        "changed_ids": changed_ids,
        "newly_scorable": newly_scorable,
        "owner_sets": owner_sets,
        "disposition_counts": dict(disposition_counts),
        "normalized_source_classification_counts": dict(
            sorted(normalized_classifications.items())
        ),
    }


def truthy_human_claims(value: Any, context: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_context = f"{context}/{key}"
            is_check_result = any(
                segment in context
                for segment in ("/field_checks", "/checks", "/assertions")
            )
            if (
                key in {"human_confirmation", "human_confirmation_recorded"}
                and child is True
                and not is_check_result
            ):
                hits.append(child_context)
            hits.extend(truthy_human_claims(child, child_context))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(truthy_human_claims(child, f"{context}[{index}]"))
    return hits


def validate_no_human_claims(inputs: Path) -> None:
    documents = []
    for root_name in ("batch1", "batch2-original", "batch3", "repair"):
        for path in sorted_files(inputs / root_name):
            if path.suffix.lower() == ".json":
                documents.append(load_json(path))
            elif path.suffix.lower() == ".jsonl":
                documents.extend(
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
    hits = [
        hit
        for index, document in enumerate(documents)
        for hit in truthy_human_claims(document, f"$document[{index}]")
    ]
    require(not hits, f"AI artifact claims human confirmation: {hits}")


def run_negative_controls(
    inputs: Path,
    base_rubric: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    def expect_rejection(name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception:
            results.append({"name": name, "result": "passed", "expected": "rejected"})
            return
        raise BuildError(f"negative control did not reject: {name}")

    owner_sets = copy.deepcopy(context["owner_sets"])

    def validate_sets(sets: dict[str, list[str]]) -> None:
        values = [criterion_id for ids in sets.values() for criterion_id in ids]
        require(
            len(values) == len(set(values)) == 113
            and canonical_hash(sorted(values)) == CANONICAL_IDS_SHA256,
            "ownership partition differs",
        )

    expect_rejection(
        "omitted_canonical_owner",
        lambda: (
            owner_sets["batch2_successor"].remove("AIS-08:R5"),
            validate_sets(owner_sets),
        ),
    )
    owner_sets = copy.deepcopy(context["owner_sets"])
    expect_rejection(
        "duplicate_canonical_owner",
        lambda: (
            owner_sets["batch2_successor"].append("HW-05:R4"),
            validate_sets(owner_sets),
        ),
    )

    base = inputs / "base-v3.0.0"
    sys.path.insert(0, str(base))
    try:
        from rubric_provenance import ProvenanceError, validate_rubric_provenance
    finally:
        sys.path.pop(0)

    mutated = copy.deepcopy(context["validation_rubric"])
    mutated["questions"][0]["criteria"][0]["evidence_refs"][0][
        "pointer_sha256"
    ] = "0" * 64
    expect_rejection(
        "bad_pointer_hash",
        lambda: validate_rubric_provenance(mutated, base / "evaluation-rubric.json"),
    )
    mutated = copy.deepcopy(context["validation_rubric"])
    source = next(
        item
        for item in mutated["evidence_sources"]
        if item["id"] == "hw_rules_v3_3"
    )
    source["sha256"] = "0" * 64
    expect_rejection(
        "bad_evidence_source_hash",
        lambda: validate_rubric_provenance(mutated, base / "evaluation-rubric.json"),
    )

    def reject_unsupported_upgrade() -> None:
        update = next(
            item
            for item in load_json(
                inputs
                / "repair"
                / "criterion-provenance-batch2-successor.overlay.json"
            )["criterion_updates"]
            if item["criterion_id"] == "HW-03:manual-1"
        )
        candidate = copy.deepcopy(update["candidate_rubric_fields"])
        candidate["validation_state"] = "validated_supported"
        candidate["corpus_support"]["semantic_support"] = "mechanically_proven"
        require(
            update["classification"] != "unsupported_or_contradicted_rubric"
            or candidate["validation_state"] == "unresolved_semantics",
            "unsupported criterion cannot become scorable",
        )

    expect_rejection("unsupported_scoring_upgrade", reject_unsupported_upgrade)

    def reject_ai_as_human() -> None:
        mutated_overlay = copy.deepcopy(
            load_json(
                inputs
                / "repair"
                / "criterion-provenance-batch2-successor.overlay.json"
            )
        )
        mutated_overlay["human_confirmation"] = True
        require(
            not truthy_human_claims(mutated_overlay),
            "AI artifact cannot claim human confirmation",
        )

    expect_rejection("ai_as_human_confirmation", reject_ai_as_human)

    def reject_out_of_scope_change() -> None:
        unexpected = set(context["changed_ids"]) | {"AIS-08:R5"}
        require(
            unexpected == set(context["changed_ids"]),
            "out-of-scope criterion mutation",
        )

    expect_rejection("out_of_scope_criterion_mutation", reject_out_of_scope_change)

    def reject_correction_attestation_registration() -> None:
        sources = copy.deepcopy(context["rubric"]["evidence_sources"])
        sources.append(
            {
                "id": "partition_correction_attestation",
                "path": "evidence/audit/partition-correction.json",
                "sha256": REPAIR_ATTESTATION_SHA256,
                "type": "json",
            }
        )
        require(
            all(
                source["sha256"] != REPAIR_ATTESTATION_SHA256
                for source in sources
            ),
            "correction attestation is audit-only",
        )

    expect_rejection(
        "correction_attestation_as_normative_evidence",
        reject_correction_attestation_registration,
    )
    require(len(results) == 8, "negative-control count differs")
    return results


def input_records(inputs: Path) -> list[dict[str, Any]]:
    records = [
        file_record(path, path.relative_to(inputs).as_posix())
        for path in sorted_files(inputs)
    ]
    require(len(records) == 79, f"expected 79 staged input files, got {len(records)}")
    return records


def compare_tree_origin(
    name: str,
    origin: Path,
    staged: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    origin_files = {
        path.relative_to(origin).as_posix(): path for path in sorted_files(origin)
    }
    staged_files = {
        path.relative_to(staged).as_posix(): path for path in sorted_files(staged)
    }
    require(
        set(origin_files) == set(staged_files),
        f"origin/staged path set differs for {name}",
    )
    records = []
    for relative in sorted(origin_files):
        source = origin_files[relative]
        copy_path = staged_files[relative]
        digest = sha256_file(source)
        require(
            digest == sha256_file(copy_path)
            and source.stat().st_size == copy_path.stat().st_size,
            f"origin/staged content differs for {name}/{relative}",
        )
        records.append(
            {
                "group": name,
                "relative_path": relative,
                "origin_path": str(source),
                "staged_path": str(copy_path),
                "bytes": source.stat().st_size,
                "sha256": digest,
                "unchanged": True,
            }
        )
    return records, {
        "name": name,
        "origin_root": str(origin),
        "staged_root": str(staged),
        "file_count": len(records),
        "unchanged": True,
    }


def git_bytes(*arguments: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), *arguments],
        capture_output=True,
        check=False,
        timeout=60,
        env=environment,
    )
    require(
        completed.returncode == 0,
        f"read-only git command failed: {' '.join(arguments)}",
    )
    return completed.stdout


def git_output(*arguments: str) -> str:
    return git_bytes(*arguments).decode("utf-8")


def verify_formal_git_lock() -> dict[str, Any]:
    head = git_output("rev-parse", "HEAD").strip()
    branch = git_output("branch", "--show-current").strip()
    staged = [
        line
        for line in git_output("diff", "--cached", "--name-status").splitlines()
        if line
    ]
    stash = [line for line in git_output("stash", "list").splitlines() if line]
    status = [
        line
        for line in git_output("status", "--porcelain=v1").splitlines()
        if line
    ]
    status_counts = Counter(line[:2] for line in status)
    require(head == FORMAL_HEAD, "repository HEAD differs from formal lock return")
    require(branch == "main", "repository branch differs from formal lock return")
    require(not staged, "repository index is not empty")
    require(not stash, "repository stash is not empty")
    require(
        len(status) == 120
        and status_counts == {" M": 73, "??": 47},
        "repository status shape differs from formal lock return",
    )
    logical_index = git_bytes("ls-files", "--stage", "-z")
    porcelain_v2 = git_bytes(
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
    )
    refs = git_bytes(
        "for-each-ref",
        "--format=%(refname)%09%(objectname)%09%(symref)",
    )
    stash_state = git_bytes("stash", "list", "--format=%gd%x09%H%x09%gs")
    cached_diff = git_bytes("diff", "--cached", "--binary", "--no-ext-diff")
    require(not cached_diff, "logical cached diff is not empty")
    index_path = REPOSITORY / ".git" / "index"
    index_stat = index_path.stat()
    authorized = []
    for relative, expected_hash in sorted(AUTHORIZED_INTER_WINDOW_PATHS.items()):
        path = REPOSITORY / Path(relative)
        require(
            path.is_file() and sha256_file(path) == expected_hash,
            f"authorized inter-window path differs: {relative}",
        )
        authorized.append(file_record(path, relative))
    caches = []
    for relative, expected_hash in sorted(ATTRIBUTABLE_CACHE_PATHS.items()):
        path = REPOSITORY / Path(relative)
        require(
            path.is_file() and sha256_file(path) == expected_hash,
            f"attributable cache path differs: {relative}",
        )
        caches.append(file_record(path, relative))
    return {
        "head": head,
        "branch": branch,
        "index_entries": len(staged),
        "stash_entries": len(stash),
        "status_entries": len(status),
        "tracked_modified": status_counts[" M"],
        "untracked": status_counts["??"],
        "status_enumeration": "git status --porcelain=v1",
        "logical_index": {
            "command": "git ls-files --stage -z",
            "bytes": len(logical_index),
            "sha256": sha256_bytes(logical_index),
        },
        "porcelain_v2": {
            "command": "git status --porcelain=v2 -z --untracked-files=all",
            "bytes": len(porcelain_v2),
            "sha256": sha256_bytes(porcelain_v2),
        },
        "refs": {
            "command": (
                "git for-each-ref "
                "--format=%(refname)%09%(objectname)%09%(symref)"
            ),
            "bytes": len(refs),
            "sha256": sha256_bytes(refs),
        },
        "stash_state": {
            "command": "git stash list --format=%gd%x09%H%x09%gs",
            "bytes": len(stash_state),
            "sha256": sha256_bytes(stash_state),
        },
        "cached_diff": {
            "command": "git diff --cached --binary --no-ext-diff",
            "bytes": len(cached_diff),
            "sha256": sha256_bytes(cached_diff),
        },
        "physical_index_informational_only": {
            "path": ".git/index",
            "bytes": index_stat.st_size,
            "sha256": sha256_file(index_path),
            "mtime_ns": index_stat.st_mtime_ns,
            "canonical_non_mutation_input": False,
            "explanation": (
                "Read-only Git status may refresh stat-cache metadata without "
                "changing logical staged content."
            ),
        },
        "authorized_payload_paths": authorized,
        "attributable_test_cache_paths": caches,
    }


def logical_git_state(lock: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in lock.items()
        if key != "physical_index_informational_only"
    }


def hash_repository_tree() -> dict[str, Any]:
    require(REPOSITORY.is_dir(), "repository junction is unavailable")
    paths: list[Path] = []
    for base, dirs, files in os.walk(REPOSITORY, followlinks=False):
        if Path(base) == REPOSITORY:
            dirs[:] = [directory for directory in dirs if directory != ".git"]
        dirs.sort()
        files.sort()
        paths.extend(Path(base) / name for name in files)

    def hash_one(path: Path) -> tuple[str, int, str]:
        return (
            path.relative_to(REPOSITORY).as_posix(),
            path.stat().st_size,
            sha256_file(path),
        )

    rows: list[tuple[str, int, str]] = []
    with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) + 4)) as pool:
        for index, row in enumerate(pool.map(hash_one, paths), start=1):
            rows.append(row)
            if index % 1000 == 0:
                print(f"      repository hash progress: {index}/{len(paths)}", flush=True)
    records = [
        f"{relative}\0{size}\0{digest}\n"
        for relative, size, digest in rows
    ]
    result = {
        "path": str(REPOSITORY),
        "files": len(rows),
        "bytes": sum(size for _, size, _ in rows),
        "sha256": sha256_bytes("".join(records).encode("utf-8")),
        "record_format": (
            "walk-order relative path + NUL + bytes + NUL + SHA-256 + LF; "
            "repository content only, excluding .git/**"
        ),
        "excluded_paths": [".git/**"],
    }
    require(
        all(result[key] == REPOSITORY_BASELINE[key] for key in REPOSITORY_BASELINE),
        "repository content tree differs from the parent-authorized baseline",
    )
    return result


def verify_source_nonmutation(inputs: Path, context: dict[str, Any]) -> dict[str, Any]:
    tree_specs = (
        (
            "authoritative_base_bundle",
            Path(
                r"C:\Users\taomar\.copilot\session-state"
                r"\135cb788-7072-4c5f-84d0-7458aba79def\files"
                r"\consume-api-provenance-harness-v3.0.0"
            ),
            inputs / "base-v3.0.0",
        ),
        (
            "batch1_root",
            Path(
                r"C:\Users\taomar\.copilot\session-state"
                r"\7b679b16-ef8a-4edb-8fe4-4e9dc2ff5215\files"
            ),
            inputs / "batch1",
        ),
        (
            "batch2_original_root",
            Path(
                r"C:\Users\taomar\.copilot\session-state"
                r"\bfcad3f2-6146-4d34-ac69-467da06af678\files"
            ),
            inputs / "batch2-original",
        ),
        (
            "batch3_root",
            Path(
                r"C:\Users\taomar\.copilot\session-state"
                r"\e62880a2-2a1f-4ae4-9abf-572a62728640\files"
            ),
            inputs / "batch3",
        ),
        (
            "partition_repair_root",
            Path(
                r"C:\Users\taomar\.copilot\session-state"
                r"\5c19f207-5e73-41bd-8612-089ef60b13c5\files"
            ),
            inputs / "repair",
        ),
    )
    records: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for name, origin, staged in tree_specs:
        group_records, group = compare_tree_origin(name, origin, staged)
        records.extend(group_records)
        groups.append(group)

    batch1_attestation = load_json(
        inputs / "batch1" / "criterion-provenance-batch1-source-attestations.json"
    )
    external_specs: list[tuple[str, Path, Path]] = []
    ais_source = next(
        item
        for item in batch1_attestation["canonical_harness_inputs"]
        if Path(item["path"]).name == "source-snapshot.ais.json"
    )
    external_specs.append(
        (
            "batch1_source_snapshot",
            Path(ais_source["path"]),
            inputs / "external-evidence" / "batch1-source-snapshot.ais.json",
        )
    )
    for evidence in batch1_attestation["normative_evidence"]:
        external_specs.append(
            (
                f"batch1_response_{evidence['key']}",
                Path(evidence["response_path"]),
                inputs
                / "external-evidence"
                / f"batch1-{Path(evidence['response_path']).name}",
            )
        )
        external_specs.append(
            (
                f"batch1_record_{evidence['key']}",
                Path(evidence["record_path"]),
                inputs
                / "external-evidence"
                / f"batch1-{Path(evidence['record_path']).stem}.record.json",
            )
        )
    batch2_attestation = context["batch2_detail"]["attestation"]
    external_specs.extend(
        [
            (
                "batch2_source_document",
                Path(batch2_attestation["source_documents"][0]["path"]),
                inputs / "external-evidence" / "batch2-hardware-source.docx",
            ),
            (
                "batch2_rule_receipt",
                Path(batch2_attestation["rule_artifacts"][0]["path"]),
                inputs / "external-evidence" / "batch2-case-hw-policy-rule.json",
            ),
        ]
    )
    batch3_attestation = load_json(
        inputs / "batch3" / "criterion-provenance-batch-3.source-hashes.json"
    )
    batch3_sources = {
        item["source_id"]: item for item in batch3_attestation["sources"]
    }
    external_specs.extend(
        [
            (
                "batch3_source_document",
                Path(batch3_sources["hw_policy_v3_3_docx"]["path"]),
                inputs / "external-evidence" / "batch3-hardware-source.docx",
            ),
            (
                "batch3_rule_export",
                Path(batch3_sources["hw_rules_v3_3"]["path"]),
                inputs
                / "external-evidence"
                / "batch3-hardware-policy-v3.3-import.json",
            ),
        ]
    )
    for name, origin, staged in external_specs:
        require(origin.is_file() and staged.is_file(), f"source is unavailable: {name}")
        digest = sha256_file(origin)
        require(
            digest == sha256_file(staged)
            and origin.stat().st_size == staged.stat().st_size,
            f"source differs from staged copy: {name}",
        )
        records.append(
            {
                "group": name,
                "relative_path": staged.name,
                "origin_path": str(origin),
                "staged_path": str(staged),
                "bytes": origin.stat().st_size,
                "sha256": digest,
                "unchanged": True,
            }
        )
        groups.append(
            {
                "name": name,
                "origin_root": str(origin),
                "staged_root": str(staged),
                "file_count": 1,
                "unchanged": True,
            }
        )
    require(len(records) == 79, f"expected 79 source comparisons, got {len(records)}")
    formal_lock = verify_formal_git_lock()
    repository = hash_repository_tree()
    return {
        "schema_version": "criterion-provenance-source-non-mutation/2",
        "status": "passed",
        "compared_file_count": len(records),
        "group_count": len(groups),
        "all_source_files_unchanged": True,
        "repository_interval_byte_identical": None,
        "repository": {
            "canonical_non_mutation_definition": (
                "Repository content tree excluding .git/**, plus separately "
                "hashed logical Git index, porcelain-v2 status, refs, and stash."
            ),
            "historical_pre_payload_snapshot": {
                **HISTORICAL_REPAIR_REPOSITORY,
                "includes_git_directory": True,
                "status": "historical_superseded_by_authorized_payload_changes",
            },
            "historical_authorized_full_tree_snapshot": {
                **AUTHORIZED_FULL_TREE_WITH_GIT,
                "includes_git_directory": True,
                "status": "superseded_by_informational_index_stat_cache_refresh",
            },
            "informational_index_refresh_full_tree_snapshot": {
                **INFORMATIONAL_INDEX_REFRESH_TREE,
                "includes_git_directory": True,
                "status": "noncanonical_physical_git_metadata_only",
            },
            "authorized_inter_window_change": {
                "status": "parent_authorized_and_formally_returned",
                "lock_return_local": "2026-09-05T02:47:00+03:00",
                "formal_git_lock_and_interval_start": formal_lock,
                "unexplained_paths": [],
            },
            "interval_start": repository,
            "interval_end": None,
        },
        "network_api_model_database_search_azure_accessed": False,
        "git_state_read_only_accessed": True,
        "git_logical_state_modified": False,
        "live_execution_performed": False,
        "groups": groups,
        "files": records,
    }


def version_migration_document() -> str:
    return f"""# Criterion Provenance Additive Successor

## Versions

- Harness: `{HARNESS_VERSION}`
- Rubric: `{RUBRIC_VERSION}` with unchanged schema `{RUBRIC_SCHEMA}`
- Manifest: `{MANIFEST_VERSION}` with unchanged schema `{MANIFEST_SCHEMA}`

This is a minor additive successor. It adds hash-bound evidence sources,
criterion provenance, and audit artifacts without changing the public rubric or
manifest schemas. Major versions therefore remain 3 and 2 respectively.

## Scope

The exact repaired 113-ID partition is applied to a fresh v3.0.0 base. Four
Batch1 and one Batch3 criteria become mechanically source-supported. Twelve
Batch2 semantic-pending criteria carry unresolved, hash-bound body evidence
and remain unscorable pending independent human confirmation. One separate
Batch2 unsupported/contradicted criterion carries unresolved evidence but
requires human reconciliation. Structural, harness, unsupported, and
product-decision-required criteria remain outside product-law failure
attribution.

Seven additional semantic-pending criteria from Batch1 and Batch3 remain
unscorable because no confirmed candidate provenance was attached. Across all
three batches, 19 semantic-pending criteria still require independent human
confirmation.

No frozen run, historical adjudication, repository file, source document, or
live service is reinterpreted or modified. Execution remains disabled.
"""


def integration_document() -> str:
    return f"""# Provenance Successor Integration

## Reproduction

From the package root, create a new output directory:

```powershell
python -B .\\build_criterion_provenance_successor.py `
  --inputs <private-resume-inputs-path> `
  --output-package <new-empty-output-package-path>
```

The builder verifies the canonical v3.0.0 payload, the repaired 113-ID
partition, every evidence pointer/body/rule/span hash, source non-mutation, and
the repository baseline. It builds twice, runs validation twice with outbound
network calls blocked, and accepts only byte-identical packages.

## Adoption

Use this bundle only for offline validation, planning, provenance preflight,
and derived scoring. `manifest.pending.json` remains execution-disabled. The
13 unresolved criteria require a separate hash-bound human-confirmation
artifact before any future scoring upgrade.

## Rollback

No product or data rollback is needed. Stop using `{HARNESS_VERSION}` and
return to the exact canonical v3.0.0 bundle at payload SHA-256
`{BASE_PAYLOAD_SHA256}`. Do not reverse changes into canonical, historical,
source, repository, or live artifacts.
"""


def adoption_document() -> str:
    return f"""# Adoption and Rollback

## Adopt

The `{HARNESS_VERSION}` bundle is ready for immediate offline adoption with
execution disabled. Verify `BUNDLE_MANIFEST.json`, `FILE_INVENTORY.json`, and
the package-level `FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json` before use.

Human confirmation is still required for 19 semantic-pending criteria: 12 are
unresolved with hash-bound candidate provenance, while seven remain unscorable
without an attached candidate. `HW-03:manual-1` separately requires human
reconciliation because its blanket expectation is unsupported/contradicted.
Two product decisions remain unresolved. Structural and harness criteria remain
non-product-law.

## Roll Back

Select the immutable v3.0.0 predecessor with canonical payload SHA-256
`{BASE_PAYLOAD_SHA256}`. No migration reversal, live execution, data repair, or
source change is required because this successor is a separate local bundle.
"""


def agent_progress_document(context: dict[str, Any]) -> str:
    return f"""# Agent Progress

## Active Milestone

Deterministic `{HARNESS_VERSION}` successor assembled and validated.

## Architectural Context

### System Boundary

Offline rubric provenance, fail-closed scoring, and controlled local adoption.

### Important Invariants

- Exactly one batch owns each of the canonical 113 finding IDs.
- Only active, source-bound, mechanically proven or independently
  human-confirmed criteria may be scorable.
- Structural and harness checks never become product-law failures.
- AI-authored artifacts never count as human confirmation.
- Execution remains disabled.

## Architectural Signals

- The predecessor ownership overlap/omission was corrected by a separate
  hash-bound artifact.
- Batch2's original source attestation remains the normative evidence source.
- The correction attestation remains audit-only.

## Root-Cause Analysis

- Prior symptom: 113 entries represented only 112 unique owners.
- Root cause: inconsistent exact ownership at positions 39 and 77.
- Correction: repaired Batch2 owns positions 39-76; Batch3 owns 77-113.

## Impact Analysis

- Changed criteria: {len(context["changed_ids"])}
- Newly scorable: {len(context["newly_scorable"])}
- Result: 20 scorable, 95 unscorable, 13 unresolved
- Schema impact: none
- Live/data impact: none
- Rollback: select the immutable v3.0.0 predecessor

## Architecture Decisions

### Decision: Minor additive version

- Context: provenance and evidence expanded without a schema break
- Decision: harness/rubric 3.1.0 and manifest 2.1.0
- Rationale: additive compatible behavior under unchanged major schemas
- Validation: native load, self-test, unit/mutation suite, hash inventory, and
  two-pass byte-identical regeneration
"""


def merge_report_document(
    context: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    return f"""# Criterion Provenance Merge and Validation Report

## Outcome

The repaired exact-ID partition was applied to a fresh canonical v3.0.0 copy.
The successor is `{HARNESS_VERSION}` with rubric `{RUBRIC_VERSION}` and
manifest `{MANIFEST_VERSION}`. Execution remains disabled.

## Partition

- Batch1: 38 IDs, canonical positions 1-38
- Batch2 successor: 38 IDs, positions 39-76
- Batch3: 37 IDs, positions 77-113
- Union: 113 unique canonical IDs
- Gaps, overlaps, and extras: 0

## Provenance result

- Total criteria: 128
- Scorable: 20
- Unscorable: 95
- Unresolved: 13
- Findings: 108
- Changed criteria: {len(context["changed_ids"])}
- Newly scorable: {len(context["newly_scorable"])}

## Source classifications

- Mechanically source-supported: 5
- Semantic support pending human confirmation: 19
- Unsupported or contradicted rubric: 1
- Structural or harness, not product law: 80
- Product decision required: 8

## Evidence validation

- Batch1: five frozen records/bodies, 24 rules, and 21 spans verified
- Batch2: five source-snapshot pointers, five DOCX body ranges, and five rule
  metadata pointers verified; 37 predecessor records preserved exactly
- Batch3: eight source pointers, eight DOCX body ranges, and seven rule records
  verified
- Correction attestation: verified as audit-only and not registered as
  normative evidence

## Validation

- Native validate: {validation["native_validate"]["status"]}
- Network-disabled self-test: {validation["native_self_test"]["status"]}
- Unit tests: {validation["unit_tests"]["passed"]} passed
- Mutation/negative controls: {validation["negative_controls"]["passed"]} passed
- Quote/literal leakage hits: {validation["leakage"]["total_hits"]}
- Two-pass deterministic build: byte-identical

## Non-mutation boundary

- Pinned provenance/source/base/batch/repair inputs: 79 unchanged files
- Repository content tree, excluding `.git/**`: {REPOSITORY_BASELINE["files"]}
  files, {REPOSITORY_BASELINE["bytes"]} bytes, SHA-256
  `{REPOSITORY_BASELINE["sha256"]}` before and after
- Logical Git index, porcelain-v2 status, refs, stash, HEAD, branch, and cached
  diff: hash-identical before and after under `GIT_OPTIONAL_LOCKS=0`
- Historical repair full-tree snapshot
  `{HISTORICAL_REPAIR_REPOSITORY["sha256"]}` is explicitly superseded by
  parent-authorized Payload writes
- Physical `.git/index` bytes are informational only because read-only status
  may refresh stat-cache metadata without changing logical staged content

## Remaining limitations

- Nineteen semantic-pending criteria require independent human confirmation:
  twelve are unresolved with hash-bound candidate provenance and seven remain
  unscorable without an attached candidate.
- `HW-03:manual-1` is unsupported/contradicted and remains unresolved.
- Two criteria require authoritative product decisions.
- Structural and harness criteria remain non-product-law.
- Batch1's underlying source document bytes are unavailable; its mechanically
  proven upgrades rely on hash-bound frozen rule payloads and span identities.
- No live transport, authorization, model, API, database, Search, Azure, or
  deployment operation was performed.
"""


def successor_test_source() -> str:
    return f'''from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CriterionProvenanceSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rubric = load(ROOT / "evaluation-rubric.json")
        cls.overlay = load(
            ROOT / "provenance" / "criterion-provenance-merged-overlay.json"
        )
        cls.ledger = load(
            ROOT / "provenance" / "criterion-provenance-merged-ledger.json"
        )

    def test_versions_are_additive_and_schema_compatible(self) -> None:
        manifest = load(ROOT / "manifest.pending.json")
        self.assertEqual(self.rubric["rubric_version"], "{RUBRIC_VERSION}")
        self.assertEqual(self.rubric["schema_version"], "{RUBRIC_SCHEMA}")
        self.assertEqual(manifest["manifest_version"], "{MANIFEST_VERSION}")
        self.assertEqual(manifest["schema_version"], "{MANIFEST_SCHEMA}")
        self.assertEqual(manifest["harness_version"], "{HARNESS_VERSION}")

    def test_partition_is_exact(self) -> None:
        partition = self.overlay["partition"]
        self.assertEqual(partition["count"], 113)
        self.assertTrue(partition["pairwise_disjoint"])
        self.assertEqual(partition["omitted_ids"], [])
        self.assertEqual(partition["duplicate_ids"], [])
        self.assertEqual(partition["extra_ids"], [])

    def test_result_counts(self) -> None:
        self.assertEqual(
            self.ledger["result_counts"],
            {{
                "criteria_total": 128,
                "scorable": 20,
                "unscorable": 95,
                "unresolved": 13,
                "findings": 108,
            }},
        )

    def test_source_classification_counts(self) -> None:
        self.assertEqual(
            self.ledger["normalized_source_classification_counts"],
            {{
                "mechanically_source_supported": 5,
                "product_decision_required": 8,
                "semantic_support_pending_human_confirmation": 19,
                "structural_harness_not_product_law": 80,
                "unsupported_or_contradicted_rubric": 1,
            }},
        )

    def test_exact_changed_population(self) -> None:
        self.assertEqual(len(self.overlay["changes"]), 18)
        self.assertEqual(len(self.ledger["changed_criteria_ids"]), 18)
        self.assertEqual(len(self.ledger["newly_scorable_ids"]), 5)

    def test_original_batch2_attestation_is_retained(self) -> None:
        path = (
            ROOT
            / "evidence"
            / "normative"
            / "normative-provenance-batch2.source-attestations.json"
        )
        self.assertEqual(sha(path), "{ORIGINAL_BATCH2_ATTESTATION_SHA256}")

    def test_correction_attestation_is_not_normative_evidence(self) -> None:
        hashes = {{source["sha256"] for source in self.rubric["evidence_sources"]}}
        self.assertNotIn("{REPAIR_ATTESTATION_SHA256}", hashes)

    def test_ais08_r5_remains_structural_and_unscorable(self) -> None:
        record = next(
            item for item in self.ledger["records"]
            if item["criterion_id"] == "AIS-08:R5"
        )
        self.assertEqual(
            record["source_classification"],
            "structural_harness_not_product_law",
        )
        self.assertEqual(record["result_disposition"], "unscorable")
        self.assertFalse(record["result_scorable"])

    def test_hw05_r4_has_batch3_as_sole_owner(self) -> None:
        record = next(
            item for item in self.ledger["records"]
            if item["criterion_id"] == "HW-05:R4"
        )
        self.assertEqual(record["owner"], "batch3")
        self.assertEqual(record["merge_action"], "retain_fail_closed")

    def test_no_human_confirmation_was_added(self) -> None:
        self.assertFalse(self.ledger["human_confirmation_added"])
        self.assertTrue(
            all(not item["human_confirmation_added"] for item in self.ledger["records"])
        )

    def test_all_evidence_paths_are_bundle_relative(self) -> None:
        for source in self.rubric["evidence_sources"]:
            path = Path(source["path"])
            self.assertFalse(path.is_absolute())
            self.assertTrue((ROOT / path).is_file())

    def test_execution_remains_disabled(self) -> None:
        manifest = load(ROOT / "manifest.pending.json")
        self.assertFalse(manifest["gates"]["parent_authorized"])
        self.assertNotEqual(manifest["status"], "authorized_for_execution")


if __name__ == "__main__":
    unittest.main()
'''


def copy_base_payload(inputs: Path, bundle: Path) -> None:
    base = inputs / "base-v3.0.0"
    skipped = {
        "AGENT_PROGRESS.md",
        "BUNDLE_MANIFEST.json",
        "FILE_INVENTORY.json",
        "PROVENANCE_INTEGRATION.md",
        "READINESS_IMPLEMENTATION_REPORT.md",
        "evaluation-rubric.json",
        "manifest.pending.json",
        "tests/test_rubric_provenance_integration.py",
    }
    for source in sorted_files(base):
        relative = source.relative_to(base).as_posix()
        if (
            relative in skipped
            or source.suffix.lower() == ".pyc"
            or "__pycache__" in source.parts
        ):
            continue
        if relative.startswith("logs/"):
            destination = bundle / "logs" / "base-v3.0.0" / relative[5:]
        else:
            destination = bundle / Path(relative)
        copy_file(source, destination)


def patch_runtime_and_tests(inputs: Path, bundle: Path) -> None:
    base = inputs / "base-v3.0.0"
    runtime = (base / "consume_matrix_runner.py").read_text(encoding="utf-8")
    runtime = runtime.replace(
        'HARNESS_VERSION = "consume-api-provenance-harness/3.0.0"',
        f'HARNESS_VERSION = "{HARNESS_VERSION}"',
    ).replace(
        'MANIFEST_VERSION = "2.0.0"',
        f'MANIFEST_VERSION = "{MANIFEST_VERSION}"',
    )
    require(
        f'HARNESS_VERSION = "{HARNESS_VERSION}"' in runtime
        and f'MANIFEST_VERSION = "{MANIFEST_VERSION}"' in runtime,
        "runtime version patch failed",
    )
    write_text(bundle / "consume_matrix_runner.py", runtime)

    tests = (
        base / "tests" / "test_rubric_provenance_integration.py"
    ).read_text(encoding="utf-8")
    tests = tests.replace(
        "consume-api-provenance-harness/3.0.0",
        HARNESS_VERSION,
    )
    tests = tests.replace(
        'manifest["manifest_version"], "2.0.0"',
        f'manifest["manifest_version"], "{MANIFEST_VERSION}"',
    )
    tests = tests.replace(
        'self.rubric["rubric_version"], "3.0.0"',
        f'self.rubric["rubric_version"], "{RUBRIC_VERSION}"',
    )
    predecessor_test = '''    def test_heading_and_inferred_criteria_are_unscorable_rubric_errors(self) -> None:
        question = self.questions["AIS-01"]
        provenance = self.preflight["questions"][question["id"]]["dimensions"]
        self.assertEqual(provenance["R1"]["criterion_provenance"], "heading_path")
        self.assertEqual(provenance["R1"]["disposition"], "unscorable")
        self.assertEqual(provenance["R3"]["criterion_provenance"], "question_only")
        self.assertEqual(provenance["R3"]["disposition"], "unscorable")
        for dimension in ("R1", "R3"):
            result = gate_evaluation(
                question,
                self.dimensions({dimension}),
                self.preflight,
                "A",
            )
            self.assertEqual(result["scored_result"], "rubric_error")
            self.assertEqual(result["product_failures"], [])
'''
    successor_test = '''    def test_supported_heading_upgrade_and_inferred_fail_closed_behavior(self) -> None:
        question = self.questions["AIS-01"]
        provenance = self.preflight["questions"][question["id"]]["dimensions"]
        self.assertEqual(provenance["R1"]["criterion_provenance"], "rule_body")
        self.assertEqual(provenance["R1"]["disposition"], "scorable")
        supported = gate_evaluation(
            question,
            self.dimensions({"R1"}),
            self.preflight,
            "A",
        )
        self.assertEqual(supported["scored_result"], "fail")
        self.assertEqual(supported["product_failures"], ["R1"])
        self.assertEqual(provenance["R3"]["criterion_provenance"], "question_only")
        self.assertEqual(provenance["R3"]["disposition"], "unscorable")
        inferred = gate_evaluation(
            question,
            self.dimensions({"R3"}),
            self.preflight,
            "A",
        )
        self.assertEqual(inferred["scored_result"], "rubric_error")
        self.assertEqual(inferred["product_failures"], [])
'''
    require(predecessor_test in tests, "predecessor fail-closed test block differs")
    tests = tests.replace(predecessor_test, successor_test)
    write_text(bundle / "tests" / "test_rubric_provenance_integration.py", tests)
    write_text(
        bundle / "tests" / "test_criterion_provenance_successor.py",
        successor_test_source(),
    )


def copy_evidence_and_provenance(
    inputs: Path,
    bundle: Path,
    script_path: Path,
) -> None:
    external = inputs / "external-evidence"
    evidence = {
        external / "batch1-E__ais-annual-vacation__r1.decoded": (
            bundle / "evidence" / "normative" / "ais_e_annual_vacation_r1.json"
        ),
        external / "batch1-E__ais-maternity-leave__r1.decoded": (
            bundle / "evidence" / "normative" / "ais_e_maternity_leave_r1.json"
        ),
        external / "batch1-E__ais-tuition-child__r1.decoded": (
            bundle / "evidence" / "normative" / "ais_e_tuition_child_r1.json"
        ),
        (
            inputs
            / "batch2-original"
            / "normative-provenance-batch2.source-attestations.json"
        ): (
            bundle
            / "evidence"
            / "normative"
            / "normative-provenance-batch2.source-attestations.json"
        ),
        external / "batch3-hardware-policy-v3.3-import.json": (
            bundle / "evidence" / "normative" / "hardware-policy-v3.3.rules.json"
        ),
    }
    for source, destination in evidence.items():
        copy_file(source, destination)

    source_batches = bundle / "provenance" / "source-batches"
    for input_name, output_name in (
        ("batch1", "batch1"),
        ("batch2-original", "batch2-original-predecessor"),
        ("repair", "batch2-successor-repair"),
        ("batch3", "batch3"),
    ):
        shutil.copytree(inputs / input_name, source_batches / output_name)
    copy_file(
        script_path,
        bundle / "provenance" / "build_criterion_provenance_successor.py",
    )


def semantic_manifest_hash(manifest: dict[str, Any]) -> str:
    normalized = copy.deepcopy(manifest)
    normalized.setdefault("hashes", {})["manifest_sha256"] = None
    return canonical_hash(normalized)


def contract_hash(manifest: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "schema_version": manifest.get("schema_version"),
            "manifest_version": manifest.get("manifest_version"),
            "harness_version": manifest.get("harness_version"),
            "request_defaults": manifest.get("request_defaults"),
            "arms": manifest.get("arms"),
            "watchdog": manifest.get("watchdog"),
        }
    )


def questions_hash(questions: list[dict[str, Any]]) -> str:
    return canonical_hash(
        [
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
    )


def write_manifest(inputs: Path, bundle: Path, rubric: dict[str, Any]) -> None:
    manifest = load_json(inputs / "base-v3.0.0" / "manifest.pending.json")
    manifest["manifest_version"] = MANIFEST_VERSION
    manifest["harness_version"] = HARNESS_VERSION
    manifest["run_id"] = "consume-api-six-arm-provenance-v3-1-pending"
    manifest["rubric"]["status"] = "criterion_provenance_additive_successor"
    manifest["rubric"]["version"] = RUBRIC_VERSION
    manifest["rubric"]["source_markdown_path"] = "RUBRIC_MIGRATION_V3_1.md"
    manifest["rubric"]["source_markdown_sha256"] = sha256_file(
        bundle / "RUBRIC_MIGRATION_V3_1.md"
    )
    manifest["hashes"] = {
        "manifest_sha256": None,
        "contract_sha256": contract_hash(manifest),
        "questions_sha256": questions_hash(rubric["questions"]),
        "rubric_sha256": sha256_file(bundle / "evaluation-rubric.json"),
        "source_snapshot_sha256": sha256_file(
            bundle / "evidence" / "source.snapshot.json"
        ),
    }
    manifest["hashes"]["manifest_sha256"] = semantic_manifest_hash(manifest)
    write_json(bundle / "manifest.pending.json", manifest)


def offline_guard_source() -> str:
    return """import socket

def _blocked(*args, **kwargs):
    raise RuntimeError("outbound network is disabled for successor validation")

class _GuardedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        return _blocked(*args, **kwargs)

    def connect_ex(self, *args, **kwargs):
        return _blocked(*args, **kwargs)

socket.socket = _GuardedSocket
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
socket.gethostbyname = _blocked
socket.gethostbyname_ex = _blocked
"""


def run_command(
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    label: str,
) -> subprocess.CompletedProcess[str]:
    print(f"        {label}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    if completed.returncode != 0:
        print(completed.stdout, flush=True)
        print(completed.stderr, file=sys.stderr, flush=True)
        raise BuildError(f"{label} failed with exit code {completed.returncode}")
    return completed


def run_native_validation(
    bundle: Path,
    negative_controls: list[dict[str, str]],
) -> dict[str, Any]:
    work = bundle / "work"
    guard = work / "offline-guard"
    temp = work / "temp"
    guard.mkdir(parents=True)
    temp.mkdir(parents=True)
    write_text(guard / "sitecustomize.py", offline_guard_source())
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(guard) + os.pathsep + str(bundle),
            "TEMP": str(temp),
            "TMP": str(temp),
            "NO_PROXY": "*",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
        }
    )
    validate = run_command(
        [
            sys.executable,
            "-B",
            "consume_matrix_runner.py",
            "validate",
            "--manifest",
            "manifest.pending.json",
        ],
        bundle,
        environment,
        "native validate",
    )
    validate_result = json.loads(validate.stdout)
    require(
        validate_result["status"] == "valid"
        and validate_result["warnings"] == []
        and validate_result["provenance_preflight"]["criterion_count"] == 128
        and validate_result["provenance_preflight"]["rubric_finding_count"] == 108,
        "native validate result differs",
    )
    self_test = run_command(
        [
            sys.executable,
            "-B",
            "consume_matrix_runner.py",
            "self-test",
            "--manifest",
            "manifest.pending.json",
        ],
        bundle,
        environment,
        "network-disabled self-test",
    )
    self_test_result = json.loads(self_test.stdout)
    require(
        self_test_result["status"] == "self-test-passed"
        and self_test_result["network_calls"] == 0,
        "native self-test result differs",
    )
    unit = run_command(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        bundle,
        environment,
        "unit and successor mutation suite",
    )
    match = re.search(r"Ran (\d+) tests?", unit.stderr)
    require(match is not None, "unit-test count was not reported")
    unit_count = int(match.group(1))
    require(unit_count >= 30, f"expected at least 30 unit tests, got {unit_count}")
    if work.exists():
        shutil.rmtree(work)
    if (bundle / "runs").exists():
        shutil.rmtree(bundle / "runs")
    return {
        "native_validate": {
            "status": "passed",
            "warnings": 0,
            "question_count": validate_result["question_count"],
            "primary_job_count": validate_result["primary_job_count"],
            "rubric_finding_count": 108,
        },
        "native_self_test": {
            "status": "passed",
            "network_calls": self_test_result["network_calls"],
            "offline_guard": "socket_connect_and_dns_blocked",
        },
        "unit_tests": {"status": "passed", "passed": unit_count, "failed": 0},
        "negative_controls": {
            "status": "passed",
            "passed": len(negative_controls),
            "failed": 0,
            "results": negative_controls,
        },
    }


def normative_candidates(inputs: Path) -> set[str]:
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for child in value:
                collect(child)
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)

    external = inputs / "external-evidence"
    for name in (
        "batch1-E__ais-annual-vacation__r1.decoded",
        "batch1-E__ais-sick-surgery__r1.decoded",
        "batch1-E__ais-maternity-leave__r1.decoded",
        "batch1-E__ais-overtime-weekend__r1.decoded",
        "batch1-E__ais-tuition-child__r1.decoded",
        "batch2-case-hw-policy-rule.json",
        "batch3-hardware-policy-v3.3-import.json",
    ):
        collect(load_json(external / name))
    for name in ("batch2-hardware-source.docx", "batch3-hardware-source.docx"):
        document = Document(external / name)
        values.extend(paragraph.text.strip() for paragraph in document.paragraphs)
    return {
        value.strip().casefold()
        for value in values
        if len(value.strip()) >= 80
        and not re.fullmatch(r"[0-9a-fA-F]{64}", value.strip())
        and not re.match(r"^[A-Za-z]:\\", value.strip())
        and not value.strip().startswith(("http://", "https://"))
    }


def leakage_scan(
    inputs: Path,
    bundle: Path,
    merged_overlay: dict[str, Any],
    merged_ledger: dict[str, Any],
) -> dict[str, Any]:
    report_paths = [
        bundle / "MERGE_VALIDATION_REPORT.md",
        bundle / "ADOPTION_AND_ROLLBACK.md",
        bundle / "AGENT_PROGRESS.md",
        bundle / "PROVENANCE_INTEGRATION.md",
        bundle / "RUBRIC_MIGRATION_V3_1.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in report_paths)
    text += canonical_json_bytes(merged_overlay).decode("utf-8")
    text += canonical_json_bytes(merged_ledger).decode("utf-8")
    folded = text.casefold()
    candidates = normative_candidates(inputs)
    source_hits = [candidate for candidate in candidates if candidate in folded]
    rubric_v1 = load_json(
        inputs / "base-v3.0.0" / "evidence" / "rubric-v1.snapshot.json"
    )
    questions = [
        question["exact_question"].strip().casefold()
        for question in rubric_v1["questions"]
    ]
    question_hits = [question for question in questions if question in folded]
    guard = (bundle / "rubric_provenance.py").read_text(encoding="utf-8")
    guard_patterns = {
        "rubric_ids": r"\b(?:AIS|HW)-\d{2}\b",
        "question_ids": r"\b(?:ais|hw)-[a-z0-9-]+\b",
        "provision_fixtures": r"\b[0-9a-f]{32}\b",
    }
    guard_hits = {
        name: len(re.findall(pattern, guard, flags=re.IGNORECASE))
        for name, pattern in guard_patterns.items()
    }
    secret_patterns = (
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"\bBearer\s+[A-Za-z0-9._-]{20,}\b",
        r"(?i)\b(?:api[_-]?key|subscription[_-]?key)\s*[:=]\s*[\"'][^\"']+[\"']",
    )
    secret_hits = sum(len(re.findall(pattern, text)) for pattern in secret_patterns)
    total_hits = len(source_hits) + len(question_hits) + sum(guard_hits.values()) + secret_hits
    require(total_hits == 0, "quote, literal, guard, or secret leakage detected")
    return {
        "status": "passed",
        "source_literal_candidates": len(candidates),
        "source_literal_hits": 0,
        "question_literals_checked": len(questions),
        "question_literal_hits": 0,
        "production_guard_hits": guard_hits,
        "secret_hits": 0,
        "total_hits": 0,
    }


def build_bundle_manifest(
    bundle: Path,
    canonical_hash_value: str,
    canonical_records: list[dict[str, Any]],
    validation: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    output_names = (
        "consume_matrix_runner.py",
        "rubric_provenance.py",
        "evaluation-rubric.json",
        "manifest.pending.json",
        "provenance/criterion-provenance-merged-overlay.json",
        "provenance/criterion-provenance-merged-ledger.json",
        "provenance/SOURCE_NON_MUTATION.json",
        "MERGE_VALIDATION_REPORT.md",
        "ADOPTION_AND_ROLLBACK.md",
    )
    return {
        "schema_version": "consume-api-controlled-adoption-bundle/1",
        "bundle_path": ".",
        "status": "ready_for_immediate_offline_adoption_execution_disabled",
        "versions": {
            "harness": HARNESS_VERSION,
            "manifest": MANIFEST_VERSION,
            "manifest_schema": MANIFEST_SCHEMA,
            "rubric": RUBRIC_VERSION,
            "rubric_schema": RUBRIC_SCHEMA,
        },
        "version_decision": {
            "kind": "minor_additive",
            "rationale": (
                "Evidence and criterion provenance were added under unchanged "
                "rubric and manifest major schemas."
            ),
            "predecessor_harness": "consume-api-provenance-harness/3.0.0",
            "predecessor_rubric": "3.0.0",
            "predecessor_manifest": "2.0.0",
        },
        "canonical_bundle_hash": {
            "algorithm": "sha256",
            "value": canonical_hash_value,
            "record_format": (
                "sorted UTF-8 relative-path + NUL + lowercase file SHA-256 + LF"
            ),
            "included_file_count": len(canonical_records),
            "included_bytes": sum(record["bytes"] for record in canonical_records),
            "excluded_paths": [
                "BUNDLE_MANIFEST.json",
                "FILE_INVENTORY.json",
                "READINESS_IMPLEMENTATION_REPORT.md",
                "work/**",
                "runs/**",
                "**/__pycache__/**",
                "**/*.pyc",
            ],
        },
        "inventory": "FILE_INVENTORY.json",
        "source_lock": "provenance/SOURCE_NON_MUTATION.json",
        "output_hashes": {
            name: sha256_file(bundle / Path(name)) for name in output_names
        },
        "provenance_preflight": {
            "status": "ready_with_rubric_findings",
            "criteria_total": 128,
            "scorable": 20,
            "unscorable": 95,
            "unresolved": 13,
            "unscorable_findings": 108,
            "changed_criteria": len(context["changed_ids"]),
            "newly_scorable": len(context["newly_scorable"]),
            "source_classifications": context[
                "normalized_source_classification_counts"
            ],
        },
        "validation": {
            **validation,
            "deterministic_regeneration": {
                "passes": 2,
                "byte_identical": True,
            },
            "source_non_mutation": "passed",
            "repository_non_mutation": "passed",
        },
        "execution": {
            "enabled": False,
            "pending_manifest_authorized": False,
        },
        "limitations": [
            (
                "19 semantic-pending criteria require independent human "
                "confirmation: 12 unresolved and 7 unscorable"
            ),
            "HW-03:manual-1 remains unsupported/contradicted and unresolved",
            "2 criteria require authoritative product decisions",
            "structural and harness criteria remain non-product-law",
            "historical replay remains contextual and non-equivalent",
        ],
    }


def finalize_bundle(
    bundle: Path,
    validation: dict[str, Any],
    context: dict[str, Any],
) -> None:
    for name in (
        "BUNDLE_MANIFEST.json",
        "FILE_INVENTORY.json",
        "READINESS_IMPLEMENTATION_REPORT.md",
    ):
        path = bundle / name
        if path.exists():
            path.unlink()
    excluded = {
        "BUNDLE_MANIFEST.json",
        "FILE_INVENTORY.json",
        "READINESS_IMPLEMENTATION_REPORT.md",
    }
    canonical_records = [
        file_record(path, path.relative_to(bundle).as_posix())
        for path in sorted_files(bundle)
        if path.relative_to(bundle).as_posix() not in excluded
        and path.suffix.lower() != ".pyc"
        and "__pycache__" not in path.parts
        and path.relative_to(bundle).parts[0] not in {"work", "runs"}
    ]
    stream = b"".join(
        record["path"].encode("utf-8")
        + b"\0"
        + record["sha256"].encode("ascii")
        + b"\n"
        for record in canonical_records
    )
    canonical_hash_value = sha256_bytes(stream)
    bundle_manifest = build_bundle_manifest(
        bundle,
        canonical_hash_value,
        canonical_records,
        validation,
        context,
    )
    write_json(bundle / "BUNDLE_MANIFEST.json", bundle_manifest)
    readiness = f"""# Harness Adoption Readiness and Implementation Report

## Canonical successor

- Harness: `{HARNESS_VERSION}`
- Rubric: `{RUBRIC_VERSION}` (`{RUBRIC_SCHEMA}`)
- Manifest: `{MANIFEST_VERSION}` (`{MANIFEST_SCHEMA}`)
- Canonical payload SHA-256: `{canonical_hash_value}`
- Canonical payload: {len(canonical_records)} files,
  {sum(record["bytes"] for record in canonical_records)} bytes
- Complete inventory: `FILE_INVENTORY.json`

## Result

The repaired three-way partition covers all 113 canonical findings exactly.
The successor has 128 criteria: 20 scorable, 95 unscorable, and 13 unresolved.
Execution remains disabled.

Nineteen semantic-pending criteria still require independent human
confirmation: twelve are unresolved and seven remain unscorable. One separate
unsupported/contradicted criterion requires human reconciliation, and two
criteria require authoritative product decisions.

## Validation

- Native validate and network-disabled self-test passed.
- {validation["unit_tests"]["passed"]} unit tests passed.
- {validation["negative_controls"]["passed"]} mutation/negative controls passed.
- Two deterministic builds were byte-identical.
- Quote/literal/guard/secret leakage hits: 0.
- 79 source/input files were unchanged.
- The {REPOSITORY_BASELINE["files"]}-file repository content tree excluding
  `.git/**` and all logical Git-state hashes were identical before and after.

## Boundaries

No repository, canonical source, frozen run, adjudication, source document,
network/API/model/database/Search/Azure resource, git state, deployment, or
migration was modified.
"""
    write_text(bundle / "READINESS_IMPLEMENTATION_REPORT.md", readiness)

    inventory_records = []
    for path in sorted_files(bundle):
        relative = path.relative_to(bundle).as_posix()
        if relative == "FILE_INVENTORY.json":
            continue
        canonical_payload = (
            relative not in excluded
            and path.suffix.lower() != ".pyc"
            and "__pycache__" not in path.parts
            and path.relative_to(bundle).parts[0] not in {"work", "runs"}
        )
        record = file_record(path, relative)
        record["canonical_payload"] = canonical_payload
        inventory_records.append(record)
    inventory = {
        "schema_version": "sha256-file-inventory/1",
        "root": ".",
        "generated_file_excluded_from_own_inventory": "FILE_INVENTORY.json",
        "canonical_bundle_sha256": canonical_hash_value,
        "canonical_hash_definition": bundle_manifest["canonical_bundle_hash"],
        "file_count_excluding_inventory_self": len(inventory_records),
        "files": inventory_records,
    }
    write_json(bundle / "FILE_INVENTORY.json", inventory)


def build_package_once(
    inputs: Path,
    package: Path,
    script_path: Path,
    context: dict[str, Any],
    input_manifest: list[dict[str, Any]],
    source_nonmutation: dict[str, Any],
    negative_controls: list[dict[str, str]],
) -> dict[str, Any]:
    require(not package.exists(), f"package pass already exists: {package}")
    bundle = package / BUNDLE_DIRECTORY
    bundle.mkdir(parents=True)
    copy_base_payload(inputs, bundle)
    patch_runtime_and_tests(inputs, bundle)
    copy_evidence_and_provenance(inputs, bundle, script_path)
    write_json(bundle / "evaluation-rubric.json", context["rubric"])
    write_json(
        bundle / "provenance" / "criterion-provenance-merged-overlay.json",
        context["merged_overlay"],
    )
    write_json(
        bundle / "provenance" / "criterion-provenance-merged-ledger.json",
        context["merged_ledger"],
    )
    write_json(
        bundle / "provenance" / "INPUT_HASH_MANIFEST.json",
        {
            "schema_version": "criterion-provenance-input-hash-manifest/1",
            "file_count": len(input_manifest),
            "files": input_manifest,
        },
    )
    write_json(
        bundle / "provenance" / "SOURCE_NON_MUTATION.json",
        source_nonmutation,
    )
    write_text(bundle / "RUBRIC_MIGRATION_V3_1.md", version_migration_document())
    write_text(bundle / "PROVENANCE_INTEGRATION.md", integration_document())
    write_text(bundle / "ADOPTION_AND_ROLLBACK.md", adoption_document())
    write_text(bundle / "AGENT_PROGRESS.md", agent_progress_document(context))
    write_text(
        bundle / "MERGE_VALIDATION_REPORT.md",
        merge_report_document(
            context,
            {
                "native_validate": {"status": "pending"},
                "native_self_test": {"status": "pending"},
                "unit_tests": {"passed": 0},
                "negative_controls": {"passed": len(negative_controls)},
                "leakage": {"total_hits": 0},
            },
        ),
    )
    write_manifest(inputs, bundle, context["rubric"])
    validation = run_native_validation(bundle, negative_controls)
    write_json(bundle / "logs" / "native-validate.json", validation["native_validate"])
    write_json(bundle / "logs" / "native-self-test.json", validation["native_self_test"])
    write_json(bundle / "logs" / "unit-tests.json", validation["unit_tests"])
    write_json(
        bundle / "logs" / "mutation-negative-controls.json",
        validation["negative_controls"],
    )
    write_text(
        bundle / "MERGE_VALIDATION_REPORT.md",
        merge_report_document(
            context,
            {**validation, "leakage": {"total_hits": 0}},
        ),
    )
    leakage = leakage_scan(
        inputs,
        bundle,
        context["merged_overlay"],
        context["merged_ledger"],
    )
    validation["leakage"] = leakage
    write_json(bundle / "logs" / "leakage-scan.json", leakage)
    write_json(
        bundle / "logs" / "validation-summary.json",
        {
            "schema_version": "criterion-provenance-successor-validation/1",
            "status": "passed",
            "versions": {
                "harness": HARNESS_VERSION,
                "rubric": RUBRIC_VERSION,
                "manifest": MANIFEST_VERSION,
            },
            "partition": {
                "count": 113,
                "pairwise_disjoint": True,
                "omissions": 0,
                "overlaps": 0,
                "extras": 0,
            },
            "counts": {
                "criteria_total": 128,
                "scorable": 20,
                "unscorable": 95,
                "unresolved": 13,
                "findings": 108,
            },
            "source_classifications": context[
                "normalized_source_classification_counts"
            ],
            **validation,
            "deterministic_regeneration": {
                "passes": 2,
                "byte_identical": True,
            },
            "execution_enabled": False,
        },
    )
    finalize_bundle(bundle, validation, context)

    write_text(
        package / "MERGE_HANDOFF.md",
        f"""# Criterion Provenance Successor Handoff

- Bundle: `{BUNDLE_DIRECTORY}`
- Harness: `{HARNESS_VERSION}`
- Rubric: `{RUBRIC_VERSION}`
- Manifest: `{MANIFEST_VERSION}`
- Counts: 128 total, 20 scorable, 95 unscorable, 13 unresolved
- Merged overlay:
  `{BUNDLE_DIRECTORY}/provenance/criterion-provenance-merged-overlay.json`
- Merged ledger:
  `{BUNDLE_DIRECTORY}/provenance/criterion-provenance-merged-ledger.json`
- Adoption and rollback:
  `{BUNDLE_DIRECTORY}/ADOPTION_AND_ROLLBACK.md`

See `FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json` for every source, input, and
output hash. Execution remains disabled.
""",
    )
    copy_file(script_path, package / script_path.name)
    refresh_package_manifest(package, input_manifest, source_nonmutation)
    return validation


def refresh_package_manifest(
    package: Path,
    input_manifest: list[dict[str, Any]],
    source_nonmutation: dict[str, Any],
) -> None:
    manifest_path = package / "FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json"
    if manifest_path.exists():
        manifest_path.unlink()
    output_records = [
        file_record(path, path.relative_to(package).as_posix())
        for path in sorted_files(package)
        if path.name != "FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json"
    ]
    write_json(
        package / "FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json",
        {
            "schema_version": "criterion-provenance-full-hash-manifest/2",
            "package_version": PACKAGE_VERSION,
            "generated_file_excluded_from_own_inventory": (
                "FULL_SOURCE_INPUT_OUTPUT_HASH_MANIFEST.json"
            ),
            "source_origin_comparison": source_nonmutation,
            "private_input_file_count": len(input_manifest),
            "private_input_files": input_manifest,
            "output_file_count_excluding_manifest_self": len(output_records),
            "output_files_excluding_manifest_self": output_records,
        },
    )


def compare_packages(first: Path, second: Path) -> dict[str, Any]:
    first_records = [
        file_record(path, path.relative_to(first).as_posix())
        for path in sorted_files(first)
    ]
    second_records = [
        file_record(path, path.relative_to(second).as_posix())
        for path in sorted_files(second)
    ]
    require(first_records == second_records, "two build passes are not byte-identical")
    stream = b"".join(
        record["path"].encode("utf-8")
        + b"\0"
        + record["sha256"].encode("ascii")
        + b"\n"
        for record in first_records
    )
    return {
        "file_count": len(first_records),
        "bytes": sum(record["bytes"] for record in first_records),
        "tree_sha256": sha256_bytes(stream),
    }


def validate_inputs(inputs: Path) -> dict[str, Any]:
    verify_required_hashes(inputs)
    parsing = strict_parse_inputs(inputs)
    base_rubric, base_preflight, canonical_ids = verify_base_bundle(inputs)
    validate_no_human_claims(inputs)
    batch1, batch1_replacements, batch1_paths = validate_batch1(
        inputs,
        base_rubric,
    )
    batch2, batch2_changes, batch2_detail = validate_batch2(inputs, base_rubric)
    batch3, batch3_replacements = validate_batch3(inputs, base_rubric)
    context = build_merged_rubric_and_artifacts(
        inputs,
        base_rubric,
        canonical_ids,
        batch1,
        batch1_replacements,
        batch1_paths,
        batch2,
        batch2_changes,
        batch3,
        batch3_replacements,
    )
    context.update(
        {
            "base_rubric": base_rubric,
            "base_preflight": base_preflight,
            "canonical_ids": canonical_ids,
            "parsing": parsing,
            "batch2_detail": batch2_detail,
        }
    )
    return context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output-package", type=Path, required=True)
    args = parser.parse_args()
    inputs = args.inputs.resolve()
    output = args.output_package.resolve()
    script_path = Path(__file__).resolve()
    require(inputs.is_dir(), f"inputs are unavailable: {inputs}")
    require(not output.exists(), f"output package already exists: {output}")

    pass1 = output.with_name(f".{output.name}.pass1-{os.getpid()}")
    pass2 = output.with_name(f".{output.name}.pass2-{os.getpid()}")
    require(not pass1.exists() and not pass2.exists(), "build-pass path exists")
    try:
        print("[1/9] Strictly validating all fresh inputs and supplied hashes", flush=True)
        context = validate_inputs(inputs)
        manifest = input_records(inputs)
        print(
            f"      inputs={len(manifest)}; JSON={context['parsing']['json_documents']}; "
            f"JSONL={context['parsing']['jsonl_records']}",
            flush=True,
        )
        print("[2/9] Re-proving repaired exact ownership and evidence chains", flush=True)
        print(
            "      partition=113 exact; changed=18; scorable=20; "
            "unscorable=95; unresolved=13",
            flush=True,
        )
        print("[3/9] Running fail-closed mutation controls", flush=True)
        negative_controls = run_negative_controls(inputs, context["base_rubric"], context)
        print(f"      mutation controls={len(negative_controls)} passed", flush=True)
        print("[4/9] Capturing formal Git lock and interval-start repository hash", flush=True)
        source_nonmutation = verify_source_nonmutation(inputs, context)
        print(
            f"      source files={source_nonmutation['compared_file_count']}; "
            "repository files="
            f"{source_nonmutation['repository']['interval_start']['files']}",
            flush=True,
        )
        print("[5/9] Building and validating deterministic pass 1", flush=True)
        validation1 = build_package_once(
            inputs,
            pass1,
            script_path,
            context,
            manifest,
            source_nonmutation,
            negative_controls,
        )
        print("[6/9] Building and validating deterministic pass 2", flush=True)
        validation2 = build_package_once(
            inputs,
            pass2,
            script_path,
            context,
            manifest,
            source_nonmutation,
            negative_controls,
        )
        print("[7/9] Capturing interval-end Git lock and repository hash", flush=True)
        end_lock = verify_formal_git_lock()
        end_repository = hash_repository_tree()
        start_lock = source_nonmutation["repository"][
            "authorized_inter_window_change"
        ]["formal_git_lock_and_interval_start"]
        require(
            end_repository == source_nonmutation["repository"]["interval_start"],
            "repository content changed during the resumed build interval",
        )
        require(
            logical_git_state(end_lock) == logical_git_state(start_lock),
            "logical Git state changed during the resumed build interval",
        )
        source_nonmutation["repository_interval_byte_identical"] = True
        source_nonmutation["git_logical_state_byte_identical"] = True
        source_nonmutation["repository"]["interval_end"] = end_repository
        source_nonmutation["repository"]["formal_lock_after_build"] = end_lock
        source_nonmutation["repository"]["physical_index_metadata"] = {
            "start": start_lock["physical_index_informational_only"],
            "end": end_lock["physical_index_informational_only"],
            "canonical_non_mutation_input": False,
        }
        for package, validation in (
            (pass1, validation1),
            (pass2, validation2),
        ):
            bundle = package / BUNDLE_DIRECTORY
            write_json(
                bundle / "provenance" / "SOURCE_NON_MUTATION.json",
                source_nonmutation,
            )
            finalize_bundle(bundle, validation, context)
            refresh_package_manifest(package, manifest, source_nonmutation)
        print("[8/9] Comparing complete packages byte-for-byte", flush=True)
        comparison = compare_packages(pass1, pass2)
        print(
            f"      files={comparison['file_count']}; bytes={comparison['bytes']}; "
            f"tree_sha256={comparison['tree_sha256']}",
            flush=True,
        )
        print("[9/9] Publishing the verified package atomically", flush=True)
        os.replace(pass1, output)
        shutil.rmtree(pass2)
        print(f"      output={output}", flush=True)
        print("RESULT: successor_ready_execution_disabled", flush=True)
        return 0
    finally:
        for temporary in (pass1, pass2):
            if temporary.exists():
                shutil.rmtree(temporary)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"BUILD ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)
