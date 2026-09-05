# Successor Child Handover — Payload and Full-Cycle Verification

| | |
|---|---|
| **New session ID** | `5a06fec2-12cd-4477-b574-4d18ab814907` |
| **New project session ID** | `adba9f9b-0f58-4e8c-b24d-f0c249832395` |
| **Old source session ID (maps from)** | `8e46052e-8e8b-4ae5-9f04-752ad175c795` |
| **Parent (oversight successor)** | `b065f09b-2a4c-479f-a012-e6e55f388234` |
| **Project** | `policy-extractor-local-oversight` (local-only, folder session) |
| **Shared checkout** | via junction `…\policy-extractor-local-oversight\repository` → `C:\Users\taomar\Downloads\policy extractor` |
| **Prepared** | 2026-09-04 |

Phase A. **Read-only throughout.** No edit, commit, push, reset, stash, clean,
branch switch, migration, deployment, mutation endpoint, or destructive call was
made. No secret value was read into any output; `.env` was inspected for **key
names only**.

Evidence tags: **[D]** direct this session · **[A]** recorded artifact · **[I]** inherited, not re-verified.

---

## 1. Documents read, in the order required

1. `8437f3da-…\files\CHILD_PAYLOAD_HANDOVER.md`
2. `8437f3da-…\files\OVERSIGHT_SUCCESSOR_HANDOVER.md` (all 15 sections)
3. `8437f3da-…\files\SPAWN_SUCCESSOR_STRUCTURE.md`
4. `8e46052e-…\files\HANDOVER.md` (original source handover)
5. Rebuild / upload / visual artifacts beside it (inventoried in the rubric §7.2)
6. Retiring-oversight artifacts under `8437f3da-…\files` (inventoried, §7)
7. `58f19b59-…\files\PAYLOAD_HANDOVER.md` (historical)

---

## 2. Direct verification results

### 2.1 Shared checkout [D]

| Item | Parent claim | Directly observed (13:1x) | Verdict |
|---|---|---|---|
| Junction target | `C:\Users\taomar\Downloads\policy extractor` | same | ✅ |
| Branch | `main` | `main` | ✅ |
| HEAD | `c0972c8bb7ba811903e981d3806afe31cc1f514d` | identical | ✅ |
| Origin | `…/policy-governance-engine.git` | identical | ✅ normal origin restored |
| Tracked modified | 64 | 64 | ✅ |
| Untracked | 37 | 37 | ✅ |
| Total status entries | 101 | 101 | ✅ |

`git stash list` is empty. HEAD and branch were re-checked at the end of the
session and are unchanged.

### 2.1a The tree moved underneath this audit — Rule Retrieval is **not quiet** [D]

Re-checking status at the end of the session returned **102 entries / 65 tracked
modified**, one more than at the start. The delta is a single file:

- `src/policy_platform/contracts/case_decision_light.py` — newly modified

I never opened this file for writing; every write I made went to my own session
artifact folder. Modification times attribute the change conclusively:

| Time (2026-09-04) | File | Group |
|---|---|---|
| 13:34:36 | `contracts/case_decision.py` | R |
| 13:34:57 | `contracts/case_decision_light.py` | R |
| 13:36:16 | `assistants/ai_case_project.py` | R |
| 13:37:18 | `application/policy_case_decision.py` | R |

Four **decision/receipt contract** files changed inside a four-minute window
during this session. That is the Rule Retrieval child's scope, mid-edit.

**Consequences, and they are load-bearing:**

1. **Rule Retrieval is actively editing. The final combined suites must stay
   blocked** — this is now direct evidence, not just the standing instruction.
2. Any suite run right now would sample a moving tree, which is precisely the
   error the predecessors recorded twice.
3. `contracts/case_decision.py`, `assistants/ai_case_project.py` and
   `application/policy_case_decision.py` are on the contested list in §4.
   Integration must not touch them concurrently.
4. Every count in this document that predates 13:34 is stated against the
   64-file tree and is labelled with the time it was taken.


### 2.2 Alembic [D]

- Repository head: `a1c5f0b3e284`
- Live local DB current: `f4b8c2e97d31`
- **Independent corroboration:** table `policy_index_builds` **does not exist** in
  the live database (`information_schema.tables` count = 0). The migration is
  genuinely unapplied — this is not inferred from the version string alone.

### 2.3 Ports [D]

- 8010 listening, PID 56832 — not mine, untouched.
- 8051 listening, PID 49636 — not mine, untouched.
- 8070 — **not listening**, consistent with the retiring session's stop.
- I started no server and stopped no process.

### 2.4 Source artifacts [D]

Both originals present in `data\documents\`:
- `b7e1c4a2-3f6d-4a91-8c25-0d3e7f184b6a_v1_AIS_Employee_Handbook-1.pdf`
- `ad020e51-7f0a-49e0-bbdc-7a6e34054803_v2_Workplace-Hardware-Provisioning-Policy-v3.3.docx`

**Refinement of the parent's wording:** the DB `storage_path` for the *ingested*
versions points at the re-uploaded copies —
`fd474c6a-…_v1_b7e1c4a2-…_AIS_Employee_Handbook-1.pdf` and
`39740a63-…_v1_ad020e51-…_v3.3.docx` — both of which also exist. `ingestion_error`
is NULL and `ingestion_diagnostics_json` is present for both. No contradiction;
the originals are the upload inputs and the prefixed files are the stored versions.

### 2.5 Database state [D]

| | `ais-e2e` | `hw-policy` |
|---|---|---|
| Index name | `policy-cases-ais-e2e-1ac4bad101c28a5b` | `policy-cases-hw-policy-893c63433e7ecaf6` |
| Status | `built` | `built` |
| `document_count` | 332 | 249 |
| `built_at` | `2026-09-03T20:25:49.981736Z` | `2026-09-03T21:21:49.373137Z` |
| `error` | NULL | NULL |
| `projection_profile` | `policy-english-projection-v1` | same |
| `quality_state` / profile | `passed` / `policy-projection-quality-v1` | same |
| Quality checked docs | 332 | 249 |
| Structural findings | 0 | 0 |
| min / mean similarity | 0.8864 / 0.9894 | 0.9990 / 1.0000 |
| Source docs / versions | 1 / 1 | 1 / 1 |
| Clauses | 362 | 193 |
| Provisions | 39 | 60 |
| Approved rules (active v1) | 293 | 189 |
| Published candidates | 293 | 189 |
| Active version | 1, effective 2026-08-24 | 1, effective 2026-08-27 |
| Decision receipts | 82 | 82 |

Total decision receipts: **164** — exactly the parent's final snapshot, i.e. **no
decision has been executed against this database since**. Confirms the tree is
quiet on the decision path.

### 2.6 Live Azure AI Search [D]

Read-only filtered queries against the live indexes:

| | `ais-e2e` | `hw-policy` |
|---|---:|---:|
| Index exists | true | true |
| policy documents | 39 | 60 |
| rule documents | 293 | 189 |
| manifest documents | 1 | 1 |
| **live total** | **333** | **250** |
| `manifest_state` | `ready` | `ready` |
| `quality_state` via serving filter | passed | passed |
| `rule_index_scope` | `all_published_rules_v1` | `all_published_rules_v1` |
| `expected_policy_documents` | 39 | 60 |
| `expected_rule_documents` | 293 | 189 |
| `uploaded_documents` | 332 | 249 |
| `indexed_at` | `2026-09-03T20:25:49.981736Z` | `2026-09-03T21:21:49.373137Z` |
| **readiness probe** (`policy_index_ready_filter`) | **true** | **true** |

The readiness probe is the exact expression the serving path uses, including the
`quality_state`/`quality_profile` clauses — so readiness is verified through the
gate, not merely from a stored row.

**Four-way agreement** in both projects: DB provisions = live policy docs;
DB approved rules = live rule docs; DB `document_count` = manifest
`uploaded_documents` = live policy+rule; DB `built_at` = manifest `indexed_at`.
Both source-to-index cycles are therefore reverified end to end.

### 2.7 Selective visual recovery persistence [D]

- AIS clauses carrying a `reading_order` replay record in `source_fragments`: **9**
- AIS `table_row` clauses: **98**
- HW clauses carrying a replay record: **0**; HW `table_row` clauses: 25

This matches the recorded "9 recovered / 2 refused" and "zero visual calls for
HW" **[I]**, and matches the 98-row blind spot named in the source handover.
The replay records survived clause persistence, which is the property the
`ReadingOrderRecovery` design exists to guarantee.

### 2.8 Preserved payload fixes present in the working tree [D]

| Preserved item | Located at |
|---|---|
| Error descriptions | `infrastructure/errors.py::describe_exception` |
| Literal shielding, inert markers | `search/english_projection.py::_number_spans`, `_identifier_spans`, `protected_literal_failure`, `preservation_failure` |
| Shared exact rule scope | `projection/policy_rule_slice.py::rule_documents_expected`; consumed by `search/policy_index.py` and `quality/projection_faithfulness.py` |
| Scope constants | `RULE_INDEX_SCOPE_ALL = all_published_rules_v1` (live manifests agree) |
| Warning-only interleaving detector | `ingestion/mixed_script_text.py::INTERLEAVED_TEXT_CODE/interleaved_tokens`; `search/policy_index.py::_warn_about_interleaved_text` |
| Selective visual tie-break | `ingestion/visual_page_reading.py` (untracked) |
| Replayable provenance | `contracts/canonical_document.py::ReadingOrderRecovery`; `ingestion/canonical_fidelity.py::replay_reading_order`; `canonical_rebuild.py::READING_ORDER_KEY`; written by `document_extraction.py` |
| Truthful upload progress | `ingestion/upload_progress.py` (untracked, carries `has_interleaved_warning`); `apps/web/src/components/UploadProgressPanel.tsx` |

All present. Nothing from the preserved list is missing from the tree.

---

## 3. Stale-claim ledger — corrections to the source handover

The source payload handover `8e46052e-…\files\HANDOVER.md` is **historical**. I
re-checked its live-state section directly rather than repeating it:

| Source handover §5/§6 claim | Current direct state |
|---|---|
| "`ais-e2e` holds TWO overlapping documents" | **False now.** 1 source document, 1 version **[D]** |
| "No extraction, publish or index build has run" | **Superseded.** 293 rules extracted, approved, published as active v1, indexed, ready and quality-passed **[D]** |
| "`hw-policy` untouched — 115 documents, `built_at` 2026-08-30" | **Superseded.** 249 documents, `built_at` 2026-09-03T21:21:49Z **[D]** |
| §6.1 whitespace comparison + bounded retry "not implemented" | **Superseded** — completed by later work **[I]**, and the pipeline that depends on them produced a ready, quality-passed AIS index **[D]** |
| §6.3 rebuild7 marker-density "diagnosed, unfixed" | **Superseded** — preservation-rejected batch splitting landed **[I]**; AIS index built successfully **[D]** |
| §6.4 `admin-index-console` / `publisher-index-progress` "not started" | **Superseded** — implemented in tree (untracked `policy_index_console.py`, `policy_index_build_progress.py`, `PolicyIndexConsolePage.tsx`, `PolicyIndexProgressPanel.tsx`) **[D]**, but **not migrated into the live DB** **[D]** |
| §1 "last full backend suite 5280 passed" | **Stale as a statement about the current tree** — the tree changed after that run **[I]** |

Historical `58f19b59-…\files\PAYLOAD_HANDOVER.md` §4 (AIS index `failed`,
`document_count` 138, `built_at` 2026-08-31) is **entirely superseded** by the
current `built` / 332 / 2026-09-03 state **[D]**.

**Claims I did not re-verify and am not repeating as current:** candidate-quality
finding counts, JSON/payload percentage reductions, all full-suite test counts,
Azure deployment endpoint health, and the two-successful-`azd up` claims. These
remain **[I]**.

---

## 4. Scoped commit map (prepared, **not** committed)

101 entries. Ownership inferred from the source handovers plus file identity.
**No file is committed, staged, or modified by me.**

### Group P — Payload / rendering / visual (this child's scope)
Tracked: `contracts/canonical_document.py`, `ingestion/canonical_fidelity.py`,
`ingestion/canonical_rebuild.py`, `ingestion/document_extraction.py`,
`search/english_projection.py`, `projection/policy_rule_slice.py`,
`quality/projection_faithfulness.py`, `api/routers/documents.py`,
`tests/unit/test_a_projection_is_checked_against_what_it_renders.py`,
`test_english_is_the_only_internal_language.py`,
`test_the_corpus_is_indexed_in_one_language.py`, `test_a_stall_does_not_cost_the_run.py`.
Untracked: `ingestion/visual_page_reading.py`, `ingestion/mixed_script_text.py`,
`ingestion/upload_progress.py`, `infrastructure/errors.py`,
`apps/web/src/components/UploadProgressPanel.tsx(+.test.tsx)`,
`tests/unit/test_a_literal_survives_a_rendering.py`,
`test_a_number_survives_a_rendering.py`, `test_a_flagged_page_is_read_again.py`,
`test_a_recovered_reading_order_is_replayable.py`,
`test_an_upload_reports_its_own_progress.py`, `test_error_descriptions.py`,
`test_interleaved_extraction_is_reported.py`.

### Group I — Integration / index progress & console (**Integration child owns**)
Untracked: `alembic/versions/a1c5f0b3e284_policy_index_builds.py`,
`search/policy_index_build_progress.py`, `api/routers/policy_index_console.py`,
`apps/web/src/PolicyIndexConsolePage.tsx(+test)`,
`components/PolicyIndexProgressPanel.tsx(+test)`,
`components/PolicyIndexBuildHistoryTable.tsx`, `policyIndexSurfaceScope.test.tsx`,
`operationId.ts`, `tests/unit/test_one_index_build_runs_at_a_time.py`.
Tracked: `domain/models.py`, `api/routers/policy_sets.py`, `api/schemas.py`,
`apps/web/src/api.ts`, `App.tsx`, `components/ProjectOverviewTab.tsx`,
`DocumentsPage*.tsx`, `everyLongRequestAnnouncesItself.test.tsx`.

### Group A — Auth / subscription keys / integration surface (**Integration child**)
Untracked: `alembic/versions/f4b8c2e97d31_api_subscription_keys.py`,
`persistence/subscription_keys.py`, `api/routers/integration.py`,
`apps/web/src/IntegrationPage.tsx(+test)`,
`integrationCapabilityIsAskedOnlyAfterSignIn.test.tsx`,
`test_an_administrator_can_issue_an_api_key.py`,
`test_a_generated_key_survives_a_rendering.py`.
Tracked: `api/app.py`, `api/authz.py`, `apps/web/src/rbac.ts(+test)`,
`.env.example`, `docs/configuration.md`.

### Group R — Rule retrieval / decision contracts (**Rule Retrieval child owns — ACTIVELY EDITING**)
Tracked: `contracts/case_decision.py`, **`contracts/case_decision_light.py` (new
since this audit began — see §2.1a)**, `assistants/ai_case_project.py`,
`assistants/ai_case_intent.py`, `application/policy_case_decision.py`,
`api/routers/policy_decisions.py`, `search/policy_index.py`,
`test_a_project_case_decision_carries_its_own_receipt.py`,
`test_policy_case_project.py`, `test_policy_index.py`,
`test_external_policy_retrieval_returns_filtered_json.py`.
Untracked: `projection/llm_reasoning_view.py` (**withdrawn, unwired — preserve, do not ship**),
`test_the_model_reads_a_reasoning_view.py`,
`test_rule_retrieval_is_an_explicit_mode.py`,
`test_a_search_result_carries_only_what_is_read.py`,
`test_large_responses_are_compressed.py`.

**This group is in flight.** Do not group, stage or commit it until the Rule
Retrieval child reports quiet; the file list will keep growing.

### Group C — Consume demo (unattributed; confirm before grouping)
`apps/consume-demo/**` (10 files).

**Contested files — must not be edited by two children at once:**
`apps/web/src/api.ts`, `api/schemas.py`, `apps/web/src/App.tsx`,
`contracts/case_decision.py`, `search/policy_index.py`, `domain/models.py`.

---

## 5. Assignment status

| Item | Status |
|---|---|
| Read all mandated handovers | done |
| Verify read-only shared state | done |
| Reverify both source-to-index cycles | done — four-way agreement |
| Reverify saved artifacts | done — inventoried in rubric §7 |
| Reverify selective recovery persistence | done — 9 AIS replay records |
| Separate direct evidence from inherited claims | done — §3 ledger |
| Scoped commit map without committing | done — §4 |
| Consume API rubric + 20-question set | done — `CONSUME_API_EVALUATION_RUBRIC.md` |
| Six paired arms A–F execution plan | done — rubric §9. A–F = 3 response surfaces (`/case/light`, `/case`, `/policies`) × 2 retrieval modes. 20 × 3 × 6 = **360 calls**, **240 receipts** (E/F write none). Historical runs are baseline only; no official row reused. |
| **Final combined focused/full backend suites** | **blocked, by instruction** — awaiting parent confirmation that Integration and Rule Retrieval are quiet |
| Cache/skip/hash/threshold/default-rule regression audit | partial — static audit only; the dynamic half needs the suites |

---

## 6. What the next holder should do first

1. Wait for the parent's "Integration and Rule Retrieval are quiet" signal.
2. Then run the combined backend suite **alone** — never beside the frontend
   suites; vitest worker-startup timeouts here are CPU contention, not failures.
3. Re-run `verify_search_live.py` immediately before any readiness claim; a DB
   `built_at` is not live Search readiness.
4. Do not reshape behaviour around AIS/HW, page numbers, or any particular corpus.
5. Treat `llm_reasoning_view.py` as preserved analysis on no serving path.
6. Before attributing any test failure to this child's scope, check the file
   against the Group P list in §4 — this tree carries four sessions' work.
