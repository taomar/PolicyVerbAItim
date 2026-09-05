# PolicyVerbAItim Consume API Matrix Inventory

Prepared: 2026-09-04

## Scope and Safety

Inventory was read-only across:

- `C:\Users\taomar\.copilot\session-state\8437f3da-491a-4139-b979-8b00996c8953\files\runs`
- `C:\Users\taomar\.copilot\session-state\58f19b59-6aa9-4d38-8782-46cbdc7640c5\files\runs`
- adjacent JSON artifacts in those retiring/predecessor session folders
- two repository-local `.artifacts` JSON files reached through the read-only
  junction

No API call, database/Search operation, migration, repository edit, or source
control operation was performed.

## Direct Inventory Totals

- Named run directories: 22 files, comprising 19 JSON files and 3 logs.
- Normalized matrix rows: 440 recorded call rows.
- Additional full-receipt fixtures: 4.
- The 440 rows are not claimed to be 440 unique decisions because older
  normalized files omit decision IDs needed for exact deduplication.
- Retiring oversight lifecycle JSON outside `runs`: 24 files, 133,287 bytes
  (13 AIS files and 11 HW files). These establish corpus lifecycle provenance
  but are not Consume matrix calls.

## Retiring Oversight Run Artifacts

Root:
`C:\Users\taomar\.copilot\session-state\8437f3da-491a-4139-b979-8b00996c8953\files\runs`

| Artifact | Bytes | Recorded coverage | Classification |
| --- | ---: | --- | --- |
| `fresh-20x2-default-results.json` | 131,135 | 20 questions x 2 = 40 | Decision Light, policy retrieval, pre-paired baseline |
| `fresh-20x2-default-summary.json` | 26,927 | 40/40 HTTP success; 17/20 scenario pass; p50 17,234 ms; p50 10,964 tokens | Derived legacy summary |
| `fresh-20x2-default.log` | 38,948 | 40 completion events plus report output | Diagnostic duplicate of legacy run |
| `fresh-20x2-rule-results.json` | 157,657 | 20 x 2 = 40 | Decision Light, rule retrieval before cardinality fix; do not mix with post-fix |
| `fresh-20x2-rule-summary.json` | 27,898 | 40/40 success; 16/20 pass; p50 28,229 ms; p50 29,741 tokens | Derived pre-fix summary |
| `fresh-20x2-rule.log` | 40,461 | 40 completion events plus report output | Diagnostic duplicate of pre-fix run |
| `postfix-paired-20x2-results.json` | 280,755 | 40 policy + 40 rule, interleaved | Best A/B pilot baseline |
| `postfix-paired-20x2-summary.json` | 1,298 | Policy p50 21,829 ms / 11,552 tokens; rule p50 26,082 ms / 15,303 tokens | Best paired legacy summary |
| `postfix-paired-20x2.log` | 11,489 | Paired completion events | Diagnostic duplicate of paired run |
| `case-ais-e2e-default.json` | 35,618 | one full policy-mode receipt | Offline C adapter/integrity fixture |
| `case-ais-e2e-rule.json` | 35,194 | one full rule-mode receipt | Offline D adapter/integrity fixture |
| `case-hw-policy-default.json` | 47,318 | one full policy-mode receipt | Offline C adapter/integrity fixture |
| `case-hw-policy-rule.json` | 63,966 | one full rule-mode receipt | Offline D adapter/integrity fixture |

The paired file includes one invalid latency observation of 20,577,488 ms caused
by Windows Modern Standby. The record should remain in raw evidence but must be
flagged and excluded from causal latency statistics. This directly motivates
the suspension watchdog in the new design.

## Predecessor Run Artifacts

Root:
`C:\Users\taomar\.copilot\session-state\58f19b59-6aa9-4d38-8782-46cbdc7640c5\files\runs`

| Artifact | Bytes | Recorded coverage | Classification |
| --- | ---: | --- | --- |
| `decision-light-20x2-results.json` | 139,648 | 20 x 2 = 40 | Decision Light policy retrieval; model provenance absent from rows |
| `decision-light-20x2-summary.json` | 26,906 | 40/40 success; 17/20 pass; p50 19,319 ms; p50 14,354 tokens | Derived legacy summary |
| `decision-light-20x2-low-results.json` | 136,920 | 20 x 2 = 40 | policy retrieval, low-effort/model experiment |
| `decision-light-20x2-low-summary.json` | 27,437 | 40/40 success; 17/20 pass; p50 19,332 ms | Derived model experiment |
| `decision-light-20x2-terra-results.json` | 136,213 | 20 x 2 = 40 | policy retrieval, Terra baseline |
| `decision-light-20x2-terra-summary.json` | 26,786 | 40/40 success; 17/20 pass; p50 25,721 ms | Derived Terra baseline |
| `decision-light-20x2-dualsol-results.json` | 115,192 | 17 scenarios, 33 calls | incomplete policy retrieval experiment |
| `decision-light-20x2-luna-results.json` | 26,641 | 4 scenarios, 7 calls | incomplete policy retrieval experiment |
| `interleaved-results.json` | 425,670 | 20 questions x 2 x 3 model arms = 120 | SOL/Terra/Luna comparison, not retrieval-mode arms |

The complete 20-question files above share the same legacy question set. The
inventory hash calculated over ordered `id + LF + exact question + LF` entries
is:

`7c3e6e70e3307a186e5cd940bdb785e39f0060d90424a380e1b013def7ad50cb`

This is an inventory fingerprint only, not the final manifest hash.

## Adjacent Supporting JSON

### Retiring Oversight Lifecycle Files

The 24 JSON files in the retiring oversight `files` root cover:

- reset/create/delete results
- upload results and upload metrics
- AI extraction results and metrics
- candidate-quality results and metrics
- bulk-review results
- publication results and metrics
- AIS index-rebuild results and metrics

They can support a source/corpus provenance appendix. They contain no reusable
20-question Consume API calls.

### JSON Retrieval and Wire-Size Probes

`C:\Users\taomar\.copilot\session-state\58f19b59-6aa9-4d38-8782-46cbdc7640c5\files\after-api-measurement.json`
contains six single calls:

| Project | Operation | Mode | Latency | Logical JSON | Decoded body | Wire body |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| AIS | policies | policy | 7,461 ms | 104,886 | 84,236 | 11,934 |
| AIS | Decision Light | policy/default | 25,484 ms | 6,726 | 6,433 | 2,231 |
| AIS | receipt | policy | 69 ms | 36,468 | 34,486 | 7,502 |
| HW | policies | policy | 5,269 ms | 19,723 | 18,536 | 3,548 |
| HW | Decision Light | policy/default | 28,820 ms | 8,890 | 8,555 | 2,905 |
| HW | receipt | policy | 20 ms | 71,852 | 67,910 | 13,295 |

`api_samples.json` contains one AIS example of policy retrieval, Decision Light,
receipt retrieval, and full Decision. These are useful response-adapter fixtures
and byte-definition prior art, but they are not a matrix.

A referenced earlier baseline also exists at:

`C:\Users\taomar\.copilot\session-state\d99011fe-a8c3-4032-872b-1643baaef994\files\baseline-api-before.json`

It has the same two projects and `policies`, `light`, and `receipt` operations.
It is a before/after payload experiment, not contemporaneous six-arm evidence.

### Discovered Full-Decision Baseline

The predecessor harness references:

`C:\Users\taomar\.copilot\session-state\bbd70aaa-01a5-4b9e-9ee2-8210b795d829\files`

That folder contains two policy-mode full-Decision result sets,
`decision-10x3-results.json` and `decision-10x3-final-results.json`. Each has 10
questions x 3 repeats = 30 calls, but the set is 6 AIS and 4 HW, not the
required 10 and 10. The two files share question-set fingerprint
`63144d961ba0d34672c71d03511a8ebb55dee7914fec73ef552ff713327b6236`.
They preserve raw full receipts and are useful C-arm fixtures only.

### Repository-Local JSON

The read-only repository junction exposes:

- `.artifacts\live-raw.json`: 23 policy-extraction model-stage records.
- `.artifacts\live-package.json`: one
  `policy-extraction-package/1` in `needs_review`.

Both concern document extraction, not Consume API comparison, and are excluded
from reuse.

## Required Field Coverage

| Required field | Legacy evidence | Gap |
| --- | --- | --- |
| Exact question | Present in normal matrices | Final parent-approved set and canonical hash are pending |
| Latency | Wall and service latency generally present | one suspension-corrupted value; C/D contract requires wall plus stage timings |
| Token size/usage | Present for decision calls; policy retrieval exposes top-level usage | field paths differ by surface and need one normalized schema |
| Input bytes | Not captured | rerun required |
| Output bytes | Present only in paired/post-fix and payload probes | exact raw body and `Content-Length` must be captured separately for every call |
| Answer/information/verdict | Present for A-D | E-F do not expose decisions; report must mark these fields not exposed, not empty |
| Source-grounded correctness | Legacy checks only expected policy-label keywords and coarse status | finalized source-grounded rubric and per-call adjudication required |
| Citations/integrity | Strong A-D checks exist | must normalize by surface and join to rubric evidence; E-F uses retrieval evidence rather than decision citations |
| Three-repeat consistency | A/B generally have two-repeat summaries; older C has three repeats for only 10 questions | full 3-repeat run required across all six arms |
| Provenance | scattered across files | freeze contract, questions, rubric, source snapshot, model/prompt, and policy/index identifiers in one manifest |

## Reuse Decision by Arm

| Arm | Existing evidence | Official reuse decision | What remains |
| --- | --- | --- | --- |
| A: Decision Light / policy | post-fix paired 20 x 2 | baseline only; rerun all 60 recommended | third repeat, input bytes, exact raw body bytes, final rubric, frozen provenance |
| B: Decision Light / rule | post-fix paired 20 x 2 | baseline only; execution blocked | stabilized mode echo, Rule Retrieval stability, then all 60 calls |
| C: full Decision / policy | two older 10 x 3 sets with 6 AIS/4 HW plus two final-state fixtures | adapter fixture only | required 20-question set, byte metrics, contemporaneous 60 calls |
| D: full Decision / rule | two singleton final-state fixtures | adapter fixture only | all 60 calls |
| E: JSON-only policies / policy | one AIS and one HW byte probe, plus one AIS sample | byte-definition fixture only | all 60 calls and finalized retrieval correctness rubric |
| F: JSON-only policies / rule | none | no reuse | all 60 calls after Rule Retrieval stabilization |

No legacy call is accepted as an official matrix row now. Reusing A/B calls
would save at most 80 primary calls but would produce a temporally mixed report,
still lack request bytes, and bias the comparison against newly collected C-F
data. A clean 360-call run is the smaller correctness risk.

## Execution Estimate

- Primary measured calls: `20 questions x 3 repeats x 6 arms = 360`.
- A/B full-receipt integrity reads: up to 120 additional non-decision GETs.
- Normal HTTP transactions: up to 480, before retries.
- Persistence: A-D create 240 decision receipts; E-F create none.
- Historical central latencies:
  - A: 21.8 seconds post-fix p50
  - B: 26.1 seconds post-fix p50
  - older C: approximately 31.9 seconds p50
  - E policy probes: approximately 5.3 to 7.5 seconds
  - D and F do not have representative matrix baselines
- Proposed serial collection window: 2.5 to 4 hours.
- Proposed hard bounds: 6 active hours and 8 wall-clock hours, with suspension
  detection and checkpointing after every attempt.
- Expected local artifact volume: approximately 25 to 100 MB, depending on
  policy payload sizes and whether compressed wire bodies are retained.
- Deterministic normalization/report generation: approximately 15 to 30
  minutes after collection. Manual adjudication time is rubric-dependent and is
  not included.

## Execution Gates

The parent has verified the A-F endpoint families and metric locations, but live
execution remains forbidden until all of these are true:

- stabilized contract supplied, including retrieval-mode echo behavior
- 10 AIS and 10 HW questions finalized
- source-grounded rubric finalized
- Rule Retrieval declared stable
- explicit parent authorization bound to frozen artifact hashes

The pending manifest intentionally sets every gate to false.
