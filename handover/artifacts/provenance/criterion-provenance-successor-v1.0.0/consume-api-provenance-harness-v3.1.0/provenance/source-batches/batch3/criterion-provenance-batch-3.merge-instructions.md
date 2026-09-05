# Criterion provenance batch 3 merge instructions

Base the merge on canonical payload SHA-256 `fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`. Recompute the deterministic unscorable list, assert 113 entries, sort by `criterion_id`, and assert that one-based indices 77-113 exactly match the overlay before applying anything.

1. Copy `hardware-policy-v3.3-import.json` byte-identically to a new successor bundle as `evidence\normative\hardware-policy-v3.3.rules.json`; require SHA-256 `0fb6a1298d13f4d3b82da8c3571e189076bd56fec943be0e871036d0875ecfbf`.
2. Add the overlay's `hw_rules_v3_3` evidence-source record to the successor rubric.
3. Replace only `HW-08:manual-1`, guarded by canonical pointer `/questions/17/criteria/5` and pointer SHA-256 `a61cef01f18ef7ff9dbba6ff215ca4c11a0dbbc5555dd3d001bc072fbe49122a`.
4. Keep the three semantic-pending criteria unscorable until a human confirmation record is attached to hash-verified body evidence. This AI review is not confirmation.
5. Keep the 33 structural/harness criteria outside product-law failure attribution. If they remain executable checks, route them through a separate integrity or response-contract result channel rather than `product_fail`.
6. Do not alter criteria outside this slice. Do not add benchmark-specific IDs, question IDs, provision IDs, or rule IDs to production guard logic.
7. Recompute all full-file, JSON-pointer, semantic manifest, inventory, and canonical payload hashes in the successor bundle. Run provenance preflight, native validation, self-test, copied tests, and leakage checks offline.

Expected batch counts: 37 total; 1 mechanically source-supported; 3 semantic support pending human confirmation; 33 structural/harness; 0 unsupported or contradicted; 0 unavailable evidence; 0 product decisions required. The merge should make exactly one criterion newly scorable for product-law attribution.
