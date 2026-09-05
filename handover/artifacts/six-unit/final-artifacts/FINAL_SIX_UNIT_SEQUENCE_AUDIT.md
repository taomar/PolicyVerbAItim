# Final six-unit sequence audit

## Recommendation

**Ready for six serialized commits from exact HEAD
`c0972c8bb7ba811903e981d3806afe31cc1f514d`.**

No ownership, architecture, applicability, import, test, exclusion, secret,
content, or shared-repository mutation blocker remains.

| Ordinal | Commit | Patch |
|---|---|---|
| 00 | `feat(indexing): establish the all-published-rule corpus scope` | `00-rule-index-foundation.patch` |
| 01 | `feat(retrieval): return native rules through audited decisions` | `01-rule-retrieval.patch` |
| 01a | `perf(retrieval): compress responses and narrow search payloads` | `01a-earlier-payload-optimizations.patch` |
| 02 | `fix(decision): close evidence and settlement gaps` | `02-payload.patch` |
| 03 | `feat(consume-demo): add rule retrieval request mode` | `03-consume-request-mode-foundation.patch` |
| 04 | `feat(consume-demo): parse and render native rule envelopes` | `04-consume-native-parser-renderer.patch` |

Do not combine or reorder them.

## What changed from the blocked audit

- Ordinal 00 supplies the persisted all-published-rule corpus contract.
- Ordinal 01 is the Rule patch rebased onto that contract.
- Ordinal 01a restores two accepted earlier Payload optimizations that had been
  misclassified into Rule: HTTP gzip and Search result select-list narrowing.
- Ordinal 02 is rebased onto the real six-unit base. Sixteen targets remain
  byte-identical to the original Payload artifact. Two test paths are explicit
  ownership-safe merges:
  - prompt version pins directly from v12 to v16;
  - the measured-float guard lands on the Rule/foundation anti-corpus file
    without importing unrelated ingestion modules absent from this sequence.
- Ordinal 03 now has direct archived authorship evidence and narrow retroactive
  approval for its exact bytes.
- Ordinal 04 is unchanged.

## Validation

- Six patches applied sequentially in a fresh exact-HEAD copy.
- Every unit passed exact base hash, result hash, changed-path-set, and excluded
  file checks.
- Candidate union: 48 paths; 963 excluded HEAD files stayed unchanged.
- Boundary imports passed.
- Focused backend: 231 + 524 + 448 passed.
- Complete candidate backend: **5,192 passed, 23 skipped** across all 246 unit
  test files in nine visible shards.
- Consume: **260/260 passed** in bounded shards; TypeScript passed.
- Post-test source integrity: 1,011 files checked, zero changes.
- Candidate/current comparison: 43 exact full-file matches; five expected
  hunk-scoped mixed paths; zero unexpected mismatches.
- Azure overlap: only `src/policy_platform/api/app.py` is in the candidate.
  Its three gzip hunks contain no Azure local-auth or Integration content.
- Secret/content scan: zero high-confidence secrets, zero live endpoints, zero
  raw source-policy/live-corpus text.
- Shared repository terminal gate: HEAD, branch, tree, logical index,
  porcelain, tracked patch, cached diff, refs, stash, all 121 dirty-file hashes,
  and the 37,199-file content tree all unchanged.

The 23 backend skips are expected in this no-live-call audit: optional
graph/docling dependencies, local-only documentation/accounts, and local
Postgres fixtures that were intentionally not contacted.

## Disclosed warning

The exact ordinal-01 source artifact adds one blank line at EOF in
`test_policy_case_project.py`; `git apply --whitespace=error-all` reports that
single line. The Rule reconstruction already disclosed it. Normal apply, exact
hashes, imports, focused tests, and the complete backend suite pass. If the
future committer enforces a zero-whitespace-warning policy, clean and rebase
ordinals 01 and 02 together, then rerun every gate; otherwise use the exact
artifacts here.

Ordinal 00 preserves the existing binary-classified CRLF form of
`test_the_corpus_is_indexed_in_one_language.py`; its patch itself passes strict
`git apply --check --whitespace=error-all`.

## Safety boundary

No shared repository file, index, ref, stash, config, hook, ignored file,
database, Search index, API, model, Azure resource, deployment, or migration was
mutated. All Git commits and staging used during validation existed only in
private audit copies.
