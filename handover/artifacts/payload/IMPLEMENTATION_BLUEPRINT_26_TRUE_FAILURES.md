# Implementation Blueprint — 27 Confirmed True Product Failures

Child: **Payload and Full-Cycle Verification** · Session `5a06fec2-12cd-4477-b574-4d18ab814907`
Parent: `b065f09b-2a4c-479f-a012-e6e55f388234` · Prepared 2026-09-04
Authority: `0fb0b358-89fc-46d2-89cb-04d162e75ff3\files\ACTIONABLE_POLICY_FAILURE_AUDIT.md`
plus `actionable-policy-audit-checkpoint-38.json` (SHA-256 `b57e782b…7ad738`).

**ARTIFACT ONLY. NO REPOSITORY EDIT IS MADE OR AUTHORISED BY THIS DOCUMENT.**
Every code reference below is a *target*, located read-only. Implementation begins
only after the shared-checkout lock is granted.

Evidence tags: **[D]** direct this session · **[A]** audit/run artifact · **[I]** inherited.

---

## 0a. Handoff constraints — read before touching any file

Parent-confirmed on acceptance. These five distinctions are the point of this
blueprint; losing any one of them turns a correct fix into a wrong one.

| # | Constraint | Where |
|---|---|---|
| 1 | **AIS-08 is a property-gate fix, ready.** Derive the gate from *cut-applied ∧ budget-unspent*. **Do not** simply add `DIRECT_POLICY_ORDER_SEMANTIC` to the frozenset — that repeats the exact defect this codebase already fixed once. | §2.3, §2.4 |
| 2 | **AIS-04 is measurement before tuning.** Attribute the sub-boundary (lexical / semantic / fusion) first. **No threshold or `RRF_K` change** until then. | §3.4 |
| 3 | **AIS-09 is a composition boundary.** Retrieval is already correct; **no retrieval change**. Changing retrieval here treats a symptom at the wrong boundary. | §4.1 |
| 4 | **AIS-03 is locate-then-fix.** Find the exact stage where the header association is dropped before changing anything; `table_headers`/`table_id` already exist. Re-extraction needs its **own authorisation**, separate from the checkout lock. | §5.3, §5.5 |
| 5 | **AIS-02 is a true decision-reasoning failure** (parent-resolved 2026-09-04, under the existing `ai-case-intent-v15` contract). A settled entitlement must not be collapsed into an operational approval. **No AIS-specific logic.** | §6 |

Two further standing limits: nothing corpus-specific ever enters product code, and
none of the 11 rubric false failures may justify a product change.

**Binding user invariant (§10).** AIS is **regression evidence only**. Every fix
must state its general invariant, pass the §10.2 leakage audit, and carry the
§10.3 diverse controls — at least three, none AIS-shaped. Three blocking coverage
gaps are recorded in §10.2 L-1/L-2: `ai_case_intent` and the three ingestion
modules are unregistered in the anti-corpus suite, and its measured-magnitude
check tests integers only, so a float constant would slip through.

**Binding execution rule (§11).** Every long test or execution must print visible
progress — progress reporters, bounded shards, or periodic logged checkpoints.
**No silent long-running commands.** A section whose verifying run was executed
silently is not complete, regardless of its result.

---

## 0. What this blueprint covers

| Group | Rows | Earliest proven boundary | Section |
|---|---:|---|---|
| P0 rubric provenance / corpus-support gate | (11 false failures) | Evaluation rubric | §1 |
| AIS-08 multi-part coverage / elbow | 9 | Semantic elbow / retention | §2 |
| AIS-04 ranking | 9 | Retrieval ranking / retention | §3 |
| AIS-09 held-evidence composition | 6 | Composition / citation gather | §4 |
| AIS-03 table ordinality | 2 | Source extraction / rule modeling | §5 |
| AIS-02 entitlement vs approval | 1 | Decision reasoning / verdict composition | §6 |
| **True product failures** | **27** | | §2–§6 |

Final classification, parent-confirmed 2026-09-04:
**27 true product failures · 11 rubric errors · 0 unresolved · 0 proven regressions.**

§1 is P0 but changes **no product behaviour**; it exists so the 11 false failures
cannot drive product tuning.

**Standing constraint applied throughout:** no corpus-, project-, index-, page-,
language- or domain-specific behaviour. No AIS question text, provision key, rank
or score may enter product code. Enforced by
`tests/unit/test_no_m2_code_is_shaped_around_a_corpus.py` **[D]**.

---

## 1. P0 — rubric provenance and corpus-support gate (no product change)

**Boundary:** evaluation artifacts only. **Rows removed from the failure set: 11.**

### 1.1 Why first

The audit proves 11 rows were failed by criteria the source does not support **[A]**:
7.9 requires HR/senior-management approval but **never written approval**; 7.13
requires a sealed medical report **after return**, not a pre-leave certificate.
If any product change were tuned to make those rows pass, the system would be
tuned to invented policy. This gate must land before §2–§5 are measured.

### 1.2 Targets — artifact side only

| Artifact | Change |
|---|---|
| `…\5a06fec2…\files\CONSUME_API_EVALUATION_RUBRIC.md` §4 | Withdraw AIS-06 "written approval" criterion; withdraw AIS-02 certificate criterion; rewrite AIS-03's as a known-limitation probe. Record all three in §10.1. |
| `…\9939b1b3…\files\consume-api-matrix\evaluation-rubric.json` and the run's `rubric.snapshot.json` | New rubric **version**, never an edit of a frozen snapshot. |
| Harness rubric schema | Add the two fields below. |

### 1.3 The two structural fields

```
criterion_provenance : "rule_body" | "heading_path" | "question_only"
corpus_support       : { checked: bool, supporting_rule_count: int, method: str }
```

**Invariant P0-1 — only body-derived criteria may fail a repetition.**
A criterion with `criterion_provenance != "rule_body"` may be *reported* but must
resolve to `n/a`, never `fail`.

**Invariant P0-2 — pre-score corpus-support check.**
Before scoring, each criterion is checked against the corpus. Zero support ⇒ the
criterion is reported as a **rubric finding**, and the repetition is not charged.

This converts my §6.1 failure mode from a matter of care into a structural
impossibility. It is the direct analogue of the guard the audit itself applies.

### 1.4 Guard tests (evaluation harness, not product)

1. **Refusal test:** a heading-derived criterion with zero corpus support must
   yield `n/a` + rubric finding, never `fail`.
2. **Control test proving it does not neuter everything:** a body-derived criterion
   with non-zero support on a genuinely wrong answer must still `fail`. Required by
   the standing rule that a validation guard needs a refusal test *and* a control.
3. **Replay fixture:** re-scoring the immutable run must reproduce Gate 1 exactly —
   AIS-06 6/6 non-failing, 5 AIS-02 non-failing, AIS-02 `C__…__r3` still
   `unresolved`.

### 1.5 Acceptance — audit Gate 1

Rubric-only rescoring of the immutable run, **no product change**. AIS-02 `C-r3`
must remain `unresolved` and **must not be counted as a pass to improve a rate**.

---

## 2. AIS-08 — multi-part coverage / elbow (9 rows)

### 2.1 Proven boundary [A]

7.5 ranks first; required **7.4 ranks second at 1.914, above the 1.75 coverage
floor**, yet only 7.5 is retained/returned across A, C and E.

### 2.2 Root cause — located directly [D]

`src\policy_platform\infrastructure\assistants\ai_case_project.py`

1. `select_semantic_policy_hits` (**:702–780**) cuts at the single largest adjacent
   gap: `count = gaps.index(largest_gap) + 1` (**:762–763**). When the largest gap
   sits between rank 0 and rank 1, `count == 1`.
2. `select_decision_policy_hits` (**:783–1000**) takes cardinality from that cut:
   `direct = ranked_direct[: len(semantic_direct)]` (**:859**, **:905**).
3. `strong_semantic_lead` (gap ≥ `DECISION_STRONG_SEMANTIC_GAP = 0.30`, **:838–839**)
   sets `direct_policy_order = DIRECT_POLICY_ORDER_SEMANTIC` (**:860**).
4. Coverage expansion is gated at **:3341** on
   `precision.get("direct_policy_order") in COVERAGE_EXPANDABLE_POLICY_ORDERS`,
   and that frozenset is `{DIRECT_POLICY_ORDER_RRF, DIRECT_POLICY_ORDER_RULE}`
   (**:365–367**) — **`DIRECT_POLICY_ORDER_SEMANTIC` is absent**.

**So a strong lead gap disables the only mechanism that could restore a
distinct-subpart provision above the coverage floor, while leaving 4 of the
5-policy budget (`RETRIEVAL_POLICY_BUDGET = 5`, **:232**) unspent.**

### 2.3 This is a repeat of a defect this codebase already fixed once

The comment at **:357–364** states the rule and records the prior instance:

> *"Coverage expansion exists to spend budget a cut left unspent… Rule mode belongs
> here for exactly the same reason policy-mode RRF does, and it was silently absent —
> **the gate read one order rather than the property the orders share**, so rule mode
> never reached the expansion even when its cut had left the budget half empty."*

`DIRECT_POLICY_ORDER_SEMANTIC` satisfies that shared property exactly: a cut
happened, and budget remains unspent. `DIRECT_POLICY_ORDER_HYBRID` correctly does
not (no cut; pool already fills the budget).

**Therefore the correct fix is structural, not another constant in the set.**
Adding `DIRECT_POLICY_ORDER_SEMANTIC` to the frozenset would fix these 9 rows and
leave the same trap armed for the next order added. Derive the gate from the
property.

### 2.4 Target change

**File:** `ai_case_project.py`
**Boundary:** selection/expansion gate — *not* the elbow's own arithmetic.

- Replace the enumerated `COVERAGE_EXPANDABLE_POLICY_ORDERS` membership test at
  **:3341** with a derived predicate, e.g. `coverage_expansion_is_available(precision)`
  returning true iff **a cut was applied** (`semantic_elbow_applied`) **and**
  `len(selected) < RETRIEVAL_POLICY_BUDGET`.
- Keep `expand_policy_query_coverage` (**:1370**) and
  `expand_policy_coverage_after_duplicate_collapse` (**:1502**) unchanged; they
  already enforce the floor (**:1070**) and one-consumption-per-term (**:1383–1385**).
- Retain the constant only if some caller still needs the named order list; it must no
  longer be the gate.

**Do not** change `DECISION_STRONG_SEMANTIC_GAP`, `DECISION_COVERAGE_SEMANTIC_FLOOR`,
`RETRIEVAL_POLICY_BUDGET`, or the elbow arithmetic. The cut is not wrong; disabling
the compensating mechanism after the cut is.

### 2.5 General invariants

- **INV-08-1** Whenever a selection cut leaves the policy budget unspent, coverage
  expansion is reachable, **for every ordering**, present or future.
- **INV-08-2** A candidate at or above `DECISION_COVERAGE_SEMANTIC_FLOOR` that
  covers an explicit query aspect not covered by the selected set is never
  discarded *solely* because a single largest-gap elbow cut above it.
- **INV-08-3** Expansion still adds only a policy whose heading names an explicit
  aspect of the query, each term consumed once (existing behaviour preserved).

### 2.6 Tests

| Test | Assertion |
|---|---|
| Unit, synthetic scores | Two candidates, largest gap at position 0, second ≥ floor and covering a distinct aspect ⇒ expansion reachable and second retained. Corpus-neutral fixture. |
| **Mutation control** | Force the gate to `False` ⇒ the test above must fail. If it still passes, the gate is not load-bearing. |
| **Order-agnosticism** | Parametrise over every `DIRECT_POLICY_ORDER_*`: expansion reachable iff cut-happened ∧ budget-unspent. Fails if anyone re-introduces an enumerated set. |
| **Non-expansion control** | Under `DIRECT_POLICY_ORDER_HYBRID` (no cut, budget full) expansion must **not** run — proves the fix did not become "always expand". |
| **Recall control** | Single-aspect question with one strong lead must **not** gain a second policy. Prevents a precision regression on AIS-01/05/07. |

**Regression sentinels:** `tests/unit/test_policy_case_project.py`,
`test_no_m2_code_is_shaped_around_a_corpus.py`.

### 2.7 Acceptance — audit Gate 2.1

3/3 per A/C/E retain or return **both** 7.4 and 7.5; A/C cite both, answer both
subquestions, verdict stays `not_requested`.

---

## 3. AIS-04 — retrieval ranking (9 rows)

### 3.1 Proven boundary [A]

A/C expose required **8.7 only at rank 10** and retain 8.6; E omits 8.7 from its
returned set. The same wrong provision (`eddb92e1`, 8.6 CONFIDENTIALITY) appears
historically **[A]/[D]** — pre-existing, not a regression.

### 3.2 Why §2's fix does not reach it

Decisive and easy to get wrong: `select_semantic_policy_hits` builds
`window = ranked[:max_budget]` with `max_budget = LIGHT_RETRIEVAL_MAX_POLICIES =
RETRIEVAL_POLICY_BUDGET = 5` (**:336**, **:232**, **:755**) **[D]**.
**Rank 10 is outside the window, so it is not a coverage-expansion candidate at
all.** Coverage expansion selects from what the window already admitted.

So AIS-04 is a **ranking/candidacy** defect, and it is a *different* boundary from
AIS-08 even though both end as "required provision not retained". Fixing §2 will
not move these 9 rows — a prediction that Gate 2.1 passing while Gate 2.2 still
fails would confirm.

### 3.3 Shared shape with AIS-08 — one question, not two

Both are: **a topically-adjacent sibling crowds out the governing provision**
(8.6 over 8.7; 7.5 over 7.4). The remedies differ by boundary — candidacy/ranking
here, post-cut expansion there — but they should be investigated as one
multi-intent ranking question and measured together.

### 3.4 Target change — investigation first, no blind tuning

**File:** `ai_case_project.py`, candidate selection and the RRF fusion at
**:867–906**; `RRF_K`; the window bound at **:755**.

Sequenced, because the audit's evidence does not yet identify which sub-boundary
is wrong:

1. **Measure before changing.** Capture, for a multi-intent question, the hybrid
   rank, semantic rank and fused rank of every candidate to rank ~20. Determine
   whether 8.7 is under-ranked by lexical, by semantic, or only by the fusion.
2. **Then** choose the smallest correction: widening the *candidate* window (not
   the retention budget), or diversification over distinct heading aspects before
   the window is cut.
3. **Never** boost by provision key, heading text or corpus.

**Explicitly deferred:** no threshold or `RRF_K` change before step 1 attributes
the cause. The standing instruction — no new cutoff or statistic before measured
attribution — applies here.

### 3.5 General invariants

- **INV-04-1** Candidate windowing must not permanently exclude a provision that a
  later coverage or diversity stage would be entitled to admit; window ⊇ what any
  downstream stage may select from.
- **INV-04-2** Two provisions of comparable relevance under the same heading parent
  must not be reduced to one by lexical similarity alone.
- **INV-04-3** No ranking input may be derived from a specific corpus, key or page.

### 3.6 Tests

- Synthetic multi-intent fixture where the governing provision ranks below a
  topical sibling ⇒ it must reach the returned set.
- **Recall control:** an unrelated low-ranked provision must **not** be admitted —
  proves the fix is not "widen until everything passes".
- Mutation control on the window bound.
- E-arm (`/policies`) assertion: 8.7 present in the returned set, since E has no
  gather to recover it.

### 3.7 Acceptance — audit Gate 2.2

3/3 per A/C/E retain or return 8.7; A/C cite it and do not ground solely in 8.6.
**Answer criteria must still be derived from 8.7's actual body text** — the audit
records that 8.7 does **not** itself state a vendor-disclosure or recusal
procedure **[A]**, so retrieval success must not be re-scored with an invented
expectation. This is the §1 gate applied to §3's own acceptance.

---

## 4. AIS-09 — held-evidence composition (6 rows)

### 4.1 Proven boundary [A]

**Retrieval is already correct**: both required provisions are retained at ranks 0
and 1. Every A/C answer cites and uses only 7.19 and **never the held 7.12**.

This is the cleanest defect in the set: the system held the evidence and did not
use it. No retrieval change is warranted, and any retrieval change made here would
be treating a symptom at the wrong boundary.

### 4.2 Target boundary

The gather/composition stage, not retrieval:
- `src\policy_platform\infrastructure\assistants\ai_case_intent.py` —
  `_gather_informational` (**:3402**) and `_gather_decision` (**:3425**) **[D]**
- `src\policy_platform\infrastructure\assistants\ai_case_project.py` —
  `select_retained` (**:1847**) and the citation assembly
- `src\policy_platform\contracts\case_decision.py` — where citations and the
  `considered`/`retained` blocks are sealed

### 4.3 Target change

Add a **composition-completeness check** between retention and finalisation:
retained authorities are tracked against the requested subparts, and finalisation
is blocked when required **held** evidence is unused.

The correct failure mode matters as much as the check. When held evidence is
unused the response must **not** silently answer from the subset. It must either
compose the held evidence or report the gap honestly — the existing
`missing_required_facts` / `not_settled_by_rules` vocabulary already expresses
this and must be reused rather than extended.

### 4.4 General invariants

- **INV-09-1** Evidence that was retained and is required by an explicit subpart of
  the question is either **used and cited**, or its non-use is **disclosed**. Silent
  non-use is prohibited.
- **INV-09-2** The check is driven by the question's own subparts and the retained
  set — never by a provision list.
- **INV-09-3** No caching or memoisation is introduced in the decision path
  (standing constraint).

### 4.5 Tests

- Two retained authorities, answer uses one ⇒ blocked or disclosed, never a silent
  partial answer.
- **Refusal + control pair:** a single-subpart question using its single authority
  must still finalise normally.
- Receipt-integrity: `citation_policy_integrity` (citations ⊆ retained) must still
  hold; adding a citation must not break the seal.
- Full/Light projection parity — an intra-execution invariant only, per rubric §9.4.

### 4.6 Acceptance — audit Gate 2.4

3/3 per A/C cite **and use** both 7.12 and 7.19, covering travel-day treatment and
what the source does or does not establish about vacation-day count.

---

## 5. AIS-03 — table ordinality extraction (2 rows)

### 5.1 Proven boundary [A]

The source table has **1st/2nd/3rd/4th occurrence columns**. The served rule lists
consequences but **loses their occurrence associations**. Corroborated
independently **[D]**: 94 anchored rules, all `routing`; "deduction" ×90,
"warning" ×35, **"first"/"second"/"third" ×0**.

Refusing on the incomplete served rule is *locally honest* — the decision path is
behaving correctly on the evidence it was given. **The defect is upstream.**

### 5.2 Scope discipline

This is the deepest fix and touches ingestion, projection and Search payloads. It
is **2 of 26 rows**. It must not be allowed to block §2–§4, which together account
for 24 rows and are far better isolated.

Also note: the visual-recovery work is **not implicated** — the pages 21–27 region
retrieves and cites correctly 6/6 **[D]**. Only the column-header association is
lost. Do not reopen the recovery path.

### 5.3 Target boundaries

| Stage | File |
|---|---|
| Canonical extraction | `infrastructure\ingestion\document_ingestion.py`, `document_extraction.py` |
| Table structure carrier | `contracts\canonical_document.py` (`table_headers`, `table_id` exist on `clauses` **[D]**) |
| Rule projection | `infrastructure\extraction\ai_extraction.py` (candidate rule formulation) |
| Search payload | `infrastructure\search\policy_rule_slice.py`, `english_projection.py` |

`clauses.table_headers` and `clauses.table_id` **already exist** **[D]**, so the
header information may already survive ingestion and be lost later. **Locate the
exact stage where the association is dropped before changing anything** — the fix
could be as small as carrying an existing field through projection.

### 5.4 General invariants

- **INV-03-1** Where a source table associates a row with a column header, that
  association survives to the served rule, or the rule **declares** that it does
  not. A flattened consequence list must not present as complete.
- **INV-03-2** Generic across any header/row table — no penalty-table, AIS or page
  special-casing.
- **INV-03-3** Existing literal-preservation and faithfulness guarantees are
  unchanged; this adds structure, never rewrites text.

### 5.5 Tests

- **Source fixture** proving explicit occurrence-to-consequence mappings survive
  extraction **and** projection (audit Gate 2.3 step 1).
- Mutation control: drop the association ⇒ fixture must fail.
- Faithfulness: `projection_faithfulness` and the literal-survival suites must stay
  green — this change must not perturb rendering.
- Re-extraction is required to realise the fix in live data. **That is a corpus
  mutation and needs its own authorisation**, separate from the checkout lock.

### 5.6 Acceptance — audit Gate 2.3

Fixture passes; then 3/3 per A/C answer first occurrence from the recovered
mapping.

---

## 6. AIS-02 — entitlement conflated with approval (1 row)

**Resolved 2026-09-04 by the parent: a true general decision-reasoning failure
under the existing `ai-case-intent-v15` contract.** No contract version change is
required — v15 already demands this behaviour; the decision path is not delivering
it. This supersedes the earlier "unresolved contract decision" framing.

### 6.1 The defect

`C__ais-sick-surgery__r3` returned `verdict = answered`, decision text `allowed`,
`verdict_reached = true` **[A]**.

The source settles entitlement and duration and imposes a **post-return** evidence
obligation. It does **not** define an operational approval process. The response
collapsed a settled *entitlement* into a settled *operational approval* — two
different questions — and answered the second on the strength of the first.

### 6.2 Required behaviour, stated generally

For any question mixing a settled entitlement with an unsettled operational
decision, the response must simultaneously:

1. **preserve** what the source does settle — the entitlement and its duration;
2. **preserve** any evidence obligation the source places at a later point in
   time, without converting it into a present precondition;
3. **keep the operational approval question `not_settled_by_rules`**, because the
   source defines no approval process;
4. **assert no missing fact** that the source does not require — specifically, the
   certificate is **not** a missing fact. §1 withdrew that criterion, and §6 must
   not reintroduce it from the product side.

Point 4 is the trap. The naive repair for a wrongly-`allowed` verdict is to demand
a missing document, which would re-implement the exact false criterion §1 removed.
**The correct verdict is `not_settled_by_rules`, with empty `missing_information`.**

### 6.3 General invariants

- **INV-02-1 — entitlement does not imply approval.** A settled entitlement,
  eligibility or duration never by itself settles an operational decision
  (approve/permit/release) that the source does not define. Absent an approval
  rule, the operational question is `not_settled_by_rules`.
- **INV-02-2 — partial settlement is reported, not rounded.** What the source
  settles must still be reported. The correct response is neither a blanket
  refusal nor a confident approval; it is "this much is settled, that is not".
- **INV-02-3 — a future obligation is not a present precondition.** An obligation
  the source places after an event must not be converted into a missing fact
  blocking it, nor silently dropped.
- **INV-02-4 — no missing fact may be asserted that the source does not require**
  (the product-side statement of §1's corpus-support rule).

None of these names a leave type, a document type, a corpus or a question.

### 6.4 Target boundary

Decision reasoning / verdict composition — the same boundary family as §4, which
is why the two should be sequenced together:

- `infrastructure\assistants\ai_case_intent.py` — `_gather_decision` (**:3425**) **[D]**
- `infrastructure\assistants\ai_case_project.py` — verdict assembly
- `contracts\case_decision.py` — `VerdictStatus` / `VerdictOutcome` vocabulary
  (**:213-231**) and the existing rule that `missing_information` is non-empty
  **iff** status is `missing_required_facts` (**:1537-1542**) **[D]**

The vocabulary needed already exists: `not_settled_by_rules` is precisely
"a relevant policy was found and it does not settle the case", held distinct from
`no_rule_bears` (**:211-212**) **[D]**. **No new status is required, and none may
be added** — a new status would be a contract change where a correct use of the
existing one is what is missing.

### 6.5 Where the correction goes — decide by evidence, not by convenience

Two candidate boundaries; the choice must be measured, not assumed:

1. **Gather/prompt** — v15 already requires this, so the model is under-complying.
2. **Verdict composition** — a structural post-check could detect the shape
   "operational decision reached with no rule defining that decision" and refuse
   to seal it.

Prefer (2) where the shape is structurally detectable, because a prompt-only fix
is model-mediated and unverifiable by a deterministic test. If it is not
structurally detectable without reading the question's semantics, say so and use
(1) with the acceptance measured over n≥5 — do **not** manufacture a keyword rule
to make it detectable. A word list here would violate §10 outright.

### 6.6 Tests — domain-neutral, entitlement vs approval

All fixtures are synthetic and carry no corpus, leave type or document type.

| Test | Assertion |
|---|---|
| **Entitlement settled, approval undefined** | Source settles an entitlement and its duration but defines no approval process ⇒ verdict `not_settled_by_rules`, `verdict_reached = false`, `missing_information` **empty**, and the settled entitlement still reported. |
| **Approval defined** *(control)* | Same shape, but the source **does** define an approval rule ⇒ a reached verdict is permitted. Proves the fix is not "never approve anything". |
| **Future obligation** | An obligation placed after an event must not surface as a present missing fact, and must not be dropped. |
| **No invented missing fact** *(refusal control)* | The response must not assert a missing fact absent from the source — the product-side mirror of §1. |
| **Mutation control** | Disable the new check ⇒ the first test must fail. If it still passes, the check is not load-bearing. |
| **Second corpus (HW)** | The same invariant on `hw-policy`, which has 7 `eligibility` rules and explicit approval-threshold provisions **[D]** — a structurally different setting for the same entitlement/approval split. |
| **Receipt discipline** | `missing_information` non-empty **iff** `missing_required_facts`; `verification_requirements` only when `reached`. Must remain green. |

### 6.7 Acceptance

- The row's correct outcome is `not_settled_by_rules` with empty
  `missing_information` — **not** a `missing_required_facts` verdict naming a
  certificate, which would be §1's withdrawn criterion re-entering by the back
  door.
- **n≥5 per A/C arm**, per the audit: one `answered` event in 6 observations
  cannot be characterised at n=3.
- Focused tests in §6.6 pass, including both controls.

---

## 7. Sequencing, ownership, and what must not happen

| Order | Work | Blocked by | Rows |
|---|---|---|---|
| 1 | §1 P0 rubric gate (artifact only) | nothing | −11 false |
| 2 | §4 AIS-09 composition | §1 | 6 |
| 3 | §6 AIS-02 entitlement vs approval | §1, §4 | 1 |
| 4 | §2 AIS-08 expansion gate | §1 | 9 |
| 5 | §3 AIS-04 ranking — **measure, then fix** | §1, §2 landed | 9 |
| 6 | §5 AIS-03 extraction | §1; re-extraction authorisation | 2 |

§6 follows §4 because both are decision-reasoning/composition work in the same
files; doing them adjacently means one lock window and one regression surface,
rather than two passes over `ai_case_intent.py`.

§2 before §3 deliberately: §2 is a bounded, well-understood gate correction, and
its completion is what makes the §3 prediction in **§3.2** falsifiable.

**Shared-checkout serialization.** §2, §3 and §4 all touch
`ai_case_project.py`; §4 and §6 also touch `ai_case_intent.py` and
`contracts\case_decision.py` — files Rule Retrieval edited on 2026-09-04 **[D]**.
These must be serialized, never concurrent, and the lock must be held per section.

### Prohibited in every section

1. No AIS question text, provision key, rank or score in product code.
2. No threshold change before measured attribution (§3.4).
3. No caching or memoisation in the decision path.
4. No re-scoring of the immutable run's frozen artifacts — new versions only.
5. **No new verdict status for §6** — the existing vocabulary is sufficient, and
   adding one would be a contract change standing in for a correct use of
   `not_settled_by_rules`.
6. **No missing fact asserted that the source does not require** — §6 must not
   repair a wrong approval by re-implementing §1's withdrawn certificate criterion.
7. No product change justified by any of the 11 false failures.
8. No claim of improvement from B/D/F.

---

## 8. Acceptance gates and the falsifiable prediction

**Gate 1** — rubric-only rescoring, no product change: AIS-06 6/6 non-failing;
**5** AIS-02 rows non-failing. `C__ais-sick-surgery__r3` **remains failing** — it is
now a true product failure (§6), not an unresolved row, and Gate 1 must not appear
to clear it.
**Gate 2** — focused boundary tests §2.6, §3.6, §4.5, §5.5, §6.6, each with its
mutation and recall/precision control.
**Gate 3** — controlled matrix rerun: same 10 AIS questions, **A/C/E only**;
n≥3 per repaired boundary, **n≥5** for the §6 outcome; model `gpt-5.6-terra`,
effort `medium`, prompt, rubric version and service build held constant. B/D/F stay
outside all actionable conclusions.

**Prediction, stated so it can fail:** after §1 alone, the 38 becomes **27 true +
0 unresolved**, with **no product change** — §1 clears exactly the 11 rubric errors
and nothing else. After §2, AIS-08 reaches 3/3 while **AIS-04 still fails** —
because rank 10 lies outside the candidate window (§3.2). If AIS-04 improves from
§2 alone, my boundary attribution is wrong and §3 must be re-derived.

Report at every gate: validity, baseline availability, old-rubric replay,
`expected_evidence_miss`, `present_in_retrieval_only`, and earliest boundary —
alongside, never instead of, the pass rate.

---

## 9. Remaining uncertainty — stated, not smoothed

1. **§3 AIS-04 sub-boundary is not yet attributed.** Lexical, semantic or fusion —
   unknown. §3.4 step 1 exists to settle it; no change is specified until it does.
2. **§5 AIS-03 loss stage is not yet located.** `table_headers`/`table_id` exist on
   `clauses` **[D]**, so the loss may be in projection rather than ingestion. The
   blueprint deliberately does not name a line.
3. **§6's correction boundary is not yet chosen.** Whether "operational decision
   reached with no rule defining it" is structurally detectable, or only reachable
   through the gather, is unresolved — §6.5 requires that to be decided by evidence
   and forbids manufacturing a keyword rule to force structural detectability.
4. **Cross-era model/index identity is not encoded** in the historical immutable
   result files (audit §Configuration continuity). My earlier report used it as a
   premise; the audit does not, and the audit is right. It is not load-bearing for
   any conclusion here.
5. **Keyword-count evidence proves token absence, not concept absence.** §5.1's
   zero counts are corroborative; the audit's direct source reading is the
   authority.
6. **n=3 cannot characterise rare events.** Any per-repetition rate in this set
   carries that limit; §6 is the one place it is decision-relevant, which is why it
   alone requires n≥5.

---

## 10. Benchmark-leakage audit and diverse controls (binding)

**Binding user invariant, reaffirmed by the parent:** implementation may use AIS
**only as regression evidence**. No file-, question-, provision-, or data-specific
case, and no corpus-tuned constant. Every fix below must state its general
invariant (already done in §2–§5), pass the leakage audit in §10.2, and carry the
diverse controls in §10.3.

### 10.1 The mechanism already exists — anchor to it, do not invent a parallel one

`tests\unit\test_no_m2_code_is_shaped_around_a_corpus.py` (32 KB) is an AST-based
suite that already enforces this **[D]**:

| Test | What it forbids |
|---|---|
| `test_no_authored_module_names_a_domain_anywhere_in_its_code` (**:437**) | any domain word in an executable string or bound name — prompts included, since a prompt is a string |
| `test_no_touched_module_lets_a_domain_word_steer_behaviour` (**:456**) | domain words in *acting* positions: comparisons, lookup keys, collections |
| `test_no_module_carries_a_project_key_or_a_record_identifier` (**:503**) | any ≥24-char hex-like literal — "a digest in code is the corpus it was debugged against, pinned in place" |
| `test_no_authored_module_branches_on_a_measured_magnitude` (**:515**) | branching on a number that was *observed* rather than chosen |
| `test_no_authored_module_carries_a_word_list` (**:532**) | vocabularies — "the single most common way a ranking stops being general" |
| `test_fusion_and_diversity_are_purely_relational` (**:725**) | **any string at all** inside fusion/diversity functions |

Registries: `AUTHORED` (**:87**) already contains `ai_case_project`;
`TOUCHED` (**:103**) contains `case_decision`; `MEASURED_MAGNITUDES` (**:158**)
is `{74, 280, 229, 188_000, 229_389}`.

### 10.2 Leakage audit — required per fix, before the fix is called done

**L-1 Registry coverage.** Every module a fix touches must be in `AUTHORED` or
`TOUCHED`. Three gaps found **[D]**, each blocking its own section:

| Module | Needed by | Currently registered? |
|---|---|---|
| `ai_case_intent` | §4 AIS-09 | **No — must be added before §4 lands** |
| `document_ingestion`, `document_extraction` | §5 AIS-03 | **No** |
| `ai_extraction` | §5 AIS-03 | **No** |

A fix that edits an unregistered module is not covered by any of §10.1, so
registration is part of the fix, not a follow-up.

**L-2 Observed magnitudes are banned.** No value read off the six-arm run may
appear in product code — notably the observed rank **10** (AIS-04) and the
observed score **1.914** (AIS-08). Add each to `MEASURED_MAGNITUDES`.

> **Gap to close first:** `test_no_authored_module_branches_on_a_measured_magnitude`
> (**:524**) tests `isinstance(node.value, int)` only **[D]**, so a float such as
> `1.914` would pass unnoticed. Extend the check to floats *before* §2 or §3 lands,
> or the ban is unenforced exactly where these two fixes could violate it.

**L-3 No identifier literals.** No provision key, document id or version id in
code. Already enforced by **:503**; re-run it against every touched module.

**L-4 Relational purity for ranking work.** Any new ranking, fusion or
diversification helper introduced by §3 must be registered in
`RELATIONAL_FUNCTIONS` and therefore proven to carry **no strings at all**. This
is the strongest available guarantee that ranking cannot be steered by what a
document says, and §3 is the fix most at risk of violating it.

**L-5 Threshold provenance.** Every constant a fix adds or changes must be
documented at its declaration as a budget, ceiling, batch size or published
constant — never as "what worked on the matrix". A constant whose justification is
a run result is a corpus fitted into code even when its value looks arbitrary.

**L-6 Question-set independence.** The fix must be explainable without reference
to any AIS question. If the only rationale is "AIS-08 needs 7.4", the fix is
mis-specified: the rationale must be the property (§2.5 INV-08-1/2), and AIS is
only the evidence that the property was violated.

### 10.3 Diverse controls — AIS may not be the only witness

Each fix carries controls drawn from **at least three** of these, none AIS-shaped:

1. **Synthetic fixture** — scores/ranks constructed to exhibit the property, with
   no corpus attached. The primary control; it can exercise cases no corpus has.
2. **Second corpus (HW)** — the same invariant must hold on `hw-policy`, whose
   structure differs sharply (60 provisions, 34 definitions, an exceptions
   appendix) **[D]**. A fix that only holds on AIS is corpus-tuned by definition.
3. **Non-Latin / mixed-script fixture** — the corpus is multilingual and the
   platform already carries mixed-script machinery; a ranking or composition rule
   that silently depends on Latin word shape is not general.
4. **Structural inversion** — the same shape with roles reversed (governing
   provision ranked *first*, sibling second) must not break.
5. **Mutation control** — disable the new gate/check; the fix's own test must then
   fail. If it still passes, the change is not load-bearing.
6. **Recall/precision control** — proves the fix did not become "always widen".
   §2.6 and §3.6 already carry these; they are mandatory, not optional.

**AIS's only role:** the regression witness that the property was violated in
production, and the acceptance evidence in Gate 3. It may never be the sole
control, and no AIS artifact may enter product code.

### 10.4 Per-fix audit obligations

| Fix | L-checks | Minimum diverse controls |
|---|---|---|
| §2 AIS-08 | L-2 (float gap first), L-5, L-6 | synthetic + order-agnostic parametrisation + non-expansion control + recall control + mutation |
| §3 AIS-04 | L-1, L-2, **L-4**, L-5, L-6 | synthetic + HW + structural inversion + recall control + mutation |
| §4 AIS-09 | **L-1 (`ai_case_intent` unregistered)**, L-3, L-6 | synthetic + HW + single-subpart control + mutation |
| §5 AIS-03 | **L-1 (3 modules unregistered)**, L-3, L-6 | synthetic header/row fixture + non-table control + mutation |
| §6 AIS-02 | **L-1 (`ai_case_intent` unregistered)**, L-6, and **no word list** — §6.5 forbids manufacturing a keyword rule, which `test_no_authored_module_carries_a_word_list` would catch anyway | synthetic entitlement/approval fixture + **approval-defined control** + future-obligation + no-invented-missing-fact refusal + HW + mutation |
| §1 P0 rubric | L-6 applied to *criteria*: no criterion may assert a corpus fact without body support | refusal + control pair (§1.4) |

§6 is the fix most exposed to L-6. Its rationale must be stated as *entitlement
does not imply approval* (INV-02-1) — never as "AIS-02 should not say allowed".

### 10.5 Audit evidence to produce

For each fix, before it is called done: the registry diff, the
`MEASURED_MAGNITUDES` diff, the full run of
`test_no_m2_code_is_shaped_around_a_corpus.py`, and a one-line statement of the
general property in terms containing **no** question id, provision key or corpus
name. If that sentence cannot be written without naming AIS, the fix is not
general and must not land.

---

## 11. Execution and progress visibility (binding)

**Binding user rule:** every long test or execution must print **visible
progress**. Use progress reporters, bounded shards, or periodic logged
checkpoints. **No silent long-running commands.**

This governs how §1–§6 and all three gates are *run*, independently of what they
change. A silent command that eventually succeeds still violates it.

### 11.1 What is actually available here — checked, not assumed [D]

`pyproject.toml` sets only `asyncio_mode = "auto"` and `testpaths = ["tests"]`.
**Not installed: `pytest-xdist`, `pytest-timeout`, `pytest-sugar`, `tqdm`** **[D]**.
This corroborates the predecessor's note that `--timeout` is unavailable and fails
the run before any test executes **[I]**. So progress must come from stock pytest
and from this repo's own harness patterns — **do not add a plugin to satisfy this
rule**; a dependency change is out of scope for every section of this blueprint.

### 11.2 Test runs

| Requirement | Mechanism |
|---|---|
| Live per-test progress | stock pytest already emits a per-test progress indicator and a running percentage; **never suppress it** with `-q`/`--quiet` on a long run |
| Named test visibility | `-v` when the run is long enough that percentages alone are not informative |
| Live log output | `--log-cli-level=INFO` (stock pytest, no plugin) |
| Slowest-test visibility | `--durations=25`, so a stalling test is identifiable afterwards |
| **Bounded shards** | select explicit test paths or `-k` expressions and run them as a sequence of bounded, individually-reported runs rather than one opaque whole-suite invocation |
| Fail-fast on a focused gate | `-x` for §-focused runs; **not** for a full regression pass, where the complete picture is the point |

**Sharding is the primary mechanism**, because it is the only one that also bounds
the blast radius of a single run. Per §10, each fix already has a focused test set;
run those as their own shard, report, then widen.

### 11.3 Long harness and matrix runs

Anchor to the patterns this project already uses **[D]/[A]**:

- **Incremental persistence** — the existing harnesses call `persist(results)`
  after every attempt, so a run that dies mid-way still leaves evidence.
- **One line per unit of work** — `paired-20x2.log` writes a single JSON object per
  call (`scenario`, `arm`, `rep`, `latency_ms`, `tokens`, …). That file *is* the
  progress reporter, and it is greppable afterwards.
- **Heartbeat** — the six-arm manifest carries `heartbeat_interval_seconds: 1`
  alongside per-attempt and whole-run timeouts.
- **Suspension awareness** — `suspension_gap_seconds: 10`. A silent run cannot
  distinguish a hung call from a suspended host; a heartbeat can, and the recorded
  20,577,488 ms Modern-Standby call is why this matters **[I]**.

### 11.4 Interaction with the standing constraints

- Backend and both frontend suites must **not** run concurrently — vitest
  worker-startup timeouts here are CPU contention, not assertion failures **[I]**.
  Sharding helps: it keeps each run small enough that contention is visible as a
  slow shard rather than a mysterious timeout.
- Progress output must carry **no policy source text, key or secret**. A progress
  line names the unit of work (`arm`, `question id`, `repetition`, counters), never
  content. This rule does not relax §10 or the secret policy.
- Gate 3's rerun is the longest execution in the plan; it must report per-arm and
  per-repetition progress as it goes, not only a final summary.

### 11.5 Acceptance

No section of this blueprint is complete if its verifying run was executed
silently. Evidence of compliance is the progress artifact itself — the shard
sequence, the per-unit log, or the heartbeat trail — retained beside the result.

---

## 12. Status

Blueprint complete for all **27** true product failures plus the P0 rubric gate.
Final classification: **27 true · 11 rubric errors · 0 unresolved · 0 proven
regressions.**

**No repository file has been created, edited or staged.** Repository verified
unchanged at HEAD `c0972c8bb7ba811903e981d3806afe31cc1f514d`, branch `main`, stash
empty **[D]**.

Ready to implement §1 (artifact-only, no lock needed) and §4/§6/§2 (lock required)
on the parent's word. §3 opens with measurement; §5 additionally needs the
re-extraction authorisation.

### Revision history

| Date | Change |
|---|---|
| 2026-09-04 | Initial blueprint — 26 true, 1 unresolved. |
| 2026-09-04 | §10 benchmark-leakage audit and diverse controls added (binding user invariant). Three coverage gaps recorded. |
| 2026-09-04 | **§6 resolved by parent**: AIS-02 `C-r3` reclassified from *unresolved contract decision* to **true general decision-reasoning failure** under the existing `ai-case-intent-v15` contract. Counts updated to **27 true / 11 rubric / 0 unresolved**; §6 rewritten with INV-02-1…4 and domain-neutral entitlement-vs-approval tests; sequencing, gates and §10.4 updated. |
| 2026-09-05 | **§11 added** — binding execution rule: every long test/execution prints visible progress; no silent long-running commands. Anchored to stock pytest and this repo's existing harness patterns after confirming `pytest-xdist`, `pytest-timeout`, `pytest-sugar` and `tqdm` are **not installed** [D], so no dependency may be added to satisfy it. |
