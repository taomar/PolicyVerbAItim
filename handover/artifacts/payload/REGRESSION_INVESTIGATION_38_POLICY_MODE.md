# Why Prior LLM/Retrieval Quality Appeared Better — Investigation of the 38 Valid Policy-Mode Failures

Child: **Payload and Full-Cycle Verification** · Session `5a06fec2-12cd-4477-b574-4d18ab814907`
Parent: `b065f09b-2a4c-479f-a012-e6e55f388234` · Prepared 2026-09-04
**Scope: the 38 valid policy-mode (A/C/E) failures only.** B/D/F excluded from every
actionable conclusion, per the run's own `not_representative_of_intended_rule_only_contract`
label. Read-only: no repository, database, Search, service or live-data mutation.

Evidence tags: **[D]** direct this session · **[A]** recorded artifact · **[I]** inherited, unverified.

---

## 1. Headline

> **No LLM or retrieval regression is proven. Zero of the 38 failures is a demonstrated
> regression against a historical baseline.**
>
> The identical current system, re-scored under the *old* rubric, returns **87.5 %**
> (42/48) on the comparable questions — against the historical **85 %** (17/20).
>
> The apparent quality drop is produced by four things, in descending size:
> a **stricter and genuinely new evaluation**, **two new questions with no baseline**,
> a **pre-existing unfixed retrieval defect**, and **two of my own manual criteria that
> assert facts the corpus does not contain**.

---

## 2. What was compared, and the control for scope

The predecessor's most useful sentence governs this entire report:

> *"A comparison is only evidence if both sides are the same scope."*
> — `8e46052e…\files\HANDOVER.md` §9

The "prior quality" figure in circulation is **17/20 scenario passes** from the recorded
20×2 matrices **[A]**. The new figure is **52/90 repetitions, 16/30 groups** for A/C/E
**[A]**. These are not the same scope on any axis: different question set, different
arms, different repetition count, and — decisively — **a different definition of passing**.

| Axis | Historical 20×2 | Six-arm run A/C/E |
|---|---|---|
| Corpus | AIS + HW | **AIS only** |
| Questions | 20 (10 AIS) | 10 AIS, **2 of them new** |
| Irrelevant controls | 3 per corpus | 1 |
| Arms | default / rule | 3 surfaces × policy mode |
| Repetitions | 2 | 3 |
| Unit reported | scenario (n=2 folded) | repetition, and group (strict 3/3) |
| Answer evaluated? | **No** | **Yes — 3 axes** |
| Evidence check | substring of heading label | exact `provision_key` |
| Composition check | none | R9, all required provisions |
| Manual criteria | none | frozen per question |

---

## 3. System configuration was identical — nothing regressed underneath

Every controllable input is the same across the historical runs and the six-arm run.

| Input | Historical | Six-arm run | Same? |
|---|---|---|---|
| Model deployment | `gpt-5.6-terra` (primary, `settings.py:169`) | `gpt-5.6-terra` in **120/120** decision records **[D]** | ✅ |
| Reasoning effort | `medium` (`decision_light_20x2.py:509`) | `medium` (`manifest.snapshot.json → request_defaults`) **[D]** | ✅ |
| Hash basis | `case_decision_v2_lang_verification` | same, 120/120 records **[D]** | ✅ |
| Light schema | `case_decision_light_v1` | same, 60/60 light records **[D]** | ✅ |
| AIS index `built_at` | `2026-09-03T20:25:49.981736Z` | **unchanged** `2026-09-03T20:25:49.981736Z` **[D]** | ✅ |
| AIS `document_count` | 332 | 332 **[D]** | ✅ |
| Manifest / quality | ready / passed | ready / passed **[D]** | ✅ |
| `rule_index_scope` | `all_published_rules_v1` | unchanged **[D]** | ✅ |

**The corpus was not rebuilt, the model did not change, and the effort did not change
between the two measurements.** Any behavioural difference must therefore come from
model non-determinism, not configuration drift.

Independent reconciliation **[D]**: decision receipts moved **164 → 284**, i.e. **+120**,
exactly the A–D decision calls (4 arms × 10 questions × 3 repetitions) with E/F writing
none — matching the receipt model predicted in rubric §9.2 before the run.

---

## 4. Retrieval is provably unchanged

Retained `provision_key`s in the new run are **identical** to the historical runs on every
comparable question **[D]/[A]**:

| Question | Historical retained label | New retained key (×6) | Same |
|---|---|---|---|
| AIS-01 annual-vacation | 7.12 ANNUAL VACATION | `ab87a692` | ✅ |
| AIS-02 sick-surgery | 7.13 SICK LEAVE | `28334f1a` | ✅ |
| AIS-03 absence-penalty | Table of Violations and Penalties | `e8326a49` | ✅ |
| AIS-04 conflict-vendor | 8.6 CONFIDENTIALITY | `eddb92e1` | ✅ (same wrong provision) |
| AIS-06 overtime-weekend | 7.9 OVERTIME | `4094ad6b` | ✅ |
| AIS-07 tuition-child | 7.20 TUITION DISCOUNT | `77ec0324` | ✅ |

Retained cardinality is 1 on the decision arms in both eras. **There is no retrieval
regression to find.** The one retrieval *defect* present (AIS-04) is present identically
in both eras.

---

## 5. The decisive test: replay the old rubric on the new data

`replay_old_rubric.py` **[D]** reproduces the old harness's judgement verbatim —
`expected_policy_matches()` casefold-substring over joined heading labels, `safe_irrelevant()`,
and `expected_status` only where a scenario declared `expected_verdict` — and applies it to
the six-arm run's own A/C repetitions.

| Question | Old rubric on NEW data | New rubric on NEW data |
|---|---:|---:|
| AIS-01 annual-vacation | 6/6 | 6/6 |
| AIS-02 sick-surgery | **6/6** | **0/6** |
| AIS-03 absence-penalty | **6/6** | **4/6** |
| AIS-04 conflict-vendor | 0/6 | 0/6 |
| AIS-05 maternity-leave | 6/6 | 6/6 |
| AIS-06 overtime-weekend | **6/6** | **0/6** |
| AIS-07 tuition-child | 6/6 | 6/6 |
| AIS-08 probation *(new)* | n/a | 0/6 |
| AIS-09 leave-travel *(new)* | n/a | 0/6 |
| AIS-10 irrelevant-football | 6/6 | 6/6 |
| **Comparable total** | **42/48 = 87.5 %** | 28/48 |

**87.5 % now vs 85 % historically.** The system has not got worse; the yardstick got
much harder. **14 repetitions pass the old rubric and fail the new one.**

### 5.1 Why the old rubric could not see these failures

The old `aggregate()` scored: `two_runs`, `schema_hash_identity`, `citation_integrity`,
`token_usage`, `stage_latency`, `expected_policy`, `irrelevant_safe`, `expected_status` **[D]**.
Of those, only two touch substance:

- **`expected_policy`** — a casefold **substring of a heading label**. For AIS-06 it asked
  only whether some retained label contains `"overtime"`. Retrieving 7.9 OVERTIME and then
  saying anything at all about it passed.
- **`expected_status`** — evaluated **only when the scenario declared `expected_verdict`**.
  Of the ten AIS scenarios, exactly **one** (`hw-refresh-26-months`, not AIS) declared it.
  So for every AIS question the verdict was **never checked**.

There was **no** answer evaluation, **no** composition check, and **no** exact-evidence
requirement. The six-arm run's own report says the same of its pre-adjudication table:
130 rows `UNREVIEWED`, "no evaluation of any answer, information track or verdict"
(`ADJUDICATION_REPORT.md` §1.1) **[A]**.

---

## 6. Attribution of all 38 failures

| # | Question | Fails | Class | Regression? |
|---|---|---:|---|---|
| 1 | AIS-06 overtime-weekend | 6 | **Rubric defect — criterion unsupported by corpus** | **No** |
| 2 | AIS-02 sick-surgery | 5 | **Rubric defect — criterion unsupported by corpus** | **No** |
| 3 | AIS-02 sick-surgery | 1 | Newly observed verdict, unproven as a rate change | **Not proven** |
| 4 | AIS-03 absence-penalty | 2 | Corpus/extraction limitation + known non-determinism | **No — pre-existing** |
| 5 | AIS-04 conflict-vendor | 9 | Pre-existing retrieval defect, fails old rubric too | **No — pre-existing** |
| 6 | AIS-08 probation *(new)* | 9 | New question, no baseline; genuine retrieval gap | **N/A — never measured** |
| 7 | AIS-09 leave-travel *(new)* | 6 | New question, no baseline; genuine composition gap | **N/A — never measured** |
| | **Total** | **38** | | **0 proven regressions** |

### 6.1 Rubric defects — 11 of 38 (29 %), and they are mine

The run's frozen source of truth, `source.snapshot.json`, contains **only structural
metadata: provision keys, heading paths, page ranges, rule types. No provision body text**
**[D]**. The manual criteria were therefore authored from what headings *imply*. My own
rubric §10 recorded that exposure in advance:

> *"Expected-evidence provision keys are asserted from heading paths and page ranges; I did
> not read provision body text to confirm that each provision states what its heading implies."*

That non-claim has now come true. `criterion_support_probe.py` **[D]** queried keyword
presence over the actual rule bodies, returning **counts only** so no policy text entered
any log:

**AIS-06 — criterion: "The absence of written approval must be the operative reason."**

| Provision 7.9 OVERTIME | Value |
|---|---|
| Rules anchored | 4 |
| Rule types | `human_judgment_requirement` ×4 |
| Rules containing "written" | **0** |
| "approval" / "authoris" / "authoriz" / "prior" | **0 / 0 / 0 / 0** |
| "entitle" / "compensat" | **0 / 0** |

7.9 contains **no written-approval condition and no entitlement or compensation rule**.
All six repetitions said exactly that — *"they do not establish any entitlement to overtime
pay… whether approval is written, verbal, or absent"* **[A]** — and they were **right about
the corpus**. The criterion demanded the system assert something the corpus does not say.
**All 6 AIS-06 failures are false failures.** Note the answer evaluation itself returned
`pass` on all three axes for every one of them **[A]**.

**AIS-02 — criterion: "The absent medical certificate must surface as missing or as the
reason the rules do not settle the case."**

| Provision 7.13 SICK LEAVE | Value |
|---|---|
| Rules anchored | 5 |
| Rules containing "certificate" | **0** |
| "medical" / "approval" / "submit" | 2 / 2 / 1 |

There is **no certificate rule** to surface. Five repetitions were failed for not surfacing
a requirement that does not exist. **5 of the 6 AIS-02 failures are false failures.**

### 6.2 The one candidate real issue — AIS-02, one repetition

One repetition returned `verdict = answered`, decision text **"allowed"**, `verdict_reached
= true`, approving all six days **[A]**. Historically this question returned
`not_settled_by_rules` in **4/4** default-mode observations **[A]**.

Stated honestly:
- **Newly observed.** No historical run produced `answered` here.
- **Not proven as a rate change.** 0/4 historical versus 1/6 new is not statistically
  separable; with n=2 per historical run a 1-in-6 event is very likely to be missed
  entirely. This is precisely the low-n blindness that motivated moving to n=3.
- **Not proven wrong on the merits.** Since 7.13 contains no certificate precondition
  **[D]**, an "allowed" verdict may be defensible. The criterion that failed it presumed a
  corpus fact that does not exist.

Treat as **a flag for a larger-n rerun**, not as a regression.

### 6.3 AIS-03 — a genuine corpus/extraction limitation, pre-existing

Historical: `verdict = answered` in 4/4. New: 4 answered, 2 `not_settled_by_rules` **[A]**.
Evidence was retrieved and quoted correctly in every case; two repetitions "declined to map
'first occurrence' onto the first listed consequence while its two sibling repetitions did"
**[A]**.

The reason is visible in the corpus **[D]**:

| Table of Violations and Penalties | Value |
|---|---|
| Rules anchored | 94, **all `routing`** |
| Rules containing "deduction" / "warning" | 90 / 35 |
| Rules containing **"first" / "second" / "third"** | **0 / 0 / 0** |

**The occurrence ordinality of the penalty table is not represented in the extracted rules.**
The consequences survived; the 1st/2nd/3rd-occurrence column structure did not. A question
whose whole point is "it is the first occurrence" therefore cannot be settled reliably —
which is exactly the observed 4/2 split.

This is a **real defect**, but it is **pre-existing**: the corpus is byte-identical to the
one the historical runs used (`built_at` unchanged **[D]**). The old rubric could not see it
because it declared no `expected_verdict` for this question, so `expected_status` was
vacuously true.

Two further notes. First, this is the **recall control** and the **visual-recovery probe**
(pages 21–27): retrieval and citation of the recovered table region still work in 6/6 **[D]**,
so the selective visual recovery is not implicated — only the ordinal structure is missing.
Second, this makes AIS-03's criterion partly unsound too, for the same reason as §6.1.

### 6.4 AIS-04 — pre-existing retrieval defect, unchanged

`017de08a` (8.7 CONFLICT OF INTEREST) was **never retrieved** in any of 9 policy-mode
repetitions, in either era **[A]/[D]**. The provision exists and carries 6 rules
("conflict" ×2, "interest" ×3) **[D]**. It fails the old rubric too. **Not a regression —
an unfixed defect**, and the single most valuable genuine finding carried forward.

Note for scoping: the provision contains **0** rules matching "disclos" or "recus" **[D]**,
so retrieving it might still not fully answer "what must I disclose". The retrieval gap is
real; the expected *answer* needs re-derivation from the body text.

### 6.5 AIS-08 and AIS-09 — 15 failures on questions that never existed

These are the two questions I added. They have **no historical baseline of any kind**, so
they cannot demonstrate regression. They were designed to probe the exact gaps they found,
and they found them:

- **AIS-08**: `39e08eda` (7.4 PROBATION) never retrieved in 9/9 while 7.5 was; yet 7.4 holds
  4 well-populated rules ("probation" ×4, "period" ×4) **[D]**. A genuine retrieval gap.
- **AIS-09**: `ab87a692` (7.12 ANNUAL VACATION) **was retained but never cited or used** —
  *"the answer never engages the annual-vacation counting rule it held"* **[A]**. A genuine
  composition gap, and precisely the failure mode R9 was created to expose.

Both are **new information**, not deterioration.

---

## 7. Root causes, ranked

1. **Evaluation redefinition (largest single cause).** The old score contained no answer,
   verdict or composition evaluation and matched evidence by heading substring. 14 of 38 are
   repetitions that the old rubric passes and the new one fails.
2. **Scope change presented as a trend.** 15 of 38 sit on two questions with no baseline;
   comparing a 20-question two-corpus figure with a 10-question one-corpus figure is not a
   like-for-like comparison.
3. **Criteria authored without body text (my defect).** 11 of 38 are false failures caused
   by criteria asserting corpus facts that do not exist. Root cause: the frozen source
   snapshot carries no provision text, and I wrote criteria from headings anyway.
4. **Pre-existing unfixed defects surfaced by a sharper instrument.** AIS-04 retrieval,
   AIS-03 lost table ordinality, AIS-08 retrieval, AIS-09 composition. Real, valuable, and
   **not new** — the old rubric simply could not express them.
5. **Model non-determinism, now visible at n=3.** Outcome distributions widened on AIS-01,
   AIS-02 and AIS-03. Historical n=2 samples were too small to observe this; the repository
   already documents the classifier as non-deterministic **[I]**.

**Not causes** — each checked and excluded **[D]**: model/deployment change, reasoning-effort
change, corpus rebuild, index rebuild, manifest or quality-state change, retrieval-method
change, retained-cardinality change, rule-index-scope change.

---

## 8. Remediation plan

### 8.1 Fix the rubric before re-running anything (blocking)

**R-1. Re-derive every manual criterion from provision body text, not headings.**
Owner: this child. The frozen `source.snapshot.json` must be extended with rule
`title`/`description` for the required provisions, or criteria must be expressed only over
what structural metadata can support. Until then, every manual criterion is an untested
assumption.

**R-2. Withdraw or rewrite three criteria now shown unsupported [D]:**
| Question | Criterion | Action |
|---|---|---|
| AIS-06 | "absence of written approval must be the operative reason" | **Withdraw.** 7.9 has no written-approval or entitlement rule. |
| AIS-02 | "absent medical certificate must surface…" | **Withdraw.** 7.13 has no certificate rule. |
| AIS-03 | "first occurrence maps to a consequence" | **Rewrite** as a known-limitation probe: the ordinal structure is absent from the corpus. |

**R-3. Add a criterion-provenance field.** Every criterion must record whether it was
derived from `heading_path` or from `rule_body`, and only `rule_body`-derived criteria may
fail a repetition. This makes §6.1's failure mode structurally impossible to repeat rather
than relying on care.

**R-4. Separate "system is wrong" from "corpus lacks it".** Add an explicit
`corpus_supports_expectation` check, evaluated before scoring, so an unsupported expectation
is reported as a rubric finding rather than charged to the system.

### 8.2 Report format

**R-5. Never publish a bare pass rate against a historical one.** Always print, in the same
table: `expected_evidence_miss`, `present_in_retrieval_only`, whether the question has a
baseline, and whether the criterion was body-derived.
**R-6. Publish the old-rubric replay alongside the new score.** It is the only figure
comparable to the historical 17/20, and it is cheap: `replay_old_rubric.py` is filesystem-only.

### 8.3 Genuine engineering defects to carry forward (not caused by this run)

| Priority | Defect | Evidence |
|---|---|---|
| 1 | **8.7 CONFLICT OF INTEREST never retrieved** — both eras, 9/9 | §6.4 |
| 2 | **Penalty-table occurrence ordinality lost in extraction** — 0/94 rules carry first/second/third | §6.3 |
| 3 | **7.4 PROBATION never retrieved** while sibling 7.5 is | §6.5 |
| 4 | **Retained-but-uncited evidence** — provision held and never used | §6.5 |

Defects 1 and 3 share one shape: **a topically-correct sibling provision crowds out the
governing one.** That is a single retrieval-ranking question, not four, and it should be
investigated as one.

### 8.4 Rerun plan

**Do not rerun to "get a better number."** The rerun exists to remove the three known
rubric defects and to measure the four real defects at usable n.

1. **Gate:** R-1 … R-4 complete; parent authorisation; Rule Retrieval quiet; corpus
   `built_at` unchanged (re-verify — a rebuild would void comparability).
2. **Scope:** the same 10 AIS questions, arms A/C/E, **n=5** (not 3). Rationale: the only
   unresolved behavioural question is a 1-in-6 event; n=3 cannot settle it and n=5 gives a
   usable rate. Cost: 10 × 5 × 2 decision arms = **100 receipts**; arm E writes none.
3. **Hold constant:** model, effort `medium`, corpus, index. Any change voids the comparison.
4. **Report both scores** — new rubric and old-rubric replay — plus per-question baseline
   availability.
5. **Expected outcome if this analysis is right:** AIS-06 → 6/6 pass and AIS-02 → ≥5/6 pass
   once the unsupported criteria are withdrawn, with AIS-04/08/09 still failing. **That is
   the falsifiable prediction of this report.** If AIS-06 still fails after R-2, this
   analysis is wrong and must be revisited.
6. **Do not** extend to HW until the AIS rubric defects are fixed; the same
   heading-derived-criteria flaw is present in the HW half and would reproduce it at scale.

---

## 9. Explicit non-claims

- I did **not** run the six-arm matrix; it was executed elsewhere. Every figure attributed
  to it is read from its immutable artifacts and cited.
- I did **not** rerun anything, start any service, or mutate any repository or live data.
- I have **not** proven the AIS-02 "allowed" repetition is a defect. It is newly observed and
  statistically unresolved; §6.2 states both.
- I did **not** read provision body text into any output. Support for criteria was tested by
  **keyword presence counts only**; a zero count proves absence of that token, not absence of
  the concept under a different wording. Where a count is non-zero I have not verified what
  the rule says.
- B/D/F rule-mode arms were excluded entirely and contributed to no conclusion here.
- The historical `[A]` figures rest on n=2 per scenario, which is too small for rate claims;
  every comparison against them is stated as suggestive, not proven.
