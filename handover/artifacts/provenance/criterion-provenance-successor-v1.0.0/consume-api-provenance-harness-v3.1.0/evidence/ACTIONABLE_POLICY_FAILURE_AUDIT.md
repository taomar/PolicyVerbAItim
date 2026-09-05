# Actionable Policy Failure Audit

## Scope and evidence

This is the authoritative read-only audit of the 38 adjudicated failures in arms
A, C, and E. Arms B, D, and F are excluded from every conclusion.

The full row ledger is:

`actionable-policy-audit-checkpoint-38.json`

Each row records the job ID; raw, raw-file, and telemetry hashes; question, arm,
and repetition; expected evidence and tracks; search candidacy/rank; retained
evidence; composed/cited evidence; answer/verdict; earliest proven failing
boundary; `failure_validity`; evidence-backed root cause; historical comparison;
corrective action; regression test; and a 3/3 acceptance criterion.

All 38 raw-record file hashes and all 38 decoded-telemetry hashes were recomputed
against `_evidence.json`: **76/76 matched**. The repository, original adjudicated
package, services, database, and Search were not modified.

| Artifact | SHA-256 |
|---|---|
| Checkpoint 10/38 | `37eb0d856c21cf9d59ae984c6a62ecd882319b3bf7faada262758f4e59a8326d` |
| Checkpoint 20/38 | `73104ac86de48276131d53d10ab82badbce518b5fba0da460edbc44df85de19d` |
| Checkpoint 30/38 | `f74abc25c2c47a4004ebe468e6d6464f867d80892e05c85cef859ea38ab6a4f4` |
| Checkpoint 38/38 | `b57e782bb49080d1067488c3ddbd61aeffa9018062bcef45bebb4b51597ad738` |

## Final adjudication

| Failure validity | Rows | Meaning |
|---|---:|---|
| `true_product_failure` | 26 | A product boundary failed against a source-supported expectation. |
| `rubric_false_failure` | 11 | The product response was failed by a criterion unsupported by the source. |
| `unresolved` | 1 | The source does not settle whether the observed product verdict is correct. |
| **Total** | **38** | |

No actual regression is proven.

| Historical category | Rows |
|---|---:|
| New-test exposure | 15 |
| Pre-existing retrieval defect | 9 |
| Stricter valid rubric exposing a pre-existing extraction defect | 2 |
| Invalid or unsupported rubric | 11 |
| Unresolved new observation | 1 |
| Proven actual regression | **0** |

## Row-level result by question

| Question | Rows | Validity | Earliest proven boundary | Evidence-backed finding |
|---|---:|---|---|---|
| AIS-02 sick surgery | 5 | Rubric false failure | Evaluation rubric | Section 7.13 grants 30 paid sick-leave days and requires a sealed medical report after return. It does not make a final certificate a pre-leave condition. |
| AIS-02 sick surgery, `C__...__r3` | 1 | Unresolved | Verdict composition / policy semantics | The response returned `allowed`. The source supports entitlement and post-return verification but does not define whether entitlement equals immediate approval. |
| AIS-03 absence penalty | 2 | True product failure | Source extraction / rule modeling | The source table has 1st/2nd/3rd/4th occurrence columns. The served rule lists consequences but loses their occurrence associations. |
| AIS-04 conflict vendor | 9 | True product failure | Retrieval ranking/retention | A/C expose required 8.7 only at rank 10 and retain 8.6; E omits 8.7 from its returned set. The same wrong provision appears historically. |
| AIS-06 overtime weekend | 6 | Rubric false failure | Evaluation rubric | Section 7.9 requires HR/senior-management approval but never written approval and supplies no overtime-pay entitlement. The frozen criterion invents "written" as operative. |
| AIS-08 probation and evaluation | 9 | True product failure | Semantic elbow / retrieval result set | 7.5 ranks first; required 7.4 ranks second at 1.914, above the 1.75 coverage floor, but only 7.5 is retained/returned. |
| AIS-09 leave/travel composition | 6 | True product failure | Evidence composition / citation gather | Both required provisions are retained at ranks 0 and 1, but every A/C answer cites and uses only 7.19, never held 7.12. |

### Earliest-boundary counts

| Boundary | Rows |
|---|---:|
| Evaluation rubric | 11 |
| Policy candidate selection / retention | 6 |
| Policy retrieval result set | 6 |
| Semantic elbow / policy retention | 6 |
| Evidence composition / citation gather | 6 |
| Source extraction / rule modeling | 2 |
| Verdict composition / policy semantics | 1 |

## Historical verification

### Old-rubric replay

The old harness was inspected directly. It:

- matches expected evidence by case-insensitive substring over policy heading
  labels;
- checks irrelevant safety from citations, answer/verdict absence, and outcomes;
- checks verdict status only when a scenario declares `expected_verdict` or
  `expected_verdict_any`.

An independent replay over the new A/C rows produced:

| Comparable question | Old rubric on new rows |
|---|---:|
| AIS-01 annual vacation | 6/6 |
| AIS-02 sick surgery | 6/6 |
| AIS-03 absence penalty | 6/6 |
| AIS-04 conflict vendor | 0/6 |
| AIS-05 maternity leave | 6/6 |
| AIS-06 overtime weekend | 6/6 |
| AIS-07 tuition child | 6/6 |
| AIS-10 irrelevant football | 6/6 |
| **Total** | **42/48 = 87.5%** |

The reported historical global value **17/20 = 85%** is arithmetically correct,
but it mixes AIS and HW and reports scenarios rather than new-run repetitions.
It is not the strongest causal comparator.

The like-for-like historical AIS subset is **7/8 = 87.5%** in both
`decision-light-20x2-summary.json` and `fresh-20x2-default-summary.json`. That
matches the new old-rubric replay exactly. This supports "no regression proven"
without relying on the weaker cross-corpus 85% comparison.

### Retained evidence continuity

Historical labels were mapped through the frozen source snapshot to exact keys.
The retained key is identical in the historical baseline, historical
fresh-default run, and all new A/C repetitions for seven positive comparable
questions:

| Question | Exact retained key |
|---|---|
| Annual vacation | `ab87a692f3a20e95c545a0ce7718ba61` |
| Sick leave | `28334f1a0b3c389682647d43c89d554f` |
| Absence penalty | `e8326a491c60c8914b7932dd0f2607eb` |
| Conflict vendor | `eddb92e116296d15639385e5283f067d` (same wrong 8.6 provision) |
| Maternity leave | `01309aeb409607211e4115e044bd8ac3` |
| Overtime | `4094ad6b422dbb097ec11368c525b5a6` |
| Tuition child | `77ec032421fdcfc11ed1dd2fb6ee7ae4` |

The irrelevant control has no expected evidence key, so "retained-key identity"
is not a meaningful claim for that row; its comparable invariant is safe
non-answering.

### Configuration continuity

Across all 38 audited rows there is exactly one value for each recorded run
input: model `gpt-5.6-terra`, effort `medium`, repository commit
`c0972c8bb7ba811903e981d3806afe31cc1f514d`, service/tree hash
`42817a2b3aa03b9f7b15300288dd4148216c7ab2cedd77b52426d4a5a7484f2d`,
policy version `86b940aa-7efd-4b75-837c-a2646e93de23`, prompt
`ai-case-intent-v15`, source snapshot, rubric snapshot, and contract snapshot.

The historical summary/result files do not encode model deployment or index
version. Therefore cross-era model/index identity cannot be independently
proved from those immutable result files alone and is not used as a premise for
the classifications above.

## Source/rubric reconciliation

The source PDF hash used for direct checks is
`a4ab80af24640509976881a36b76895b474558f3cb5a1b4fa564d0bf7faf07e9`.

- **AIS-06:** source 7.9 says overtime should be approved and controlled by HR
  and senior management. It does not say approval must be written. All six
  responses cite 7.9 and honestly decline to infer compensation entitlement.
  These are rubric false failures.
- **AIS-02:** source 7.13 says medical reports with an official seal should be
  submitted after return. Five non-answered responses were failed for not
  treating a final certificate as a current missing fact. Those are rubric
  false failures.
- **AIS-02 C-r3:** the answer correctly preserves post-return report
  verification but returns `allowed`. The source does not define ordinary
  pre-approval. This is unresolved, not a false-failure pass and not a proven
  product failure.
- **AIS-03:** the source table contains explicit occurrence headers, while the
  cited served rule is flattened into an offense plus consequence list without
  headers. The product failure is real and begins in extraction/modeling, even
  though refusing on the incomplete served rule is locally honest.
- **AIS-04:** source 8.7 exists and is mandatory governing evidence, but it does
  not itself state a vendor-disclosure or recusal procedure. Retrieval must be
  fixed; answer criteria must still be derived from actual body text.

## Reconciliation with provisional work

Agreement with the retired worker's provisional rows:

- AIS-04 begins at retrieval ranking/cut.
- AIS-08 begins at the composition-blind semantic elbow/retention cut.

Disagreement:

- Provisional rows 1, 2, 7, and 8 call AIS-02/AIS-06 product
  answer-reasoning defects. Direct source evidence shows their decisive manual
  criteria are unsupported; they are rubric false failures.
- Provisional row 3 calls AIS-03 a verdict-classification regression. The source
  and cited served rule place the earliest defect in extraction/rule modeling,
  and the old rubric never checked this AIS verdict. It is pre-existing debt
  exposed by a stricter valid check, not a proven regression.

The Payload historical report's final totals agree with this audit:
11 false failures, 26 real product failures across four defect groups, one
unresolved AIS-02 observation, and zero proven regressions. This audit narrows
two statements:

1. the best historical comparator is AIS 7/8, not global 17/20;
2. historical cross-era model/index identity is not independently encoded in
   the immutable result files.

## Prioritized remediation plan

| Priority | Owner / boundary | Correction | Why first |
|---|---|---|---|
| P0 | Evaluation owner / rubric authoring | Withdraw AIS-02 certificate and AIS-06 written-approval criteria. Require body-derived criterion provenance and a pre-score corpus-support check. | Removes 11 false failures and prevents product tuning to invented policy. |
| P1 | Retrieval owner / candidate selection | Add coverage-aware handling for explicit multi-part queries. A second candidate above the coverage floor must not be discarded solely by a single largest-gap elbow. | Fixes all 9 AIS-08 rows without corpus-specific boosts. |
| P1 | Retrieval owner / ranking and rescue | Improve multi-intent ranking/diversification so governing provisions are not crowded out by topical siblings; test 8.7 vs 8.6. | Fixes all 9 AIS-04 rows, the largest real pre-existing defect. |
| P1 | Ingestion/extraction owner / table semantics | Preserve table headers and row-to-column occurrence associations through canonical extraction, approved-rule projection, and Search payloads. | Fixes the upstream cause of both AIS-03 failures. |
| P1 | Decision/gather owner / composition completeness | Track requested subparts against retained authorities and block finalization when required held evidence is unused. | Fixes all 6 AIS-09 rows; retrieval is already correct. |
| P2 | Product-contract owner / verdict semantics | Define whether leave entitlement can yield immediate `allowed` without an explicit approval rule. Keep C-r3 unresolved until decided. | Prevents accidental policy invention in either direction. |
| P2 | Evaluation/reporting owner | Always report validity, baseline availability, old-rubric replay, expected evidence misses, and earliest boundary with pass rates. | Prevents false trend claims and keeps retrieval, composition, and rubric defects separate. |

No remediation should hardcode AIS question text, provision keys, ranks, or
thresholds into product behavior.

## Regression tests and rerun gates

### Gate 1 - rubric-only rescoring, no product changes

1. Re-score the immutable run after withdrawing unsupported criteria.
2. AIS-06 must become non-failing in all 6 A/C rows.
3. Five non-answered AIS-02 rows must become non-failing.
4. AIS-02 C-r3 must remain explicitly unresolved until the approval contract is
   decided; do not count it as a pass to improve a rate.

### Gate 2 - focused boundary tests

1. **AIS-08 retrieval:** 3/3 per A/C/E retain or return both 7.4 and 7.5; A/C
   cite both, answer both subquestions, and leave verdict `not_requested`.
2. **AIS-04 retrieval:** 3/3 per A/C/E retain or return 8.7; A/C cite it and do
   not ground solely in 8.6.
3. **AIS-03 extraction:** a source fixture proves explicit
   occurrence-to-consequence mappings survive extraction and projection; then
   3/3 per A/C answer first occurrence from that mapping.
4. **AIS-09 composition:** 3/3 per A/C cite and use both 7.12 and 7.19, covering
   travel-day treatment and what the source does or does not establish about
   vacation-day count.

### Gate 3 - controlled matrix rerun

1. Run the same 10 AIS questions on A/C/E only. Keep B/D/F outside actionable
   conclusions.
2. Use at least 3 repetitions for each repaired deterministic boundary. Use at
   least 5 per A/C arm for the unresolved AIS-02 outcome after its contract is
   defined, because one answered event appeared in 6 new observations.
3. Hold model `gpt-5.6-terra`, effort `medium`, prompt, rubric version, and
   service build constant within the rerun.
4. If extraction is repaired, rebuild the index and record new source/index
   hashes. Do not call that run historically identical across the rebuild.
5. Require 3/3 focused acceptance before using aggregate rates.
6. Publish the corrected rubric score and old-rubric replay together, with
   baseline scope and unavailable comparisons stated explicitly.

