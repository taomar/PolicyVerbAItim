# Child Mapping: Rule Retrieval

## Model

Use Claude Opus 5, maximum reasoning, long context.

## Maps from

- Read-only project session `fbae4b69-cd04-4c75-b346-86688320f68f`
- Rule-cardinality implementation agent
- Partial score-disclosure task stopped during migration

## Read first

1. `C:\Users\taomar\.copilot\session-state\fbae4b69-cd04-4c75-b346-86688320f68f\files\HANDOVER-rule-retrieval-investigation.md`
2. Parent successor handover.
3. Matrix artifacts under
   `C:\Users\taomar\.copilot\session-state\8437f3da-491a-4139-b979-8b00996c8953\files\runs`.

## Completed stage 1

- Added evidence/cardinality cut to rule-parent selection.
- Bounded policy fallback by evidence and capacity.
- Restored rule-mode coverage expansion.
- Independent focused suite: 534 passed.
- Post-fix paired matrix: both modes 17/20 passes and 40/40 integrity.
- Per-policy token inflation is gone; residual cost is extra retained parents.

## Current partial work

The working tree contains unverified additive disclosure fields:

- `best_score_kind`
- `semantic_score`
- `rule_lead_semantic_score`
- `rule_max_semantic_score`
- score-kind constants and `_score_disclosure`

Do not assume this patch is complete. It was interrupted for migration.

## Decisions already made

- Defer matched-rules-only payload for small parents.
- Treat "rule-first smaller" as an aggregate target with recall controls, not a
  hard per-scenario inequality.
- Do not tune a threshold or change score statistic until score inputs and
  channels are observable.

## Ordered assignment

1. Review and finish score-scale disclosure only; selection must not change.
2. Test all selection paths:
   semantic, hybrid, policy RRF, rule-weighted RRF.
3. Prove old receipts remain valid and decision hash basis is unchanged.
4. Capture in a fast harness:
   semantic selected/elbow/cutoff, fallback offered/admitted, coverage expansion,
   lead semantic, max semantic, score kind.
5. Run retrieval-only paired measurements with a hard whole-run watchdog and
   host-suspension detection.
6. Attribute residual exactly.
7. Only then propose/implement:
   lead-rule semantic elbow input, rule-only flat default of one, or corrected
   coverage floor.
8. Pair narrowing tests with a strong-rule-only recall control.

## Important evidence

- Original rule mode always retained five policies.
- After stage 1: median retained default 1, rule 2; paired median +2,390 tokens.
- At equal retained cardinality, modes differ by approximately 1% tokens.
- Four of 30 earlier extras were cited.
- Ambiguous `best_score` scales are a verified disclosure defect.
- Max-of-k semantic compression is inferred, not yet measured.
