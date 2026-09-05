<overview>
The user requested a safe migration of PolicyVerbAItim oversight into a local-only parent, preservation of Azure deployment work, completion of the rule-retrieval investigation, and a comprehensive Consume API benchmark. Work is coordinated through specialized child sessions with strict shared-checkout serialization, source-grounded correctness evaluation, and no unapproved live mutations.
</overview>

<history>
1. The user ordered migration from retiring oversight session `8437f3da-491a-4139-b979-8b00996c8953`.
   - Read all seven migration Markdown artifacts and their cited handovers.
   - Independently verified Git, Alembic, DB/Search state, source files, ports, and Azure endpoints.
   - The repository project rejected child creation because saved repo `taomar/policyAIengine` conflicts with origin `taomar/policy-governance-engine`.
   - Preserved the origin and created four successors under local-only project `398fea1a-f058-481a-8546-dc08cfa1eb6f`.

2. The user asked what remained pending.
   - Reported incomplete Rule Retrieval disclosure/attribution, unapplied index migration, mixed uncommitted shared-tree work, and Azure risks.
   - Established edit order: Integration quiet first, Rule Retrieval second, Payload validation last.

3. The user asked whether rule retrieval’s higher token/time investigation was unfinished and ordered Azure work halted and committed.
   - Confirmed stage-one cardinality fix was complete but residual extra-parent cost remained.
   - Halted and archived Azure successor.
   - Committed exactly nine verified Azure deployment files as `a17525cad24b3af262290826eb9846f90acea9ae`, message `Fix reproducible Azure deployment`.
   - No push, merge, redeployment, teardown, or live Azure mutation followed.

4. The user requested a six-arm Consume API report:
   - 10 AIS and 10 HW questions.
   - Three repetitions each.
   - Questions spanning complex mixed scenarios, information, verdict, light questions, and one irrelevant question per corpus.
   - Arms:
     - A: Decision Light, policy retrieval.
     - B: Decision Light, rule retrieval.
     - C: Full Decision, policy retrieval.
     - D: Full Decision, rule retrieval.
     - E: JSON-only retrieval, policy mode.
     - F: JSON-only retrieval, rule mode.
   - Required fields: question, latency, tokens, input/output size, answer/information/verdict, correctness evaluation, and consistency.
   - Requested that rule-path defects be investigated/fixed before measurement and existing evidence reused where valid.

5. Consume API orchestration was established.
   - Integration audited endpoints/contracts.
   - Payload developed the source-grounded question rubric.
   - Rule Retrieval began disclosure/fix work.
   - New Matrix Runner inventoried historical artifacts and designed the final harness.
   - Historical runs were classified as baseline-only; none qualify as official final rows.

6. Integration completed its contract audit and released shared files.
   - Confirmed four endpoints cover all six requested arms:
     - A/B: `POST /api/policy-decisions/{key}/case/light`
     - C/D: `POST /api/policy-decisions/{key}/case`
     - E/F: `POST /api/policy-decisions/{key}/policies`
     - `rule_retrieval=false/true` selects policy/rule mode.
   - Declared `case_decision.py`, `policy_case_decision.py`, `case_decision_light.py`, `policy_decisions.py`, `policy_retrieval.py`, `schemas.py`, `api.ts`, and `App.tsx` quiet.
   - Found that Light responses did not echo requested/executed retrieval mode.
   - Found unrelated duplicate-operation-ID error reporting defect; documented but deferred.

7. Rule Retrieval completed Phase A and was unblocked for Phase B.
   - Found existing score-disclosure patch was inert: `_score_disclosure` existed but was never called.
   - Candidate fields were silently dropped by `PolicyRef`/`_policy_ref`.
   - Found policy-mode rescue path incorrectly labels max-over-child-rule semantic score as ordinary semantic.
   - Prepared atomic E1–E8/T1–T12 plan covering both envelope versions, citations, historical parsing, no silent drops, hash compatibility, unchanged selection, and recall controls.
   - Was explicitly authorized to implement the atomic disclosure correction plus minimal additive Light mode echo.
   - Selection thresholds/statistics remain frozen until measurement confirms a correction.

8. Payload completed source/index verification and the evaluation rubric.
   - Confirmed AIS: 293 rules, 39 provisions, 362 clauses, 332 content docs, ready manifest.
   - Confirmed HW: 189 rules, 60 provisions, 193 clauses, 249 content docs, ready manifest.
   - Confirmed receipt count remained 164 at that check.
   - Final question proposal retains seven substantive historical questions plus one stable irrelevant per corpus and adds:
     - AIS probation evaluation.
     - AIS leave/travel composition.
     - HW approval thresholds.
     - HW executive refresh override.
   - Added required `expected_evidence_miss` reporting.
   - Identified wrong-provision retrieval as a major failure mode.

9. Matrix Runner completed inventory/design.
   - Found 22 run files, 440 normalized historical call rows, and four full-receipt fixtures.
   - Historical data is baseline-only due missing third repetitions, incomplete arm coverage, missing byte metrics, pre-fix Rule data, and different rubrics.
   - Designed 360 primary calls: 20 questions × 3 repetitions × 6 requested API arms.
   - A–D create 240 receipts; E/F create none.
   - Added per-job atomic artifacts, watchdogs, suspension detection, balanced ordering, exact byte accounting, and source-grounded derived evaluation.

10. The user showed an Azure login failure screenshot and requested diagnostics in a sub-session.
   - Created read-only child `e1fe8465-c0af-4522-987d-84a5f30c75bf`.
   - It is diagnosing why the production login form rejects local credentials.
   - Known evidence: production startup refuses local-account authentication, Entra was deployed disabled, yet the frontend still presents local login.

11. Latest Payload message introduced a critical misunderstanding.
   - Payload incorrectly redefined A–F as `reasoning_effort × retrieval mode` and proposed 240 calls with two repetitions.
   - This contradicts the user’s explicit six endpoint arms and three repetitions.
   - Matrix Runner and Integration have the correct interpretation: six API response surfaces, 360 primary calls.
</history>

<work_done>
Files created outside the repository:
- `C:\Users\taomar\.copilot\session-state\b065f09b-2a4c-479f-a012-e6e55f388234\files\PARENT_SUCCESSOR_HANDOVER.md`
- Payload:
  - `...\5a06fec2-12cd-4477-b574-4d18ab814907\files\CONSUME_API_EVALUATION_RUBRIC.md`
  - `...\5a06fec2-12cd-4477-b574-4d18ab814907\files\CHILD_PAYLOAD_SUCCESSOR_HANDOVER.md`
- Integration:
  - `...\94102b91-353f-46f3-a59b-72d8381912f9\files\CHILD_INTEGRATION_SUCCESSOR_HANDOVER.md`
- Rule Retrieval:
  - `...\7d783c45-9dd4-49c8-bdc0-ad43f0192148\files\CHILD_RULE_RETRIEVAL_SUCCESSOR_HANDOVER.md`
  - `...\7d783c45-9dd4-49c8-bdc0-ad43f0192148\files\PHASE_B_PATCH_AND_TEST_PLAN.md`
- Matrix:
  - `...\9939b1b3-2fdf-4665-86b7-4211c7fa52de\files\consume-api-matrix\INVENTORY.md`
  - `HARNESS_DESIGN.md`
  - `manifest.pending.json`
  - `schemas\raw-result.schema.json`
  - `schemas\derived-result.schema.json`
  - `AGENT_PROGRESS.md`

Repository change completed:
- Azure deployment checkout committed at `a17525cad24b3af262290826eb9846f90acea9ae`.
- Nine files, 199 additions/98 deletions:
  - `.azure/deployment-plan.md`
  - `.dockerignore`
  - `apps/web/package-lock.json`
  - `azure.yaml`
  - `infra/main.bicep`
  - `infra/modules/container-apps.bicep`
  - `infra/modules/platform.bicep`
  - `infra/scripts/Invoke-PostDeployBootstrap.ps1`
  - `pyproject.toml`

Sessions:
- Parent: `b065f09b-2a4c-479f-a012-e6e55f388234`
- Payload: `5a06fec2-12cd-4477-b574-4d18ab814907`
- Integration: `94102b91-353f-46f3-a59b-72d8381912f9`
- Rule Retrieval: `7d783c45-9dd4-49c8-bdc0-ad43f0192148`
- Matrix Runner: `9939b1b3-2fdf-4665-86b7-4211c7fa52de`
- Azure Login Diagnostics: `e1fe8465-c0af-4522-987d-84a5f30c75bf`
- Azure deployment successor was archived.

Current task state:
- Completed: evidence inventory, Consume API contract audit, question/rubric definition.
- In progress: Rule Retrieval correction; offline six-arm harness implementation.
- Pending: live matrix, evaluation, final report.
</work_done>

<technical_details>
- Shared checkout:
  - `C:\Users\taomar\Downloads\policy extractor`
  - Branch `main`
  - HEAD `c0972c8bb7ba811903e981d3806afe31cc1f514d`
  - Origin `https://github.com/taomar/policy-governance-engine.git`
  - Initially 64 tracked + 37 untracked; Rule Retrieval’s authorized edits increased status entries.
- Local-only parent accesses checkout through `repository` junction.
- Alembic:
  - Live DB: `f4b8c2e97d31`
  - Repository head: `a1c5f0b3e284`
  - `policy_index_builds` migration remains unapplied.
- Live Search:
  - AIS: 39 policy + 293 rule + manifest.
  - HW: 60 policy + 189 rule + manifest.
  - Both ready, quality-passed, `all_published_rules_v1`.
- Historical Rule Retrieval result:
  - Default median retained policies: 1.
  - Rule median: 2.
  - Median residual: +2,390 tokens and +2,939 ms.
  - Stage-one fix removed unconditional five-policy saturation.
- Score disclosure:
  - Existing helper is inert.
  - `best_score` may mean semantic reranker, raw hybrid/RRF, policy RRF, rule-weighted RRF, or rescue max-over-child-rules.
  - Candidate disclosure must pass through typed receipt contracts or Pydantic silently drops it.
- Required Rule fix sequence:
  1. Complete additive disclosure and Light mode echo.
  2. Verify historical V1/V2 receipts and request hashes.
  3. Verify retained IDs/selection unchanged.
  4. Instrument lead/max semantic scores, cutoff/elbow, fallback, and coverage expansion.
  5. Measure.
  6. Only then consider lead-rule semantic elbow input, rule-only flat default one, or coverage-floor correction with recall controls.
- API metrics:
  - A/B and C/D token usage: `trace.token_usage`.
  - E/F token usage: top-level `token_usage`.
  - A/B and E/F expose top-level `latency_ms`.
  - C/D require wall-clock plus `trace.stage_latency_ms`.
  - Record raw response bytes and `Content-Length` separately.
  - `SizeRef` fields are characters, not bytes.
- Decision persistence:
  - A–D each persist a receipt.
  - E/F are retrieval-only and do not.
  - Official matrix therefore adds approximately 240 receipts.
- Rule-not-ready `503` is terminal evidence; never silently downgrade to policy retrieval.
- Existing 20×2 runs cannot be mixed into official final results.
- One historical 20,577,488 ms latency was Windows Modern Standby suspension; preserve raw, exclude from causal latency statistics.
- Azure login:
  - `POST /api/auth/login` returns 404 when local accounts are disabled, 401 for invalid credentials.
  - Production startup explicitly refuses `LOCAL_ACCOUNTS_ENABLED=true`.
  - Azure deployment had `AZURE_ENABLE_ENTRA_AUTH=false`.
  - Local `.local-accounts.txt` credentials are development-only and should not work on production Azure.
- Never expose credential contents in chat.
</technical_details>

<important_files>
- `PARENT_SUCCESSOR_HANDOVER.md`
  - Durable parent hierarchy, state verification, mappings, risks, serialization rules, and Azure commit update.

- `CONSUME_API_EVALUATION_RUBRIC.md`
  - Source-grounded 20-question set and R1–R10 rubric.
  - Its latest §9 A–F reinterpretation is wrong and must be corrected back to endpoint arms.

- `CHILD_INTEGRATION_SUCCESSOR_HANDOVER.md`
  - Authoritative A–F endpoint contract, field locations, persistence behavior, and quiet-file release.

- `PHASE_B_PATCH_AND_TEST_PLAN.md`
  - Atomic Rule Retrieval disclosure and compatibility plan.

- `src\policy_platform\infrastructure\assistants\ai_case_project.py`
  - Retrieval ranking, score kinds, cardinality cuts, disclosure helper, rescue paths.

- `src\policy_platform\contracts\case_decision.py`
  - `PolicyRef`, V1/V2 envelopes, citations, request hash behavior.

- `src\policy_platform\application\policy_case_decision.py`
  - `_policy_ref`, receipt construction, retrieval field allow-list.

- `src\policy_platform\contracts\case_decision_light.py`
  - Light response projection; currently being changed to echo retrieval mode.

- `src\policy_platform\api\routers\policy_decisions.py`
  - Defines `/case`, `/case/light`, and `/policies`.

- Matrix artifacts under:
  - `C:\Users\taomar\.copilot\session-state\9939b1b3-2fdf-4665-86b7-4211c7fa52de\files\consume-api-matrix`
  - Correct 360-job six-endpoint design and schemas.

- Historical runs:
  - `...\8437f3da-491a-4139-b979-8b00996c8953\files\runs`
  - `...\58f19b59-6aa9-4d38-8782-46cbdc7640c5\files\runs`
</important_files>

<next_steps>
1. Immediately correct Payload:
   - A–F are the user’s six endpoint/response arms, not reasoning-effort combinations.
   - Three repetitions, not two.
   - Official total is 360 primary calls.
   - Reasoning effort should remain one controlled value, preferably production-default `medium`, across A–D.

2. Confirm Matrix Runner’s offline harness uses:
   - 20 questions × 3 repetitions × six API arms.
   - Correct contract field extraction.
   - 240 receipt-writing decision calls.
   - E/F non-persistent retrieval calls.
   - `expected_evidence_miss` beside correctness rates.

3. Wait for Rule Retrieval Phase B report.
   - Review exact diff/tests.
   - Confirm Light mode echo and per-candidate disclosure are visible.
   - Confirm hashes, historical parsing, and retained IDs are unchanged.
   - Do not start live matrix until stable.

4. After disclosure stability:
   - Run attribution harness.
   - Decide whether any selection correction is justified.
   - If changed, rerun focused tests and stabilize again.

5. Have Payload run final combined backend validation only after Rule Retrieval is quiet.
   - Avoid concurrent frontend/backend suites.
   - Reconfirm sparse `rule_retrieval` request-hash behavior.

6. Obtain/record explicit authorization for the 240 receipt-writing decision calls before opening the live matrix window.
   - The user requested the matrix, but Payload requested a distinct mutation confirmation.
   - Announce the execution window and expected receipt increase from 164 to roughly 404.

7. Run the resumable 360-call matrix, evaluate results, and publish the detailed per-question and aggregate report.

8. Collect Azure Login Diagnostics result and report the root cause/remediation separately without resuming general Azure deployment work.
</next_steps>