from __future__ import annotations

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
        self.assertEqual(self.rubric["rubric_version"], "3.1.0")
        self.assertEqual(self.rubric["schema_version"], "consume-api-evaluation-rubric/3")
        self.assertEqual(manifest["manifest_version"], "2.1.0")
        self.assertEqual(manifest["schema_version"], "consume-api-matrix-manifest/2")
        self.assertEqual(manifest["harness_version"], "consume-api-provenance-harness/3.1.0")

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
            {
                "criteria_total": 128,
                "scorable": 20,
                "unscorable": 95,
                "unresolved": 13,
                "findings": 108,
            },
        )

    def test_source_classification_counts(self) -> None:
        self.assertEqual(
            self.ledger["normalized_source_classification_counts"],
            {
                "mechanically_source_supported": 5,
                "product_decision_required": 8,
                "semantic_support_pending_human_confirmation": 19,
                "structural_harness_not_product_law": 80,
                "unsupported_or_contradicted_rubric": 1,
            },
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
        self.assertEqual(sha(path), "cef48741a6e19806b6f1bade107402c43d6ed15b04ae5a8bd2a10c80a502cc15")

    def test_correction_attestation_is_not_normative_evidence(self) -> None:
        hashes = {source["sha256"] for source in self.rubric["evidence_sources"]}
        self.assertNotIn("87e18c82c7418e16e2296e4188d9045653cafed056680bc277e698997e434237", hashes)

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
