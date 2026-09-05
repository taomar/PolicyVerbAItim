from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import consume_matrix_runner as runner  # noqa: E402
from rubric_provenance import (  # noqa: E402
    ProvenanceError,
    classify_manual_decisions,
    gate_evaluation,
    sha256_file,
    validate_rubric_provenance,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CopiedHarnessIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rubric_path = ROOT / "evaluation-rubric.json"
        cls.rubric = load_json(cls.rubric_path)
        cls.preflight = validate_rubric_provenance(
            cls.rubric,
            cls.rubric_path,
        )
        cls.questions = {
            question["rubric_id"]: question
            for question in cls.rubric["questions"]
        }

    def dimensions(self, failed: set[str] | None = None) -> dict[str, dict[str, str]]:
        failed = failed or set()
        return {
            name: runner.dimension(
                "fail" if name in failed else "pass",
                "synthetic integration observation",
            )
            for name in runner.SCORED_DIMENSIONS
        }

    def generic_preflight(self, question_id: str) -> dict:
        criterion = {
            "active": True,
            "description": "generic source-provenanced expectation",
            "criterion_provenance": "rule_body",
            "provenance_kind": "normative_source_body",
            "source_provision_ids": ["fixture-provision"],
            "source_rule_ids": ["fixture-rule"],
            "validation_state": "validated_supported",
            "corpus_support": {
                "checked": True,
                "supporting_rule_count": 1,
                "supporting_provision_count": 1,
                "method": "synthetic_explicit_source_relation",
                "semantic_support": "mechanically_proven",
            },
            "evidence_refs": [],
            "disposition": "scorable",
            "reason": None,
            "known_limitation": None,
        }
        return {
            "questions": {
                question_id: {
                    "dimensions": {
                        name: {
                            **criterion,
                            "criterion_id": f"generic:{name}",
                        }
                        for name in ("R1", "R3", "R4", "R5", "R9")
                    },
                    "manual": [],
                }
            }
        }

    def generic_record(
        self,
        verdict_status: str,
        *,
        missing_information: list[str] | None = None,
    ) -> dict:
        missing_information = missing_information or []
        return {
            "repetition": 1,
            "job_id": "A__generic-entitlement__r1",
            "arm": {
                "id": "A",
                "surface": "decision_light",
                "retrieval_mode": "policy",
                "persists_decision": True,
            },
            "normalized": {
                "retained_policy_keys": [],
                "citations": [],
                "outcome": {
                    "information": "answered",
                    "verdict": verdict_status,
                },
                "verdict": {
                    "status": verdict_status,
                    "text": "generic decision",
                },
                "information": {"text": "generic entitlement"},
                "verdict_reached": verdict_status == "answered",
                "missing_information": missing_information,
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

    def test_generic_entitlement_execution_controls(self) -> None:
        question_id = "generic-entitlement"
        preflight = self.generic_preflight(question_id)
        base_question = {
            "id": question_id,
            "expected_evidence": {"required": []},
            "irrelevant": False,
            "manual_criteria": [],
        }
        cases = (
            (
                "silent present authorization cannot be answered",
                {"information": ["answered"], "verdict": ["not_settled_by_rules"]},
                self.generic_record("answered"),
                "fail",
            ),
            (
                "explicit self-executing authorization may be answered",
                {"information": ["answered"], "verdict": ["answered"]},
                self.generic_record("answered"),
                "pass",
            ),
            (
                "explicit prior approval with omitted status is missing a fact",
                {"information": ["answered"], "verdict": ["missing_required_facts"]},
                self.generic_record(
                    "missing_required_facts",
                    missing_information=["approval status"],
                ),
                "pass",
            ),
        )
        for label, tracks, record, expected in cases:
            with self.subTest(label=label):
                question = {**base_question, "expected_tracks": tracks}
                evaluated = runner.evaluate_record(
                    record,
                    question,
                    set(),
                    preflight,
                )
                self.assertEqual(evaluated["scored_result"], expected)

    def test_native_bundle_validation_runs_provenance_preflight(self) -> None:
        bundle = runner.load_bundle(ROOT / "manifest.pending.json")
        self.assertEqual(
            bundle["provenance_preflight"]["status"],
            "ready_with_rubric_findings",
        )
        self.assertEqual(
            bundle["hashes"]["rubric_sha256"],
            sha256_file(self.rubric_path),
        )

    def test_source_lock_accepts_only_the_exact_base_copy(self) -> None:
        command = [
            sys.executable,
            str(ROOT / "verify_source_lock.py"),
            "--lock",
            str(ROOT / "SOURCE_LOCK.json"),
            "--root",
            str(ROOT),
            "--section",
            "migration_evidence",
        ]
        accepted = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "harness"
            locked = load_json(ROOT / "SOURCE_LOCK.json")["migration_evidence"]
            for relative in locked:
                destination = mutated / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            with (mutated / "evidence" / "rubric-v1.snapshot.json").open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write("\n")
            rejected = subprocess.run(
                [*command[:5], str(mutated), *command[6:]],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("failed", rejected.stdout)

    def test_missing_provenance_fails_closed_before_planning(self) -> None:
        mutated = copy.deepcopy(self.rubric)
        del mutated["questions"][0]["criteria"][0]["criterion_provenance"]
        with self.assertRaisesRegex(ProvenanceError, "missing required"):
            validate_rubric_provenance(mutated, self.rubric_path)

    def test_unknown_provenance_fails_closed_before_planning(self) -> None:
        mutated = copy.deepcopy(self.rubric)
        mutated["questions"][0]["criteria"][0][
            "criterion_provenance"
        ] = "body_maybe"
        with self.assertRaisesRegex(ProvenanceError, "unknown"):
            validate_rubric_provenance(mutated, self.rubric_path)

    def test_bad_pointer_hash_fails_closed_before_planning(self) -> None:
        mutated = copy.deepcopy(self.rubric)
        mutated["questions"][0]["criteria"][0]["evidence_refs"][0][
            "pointer_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ProvenanceError, "pointer hash mismatch"):
            validate_rubric_provenance(mutated, self.rubric_path)

    def test_unsupported_ais06_manual_failures_are_rubric_errors(self) -> None:
        question = self.questions["AIS-06"]
        decisions = [
            {"decision": "fail", "evidence": f"preserved observation {index}"}
            for index in range(len(question["manual_criteria"]))
        ]
        result = classify_manual_decisions(
            question,
            decisions,
            self.preflight,
            "A",
        )
        self.assertEqual(result["classification"], "rubric_error")
        self.assertEqual(result["product_failure_criteria"], [])
        self.assertEqual(len(result["unsupported_observations_preserved"]), 2)
        self.assertTrue(
            all(
                not item["charged_to_product"]
                for item in result["criterion_results"]
            )
        )

    def test_five_ais02_certificate_failures_cannot_be_product_failures(self) -> None:
        question = self.questions["AIS-02"]
        decisions = [
            {"decision": "fail", "evidence": f"preserved observation {index}"}
            for index in range(len(question["manual_criteria"]))
        ]
        for arm in ("A", "C", "A", "C", "A"):
            result = classify_manual_decisions(
                question,
                decisions,
                self.preflight,
                arm,
            )
            self.assertEqual(result["classification"], "rubric_error")
            self.assertFalse(result["product_failure_criteria"])

    def test_ais02_answered_outlier_is_a_source_provenanced_failure(self) -> None:
        result = gate_evaluation(
            self.questions["AIS-02"],
            self.dimensions({"R3"}),
            self.preflight,
            "C",
        )
        self.assertEqual(result["scored_result"], "fail")
        self.assertEqual(result["product_failures"], ["R3"])
        self.assertEqual(result["unresolved_criteria"], [])

    def test_valid_ais_criteria_still_produce_product_failures(self) -> None:
        cases = (
            ("AIS-03", "R3"),
            ("AIS-04", "R1"),
            ("AIS-08", "R9"),
            ("AIS-09", "R1"),
        )
        for rubric_id, dimension in cases:
            with self.subTest(rubric_id=rubric_id, dimension=dimension):
                result = gate_evaluation(
                    self.questions[rubric_id],
                    self.dimensions({dimension}),
                    self.preflight,
                    "A",
                )
                self.assertEqual(result["scored_result"], "fail")
                self.assertEqual(result["product_failures"], [dimension])

    def test_corrected_failure_population_is_27_11_0(self) -> None:
        classifications: list[str] = []
        unsupported_groups = (("AIS-02", 5), ("AIS-06", 6))
        for rubric_id, repetitions in unsupported_groups:
            question = self.questions[rubric_id]
            decisions = [
                {
                    "decision": "fail",
                    "evidence": f"preserved unsupported observation {index}",
                }
                for index in range(len(question["manual_criteria"]))
            ]
            for _ in range(repetitions):
                classifications.append(
                    classify_manual_decisions(
                        question,
                        decisions,
                        self.preflight,
                        "A",
                    )["classification"]
                )

        classifications.append(
            gate_evaluation(
                self.questions["AIS-02"],
                self.dimensions({"R3"}),
                self.preflight,
                "C",
            )["scored_result"]
        )
        product_groups = (
            ("AIS-03", "R3", 2),
            ("AIS-04", "R1", 9),
            ("AIS-08", "R9", 9),
            ("AIS-09", "R1", 6),
        )
        for rubric_id, dimension, repetitions in product_groups:
            for _ in range(repetitions):
                classifications.append(
                    gate_evaluation(
                        self.questions[rubric_id],
                        self.dimensions({dimension}),
                        self.preflight,
                        "A",
                    )["scored_result"]
                )

        self.assertEqual(
            {
                "product_fail": classifications.count("fail"),
                "rubric_error": classifications.count("rubric_error"),
                "unresolved": classifications.count("unresolved"),
                "total": len(classifications),
            },
            {
                "product_fail": 27,
                "rubric_error": 11,
                "unresolved": 0,
                "total": 38,
            },
        )

    def test_b_d_f_never_enter_actionable_conclusions(self) -> None:
        question = self.questions["AIS-04"]
        for arm in ("B", "D", "F"):
            with self.subTest(arm=arm):
                result = gate_evaluation(
                    question,
                    self.dimensions({"R1"}),
                    self.preflight,
                    arm,
                )
                self.assertEqual(
                    result["scored_result"],
                    "excluded_non_actionable",
                )
                self.assertFalse(result["actionable_target_rule_conclusion"])

    def test_historical_replay_is_non_equivalent(self) -> None:
        replay = self.rubric["historical_replay"]
        self.assertEqual(replay["label"], "old_rubric_replay_non_equivalent")
        self.assertFalse(replay["comparison_valid"])
        self.assertFalse(replay["causal_regression_claim_allowed"])
        self.assertEqual(
            replay["corrected_failure_population"],
            {"product_fail": 27, "rubric_error": 11, "unresolved": 0},
        )

    def test_zero_support_mutation_neuters_only_the_mutated_criterion(self) -> None:
        mutated = copy.deepcopy(self.rubric)
        criterion = next(
            item
            for item in self.questions["AIS-04"]["criteria"]
            if item["applies_to"] == {"kind": "dimension", "dimension": "R1"}
        )
        mutated_criterion = next(
            item
            for question in mutated["questions"]
            if question["rubric_id"] == "AIS-04"
            for item in question["criteria"]
            if item["criterion_id"] == criterion["criterion_id"]
        )
        mutated_criterion["corpus_support"]["supporting_provision_count"] = 0
        mutated_preflight = validate_rubric_provenance(
            mutated,
            self.rubric_path,
        )
        result = gate_evaluation(
            next(
                question
                for question in mutated["questions"]
                if question["rubric_id"] == "AIS-04"
            ),
            self.dimensions({"R1"}),
            mutated_preflight,
            "A",
        )
        self.assertEqual(result["scored_result"], "rubric_error")
        self.assertEqual(result["product_failures"], [])

    def test_migration_is_deterministic_and_hash_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copy2(
                ROOT / "RUBRIC_MIGRATION_V3.md",
                target / "RUBRIC_MIGRATION_V3.md",
            )
            evidence = target / "evidence"
            evidence.mkdir()
            for name in (
                "rubric-v1.snapshot.json",
                "manifest-v1.snapshot.json",
                "source.snapshot.json",
                "ACTIONABLE_POLICY_FAILURE_AUDIT.md",
                "AIS02_SEMANTIC_DECISION.json",
            ):
                shutil.copy2(ROOT / "evidence" / name, evidence / name)

            command = [
                sys.executable,
                str(ROOT / "migrate_rubric_provenance.py"),
                "--rubric-in",
                str(evidence / "rubric-v1.snapshot.json"),
                "--manifest-in",
                str(evidence / "manifest-v1.snapshot.json"),
                "--source",
                str(evidence / "source.snapshot.json"),
                "--audit",
                str(evidence / "ACTIONABLE_POLICY_FAILURE_AUDIT.md"),
                "--ais02-decision",
                str(evidence / "AIS02_SEMANTIC_DECISION.json"),
                "--migration-doc",
                str(target / "RUBRIC_MIGRATION_V3.md"),
                "--rubric-out",
                str(target / "evaluation-rubric.json"),
                "--manifest-out",
                str(target / "manifest.pending.json"),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            first = (
                sha256_file(target / "evaluation-rubric.json"),
                sha256_file(target / "manifest.pending.json"),
            )
            subprocess.run(command, check=True, capture_output=True, text=True)
            second = (
                sha256_file(target / "evaluation-rubric.json"),
                sha256_file(target / "manifest.pending.json"),
            )
            self.assertEqual(first, second)

            with (evidence / "rubric-v1.snapshot.json").open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(" ")
            rejected = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("hash mismatch", rejected.stderr)

    def test_production_guard_has_no_benchmark_leakage(self) -> None:
        production_guard = (ROOT / "rubric_provenance.py").read_text(
            encoding="utf-8"
        )
        forbidden_patterns = {
            "rubric IDs": r"\b(?:AIS|HW)-\d{2}\b",
            "question IDs": r"\b(?:ais|hw)-[a-z0-9-]+\b",
            "provision fixtures": r"\b[0-9a-f]{32}\b",
            "benchmark artifact names": (
                r"ACTIONABLE_POLICY_FAILURE_AUDIT|"
                r"CONSUME_API_EVALUATION_RUBRIC|corpus_topic_map|"
                r"source\.snapshot|rubric-v1|manifest-v1"
            ),
            "benchmark headings": (
                r"SICK LEAVE|OVERTIME|CONFLICT OF INTEREST|"
                r"PROBATION PERIOD|ANNUAL VACATION"
            ),
        }
        for label, pattern in forbidden_patterns.items():
            with self.subTest(label=label):
                self.assertIsNone(
                    re.search(pattern, production_guard, flags=re.IGNORECASE)
                )

    def test_successor_versions_and_complete_hashes(self) -> None:
        manifest = load_json(ROOT / "manifest.pending.json")
        bundle = runner.load_bundle(ROOT / "manifest.pending.json")
        self.assertEqual(runner.HARNESS_VERSION, "consume-api-provenance-harness/3.1.0")
        self.assertEqual(manifest["schema_version"], "consume-api-matrix-manifest/2")
        self.assertEqual(manifest["manifest_version"], "2.1.0")
        self.assertEqual(manifest["harness_version"], runner.HARNESS_VERSION)
        self.assertEqual(self.rubric["schema_version"], "consume-api-evaluation-rubric/3")
        self.assertEqual(self.rubric["rubric_version"], "3.1.0")
        self.assertEqual(bundle["warnings"], [])
        self.assertTrue(all(bundle["hashes"].values()))

    def test_supported_heading_upgrade_and_inferred_fail_closed_behavior(self) -> None:
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

    def test_derived_schema_accepts_new_result_categories(self) -> None:
        schema = load_json(ROOT / "schemas" / "derived-result.schema.json")
        Draft202012Validator.check_schema(schema)
        scored_values = set(schema["$defs"]["scoredResult"]["enum"])
        self.assertTrue(
            {
                "rubric_error",
                "unresolved",
                "harness_error",
                "excluded_non_actionable",
            }
            <= scored_values
        )


if __name__ == "__main__":
    unittest.main()
