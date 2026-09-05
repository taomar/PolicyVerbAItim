# Batch 1 provenance merge instructions

This overlay owns only sorted unscorable criterion indices **1-38** from the
canonical 113-item preflight set. Apply it only to a secured local copy of the
v3.0.0 harness; do not edit the authoritative bundle.

1. Verify the canonical bundle payload hash is `fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c` and
   the rubric hash is `6bd271a45d466ed048427a32ea2c7143bc23b3376e9ea06627f7239c481d7c58`.
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
