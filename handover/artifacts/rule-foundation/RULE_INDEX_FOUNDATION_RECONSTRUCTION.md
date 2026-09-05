# Rule Index Foundation Reconstruction

## Verdict

**Ordinal 0 is safe and ready as an artifact.** The seven-path patch applies
cleanly to exact `HEAD c0972c8bb7ba811903e981d3806afe31cc1f514d`, imports coherently, and passes 204 focused
index/projection/anti-corpus/reachability tests.

**Native Rule Retrieval is separately ready as a rebased artifact.** The
previous 18-path patch cannot follow ordinal 0 because both edit the same
`ai_case_project` import/filter context. The rebased 17-path patch applies after
ordinal 0 and passes 511 focused foundation-plus-Rule tests.

**A broader sequence gap remains outside both units.** Two measured earlier
Payload optimizations were misclassified into the frozen Rule subset:

- HTTP gzip coverage without its `api/app.py` implementation
- Azure AI Search `select` narrowing and its focused test

Neither pair is present in ordinal-02 Payload. They are excluded rather than
silently absorbed. This does not block ordinal 0 or Native Rule Retrieval, but a
writer preserving every accepted dirty-tree optimization needs a separate
earlier-Payload optimization commit.

## Exact artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `C:\Users\taomar\.copilot\session-state\c17eaeeb-2be8-496d-b206-d2457f7b30f8\files\00-rule-index-foundation.patch` | 51705 | `c3b2e80468878cbf1b0940e33a2c08950ac96980549a897ea8e37fd3a930c218` |
| `C:\Users\taomar\.copilot\session-state\c17eaeeb-2be8-496d-b206-d2457f7b30f8\files\01-rule-retrieval.rebased-on-foundation.patch` | 316091 | `c75e0bb4d990f418f9f434bc832602e01d08c3d91cbfd3e94be3aa932903e4a1` |
| `PATH_HUNK_MANIFEST.json` | generated | see `INPUT_OUTPUT_HASHES.json` |
| `RULE_REBASE_DELTA_MANIFEST.json` | generated | see `INPUT_OUTPUT_HASHES.json` |
| `SEQUENCE_VALIDATION.json` | generated | see `INPUT_OUTPUT_HASHES.json` |
| `EXCLUSIONS.json` | generated | see `INPUT_OUTPUT_HASHES.json` |

## Architecture and ownership

The correction belongs at the persisted corpus contract, not at Rule's import
site:

1. `policy_rule_slice` owns the shared scope vocabulary and
   `rule_documents_expected`.
2. `policy_index` uses it to select documents, declare the schema, stamp the
   manifest, read the scope, and pass exact expected counts to validation.
3. `projection_faithfulness` judges the corpus under that recorded scope and
   refuses an unknown one.
4. the existing policy-mode reader uses `policy_rule_content_filter(...,
   large_policies_only=True)` so widening the stored corpus does not widen the
   default query.

This preserves two invariants: every published rule is individually retrievable
under `all_published_rules_v1`, and callers that did not request native Rule
Retrieval continue to query exactly the legacy large-provision rule subset.

No Rule-only `policy_index.py` hunk remains after this boundary is assigned
correctly. Rule consumes the complete ordinal-00 contract. Rule still owns its
`context_rule_ids` alias and the Rule-only anti-corpus module registrations.

## Mixed-file decomposition

- `policy_rule_slice.py`: scope helper in ordinal 0; literal/prose rendering
  provenance excluded; `context_rule_ids` deferred to Rule.
- `policy_index.py`: only scope/filter/schema/manifest/build eligibility/exact
  expected-count/readiness-validation hunks included. Rendering spans, error
  description, interleaving, and PolicyIndexBuild progress/history are excluded.
- `projection_faithfulness.py`: complete scope-aware validation diff included.
- `test_no_m2_code_is_shaped_around_a_corpus.py`: foundation helper guard in
  ordinal 0; Rule module registrations in Rule; later Payload float controls
  excluded.
- `test_the_corpus_is_indexed_in_one_language.py`: scope/build/manifest/shrink
  hunks included; unrelated rendering-preservation hunk excluded.
- `ai_case_project.py`: ordinal 0 adapts the existing reader only; Rule adds the
  native mode. Payload select-list narrowing is excluded.

Every included hunk has exact base/result SHA-256 and exact hunk SHA-256 in
`PATH_HUNK_MANIFEST.json`.

## Validation

- ordinal 0 strict apply check: passed
- ordinal 0 exact target comparison: 7/7 paths
- ordinal 0 import check: passed
- ordinal 0 focused suite: **204 passed**
- old Rule-after-foundation apply check: failed at the expected overlapping
  `ai_case_project` context
- rebased Rule apply check: passed
- final exact target comparison: 1,002 files checked
- foundation-to-Rule import check: passed
- final focused suite: **511 passed**
- excluded existing HEAD paths unchanged: **981**
- Azure-overlap paths: all remain at HEAD
- withdrawn reasoning-view work: absent or at HEAD
- dependencies installed: none
- live API/model/DB/Search/Azure/deployment/migration calls: none

The full backend suite was not run. The future writer command is:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit -v --durations=25
```

## Leakage and anti-corpus review

Candidate additions contain no AIS/HW identifier, source filename, source
document text, observed rank/score literal, secret, or corpus-tuned executable
branch. The number `36` appears only in explanatory comments/docstrings about
the prior builder/validator drift. It is not executable, a threshold, a rank, a
score, or a corpus selector. The anti-corpus guard passes in both validation
runs.

## Sequence gap

Ordinal-02 Payload contains neither `src/policy_platform/api/app.py` nor
`tests/unit/test_large_responses_are_compressed.py`; it therefore does not carry
the gzip implementation/test pair. It also omits the Search select-narrowing
test. Exact evidence and hunk hashes are in
`RULE_REBASE_DELTA_MANIFEST.json`.

The smallest safe unblock is a separate earlier-Payload optimization commit:

1. app gzip hunks 1, 3, and 4 plus the gzip test, after hunk-reviewing the mixed
   app path against Azure commit `3815866`
2. the four `ai_case_project` select-list narrowing hunks plus their focused test

Neither belongs in ordinal 0 or Native Rule Retrieval.

## Shared repository non-mutation

End-state gates match the frozen start: HEAD, branch, HEAD tree, logical
`ls-files --stage`, exhaustive porcelain-v2, tracked patch, empty cached diff,
refs, empty stash, 120/121 status counts, all 121 dirty-file hashes, and the
37,199-file repository content tree. The exact PowerShell start fingerprint also
matches at end. See `END_SHARED_REPOSITORY_STATE.json` and
`END_POWERSHELL_TREE.json`.
