# AGENT_PROGRESS — §4 Composition Completeness

Session `5a06fec2-12cd-4477-b574-4d18ab814907` · shared-checkout writer · 2026-09-05

## Architecture Decision

### Context
The six-arm run showed six AIS-09 repetitions where both required provisions were
retained at ranks 0 and 1 and the answer cited only one. Retrieval was correct;
the answer rested on less than it held, and the receipt could not show that.

### First attempt, and why it was insufficient
I first derived a `cited`/`uncited` disposition **server-side** from the citations
that already existed. The parent correctly reclassified this as
**containment/observability**: the server can see which citations exist but cannot
see whether a unit was *relevant*, so the same reply stays `answered` with the
unused provision merely labelled. It documents the gap; it does not close it.

### Decision (Option C, parent-approved)
The **model declares** what it did with every unit of evidence it was handed; the
**server refuses to call the result an answer** unless that account is complete.

- `evidence_dispositions` added to `PLAN_KEYS` and to `CasePlan` as
  `tuple[EvidenceDisposition, ...]`. Identities and one closed token only — the
  `reason` is prose, is listed in `DETAIL_PROSE_FIELDS`, and is never read, so no
  wording of it can move a decision.
- New `ai_case_evidence_accounting.py` checks four things: **totality** (every
  unit named), **recognition** (closed token), **ownership** (a `used` claim names
  a citation from the closed rule set), **disclosure** (a set-aside unit says why,
  presence only).
- Enforced in `_decision_from_parsed` immediately after the existing
  `states_verdict` repair. A blocked account becomes **`not_settled_by_rules`** —
  no new status, reusing the vocabulary that already means "rules bore on the case
  and did not settle it".
- `PROMPT_VERSION` v15 → **v16**; `PLAN_PROFILE` case-plan-v3 → **v4**.
- The server-derived `PolicyRef.composition` is **retained as containment
  substrate** and remains sealed write-only-when-present.

### Rationale — why not the obvious repair
Forcing every retained unit into the citations would close the gap by trading
precision for a number. Retrieval deliberately keeps more than one answer needs.
Setting evidence aside is legitimate; setting it aside **silently** is not. Every
control in both new suites exists to prove that distinction survived.

### Alternatives considered
- **Server-derived only** — rejected by the parent: cannot see relevance.
- **Tolerate an absent declaration** — reopens the silent gap; a non-compliant
  reply becomes indistinguishable from a complete one.
- **A new disclosed-non-use status** — rejected: a second contract change on top
  of the prompt one, where an existing status already says the right thing.

## Behavioural risk

`answered` is now conditional on a complete account. A reply that does not
declare, or declares incompletely, degrades to `not_settled_by_rules`.

- **Direction is fail-closed**, consistent with this platform's stated stance that
  a single unfaithful item fails closed. The failure mode is a case reported as
  unsettled, not a wrong determination.
- **The rate is unknown.** If the model under-complies with the v16 instruction,
  more cases report unsettled than before. Nothing in this change bounds that rate.
- **Prompt and validation landed atomically**, so there is no window in which
  validation is strict and the prompt has not asked.

## Live-compliance limitation — stated plainly

**I could not verify that the model actually emits compliant dispositions.** Live
API/model calls are outside this grant. Everything asserted here is proved against
synthetic parsed payloads: the validation logic, all four failure modes, ownership
against the closed rule set, sealing, and legacy-hash compatibility.

What remains unmeasured, and must be measured in Gate 3 before this is called
resolved rather than implemented:
1. the rate at which v16 replies carry a complete account;
2. whether AIS-09's six repetitions now block or compose;
3. whether any previously-`answered` case degrades that should not.

## Anti-corpus guards (done first)

- `ai_case_intent` was **already** registered in `TOUCHED`; the blueprint's L-1
  gap was stale. Verified, nothing added.
- **Float gap closed**: `test_no_authored_module_branches_on_a_measured_magnitude`
  read `int` only, so a score pasted from a run would have passed unchallenged.
  Now `(int, float)`, excluding `bool`. `1.914` added to `MEASURED_MAGNITUDES`.
- **`10` deliberately not banned.** Probed first: `visual_page_reading` carries a
  legitimate literal `10`. A rank in one run is an ordinary ceiling everywhere
  else, and banning it would condemn correct code that never saw the measurement.
- Added a **refusal + control pair** proving the float branch fires, because no
  shipped module carries a measured float and the check would otherwise report
  success whether or not it worked.

## Files changed

| File | Change |
|---|---|
| `contracts/case_decision.py` | disposition vocabulary, `PolicyRef.composition`, `_sealed_policy_entry` |
| `application/policy_case_decision.py` | `_apply_composition`, envelope wiring |
| `assistants/ai_case_plan.py` | `EvidenceDisposition`, `PLAN_KEYS`, `PLAN_PROFILE` v4, `_dispositions_from_reply` |
| `assistants/ai_case_evidence_accounting.py` | **new** — the four checks |
| `assistants/ai_case_intent.py` | `_evidence_keys`, gate in `_decision_from_parsed`, prompt field, `PROMPT_VERSION` v16 |
| 6 test files | version pins, plan-field guard, evidence accounts on `answered` fixtures |
| 2 new test files | 35 tests |

## Verification

| Shard | Result |
|---|---|
| Anti-corpus guards | 68 passed |
| Held-evidence disposition | 15 passed |
| Evidence accounting | 20 passed |
| Impacted decision suites | 234 passed |
| **Full backend suite** | **5514 passed, 18 skipped, 0 failed** (baseline 5471/18) |

All runs emitted visible progress; no silent pipelines.

## Not done

No staging, no commit — per the commit-decomposition audit.

---

# §6 — Entitlement versus operational approval

## Decision
Rule type cannot decide this: a record conferring an entitlement carries ordinary
`permission`/`eligibility` rules, so nothing structural separates "settles what is
conferred" from "settles whether it is approved now". Same shape as §4 — the reply
declares `settles_requested_decision`, and the decision stage compares that claim
against the status it chose. An explicit `false` beside `answered` becomes
**`not_settled_by_rules`**; absence is not denial, and only a real boolean counts.
No new status; the explanation survives, so partial settlement is reported.

## A coupled invariant found by the tests
`verdict = prose["verdict"] if status == ANSWERED else ""` sat **above** the new
gates, so a repaired status left the verdict string behind — a receipt whose
verdict is non-empty while not reached, contradicting the contract. §4's gate had
the same latent exposure. The read was moved below every status repair and the
comment now says so, so the next gate added is told where it belongs.

## Files
`ai_case_plan.py` · `ai_case_intent.py` · plan-purity guard ·
`test_a_conferred_entitlement_is_not_an_approval.py` (new, 21 tests).

Versions unchanged: v16 / case-plan-v4, both unreleased in this same change set.

---

# §2 — Coverage expansion eligibility

## Decision
`COVERAGE_EXPANDABLE_POLICY_ORDERS` — an enumeration of orderings — replaced by
`coverage_expansion_is_eligible(precision, selected_count)`, derived from the two
facts that make expansion meaningful: **a relevance cut was applied** and
**retention budget remains**.

The enumeration was itself the defect. It had already been wrong once (rule mode
absent), and naming the missing order fixed that instance while leaving the
mechanism intact — so `semantic_strong_lead_v1` was omitted in exactly the same
way, and a lead strong enough to keep one policy of five left four slots
unreachable.

## What did not change
No threshold, budget, selection limit, ordering, or record boundary. Eligibility
is asked *after* selection, about its own reported outcome.

## Files
`ai_case_project.py` · `test_rule_retrieval_is_an_explicit_mode.py` ·
`test_policy_case_project.py` ·
`test_coverage_expansion_is_eligible_by_property.py` (new, 24 tests).

## Verification across all three milestones

| Stage | Result |
|---|---|
| Baseline at handoff | 5471 passed / 18 skipped |
| After §4 | 5514 / 18 / 0 |
| After §6 | 5535 / 18 / 0 |
| **After §2** | **5557 / 18 / 0** |

All runs emitted visible progress in bounded shards.

