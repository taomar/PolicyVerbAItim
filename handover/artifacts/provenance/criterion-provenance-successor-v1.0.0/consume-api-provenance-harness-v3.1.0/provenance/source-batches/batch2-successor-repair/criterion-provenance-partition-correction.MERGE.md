# Provenance Partition Correction Merge Instructions

## Scope

This correction replaces the original Batch2 ownership artifacts. It does not alter
the canonical bundle, Batch1, Batch3, source evidence, repository, or live resources.
It does not create the final successor bundle.

## Integrity

- Canonical payload SHA-256: `fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`
- Canonical 113-ID SHA-256: `4a752fd8e13b1fb1d1c37bf110e4b1334ca3bbae1beaab5d630e8d3b1719acb3`
- Corrected Batch2 ID SHA-256: `251c3289af2ae64a3312e9242129ffef08f87614766338d2df9a684dfc14b6ed`
- Corrected overlay: `5d0d9bbb374bd7ec3c3f7e5617494da3e2dd62dcd1809889d99a52aa5de9167a` (37276 bytes)
- Corrected ledger: `ae7e00d8ecf9f3916f4ff2c0424eee9392baf00aa925fafcf113838b96ac0887` (58095 bytes)
- Correction attestation: `87e18c82c7418e16e2296e4188d9045653cafed056680bc277e698997e434237` (13565 bytes)

## Exact merge semantics

1. Recompute the canonical provenance preflight and require exactly 113 sorted
   findings with the canonical ID hash above.
2. Keep Batch1 as canonical positions 1-38 and Batch3 as positions 77-113.
3. Replace, rather than combine with, the original Batch2 overlay and ledger using
   `criterion-provenance-batch2-successor.overlay.json` and `criterion-provenance-batch2-successor.ledger.json`. The successor owns positions 39-76.
4. Keep the original `normative-provenance-batch2.source-attestations.json`
   byte-identical at SHA-256
   `cef48741a6e19806b6f1bade107402c43d6ed15b04ae5a8bd2a10c80a502cc15`.
   The corrected overlay intentionally preserves its existing evidence-source binding.
5. Match every merge operation by exact criterion ID, never by position alone.
6. Keep `AIS-08:R5` fail-closed as
   `structural_harness_not_product_law`; it does not become scorable.
7. Keep `HW-05:R4` solely in Batch3. Both predecessor records were materially
   consistent; no evidence or replacement is discarded.
8. Reject any omitted owner, duplicate owner, changed preserved record, hash
   mismatch, unsupported scoring upgrade, or AI-as-human confirmation claim.
9. Run the provenance guard on a private copy. The validated combined result is
   20 scorable,
   95 unscorable, and
   13 unresolved criteria.

## Boundaries

The correction attestation is audit metadata, not normative evidence. Do not
register it as a rubric evidence source. Preserve execution-disabled gates and
perform final successor-bundle assembly only in the existing merge session.
