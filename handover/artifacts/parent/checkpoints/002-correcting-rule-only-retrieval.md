<overview>
The user is coordinating a local PolicyVerbAItim migration, Consume API matrix, true rule-only retrieval correction, and Azure production local authentication. Accuracy is mandatory: provisional findings must never be presented as final, policies must return policies, rules must return rules, and progress/results should be printed in concise tables.
</overview>

<history>
1. Migration and hierarchy
   - Migrated oversight into local-only parent session `b065f09b-2a4c-479f-a012-e6e55f388234`.
   - Coordinated Payload, Integration, Rule Retrieval, Matrix, and Azure diagnostics children.
   - Preserved shared-checkout serialization and avoided unapproved deployment/migration/data mutation.

2. Azure deployment preservation
   - Earlier Azure deployment work was committed as:
     - `a17525cad24b3af262290826eb9846f90acea9ae`
     - `Fix reproducible Azure deployment`
   - Deployment remained halted while diagnostics and local-auth design proceeded.

3. Rule Retrieval Phase B
   - Added score disclosure and Light requested/executed retrieval-mode echo.
   - Full backend suite passed: 5,364 passed, 18 skipped.
   - Attribution rejected the previous max-of-k hypothesis:
     - 39/39 cuts identical.
     - 618/618 parent lead scores equalled maximum scores.
   - No threshold/selection correction was justified.

4. AIS-only matrix
   - User reduced scope from AIS+HW to AIS only: 10 questions × 3 repetitions × 6 arms.
   - Executed 180 calls in 74 minutes:
     - 180 HTTP 200.
     - No retries, suspensions, terminal 503s, or raw integrity failures.
     - Receipts increased exactly 164 → 284.
   - Raw evidence: 180/180 schema-valid, 2,047 files, no secret occurrences.

5. Matrix report correction
   - Initial deterministic table incorrectly displayed `needs_review` rows beside failures without completed answer evaluation.
   - User objected correctly.
   - Manual adjudication was then completed for all 180 responses:
     - 109 pass / 71 fail.
     - 33/60 strict groups passed.
   - Existing B/D/F measurements were reclassified as defective-current rule-mode baseline, not target rule-only results.

6. Root cause of oversized rule mode
   - Confirmed current implementation was “rule-first parent-policy expansion”:
     - Search rule documents.
     - Map rules back to parent policies.
     - Add policy fallback.
     - Send full policy projections to the answer path.
   - This violated the user’s intended contract.
   - In observed rule mode, 79/198 attributed retained parents came from policy fallback; fallback was non-zero in 81/90 rule-mode repetitions.

7. Corrected user contract
   - User explicitly clarified:
     - Policies → policy records only.
     - Rules → rule records only.
   - Authorized structural correction to true rule-only retrieval.
   - Rule-mode responses must use native `rules[]`, never parent policy bodies or policy fallback.

8. Azure login/local-auth work
   - Diagnosis found:
     - nginx Host routing loop causing 502.
     - Local production auth intentionally disabled.
     - Entra/Easy Auth and SPA integration absent.
   - User required production local auth when APIM/Entra are opted out.
   - Approved architecture:
     - Explicit `AUTH_MODE=local|entra`.
     - Key Vault-backed Argon2id credential bundle.
     - Real RBAC.
     - HttpOnly secure cookies and CSRF protection.
     - Single API replica containment for local mode.
     - Full deployment-script/IaC integration.
   - No Azure, Key Vault, deployment, migration, or real-secret mutation occurred.
</history>

<work_done>
Completed:
- Rule Retrieval Phase B disclosure and Light mode echo.
- Rule attribution investigation.
- AIS matrix execution.
- Raw and corrected deterministic postflight validation.
- Manual adjudication of all 180 AIS responses.
- Azure production-local-auth architecture.
- Initial Azure backend/auth/nginx implementation foundation.
- Integration plan for native rule envelopes.

AIS matrix actual results:
- Valid policy-mode baseline A/C/E:
  - 52/90 responses passed: 57.8%.
  - 16/30 strict groups passed: 53.3%.
- Defective old rule mode B/D/F:
  - 57/90 passed: 63.3%.
  - These results are invalid for intended rule-only claims.
- Combined reconciliation only:
  - 109/180 passed: 60.6%.
  - 33/60 groups passed: 55%.

Per-question strict group results:

| Question | A policy | C policy | E policy retrieval | B old rule | D old rule | F old rule retrieval |
|---|---|---|---|---|---|---|
| Annual vacation | P | P | P | P | P | P |
| Sick surgery | F 0/3 | F 0/3 | P | F 0/3 | F 2/3 | P |
| Absence penalty | F 2/3 | F 2/3 | P | F 2/3 | F 2/3 | P |
| Conflict vendor | F 0/3 | F 0/3 | F 0/3 | F 0/3 | F 0/3 | F 0/3 |
| Maternity leave | P | P | P | P | P | P |
| Overtime weekend | F 0/3 | F 0/3 | P | F 0/3 | F 0/3 | P |
| Tuition child | P | P | P | P | P | F 0/3 |
| Probation evaluation | F 0/3 | F 0/3 | F 0/3 | P | P | F 0/3 |
| Leave/travel composition | F 0/3 | F 0/3 | P | F 0/3 | F 0/3 | P |
| Irrelevant football | P | P | P | P | P | P |

Main failures:
- Conflict-of-interest: governing provision missing in all 18 repetitions; retrieval defect.
- Probation: provision 7.4 missing from policy-mode retrieval; composition/evidence failure.
- Leave/travel: both policies retrieved, but annual-vacation evidence dropped by decision path; post-retrieval composition loss.
- Tuition: old rule retrieval control F missed the tuition provision.
- Overtime: evidence was present, but all decision responses reasoned from the wrong operative gap.
- Five answerability/outcome failures occurred; direct verdict-discipline checks themselves had zero failures.

In progress:
- True rule-only backend implementation.
- Azure local-auth application/deployment implementation.
- Final report integrity/hash publication.

Issues encountered:
- Initial derived report had 181 schema errors.
- Raw evidence was unaffected.
- Separate corrected postflight evaluator produced 60/60 schema-valid rows.
- Matrix worker sessions repeatedly errored while idle; execution continued independently.
</work_done>

<technical_details>
- Parent folder:
  - `C:\Users\taomar\Downloads\policy-extractor-local-oversight`
- Shared repository junction:
  - `C:\Users\taomar\Downloads\policy-extractor-local-oversight\repository`
- Shared checkout:
  - HEAD `c0972c8bb7ba811903e981d3806afe31cc1f514d`
  - Tree moved from 103 to 105 status entries as Rule Retrieval added files.
- Live DB:
  - Revision `f4b8c2e97d31`
  - Repo head `a1c5f0b3e284`
  - Migration remains unapplied and was non-blocking for the matrix.
  - Current receipts: 284 completed, 0 pending/failed.
- AIS Search remained ready:
  - 39 policy documents.
  - 293 rule documents.
  - `all_published_rules_v1`.
- Matrix API on port 8010 was parent-owned and was stopped after the matrix.

Correct rule-only architecture:
- `policy_retrieval_v1` contains `policies[]` only.
- `rule_retrieval_v1` contains `rules[]` only.
- Opposite field must be absent on the corrected wire contract.
- Rule mode:
  - Must issue no policy query.
  - Must use no policy fallback.
  - Must never expand into parent policy content.
  - May add bounded related rule records for conditions/exceptions/overrides.
- Native rule records carry minimal source/citation identifiers only.
- Stale clients must fail closed using runtime schema guards.

Rule budget:
- Exact canonical UTF-8 byte ceiling: 40,000 bytes.
- Token estimator was corrected:
  - `/2.5` heuristic was rejected as unproven.
  - Current design uses one proxy token per UTF-8 byte.
  - Exact byte bound is authoritative.
- No oversize exception:
  - Highest-ranked oversize rule yields typed `rule_grounding_budget_exceeded`.
  - No false empty/no-rule response.
- Rules are omitted only at whole-rule boundaries with explicit reasons.

Rule test migration:
- Ledger approved:
  - Delete 16 tests solely covering removed parent grouping/fallback.
  - Rewrite 12 tests for native rule invariants.
  - Amend one policy-only coverage test.
- Important preserved checks:
  - Irrelevant query must not fill the rule budget.
  - Evidence-driven cardinality.
  - Rule score/cutoff scale.
  - Mode and query isolation.
  - Request-hash separation.
  - Related-rule recall.
  - Terminal 503 behavior.
  - Deterministic omissions.

Integration:
- Real retrieval client is `apps/consume-demo`, not `apps/web`.
- Existing unchecked TypeScript cast can silently show “0 policies” for a rule response.
- Runtime parser requirements:
  - Own collection must exist and be an array; empty is a valid negative.
  - Opposite interim compatibility collection may be absent or empty.
  - Missing/non-array own collection fails.
  - Non-empty opposite collection is mixed and fails.
  - Unknown/missing schema version fails visibly.

Azure local-auth:
- Explicit local mode is independent of optional APIM and Entra.
- Production file credential source is prohibited; Key Vault/UAMI required.
- Credential bundle includes Argon2id hashes, immutable IDs, roles, generation/token version, and `kid` key ring.
- Bounded last-known-good Key Vault behavior is required.
- Local mode uses HttpOnly, Secure, SameSite=Strict cookies and double-submit CSRF.
- Local production mode is hard-constrained to one API replica because limiter state is in-memory.
- This is containment, not horizontal-scale resolution.
- Horizontal scaling requires future shared transactional lockout state.
- Legacy `AZURE_ENABLE_ENTRA_AUTH=false` must not silently become local mode.
- No actual credentials, hashes, keys, or secret values were generated or exposed.
</technical_details>

<important_files>
- `...\b9e79289-63de-4596-8a76-88064fb51cf8\files\consume-api-matrix-ais\runs\consume-api-ais-six-arm-20260904\reports\postflight\adjudicated\ADJUDICATION_REPORT.md`
  - Final manual AIS evaluation.
  - Contains pass/fail, per-question matrix, exact failure causes, telemetry, and baseline validity labels.
  - Key sections:
    - §0 defective rule-mode evidence.
    - §1 headline results.
    - §2 aggregate by arm.
    - §3 question matrix.
    - §4 exact failure causes.

- Same directory:
  - `manual-decisions.json`
  - `answer-evaluation-ledger.json`
  - `deterministic-failure-ledger.json`
  - `aggregate-by-arm.csv`
  - `per-question-arm.csv`
  - `rule-channel-attribution.json`
  - `paired-telemetry.json`
  - These provide auditable per-response evidence and metrics.

- `...\reports\postflight\POSTFLIGHT_REPORT.md`
  - Corrected deterministic report before manual adjudication.

- `...\7d783c45-9dd4-49c8-bdc0-ad43f0192148\files\FINAL_FINDINGS_RULE_RETRIEVAL.md`
  - Phase B and attribution findings.
  - Documents rejected max-of-k hypothesis and old fallback behavior.

- `...\7d783c45-9dd4-49c8-bdc0-ad43f0192148\files\TEST_DISPOSITION_LEDGER.md`
  - Approved 29-test delete/rewrite/amend map.

- Shared repository files currently being changed for rule-only mode:
  - `src\policy_platform\contracts\policy_retrieval.py`
    - Separate policy/rule envelopes and native rule records.
  - `src\policy_platform\infrastructure\assistants\ai_case_project.py`
    - Rule-only selector, no-policy-query branch, related-rule expansion, budget logic.
  - `src\policy_platform\infrastructure\projection\policy_rule_slice.py`
    - Shared related-rule context logic.
  - `tests\unit\test_rule_mode_returns_rules_not_policies.py`
    - New rule-only contract tests.

- `...\94102b91-353f-46f3-a59b-72d8381912f9\files\RULE_RETRIEVAL_V1_INTEGRATION_PLAN.md`
  - apps/consume-demo parser/runtime-guard migration plan.

- `...\e1fe8465-c0af-4522-987d-84a5f30c75bf\files\PRODUCTION_LOCAL_AUTH_ARCHITECTURE.md`
  - Approved Azure local-auth architecture.

- Azure checkout changes include:
  - `.azure/deployment-plan.md`
  - `.env.example`
  - `pyproject.toml`
  - settings/auth/local-auth modules
  - nginx and web Dockerfile
  - Bicep/azd/bootstrap parameters and scripts
  - tests and documentation
</important_files>

<next_steps>
1. Finalize and validate the adjudication report hashes.
   - Print the verified final report and concise failure table in chat.
   - Do not present B/D/F as intended rule-only results.

2. Complete true rule-only backend wiring.
   - Finish `/policies` rule response using native `RuleRetrievalEnvelope`.
   - Complete rule-native gather, receipt, and citation projection.
   - Apply the approved 29-test disposition.
   - Run focused and full backend suites.
   - Measure actual AIS rule JSON/input size after wiring.
   - Do not claim “always smaller” without paired evidence.

3. Release Integration after backend contract stability.
   - Update `apps/consume-demo`.
   - Add tag-first runtime guards and 13+ shape/refusal/control tests.
   - Run frontend tests and TypeScript checking.

4. Rerun rule arms after correction.
   - Existing B/D/F are defective baselines.
   - Build a migrated harness for native `rules[]`.
   - Decide whether to rerun B/D/F only or all six AIS arms for strict contemporaneous comparison.
   - Print new results in tables.

5. Complete Azure production local auth.
   - Finish SPA, Bicep/azd, Easy Auth scope, operator lifecycle, deployment docs, and cleanup.
   - Resolve five owned full-suite failures.
   - Keep eight suspected inherited ambient-config failures explicitly separated unless directly proven.
   - Perform offline backend/frontend/IaC validation.
   - Review and commit the completed Azure changes.
   - Do not deploy or mutate Key Vault without separate authorization.
</next_steps>