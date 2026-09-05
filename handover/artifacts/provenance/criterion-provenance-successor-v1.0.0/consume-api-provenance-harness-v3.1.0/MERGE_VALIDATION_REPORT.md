# Criterion Provenance Merge and Validation Report

## Outcome

The repaired exact-ID partition was applied to a fresh canonical v3.0.0 copy.
The successor is `consume-api-provenance-harness/3.1.0` with rubric `3.1.0` and
manifest `2.1.0`. Execution remains disabled.

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
- Changed criteria: 18
- Newly scorable: 5

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

- Native validate: passed
- Network-disabled self-test: passed
- Unit tests: 31 passed
- Mutation/negative controls: 8 passed
- Quote/literal leakage hits: 0
- Two-pass deterministic build: byte-identical

## Non-mutation boundary

- Pinned provenance/source/base/batch/repair inputs: 79 unchanged files
- Repository content tree, excluding `.git/**`: 37199
  files, 553349103 bytes, SHA-256
  `a702437f485cdf04aca82c37122621cfa6e61b2f021ac1c7bf7b118684099a28` before and after
- Logical Git index, porcelain-v2 status, refs, stash, HEAD, branch, and cached
  diff: hash-identical before and after under `GIT_OPTIONAL_LOCKS=0`
- Historical repair full-tree snapshot
  `75469f06f199ecf5da63cdb3448d329d8033606e2f7f3c4028de486eabc84c19` is explicitly superseded by
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
