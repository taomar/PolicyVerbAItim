<overview>
The user is coordinating a local-only migration and remediation of PolicyVerbAItim, prioritizing accurate policy/rule retrieval, truthful Consume API behavior, production local authentication, and reliable evaluation. Work is orchestrated across parallel Sol/xhigh sessions, while repository writers remain serialized; fixes must be generalized, never AIS/file/data-specific, and long operations must print progress.
</overview>

<history>
1. **Oversight migration and preservation**
   - Migrated coordination into local parent `policy-extractor-local-oversight`.
   - Preserved handovers and shared-checkout ownership rules.
   - Earlier Azure deployment work was preserved in commit `a17525cad24b3af262290826eb9846f90acea9ae`.
   - No deployment, database/Search migration, Key Vault mutation, or live secret creation occurred.

2. **AIS six-arm matrix execution**
   - Ran 180 AIS calls: 10 questions × 3 repetitions × 6 arms.
   - All 180 returned HTTP 200; raw evidence and receipt accounting were valid.
   - Initial report presentation was corrected because provisional gates were shown without completed answer evaluation.
   - Final manual adjudication produced:
     - Combined historical reconciliation: 109 PASS / 71 FAIL.
     - Valid policy baseline A/C/E: 52 PASS / 38 FAIL.
     - Defective old rule mode B/D/F: 57 PASS / 33 FAIL.
   - B/D/F were excluded from intended rule-only conclusions because they expanded rule matches into parent policies and used policy fallback.

3. **Independent review of the 38 valid-policy failures**
   - Audited all 38 A/C/E failures individually with raw and telemetry hashes.
   - Historical replay showed no proven regression:
     - New data under the old rubric: 42/48, 87.5%.
     - Like-for-like historical AIS subset: 7/8, 87.5%.
     - The previously quoted global 17/20, 85% result was not fully comparable.
   - Final classification:
     - 27 true product failures.
     - 11 rubric errors.
     - 0 unresolved.
     - 0 proven regressions.
   - The 11 rubric errors were:
     - AIS-06 ×6: unsupported requirement that overtime approval be written.
     - AIS-02 ×5: unsupported pre-leave certificate requirement.
   - The remaining AIS-02 call was resolved as a true reasoning defect: entitlement did not establish immediate operational approval.

4. **Rubric provenance correction**
   - Built a fail-closed provenance guard preventing unsupported, heading-derived, or inferred criteria from becoming product failures.
   - Isolated guard passed 17/17 tests.
   - Created versioned harness `consume-api-provenance-harness/3.0.0`.
   - Harness validation included deterministic regeneration, mutation controls, no-network self-tests, and leakage scans.
   - Current corrected result is structurally enforced as 27 product failures / 11 rubric errors / 0 unresolved.
   - 113/128 criteria remain intentionally unscorable pending normative provenance.
   - Started three parallel provenance sessions covering deterministic slices 1–38, 39–76, and 77–113.

5. **True rule-only backend correction**
   - Replaced rule-first parent-policy expansion with native rule retrieval.
   - Rule mode now:
     - Issues no policy query.
     - Uses no policy fallback.
     - Returns native `rules[]`.
     - Never expands to parent policy bodies.
     - May add bounded related/override rules.
   - Separate retrieval envelopes:
     - `policy_retrieval_v1` → `policies[]`, no `rules`.
     - `rule_retrieval_v1` → `rules[]`, no `policies`.
   - Added tag-first, fail-closed route/OpenAPI behavior.
   - Added separate Full and Light rule decision envelopes and rule-native citations.
   - Added rule-specific receipt hashing sealing actual rule evidence.
   - Fixed all six independent integrity-review findings:
     - Policy-shaped nested citations.
     - Incomplete hash coverage.
     - Mixed payloads silently accepted.
     - Missing rule receipt reader/discriminator.
     - Nullable grounding and duplicate-rule ambiguity.
     - Missing receipt/mode/section invariants.
   - Additional fixes:
     - Rule Search outage now propagates as 503 instead of false no-match.
     - Exact byte budget includes selector-catalogue bytes.
     - Semantic score labels seal the score they name.
   - Final backend validation:
     - Full suite: 5,471 passed, 18 skipped, 0 failed.
     - Focused final review: 301/301.
     - Anti-corpus guards: 67/67.
   - Frozen projection measurement:
     - 1–12 rules.
     - Maximum exact transport: 39,562 UTF-8 bytes.
     - Rule payload smaller than policy payload in 6/10 fixtures.
     - No universal “rule mode is always smaller” claim.
   - Native live AIS Search was not rerun.

6. **Consume Demo integration**
   - Updated `apps/consume-demo` to parse and render native rule envelopes.
   - Added strict policy/rule union types and runtime shape validation.
   - Own collection must exist and be an array; empty is valid.
   - Opposite collection may be absent or empty for rolling compatibility; non-empty/malformed shapes fail closed.
   - Removed unchecked policy-envelope casting.
   - Added native rule rendering without parent grouping.
   - Prevented malformed-response diagnostics from copying raw policy/rule content into support clipboard details.
   - Validation:
     - New parser/render/leakage tests: 19/19.
     - Full Consume Demo suite: 260/260.
     - TypeScript: passed.
     - Mutation proof: weakening the parser caused exactly the expected five guard failures.
     - `apps/web` TypeScript: passed.
     - `apps/web` full baseline: 1,902/1,903; the single polling timeout passed 25/25 in isolation and was attributed to full-suite contention.
   - Exactly eight Consume Demo files were changed.
   - Work remains uncommitted in the shared working tree.

7. **Azure production local authentication**
   - Implemented explicit `local|entra` human-auth modes independently of machine API mode.
   - Added Key Vault-backed Argon2 credentials, RBAC, token/key rotation, bounded last-known-good behavior, secure HttpOnly cookies, CSRF, stale-cookie logout, spoof-resistant limiter containment, and one-replica local-mode enforcement.
   - Fixed nginx Host/SNI routing.
   - Added Entra private Blob token store, private endpoint/DNS, secure SAS flow, and v2 issuer/audience/scope predeploy validation.
   - Routed all direct SPA calls through one cookie/CSRF-aware fetch seam.
   - Disabled production docs/OpenAPI exposure.
   - Validation:
     - Backend/IaC/security: 69 passed.
     - Frontend auth/equivalent paths: 93 passed.
     - Full frontend: 1,821 passed.
     - Bicep, PowerShell parsing, lint, build, diff/secret scans, and security review passed.
     - Default backend: 4,975 passed, 21 skipped, 9 failures in untouched ambient-AI fixtures; the exact nine pass with complete synthetic process-only configuration.
   - Preserved in isolated commit:
     - `381586688f0337be15dcc1d42d2be7d4b0fe4936`
     - `Add production local authentication`
   - No push or live deployment occurred.
   - Local mode remains deliberate one-replica containment; horizontal scaling requires shared transactional lockout state.

8. **Generalized product-failure investigations**
   - AIS-04:
     - 8.7 ranks hybrid 6, semantic 17, fused 10.
     - 8.6 ranks 0 across all channels.
     - Query normalization and index absence/staleness were ruled out.
     - Semantic under-ranking is confirmed.
     - Lexical-versus-vector and indexed-content contributions require new telemetry before any fix.
   - AIS-08:
     - Strong semantic elbow selects rank 0 and leaves budget unused.
     - Coverage expansion is gated by enumerated ranking modes and excludes semantic ordering.
     - Planned generalized fix derives eligibility from `cut applied && budget unspent`, without changing thresholds or budgets.
   - AIS-09:
     - Both required policies reach the gather intact.
     - The model cites only one; postprocessing does not remove the second.
     - Root cause is missing composition-completeness contract.
   - AIS-03:
     - Ordered table headers and cells coexist initially.
     - `_table_to_blocks` collapses cells into pipe-joined text.
     - Canonical persistence loses row/cell positions and header-value mappings.
     - Later extraction cannot reconstruct occurrence ordinality.
   - AIS-02:
     - General decision contract: entitlement does not imply immediate approval.
     - Correct behavior preserves entitlement and later evidence obligations but returns `not_settled_by_rules` for present approval when rules are silent.
     - No invented missing certificate.

9. **Current Payload implementation**
   - `Payload and full-cycle verification` owns the shared checkout.
   - Initial composition patch added sealed cited/uncited disclosure and passed:
     - Guard shard: 68.
     - New composition tests: 15.
     - Regression shard: 163.
   - Parent rejected disclosure-only as a complete resolution because it exposed omission without preventing incomplete successful answers.
   - Current approved architecture:
     - Atomically bump `ai-case-intent` prompt v15 → v16.
     - Require model-declared total evidence/subpart dispositions.
     - Validate totality, citation ownership, and coverage.
     - Missing/incomplete/relevant-unused dispositions fail closed to `not_settled_by_rules`.
     - No new verdict status.
     - Update 14 affected test files/82 payload sites.
     - Preserve legacy receipt hashes.
   - Payload is implementing this before the entitlement/approval and coverage fixes.

10. **Session cleanup and orchestration**
    - Completed sessions were archived, including Rule Retrieval, Consume Demo, Azure, matrix, audit, rubric guard, and investigation sessions.
    - Active repository writer: Payload.
    - Active parallel artifact sessions:
      - Criterion provenance batch 1.
      - Criterion provenance batch 2.
      - Criterion provenance batch 3.
    - User preferences stored and propagated:
      - Automatically parallelize independent work.
      - Serialize writers sharing a checkout.
      - Long tests/executions must print progress.
      - Never implement AIS/file/question/provision/data-specific fixes.
</history>

<work_done>
Completed:
- [x] Local oversight migration and handover preservation.
- [x] AIS 180-call matrix and final adjudication.
- [x] Independent 38-call failure audit.
- [x] Historical comparison proving no measured regression.
- [x] Rubric provenance guard and versioned harness v3.
- [x] Native rule-only retrieval backend.
- [x] Full/Light rule receipts, citations, hashes, persistence, replay, and OpenAPI.
- [x] Consume Demo native rule parser/rendering integration.
- [x] Azure production local-auth implementation and isolated commit.
- [x] Root-cause investigations for AIS-02/03/04/08/09.
- [x] Generalized implementation blueprint.
- [x] Read-only commit-decomposition audit.

Current shared checkout:
- Repository: `C:\Users\taomar\Downloads\policy-extractor-local-oversight\repository`
- HEAD: `c0972c8bb7ba811903e981d3806afe31cc1f514d`
- Branch: `main`
- Dirty shared tree; no shared commit, staging, push, reset, stash, or clean.
- Last commit-audit snapshot observed 113 dirty entries and an empty index; Payload has modified the tree afterward.
- Whole-file staging is unsafe because several files mix Rule, Consume Demo, Payload, and older work.

Current implementation:
- [ ] Model-declared composition-completeness contract, prompt v16.
- [ ] General entitlement-versus-approval enforcement.
- [ ] Property-derived multi-part coverage expansion.
- [ ] Ranking-component telemetry.
- [ ] Canonical table-structure carrier.
- [ ] Normative provenance for 113 currently unscorable criteria.
- [ ] Safe scoped commits for shared-checkout work.

Known issues:
- No live native-rule AIS rerun has occurred.
- No client-side live HTTP arm-F run has occurred.
- Existing data will not gain table ordinality without separately authorized re-extraction.
- Shared tree contains unknown/mixed ownership paths.
- A withdrawn `llm_reasoning_view` experiment/test/quarantine must not be committed.
</work_done>

<technical_details>
- **Rule retrieval limits**
  - Azure Search scan: up to 200 rule hits.
  - Semantic reranker window: up to 50.
  - Final selected/delivered rules: 0–12.
  - Absolute relevance floor: 1.75.
  - Exact serialized UTF-8 cap: 40,000 bytes.
  - Whole-rule boundaries only; omissions are named.
  - Oversize first rule raises typed refusal rather than false empty result.

- **Receipt architecture**
  - `case_decision_rule_v1` and `case_decision_rule_light_v1` are separate from policy receipts.
  - Rule citations carry source identifiers only, never policy bodies.
  - Rule hash seals rule IDs, grounding/admission state, source identity, dispositions, decision tracks, citations, request/executed mode, and other integrity-relevant fields.
  - Historical V1/V2 receipts remain parseable and verifiable unchanged.
  - Mixed/unknown shapes fail closed.

- **Consume Demo parser**
  - Discriminates on `schema_version`.
  - Required own array distinguishes legitimate empty negative from malformed payload.
  - Opposite array must be absent or empty.
  - Unknown tag, missing own collection, non-array own collection, or mixed non-empty opposite collection fails visibly.
  - Diagnostics expose structural summaries only.

- **Evaluation integrity**
  - Only criteria with normative source/rule provenance may create product failures.
  - Heading-derived, question-inferred, unsupported, unavailable, or pending-human criteria remain rubric errors/unscorable.
  - AI review must never be represented as human semantic confirmation.
  - Old-rubric replay is labeled non-equivalent.

- **Generalization constraints**
  - AIS is a regression witness only.
  - No production logic may contain AIS IDs, provision IDs, source filenames, question strings, observed scores/ranks, or corpus-tuned thresholds.
  - Anti-corpus AST guards must cover every modified executable module.
  - Numeric leakage guard was expanded from integers to integers/floats while excluding booleans.
  - Required controls include synthetic, second-corpus/HW, non-Latin, inversion, mutation, recall, and precision cases.

- **Long-command requirement**
  - No silent long-running test or execution.
  - Use visible reporters, bounded shards, or periodic progress checkpoints.
  - Avoid buffered pipelines that withhold output until completion.

- **Commit safety**
  - Commit-decomposition audit:
    - Rule files, Consume Demo files, Payload files, unrelated files, and unknown/mixed files coexist.
    - `case_decision.py` and `policy_case_decision.py` are now mixed Rule+Payload files.
    - Several Consume Demo files also contain earlier changes.
    - Final staging should use explicit cached patches/hunks after Payload releases the lock.
    - Unknown ownership must be excluded rather than guessed.
</technical_details>

<important_files>
- `repository\src\policy_platform\contracts\policy_retrieval.py`
  - Separate policy/rule retrieval envelopes and native rule records.

- `repository\src\policy_platform\contracts\case_decision.py`
  - Policy and rule receipt contracts, hash preimages, rule citations, strict invariants.
  - Currently also contains Payload’s optional composition-disposition substrate.

- `repository\src\policy_platform\contracts\case_decision_light.py`
  - Separate policy/rule Light envelopes.

- `repository\src\policy_platform\infrastructure\assistants\ai_case_project.py`
  - Rule-only selection, no-policy-query branch, neighbour expansion, exact byte budgeting, coverage selection.

- `repository\src\policy_platform\infrastructure\assistants\ai_case_intent.py`
  - Decision gather/model contract.
  - Current target for prompt v16 and composition-completeness enforcement.

- `repository\src\policy_platform\application\policy_case_decision.py`
  - Builds/persists/replays Full and Light envelopes.
  - Currently mixed Rule+Payload ownership.

- `repository\src\policy_platform\api\routers\policy_decisions.py`
  - Discriminated policy/rule route response models and OpenAPI.

- `repository\src\policy_platform\infrastructure\projection\policy_rule_slice.py`
  - Rule-neighbour and rule-slice projection.

- `repository\src\policy_platform\infrastructure\document_ingestion.py`
  - `_table_to_blocks` is the earliest observed legacy table-cell positional loss.

- `repository\tests\unit\test_no_m2_code_is_shaped_around_a_corpus.py`
  - Central anti-corpus AST guard; now checks integer and float measured values.

- `repository\tests\unit\test_held_evidence_is_accounted_for.py`
  - New Payload composition tests; current disclosure layer is containment pending full v16 contract.

- `repository\tests\unit\test_rule_mode_returns_rules_not_policies.py`
  - Native rule contract, budget, hash, strictness, and compatibility coverage.

- `repository\tests\unit\test_the_retrieval_route_answers_in_the_shape_the_mode_asked_for.py`
  - Real route/OpenAPI policy/rule discrimination tests.

- `repository\apps\consume-demo\src\contracts\caseDecision.ts`
  - TypeScript policy/rule retrieval union and runtime parser.

- `repository\apps\consume-demo\src\lib\apiClient.ts`
  - Replaced unchecked policy cast with verified retrieval result.

- `repository\apps\consume-demo\src\components\RuleRetrievalResult.tsx`
  - Native rule rendering.

- `repository\apps\consume-demo\src\retrievalEnvelopeIsParsedByTag.test.tsx`
  - Parser, malformed-shape, render, leakage, and controls.

- `repository\AGENT_PROGRESS.md`
  - Rule milestone 73 completion and architecture/validation record.

Key artifacts:
- Final matrix report:
  - `C:\Users\taomar\.copilot\session-state\b9e79289-63de-4596-8a76-88064fb51cf8\files\consume-api-matrix-ais\runs\consume-api-ais-six-arm-20260904\reports\postflight\adjudicated\ADJUDICATION_REPORT.md`
  - SHA `ed9a9e141d983829c88d39aa7d272a471dfcce395657acdf7cd4087e6301be65`

- Authoritative 38-row audit:
  - `C:\Users\taomar\.copilot\session-state\0fb0b358-89fc-46d2-89cb-04d162e75ff3\files\ACTIONABLE_POLICY_FAILURE_AUDIT.md`
  - SHA `a46099c8a187fbca985300097f962561c5d6c2c9b6fe4b921b03c7a436e6923a`

- Final remediation blueprint:
  - `C:\Users\taomar\.copilot\session-state\5a06fec2-12cd-4477-b574-4d18ab814907\files\IMPLEMENTATION_BLUEPRINT_26_TRUE_FAILURES.md`
  - Filename intentionally remains stable; content reflects 27/11/0.

- Rule measurement:
  - `C:\Users\taomar\.copilot\session-state\eeeb738a-4e41-4fdb-ba8a-7e9946183ab3\files\RULE_RETRIEVAL_MEASUREMENT.md`

- Versioned provenance harness:
  - `C:\Users\taomar\.copilot\session-state\135cb788-7072-4c5f-84d0-7458aba79def\files\consume-api-provenance-harness-v3.0.0`
  - Payload SHA `fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`

- Commit-decomposition audit:
  - `C:\Users\taomar\.copilot\session-state\ad57ae08-1a8d-4ad3-b853-af391de7868f\files\COMMIT_DECOMPOSITION_AUDIT.md`
  - SHA `888d0ae8bf12c65310bcf3e454ad8b571b18c06155b5f23055a03f16116431e4`

- Azure implementation handoff:
  - `C:\Users\taomar\.copilot\session-state\e1fe8465-c0af-4522-987d-84a5f30c75bf\files\PRODUCTION_LOCAL_AUTH_IMPLEMENTATION.md`
  - Commit `381586688f0337be15dcc1d42d2be7d4b0fe4936`
</important_files>

<next_steps>
1. **Payload repository work**
   - Complete atomic prompt-v16 composition contract.
   - Run visible, bounded targeted tests.
   - Implement generalized entitlement-versus-approval behavior.
   - Implement property-derived semantic coverage expansion.
   - Run focused and full backend suites with visible progress.
   - Return checkout lock with exact file/result handoff.

2. **Criterion provenance batches**
   - Finish three deterministic slices covering all 113 unscorable criteria.
   - Preserve unsupported, unavailable, structural, and pending-human criteria as unscorable.
   - After all three finish, create a merge/validation session.
   - Produce a new canonical harness revision and source-hash manifest.

3. **Later serialized repository work**
   - Add general lexical/vector/semantic/fusion telemetry before changing AIS-04 ranking.
   - Add canonical table row/cell/header mappings.
   - Do not re-extract existing data without separate authorization.

4. **Commit preparation**
   - Re-run commit decomposition after Payload releases the lock.
   - Stage by verified hunks/patches, not whole mixed files.
   - Exclude unknown/unrelated paths and withdrawn `llm_reasoning_view` work.
   - Prepare coherent Rule, Payload, and Consume Demo commits with required tests.
   - Do not push unless authorized.

5. **Future controlled validation**
   - Adopt the provenance harness for future runs.
   - Native A/C/E and corrected rule-mode reruns require live-call authorization.
   - Use n≥5 where model variability matters.
   - Re-extraction and Azure deployment remain separate authorization gates.
</next_steps>