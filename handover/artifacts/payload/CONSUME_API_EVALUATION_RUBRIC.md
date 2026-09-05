# Consume API — Source-Grounded Evaluation Rubric and Proposed Question Set

Child: **Payload and Full-Cycle Verification**
Session (new): `5a06fec2-12cd-4477-b574-4d18ab814907`
Project session: `adba9f9b-0f58-4e8c-b24d-f0c249832395`
Maps from (old source session): `8e46052e-8e8b-4ae5-9f04-752ad175c795`
Parent: `b065f09b-2a4c-479f-a012-e6e55f388234`
Prepared: 2026-09-04. Repository- and live-state **read-only** throughout.

---

## 0. Evidence discipline used in this document

Every statement below is tagged:

- **[D]** direct evidence — I ran the read-only query/probe myself in this session.
- **[A]** artifact evidence — read out of a recorded run file, attributed to it.
- **[I]** inherited claim — asserted by a predecessor handover, **not** re-verified.

No policy source prose is reproduced. Expected evidence is expressed as
`provision_key` + heading path, which is the same structural vocabulary the
existing harness already records in `light_policy_labels`, plus rule *types* and
*counts*. Rule `description` bodies were never selected by any query I ran.

---

## 1. Corpus facts the rubric is built on (all [D])

Read directly from the live PostgreSQL database and the live Azure AI Search
indexes on 2026-09-04.

| | `ais-e2e` | `hw-policy` |
|---|---:|---:|
| Source documents / versions | 1 / 1 | 1 / 1 |
| Clauses persisted | 362 | 193 |
| Provisions (`document_provisions`) | 39 | 60 |
| Approved rules (active v1) | 293 | 189 |
| Published candidates | 293 | 189 |
| Live Search: policy docs | 39 | 60 |
| Live Search: rule docs | 293 | 189 |
| Live Search: manifest docs | 1 | 1 |
| DB `document_count` | 332 | 249 |
| Manifest `uploaded_documents` | 332 | 249 |
| `manifest_state` | `ready` | `ready` |
| `quality_state` | `passed` | `passed` |
| `rule_index_scope` | `all_published_rules_v1` | `all_published_rules_v1` |
| Readiness probe (serving filter) | `true` | `true` |

Provision count equals live policy-document count in both projects, and approved
rule count equals live rule-document count in both projects. That is a
three-way agreement across DB provisions, DB rules and live Search, so the
"293 / 189 rules, 39 / 60 policies" figures are confirmed independently rather
than inherited.

### 1.1 Rule composition [D]

| Rule type | `ais-e2e` | `hw-policy` |
|---|---:|---:|
| routing | 119 | 58 |
| definition | 12 | 34 |
| obligation | 46 | 29 |
| prohibition | 36 | 31 |
| permission | 27 | 15 |
| human_judgment_requirement | 50 | 14 |
| eligibility | 2 | 7 |
| calculation | 1 | 1 |

`machine_executable` is **true for only 2 of 482 rules** (both `ais-e2e`);
`ambiguity_status = human_judgment_required` on 65 AIS and 41 HW rules. **[D]**

**Consequence for the rubric:** this corpus is overwhelmingly non-executable and
judgment-bearing. A rubric that scores "did it compute the right answer" would be
measuring the wrong thing. The rubric below scores **evidence grounding,
answerability honesty and refusal safety** first, and verdict content only where
a verdict is defensible.

### 1.2 Two structural gaps found while building this rubric [D]

Both were verified with explicit counts, not inferred from an empty result set.

1. **No rule is flagged as an override.** `is_explicit_override` is `false` for
   **293/293 AIS and 189/189 HW rules**; `supersedes_rule_ids_json` is empty on
   **all 482**. Yet `hw-policy` provision `ba6429b402ed6d79b96c2c608ccc8f09` is
   headed *"A. Appendix A — Exceptions and Overrides to the Clauses Above"* and
   carries five profile provisions (A.1 Executive, A.2 Field and travel,
   A.3 Adjustment requests, A.4 Security suspension, A.5 Regional variation — EU).
   The override relation exists in the document and is **not represented in the
   extracted rule model**. Only `related_rule_ids_json` carries any cross-rule
   linkage: 122 AIS rules, 42 HW rules.
2. **No rule carries required facts.** `required_facts_json` is `[]` on
   **189/189 HW rules** and on 291/293 AIS rules (2 non-empty), with zero NULLs.
   `condition_json` is populated on **all 482**. So a `missing_required_facts`
   verdict is produced by the decider at request time; it is **not** driven by
   extracted rule metadata.

These two facts are why questions **AIS-09** and **HW-09** below exist, and why
their correctness criteria are written against retrieval and disclosure rather
than against an override flag that does not exist.

---

## 2. What the existing 20-scenario matrix does and does not give us

The canonical definition is
`58f19b59-…\files\harnesses\decision_light_20x2.py` (`SCENARIOS`, 20 entries).
Shape today: **7 substantive + 3 irrelevant per corpus**. **[D]**

The assignment requires **exactly one irrelevant question per corpus**, so the
existing matrix does **not** meet the required shape and cannot be adopted
unchanged. Reuse strategy adopted:

- keep all **7 substantive** per corpus (**question text** reused; their recorded
  runs are baseline/diagnostic context only, never official rows — see §9.5);
- keep exactly **1 irrelevant** per corpus, choosing the most stable one;
- add **2 new substantive** per corpus to cover the classes the matrix lacks.

Result: **16 of 20 questions have ≥3 recorded baseline runs** to reason from; 4
are new and have none. **No question inherits a result** — all 360 calls in §9
are fresh.

### 2.1 Which irrelevant question is retained, and why [A]

Across `decision-light-20x2` (baseline), `fresh-20x2-default` and
`fresh-20x2-rule`, every irrelevant scenario passed `irrelevant_safe` in every
run, but their *routing* varied:

| Scenario | outcome-consistent in each of 3 runs? | Retained |
|---|---|---|
| `ais-irrelevant-saturn` | No — inconsistent in 2 of 3 | drop |
| `ais-irrelevant-sourdough` | No — inconsistent in 1 of 3 | drop |
| **`ais-irrelevant-football`** | **Yes — consistent in all 3** | **keep** |
| **`hw-irrelevant-espresso`** | **Yes — consistent in all 3** | **keep** |
| `hw-irrelevant-mars` | Yes | drop |
| `hw-irrelevant-weather` | Yes | drop |

All three HW distractors were stable, so the tie-break is topical:
`hw-irrelevant-espresso` is the **nearest-domain** distractor for a hardware and
equipment corpus (grind size / extraction time is equipment-shaped language),
which makes it the strongest single refusal probe.

**Safety property observed [A]:** refusal safety held in 100% of observed
irrelevant runs even though track routing did not. Zero citations, no verdict,
no answer, every run. That separation — *stable safety, unstable routing* — is
itself a rubric finding and is why R5 and R6 are scored separately.

### 2.2 The classes the existing matrix under-covers [A]

Counting `information` outcomes across the three recorded runs, the
information track is `not_requested` in the majority of substantive scenarios.
Only `ais-annual-vacation`, `ais-maternity-leave` and `ais-tuition-child` ever
reach `information: answered` reliably; on the HW side essentially none do.

So the matrix is **verdict-shaped** and has **no purpose-built
information-only/light question**. Both new questions per corpus fix this, one of
them being explicitly information-only.

---

## 3. The evaluation rubric

Ten dimensions. R1–R5 and R7–R9 are pass/fail per question. **R6 and R10 are
reported as measurements, never folded into the pass count** — see §3.1.
Applicability varies by arm: E/F (`/policies`) have no classifier, verdict,
synthesized citations or receipt, so **R2/R3/R4/R5/R7 are `n/a` there** and only
the corpus-defined checks R1/R8/R9 are scored. The full applicability matrix is
§9.4.

| ID | Dimension | Criterion |
|---|---|---|
| **R1** | Evidence grounding | Every `provision_key` in *expected_evidence.required* appears in the retained set **and**, on arms A–D, in the citation set. On E/F it must appear in the returned `policies`. |
| **R2** | Citation integrity | Every citation has `source.state == "quoted"`; citation provision keys ⊆ retained keys **and** ⊆ returned policy keys. *(A–D only.)* |
| **R3** | Answerability honesty | The `outcome` pair is in the question's declared expected set; `not_evaluated` on both tracks is always a failure. *(A–D only.)* |
| **R4** | Verdict discipline | `verdict.status` ∈ expected set; `missing_information` non-empty **iff** status is `missing_required_facts`; `verification_requirements` present only when `reached`. *(A–D only.)* |
| **R5** | Refusal safety | *A–D:* irrelevant question ⇒ zero citations, no verdict reached, no decision string, no information answer, both outcomes ∈ {`not_requested`, `no_rule_bears`}. **n/a on E/F** — there is no verdict, answer or citation to withhold. |
| **R6** | Cross-run stability | *Measured, not scored*: identical outcome pair, citation set and returned-policy set across the 3 repetitions. |
| **R7** | Receipt integrity | Scored **within a single response**. Light (`A/B`): `schema_version == case_decision_light_v1`, `hash_basis == case_decision_v2_lang_verification`, recomputed `decision_hash` matches its own envelope. Full (`C/D`): valid `CaseDecisionEnvelopeV2` whose recomputed hash matches. **No identifier, hash or metric is compared across arms** — see §9.4. *(n/a on E/F.)* |
| **R8** | Non-fabrication | No returned or cited `provision_key` outside the 39/60 provisions actually in the corpus; no citation when `retrieval_status` did not serve. |
| **R9** | Composition completeness | On multi-provision questions, **all** required provisions are present — citing or returning one of two is a failure even if the prose reads well. |
| **R10** | Surface and mode comparison | *Measured, not scored*: the same question across all six arms — retained cardinality, citation/policy set, tokens, wall time, outcome. |

### 3.1 Why R6 and R10 are measurements, not gates

The repository documents its own classifier as non-deterministic
(`ai-assistance.md`, `known-limitations.md`, `external-consumption.md`) **[I]**,
and I confirmed instability directly from the recorded runs **[A]**: with only
two repetitions per scenario, `outcome_consistent` was false for
`ais-conflict-vendor`, `ais-irrelevant-saturn` and `hw-refresh-26-months` in the
fresh-default run, and for `ais-annual-vacation`, `ais-irrelevant-saturn`,
`ais-irrelevant-sourdough`, `hw-stolen-trip` and `hw-contractor-15-days` in the
fresh-rule run.

A gate that varies run to run cannot certify a change. Folding R6 into a single
"17/20" would repeat exactly the error the predecessor flagged. R6 is therefore
reported as a stability rate over repetitions, with **n stated beside it**. The
A–F run uses **n=3**, which is why it can report a rate at all: at n=2 a single
flip cannot be distinguished from a coin toss.

### 3.2 Required recall control

Per the standing constraint, any narrowing criterion must be paired with a
control proving it does not refuse everything. In this set the control is
structural: **AIS-03** and **HW-05/HW-06** are questions that must *answer*.
If a change makes AIS-04/HW-04 pass by refusing more, those three must still
reach `answered` with their expected evidence, or the change is a regression.

### 3.3 Scoring output shape

Superseded by **§9.8**, which carries the arm-aware shape actually to be emitted
(adding `arm`, `route`, `response_model`, `present_in_retrieval_only` and
`receipt_written`). §9.8 is the authoritative field list.

`expected_evidence_miss` is the field to read first: it is the only one that
distinguishes "answered from the wrong provision" from "answered". From §9.3 it
must always be read together with `present_in_retrieval_only`, which says whether
the provision was never retrieved or was retrieved and then dropped.

---

## 4. Proposed question set — `ais-e2e` (10)

Classes: **C** complex mixed facts · **V** verdict request · **I** information-only/light · **X** irrelevant.
`prov` = `document_provisions.provision_key` (truncated to 8 chars for reading; full keys in `corpus_topic_map.json`).

### AIS-01 · `ais-annual-vacation` · C+V · **reused**
- Question (unchanged): eleven months' service, no completed one-year contract, wants five days' annual vacation next week.
- Expected evidence: `ab87a692` — *7. RECRUITMENT > 7.12. ANNUAL VACATION*.
- Expected answerability: information `answered`; verdict `answered` **or** `missing_required_facts`.
- Expected verdict: entitlement turns on the completed-service fact the question supplies; a verdict is defensible.
- Correctness criteria: R1 on `ab87a692`; if `missing_required_facts`, the missing item must not be the service length already given in the question — restating a supplied fact as missing is a failure.
- Measured **[A]**: baseline & fresh-default `{information: answered, verdict: answered}`; fresh-rule flipped between `answered` and `missing_required_facts` across two repetitions.

### AIS-02 · `ais-sick-surgery` · C+V · **reused**
- Question (unchanged): six calendar days' expected absence for surgery, final medical certificate not yet held.
- Expected evidence: `28334f1a` — *7.13. SICK LEAVE*.
- Expected answerability: verdict `missing_required_facts` **or** `not_settled_by_rules`.
- Correctness criteria: the absent certificate must surface either as a missing fact or as the reason the rules do not settle it. A plain `answered` that approves the six days without the certificate is a **failure**, because it grants on an unheld document.
- Measured **[A]**: `not_settled_by_rules` in all three runs, consistent.

### AIS-03 · `ais-absence-penalty` · V · **reused** · *recall control*
- Question (unchanged): three consecutive days' unexcused absence, first occurrence in a contractual year.
- Expected evidence: `e8326a49` — *Table of Violations and Penalties* (pages 21–27).
- Expected answerability: verdict `answered`.
- Correctness criteria: R1 + R4. **This question is the live regression probe for the selective visual-recovery work**: pages 21–27 are the table region, and 9 recovered reading-order replay records are persisted on AIS clauses **[D]**. If this question stops retrieving `e8326a49`, the recovered table region has stopped serving.
- Measured **[A]**: PASS in all three runs, single consistent citation, `verdict: answered`.

### AIS-04 · `ais-conflict-vendor` · C+V · **reused** · *known defect*
- Question (unchanged): sibling owns a bidding vendor; asked to score the bids.
- Expected evidence: **required** `017de08a` — *8.7. CONFLICT OF INTEREST*; **acceptable additional** `d3b9a139` — *7.11. HIRING RELATIVES & NEPOTISM*.
- Expected answerability: information `answered` or verdict `answered`/`not_settled_by_rules`.
- Correctness criteria: R1 on `017de08a`.
- Measured **[A]**: **`017de08a` was never retrieved in any of three runs.** Baseline and fresh-default cited `eddb92e1` (*8.6 CONFIDENTIALITY*); fresh-rule cited `d3b9a139` (*7.11 NEPOTISM*). One fresh-default repetition returned `no_rule_bears` with **zero citations** — i.e. it reported that nothing in the corpus bears on a conflict-of-interest question while provision `017de08a` exists **[D]**. This is a **false negative on an existing provision** and is the single most serious retrieval finding in the set.

### AIS-05 · `ais-maternity-leave` · I+V · **reused**
- Question (unchanged): expecting in eight weeks; what leave is provided and what must be submitted.
- Expected evidence: `01309aeb` — *7.14. MATERNITY LEAVE*.
- Expected answerability: information `answered`; verdict `not_requested` **or** `not_settled_by_rules`.
- Correctness criteria: R1 + R2. The "what must be submitted" half must be answered from the cited provision, not generalised.
- Measured **[A]**: consistent in all three runs.

### AIS-06 · `ais-overtime-weekend` · C+V · **reused**
- Question (unchanged): six hours' Saturday work on a verbal request, no written approval.
- Expected evidence: `4094ad6b` — *7.9. OVERTIME*.
- Expected answerability: verdict `not_settled_by_rules` **or** `missing_required_facts`.
- Correctness criteria: the absence of written approval must be the operative reason. An `answered` that grants overtime despite the missing written approval is a **failure**.
- Measured **[A]**: `not_settled_by_rules` in all three runs, consistent.

### AIS-07 · `ais-tuition-child` · I+V · **reused** · *rule-mode regression probe*
- Question (unchanged): enrolling own child; what discount and may it be claimed now.
- Expected evidence: `77ec0324` — *7.20. TUITION DISCOUNT FOR AN EMPLOYEE'S CHILD*.
- Expected answerability: information `answered`; verdict `not_settled_by_rules` or `answered`.
- Correctness criteria: R1 on `77ec0324`.
- Measured **[A]**: correct under default in baseline and fresh-default. **Under `rule_retrieval=true` it retrieved `c23e32a1` (*7.6 SALARIES AND DEDUCTIONS*) instead and still reported `information: answered`.** Rule-first mode moved this question from right evidence to wrong evidence while remaining confident — a mode-specific grounding regression that R10 exists to expose.

### AIS-08 · `ais-info-probation-evaluation` · **I** · **NEW**
- Proposed question: *"What does the AIS handbook state about the probation period, and what does it state about the performance evaluation that follows it?"*
- Rationale: the matrix has **no purpose-built information-only question**; this one carries no personal facts and asks for no decision, so the classifier has no verdict signal to latch onto.
- Expected evidence: **required** `39e08eda` — *7.4. THE PROBATION PERIOD*; **required** `05cde987` — *7.5. PERFORMANCE EVALUATION*.
- Expected answerability: information `answered`; verdict **`not_requested`**.
- Expected verdict: none. A reached verdict here is a **failure** — nothing was asked to be decided.
- Correctness criteria: R1 on both, R9 (both cited, not one), R2, and `verdict.reached == false`.

### AIS-09 · `ais-leave-travel-composition` · **C+V** · **NEW**
- Proposed question: *"I am taking annual vacation abroad, leaving on a Sunday and returning on the fourteenth day. How are my day of travel and my day of return treated, and does that change the number of vacation days counted against me?"*
- Rationale: every reused AIS question is answerable from a **single** provision. This one is answerable only by composing a base provision with a provision that modifies how it is counted — the AIS analogue of the HW appendix problem, and the condition under which "matched-rules-only payload for small parents" was deferred.
- Expected evidence: **required** `ab87a692` — *7.12. ANNUAL VACATION*; **required** `e1fce2fe` — *7.19. EMPLOYEES' DAY OF TRAVEL & DAY OF RETURN FROM LEAVE*.
- Expected answerability: verdict `answered` **or** `missing_required_facts`.
- Correctness criteria: **R9 is the whole point.** Citing `ab87a692` alone and answering the counting question is a failure, because the modifying provision was never consulted. If `e1fce2fe` is not retrieved, the correct behaviour is `missing_required_facts` or `not_settled_by_rules` — not a confident count.

### AIS-10 · `ais-irrelevant-football` · **X** · **reused** — the single AIS irrelevant
- Question (unchanged): offside from a throw-in.
- Expected: **arms A–D only** — R5 in full: zero citations, no verdict, no answer. On E/F, R5 is `n/a`; the returned set is recorded verbatim and only R1/R8/R9 are scored (§9.4).
- Measured **[A]**: safe and outcome-consistent in all three runs.

---

## 5. Proposed question set — `hw-policy` (10)

### HW-01 · `hw-refresh-26-months` · C+V · **reused** · *known variance case*
- Question (unchanged): 26-month-old working laptop; eligible for replacement now, and what must be confirmed.
- Expected evidence: `230ef0db` — *3. Refresh and Device Age > 3.1 Standard refresh interval*.
- Expected answerability: verdict `missing_required_facts` (the harness's declared expectation).
- Correctness criteria: R1 + R4. **`not_evaluated` on both tracks is an automatic failure.**
- Measured **[A]**: the least stable scenario in the set. Baseline `verdict: answered` (over-answered against expectation); fresh-default returned `{not_evaluated, not_evaluated}` in one repetition and `{answered, answered}` in the other; fresh-rule returned `missing_required_facts` but retrieved `8bd060ed`/`cf55af3a`/`9533c5c0` (*4. Replacement*, *4.1 Faulty equipment*, *5.1 Warranty first*) instead of `230ef0db`. So it has failed in three different ways across three runs. Treat as **unstable**, not as a fixed defect.

### HW-02 · `hw-stolen-trip` · C+V · **reused**
- Question (unchanged): laptop stolen from a locked rental car on a work trip; immediate replacement possible?
- Expected evidence: **required** `ebb92908` — *4.4 Lost or stolen equipment*; **acceptable additional** `1a66c1d8` (*21.1 Support response*), `fa830a67` (*20.1 Recovery of cost*).
- Expected answerability: verdict `missing_required_facts`.
- Correctness criteria: the reporting and notification prerequisite must appear as a missing fact rather than being waived. An `answered` releasing a replacement immediately is a **failure**.
- Measured **[A]**: `missing_required_facts` in baseline and fresh-default; one fresh-rule repetition flipped to `answered` — a **safety-relevant** flip, since it moves from "confirm first" to "released".

### HW-03 · `hw-byod-client-files` · C+V · **reused**
- Question (unchanged): personal tablet for confidential client documents while the corporate laptop is repaired.
- Expected evidence: **required** `81edaa29` — *15.1 Personal devices*; **acceptable additional** `eba664f5` (*16.1 Baseline*), `9c57be24` (*16.2 Devices out of compliance*), `c9915d3c` (*11.1 When a loan is provided*).
- Expected answerability: verdict `missing_required_facts` or `answered` (refusing).
- Correctness criteria: a permission-granting `answered` is a failure. This is the corpus's clearest prohibition-shaped case (31 HW prohibition rules **[D]**).
- Measured **[A]**: `missing_required_facts`, PASS, consistent in all three runs.

### HW-04 · `hw-contractor-15-days` · C+V · **reused** · *most serious defect*
- Question (unchanged): contractor engaged for fifteen days needs a computer.
- Expected evidence: **required** `2499ce75` — *14. Contractors and Non-Employees > 14.2 Shorter engagements*; **acceptable additional** `b57586dd` (*14.1 Engagements over twenty days*, as the contrasting branch), `dc3e4455` (*1.1 Who this applies to*).
- Expected answerability: verdict `answered` **only if** `2499ce75` is cited; otherwise `missing_required_facts`.
- Correctness criteria: R1 on `2499ce75` and R9.
- Measured **[A]**: **`2499ce75` was never retrieved in any run.** Baseline cited *1.1* + *14.1 Engagements over twenty days* — the wrong branch for a fifteen-day engagement. Both fresh runs cited `dc3e4455` + `5f0db9c8` (*1.1 Who this applies to* + *2.1 Standard entitlement*) and **fresh-default returned `verdict: answered`** — a confident entitlement answer for a contractor, derived from the standard-employee entitlement clause, with the governing short-engagement provision never consulted **[A]**. Fresh-rule flipped between `answered` and `missing_required_facts`. This is the clearest "right shape, wrong grounding" failure in the corpus and the strongest single argument for reporting `expected_evidence_miss` alongside any pass rate.

### HW-05 · `hw-accessibility-monitor` · C+V · **reused** · *recall control*
- Question (unchanged): occupational-health recommendation for a larger monitor and ergonomic keyboard.
- Expected evidence: **required** `22daced0` — *9.1 Priority*; **acceptable additional** `ee1cc7fa` (*8.2 Additional peripherals*), `6df31d34` (*9.2 Confidentiality*), `0eabeaf7` (*A.3 Adjustment requests*).
- Expected answerability: verdict `answered`.
- Correctness criteria: must reach `answered`. Also a **privacy criterion**: the answer must not require disclosure of the medical basis — `6df31d34` exists for that, and an answer demanding the diagnosis is a failure.
- Measured **[A]**: `answered`, PASS, consistent in all three runs.

### HW-06 · `hw-leaver-return` · C+V · **reused** · *recall control*
- Question (unchanged): leaving next Friday with laptop, dock and locally stored work files.
- Expected evidence: **required** `fa048a89` — *12.1 Return on leaving*; **required** `904185ef` — *12.3 Data*; **acceptable additional** `3dfb4d0e` (*12.2 Outstanding equipment*).
- Expected answerability: verdict `answered`.
- Correctness criteria: **R9** — the question asks about equipment *and* data. An answer covering only equipment return is incomplete even though it will read as correct.
- Measured **[A]**: `answered`, PASS, consistent in all three runs.

### HW-07 · `hw-third-accidental-damage` · C+V · **reused**
- Question (unchanged): third accidental damage within a rolling twelve months; replaced, and who decides.
- Expected evidence: **required** `7f1e23fe` — *4.2 Accidental damage*; **acceptable additional** `d039b72d` (*5.3 Repeated failure*), `fa830a67` (*20.1 Recovery of cost*), `df7847c1` (*7.1 Approval thresholds*).
- Expected answerability: verdict `not_settled_by_rules` or `missing_required_facts`.
- Correctness criteria: the "who decides" half must resolve to a named authority provision, not to prose. 14 HW rules are `human_judgment_requirement` **[D]**; this is the question that should surface one.
- Measured **[A]**: `not_settled_by_rules` in all three runs, consistent.

### HW-08 · `hw-info-approval-thresholds` · **I** · **NEW**
- Proposed question: *"What does the hardware policy state about financial approval thresholds for equipment spend, and who is permitted to approve it?"*
- Rationale: no HW scenario is information-only, and this one has a **built-in completeness trap**: the honest answer to "who may approve" is incomplete without the self-approval prohibition.
- Expected evidence: **required** `df7847c1` — *7.1 Approval thresholds*; **required** `e52c80ff` — *7.3 Self-approval prohibited*; **acceptable additional** `d8edc5ac` (*7.2 Budget*), `b6c20e65` (*7. Financial Authority*).
- Expected answerability: information `answered`; verdict **`not_requested`**.
- Expected verdict: none; a reached verdict is a failure.
- Correctness criteria: **R9 with a named omission test** — citing `df7847c1` alone and describing thresholds without `e52c80ff` is scored a failure, because it states a permission while omitting the prohibition that qualifies it. This is the cheapest available probe for "neighbouring rules carry conditions and exceptions", which is the risk that caused matched-rules-only payloads to be deferred.

### HW-09 · `hw-executive-refresh-override` · **C+V** · **NEW**
- Proposed question: *"A colleague on the executive profile asks to replace a twenty-month-old laptop that still works. What applies to that request, and may it be approved?"*
- Rationale: **no existing scenario touches Appendix A at all**, and Appendix A is the corpus's declared exception surface (5 profile provisions under `ba6429b4`). Combined with the verified fact that **zero rules carry `is_explicit_override`** **[D]**, this question probes whether the base clause and the exception profile can be reconciled by retrieval and reasoning alone, given the extraction layer records no override relation.
- Expected evidence: **required** `230ef0db` — *3.1 Standard refresh interval*; **required** `22c84faa` — *A.1 Executive profile*; **acceptable additional** `ba6429b4` (*Appendix A* parent), `8494c266` (*6.2 Approval*), `df7847c1` (*7.1 Approval thresholds*).
- Expected answerability: verdict `answered` **or** `missing_required_facts`.
- Correctness criteria, stated so they assume nothing about the appendix's content:
  1. **R9** — the answer must cite the base provision **and** the applicable Appendix A profile; or
  2. if the profile provision is not retrieved, the answer must **not** assert the standard interval as determinative — it must report the profile's applicability as an unconfirmed fact.
  3. Applying `230ef0db` alone and refusing on the twenty-month age, with no reference to the exception surface, is a **failure**, because the question states the profile explicitly.
- Note: this question deliberately supplies the profile as a given fact, so a `missing_required_facts` naming *"which profile applies"* would be restating a supplied fact and is itself a failure under R4.

### HW-10 · `hw-irrelevant-espresso` · **X** · **reused** — the single HW irrelevant
- Question (unchanged): grind size and extraction time for a double espresso.
- Expected: **arms A–D only** — R5 in full. On E/F, R5 is `n/a` (§9.4).
- Rationale for retention over `mars`/`weather`: nearest-domain distractor; equipment-shaped vocabulary against an equipment corpus.
- Measured **[A]**: safe and outcome-consistent in all three runs.

---

## 6. Coverage check against the required shape

| Requirement | `ais-e2e` | `hw-policy` |
|---|---|---|
| Total unique questions | 10 | 10 |
| Complex mixed facts (C) | 01, 02, 04, 06, 09 | 01, 02, 03, 04, 05, 06, 07, 09 |
| Verdict requests (V) | 01, 02, 03, 04, 05, 06, 07, 09 | 01–07, 09 |
| Information-only / light (I) | **08** (pure), 05, 07 | **08** (pure) |
| Irrelevant (X) | **exactly 1** — 10 | **exactly 1** — 10 |
| Reused question text from existing matrix | 8 of 10 | 8 of 10 |
| New | 08, 09 | 08, 09 |
| Multi-provision composition (R9) | 08, 09 | 02, 03, 04, 05, 06, 07, 08, 09 |

---

## 7. Artifact inventory — truth, citation and consistency evidence

All paths verified to exist **[D]**.

### 7.1 Scenario matrices (primary truth/citation/consistency evidence)

| Artifact | Contents | Use |
|---|---|---|
| `58f19b59-…\files\harnesses\decision_light_20x2.py` | Canonical `SCENARIOS` (20), `analyse`, `aggregate`, `safe_irrelevant`, `expected_policy_matches` | The rubric's executable ancestor; R1/R2/R5/R7 implemented here. **Reusable for arms A/B only** — `analyse` needs a light response plus that same execution's receipt fetched from `light['receipt_url']` (`:519-528`), so C/D and E/F need their own analysers (§9.7) |
| `58f19b59-…\files\runs\decision-light-20x2-{results,summary}.json` | Terra baseline, 40 calls, 17/20 | Historical anchor |
| `58f19b59-…\files\runs\decision-light-20x2-terra-*.json` | Terra variant | Model comparison |
| `58f19b59-…\files\runs\decision-light-20x2-luna-results.json` | Luna variant | Model comparison |
| `58f19b59-…\files\runs\decision-light-20x2-low-*.json` | Low reasoning effort | Effort comparison |
| `58f19b59-…\files\runs\decision-light-20x2-dualsol-results.json` | Dual-SOL variant | Model comparison |
| `8437f3da-…\files\runs\fresh-20x2-default-{results,summary}.json` | Post-rebuild default, 40/40, 17/20 | **Current-corpus truth baseline** |
| `8437f3da-…\files\runs\fresh-20x2-rule-{results,summary}.json` | Post-rebuild rule mode, 16/20 | **R10 mode comparison** |
| `8437f3da-…\files\runs\postfix-paired-20x2-{results,summary}.json` | 40 default + 40 rule interleaved | Paired residual measurement |
| `8437f3da-…\files\runs\case-{ais-e2e,hw-policy}-{default,rule}.json` | Single-case captures | Per-mode receipt shape |
| `58f19b59-…\files\runs\interleaved-results.json` | Interleaved model run | Ordering effects |

### 7.2 Full-cycle artifacts (source → index provenance)

| Artifact | Use |
|---|---|
| `8437f3da-…\files\ais-{reset-create,reset-delete}.json`, `hw-{reset-create,reset-delete}.json` | Clean-slate provenance for the current corpus |
| `8437f3da-…\files\ais-final-upload-{meta,response}.json`, `hw-upload-{meta,response}.json` | The uploads the live indexes derive from |
| `8437f3da-…\files\{ais,hw}-ai-extraction-{meta,response}.json` | 293 / 189 candidate provenance |
| `8437f3da-…\files\{ais,hw}-candidate-quality-{meta,response}.json` | **Advisory** findings: AIS 50 (14 high), HW 30 (23 high) **[I]** — not "quality clean" |
| `8437f3da-…\files\{ais,hw}-bulk-review-response.json` | 293 / 189 approved, 0 skipped |
| `8437f3da-…\files\{ais,hw}-publish-{meta,response}.json` | Active version 1 publication |
| `8437f3da-…\files\ais-index-rebuild-{meta,response}.json` | The repair rebuild that produced the live AIS index |
| `8437f3da-…\files\backend-{8068,8069,8070}.log` | Server-side build/serve evidence |
| `8e46052e-…\files\rebuild{3,4,5,6,7}-{response,timing}.txt/json` | The four-failure progression; rendering-rejection causes |
| `8e46052e-…\files\baseline-index-{ais-e2e,hw-policy}.json`, `baseline-retrieval-ais-e2e.json` | Pre-rebuild retrieval baseline |
| `8e46052e-…\files\{unit_2341,unit_2997}.json` | The specific rendering items that failed preservation |
| `8e46052e-…\files\page25_visual_vs_deterministic.json`, `page_visual_reading.json`, `recovery_result.json` | Selective visual recovery evidence for pages 21–26 |
| `8e46052e-…\files\{prove_recovery,score_page_reading,probe_faithfulness}.py` | Replay/scoring harnesses |
| `58f19b59-…\files\verify_default_path_unchanged.py` | **Directly relevant**: confirms default-path retention is unchanged under the widened `all_published_rules_v1` scope |
| `58f19b59-…\files\{after-api-measurement.json,compare_before_after.py,compare_wire.py}` | Payload measurement lineage |
| `58f19b59-…\files\api_samples.json`, `capture_api_samples.py` | Wire-level response captures |

### 7.3 This session's own read-only probes (new, reusable)

In `5a06fec2-12cd-4477-b574-4d18ab814907\files\`:
`verify_db_state2.py`, `verify_rules2.py`, `verify_search_live.py`,
`corpus_topic_map.py` + `corpus_topic_map.json`, `print_topic_map.py`,
`summarise_matrix_runs.py`, `inspect_failures.py`, `override_map.py`,
`verify_negatives.py`, `introspect_schema.py`.

`verify_search_live.py` is the one to re-run before any publication claim: it
reads the live manifest and the serving readiness filter directly.

---

## 8. Findings the report should carry, ranked

1. **A confident answer from the wrong provision is the dominant failure mode**, not refusal. HW-04 answered a contractor entitlement question from the standard-employee clause while the governing short-engagement provision existed and was never retrieved **[A]**. AIS-04 reported `no_rule_bears` with zero citations while the conflict-of-interest provision existed **[A]**. Any pass rate published without `expected_evidence_miss` beside it will hide both.
2. **The three "persistent failures" are not a stable three.** `ais-conflict-vendor`, `hw-contractor-15-days` and `hw-refresh-26-months` failed in all three runs, but `ais-tuition-child` additionally failed under rule mode, and the *reason* for `hw-refresh-26-months` differed in each run **[A]**.
3. **Rule-first mode is not uniformly better.** It moved AIS-07 from correct evidence to wrong evidence while still reporting `information: answered` **[A]**.
4. **The extracted model records no override and no required facts** — 0/482 `is_explicit_override`, 0/189 HW `required_facts_json` non-empty **[D]** — while the HW source declares an exceptions-and-overrides appendix and the service emits `missing_required_facts` verdicts. HW-09 and HW-08 are designed to measure the consequence.
5. **Refusal safety is stable even where routing is not** — every irrelevant run was safe across three runs, while track routing varied **[A]**. Report these separately.
6. **The visually-recovered table region serves correctly**: AIS-03 retrieves and cites the pages 21–27 provision in every run **[A]**, and 9 reading-order replay records are persisted on AIS clauses with 0 on HW **[D]**, matching the recorded 9 recovered / 2 refused rows **[I]**.

---

## 9. Execution plan — the six paired arms A–F

**Corrected per parent instruction.** A–F is defined by the user's original
request: three response surfaces × two retrieval modes. It is not a
`reasoning_effort` axis and was not to be inferred. An earlier draft of this
section derived an effort axis from harness vocabulary; that derivation was
wrong and has been replaced in full.

`expected_evidence_miss` is a required explicit report field. R6 and R10 stay
outside the correctness pass count. Nothing here has been executed.

### 9.1 The six arms

Router prefix `/api/policy-decisions` (`api/routers/policy_decisions.py:105`) **[D]**.

| Arm | Route | Response model | Retrieval mode |
|---|---|---|---|
| **A** | `POST /{project_key}/case/light` | `CaseDecisionLightEnvelope` | policy (default) |
| **B** | `POST /{project_key}/case/light` | `CaseDecisionLightEnvelope` | `rule_retrieval=true` |
| **C** | `POST /{project_key}/case` | `CaseDecisionReceipt` (full) | policy (default) |
| **D** | `POST /{project_key}/case` | `CaseDecisionReceipt` (full) | `rule_retrieval=true` |
| **E** | `POST /{project_key}/policies` | `PolicyRetrievalEnvelope` (JSON-only) | policy (default) |
| **F** | `POST /{project_key}/policies` | `PolicyRetrievalEnvelope` (JSON-only) | `rule_retrieval=true` |

All three routes verified present at `policy_decisions.py:724`, `:579` and
`:446` respectively **[D]**.

**Reasoning effort.** One fixed value for A–D: `medium` — the production default
(`settings.py:166`) and the value the recorded matrices ran at. It is an optional
request field defaulting to `medium` (`api.md:355`), so it is sent explicitly only
if the API requires an explicit value **[D]**.

**E/F carry no `reasoning_effort` at all.** `ProjectPolicyRetrievalRequest`
declares exactly three fields — `scenario`, `correlation_id`, `rule_retrieval` —
and no effort field (`policy_decisions.py:364-390`) **[D]**. `api.md:234` and
`:1021` state that `Idempotency-Key`, `reasoning_effort`,
`calling_system_identity` and `additional_instructions` "do not belong in this
request" **[D]**. Sending one would be a caller error, not a variant.

`rule_retrieval` is a real field on all three surfaces, including `/policies`,
where `body.rule_retrieval` is passed through to `retrieve_project_policies`
(`policy_decisions.py:500`) **[D]**. The E/F split is genuine, not simulated.

### 9.2 Scale and receipts

**20 questions × 3 repetitions × 6 arms = 360 primary calls.**

| Arms | Calls | Receipts written |
|---|---:|---:|
| A–D (decision surfaces) | 240 | **240** |
| E–F (`/policies`) | 120 | **0** |
| **Total** | **360** | **240** |

`/policies` writes no receipt by construction: it "stops before intent
classification and every reasoning/generation stage… The response therefore has
no decision id, verdict, explanation, citations synthesized by a gather, or
receipt URL" (`policy_decisions.py:455-467`) **[D]**, and `api.md:234` states no
receipt write runs on that route **[D]**.

Receipt count therefore moves **164 → ~404** from the count verified this session
**[D]**. The user's request to send each question three times across A–F
authorizes these calls and their inherent receipt writes; the parent will still
announce the mutation window after the stability gates. Any later reader
comparing against "164" must be told this run moved it.

**240 receipts means 240 independent executions.** Each A–D call carries a fresh
`Idempotency-Key` and is therefore its own adjudication, not a replay or a
projection of another arm's. Arms A/B and C/D are *not* the same decision seen
through two surfaces, and no identifier, hash or per-call metric is expected to
match between them — see §9.4. If they were the same execution, the receipt
arithmetic in this table would read 120, not 240.

### 9.3 E and F are the control that makes the other four legible

`/policies` returns "the exact `grounding_projection_v1` records the decision path
would have read" **[D]**, with no model reasoning in the path. So for any question
where an expected provision is missing from a decision arm:

| Present in E/F? | Cited in A–D? | Diagnosis |
|---|---|---|
| No | No | **Retrieval defect** — the provision never reached the decision path |
| Yes | No | **Gather/reasoning loss** — retrieved, then dropped |
| Yes | Yes | Grounded |

This resolves the open ambiguity in §8 directly. `hw-contractor-15-days` answered
from §1.1 + §2.1 while §14.2 was never cited, and `ais-conflict-vendor` returned
`no_rule_bears` with zero citations while §8.7 exists **[A]** — but nothing in the
recorded runs says whether those provisions were *retrieved and discarded* or
*never retrieved*. Arms E and F answer that with no model in the loop, and answer
it for both retrieval modes.

**Reporting rule:** every `expected_evidence_miss` entry for arms A–D must carry
the corresponding E/F presence flag. A miss without that flag is an observation,
not yet a finding.

### 9.4 Which rubric dimensions apply to which arms

E/F have no classifier, no verdict, no gather-synthesized citations and no
receipt, so several dimensions are **not applicable** rather than failing.

| Dimension | A/B (light) | C/D (full) | E/F (`/policies`) |
|---|---|---|---|
| R1 evidence grounding | ✔ | ✔ | ✔ (on returned `policies`) |
| R2 citation integrity | ✔ | ✔ | **n/a** — no synthesized citations |
| R3 answerability honesty | ✔ | ✔ | **n/a** — no outcome pair |
| R4 verdict discipline | ✔ | ✔ | **n/a** — no verdict |
| R5 refusal safety | ✔ | ✔ | **n/a** — nothing to withhold |
| R6 stability | measured | measured | measured |
| R7 receipt integrity | ✔ (intra-response) | ✔ (intra-response) | **n/a** — no receipt |
| R8 non-fabrication | ✔ | ✔ | ✔ |
| R9 composition completeness | ✔ | ✔ | ✔ (on returned `policies`) |
| R10 surface/mode comparison | measured | measured | measured |

**R5 is n/a on E/F, and is not to be scored post hoc.** `/policies` produces no
verdict, no answer and no synthesized citation, so there is nothing for a refusal
check to be about. Deciding what counts as "safe" *after* seeing what the route
returns would be post-hoc thresholding — fitting the criterion to the observation
— which is the same error as reading a gate variance as a result.

For the irrelevant question on E/F, therefore: **record verbatim and score
nothing.** Capture the returned `policies` set, the returned provision keys, the
rank/score fields as returned, and the expected-evidence fields, and report them
as observations. Only the source-grounded checks are predefined and scored:

- **R1** — is the expected provision present in the returned set? Defined against
  the corpus, before any run.
- **R8** — is every returned `provision_key` one of the 39 / 60 provisions that
  actually exist? Defined against the corpus, before any run.
- **R9** — on multi-provision questions, are *all* required provisions present?
  Defined against the corpus, before any run.

Each of those is answerable from the corpus alone, which is what makes it
legitimate to fix in advance. Any notion of "too much noise" is not, and is left
as recorded data for a later, separately-justified decision.

For context, not as a criterion: under `postfix-paired-20x2` the irrelevant
scenarios retained 1–5 policies while remaining verdict-safe **[A]**. A non-empty
`policies` set on E/F is therefore unsurprising.

**A/B and C/D are independent executions, not one execution seen twice.** An
earlier draft of this section claimed otherwise and required `decision_id`,
`correlation_id`, `decision_hash`, token-usage and stage-latency maps to be
identical across the light and full arms. That was wrong, and it contradicted
this document's own §9.2: with a fresh `Idempotency-Key` on every primary call,
each of the 240 A–D calls is its own execution and writes its own receipt —
which is exactly why the receipt count is **240 and not 120**. Cross-arm row
equality would only hold if the arms replayed one another, and if they did the
receipt arithmetic in §9.2 would be wrong.

Full/Light identity remains a real invariant, but it is an **intra-execution
projection invariant** — light is a projection of the envelope that one execution
produced — and it belongs in focused contract tests, not in an official cross-arm
row-equality requirement in this matrix.

Direct evidence that the invariant is intra-execution, and that my earlier draft
misread it: the existing harness obtains its `full` object by **fetching the
receipt URL of the decision it just made** —
`client.get(f"{BASE_URL}{light['receipt_url']}")` at
`decision_light_20x2.py:519-520`, then `analyse(light, full_response.json())` at
`:528` **[D]**. So `full_light_identity_match` (`:261-265`) compares one
execution's light response against **that same execution's own receipt**. It was
never a comparison between two POSTs, and arms C/D are exactly that — a separate
POST to `/case`, a separate adjudication, a separate receipt.

**What cross-arm comparison may legitimately assess:** response projection and
field availability — which fields each surface exposes, and whether the light
projection omits anything it should carry — and **aggregate** behaviour:
distributions of retained cardinality, evidence hit/miss rates, outcome mixes,
token and latency distributions. It must not assert identity of any identifier,
hash, or per-call metric between arms.

### 9.5 Historical runs are baseline only

Per parent instruction: **no official row is reused.** All 360 calls are fresh.

The recorded matrices (`decision-light-20x2-*`, `fresh-20x2-default`,
`fresh-20x2-rule`, `postfix-paired-20x2`) remain valuable as **baseline and
diagnostic context** — they are the source of every `[A]` finding in §4, §5 and
§8, and they are why the four new questions exist. They are **not** official rows
in this report, are not merged into any A–F table, and no pass rate here is
inherited from them.

Where §4 and §5 record measured behaviour, read those lines as *prior baseline
observations that motivated the expectation*, never as results for arms A–F.

### 9.6 Pre-execution checks (blocking)

1. **Rule Retrieval stable**, confirmed by the parent *and* by a `git status`
   count steady across two checks minutes apart. `contracts/case_decision.py`,
   `case_decision_light.py`, `ai_case_project.py` and `policy_case_decision.py`
   were edited 13:34–13:37, and status has since moved 101 → 102 → 103 **[D]**.
   `case_decision_light.py` is the response model for arms A/B and
   `case_decision.py` seals what R7 validates, so measuring across this window
   would measure nothing.
2. **Re-run `verify_search_live.py`**; require `readiness_probe: true` on both
   projects. A DB `built_at` is not live readiness.
3. **Re-confirm `rule_retrieval` joins `request_hash` in the sparse form.**
   Omitting it lets two calls differing only in retrieval mode share an
   idempotency key and replay each other's receipt **[I]** — that would corrupt
   every (A,B) and (C,D) pair. `case_decision.py` is one of the files just edited,
   so this must be re-verified **after** Rule Retrieval reports stable.
4. **Restart the backend** once the tree settles — no `--reload`, so a code change
   is not live until restart **[I]**.
5. **Capture backend stderr to a file** before the first call **[I]**.
6. Confirm no frontend suite is running concurrently **[I]**.

### 9.7 Harness requirements

- **Fresh UUID `Idempotency-Key` per call on A–D**, regardless of check 3.
  **Send none on E/F** — it does not belong in that request **[D]**.
- **Interleave and rotate**: put each question to all six arms back to back, with
  arm order rotated per question and per repetition, so service drift lands on all
  arms equally instead of on whichever arm is always first. This is the pattern
  `interleaved_models.py` already establishes **[D]**.
- **Whole-run watchdog with suspension awareness.** One recorded call measured
  20,577,488 ms because the host entered Modern Standby **[I]**; all other paired
  calls were 13–47 s. Detect and exclude such calls from causal statistics rather
  than reporting them as latency.
- **3 repetitions**, not 2. This is a real improvement: several instabilities in
  §8 are visible in the recorded runs only as a single flip at n=2, which cannot
  distinguish a rare event from a coin toss. n=3 makes R6 a rate.
- **Never write into `58f19b59-…\files\runs\`** — those are baselines. New
  filenames, this session's folder.
- **Harness reuse is narrower than an earlier draft claimed.**
  `decision_light_20x2.analyse(light, full, wall_ms)` requires a light response
  **and that same decision's receipt**, fetched from `light['receipt_url']`
  (`:519-528`) **[D]**. That signature fits **arms A/B only**, where the receipt
  fetch is a read of the arm's own execution — it adds `GET` calls but no new
  receipts. It does **not** fit arms C/D: `POST /case` returns the full receipt
  directly with no light projection to pair it against, and passing another arm's
  response as `full` would fabricate exactly the cross-arm identity this rubric
  now forbids.
  - **A/B:** reuse `analyse` as-is; its `full_light_identity_match` is then an
    intra-execution check, which is its original meaning.
  - **C/D:** need a full-only analyser reading `considered`/`retained`, verdict,
    citations and usage straight off `CaseDecisionEnvelopeV2`.
  - **E/F:** need a third, smaller analyser — `PolicyRetrievalEnvelope` has no
    `outcome`, `verdict`, `citations` or `decision_hash`, and `analyse` would
    raise on its `validate_receipt` call.
  `aggregate` and `safe_irrelevant` are reusable across A–D unchanged.

### 9.8 Required report fields

Per question × arm:

```
{ id, project, class, arm, route, response_model, retrieval_mode,
  reasoning_effort,            # medium on A-D; null on E/F
  n: 3,
  R1,R2,R3,R4,R5,R7,R8,R9 : pass|fail|n/a,   # E/F: R2,R3,R4,R5,R7 are n/a
  correctness_pass          : bool,    # R6/R10 excluded by construction
  expected_evidence_hit     : [provision_key...],
  expected_evidence_miss    : [provision_key...],   # REQUIRED, never omitted
  present_in_retrieval_only : bool,    # from the paired E/F arm - see 9.3
  R6 : { outcome_stability: k/3, citation_stability: k/3, policy_set_stability: k/3 },
  R10: { retained_cardinality, citation_keys, total_tokens, wall_ms, outcome },
  receipt_written           : bool,    # true on A-D, false on E/F
  decision_id, correlation_id, decision_hash }   # RECORDED, never compared across arms
```

**Recorded-only fields.** `decision_id`, `correlation_id`, `decision_hash`,
token-usage and stage-latency maps are captured for traceability and are
**never** asserted equal between arms: every A–D call is an independent execution
(§9.2, §9.4). `full_light_identity_match` may appear only on arms A/B, where it
compares an execution against its own fetched receipt.

**E/F irrelevant rows** carry the returned `policies` set, the returned provision
keys and the rank/score fields **verbatim as observations**, with `R5: n/a`.
Only R1, R8 and R9 — all defined against the corpus before any run — are scored
there. No threshold is derived from observed output.

`expected_evidence_miss` must be printed **beside every pass rate, in the same
table**, never in an appendix, and each entry must carry
`present_in_retrieval_only`, so a retrieval defect is never reported as a
reasoning defect or the reverse.

Aggregate reporting must state, separately and never merged:
`correctness_pass` per arm (out of 20, with the n/a dimensions named for E/F) ·
R6 stability rates with **n=3** stated · R10 surface and mode deltas, as
distributions rather than per-call equalities · total calls (360) · total
receipts written (240).

---

## 10. Explicit non-claims

- I have **not** executed any decision call, matrix or test suite. Every measured
  number above is read from a recorded artifact and attributed.
- I have **not** verified that the 4 new questions behave as expected. Their
  expected values are **designed criteria**, not observations, and are labelled
  as proposals throughout.
- Candidate-quality findings remain **advisory** and were not re-derived here.
- Expected-evidence provision keys are asserted from heading paths and page
  ranges **[D]**; I did not read provision body text to confirm that each
  provision states what its heading implies.

### 10.1 Retracted claims, recorded rather than silently removed

Three claims appeared in earlier drafts of this document and are **withdrawn**.
They are listed because a reader of an intermediate copy would otherwise carry
them forward.

1. **A–F as a `reasoning_effort` axis.** Inferred from harness vocabulary. Wrong:
   A–F is defined by the user's request as three response surfaces × two
   retrieval modes (§9.1).
2. **"A/B and C/D are the same execution seen twice", with `decision_id`,
   `correlation_id`, `decision_hash`, token-usage and stage-latency maps required
   identical across arms.** Wrong, and self-contradictory: with a fresh
   `Idempotency-Key` per primary call each A–D call is an independent
   adjudication, which is why §9.2 counts **240** receipts and not 120. The
   invariant is intra-execution and belongs in focused contract tests; the
   existing harness's `full_light_identity_match` compares one execution's light
   response against **its own** fetched receipt (`decision_light_20x2.py:519-528`)
   **[D]**, never two POSTs. Cross-arm comparison is limited to projection/field
   availability and aggregate distributions (§9.4).
3. **"Score E/F irrelevant safety after the first run establishes what the route
   does."** Wrong: that is post-hoc thresholding — fitting the criterion to the
   observation. R5 is **`n/a`** on E/F, the returned sets are recorded verbatim,
   and only the corpus-defined checks R1/R8/R9 are predefined and scored (§9.4).

Claims 2 and 3 were corrected on parent instruction; claim 1 likewise. Each was
an error of my own reasoning, not of the sources.
