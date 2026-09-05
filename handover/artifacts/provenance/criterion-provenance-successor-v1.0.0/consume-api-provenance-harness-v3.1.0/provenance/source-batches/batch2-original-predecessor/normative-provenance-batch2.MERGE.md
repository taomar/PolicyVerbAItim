# Normative Provenance Batch 2 Merge Instructions

## Scope

- Authoritative bundle payload SHA-256: `fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`
- Deterministic finding population: `113`
- Owned zero-based slice: `39..76` inclusive
- Owned criteria: `38`
- First/last IDs: `AIS-08:manual-2` / `HW-05:R4`
- Selected-ID-list SHA-256: `0af8f69bf306e0c0fbc046fa875b549dd6a7a4ee1f7725711cfd21e0162c7f61`

Do not apply this overlay to any criterion outside the owned ID list. The canonical
bundle, frozen source snapshot, local source document, frozen rule receipt, repository,
live services, and production guard were not modified.

## Merge

1. Verify the hashes in `normative-provenance-batch2.source-attestations.json` against the read-only local artifacts.
2. Copy `normative-provenance-batch2.source-attestations.json` into the successor rubric evidence directory and register
   it as JSON evidence source `normative_batch2_source_attestations` using SHA-256
   `cef48741a6e19806b6f1bade107402c43d6ed15b04ae5a8bd2a10c80a502cc15`.
3. Read `normative-provenance-batch2.overlay.json` and match updates by exact `criterion_id`; never merge by
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
