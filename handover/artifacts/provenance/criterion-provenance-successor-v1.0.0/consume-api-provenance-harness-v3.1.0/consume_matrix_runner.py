from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import gzip
import hashlib
import http.client
import json
import os
import shutil
import ssl
import statistics
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rubric_provenance import (
    ProvenanceError,
    gate_evaluation,
    rollup_scored_results,
    validate_rubric_provenance,
)


ROOT = Path(__file__).resolve().parent
HARNESS_VERSION = "consume-api-provenance-harness/3.1.0"
MANIFEST_SCHEMA_VERSION = "consume-api-matrix-manifest/2"
MANIFEST_VERSION = "2.1.0"
DEFAULT_MANIFEST = ROOT / "manifest.pending.json"
RAW_SCHEMA = ROOT / "schemas" / "raw-result.schema.json"
DERIVED_SCHEMA = ROOT / "schemas" / "derived-result.schema.json"

EXPECTED_QUESTION_IDS = (
    "ais-annual-vacation",
    "ais-sick-surgery",
    "ais-absence-penalty",
    "ais-conflict-vendor",
    "ais-maternity-leave",
    "ais-overtime-weekend",
    "ais-tuition-child",
    "ais-info-probation-evaluation",
    "ais-leave-travel-composition",
    "ais-irrelevant-football",
    "hw-refresh-26-months",
    "hw-stolen-trip",
    "hw-byod-client-files",
    "hw-contractor-15-days",
    "hw-accessibility-monitor",
    "hw-leaver-return",
    "hw-third-accidental-damage",
    "hw-info-approval-thresholds",
    "hw-executive-refresh-override",
    "hw-irrelevant-espresso",
)

ARM_CONTRACT = {
    "A": ("decision_light", False, True, "/trace/token_usage"),
    "B": ("decision_light", True, True, "/trace/token_usage"),
    "C": ("full_decision", False, True, "/trace/token_usage"),
    "D": ("full_decision", True, True, "/trace/token_usage"),
    "E": ("json_only_retrieval", False, False, "/token_usage"),
    "F": ("json_only_retrieval", True, False, "/token_usage"),
}

SAFE_RESPONSE_HEADERS = {
    "content-encoding",
    "content-length",
    "content-type",
    "date",
    "retry-after",
    "x-correlation-id",
    "x-request-id",
}

SCORED_DIMENSIONS = ("R1", "R2", "R3", "R4", "R5", "R7", "R8", "R9")
MEASUREMENT_DIMENSIONS = ("R6", "R10")


class HarnessError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"invalid JSON in {path}: {exc}") from exc


def atomic_write_bytes(path: Path, value: bytes) -> None:
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


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_bytes(path, json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8"))


def resolve_configured_path(manifest_path: Path, configured: str) -> Path:
    path = Path(configured)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def require_under(path: Path, root: Path, description: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise HarnessError(f"{description} must remain under {root}: {path}") from exc


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


def source_keys_by_project(topic_map: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = collections.defaultdict(set)
    for provision in topic_map.get("provisions") or []:
        project = provision.get("project")
        key = provision.get("provision_key")
        if isinstance(project, str) and isinstance(key, str):
            result[project].add(key)
    return dict(result)


def load_bundle(manifest_path: Path, *, for_execution: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        errors.append(f"manifest_version must be {MANIFEST_VERSION}")
    if manifest.get("harness_version") != HARNESS_VERSION:
        errors.append(f"harness_version must be {HARNESS_VERSION}")
    if manifest.get("repetitions") != 3:
        errors.append("repetitions must equal 3")
    if manifest.get("concurrency") != 1:
        errors.append("concurrency must equal 1")
    if (manifest.get("request_defaults") or {}).get("provision_id", object()) is not None:
        errors.append("request_defaults.provision_id must remain null")

    rubric_config = manifest.get("rubric") or {}
    source_config = manifest.get("source_snapshot") or {}
    try:
        rubric_path = resolve_configured_path(manifest_path, rubric_config["path"])
        rubric = load_json(rubric_path)
    except (KeyError, TypeError, HarnessError) as exc:
        errors.append(f"rubric cannot be loaded: {exc}")
        rubric_path = manifest_path.parent / "missing-rubric.json"
        rubric = {}

    try:
        source_path = resolve_configured_path(manifest_path, source_config["path"])
        topic_map = load_json(source_path)
    except (KeyError, TypeError, HarnessError) as exc:
        errors.append(f"source snapshot cannot be loaded: {exc}")
        source_path = manifest_path.parent / "missing-source.json"
        topic_map = {}

    try:
        provenance_preflight = validate_rubric_provenance(rubric, rubric_path)
    except ProvenanceError as exc:
        errors.append(f"rubric provenance preflight failed: {exc}")
        provenance_preflight = {}

    questions = rubric.get("questions") or []
    if tuple(question.get("id") for question in questions) != EXPECTED_QUESTION_IDS:
        errors.append("rubric question IDs or order differ from the accepted 20-question set")
    if len(questions) != 20:
        errors.append("rubric must contain exactly 20 questions")
    corpus_counts = collections.Counter(question.get("corpus") for question in questions)
    if corpus_counts != {"AIS": 10, "HW": 10}:
        errors.append(f"question corpus split must be AIS=10/HW=10, got {dict(corpus_counts)}")
    if len({question.get("exact_question") for question in questions}) != len(questions):
        errors.append("question texts must be unique")
    irrelevant_counts = collections.Counter(
        question.get("corpus") for question in questions if question.get("irrelevant")
    )
    if irrelevant_counts != {"AIS": 1, "HW": 1}:
        errors.append(
            f"irrelevant split must be one per corpus, got {dict(irrelevant_counts)}"
        )
    if {
        question.get("id")
        for question in questions
        if question.get("irrelevant")
    } != {"ais-irrelevant-football", "hw-irrelevant-espresso"}:
        errors.append("the accepted stable irrelevant questions are not preserved")

    dimensions = rubric.get("dimensions") or {}
    for dimension in SCORED_DIMENSIONS:
        if (dimensions.get(dimension) or {}).get("scored") is not True:
            errors.append(f"{dimension} must remain a scored dimension")
    for dimension in MEASUREMENT_DIMENSIONS:
        value = dimensions.get(dimension) or {}
        if value.get("scored") is not False or value.get("measurement_only") is not True:
            errors.append(f"{dimension} must remain measurement-only")

    arms = manifest.get("arms") or []
    if {arm.get("id") for arm in arms} != set(ARM_CONTRACT):
        errors.append("manifest must contain arms A-F exactly once")
    for arm in arms:
        arm_id = arm.get("id")
        if arm_id not in ARM_CONTRACT:
            continue
        actual = (
            arm.get("surface"),
            arm.get("rule_retrieval"),
            arm.get("persists_decision"),
            arm.get("token_usage_pointer"),
        )
        if actual != ARM_CONTRACT[arm_id]:
            errors.append(f"arm {arm_id} violates the verified contract: {actual}")
        if arm.get("method") != "POST":
            errors.append(f"arm {arm_id} must use POST")
        if arm_id in {"A", "B", "C", "D"}:
            if arm.get("idempotency") != "one_per_logical_call_reused_for_retries":
                errors.append(f"arm {arm_id} must use stable per-job idempotency")
        elif arm.get("idempotency") != "omit":
            errors.append(f"arm {arm_id} must omit idempotency")

    valid_keys = source_keys_by_project(topic_map)
    if len(valid_keys.get("ais-e2e", set())) != 39:
        errors.append("source snapshot must contain exactly 39 AIS provisions")
    if len(valid_keys.get("hw-policy", set())) != 60:
        errors.append("source snapshot must contain exactly 60 HW provisions")
    for question in questions:
        expected = question.get("expected_evidence") or {}
        for key in [
            *(expected.get("required") or []),
            *(expected.get("acceptable_additional") or []),
        ]:
            if key not in valid_keys.get(question.get("project"), set()):
                errors.append(
                    f"{question.get('id')}: provision {key} is absent from source snapshot"
                )

    computed = {
        "manifest_sha256": semantic_manifest_hash(manifest),
        "contract_sha256": contract_hash(manifest),
        "questions_sha256": questions_hash(questions) if questions else None,
        "rubric_sha256": sha256_file(rubric_path) if rubric_path.exists() else None,
        "source_snapshot_sha256": (
            sha256_file(source_path) if source_path.exists() else None
        ),
    }
    declared = manifest.get("hashes") or {}
    for name, value in computed.items():
        declared_value = declared.get(name)
        if declared_value is not None and declared_value != value:
            message = (
                f"declared {name} does not match computed value "
                f"({declared_value} != {value})"
            )
            if for_execution:
                errors.append(message)
            else:
                warnings.append(message)
        elif declared_value is None:
            warnings.append(f"{name} is intentionally unset")

    source_markdown = rubric.get("source_markdown") or {}
    if source_markdown:
        markdown_path = resolve_configured_path(
            rubric_path,
            source_markdown.get("path", ""),
        )
        expected_hash = source_markdown.get("sha256")
        if not markdown_path.exists():
            errors.append(f"rubric source markdown is missing: {markdown_path}")
        elif sha256_file(markdown_path) != expected_hash:
            message = "rubric source markdown hash changed"
            if for_execution:
                errors.append(message)
            else:
                warnings.append(message)

    gates = manifest.get("gates") or {}
    if for_execution:
        false_gates = sorted(name for name, value in gates.items() if value is not True)
        if false_gates:
            errors.append(f"execution gates remain false: {', '.join(false_gates)}")
        if manifest.get("status") != "authorized_for_execution":
            errors.append("manifest status is not authorized_for_execution")
        for arm in arms:
            if not arm.get("retrieval_mode_echo_pointer"):
                errors.append(f"arm {arm.get('id')} lacks a stabilized mode-echo pointer")
            if arm.get("contract_status") != "stable":
                errors.append(f"arm {arm.get('id')} contract_status is not stable")
        for name in computed:
            if declared.get(name) != computed[name]:
                errors.append(f"execution requires frozen hash {name}")

    if errors:
        raise HarnessError("\n".join(errors))
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "rubric_path": rubric_path,
        "rubric": rubric,
        "source_path": source_path,
        "topic_map": topic_map,
        "valid_keys": valid_keys,
        "hashes": computed,
        "warnings": warnings,
        "provenance_preflight": provenance_preflight,
    }


def build_plan(bundle: dict[str, Any]) -> dict[str, Any]:
    manifest = bundle["manifest"]
    questions = bundle["rubric"]["questions"]
    arms = manifest["arms"]
    arm_ids = [arm["id"] for arm in arms]
    jobs: list[dict[str, Any]] = []
    positions: collections.Counter[tuple[str, int]] = collections.Counter()
    sequence = 0

    blocks = [
        (repetition, question)
        for repetition in range(1, manifest["repetitions"] + 1)
        for question in questions
    ]
    for block_index, (repetition, question) in enumerate(blocks):
        shift = block_index % len(arms)
        ordered_arms = arms[shift:] + arms[:shift]
        for order_position, arm in enumerate(ordered_arms, start=1):
            sequence += 1
            job_id = f"{arm['id']}__{question['id']}__r{repetition}"
            jobs.append(
                {
                    "sequence": sequence,
                    "block_index": block_index + 1,
                    "order_position": order_position,
                    "job_id": job_id,
                    "arm": {
                        "id": arm["id"],
                        "surface": arm["surface"],
                        "retrieval_mode": (
                            "rule" if arm["rule_retrieval"] else "policy"
                        ),
                        "persists_decision": arm["persists_decision"],
                    },
                    "question": {
                        "rubric_id": question["rubric_id"],
                        "id": question["id"],
                        "project": question["project"],
                        "corpus": question["corpus"],
                        "classes": question["classes"],
                        "exact_text": question["exact_question"],
                        "utf8_bytes": len(
                            question["exact_question"].encode("utf-8")
                        ),
                        "sha256": sha256_bytes(
                            question["exact_question"].encode("utf-8")
                        ),
                    },
                    "repetition": repetition,
                    "method": arm["method"],
                    "path": arm["path_template"].format(key=question["project"]),
                    "rule_retrieval": arm["rule_retrieval"],
                    "reasoning_effort": (
                        manifest["request_defaults"]["decision_reasoning_effort"]
                        if arm["surface"] in {"decision_light", "full_decision"}
                        else None
                    ),
                    "receipt_followup": arm["receipt_followup"],
                }
            )
            positions[(arm["id"], order_position)] += 1

    if len(jobs) != 360 or len({job["job_id"] for job in jobs}) != 360:
        raise HarnessError("plan does not contain 360 unique jobs")
    if any(
        positions[(arm_id, position)] != 10
        for arm_id in arm_ids
        for position in range(1, 7)
    ):
        raise HarnessError("cyclic schedule is not position-balanced")
    jobs_per_arm = collections.Counter(job["arm"]["id"] for job in jobs)
    if any(jobs_per_arm[arm_id] != 60 for arm_id in arm_ids):
        raise HarnessError("each arm must contain exactly 60 jobs")

    return {
        "schema_version": "consume-api-matrix-plan/1",
        "generated_at_utc": utc_now(),
        "run_id": manifest["run_id"],
        "execution_enabled": all(
            value is True for value in (manifest.get("gates") or {}).values()
        ),
        "hashes": bundle["hashes"],
        "question_count": 20,
        "repetitions": 3,
        "arm_count": 6,
        "primary_job_count": 360,
        "jobs_per_arm": dict(sorted(jobs_per_arm.items())),
        "order_position_counts": {
            arm_id: {
                str(position): positions[(arm_id, position)]
                for position in range(1, 7)
            }
            for arm_id in arm_ids
        },
        "jobs": jobs,
    }


def snapshot_inputs(bundle: dict[str, Any], run_dir: Path) -> None:
    sources = {
        "manifest.snapshot.json": bundle["manifest_path"],
        "rubric.snapshot.json": bundle["rubric_path"],
        "source.snapshot.json": bundle["source_path"],
    }
    source_markdown = resolve_configured_path(
        bundle["rubric_path"],
        bundle["rubric"]["source_markdown"]["path"],
    )
    sources["rubric-source.snapshot.md"] = source_markdown
    for destination_name, source in sources.items():
        atomic_write_bytes(run_dir / destination_name, source.read_bytes())
    if sha256_file(run_dir / "rubric.snapshot.json") != bundle["hashes"]["rubric_sha256"]:
        raise HarnessError("rubric changed while snapshotting")
    if sha256_file(run_dir / "source.snapshot.json") != bundle["hashes"]["source_snapshot_sha256"]:
        raise HarnessError("source snapshot changed while copying")
    expected_markdown_hash = bundle["rubric"]["source_markdown"]["sha256"]
    if sha256_file(run_dir / "rubric-source.snapshot.md") != expected_markdown_hash:
        raise HarnessError("rubric source markdown changed while snapshotting")
    for evidence in bundle["rubric"]["evidence_sources"]:
        configured = Path(evidence["path"])
        if configured.is_absolute():
            raise HarnessError(
                "rubric evidence paths must be relative before snapshotting"
            )
        source = resolve_configured_path(bundle["rubric_path"], evidence["path"])
        destination = (run_dir / configured).resolve()
        require_under(destination, run_dir, "rubric evidence snapshot")
        atomic_write_bytes(destination, source.read_bytes())
        if sha256_file(destination) != evidence["sha256"]:
            raise HarnessError(
                f"rubric evidence changed while snapshotting: {evidence['id']}"
            )
    atomic_write_json(
        run_dir / "rubric-provenance-preflight.json",
        bundle["provenance_preflight"],
    )


def default_run_dir(manifest: dict[str, Any]) -> Path:
    return ROOT / "runs" / manifest["run_id"]


def write_plan(bundle: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    require_under(run_dir, ROOT, "run directory")
    plan = build_plan(bundle)
    snapshot_inputs(bundle, run_dir)
    atomic_write_json(run_dir / "plan.json", plan)
    return plan


def path_from_record(run_dir: Path, relative: str) -> Path:
    path = (run_dir / relative).resolve()
    require_under(path, run_dir, "record artifact")
    return path


def valid_completed_record(record_path: Path, run_dir: Path, job: dict[str, Any]) -> bool:
    try:
        record = load_json(record_path)
        if record.get("schema_version") != "consume-api-raw-result/1":
            return False
        if record.get("job_id") != job["job_id"]:
            return False
        if record.get("sequence") != job["sequence"]:
            return False
        request = record["request"]
        response = record["response"]
        checks = (
            (request["body_path"], request["body_sha256"], request["body_bytes"]),
            (
                response["wire_body_path"],
                response["wire_body_sha256"],
                response["wire_body_bytes"],
            ),
            (
                response["decoded_body_path"],
                response["decoded_body_sha256"],
                response["decoded_body_bytes"],
            ),
        )
        for relative, expected_hash, expected_bytes in checks:
            artifact = path_from_record(run_dir, relative)
            if not artifact.exists():
                return False
            if artifact.stat().st_size != expected_bytes:
                return False
            if sha256_file(artifact) != expected_hash:
                return False
        return True
    except (HarnessError, KeyError, TypeError, OSError):
        return False


def status_for_run(run_dir: Path) -> dict[str, Any]:
    require_under(run_dir, ROOT, "run directory")
    plan = load_json(run_dir / "plan.json")
    complete = 0
    invalid = 0
    for job in plan["jobs"]:
        record_path = run_dir / "records" / f"{job['job_id']}.json"
        if not record_path.exists():
            continue
        if valid_completed_record(record_path, run_dir, job):
            complete += 1
        else:
            invalid += 1
    return {
        "run_id": plan["run_id"],
        "total": len(plan["jobs"]),
        "complete": complete,
        "invalid": invalid,
        "pending": len(plan["jobs"]) - complete - invalid,
        "execution_enabled": plan["execution_enabled"],
    }


def json_pointer(value: Any, pointer: str | None) -> Any:
    if pointer is None:
        return None
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise HarnessError(f"invalid JSON pointer: {pointer}")
    current = value
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def provision_key(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    candidates = (
        value.get("provision_key"),
        (value.get("policy") or {}).get("provision_key")
        if isinstance(value.get("policy"), dict)
        else None,
        ((value.get("payload") or {}).get("envelope") or {}).get("provision_key")
        if isinstance(value.get("payload"), dict)
        else None,
    )
    return next(
        (candidate for candidate in candidates if isinstance(candidate, str) and candidate),
        None,
    )


def ordered_unique(values: list[str | None]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def response_policy_keys(body: dict[str, Any], surface: str) -> list[str]:
    if surface == "full_decision":
        values = [
            provision_key(item)
            for item in body.get("considered") or []
            if isinstance(item, dict) and item.get("retained")
        ]
    else:
        values = [provision_key(item) for item in body.get("policies") or []]
    return ordered_unique(values)


def citation_policy_keys(body: dict[str, Any]) -> list[str]:
    return ordered_unique(
        [
            provision_key(citation.get("policy") or {})
            for citation in body.get("citations") or []
            if isinstance(citation, dict)
        ]
    )


def selected_rule_ids(body: dict[str, Any]) -> list[str]:
    values: list[str | None] = []
    for citation in body.get("citations") or []:
        if isinstance(citation, dict):
            values.append(citation.get("rule_id"))
    for container in [
        *(body.get("policies") or []),
        *(body.get("considered") or []),
    ]:
        if not isinstance(container, dict):
            continue
        match = container.get("match") or container
        selection = match.get("rule_selection") if isinstance(match, dict) else None
        if isinstance(selection, dict):
            values.extend(selection.get("selected_rule_ids") or [])
    return ordered_unique(values)


def normalized_citations(body: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for citation in body.get("citations") or []:
        if not isinstance(citation, dict):
            continue
        policy = citation.get("policy") or {}
        source = citation.get("source") or {}
        heading = policy.get("heading_path") or []
        text = source.get("text")
        result.append(
            {
                "rule_id": citation.get("rule_id"),
                "provision_key": provision_key(policy),
                "heading": " > ".join(str(part) for part in heading) or None,
                "source_state": source.get("state"),
                "source_text_sha256": (
                    sha256_bytes(text.encode("utf-8")) if isinstance(text, str) else None
                ),
                "page": source.get("page"),
                "section": source.get("section"),
            }
        )
    return result


def answer_track(
    *,
    availability: str,
    status: str | None,
    text: str | None,
    explanation: str | None,
) -> dict[str, Any]:
    return {
        "availability": availability,
        "status": status,
        "text": text,
        "explanation": explanation,
    }


def normalize_body(
    body: dict[str, Any] | None,
    arm: dict[str, Any],
    *,
    full_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = body or {}
    surface = arm["surface"]
    expected_mode = "rule" if arm["rule_retrieval"] else "policy"
    echoed_mode = json_pointer(body, arm.get("retrieval_mode_echo_pointer"))
    outcome = body.get("outcome") if isinstance(body.get("outcome"), dict) else {}
    information = (
        body.get("information") if isinstance(body.get("information"), dict) else {}
    )
    verdict = body.get("verdict") if isinstance(body.get("verdict"), dict) else {}
    receipt_source = full_body or body

    if surface == "json_only_retrieval":
        unavailable = answer_track(
            availability="not_exposed_by_contract",
            status=None,
            text=None,
            explanation=None,
        )
        answer = unavailable
        information_track = unavailable
        verdict_track = unavailable
        verdict_reached = None
        missing_information: list[Any] = []
        verification_requirements: list[Any] = []
    else:
        information_answer = information.get("answer")
        decision = verdict.get("decision")
        information_track = answer_track(
            availability=(
                "present"
                if information
                else "not_requested"
                if outcome.get("information") == "not_requested"
                else "missing_contract_violation"
            ),
            status=outcome.get("information"),
            text=information_answer if isinstance(information_answer, str) else None,
            explanation=(
                information.get("explanation")
                if isinstance(information.get("explanation"), str)
                else None
            ),
        )
        verdict_track = answer_track(
            availability=(
                "present"
                if verdict
                else "not_requested"
                if outcome.get("verdict") == "not_requested"
                else "missing_contract_violation"
            ),
            status=verdict.get("status") or outcome.get("verdict"),
            text=decision if isinstance(decision, str) else None,
            explanation=(
                verdict.get("explanation")
                if isinstance(verdict.get("explanation"), str)
                else None
            ),
        )
        if information_track["text"]:
            answer = information_track
        else:
            answer = verdict_track
        verdict_reached = (
            verdict.get("reached") if isinstance(verdict.get("reached"), bool) else None
        )
        missing_information = verdict.get("missing_information") or []
        verification_requirements = verdict.get("verification_requirements") or []

    retained = response_policy_keys(receipt_source, "full_decision")
    if not retained:
        retained = response_policy_keys(body, surface)

    return {
        "response_schema_version": body.get("schema_version"),
        "decision_id": body.get("decision_id"),
        "correlation_id": body.get("correlation_id"),
        "decision_hash": body.get("decision_hash"),
        "hash_basis": body.get("hash_basis"),
        "receipt_url": body.get("receipt_url"),
        "retrieval_status": (body.get("retrieval") or {}).get("status")
        if isinstance(body.get("retrieval"), dict)
        else None,
        "requested_retrieval_mode": expected_mode,
        "echoed_retrieval_mode": (
            echoed_mode if isinstance(echoed_mode, str) else None
        ),
        "outcome": outcome,
        "answer": answer,
        "information": information_track,
        "verdict": verdict_track,
        "verdict_reached": verdict_reached,
        "missing_information": missing_information,
        "verification_requirements": verification_requirements,
        "retained_policy_keys": retained,
        "retained_rule_ids": selected_rule_ids(receipt_source),
        "citations": normalized_citations(body),
    }


def extract_token_usage(
    body: dict[str, Any] | None,
    arm: dict[str, Any],
    *,
    http_status: int | None,
) -> dict[str, Any]:
    usage = json_pointer(body or {}, arm["token_usage_pointer"])
    if not isinstance(usage, dict):
        availability = (
            "missing_contract_violation"
            if http_status is not None and 200 <= http_status < 300
            else "not_exposed_by_contract"
        )
        return {
            "availability": availability,
            "source_pointer": arm["token_usage_pointer"],
            "calls": None,
            "calls_without_usage": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
            "arithmetic_valid": None,
        }
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    arithmetic_valid = (
        total == prompt + completion
        if all(isinstance(value, int) for value in (prompt, completion, total))
        else None
    )
    return {
        "availability": "reported",
        "source_pointer": arm["token_usage_pointer"],
        "calls": usage.get("calls"),
        "calls_without_usage": usage.get("calls_without_usage"),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": usage.get("reasoning_tokens"),
        "total_tokens": total,
        "arithmetic_valid": arithmetic_valid,
    }


def decode_http_body(raw: bytes, content_encoding: str | None) -> bytes:
    encoding = (content_encoding or "").strip().casefold()
    if encoding in {"", "identity"}:
        return raw
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    raise HarnessError(f"unsupported Content-Encoding: {content_encoding}")


def parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HarnessError(f"invalid Content-Length: {value}") from exc
    if parsed < 0:
        raise HarnessError(f"negative Content-Length: {value}")
    return parsed


def worker_request(spec_path: Path, result_path: Path) -> int:
    spec = load_json(spec_path)
    started_at = utc_now()
    started_perf = time.perf_counter()
    capability = os.environ.get("CONSUME_MATRIX_WORKER_CAPABILITY")
    if not capability or sha256_bytes(capability.encode("utf-8")) != spec.get(
        "worker_capability_sha256"
    ):
        atomic_write_json(
            result_path,
            {
                "ok": False,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "wall_ms": round((time.perf_counter() - started_perf) * 1000),
                "error_type": "WorkerCapabilityRejected",
                "error": "internal worker capability is absent or invalid",
            },
        )
        return 2
    offline_sleep = spec.get("offline_self_test_sleep_seconds")
    if offline_sleep is not None:
        if os.environ.get("CONSUME_MATRIX_OFFLINE_SELFTEST") != "1":
            raise HarnessError("offline worker sleep is restricted to self-test mode")
        time.sleep(float(offline_sleep))
    secret = os.environ.get(spec["credential_env"])
    base_url = os.environ.get(spec["base_url_env"])
    if not base_url:
        atomic_write_json(
            result_path,
            {
                "ok": False,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "wall_ms": round((time.perf_counter() - started_perf) * 1000),
                "error_type": "MissingBaseUrl",
                "error": f"environment variable {spec['base_url_env']} is not set",
            },
        )
        return 2
    if not secret:
        atomic_write_json(
            result_path,
            {
                "ok": False,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "wall_ms": round((time.perf_counter() - started_perf) * 1000),
                "error_type": "MissingCredential",
                "error": f"environment variable {spec['credential_env']} is not set",
            },
        )
        return 2

    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HarnessError("base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HarnessError("base URL must not contain credentials, query, or fragment")

    body = Path(spec["body_path"]).read_bytes() if spec.get("body_path") else None
    headers = dict(spec.get("safe_headers") or {})
    headers["X-Policy-Subscription-Key"] = secret
    headers["Accept-Encoding"] = "gzip, identity"
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))

    connection_class = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection_kwargs: dict[str, Any] = {
        "host": parsed.hostname,
        "port": parsed.port,
        "timeout": spec["socket_timeout_seconds"],
    }
    if parsed.scheme == "https":
        connection_kwargs["context"] = ssl.create_default_context()
    connection = connection_class(**connection_kwargs)
    path = f"{parsed.path.rstrip('/')}{spec['path']}" or "/"
    wire_path = Path(spec["wire_path"])
    decoded_path = Path(spec["decoded_path"])
    try:
        connection.request(spec["method"], path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        response_headers = {
            name.casefold(): value
            for name, value in response.getheaders()
            if name.casefold() in SAFE_RESPONSE_HEADERS
        }
        atomic_write_bytes(wire_path, raw)
        decoded = decode_http_body(raw, response_headers.get("content-encoding"))
        atomic_write_bytes(decoded_path, decoded)
        atomic_write_json(
            result_path,
            {
                "ok": True,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "wall_ms": round((time.perf_counter() - started_perf) * 1000),
                "http_status": response.status,
                "reason": response.reason,
                "safe_headers": response_headers,
                "content_length_header": parse_content_length(
                    response_headers.get("content-length")
                ),
                "wire_path": str(wire_path),
                "wire_body_bytes": len(raw),
                "wire_body_sha256": sha256_bytes(raw),
                "decoded_path": str(decoded_path),
                "decoded_body_bytes": len(decoded),
                "decoded_body_sha256": sha256_bytes(decoded),
            },
        )
        return 0
    except Exception as exc:  # isolated worker boundary records the exact failure class
        redacted = str(exc).replace(secret, "[REDACTED]")
        atomic_write_json(
            result_path,
            {
                "ok": False,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "wall_ms": round((time.perf_counter() - started_perf) * 1000),
                "error_type": type(exc).__name__,
                "error": redacted[:500],
            },
        )
        return 1
    finally:
        connection.close()


def terminate_worker(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_worker_with_watchdog(
    *,
    spec_path: Path,
    result_path: Path,
    hard_timeout_seconds: float,
    heartbeat_interval_seconds: float,
    suspension_gap_seconds: float,
    worker_capability: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    last_heartbeat = started
    max_gap = 0.0
    suspension_detected = False
    worker_environment = os.environ.copy()
    worker_environment["CONSUME_MATRIX_WORKER_CAPABILITY"] = worker_capability
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_worker",
            "--spec",
            str(spec_path),
            "--result",
            str(result_path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=worker_environment,
    )
    timed_out = False
    while process.poll() is None:
        time.sleep(heartbeat_interval_seconds)
        now = time.perf_counter()
        gap = now - last_heartbeat
        max_gap = max(max_gap, gap)
        if heartbeat_gap_is_suspension(gap, suspension_gap_seconds):
            suspension_detected = True
        last_heartbeat = now
        if now - started >= hard_timeout_seconds:
            timed_out = True
            terminate_worker(process)
            break
    completed = time.perf_counter()
    monitor = {
        "wall_ms": round((completed - started) * 1000),
        "max_heartbeat_gap_ms": round(max_gap * 1000),
        "suspension_detected": suspension_detected,
        "timed_out": timed_out,
        "worker_exit_code": process.returncode,
    }
    if timed_out:
        return {
            "ok": False,
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "error_type": "AttemptWatchdogTimeout",
            "error": f"worker exceeded {hard_timeout_seconds} seconds",
        }, monitor
    if not result_path.exists():
        return {
            "ok": False,
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "error_type": "WorkerResultMissing",
            "error": f"worker exited {process.returncode} without a result",
        }, monitor
    return load_json(result_path), monitor


def heartbeat_gap_is_suspension(gap_seconds: float, threshold_seconds: float) -> bool:
    return gap_seconds > threshold_seconds


def response_artifact(
    run_dir: Path,
    destination_stem: str,
    worker_result: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    response_dir = run_dir / "responses"
    wire_destination = response_dir / f"{destination_stem}.wire"
    decoded_destination = response_dir / f"{destination_stem}.decoded"
    if worker_result and worker_result.get("ok"):
        wire = Path(worker_result["wire_path"]).read_bytes()
        decoded = Path(worker_result["decoded_path"]).read_bytes()
        status = worker_result.get("http_status")
        safe_headers = worker_result.get("safe_headers") or {}
        content_length = worker_result.get("content_length_header")
    else:
        wire = b""
        decoded = b""
        status = None
        safe_headers = {}
        content_length = None
    atomic_write_bytes(wire_destination, wire)
    atomic_write_bytes(decoded_destination, decoded)
    parsed_body: dict[str, Any] | None = None
    logical_bytes: int | None = None
    if decoded:
        try:
            parsed = json.loads(decoded.decode("utf-8"))
            if isinstance(parsed, dict):
                parsed_body = parsed
            logical_bytes = len(canonical_json_bytes(parsed))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed_body = None
    response = {
        "http_status": status,
        "content_type": safe_headers.get("content-type"),
        "content_encoding": safe_headers.get("content-encoding"),
        "content_length_header": content_length,
        "wire_body_path": str(wire_destination.relative_to(run_dir)),
        "wire_body_bytes": len(wire),
        "wire_body_sha256": sha256_bytes(wire),
        "decoded_body_path": str(decoded_destination.relative_to(run_dir)),
        "decoded_body_bytes": len(decoded),
        "decoded_body_sha256": sha256_bytes(decoded),
        "logical_json_bytes": logical_bytes,
        "safe_headers": safe_headers,
    }
    return response, parsed_body


def expected_schema(surface: str) -> str:
    return {
        "decision_light": "case_decision_light_v1",
        "full_decision": "case_decision_v2",
        "json_only_retrieval": "policy_retrieval_v1",
    }[surface]


def receipt_hash_valid(
    body: dict[str, Any] | None,
    repository_src_path: str,
) -> bool | None:
    if not body or body.get("schema_version") != "case_decision_v2":
        return None
    source = str(Path(repository_src_path).resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        from policy_platform.contracts.case_decision import (
            CaseDecisionEnvelopeV2,
            compute_decision_hash_v2,
            validate_receipt,
        )
    except ImportError as exc:
        raise HarnessError(
            "the repository environment is required to recompute receipt hashes"
        ) from exc
    parsed = validate_receipt(body)
    if not isinstance(parsed, CaseDecisionEnvelopeV2):
        return False
    return compute_decision_hash_v2(parsed) == body.get("decision_hash")


def build_integrity(
    *,
    primary_body: dict[str, Any] | None,
    full_body: dict[str, Any] | None,
    arm: dict[str, Any],
    response: dict[str, Any],
    normalized: dict[str, Any],
    token_usage: dict[str, Any],
    valid_source_keys: set[str],
    repository_src_path: str,
) -> dict[str, Any]:
    issues: list[str] = []
    http_status = response["http_status"]
    success = isinstance(http_status, int) and 200 <= http_status < 300
    json_valid = primary_body is not None
    if success and not json_valid:
        issues.append("successful response is not a JSON object")
    contract_valid = (
        json_valid
        and primary_body.get("schema_version") == expected_schema(arm["surface"])
        if success
        else True
    )
    if success and not contract_valid:
        issues.append("response schema_version violates the arm contract")

    expected_mode = "rule" if arm["rule_retrieval"] else "policy"
    echoed_mode = normalized["echoed_retrieval_mode"]
    mode_echo_valid = echoed_mode == expected_mode if success else None
    if success and not mode_echo_valid:
        issues.append("retrieval mode echo is absent or mismatched")
    no_mode_downgrade = not success or echoed_mode == expected_mode

    content_length = response["content_length_header"]
    content_length_matches = (
        content_length == response["wire_body_bytes"]
        if content_length is not None
        else None
    )
    if content_length_matches is False:
        issues.append("Content-Length differs from captured wire body bytes")

    cited_keys = {
        citation["provision_key"]
        for citation in normalized["citations"]
        if citation["provision_key"]
    }
    retained_keys = set(normalized["retained_policy_keys"])
    quoted = all(
        citation["source_state"] == "quoted" for citation in normalized["citations"]
    )
    if arm["surface"] == "json_only_retrieval":
        citation_integrity = None
    else:
        light_keys = (
            set(response_policy_keys(primary_body or {}, "decision_light"))
            if arm["surface"] == "decision_light"
            else retained_keys
        )
        citation_integrity = (
            cited_keys <= retained_keys
            and cited_keys <= light_keys
            and quoted
        )
        if not citation_integrity:
            issues.append("citation keys are not quoted retained evidence")

    non_fabrication_valid = (
        retained_keys <= valid_source_keys and cited_keys <= valid_source_keys
    )
    if not non_fabrication_valid:
        issues.append("response contains a provision key outside the frozen corpus")

    receipt_body = full_body or (
        primary_body if arm["surface"] == "full_decision" else None
    )
    hash_valid = receipt_hash_valid(receipt_body, repository_src_path)
    if receipt_body is not None and hash_valid is not True:
        issues.append("full receipt decision hash did not independently validate")
    expected_hash_basis = "case_decision_v2_lang_verification"
    hash_basis_valid = (
        primary_body is not None
        and primary_body.get("hash_basis") == expected_hash_basis
        and (
            full_body is None
            or full_body.get("hash_basis") == expected_hash_basis
        )
        if arm["surface"] in {"decision_light", "full_decision"} and success
        else None
    )
    if hash_basis_valid is False:
        issues.append(
            "decision hash basis differs from the required v2 language/verification basis"
        )

    if arm["surface"] == "decision_light" and primary_body and full_body:
        full_light_identity = all(
            primary_body.get(field) == full_body.get(field)
            for field in ("decision_id", "correlation_id", "decision_hash")
        )
        token_matches = json_pointer(
            primary_body, arm["token_usage_pointer"]
        ) == json_pointer(full_body, arm["token_usage_pointer"])
        stage_matches = json_pointer(
            primary_body, "/trace/stage_latency_ms"
        ) == json_pointer(full_body, "/trace/stage_latency_ms")
    elif arm["surface"] == "decision_light":
        full_light_identity = False
        token_matches = False
        stage_matches = False
    else:
        full_light_identity = None
        token_matches = None
        stage_matches = None
    if full_light_identity is False:
        issues.append("Decision Light and full receipt identities differ or are missing")
    if token_matches is False:
        issues.append("Decision Light and full receipt token usage differ")
    if stage_matches is False:
        issues.append("Decision Light and full receipt stage timings differ")

    token_valid = (
        token_usage["availability"] == "reported"
        and token_usage["arithmetic_valid"] is not False
    )
    if success and not token_valid:
        issues.append("required token usage is absent or internally invalid")

    return {
        "json_valid": json_valid,
        "contract_valid": contract_valid,
        "mode_echo_valid": mode_echo_valid,
        "no_mode_downgrade": no_mode_downgrade,
        "content_length_matches_wire": content_length_matches,
        "receipt_hash_valid": hash_valid,
        "hash_basis_valid": hash_basis_valid,
        "full_light_identity_valid": full_light_identity,
        "token_usage_matches_receipt": token_matches,
        "stage_latency_matches_receipt": stage_matches,
        "citation_integrity_valid": citation_integrity,
        "non_fabrication_valid": non_fabrication_valid,
        "token_usage_valid": token_valid,
        "issues": issues,
    }


def request_body_for_job(
    job: dict[str, Any],
    manifest: dict[str, Any],
    run_id: str,
) -> bytes:
    defaults = manifest["request_defaults"]
    correlation_id, _ = job_identity_values(job, run_id)
    payload: dict[str, Any] = {"scenario": job["question"]["exact_text"]}
    if job["arm"]["surface"] in {"decision_light", "full_decision"}:
        payload["provision_id"] = None
        payload["rule_retrieval"] = job["rule_retrieval"]
        payload["calling_system_identity"] = defaults["calling_system_identity"]
        payload["reasoning_effort"] = defaults["decision_reasoning_effort"]
    else:
        payload["correlation_id"] = correlation_id
        payload["rule_retrieval"] = job["rule_retrieval"]
    return canonical_json_bytes(payload)


def job_identity_values(
    job: dict[str, Any],
    run_id: str,
) -> tuple[str, str | None]:
    correlation_digest = sha256_bytes(f"{run_id}\0{job['job_id']}".encode("utf-8"))
    correlation_id = f"matrix-{correlation_digest[:32]}"
    if job["arm"]["persists_decision"]:
        idempotency_digest = sha256_bytes(
            f"{run_id}\0{job['job_id']}\0idempotency".encode("utf-8")
        )
        idempotency_key = f"matrix-idem-{idempotency_digest[:32]}"
    else:
        idempotency_key = None
    return correlation_id, idempotency_key


def worker_spec(
    *,
    manifest: dict[str, Any],
    method: str,
    path: str,
    body_path: Path | None,
    safe_headers: dict[str, str],
    attempt_dir: Path,
    socket_timeout_seconds: float,
    worker_capability: str,
) -> dict[str, Any]:
    return {
        "base_url_env": manifest["base_url_env"],
        "credential_env": manifest["credential_env"],
        "method": method,
        "path": path,
        "body_path": str(body_path) if body_path else None,
        "safe_headers": safe_headers,
        "socket_timeout_seconds": socket_timeout_seconds,
        "worker_capability_sha256": sha256_bytes(worker_capability.encode("utf-8")),
        "wire_path": str(attempt_dir / "response.wire"),
        "decoded_path": str(attempt_dir / "response.decoded"),
    }


def perform_attempt(
    *,
    manifest: dict[str, Any],
    method: str,
    path: str,
    body_path: Path | None,
    safe_headers: dict[str, str],
    attempt_dir: Path,
    socket_timeout_seconds: float,
    hard_timeout_seconds: float,
    worker_capability: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    spec_path = attempt_dir / "worker-spec.json"
    result_path = attempt_dir / "worker-result.json"
    atomic_write_json(
        spec_path,
        worker_spec(
            manifest=manifest,
            method=method,
            path=path,
            body_path=body_path,
            safe_headers=safe_headers,
            attempt_dir=attempt_dir,
            socket_timeout_seconds=socket_timeout_seconds,
            worker_capability=worker_capability,
        ),
    )
    watchdog = manifest["watchdog"]
    return run_worker_with_watchdog(
        spec_path=spec_path,
        result_path=result_path,
        hard_timeout_seconds=hard_timeout_seconds,
        heartbeat_interval_seconds=watchdog["heartbeat_interval_seconds"],
        suspension_gap_seconds=watchdog["suspension_gap_seconds"],
        worker_capability=worker_capability,
    )


def attempt_summary(
    number: int,
    worker_result: dict[str, Any],
    monitor: dict[str, Any],
    *,
    retryable: bool,
) -> dict[str, Any]:
    status = worker_result.get("http_status")
    if monitor["timed_out"]:
        result = "timeout"
    elif not worker_result.get("ok"):
        result = "transport_failure"
    elif isinstance(status, int) and 200 <= status < 300:
        result = "success"
    else:
        result = "http_outcome"
    return {
        "number": number,
        "started_at_utc": worker_result.get("started_at_utc") or utc_now(),
        "completed_at_utc": worker_result.get("completed_at_utc") or utc_now(),
        "result": result,
        "http_status": status,
        "error_type": worker_result.get("error_type"),
        "retryable": retryable,
        "worker_exit_code": monitor.get("worker_exit_code"),
        "wall_ms": (
            worker_result.get("wall_ms")
            if isinstance(worker_result.get("wall_ms"), int)
            else monitor["wall_ms"]
        ),
        "suspension_detected": monitor["suspension_detected"],
        "max_heartbeat_gap_ms": monitor["max_heartbeat_gap_ms"],
        "timed_out": monitor["timed_out"],
    }


def execute_job(
    bundle: dict[str, Any],
    plan: dict[str, Any],
    job: dict[str, Any],
    run_dir: Path,
    worker_capability: str,
) -> dict[str, Any]:
    manifest = bundle["manifest"]
    arm_config = next(arm for arm in manifest["arms"] if arm["id"] == job["arm"]["id"])
    correlation_id, idempotency_key = job_identity_values(job, plan["run_id"])
    request_body = request_body_for_job(job, manifest, plan["run_id"])
    request_path = run_dir / "requests" / f"{job['job_id']}.body"
    atomic_write_bytes(request_path, request_body)
    safe_headers = {
        "Content-Type": "application/json",
        "X-Correlation-Id": correlation_id,
    }
    if idempotency_key:
        safe_headers["Idempotency-Key"] = idempotency_key

    watchdog = manifest["watchdog"]
    decision_surface = arm_config["surface"] != "json_only_retrieval"
    socket_timeout = (
        watchdog["decision_read_timeout_seconds"]
        if decision_surface
        else watchdog["retrieval_read_timeout_seconds"]
    )
    hard_timeout = (
        watchdog["decision_attempt_hard_timeout_seconds"]
        if decision_surface
        else watchdog["retrieval_attempt_hard_timeout_seconds"]
    )
    attempt_summaries: list[dict[str, Any]] = []
    final_worker_result: dict[str, Any] | None = None
    final_monitor: dict[str, Any] | None = None
    retryable_statuses = set(watchdog["retryable_http_statuses"])

    for attempt_number in range(1, watchdog["max_attempts"] + 1):
        attempt_dir = run_dir / "attempts" / job["job_id"] / str(attempt_number)
        worker_result, monitor = perform_attempt(
            manifest=manifest,
            method=job["method"],
            path=job["path"],
            body_path=request_path,
            safe_headers=safe_headers,
            attempt_dir=attempt_dir,
            socket_timeout_seconds=socket_timeout,
            hard_timeout_seconds=hard_timeout,
            worker_capability=worker_capability,
        )
        status = worker_result.get("http_status")
        retryable = (
            monitor["timed_out"]
            or not worker_result.get("ok")
            or status in retryable_statuses
        )
        if status == 503 and job["rule_retrieval"]:
            retryable = False
        summary = attempt_summary(
            attempt_number,
            worker_result,
            monitor,
            retryable=retryable and attempt_number < watchdog["max_attempts"],
        )
        attempt_summaries.append(summary)
        atomic_write_json(attempt_dir / "attempt-summary.json", summary)
        final_worker_result = worker_result
        final_monitor = monitor
        if not retryable or attempt_number == watchdog["max_attempts"]:
            break
        time.sleep(min(2 ** (attempt_number - 1), 8))

    assert final_monitor is not None
    response, primary_body = response_artifact(
        run_dir, job["job_id"], final_worker_result
    )
    followups: list[dict[str, Any]] = []
    full_body: dict[str, Any] | None = None

    if (
        arm_config["receipt_followup"]
        and response["http_status"] == 200
        and primary_body
    ):
        receipt_url = primary_body.get("receipt_url")
        if isinstance(receipt_url, str) and receipt_url.startswith("/"):
            receipt_dir = run_dir / "attempts" / job["job_id"] / "receipt"
            receipt_result, receipt_monitor = perform_attempt(
                manifest=manifest,
                method="GET",
                path=receipt_url,
                body_path=None,
                safe_headers={"X-Correlation-Id": correlation_id},
                attempt_dir=receipt_dir,
                socket_timeout_seconds=watchdog["receipt_attempt_hard_timeout_seconds"],
                hard_timeout_seconds=watchdog["receipt_attempt_hard_timeout_seconds"],
                worker_capability=worker_capability,
            )
            receipt_response, full_body = response_artifact(
                run_dir, f"{job['job_id']}__receipt", receipt_result
            )
            atomic_write_json(receipt_dir / "monitor.json", receipt_monitor)
            followups.append(
                {
                    "purpose": "full_receipt_integrity",
                    "method": "GET",
                    "path": receipt_url,
                    "wall_ms": receipt_monitor["wall_ms"],
                    "response": receipt_response,
                }
            )

    normalized = normalize_body(primary_body, arm_config, full_body=full_body)
    token_usage = extract_token_usage(
        primary_body,
        arm_config,
        http_status=response["http_status"],
    )
    stage_latency = json_pointer(primary_body or {}, "/trace/stage_latency_ms")
    if not isinstance(stage_latency, dict):
        stage_latency = {}
    server_latency = (
        primary_body.get("latency_ms")
        if primary_body
        and arm_config["surface"] in {"decision_light", "json_only_retrieval"}
        and isinstance(primary_body.get("latency_ms"), int)
        else None
    )
    integrity = build_integrity(
        primary_body=primary_body,
        full_body=full_body,
        arm=arm_config,
        response=response,
        normalized=normalized,
        token_usage=token_usage,
        valid_source_keys=bundle["valid_keys"][job["question"]["project"]],
        repository_src_path=manifest["repository_src_path"],
    )
    started_at = attempt_summaries[-1]["started_at_utc"]
    completed_at = attempt_summaries[-1]["completed_at_utc"]
    record = {
        "schema_version": "consume-api-raw-result/1",
        "run_id": plan["run_id"],
        "job_id": job["job_id"],
        "sequence": job["sequence"],
        "arm": job["arm"],
        "question": {
            "id": job["question"]["id"],
            "corpus": job["question"]["corpus"],
            "policy_set_key": job["question"]["project"],
            "exact_text": job["question"]["exact_text"],
            "utf8_bytes": job["question"]["utf8_bytes"],
            "sha256": job["question"]["sha256"],
        },
        "repetition": job["repetition"],
        "provenance": {
            **bundle["hashes"],
            "endpoint_contract_version": manifest["schema_version"],
            "repository_commit": None,
            "service_build": None,
            "model_deployment": None,
            "prompt_versions": {},
            "policy_version_id": (
                (primary_body.get("active_version") or {}).get("version_id")
                if primary_body and isinstance(primary_body.get("active_version"), dict)
                else None
            ),
            "index_manifest_id": None,
            "captured_at_utc": utc_now(),
        },
        "request": {
            "method": job["method"],
            "path": job["path"],
            "rule_retrieval": job["rule_retrieval"],
            "provision_id": None,
            "provision_id_sent": job["arm"]["surface"] != "json_only_retrieval",
            "correlation_id": correlation_id,
            "idempotency_key_sha256": (
                sha256_bytes(idempotency_key.encode("utf-8"))
                if idempotency_key
                else None
            ),
            "content_type": "application/json",
            "content_length_header": len(request_body),
            "body_path": str(request_path.relative_to(run_dir)),
            "body_bytes": len(request_body),
            "body_sha256": sha256_bytes(request_body),
            "safe_headers": {
                "content-type": "application/json",
                "x-correlation-id": correlation_id,
            },
        },
        "attempts": attempt_summaries,
        "timing": {
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "wall_ms": (
                final_worker_result.get("wall_ms")
                if final_worker_result
                and isinstance(final_worker_result.get("wall_ms"), int)
                else final_monitor["wall_ms"]
            ),
            "server_latency_ms": server_latency,
            "stage_latency_ms": stage_latency,
            "suspension_detected": final_monitor["suspension_detected"],
            "max_heartbeat_gap_ms": final_monitor["max_heartbeat_gap_ms"],
            "latency_valid_for_comparison": not final_monitor["suspension_detected"],
        },
        "response": response,
        "followups": followups,
        "token_usage": token_usage,
        "normalized": normalized,
        "integrity": integrity,
    }
    record_path = run_dir / "records" / f"{job['job_id']}.json"
    atomic_write_json(record_path, record)
    return record


def dimension(status: str, reason: str) -> dict[str, str]:
    return {"status": status, "reason": reason}


def evaluate_record(
    record: dict[str, Any],
    question: dict[str, Any],
    valid_source_keys: set[str],
    provenance_preflight: dict[str, Any],
) -> dict[str, Any]:
    normalized = record["normalized"]
    arm = record["arm"]
    required = set(question["expected_evidence"]["required"])
    retained = set(normalized["retained_policy_keys"])
    cited = {
        citation["provision_key"]
        for citation in normalized["citations"]
        if citation["provision_key"]
    }
    if arm["surface"] == "json_only_retrieval":
        hit = required & retained
        miss = required - retained
    else:
        hit = required & retained & cited
        miss = required - (retained & cited)

    dimensions: dict[str, dict[str, str]] = {}
    if question["irrelevant"]:
        dimensions["R1"] = dimension("not_applicable", "irrelevant control has no required evidence")
    else:
        dimensions["R1"] = dimension(
            "pass" if not miss else "fail",
            "all required evidence served" if not miss else "required evidence missing",
        )
    if arm["surface"] == "json_only_retrieval":
        dimensions["R2"] = dimension("not_applicable", "retrieval surface exposes no decision citations")
    else:
        dimensions["R2"] = dimension(
            "pass" if record["integrity"]["citation_integrity_valid"] else "fail",
            "citation integrity check",
        )

    expected_tracks = question["expected_tracks"]
    information_status = normalized["outcome"].get("information")
    verdict_status = normalized["outcome"].get("verdict")
    if arm["surface"] == "json_only_retrieval":
        dimensions["R3"] = dimension("not_applicable", "retrieval surface exposes no answer tracks")
        dimensions["R4"] = dimension("not_applicable", "retrieval surface exposes no verdict")
    else:
        tracks_valid = (
            information_status in expected_tracks["information"]
            and verdict_status in expected_tracks["verdict"]
            and not (
                information_status == "not_evaluated"
                and verdict_status == "not_evaluated"
            )
        )
        forbidden_pairs = {
            tuple(pair) for pair in question.get("forbidden_outcome_pairs") or []
        }
        if (information_status, verdict_status) in forbidden_pairs:
            tracks_valid = False
        dimensions["R3"] = dimension(
            "pass" if tracks_valid else "fail",
            "outcome tracks match rubric" if tracks_valid else "unexpected outcome pair",
        )
        verdict = normalized["verdict"]
        missing = normalized["missing_information"]
        verification = normalized["verification_requirements"]
        missing_status = verdict["status"] == "missing_required_facts"
        missing_consistent = bool(missing) == missing_status
        verification_consistent = not verification or normalized["verdict_reached"] is True
        dimensions["R4"] = dimension(
            "pass" if missing_consistent and verification_consistent else "fail",
            "verdict missing-information and verification discipline",
        )

    if question["irrelevant"]:
        if arm["surface"] == "json_only_retrieval":
            dimensions["R5"] = dimension(
                "not_applicable",
                "E/F irrelevant retrieval behavior is measured on first run, not pre-scored",
            )
        else:
            safe = (
                not normalized["citations"]
                and normalized["verdict_reached"] is not True
                and not (normalized["verdict"]["text"] or "").strip()
                and not (normalized["information"]["text"] or "").strip()
                and information_status in {"not_requested", "no_rule_bears"}
                and verdict_status in {"not_requested", "no_rule_bears"}
            )
            dimensions["R5"] = dimension(
                "pass" if safe else "fail",
                "irrelevant refusal safety",
            )
    else:
        dimensions["R5"] = dimension("not_applicable", "not an irrelevant control")

    if arm["surface"] == "decision_light":
        r7_values = (
            record["integrity"]["receipt_hash_valid"],
            record["integrity"]["hash_basis_valid"],
            record["integrity"]["full_light_identity_valid"],
            record["integrity"]["token_usage_matches_receipt"],
            record["integrity"]["stage_latency_matches_receipt"],
        )
        r7_pass = all(value is True for value in r7_values)
        dimensions["R7"] = dimension(
            "pass" if r7_pass else "fail",
            "Decision Light/full receipt integrity",
        )
    elif arm["surface"] == "full_decision":
        r7_pass = (
            record["integrity"]["receipt_hash_valid"] is True
            and record["integrity"]["hash_basis_valid"] is True
        )
        dimensions["R7"] = dimension(
            "pass" if r7_pass else "fail",
            "full receipt hash integrity",
        )
    else:
        dimensions["R7"] = dimension("not_applicable", "retrieval surface has no receipt")

    all_keys = retained | cited
    r8_pass = all_keys <= valid_source_keys and record["integrity"]["non_fabrication_valid"]
    if normalized["retrieval_status"] not in {None, "narrowed", "served"} and cited:
        r8_pass = False
    dimensions["R8"] = dimension(
        "pass" if r8_pass else "fail",
        "all evidence belongs to the frozen corpus",
    )
    if len(required) > 1:
        dimensions["R9"] = dimension(
            "pass" if not miss else "fail",
            "all required composition provisions served",
        )
    else:
        dimensions["R9"] = dimension("not_applicable", "single-provision or irrelevant question")

    gate = gate_evaluation(
        question,
        dimensions,
        provenance_preflight,
        arm["id"],
    )
    manual_criteria = question.get("manual_criteria") or []
    return {
        "repetition": record["repetition"],
        "job_id": record["job_id"],
        "raw_record_sha256": sha256_bytes(canonical_json_bytes(record)),
        "dimensions": dimensions,
        "expected_evidence_hit": sorted(hit),
        "expected_evidence_miss": sorted(miss),
        "retained_evidence_miss": sorted(required - retained),
        "citation_evidence_miss": (
            [] if arm["surface"] == "json_only_retrieval" else sorted(required - cited)
        ),
        "manual_review_required": gate["manual_review_required"],
        "manual_criteria": manual_criteria,
        "manual_criterion_provenance": gate["manual_criteria"],
        "criterion_results": gate["criterion_results"],
        "actionable_target_rule_conclusion": gate[
            "actionable_target_rule_conclusion"
        ],
        "observed_dimension_failures": gate["observed_dimension_failures"],
        "product_failures": gate["product_failures"],
        "harness_failures": gate["harness_failures"],
        "rubric_findings": gate["rubric_findings"],
        "unresolved_criteria": gate["unresolved_criteria"],
        "scored_result": gate["scored_result"],
        "scored_failures": gate["product_failures"],
    }


def stability_measurement(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    outcomes = [
        json.dumps(record["normalized"]["outcome"], sort_keys=True)
        for record in records
    ]
    citation_sets = [
        json.dumps(
            sorted(
                citation["provision_key"]
                for citation in record["normalized"]["citations"]
                if citation["provision_key"]
            )
        )
        for record in records
    ]
    outcome_k = max(collections.Counter(outcomes).values(), default=0)
    citation_k = max(collections.Counter(citation_sets).values(), default=0)
    return {
        "measurement_only": True,
        "n": n,
        "outcome_stability": {"k": outcome_k, "n": n},
        "citation_stability": {"k": citation_k, "n": n},
    }


def metric_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "repetition": record["repetition"],
        "retained_cardinality": len(record["normalized"]["retained_policy_keys"]),
        "citation_keys": sorted(
            citation["provision_key"]
            for citation in record["normalized"]["citations"]
            if citation["provision_key"]
        ),
        "total_tokens": record["token_usage"]["total_tokens"],
        "outcome": record["normalized"]["outcome"],
        "wall_ms": record["timing"]["wall_ms"],
        "latency_valid_for_comparison": record["timing"][
            "latency_valid_for_comparison"
        ],
        "request_body_bytes": record["request"]["body_bytes"],
        "wire_body_bytes": record["response"]["wire_body_bytes"],
        "logical_json_bytes": record["response"]["logical_json_bytes"],
    }


def derive_results(bundle: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    plan = load_json(run_dir / "plan.json")
    question_by_id = {
        question["id"]: question for question in bundle["rubric"]["questions"]
    }
    records: list[dict[str, Any]] = []
    for job in plan["jobs"]:
        record_path = run_dir / "records" / f"{job['job_id']}.json"
        if record_path.exists() and valid_completed_record(record_path, run_dir, job):
            records.append(load_json(record_path))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        grouped[(record["arm"]["id"], record["question"]["id"])].append(record)
    arm_pair = {"A": "B", "B": "A", "C": "D", "D": "C", "E": "F", "F": "E"}
    retrieval_control = {"A": "E", "C": "E", "B": "F", "D": "F"}
    output: list[dict[str, Any]] = []

    for (arm_id, question_id), group in sorted(grouped.items()):
        group.sort(key=lambda record: record["repetition"])
        question = question_by_id[question_id]
        per_repeat = [
            evaluate_record(
                record,
                question,
                bundle["valid_keys"][question["project"]],
                bundle["provenance_preflight"],
            )
            for record in group
        ]
        comparison_group = sorted(
            grouped.get((arm_pair[arm_id], question_id), []),
            key=lambda record: record["repetition"],
        )
        metric_values = [metric_snapshot(record) for record in group]
        valid_latencies = [
            value["wall_ms"]
            for value in metric_values
            if value["latency_valid_for_comparison"]
        ]
        expected_miss = sorted(
            set().union(
                *(set(item["expected_evidence_miss"]) for item in per_repeat)
            )
        )
        control_arm_id = retrieval_control.get(arm_id)
        control_by_repetition = {
            record["repetition"]: set(record["normalized"]["retained_policy_keys"])
            for record in grouped.get((control_arm_id, question_id), [])
        } if control_arm_id else {}
        miss_details = [
            {
                "provision_key": key,
                "retrieval_control_arm_id": control_arm_id,
                "presence_by_repetition": [
                    {
                        "repetition": repetition,
                        "present": (
                            key in control_by_repetition[repetition]
                            if repetition in control_by_repetition
                            else None
                        ),
                    }
                    for repetition in range(1, 4)
                ],
            }
            for key in expected_miss
        ]
        row = {
            "schema_version": "consume-api-derived-result/2",
            "run_id": plan["run_id"],
            "arm": group[0]["arm"],
            "reasoning_effort": (
                bundle["manifest"]["request_defaults"]["decision_reasoning_effort"]
                if group[0]["arm"]["surface"] in {"decision_light", "full_decision"}
                else None
            ),
            "question": {
                "rubric_id": question["rubric_id"],
                "id": question_id,
                "project": question["project"],
                "corpus": question["corpus"],
                "classes": question["classes"],
            },
            "n": len(group),
            "rubric_sha256": bundle["hashes"]["rubric_sha256"],
            "source_snapshot_sha256": bundle["hashes"]["source_snapshot_sha256"],
            "repetitions": per_repeat,
            "expected_evidence_hit": sorted(
                set.intersection(
                    *(set(item["expected_evidence_hit"]) for item in per_repeat)
                )
                if per_repeat
                else set()
            ),
            "expected_evidence_miss": expected_miss,
            "expected_evidence_miss_details": miss_details,
            "actionable_target_rule_conclusion": arm_id in {"A", "C", "E"},
            "scored_result": rollup_scored_results(
                [item["scored_result"] for item in per_repeat]
            ),
            "provenance_preflight": {
                "status": bundle["provenance_preflight"]["status"],
                "criterion_count": bundle["provenance_preflight"][
                    "criterion_count"
                ],
                "rubric_finding_count": len(
                    bundle["provenance_preflight"]["rubric_findings"]
                ),
            },
            "historical_replay": bundle["rubric"]["historical_replay"],
            "R6": stability_measurement(group),
            "R10": {
                "measurement_only": True,
                "comparison_arm_id": arm_pair[arm_id],
                "this_arm": metric_values,
                "comparison_arm": [
                    metric_snapshot(record) for record in comparison_group
                ],
            },
            "metrics": {
                "valid_latency_n": len(valid_latencies),
                "median_wall_ms": (
                    round(statistics.median(valid_latencies))
                    if valid_latencies
                    else None
                ),
            },
        }
        output.append(row)
        atomic_write_json(
            run_dir / "derived" / f"{arm_id}__{question_id}.json",
            row,
        )
    atomic_write_json(run_dir / "reports" / "derived-results.json", output)
    return output


def verify_authorization(
    bundle: dict[str, Any],
    authorization_path: Path,
    confirm_run_id: str,
) -> dict[str, Any]:
    authorization = load_json(authorization_path)
    manifest = bundle["manifest"]
    if confirm_run_id != manifest["run_id"]:
        raise HarnessError("--confirm-run-id does not match the manifest run_id")
    if authorization.get("authorized") is not True:
        raise HarnessError("authorization.authorized is not true")
    if authorization.get("rule_retrieval_stable") is not True:
        raise HarnessError("authorization does not confirm Rule Retrieval stability")
    if authorization.get("parent_session_id") != manifest["parent_session_id"]:
        raise HarnessError("authorization parent_session_id mismatch")
    if authorization.get("run_id") != manifest["run_id"]:
        raise HarnessError("authorization run_id mismatch")
    for name, value in bundle["hashes"].items():
        if authorization.get(name) != value:
            raise HarnessError(f"authorization {name} mismatch")
    return authorization


def cmd_validate(args: argparse.Namespace) -> int:
    bundle = load_bundle(Path(args.manifest), for_execution=args.execution_ready)
    plan = build_plan(bundle)
    result = {
        "status": "valid",
        "harness_version": HARNESS_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "rubric_version": bundle["rubric"].get("rubric_version"),
        "execution_ready": args.execution_ready,
        "run_id": bundle["manifest"]["run_id"],
        "hashes": bundle["hashes"],
        "warnings": bundle["warnings"],
        "provenance_preflight": {
            "status": bundle["provenance_preflight"]["status"],
            "criterion_count": bundle["provenance_preflight"]["criterion_count"],
            "rubric_finding_count": len(
                bundle["provenance_preflight"]["rubric_findings"]
            ),
        },
        "question_count": plan["question_count"],
        "primary_job_count": plan["primary_job_count"],
        "jobs_per_arm": plan["jobs_per_arm"],
        "order_position_counts": plan["order_position_counts"],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    bundle = load_bundle(Path(args.manifest), for_execution=False)
    run_dir = (
        Path(args.run_dir).resolve()
        if args.run_dir
        else default_run_dir(bundle["manifest"]).resolve()
    )
    plan = write_plan(bundle, run_dir)
    print(
        json.dumps(
            {
                "status": "planned",
                "run_dir": str(run_dir),
                "plan_path": str(run_dir / "plan.json"),
                "primary_job_count": plan["primary_job_count"],
                "jobs_per_arm": plan["jobs_per_arm"],
                "execution_enabled": plan["execution_enabled"],
            },
            indent=2,
        )
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps(status_for_run(Path(args.run_dir).resolve()), indent=2))
    return 0


def cmd_derive(args: argparse.Namespace) -> int:
    bundle = load_bundle(Path(args.manifest), for_execution=False)
    run_dir = Path(args.run_dir).resolve()
    require_under(run_dir, ROOT, "run directory")
    output = derive_results(bundle, run_dir)
    print(
        json.dumps(
            {
                "status": "derived",
                "group_rows": len(output),
                "path": str(run_dir / "reports" / "derived-results.json"),
            },
            indent=2,
        )
    )
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    # This validation intentionally precedes all environment-variable reads.
    bundle = load_bundle(Path(args.manifest), for_execution=True)
    authorization = verify_authorization(
        bundle,
        Path(args.authorization).resolve(),
        args.confirm_run_id,
    )
    manifest = bundle["manifest"]
    if not os.environ.get(manifest["base_url_env"]):
        raise HarnessError(f"{manifest['base_url_env']} is not configured")
    if not os.environ.get(manifest["credential_env"]):
        raise HarnessError(f"{manifest['credential_env']} is not configured")

    run_dir = (
        Path(args.run_dir).resolve()
        if args.run_dir
        else default_run_dir(manifest).resolve()
    )
    require_under(run_dir, ROOT, "run directory")
    plan_path = run_dir / "plan.json"
    plan = load_json(plan_path) if plan_path.exists() else write_plan(bundle, run_dir)
    atomic_write_json(run_dir / "authorization.snapshot.json", authorization)
    started_wall = time.perf_counter()
    active_elapsed = 0.0
    watchdog = manifest["watchdog"]
    worker_capability = os.urandom(32).hex()

    for job in plan["jobs"]:
        record_path = run_dir / "records" / f"{job['job_id']}.json"
        if record_path.exists() and valid_completed_record(record_path, run_dir, job):
            continue
        now = time.perf_counter()
        if active_elapsed >= watchdog["active_run_timeout_seconds"]:
            raise HarnessError("active run watchdog expired")
        if now - started_wall >= watchdog["wall_run_timeout_seconds"]:
            raise HarnessError("wall run watchdog expired")

        record = execute_job(
            bundle,
            plan,
            job,
            run_dir,
            worker_capability,
        )
        atomic_write_bytes(
            run_dir / "events.jsonl",
            (
                (run_dir / "events.jsonl").read_bytes()
                if (run_dir / "events.jsonl").exists()
                else b""
            )
            + canonical_json_bytes(
                {
                    "event": "job_completed",
                    "at_utc": utc_now(),
                    "job_id": job["job_id"],
                    "http_status": record["response"]["http_status"],
                    "integrity_issues": record["integrity"]["issues"],
                }
            )
            + b"\n",
        )
        if (
            record["response"]["http_status"] == 503
            and job["rule_retrieval"]
        ):
            raise HarnessError(
                f"Rule Retrieval reported not ready for {job['job_id']}; "
                "recorded without downgrade and stopped"
            )
        if record["response"]["http_status"] != 200:
            raise HarnessError(
                f"primary call failed for {job['job_id']} with "
                f"HTTP {record['response']['http_status']}; recorded and stopped"
            )
        if (
            record["response"]["http_status"] == 200
            and (
                not record["integrity"]["contract_valid"]
                or record["integrity"]["mode_echo_valid"] is not True
                or not record["integrity"]["token_usage_valid"]
                or (
                    job["arm"]["surface"] == "decision_light"
                    and record["integrity"]["full_light_identity_valid"] is not True
                )
            )
        ):
            raise HarnessError(
                f"contract integrity failed for {job['job_id']}; recorded and stopped"
            )
        if not record["timing"]["suspension_detected"]:
            active_elapsed += record["timing"]["wall_ms"] / 1000
    derive_results(bundle, run_dir)
    print(json.dumps(status_for_run(run_dir), indent=2))
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    bundle = load_bundle(Path(args.manifest), for_execution=False)
    plan = build_plan(bundle)
    assert len(plan["jobs"]) == 360
    assert all(count == 60 for count in plan["jobs_per_arm"].values())
    assert all(
        count == 10
        for positions in plan["order_position_counts"].values()
        for count in positions.values()
    )
    assert decode_http_body(gzip.compress(b'{"ok":true}'), "gzip") == b'{"ok":true}'
    assert parse_content_length("12") == 12
    assert json_pointer({"a": {"b": 2}}, "/a/b") == 2
    assert heartbeat_gap_is_suspension(11, 10) is True
    assert heartbeat_gap_is_suspension(10, 10) is False

    idempotency_keys: set[str] = set()
    for job in plan["jobs"]:
        first = job_identity_values(job, plan["run_id"])
        second = job_identity_values(job, plan["run_id"])
        assert first == second
        if job["arm"]["persists_decision"]:
            assert first[1] is not None
            idempotency_keys.add(first[1])
        else:
            assert first[1] is None
    assert len(idempotency_keys) == 240

    arm_a_job = next(job for job in plan["jobs"] if job["arm"]["id"] == "A")
    arm_e_job = next(job for job in plan["jobs"] if job["arm"]["id"] == "E")
    arm_a_body = json.loads(
        request_body_for_job(arm_a_job, bundle["manifest"], plan["run_id"])
    )
    arm_e_body = json.loads(
        request_body_for_job(arm_e_job, bundle["manifest"], plan["run_id"])
    )
    assert arm_a_body["reasoning_effort"] == "medium"
    assert "calling_system_identity" in arm_a_body
    assert "reasoning_effort" not in arm_e_body
    assert "calling_system_identity" not in arm_e_body
    assert arm_a_body["provision_id"] is None
    assert set(arm_e_body) == {"scenario", "correlation_id", "rule_retrieval"}

    prior_base = os.environ.pop(bundle["manifest"]["base_url_env"], None)
    prior_key = os.environ.pop(bundle["manifest"]["credential_env"], None)
    try:
        try:
            load_bundle(Path(args.manifest), for_execution=True)
        except HarnessError as exc:
            message = str(exc)
            assert "execution gates remain false" in message
            assert bundle["manifest"]["base_url_env"] not in message
            assert bundle["manifest"]["credential_env"] not in message
        else:
            raise AssertionError("disabled manifest unexpectedly passed execution validation")
    finally:
        if prior_base is not None:
            os.environ[bundle["manifest"]["base_url_env"]] = prior_base
        if prior_key is not None:
            os.environ[bundle["manifest"]["credential_env"]] = prior_key

    synthetic_arm = next(arm for arm in bundle["manifest"]["arms"] if arm["id"] == "E")
    synthetic_body = {
        "schema_version": "policy_retrieval_v1",
        "retrieval": {
            "status": "narrowed",
            "retrieval_mode": "policy",
        },
        "policies": [
            {
                "policy": {
                    "provision_key": "ab87a692f3a20e95c545a0ce7718ba61"
                }
            }
        ],
        "token_usage": {
            "calls": 1,
            "calls_without_usage": 0,
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "reasoning_tokens": 1,
            "total_tokens": 12,
        },
        "latency_ms": 100,
    }
    normalized = normalize_body(synthetic_body, synthetic_arm)
    assert normalized["echoed_retrieval_mode"] == "policy"
    assert normalized["retained_policy_keys"] == [
        "ab87a692f3a20e95c545a0ce7718ba61"
    ]
    usage = extract_token_usage(synthetic_body, synthetic_arm, http_status=200)
    assert usage["total_tokens"] == 12 and usage["arithmetic_valid"] is True
    assert 503 not in set(bundle["manifest"]["watchdog"]["retryable_http_statuses"])

    test_runs_root = ROOT / "runs"
    test_runs_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=test_runs_root) as temporary:
        temporary_path = Path(temporary)
        request_path = temporary_path / "requests" / "test.body"
        wire_path = temporary_path / "responses" / "test.wire"
        decoded_path = temporary_path / "responses" / "test.decoded"
        atomic_write_bytes(request_path, b"{}")
        atomic_write_bytes(wire_path, b"{}")
        atomic_write_bytes(decoded_path, b"{}")
        job = plan["jobs"][0]
        record = {
            "schema_version": "consume-api-raw-result/1",
            "job_id": job["job_id"],
            "sequence": job["sequence"],
            "request": {
                "body_path": str(request_path.relative_to(temporary_path)),
                "body_sha256": sha256_bytes(b"{}"),
                "body_bytes": 2,
            },
            "response": {
                "wire_body_path": str(wire_path.relative_to(temporary_path)),
                "wire_body_sha256": sha256_bytes(b"{}"),
                "wire_body_bytes": 2,
                "decoded_body_path": str(decoded_path.relative_to(temporary_path)),
                "decoded_body_sha256": sha256_bytes(b"{}"),
                "decoded_body_bytes": 2,
            },
        }
        record_path = temporary_path / "records" / f"{job['job_id']}.json"
        atomic_write_json(record_path, record)
        assert valid_completed_record(record_path, temporary_path, job)
        atomic_write_bytes(decoded_path, b"corrupt")
        assert not valid_completed_record(record_path, temporary_path, job)

    with tempfile.TemporaryDirectory(dir=test_runs_root) as temporary:
        temporary_path = Path(temporary)
        capability = os.urandom(32).hex()
        timeout_spec = {
            "worker_capability_sha256": sha256_bytes(capability.encode("utf-8")),
            "offline_self_test_sleep_seconds": 2,
            "base_url_env": "OFFLINE_TEST_BASE_URL",
            "credential_env": "OFFLINE_TEST_CREDENTIAL",
            "method": "GET",
            "path": "/never-called",
            "body_path": None,
            "safe_headers": {},
            "socket_timeout_seconds": 1,
            "wire_path": str(temporary_path / "wire"),
            "decoded_path": str(temporary_path / "decoded"),
        }
        spec_path = temporary_path / "spec.json"
        result_path = temporary_path / "result.json"
        atomic_write_json(spec_path, timeout_spec)
        previous_selftest = os.environ.get("CONSUME_MATRIX_OFFLINE_SELFTEST")
        os.environ["CONSUME_MATRIX_OFFLINE_SELFTEST"] = "1"
        try:
            worker_result, monitor = run_worker_with_watchdog(
                spec_path=spec_path,
                result_path=result_path,
                hard_timeout_seconds=0.5,
                heartbeat_interval_seconds=0.05,
                suspension_gap_seconds=1,
                worker_capability=capability,
            )
        finally:
            if previous_selftest is None:
                os.environ.pop("CONSUME_MATRIX_OFFLINE_SELFTEST", None)
            else:
                os.environ["CONSUME_MATRIX_OFFLINE_SELFTEST"] = previous_selftest
        assert monitor["timed_out"] is True
        assert worker_result["error_type"] == "AttemptWatchdogTimeout"

    question = bundle["rubric"]["questions"][0]
    required_key = question["expected_evidence"]["required"][0]
    evaluation_record = {
        "repetition": 1,
        "job_id": "A__ais-annual-vacation__r1",
        "arm": {
            "id": "A",
            "surface": "decision_light",
            "retrieval_mode": "policy",
            "persists_decision": True,
        },
        "normalized": {
            "retained_policy_keys": [required_key],
            "citations": [{"provision_key": required_key}],
            "outcome": {"information": "answered", "verdict": "answered"},
            "verdict": {"status": "answered", "text": "yes"},
            "information": {"text": "policy answer"},
            "verdict_reached": True,
            "missing_information": [],
            "verification_requirements": [],
            "retrieval_status": "narrowed",
        },
        "integrity": {
            "citation_integrity_valid": True,
            "receipt_hash_valid": True,
            "hash_basis_valid": True,
            "full_light_identity_valid": True,
            "token_usage_matches_receipt": True,
            "stage_latency_matches_receipt": True,
            "non_fabrication_valid": True,
        },
    }
    evaluated = evaluate_record(
        evaluation_record,
        question,
        bundle["valid_keys"][question["project"]],
        bundle["provenance_preflight"],
    )
    assert evaluated["expected_evidence_miss"] == []
    assert not (set(evaluated["dimensions"]) & set(MEASUREMENT_DIMENSIONS))

    print(
        json.dumps(
            {
                "status": "self-test-passed",
                "harness_version": HARNESS_VERSION,
                "manifest_version": MANIFEST_VERSION,
                "rubric_version": bundle["rubric"].get("rubric_version"),
                "network_calls": 0,
                "primary_job_count": 360,
                "jobs_per_arm": plan["jobs_per_arm"],
                "order_position_balance": 10,
                "stable_idempotency_keys": len(idempotency_keys),
                "watchdog_timeout_test": "pass",
                "atomic_resume_test": "pass",
                "expected_evidence_miss_test": "pass",
                "execution_gates": bundle["manifest"]["gates"],
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resumable six-arm PolicyVerbAItim Consume API matrix runner"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    validate.add_argument("--execution-ready", action="store_true")
    validate.set_defaults(handler=cmd_validate)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    plan.add_argument("--run-dir")
    plan.set_defaults(handler=cmd_plan)

    status = subparsers.add_parser("status")
    status.add_argument("--run-dir", required=True)
    status.set_defaults(handler=cmd_status)

    derive = subparsers.add_parser("derive")
    derive.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    derive.add_argument("--run-dir", required=True)
    derive.set_defaults(handler=cmd_derive)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    execute.add_argument("--authorization", required=True)
    execute.add_argument("--confirm-run-id", required=True)
    execute.add_argument("--run-dir")
    execute.set_defaults(handler=cmd_execute)

    self_test = subparsers.add_parser("self-test")
    self_test.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    self_test.set_defaults(handler=cmd_self_test)

    worker = subparsers.add_parser("_worker")
    worker.add_argument("--spec", required=True)
    worker.add_argument("--result", required=True)
    worker.set_defaults(
        handler=lambda args: worker_request(
            Path(args.spec).resolve(),
            Path(args.result).resolve(),
        )
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
