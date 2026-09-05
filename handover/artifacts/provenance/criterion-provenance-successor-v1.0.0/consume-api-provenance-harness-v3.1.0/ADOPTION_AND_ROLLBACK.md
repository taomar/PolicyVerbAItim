# Adoption and Rollback

## Adopt

The `consume-api-provenance-harness/3.1.0` bundle is ready for immediate offline adoption with
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
`fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`. No migration reversal, live execution, data repair, or
source change is required because this successor is a separate local bundle.
