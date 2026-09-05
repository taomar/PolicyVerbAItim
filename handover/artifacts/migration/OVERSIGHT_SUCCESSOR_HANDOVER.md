# PolicyVerbAItim v3 Oversight Successor Handover

Prepared: 2026-09-04

## 1. Purpose

This document transfers the complete oversight state from session
`8437f3da-491a-4139-b979-8b00996c8953` to a new top-level project session.

The new session must remain an oversight coordinator. It audits direct evidence,
assigns bounded work, prevents concurrent edits in the shared checkout, and does
not silently replace worker reports with facts.

## 2. Safety rules

1. A negative claim needs direct evidence exactly like a positive one.
2. Never use PowerShell `**` with `-Path`; use repository grep or
   `Get-ChildItem -Recurse`.
3. Before saying a file is missing, search the expected tree and, when relevant,
   the machine/session-artifact tree.
4. Before calling a test failure environmental, check ambient `.env` inheritance.
5. Before calling a failure pre-existing, inspect the actual diff and baseline.
6. DB `built_at` is not live Azure Search readiness. Read both independently.
7. Never print or preserve secrets from `.env`, Key Vault, request headers, logs,
   connection strings, tokens, or generated subscription keys.
8. Do not commit, push, reset, stash, clean, switch branches, or rewrite history
   without explicit user authorization.
9. Do not run backend and both frontend suites concurrently. Vitest worker
   startup timeouts in this checkout have been caused by CPU contention.
10. No caching or memoization in the decision path.
11. No corpus-, project-, index-, page-, language-, or domain-specific behavior.
12. A validation guard requires a refusal test and a control proving it does not
    refuse everything.
13. Announce destructive mutation windows before opening them.
14. The 10-minute scheduled oversight audit was explicitly stopped.

## 3. Project and session topology

Configured project:

- Project ID: `f8d6ba17-9121-4470-8a09-7dc2ecbe9cef`
- Saved repository: `taomar/policyAIengine`
- Shared checkout: `C:\Users\taomar\Downloads\policy extractor`
- Required worker workspace type: `branch`

Origin mismatch:

- Normal shared-checkout origin:
  `https://github.com/taomar/policy-governance-engine.git`
- `create_session` is accepted only while origin temporarily points to:
  `https://github.com/taomar/policyAIengine.git`
- Restore the normal origin immediately after every session creation.

Session map:

| Role | Session ID | Primary artifacts |
|---|---|---|
| Original V3 predecessor | `58f19b59-6aa9-4d38-8782-46cbdc7640c5` | `files\OVERSIGHT_HANDOVER.md`, `PAYLOAD_HANDOVER.md`, `INTEGRATION_HANDOVER.md`, `AZURE_DEPLOY_HANDOVER.md`, harnesses and baseline runs |
| Retiring oversight | `8437f3da-491a-4139-b979-8b00996c8953` | this package, checkpoints, upload/publish/index artifacts, matrix runs |
| Payload worker | `8e46052e-8e8b-4ae5-9f04-752ad175c795` | `files\HANDOVER.md`, rebuild logs/results, visual probes |
| Integration worker | `bb565e7e-96a3-44c4-94dd-85d5f9d2f0dc` | `files\HANDOVER.md`, `VERIFICATION_FINDINGS.md`, `migration_probe2.py` |
| Azure Deploy worker | `bb2a8cbc-e4f0-44ac-ba5e-cc8e80b1c15f` | `files\AZURE_DEPLOY_SESSION_HANDOVER.md`, `AZURE_DEPLOY_RUN_LOG.md`, `AZURE_DEPLOY_VERIFICATION.md` |
| Rule Retrieval investigator | `fbae4b69-cd04-4c75-b346-86688320f68f` | `files\HANDOVER-rule-retrieval-investigation.md` |

An incorrectly nested successor, project-session ID
`fa724b93-b7f4-4306-b10e-61ddc539dee2`, was archived. It produced no artifact
files and must not be treated as the successor.

The session API always preserves a parent-child relationship. Therefore the new
top-level parent must be created manually from the Policy Extractor project UI.
Once it exists, it can create the mapped children under itself.

## 4. Direct current snapshot

Verified directly on 2026-09-04:

- Shared checkout branch: `main`
- HEAD: `c0972c8bb7ba811903e981d3806afe31cc1f514d`
- Tracked changed files: 64
- Untracked files: 37
- Total status entries: 101
- Origin remains
  `https://github.com/taomar/policy-governance-engine.git`.
- The new top-level parent is created through a manual workflow bound to host
  `local` and root `C:\Users\taomar\Downloads\policy extractor`; it is not a
  cloud/GitHub session.
- No commit, push, reset, stash, clean, or branch switch was performed by
  oversight.

Alembic:

- Live local DB current: `f4b8c2e97d31`
- Repository head: `a1c5f0b3e284`
- The new index-progress/history migration is not applied to the live local DB.
- Exactly one `PolicyIndexBuild` model and one
  `a1c5f0b3e284_policy_index_builds.py` migration were directly verified.
- Model and migration have 36 columns; `active_slot` exists.

Local ports:

- 8010: listening, PID 56832, not owned by retiring oversight.
- 8051: listening, PID 49636, not owned by retiring oversight.
- 8070: stopped by retiring oversight after matrix completion.

## 5. Current DB and Search state

Verified directly:

| Project | Source docs/versions | Active rules | DB index state | Content docs | Search live |
|---|---:|---:|---|---:|---|
| `ais-e2e` | 1 / 1 | 293 | built | 332 | 39 policy + 293 rule + 1 manifest = 333 |
| `hw-policy` | 1 / 1 | 189 | built | 249 | 60 policy + 189 rule + 1 manifest = 250 |

Both Search manifests are:

- `manifest_state=ready`
- `quality_state=passed`
- `rule_index_scope=all_published_rules_v1`
- readiness probe `true`
- expected/uploaded/live counts agree.

DB timestamps:

- AIS built at `2026-09-03T20:25:49.981736Z`
- HW built at `2026-09-03T21:21:49.373137Z`

Decision receipt count at the final direct snapshot: 164. This is an observation,
not a fixed target; matrices and direct checks legitimately added receipts.

Both source artifacts remain present:

- `data\documents\b7e1c4a2-3f6d-4a91-8c25-0d3e7f184b6a_v1_AIS_Employee_Handbook-1.pdf`
- `data\documents\ad020e51-7f0a-49e0-bbdc-7a6e34054803_v2_Workplace-Hardware-Provisioning-Policy-v3.3.docx`

## 6. Payload, extraction, publication, and indexing work

### Completed generalized fixes

1. Non-empty error descriptions for message-less transport exceptions.
2. Azure OpenAI/Search bounded retries and split transport/read timeouts.
3. Exact literal protection through rendering:
   - number and identifier spans are derived from the same predicates as guards;
   - markers are letters-only and inert to number/identifier predicates;
   - protected occurrences are one-to-one;
   - preservation-rejected multi-item batches split deterministically and retry
     as smaller calls;
   - a single unfaithful item still fails closed.
4. Shared rule-index scope and exact expected rule-document counts between build
   and quality validation.
5. Warning-only residual interleaving detector shared by upload and rebuild.
6. Selective GPT-5.6-SOL visual tie-breaker:
   - deterministic extraction remains primary;
   - only detector-flagged table pages are sent;
   - ordinary multilingual pages make zero model calls;
   - output is accepted only as a replayable permutation of parser characters;
   - Unicode whitespace is structural and silently normalized;
   - one targeted retry may use parser cells as secondary evidence;
   - no source text appears in diagnostics;
   - replay provenance survives clause persistence and canonical reconstruction.
7. Truthful upload progress with real stages/counters, server authority, terminal
   lifecycle, reduced-motion support, and one live region.

### Fresh full cycles

AIS:

- Reset/recreated through supported API.
- Uploaded through normal multipart route.
- 362 clauses persisted and authoring-indexed.
- SOL pages: 21, 22, 23, 25, 26.
- SOL calls attempted/succeeded: 16/14.
- Damaged rows recovered/refused: 9/2.
- Two refused rows stayed original with explicit warnings.
- AI extraction: 293 candidates from all 362 clauses.
- Bulk approved: 293, skipped 0.
- Published active version 1, effective from 2026-08-24.
- First automatic index attempt failed before manifest because one two-item
  rendering batch lost protected markers.
- General multi-item preservation split fix was added and verified.
- Repair rebuild succeeded: 39 policy + 293 rule; ready and quality-passed.

HW:

- Reset/recreated through supported API.
- Uploaded real DOCX through normal route.
- 193 clauses; no ingestion diagnostics; zero visual SOL calls.
- AI extraction: 189 candidates.
- Bulk approved: 189, skipped 0.
- Published active version 1, effective from 2026-08-27.
- Automatic index build succeeded: 60 policy + 189 rule; ready and
  quality-passed.

### Candidate-quality observations

- AIS: 50 deterministic findings, including 14 high. Optional AI review was
  throttled by Azure 429 and did not run. Findings were advisory.
- HW: 30 findings, including 23 high; AI review completed. Findings were
  advisory.

Do not round these into "quality clean." Projection quality passed; candidate
quality still recorded advisory findings.

## 7. JSON and decision measurements

### Stored/served JSON

HW identical `/policies` scenario:

- Decoded JSON: 20,508 -> 13,015 bytes, reduction 36.5%.
- Gzip transfer: 3,453 -> 3,033 bytes, reduction 12.2%.

Normalized payload observations:

- AIS average policy payload: -0.88%.
- AIS p95 policy payload: -13.42%.
- AIS total payload: +1.73% because policies/rules increased.
- HW total published payload: -46.72%.
- HW total structured rule JSON: -46.96%.
- HW max policy payload: -10.86%.

Search total bytes are not a payload-reduction metric after all-rule indexing:

- AIS Search total +5.33% with more rules.
- HW Search total +124.69% because the old index held zero rule documents and
  the new one holds 189.
- Per-document p95 still fell 1.60% AIS and 5.61% HW.

### Baseline and fresh matrices

Prior Terra baseline:

- 20 scenarios x 2 repetitions = 40 calls.
- 40/40 successful; 17/20 scenario passes.
- p50 25,721 ms; p95 39,607 ms; median tokens 14,402.

Fresh default:

- 40/40 successful; 17/20 passes.
- p50 17,234 ms (-33.0%).
- p95 37,724 ms (-4.75%).
- median tokens 10,964 (-23.87%).
- 40/40 hash, Full-Light identity, citation, usage, and stage integrity.

Pre-cardinality-fix rule mode:

- 40/40 successful; 16/20 passes.
- p50 28,229 ms.
- p95 46,866 ms.
- median tokens 29,741.
- Rule mode always retained five policies. This was a defect.

First cardinality fix:

- Added evidence-based semantic elbow for rule parents.
- Bounded policy fallback by evidence and remaining capacity.
- Restored duplicate-collapse coverage expansion for rule order.
- Full unit suite reported 5,348 passed / 18 skipped.
- Independent focused verification: 534 passed.

Post-fix paired matrix:

- 40 default + 40 rule, interleaved order.
- Default: median retained 1.0, p50 tokens 11,552.
- Rule: median retained 2.0, p50 tokens 15,303.
- Both 17/20 scenario passes and 40/40 integrity.
- Paired median residual: +1 retained policy, +2,390 tokens, +40 light-response
  bytes, +469 full-receipt bytes, +2,939 ms.
- One default call recorded 20,577,488 ms because Windows entered Modern Standby
  at 02:07 and resumed 11:34. Exclude that call from causal statistics.

The first fix removed per-policy inflation. At equal retained cardinality, token
cost is approximately equal by mode. Remaining cost is additional parents.

## 8. Rule Retrieval status and ordered next work

### Completed stage 1

The original defect was an absent cardinality cut. Rule mode ordered every
parent, appended fallback, then let the budget of five become the selector.
This was fixed and tested.

### Verified remaining defects

1. `considered[].best_score` carries incompatible quantities:
   semantic reranker, raw hybrid score, policy RRF, or rule-weighted RRF.
   A receipt could show a semantic cutoff around 2.09 beside `best_score` around
   0.033, which is not comparable.
2. Rule-mode elbow input uses max semantic score across counted rules while its
   final order uses weighted rule RRF. The inferred max-of-k compression effect
   is plausible but not yet measured.
3. Rule mode still retains one additional parent at median. Four of 30 old extras
   were genuinely cited, so a strict per-scenario `rule <= policy` assertion
   would create recall risk.

### Partial unverified disclosure work in tree

A stopped task began additive disclosure work:

- `best_score_kind`
- `semantic_score`
- `rule_lead_semantic_score`
- `rule_max_semantic_score`
- score-kind constants

Direct search confirms these fields exist in the working tree. No successor may
assume the partial patch is complete or tested. Review the exact diff and run
receipt compatibility/integrity tests before using it.

### Oversight decisions

- Matched-rules-only payload for small parents is deferred because neighbouring
  rules may carry conditions/exceptions and existing failures already involve
  missing required facts.
- "Rule-first smaller than policy-first" is an aggregate target with recall
  controls, not a hard per-scenario invariant.

### Required sequence

1. Finish and verify score-scale disclosure without changing selection.
2. Capture `semantic_selected`, elbow, fallback offered/admitted, coverage
   expansion, lead/max semantic scores in a fast harness.
3. Run retrieval-only paired measurements with a whole-run watchdog and
   suspension awareness.
4. Only after measured attribution, decide whether to use lead-rule semantic
   score, rule-scoped flat default of one, or a corrected coverage floor.
5. Pair every narrowing test with a recall control proving a parent found only by
   a strong rule can still survive.

## 9. Index progress/history feature

Implemented in shared tree:

- One `PolicyIndexBuild` model/table.
- Migration `a1c5f0b3e284_policy_index_builds.py`.
- Shared `policy_index_build_progress.py`.
- One tracked build orchestrator used by publish and manual rebuild.
- PostgreSQL-backed unique nullable `active_slot` for cross-process global
  one-build exclusion.
- Lease heartbeat/reclaim.
- Admin aggregate console, progress lookup, project history/retry.
- Publisher project progress/history/retry.
- Frontend server-authority resume, reduced motion, one live region, no
  fabricated percentage.

Integration independent verification:

- Backend: 5,334 passed, 18 skipped.
- Frontend: 151 files / 1,896 tests passed.
- TypeScript: clean.
- Scratch PostgreSQL full migration chain and discriminating lock probe passed:
  first running row inserted, second refused, finished NULL-slot rows both
  inserted.
- Exactly one model/migration and linear Alembic chain.

Remaining:

- Live local database migration not applied: current `f4b8c2e97d31`, head
  `a1c5f0b3e284`.
- Authorization is role-only. Any policy author may currently read/rebuild any
  project; no project ACL exists.
- Concurrent builds are refused, not queued.
- Deferred publish builds are recorded but no worker drains them.
- Review the code path that generates `operation_id` when omitted.
- The stopped Integration session's handover is authoritative for detailed
  implementation ownership and tests.

## 10. Azure deployment

Live, directly rechecked:

- Subscription: `5a03d84f-151a-4ad3-9568-063e4e502bf0`
- Region: Sweden Central
- Resource group: `rg-pvai-swc`
- Required tag: `SecurityControl=Ignore`
- Mode: direct, no APIM, `LOCAL=true`
- API:
  `https://ca-pvaiswc-api-k6pmkx.thankfulrock-18993f62.swedencentral.azurecontainerapps.io`
- Web:
  `https://ca-pvaiswc-web-k6pmkx.thankfulrock-18993f62.swedencentral.azurecontainerapps.io`
- API `/health`: HTTP 200.
- API `/docs`: HTTP 200.
- Web root: HTTP 200.

`azd up` succeeded twice, including 14m11s and 19m51s runs.

Six deployment-kit defects fixed:

1. Incorrect `azure.yaml` Docker path/context semantics.
2. Root `.dockerignore` included 106 MB of consume-demo dependencies.
3. Linux lockfile dependencies missing for WASM binding.
4. False assumption that azd skips unmatched service tags.
5. Container App job `--image` override dropped command/args/env.
6. Missing `aiohttp` dependency for async managed identity.

Other verified deployment details:

- Resource group tag survives repeated `azd up`.
- `LOCAL` derives from `!enableApiManagement`, not direct exposure.
- 41 migrations applied in deployed environment.
- Search/OpenAI calls work; OpenAI returned real token usage.
- OpenAI/Search local auth disabled and public access disabled.
- No Owner/Contributor workload role.
- Audited endpoint returns 401 unauthenticated.
- 28 regional resources plus 10 global Private DNS resources/links.

Deployment checkout:

- Azure branch HEAD: `90fe48f`.
- Nine load-bearing modified files are uncommitted.
- No commit, push, merge, or `azd down`.
- Resources remain live and billing.

Open decisions:

- Commit the nine fixes.
- Merge Azure branch with shared application work.
- Keep or tear down billing resources.
- Enable Entra before treating direct mode as production-ready.
- `integration.py` was not in the deploy branch; `LOCAL=true` is wired but its
  integration capability was absent from deployed OpenAPI.
- Resolve `search_client.py` merge conflict while preserving exactly one async
  `_headers` definition and eight awaited callers.

## 11. Test evidence ledger

Direct captures by retiring oversight:

- Selective visual and adjacent: 235 passed.
- Projection/render boundaries: 526 passed.
- Rule-cardinality focused: 534 passed.
- Full cycle API/Search/DB verification and 20x2 artifacts.

Worker-reported but supported by artifact/handover:

- Payload final full suite: 5,280 passed / 18 skipped at its stopping point.
- Rule-cardinality agent full suite: 5,348 passed / 18 skipped.
- Integration final backend: 5,334 passed / 18 skipped.
- Integration frontend: 1,896 passed.
- Azure verification and two successful `azd up` runs.

The combined current tree changed after some full-suite runs. The successor must
run the relevant final combined suites before any commit.

## 12. Contradiction and stale-claim ledger

1. Payload `HANDOVER.md` says visual whitespace handling and targeted retry were
   unfinished and AIS held duplicate uploads. Later work completed those fixes,
   reset AIS again, ran a single final upload, published, and verified ready
   Search. The payload handover is historical, not current state.
2. Payload handover says no extraction/publish/index ran after its duplicate
   state. Later oversight completed the full cycles for both projects.
3. Earlier oversight summaries said AIS index had 319 live incomplete documents.
   Current direct state is 333 ready/quality-passed.
4. Earlier DB decision counts of 751 or 308 are historical. Project resets
   removed scoped receipts and later matrices added new ones. Current direct
   count was 164.
5. Integration initially claimed no progress files existed because `git grep`
   ignores untracked files. Recursive filename search found them. A duplicate
   model/migration added under that false premise was removed; current tree has
   exactly one.
6. The archived nested successor was not a valid top-level replacement and
   created no artifact files.
7. A 5h43m matrix call was not model latency. Windows Modern Standby suspended
   the host. All other paired calls were 13-47 seconds.

## 13. Pending work and dependencies

Priority 1: Complete top-level migration and create four mapped children.

Priority 2: Integration child:

- Verify current combined diff after rule changes.
- Apply `a1c5f0b3e284` to the intended local DB only with explicit authorization.
- Live-test admin/publisher progress, history, lock conflict and retry.
- Resolve operation-ID omission check.

Priority 3: Rule Retrieval child:

- Validate/finish partial score-disclosure work.
- Capture channel counters and semantic input values.
- Measure with watchdog.
- Make no new cutoff/statistic change before attribution.

Priority 4: Payload child:

- Final combined regression audit.
- Reverify both live manifests and selective recovery persistence.
- Prepare safe scoped commit grouping; do not commit without authorization.

Priority 5: Azure child:

- Preserve nine uncommitted fixes.
- Decide commit/merge/teardown with user.
- Revalidate deployment after integration/application merge.

## 14. Immediate successor action

1. Read this document and all four child handovers.
2. Read every cited original handover.
3. Verify this is a local-host session rooted at the shared checkout.
4. Verify HEAD/status, migration current/head, DB/Search readiness, source files,
   ports, Azure endpoints, and Azure checkout status.
5. Run `/orchestrate` using `SPAWN_SUCCESSOR_STRUCTURE.md`.
6. Do not allow Integration and Rule Retrieval to edit shared contract files
   concurrently.

## 15. Secret policy

This handover contains identifiers, resource names and public endpoint URLs only.
It deliberately contains no password, API key, subscription key, token,
connection string, Key Vault value, or policy source text. The successor must
preserve that boundary.
