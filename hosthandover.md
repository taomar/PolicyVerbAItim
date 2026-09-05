# PolicyVerbAItim — Host Migration Handover

Prepared by session `8476596b-1943-4577-8a2c-10e0d7553606` ("Host migration handover")
under parent `b065f09b-2a4c-479f-a012-e6e55f388234`.

Evidence snapshot taken **2026-09-05T04:50:02Z** (local `2026-09-05 07:50 +03:00`).

This document is **read-only output**. No repository file, index, ref, stash, config,
hook, ignored file, database row, Search document, Azure resource, deployment, or
migration was changed while producing it. Every command run against a repository was
a read-only Git query issued with `GIT_OPTIONAL_LOCKS=0`.

> **Evidence discipline.** Everything below is labelled `verified`, `historical`,
> `pending`, `blocked`, `withdrawn`, `containment`, or `unverified`. Where a fact could
> not be established from repository or session evidence at snapshot time, it is marked
> `UNVERIFIED` rather than asserted.

---

## 0. Portable target-host operating model

**Read this before anything else. It governs how every other section is to be used.**

You are working from a clean clone of the private archival repository
`https://github.com/taomar/PolicyVerbAItim`. That clone is self-sufficient:

| What you need | Where it is |
|---|---|
| The product source, including the previously uncommitted in-flight bytes | the repository tree itself, already reconciled on the archival `main` |
| Continuity evidence — patches, reconstructions, adoption records, provenance package, publisher records | `handover/artifacts/` |
| Narrative, ledgers, task list, checksums | `hosthandover.md` and `handover/` |

### 0.1 Four rules

1. **No session-state directory is required.** Nothing in the target-host workflow
   depends on an agent session store, a checkpoint tree, or an event log. Everything
   needed was vendored into `handover/artifacts/`.
2. **No old checkout is required.** Do not copy, mount, or hunt for a previous working
   tree or worktree. Clone and verify; that is the whole restore.
3. **Absolute `C:\Users\taomar\...` paths describe the source host only.** They appear
   in `handover/artifacts/historical/`, in `source_path` provenance fields, and in
   sections of this document explicitly labelled *historical*. They are a record of
   where the work happened. **They are never an instruction and never a dependency.**
   If a step appears to require one, that step is historical narrative, not a task.
4. **The live task list is `handover/PENDING_DECISIONS_AND_TASKS.json`**, tasks `T-01`
   onward. The frozen source-host task list under
   `handover/artifacts/historical/` is superseded and non-actionable.

### 0.2 Restore path

```
1. Authenticate to GitHub as user  taomar          <-- identity matters, see below
2. git clone https://github.com/taomar/PolicyVerbAItim
3. Verify remote HEAD and the recursive handover checksums
4. Work from the clean archival clone
```

> **Identity trap — this already bit once.** The repository is private and owned by
> `taomar`. An ambient `GH_TOKEN` belonging to `taomar_microsoft` receives a
> **404 `Repository not found`**, which is indistinguishable from the repository not
> existing. Use the keyring token for GitHub user `taomar`. See §15.4.

Full instructions: `handover/RESUME_FIRST.md`. Authoritative task list:
`handover/PENDING_DECISIONS_AND_TASKS.json`. Late-breaking publication evidence: **§15**,
which supersedes the publication-status statements in §§1.2, 1.3, 3.3, 5, 11 and 14.

### 0.3 What the archival main contains

The source host carried significant work that had never been committed. Rather than
discard or blindly overwrite it, it was captured against the exact base it was authored
on (`3414811752cc2cb08bf26b87dd8d8fa2c22baf65`) and **merged** with that as the merge
base, so the separately adopted feature commits appear as one-sided additions and
survive intact. The archival `main` is therefore the union of:

- the nine-commit product line (§3.1), and
- the reconciled in-flight working tree (§8.5),

plus a separately committed, deliberately audited set of otherwise-ignored developer
`skills` assets.

You inherit the reconciled result. §2.4's synthetic-status hazard is a **historical**
description of how the source host looked, retained because it explains why the merge
base matters — not a state you will encounter in the clone.

### 0.4 What is deliberately *not* in the clone

Secrets, credentials, signing keys, `.env` files, the runtime document store, database
backups, dependency trees, build output and caches. Restore them out of band **only if
you must actually run the system** (task `T-05`). Reading, reviewing and auditing this
package requires none of them.

One product artifact is also off-main: the preserved Azure production local-auth commit
`381586688f0337be15dcc1d42d2be7d4b0fe4936`. It does **not** travel on `main`; its full
content is vendored as `handover/artifacts/azure/AZURE_3815866.patch`. Never apply,
deploy, push or merge it without new authorization.

---

## 1. Executive resume point and no-development lock

### 1.1 Lock state — currently in force

**ALL FEATURE DEVELOPMENT IS STOPPED.** The parent placed the whole programme into
archival-only mode. On the new host the lock stays in force until the human owner
explicitly lifts it.

Prohibited without new, explicit authorization:

| Action | Status |
|---|---|
| Editing repository source | **Prohibited** |
| `git add` / `commit` / `reset` / `stash` / `clean` / `checkout` of the shared tree | **Prohibited** |
| `git push` to any remote | **Prohibited** (one private base publication is the sole in-flight exception, see §1.3) |
| Azure deployment, IaC apply, Key Vault mutation | **Prohibited** |
| Alembic migration against any live database | **Prohibited** |
| Live Azure AI Search index build/upload | **Prohibited** |
| Live model / API calls against production endpoints | **Prohibited** |
| Provenance harness execution | **Prohibited** (execution flag is `false` in the bundle) |

Permitted without new authorization: read-only inspection, hashing, and writing
handover artifacts into a session-state `files` directory.

### 1.2 One-paragraph resume point

Local `main` in the shared checkout is `d3bb0f94d58d1810a1ff24cacf8118d82f9c554f`
("Instrument ranking components"), **nine commits ahead of `origin/main`
(`db882ef31b9cb6e6327f13e7e1750ebcfe2563d5`) and never pushed**. Those nine are: one
pre-existing commit (`c0972c8`), the six-unit decomposition of the previously
uncommittable shared working tree, and two independently reviewed feature commits
(canonical table carrier, ranking telemetry). The shared working tree is still dirty
on purpose — 86 status entries — because the adoptions deliberately preserved
working-tree bytes rather than cleaning them. A private GitHub base publication to
`https://github.com/taomar/PolicyVerbAItim.git` was in flight at snapshot time; its
final remote SHA is **not yet known** and must be supplied by the parent.

### 1.3 The single in-flight exception

Session `ecd8492d-9745-4265-991a-cba401a6ebc3` (visible nested publisher) was
authorized for archival reconciliation plus **one** private push. At snapshot time it
had produced two local commits and had **not** been observed to complete a push:

- `cf2d0f104c55f5a961d4634e692b9ebbe49e2aa7` — "Capture the in-flight working tree as
  archival source", parent `3414811`, on branch `archive-inflight`.
- `b13f168db44f2dd0218b3deea0bba1bf186fb27e` — "Reconcile the in-flight archive with
  the adopted feature commits", a **merge commit** with parents `d3bb0f94…` and
  `cf2d0f10…`, on branch `taomar-microsoft-private-base-publisher`.
- `8bc0657a7076e8bf85b0a5f1b5ea009911829040` — "Carry the ignored skill assets into the
  archive", parent `b13f168…`, branch tip at the 06:38:47Z recheck. It deliberately
  pulls three `skills` asset sets (reference notes, helper scripts, fonts, licence
  files) past the `.gitignore` `skills` rule, committed **separately** so the bypass is
  auditable in one place. `.gitignore` itself is unchanged; generated coverage output
  was left behind.

`git ls-remote --heads base` from this session returned
`remote: Repository not found. fatal: repository 'https://github.com/taomar/PolicyVerbAItim.git/' not found`.
This is **UNVERIFIED** as to cause: it is consistent either with the repository not
existing/being inaccessible, or with this process lacking credentials for a private
repository. **Do not conclude that the push failed or succeeded.** Await the parent's
final remote SHA.

---

## 2. Repository, remotes, HEAD, index, stash and status — before and after each adoption

### 2.1 Locations — HISTORICAL (source host only, non-actionable)

> These paths describe the machine the work was performed on. They are provenance, not
> instructions. On the target host you need none of them — see §0.

| Thing | Windows path on the source host |
|---|---|
| Oversight project root (folder project, not a Git repo) | `C:\Users\taomar\Downloads\policy-extractor-local-oversight` |
| Shared checkout **junction** | `C:\Users\taomar\Downloads\policy-extractor-local-oversight\repository` |
| Junction target (the real working tree) | `C:\Users\taomar\Downloads\policy extractor` |
| Git directory | `C:\Users\taomar\Downloads\policy extractor\.git` |
| Separate Azure deployment checkout | `C:\Users\taomar\Downloads\policy-extractor-azure-deploy` |

`repository` was an NTFS **junction**, not a copy. This mattered on the source host; it
is irrelevant to the clone.

### 2.2 Remotes (verified at snapshot)

| Remote | URL | Notes |
|---|---|---|
| `origin` | `https://github.com/taomar/policyAIengine.git` | **Changed** from the historical `taomar/policy-governance-engine.git`. The migration handover said origin was temporarily repointed to `policyAIengine` only to let `create_session` accept the project, and was to be restored. It is currently **not** restored. |
| `base` | `https://github.com/taomar/PolicyVerbAItim.git` | Added by the private publisher. Reachability **UNVERIFIED** (see §1.3). |

`refs/remotes/origin/main` and `refs/remotes/origin/HEAD` both point at
`db882ef31b9cb6e6327f13e7e1750ebcfe2563d5`. There are **no** remote-tracking refs for
`base`.

### 2.3 State transitions

Three distinct adoption events moved `main`. Each preserved working-tree bytes.

#### Baseline (historical — start of the oversight migration, 2026-09-04)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `c0972c8bb7ba811903e981d3806afe31cc1f514d` |
| Origin (then) | `https://github.com/taomar/policy-governance-engine.git` |
| Status entries | 101 (64 tracked changes + 37 untracked) |
| Index | empty (no staged changes) |
| Stash | empty |

Later in the same session, after further worker edits, the pre-decomposition snapshot
was **120 normal / 121 exhaustive** status entries (73 modified + 47 untracked). The
120 vs 121 difference is representational only: normal `git status` collapses
`.serena/` into one entry, exhaustive mode lists its two files.

#### Adoption A — six-unit decomposition (2026-09-05T03:14:44Z)

| Field | Before | After |
|---|---|---|
| `main` | `c0972c8bb7ba811903e981d3806afe31cc1f514d` | `3414811752cc2cb08bf26b87dd8d8fa2c22baf65` |
| Final tree | — | `5ade3ef636fd71c0a7c87b3ba9b69393f47d9e94` |
| Normal status entries | 120 | **77** |
| Exhaustive status entries | 121 | **78** |
| Tracked modified | 73 | **42** |
| Untracked physical | 47 | **36** |
| Index (cached diff) | empty | empty |
| Stash | empty | empty |

- Mechanism: detached private worktree; raw base/result hash validation; explicit path
  staging; `write-tree` / `commit-tree`; detached `update-ref`.
- 43 dirty paths were **cleaned** — their working-tree bytes became identical to the
  new HEAD, so they left the status list.
- 5 paths remain **mixed residual** (partially committed, partially still dirty):
  `src/policy_platform/api/app.py`,
  `src/policy_platform/infrastructure/projection/policy_rule_slice.py`,
  `src/policy_platform/infrastructure/search/policy_index.py`,
  `tests/unit/test_no_m2_code_is_shaped_around_a_corpus.py`,
  `tests/unit/test_the_corpus_is_indexed_in_one_language.py`.
- Non-mutation gate after adoption: 121 dirty-file hashes unchanged; content tree of
  37,199 files / 553,349,103 bytes hashed to
  `a702437f485cdf04aca82c37122621cfa6e61b2f021ac1c7bf7b118684099a28`, unchanged.
- Rollback record written and **not used** (`used: false`). Backups:
  `shared-index-before.bin` (120,664 bytes, sha256
  `bdc2eb8cbd6d29e03595b8f6c60159ae68432f865293f1c74a63456536152bb2`),
  `shared-HEAD-before.bin` (21 bytes, sha256
  `28d25bf82af4c0e2b72f50959b2beb859e3e60b9630a5e8c603dad4ddb2b6e80`).
- The temporary detached worktree used for the adoption was **removed**.

#### Adoption B — two feature commits (2026-09-05T04:35:10Z)

| Field | Before | After |
|---|---|---|
| `main` | `3414811752cc2cb08bf26b87dd8d8fa2c22baf65` | `d3bb0f94d58d1810a1ff24cacf8118d82f9c554f` |
| Final tree | `5ade3ef6…` | `3caa34fcb3893e2a877941d1814365598e708cf0` |
| Normal status entries | 77 | **86** |
| Exhaustive status entries | 78 | **87** |
| Tracked changed | 42 | **51** |
| Untracked physical | 36 | **36** |
| Index (cached diff) | empty | empty |
| Stash | 0 entries | 0 entries |

Pre-adoption integrity anchors (`START_STATE.json`):

- `normal_status_sha256` = `28584ef487e36ee35bf4309b3191a33b502296df9e5891c217d94a4e80bcfb88`
- `expanded_status_sha256` = `3c7cfef96d0bd7c391fa139a70bdc15ee171c550627ab2cf3db4ac663f738f72`
- `logical_index_sha256` = `6676de77652921e53e56f2d8e327b4c9e799c33242b79a79d43d7931e9919037`
- `index_backup_sha256` = `1dc49e3b3203ea82bd4beeda6553e6b901b758d9f53ffe4dea26a1d4dc19389f`
- 78 dirty-file byte hashes recorded individually.
- `working_tree_bytes_unchanged: true` after adoption.

#### Current (verified at snapshot 2026-09-05T04:50:02Z)

```
branch                 main
HEAD                   d3bb0f94d58d1810a1ff24cacf8118d82f9c554f
ahead of origin/main   9
normal status entries  86   (48  M  +  35 ??  +  3  D)
exhaustive entries     87
cached diff            EMPTY  (index has no staged changes)
stash                  empty
```

### 2.4 Dirty-byte-preserving index adoption — and why status showed synthetic `D`/`M`

> **HISTORICAL.** This describes the source host's working tree. The archival clone
> already carries the reconciled result. Retained because it is the reason the merge
> base in §8.5 matters, and the reason any future re-derivation must follow the same
> rule.

**What was done.** Both adoptions built the new commits in a *separate, private*
worktree, validated the resulting tree hash, and then moved only `refs/heads/main` and
the *logical* index in the shared checkout. The shared **working-tree bytes were never
written to**. This was deliberate: the shared tree contained cross-session,
mixed-ownership, partially unattributed work that must not be destroyed by a checkout.

**Why the shared `.git/index` byte image is not a mutation signal.** A read-only
`git status` can refresh stat metadata inside `.git/index`, so the physical file bytes
change without any logical change. All non-mutation proofs therefore hash *repository
content excluding `.git/**`* and separately verify the **logical** index (the entry
list), status porcelain, refs, and stash — all under `GIT_OPTIONAL_LOCKS=0`.

**Why post-adoption status contains synthetic entries.** After Adoption B, HEAD
contains the two feature commits but the working tree still holds the pre-adoption
bytes. Git therefore reports the difference as if the developer had reverted them:

- **3 synthetic `D` (deleted)** — files that the feature commits *added*, which have
  never existed in the shared working tree:
  - `src/policy_platform/infrastructure/search/ranking_telemetry.py`
  - `tests/unit/test_a_ranking_says_which_component_ranked_it.py`
  - `tests/unit/test_a_table_keeps_its_shape.py`

  *Verified at snapshot: none of these three exists on disk.*

- **6 synthetic `M` (modified)** — files the feature commits changed, whose
  working-tree copies still carry the older pre-commit content:
  - `src/policy_platform/api/routers/extraction.py`
  - `src/policy_platform/contracts/reading_plan.py`
  - `src/policy_platform/contracts/structural_graph.py`
  - `src/policy_platform/infrastructure/extraction/ai_extraction.py`
  - `src/policy_platform/infrastructure/ingestion/document_ingestion.py`
  - `tests/unit/test_clause_projection_boundary.py`

  *Verified at snapshot: each reports exactly `" M <path>"`.*

Arithmetic: 16 feature paths; 7 were already dirty before Adoption B and stayed dirty;
the other 9 became new status entries as 3 `D` + 6 `M`. 42 + 9 = 51 tracked changes.

**Operational consequence — this is the single most dangerous item in the handover.**

> Those 3 `D` entries are **NOT** real deletions and those 6 `M` entries are **NOT**
> real reverts. A naive `git checkout -- .`, `git restore .`, `git stash`, `git clean`,
> `git reset --hard`, or a wholesale `git add -A && git commit` will either destroy
> uncommitted in-flight work or re-delete committed feature files. Reconciliation must
> be **by hunk against merge base `3414811`**, never by wholesale replacement.

### 2.5 The 86 / 87 discrepancy

Normal status collapses the untracked directory `.serena/` into a single `?? .serena/`
entry; exhaustive mode lists `.serena/.gitignore` and `.serena/project.yml`
separately. 35 normal untracked entries ≡ 36 exhaustive untracked files.

---

## 3. Commit ledger

Author/committer identity on every reconstructed commit: `Policy Platform
<policy-platform@local>`. Every reconstructed commit carries the trailer
`Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`.

### 3.1 Main line — `origin/main` through current HEAD

| # | SHA | Tree | Parent | Subject | Ownership | Pushed |
|---|---|---|---|---|---|---|
| — | `db882ef31b9cb6e6327f13e7e1750ebcfe2563d5` | `c9a97e86…` | `68979048…` | Document the REST integration surface against measured responses | historical, on `origin/main` | **yes** |
| 0 | `c0972c8bb7ba811903e981d3806afe31cc1f514d` | `f0ee85e9…` | `db882ef3…` | Point receipt verification at a working canonical-hash implementation | historical, pre-existing local commit | **no** |
| 00 | `e689bf77ca900b69269e0ae3334b41d7608dda81` | `3fe60a8c…` | `c0972c8b…` | Build all-published rule index foundation | Rule index/projection foundation (session `c17eaeeb…`) | **no** |
| 01 | `5d731b69c3e5c56ad8e9b0c92e7f3db402172eb7` | `a3e851c8…` | `e689bf77…` | Implement native rule retrieval | Rule Retrieval track | **no** |
| 01a | `acff6e8daa16dfb7a1fe8c65f584d3476194ee43` | `28731a3c…` | `5d731b69…` | Optimize response compression and search projection | earlier Payload optimizations, reclassified out of Rule | **no** |
| 02 | `b8459180aebaf1c8252000ef07402ac9871b47d8` | `5bc79b29…` | `acff6e8d…` | Enforce evidence-complete case decisions | Payload track (session `5a06fec2…`) | **no** |
| 03 | `be2608140d824e42a6d66cf9fbac07dae4792f1f` | `8449ef73…` | `b8459180…` | Add Consume rule retrieval request mode | older Consume request-mode foundation; authorship traced to `d99011fe…`, retroactively approved | **no** |
| 04 | `3414811752cc2cb08bf26b87dd8d8fa2c22baf65` | `5ade3ef6…` | `be260814…` | Render native rule retrieval responses | Consume native parser/renderer | **no** |
| F1 | `3da502fee2f4c56ec1864a76553fc1a7ecd9ca94` | `84bae5ba…` | `34148117…` | Preserve canonical table structure | canonical table-structure carrier; reviewed by `690ae612…` | **no** |
| F2 | `d3bb0f94d58d1810a1ff24cacf8118d82f9c554f` | `3caa34fc…` | `3da502fe…` | Instrument ranking components | ranking telemetry, **rebased**; reviewed by `749bf4f5…` | **no** |

`d3bb0f94…` is the current `main` and the current shared-checkout HEAD.

### 3.2 Feature commits — original vs adopted

| Feature | Original object | Original tree | Original parent | Adopted object | Note |
|---|---|---|---|---|---|
| Canonical table carrier | `3da502fee2f4c56ec1864a76553fc1a7ecd9ca94` | `84bae5ba…` | `3414811752…` | same object | fast-forwarded unchanged |
| Ranking telemetry | `4f9f21a982ca612c08a3af7f8e6128f59fca605f` | `82862cf9e88f24c9c7a88ed2acc272366a19af52` | `3414811752…` | `d3bb0f94d58d1810a1ff24cacf8118d82f9c554f` (tree `3caa34fc…`) | **rebased** onto the table carrier; the original object still exists on branch `taomar-microsoft-ranking-telemetry` |

Both reviewers independently reported the same seeding defect: their review worktrees
were cut at `db882ef` (7 commits behind local `main`), not at the asserted `3414811`.
Because `db882ef` is an *ancestor*, `git merge --ff-only` still succeeded and swept in
the 7 already-on-main commits. Final parents were correct, but the asserted
pre-condition was false, and the UI's "61 files / +11,901" figure is the cumulative
`db882ef..HEAD` range, not the commit. **Fix how these sessions are seeded.**

### 3.3 Off-main commits

| SHA | Branch | Parent(s) | Subject | Status |
|---|---|---|---|---|
| `4f9f21a982ca612c08a3af7f8e6128f59fca605f` | `taomar-microsoft-ranking-telemetry` | `3414811…` | Instrument ranking components | superseded by the rebased `d3bb0f94…`; retained as provenance |
| `cf2d0f104c55f5a961d4634e692b9ebbe49e2aa7` | `archive-inflight` | `3414811…` | Capture the in-flight working tree as archival source | **in flight**; 76 files, +16,841 / −395 |
| `b13f168db44f2dd0218b3deea0bba1bf186fb27e` | `taomar-microsoft-private-base-publisher` | `d3bb0f94…`, `cf2d0f10…` | Reconcile the in-flight archive with the adopted feature commits | **in flight**; merge commit, 4 files hand-resolved |
| `8bc0657a7076e8bf85b0a5f1b5ea009911829040` | `taomar-microsoft-private-base-publisher` | `b13f168…` | Carry the ignored skill assets into the archive | **in flight**; branch tip at 06:38:47Z recheck; deliberate, audited `.gitignore` bypass for `skills` assets |
| `381586688f0337be15dcc1d42d2be7d4b0fe4936` | `azure-deploy` | `a17525ca…` | Add production local authentication | **preserved, do not deploy or push** |
| `a17525cad24b3af262290826eb9846f90acea9ae` | `azure-deploy` | `90fe48ff…` | Fix reproducible Azure deployment | historical, authorized preservation commit |

### 3.4 Six-unit reconstruction patches (byte-identical inputs to commits 00–04)

Vendored at `handover/artifacts/six-unit/final-artifacts/`
(exactly what was committed is also at `handover/artifacts/six-unit/adoption/*-commit.patch`).

| Ord | Patch | Bytes | SHA-256 |
|---|---|---:|---|
| 00 | `00-rule-index-foundation.patch` | 51,705 | `c3b2e80468878cbf1b0940e33a2c08950ac96980549a897ea8e37fd3a930c218` |
| 01 | `01-rule-retrieval.patch` | 316,091 | `c75e0bb4d990f418f9f434bc832602e01d08c3d91cbfd3e94be3aa932903e4a1` |
| 01a | `01a-earlier-payload-optimizations.patch` | 31,908 | `917e7caa44e4d5fbf32b200e846434638b4f475c1d0d4de71334ff8cf182604e` |
| 02 | `02-payload.patch` | 87,833 | `2714ca1f86e7ed0a16b8271a24aa39223692d38dc0e827cb0b6e36879e2c34b7` |
| 03 | `03-consume-request-mode-foundation.patch` | 27,171 | `3471d8abc20c97da7792a7f89537a7e1011670b1a9dcdd9958e91fc257fcbec7` |
| 04 | `04-consume-native-parser-renderer.patch` | 35,998 | `103af6f4551f2c3437aaf4f72b711c4a73f497af08259267f6630fa8c4e7831a` |

All six were `byte_identical: true` against their originating sessions' outputs.

**Disclosed whitespace warning (still open, non-blocking):** the ordinal-01 artifact
adds one blank line at EOF in `test_policy_case_project.py`; `git apply
--whitespace=error-all` reports exactly that one line. Normal apply, exact hashes,
imports, focused tests and the full backend all pass. If a zero-whitespace-warning
policy is ever enforced, ordinals 01 and 02 must be cleaned and rebased **together**
and every gate re-run.

---

## 4. Session hierarchy and ID ledger — HISTORICAL (source host only, non-actionable)

> This records who produced what, so every artifact's provenance is auditable. **No
> session-state directory is required on the target host**; everything needed was
> vendored into `handover/artifacts/` (see `handover/artifacts/BUNDLED_ARTIFACTS.json`
> for the file-by-file mapping). Session IDs and `…\session-state\…` paths below are
> provenance, not instructions.

### 4.1 Chain of custody

```
58f19b59-6aa9-4d38-8782-46cbdc7640c5   original V3 predecessor (historical)
        |
8437f3da-491a-4139-b979-8b00996c8953   retiring oversight — 7 migration artifacts
        |
b065f09b-2a4c-479f-a012-e6e55f388234   TOP-LEVEL PARENT (current oversight)
        |
        +-- 5a06fec2-12cd-4477-b574-4d18ab814907   Payload & full-cycle verification
        +-- 94102b91-353f-46f3-a59b-72d8381912f9   Integration & index progress
        +-- d185704d-4bd4-4a2a-b2f4-8a6fa3f25961   Azure deploy (halted, archived)
        +-- 7d783c45-9dd4-49c8-bdc0-ad43f0192148   Rule retrieval
        +-- 71c6d508-6a53-4419-8513-eb812f72ca69   Criterion provenance successor
        +-- 6713376d-9ff3-4740-9060-dcaf7afcbb08   Final commit-decomposition auditor
        +-- c17eaeeb-2be8-496d-b206-d2457f7b30f8   Ordinal-00 rule index foundation
        +-- d5da914d-1050-4c78-9b63-798ced2d1610   Ordinal-03 Consume request foundation
        +-- 690ae612-611a-4b4a-99e4-c39753610534   Table carrier reviewer (ARCHIVED)
        +-- 749bf4f5-26be-4bce-ba4e-0fc3d3551d60   Ranking telemetry reviewer (ARCHIVED)
        +-- ecd8492d-9745-4265-991a-cba401a6ebc3   Private base publisher (IN FLIGHT)
        +-- 8476596b-1943-4577-8a2c-10e0d7553606   THIS handover session
```

Project: `policy-extractor-local-oversight`, project ID
`398fea1a-f058-481a-8546-dc08cfa1eb6f`, local-only **folder** project (no Git root at
the project level; the repository is reached only through the `repository` junction).

Historically configured project `f8d6ba17-9121-4470-8a09-7dc2ecbe9cef` had saved
repository `taomar/policyAIengine` while the verified origin was
`taomar/policy-governance-engine`, which is why child creation was refused and the
local-only folder project was used instead. An incorrectly nested successor
`fa724b93-b7f4-4306-b10e-61ddc539dee2` was archived and produced no artifacts; it must
**not** be treated as a successor.

### 4.2 Session detail

| Session | Role / purpose | State at snapshot | Artifacts (Windows paths) |
|---|---|---|---|
| `8437f3da-491a-4139-b979-8b00996c8953` | Retiring oversight; source of the 7 migration artifacts | retired | `…\session-state\8437f3da-…\files\OVERSIGHT_SUCCESSOR_HANDOVER.md`, `SPAWN_SUCCESSOR_STRUCTURE.md`, `TOP_LEVEL_PARENT_KICKOFF.md`, `CHILD_AZURE_HANDOVER.md`, `CHILD_INTEGRATION_HANDOVER.md`, `CHILD_PAYLOAD_HANDOVER.md`, `CHILD_RULE_RETRIEVAL_HANDOVER.md` + AIS/HW upload-publish-index evidence + `data-db-before-local-workflow.sqlite` |
| `b065f09b-2a4c-479f-a012-e6e55f388234` | Top-level parent / oversight coordinator | **active** | `…\files\PARENT_SUCCESSOR_HANDOVER.md`, `matrix-api.log`, `feature-adoption\`, `feature-integration-candidate\`, `worktrees\`; 4 checkpoints |
| `5a06fec2-12cd-4477-b574-4d18ab814907` | Payload & full-cycle verification (writer, returned lock) | archived | `CHILD_PAYLOAD_SUCCESSOR_HANDOVER.md`, `IMPLEMENTATION_BLUEPRINT_26_TRUE_FAILURES.md`, `REGRESSION_INVESTIGATION_38_POLICY_MODE.md`, `CONSUME_API_EVALUATION_RUBRIC.md`, probe scripts |
| `6713376d-9ff3-4740-9060-dcaf7afcbb08` | Final read-only commit-decomposition auditor; performed Adoption A | idle | `FINAL_COMMIT_DECOMPOSITION.md`, `NEXT_ACTION_HANDOFF.md`, `six-unit-audit\` (incl. `final-artifacts\`, `adoption\`), `COMPLETE_PATH_LEDGER.json`, `EXCLUSIONS.json`, `HEAD-c0972c8.tar` |
| `c17eaeeb-2be8-496d-b206-d2457f7b30f8` | Ordinal-00 rule index/projection foundation reconstruction | completed | `00-rule-index-foundation.patch`, `01-rule-retrieval.rebased-on-foundation.patch`, `RULE_INDEX_FOUNDATION_RECONSTRUCTION.md`, `PATH_HUNK_MANIFEST.json`, `SEQUENCE_VALIDATION.json`, `private-head-c0972c8.tar` |
| `d5da914d-1050-4c78-9b63-798ced2d1610` | Ordinal-03 Consume request-mode foundation reconstruction | completed | `03-consume-request-mode-foundation.patch`, `04-consume-native-parser-renderer.patch`, `APPROVAL_AUTHORSHIP_EVIDENCE.json`, `CONSUME_REQUEST_FOUNDATION_RECONSTRUCTION.md`, `NON_MUTATION_PROOF.json` |
| `71c6d508-6a53-4419-8513-eb812f72ca69` | Criterion provenance merge/validation successor | archived | `criterion-provenance-successor-v1.0.0\`, `criterion-provenance-merge-blocked-v1.0.0\`, `HANDOFF_HASH_MANIFEST.json`, `validate_provenance_partition.py` |
| `690ae612-611a-4b4a-99e4-c39753610534` | Visible reviewer, canonical table carrier | **archived** by parent | worktree `…\copilot-worktrees\policy extractor\taomar-microsoft-bookish-system` (branch later renamed `taomar-microsoft-canonical-table-carrier`) |
| `749bf4f5-26be-4bce-ba4e-0fc3d3551d60` | Visible reviewer, ranking telemetry | **archived** by parent | worktree `…\copilot-worktrees\policy extractor\taomar-microsoft-symmetrical-waddle` (branch later renamed `taomar-microsoft-ranking-telemetry`) |
| `ecd8492d-9745-4265-991a-cba401a6ebc3` | Visible nested private base publisher | **in flight** | `msg-snapshot.txt`, `msg-merge.txt`, `pathspec.txt` (76 lines), `safe-inflight-paths.txt` (76 paths) |
| `d99011fe-a8c3-4032-872b-1643baaef994` | "Policy payload size audit" — proven author of the Consume T1 edits | historical | `events.jsonl` is the authorship evidence (warning turns 35–36; edit events ≈ lines 3600–3688) |
| `8476596b-1943-4577-8a2c-10e0d7553606` | **This** handover session | active | this package |

### 4.3 Notable handoffs

1. `8437f3da` → `b065f09b`: seven migration artifacts plus every handover they cite;
   nothing mutated during migration.
2. Rule/Payload/Consume workers → `6713376d`: read-only decomposition proved the three
   feature areas were implemented but **not directly committable from HEAD**, and
   produced the ordered five/six-patch plan.
3. `c17eaeeb` + `d5da914d` → `6713376d`: validated prerequisite patches, enabling the
   final six-unit sequence and Adoption A.
4. Isolated builders → `690ae612` / `749bf4f5`: two feature commits reviewed
   independently, then Adoption B.
5. `b065f09b` → `ecd8492d`: private base publication, restricted to archival
   reconciliation and one push.
6. `b065f09b` → `8476596b`: this host-transfer package.

---

## 5. Worktree ledger — HISTORICAL (source host only, non-actionable)

> None of these worktrees travel to the target host and none is required there. This
> ledger is retained so the provenance of every commit is auditable, and so that anyone
> returning to the source host knows what must not be pruned.

Verified via `git worktree list` plus `for-each-ref` on the source host. **Note:** the
publisher advanced two branches *after* the first listing; SHAs below are the snapshot
values.

| # | Worktree path | Branch / state | SHA at snapshot | Disposition |
|---|---|---|---|---|
| 1 | `C:\Users\taomar\Downloads\policy extractor` | `main` | `d3bb0f94…` | **The shared dirty checkout. Primary. Keep. Never clean.** |
| 2 | `C:\Users\taomar\.copilot\repos\copilot-worktrees\policy extractor\taomar-microsoft-automatic-train` | `archive-inflight` | `cf2d0f10…` | Publisher's worktree. **In flight — do not remove until the publisher reports done.** |
| 3 | `C:\Users\taomar\.copilot\repos\copilot-worktrees\policy extractor\taomar-microsoft-jubilant-broccoli` | `taomar-microsoft-policyverbatim-v3-oversight` | `db882ef…` | Stale oversight worktree at `origin/main`. Removable after the branch is confirmed unneeded. |
| 4 | `C:\Users\taomar\.copilot\session-state\b065f09b-…\files\feature-integration-candidate` | detached | `d3bb0f9…` | Parent's adoption candidate. Removable; contents reachable from `main`. |
| 5 | `C:\Users\taomar\.copilot\session-state\b065f09b-…\files\worktrees\canonical-table-carrier` | detached | `3da502f…` | Temporary review worktree. Removable; commit reachable from `main`. |
| 6 | `C:\Users\taomar\.copilot\session-state\b065f09b-…\files\worktrees\ranking-telemetry` | detached | `4f9f21a…` | Temporary review worktree. Removable **only** if `taomar-microsoft-ranking-telemetry` is kept, otherwise `4f9f21a` becomes unreachable. |
| 7 | `C:\Users\taomar\Downloads\policy-extractor-azure-deploy` | `azure-deploy` | `3815866…` | **Separate Azure checkout. Clean (0 status entries). Keep, never deploy.** |
| — | `…\6713376d-…\files\six-unit-audit\adoption\detached-worktree` | detached | — | Already removed by the adopter. |

The visible reviewer worktrees `taomar-microsoft-bookish-system` and
`taomar-microsoft-symmetrical-waddle` no longer appear in `git worktree list`; their
sessions were archived. Their commits survive on named branches and on `main`.

### 5.1 Reachability — what must not be pruned

| Object | Reachable from |
|---|---|
| `d3bb0f94…`, `3da502fe…`, `3414811…`, `be26081…`, `b845918…`, `acff6e8…`, `5d731b6…`, `e689bf7…`, `c0972c8…` | `refs/heads/main` |
| `4f9f21a…` (original ranking object) | `refs/heads/taomar-microsoft-ranking-telemetry` **only** |
| `cf2d0f10…` | `refs/heads/archive-inflight` **only** |
| `b13f168…` | `refs/heads/taomar-microsoft-private-base-publisher` **only** |
| `8bc0657…` | `refs/heads/taomar-microsoft-private-base-publisher` **only** |
| `3815866…`, `a17525ca…` | `refs/heads/azure-deploy` **only** |

There are also 6 `refs/copilot-preserved/6d6207dd-…/…` refs and tags `stable1`
(`deba264c…`) and `v3` (`dab017e8…`). Other local branches:
`taomar-microsoft-advancedtooling` (`13e67f0b…`), `taomar-microsoft-cuddly-garbanzo`
(`db882ef…`), `taomar-microsoft-entity-recognition-skill-eval` (`bcb4f7a0…`),
`taomar-microsoft-fluffy-train` (`b491fb4b…`), `taomar-microsoft-modularize-codebase`
(`dd655214…`), `taomar-microsoft-policy-queue-and-backlog` (`51270f21…`),
`taomar-microsoft-canonical-table-carrier` (`3da502fe…`),
`taomar-microsoft-policyverbatim-v3-oversight` (`db882ef…`).

**Do not run `git gc --prune`, `git reflog expire`, or delete branches during the host
move.** Migrate the whole `.git` directory intact.

---

## 6. Architecture decisions and invariants

### 6.1 Native Rule Retrieval — architectural resolution

**Problem.** "Rule mode" was rule-*first*, not rule-*only*: it expanded rule matches
into parent policies and fell back to policy search. Evaluation arms B/D/F were
therefore not measuring rule retrieval at all.

**Decision.** Replace expansion with true native retrieval. Rule mode issues **no**
policy query, uses **no** policy fallback, returns native `rules[]`, and never expands
into parent policy bodies. It may add bounded related/override rules.

**Invariants.**
- Two disjoint envelopes: `policy_retrieval_v1` → `policies[]` with no `rules`;
  `rule_retrieval_v1` → `rules[]` with no `policies`. Mixed payloads fail closed.
- Separate receipts `case_decision_rule_v1` and `case_decision_rule_light_v1`,
  distinct from policy receipts. Historical V1/V2 receipts stay parseable and
  verifiable unchanged.
- Rule citations carry **source identifiers only**, never policy bodies.
- The rule hash seals rule IDs, grounding/admission state, source identity,
  dispositions, decision tracks, citations, and requested-vs-executed mode.
- Tag-first, fail-closed route and OpenAPI behaviour.
- A Rule Search outage propagates as **HTTP 503**, never as a false "no match".
- Budget: Azure Search scan ≤ 200 rule hits; semantic reranker window ≤ 50; final
  delivered rules 0–12; absolute relevance floor 1.75; exact serialized UTF-8 cap
  **40,000 bytes** including selector-catalogue bytes; whole-rule boundaries only with
  omissions named; an oversize first rule raises a typed refusal rather than a false
  empty result.
- Semantic score labels seal the score they name.

**Measurement (frozen, not a universal claim).** 1–12 rules, maximum exact transport
39,562 UTF-8 bytes; rule payload smaller than policy payload in 6 of 10 fixtures. There
is **no** claim that rule mode is always smaller.

### 6.2 Evidence-complete decisions — prompt v16 / case-plan v4

**Escalation.** AIS-09 showed both required policies reaching the gather while the
model cited only one. Post-processing was not removing the second — the contract simply
never required completeness. A first patch added sealed cited/uncited **disclosure**;
the parent correctly reclassified that as **containment**, because it exposed omission
without preventing an incomplete *successful* answer.

**Decision.** Atomically bump `ai-case-intent` prompt v15 → v16 and case-plan to v4;
require model-declared **total** evidence/subpart dispositions; validate totality,
recognized disposition tokens, citation ownership for used evidence, and disclosure for
set-aside evidence.

**Invariants.**
- Missing, incomplete, or relevant-but-unused dispositions **fail closed** to
  `not_settled_by_rules`. **No new verdict status was introduced.**
- Verdict extraction must occur **after** every status repair, or receipts contradict
  themselves.
- Legacy receipt hashes stay compatible because optional composition data is sealed
  only when present.
- Blast radius: 14 test files / 82 payload sites updated.

Owning module: `repository\src\policy_platform\infrastructure\assistants\ai_case_evidence_accounting.py`
(new), with `ai_case_intent.py` and `ai_case_plan.py`.

### 6.3 Entitlement versus present approval

**Root cause.** A conferred entitlement was being read as immediate operational
approval — a decision-contract defect, not a corpus quirk.

**Decision.** Preserve the entitlement and any later evidence obligations, but return
`not_settled_by_rules` for *present approval* when the rules are silent.

**Invariants.**
- `settles_requested_decision` is read **only** as a real boolean. Explicit `false`
  blocks an answer; **absence is not interpreted as denial**.
- No invented missing certificate, and no AIS-specific logic.

Guard: `tests\unit\test_a_conferred_entitlement_is_not_an_approval.py`.

### 6.4 Property-derived coverage expansion

**Root cause.** Coverage expansion was gated by an **enumerated** list of ranking
modes, which silently excluded semantic ordering (AIS-08: a strong semantic elbow
selected rank 0 and left the budget unused).

**Decision.** Derive eligibility from a **property**: `relevance cut applied && exact
policy budget still unfilled`. Thresholds and budgets unchanged.

Guard: `tests\unit\test_coverage_expansion_is_eligible_by_property.py`.

### 6.5 Consume Demo — request mode and native parsing

**Request mode (ordinal 03).** `rule_retrieval` is written into the request body
**only when true**, so default wire bodies and canonical request hashes stay
backward-compatible and the client preview stays aligned with the server's idempotency
binding.

**Native parsing/rendering (ordinal 04).**
- Discriminate on `schema_version`.
- The **own** collection must exist and be an array; empty is a legitimate negative.
- The **opposite** collection must be absent or empty (rolling compatibility);
  non-empty or malformed opposite shapes fail closed and visibly.
- Unchecked policy-envelope casting removed; native rule rendering has no parent
  grouping.
- Malformed-response diagnostics expose **structural summaries only** and must never
  copy raw policy/rule content into the support clipboard.

**Governance note (resolved).** The ordinal-03 bytes were originally written by session
`d99011fe-a8c3-4032-872b-1643baaef994`, whose own task was read-only — real scope
drift. Authorship was proven from archived events; a **narrow retroactive approval**
was issued for exactly the validated patch bytes (sha256 `3471d8ab…`), explicitly not a
blanket approval of that session's work.

### 6.6 All-published-rule index foundation (ordinal 00)

**Escalation.** Native Rule Retrieval could not be a coherent commit because it assumed
a persisted all-published-rule corpus scope that did not exist in `c0972c8`.

**Decision.** Extract *only* the scope/manifest/filter/readiness/validation hunks from
`policy_rule_slice.py`, `policy_index.py` and `projection_faithfulness.py`, plus their
focused guards, into a prerequisite commit. Explicitly excluded from ordinal 00:
PolicyIndexBuild progress/history, auth, upload UI/docs, migrations, and unresolved
transport work.

**Invariant.** Scope `all_published_rules_v1`; projection `policy-english-projection-v1`
validated by `policy-projection-quality-v1`; manifest expected counts must equal
uploaded counts.

Ordinal 00 preserves the existing binary-classified CRLF form of
`test_the_corpus_is_indexed_in_one_language.py`.

### 6.7 gzip and Search projection optimization (ordinal 01a)

Two accepted **earlier Payload** optimizations had been misclassified into the Rule
patch: HTTP gzip response compression and Search result select-list narrowing. They
were re-extracted into their own ordinal so each commit has one owner. Azure overlap
review: only `src\policy_platform\api\app.py` is shared with the Azure work, and its
three gzip hunks contain **no** Azure local-auth or Integration content.

### 6.8 Criterion provenance v3.1.0

**Escalation.** Unsupported, heading-derived, or inferred rubric criteria were being
converted into product failures.

**Decision.** A fail-closed provenance guard. Only criteria with normative source/rule
provenance may create product failures; heading-derived, question-inferred,
unsupported, unavailable, or pending-human criteria remain rubric errors or unscorable.

**Invariants.**
- AI review must **never** be represented as human semantic confirmation.
- Old-rubric replay is explicitly labelled non-equivalent.
- **Partition validation must precede semantic overlay application.** The first merge
  correctly failed closed because Batch 2 and Batch 3 overlapped on `HW-05:R4` and
  omitted `AIS-08:R5`; a repair session re-cut Batch 2 to positions 39–76.

### 6.9 Canonical table-structure carrier

Generic carrier; no corpus or domain shaping. `covered_columns` was **moved** from
`structural_graph._covered_columns` into the contract so the graph and the carrier
cannot disagree about a span — duplication removed, not added. `table_structure_of` /
`table_cell_of` normalise the two converter shapes (row-emitting vs cell-emitting) in
one place, so no consumer needs to know which parser ran.

**Invariants preserved (verified, not assumed).** `_clause_ref` is computed from typed
`element.source_fragments` *before* the sidecar is appended to the separate
`provenance` list, so refs are unchanged. `element_identity()` takes explicit keyword
scalars only. Rebuild reuses the stored `clause.element_id` and never recomputes an id.
Sidecars are matched by **shape**, so foreign sidecars are stepped over and legacy
clauses rebuild byte-for-byte.

**No migration required** — no schema change, no Alembic revision; rides existing
nullable JSONB with all new fields optional.

**Forward-only behavioural tightening (disclosed):** `canonical_fidelity` can now
return `failed` where it previously returned `unprovable`, for a row whose recorded
cells do not rejoin to its text. It fires only on newly-ingested rows. Existing data
will **not** gain table ordinality without separately authorized re-extraction.

### 6.10 Ranking-component telemetry

Ownership is confined to exactly three `record_ranking` call sites, all inside
`AzureSearchClient.vector_search` (transport fault / ≥400 / success). No caller-level
instrumentation, because callers rewrite scores (semantic over base) before selecting.

**Invariants.** `VECTOR_FIELD` is the same literal, so the request body is
byte-identical. `observed` is built after the body is complete and only reads it. The
returned list is the same object in service order. A bare `raise` preserves exception
and traceback. No retry was added; the public signature is unchanged. Hashes are
deterministic and **names-only**.

**Load-bearing design point.** The success-path call site has no `try`/`except`, so the
failure guard had to live *inside* `record_ranking` — and it does, wrapping build and
emit in one `try`/`except` with a nested guarded warning. That also prevents a telemetry
fault from replacing the original exception on the failure path.

### 6.11 Cross-cutting generalization constraints (repository law)

- AIS is a **regression witness only**.
- No production logic may contain AIS IDs, provision IDs, source filenames, question
  strings, observed scores/ranks, or corpus-tuned thresholds.
- Anti-corpus AST guards must cover **every** modified executable module. The numeric
  leakage guard covers integers **and** floats while excluding booleans.
- Required controls: synthetic, second-corpus/HW, non-Latin, inversion, mutation,
  recall and precision cases.
- A validation guard requires a refusal test **and** a control proving it does not
  refuse everything.
- No caching or memoization in the decision path.
- One writer at a time in the shared checkout; long-running tests must print progress
  (no silent buffered pipelines).

### 6.12 Withdrawn / containment items

| Item | Classification |
|---|---|
| `llm_reasoning_view` experiment + `test_the_model_reads_a_reasoning_view.py` | **Withdrawn.** Must not be committed as product. It *is* present in the publisher's archival snapshot as in-flight source. |
| Composition **disclosure**-only patch | **Containment**, superseded by the prompt-v16 evidence-completeness contract (§6.2). |
| Local-mode one-replica enforcement | **Containment.** Horizontal scaling requires shared transactional lockout state. |
| Score-scale disclosure (Rule Retrieval stage 2) | **Withdrawn/partial.** Incomplete working-tree patch; not verified; not authority to change selection. |

---

## 7. Validation ledger

### 7.1 Six-unit candidate sequence (session `6713376d`, private copies only)

| Gate | Result |
|---|---|
| Sequential apply of all six patches from exact HEAD `c0972c8` | **passed** |
| Per-unit base hash / result hash / changed-path-set / excluded-file checks | **passed** |
| Candidate union | 48 paths; 963 excluded HEAD files unchanged |
| Boundary imports | **passed** |
| Focused backend — foundation + 01a | **231 passed** |
| Focused backend — Rule | **524 passed** |
| Focused backend — Payload | **448 passed** |
| Full backend (246 files, 9 visible shards) | **5,192 passed, 23 skipped, 0 failed** |
| Consume Demo (bounded shards 98 + 143 + 19) | **260 passed** |
| Consume TypeScript `tsc` | **passed** (exit 0, empty log) |
| Post-test source integrity | 1,011 files checked, **0 changes** |
| Candidate vs current tree | 43 exact full-file matches, 5 expected hunk-scoped mixed paths, **0 unexpected mismatches** |
| Secret / content scan | 0 high-confidence secrets, 0 live endpoints, 0 raw source-policy or live-corpus text |
| Shared-repository terminal non-mutation gate | HEAD, branch, tree, logical index, porcelain, tracked patch, cached diff, refs, stash, **all 121 dirty-file hashes**, and the 37,199-file content tree all unchanged |

The 23 skips are expected in a no-live-call audit: optional graph/docling dependencies,
local-only documentation/accounts fixtures, and local Postgres fixtures that were
deliberately not contacted. Environment notes: dependencies **not** installed, no live
calls, no database calls, `TEST_DATABASE_URL` pointed at the non-secret
`localhost:1` refusal address, and Git metadata was initialized **only inside the
private tree** so publication guards could execute.

### 7.2 Historical track validation (as reported by owning sessions)

| Track | Result |
|---|---|
| Native rule backend, full suite | 5,471 passed, 18 skipped, 0 failed |
| Native rule focused final review | 301 / 301 |
| Anti-corpus guards | 67 / 67 |
| Consume Demo full suite | 260 / 260; TypeScript passed |
| Consume new parser/render/leakage tests | 19 / 19 |
| Consume mutation proof | weakening the parser produced exactly the expected 5 guard failures |
| `apps/web` TypeScript | passed |
| `apps/web` full baseline | 1,902 / 1,903 — the single polling timeout passed 25/25 in isolation; attributed to full-suite CPU contention |
| Payload after prompt-v16 + entitlement + coverage | 5,557 passed, 18 skipped, 0 failed |
| Azure local-auth: backend/IaC/security | 69 passed |
| Azure local-auth: frontend auth/equivalent paths | 93 passed |
| Azure local-auth: full frontend | 1,821 passed |
| Rubric provenance guard, isolated | 17 / 17 |
| Provenance harness v3.1.0 unit tests | 31 passed, 0 failed |
| Provenance negative controls | 8 passed, 0 failed |
| Provenance leakage scan | 0 hits of 167 source-literal candidates and 20 question literals |
| Provenance deterministic regeneration | 2 passes, byte-identical |

### 7.3 Feature-commit validation, with the baseline defect

Both feature reviewers ran the full unit suite at HEAD and at base `3414811` and
**programmatically diffed the failing/erroring node IDs**.

| Suite run | passed | failed | skipped | errors |
|---|---:|---:|---:|---:|
| Base `3414811` (both reviewers) | 5,169 | **9** | 23 | **12** |
| HEAD `3da502f` — table carrier | 5,256 | **9** | 23 | **12** |
| HEAD `4f9f21a` — ranking telemetry | 5,216 | **9** | 23 | **12** |

Failing and erroring node IDs are **identical** between HEAD and base in both cases —
**zero regressions**. Net +87 passing for the table carrier; +47 for ranking telemetry
(43 new + 4 anti-corpus parametrizations). Focused: table carrier
`test_a_table_keeps_its_shape.py` 83 passed (81 cases + 2 guards) and a 35-file
targeted superset at 827 passed / 6 skipped / 12 corpus errors; ranking telemetry
43 new + 64 anti-corpus passed and 456 targeted passed / 0 failed.

#### The two baseline-known groups

1. **12 errors — absent corpus, by design.** Caused by the gitignored `data/documents/`
   store not being present. Genuine absent-artifact-by-design; **not** a code defect.
   These will reappear on any host that does not carry the runtime document store.

2. **9 failures — `503`, and this one is a real test-harness defect.**
   The harness **never patches `get_settings` on `api/routers/ai.py`**, so those tests
   read the ambient `.env` and fail with HTTP 503 from Azure OpenAI when a real `.env`
   is absent (or wrong).

   > **File:** `repository\src\policy_platform\api\routers\ai.py`
   > **Classification:** pre-existing at base `3414811`; unrelated to any feature work
   > in this programme; **left unfixed on purpose** under scope discipline.
   > **Recommendation:** fix it as its own separately authorized change — patch
   > `get_settings` on the `api.routers.ai` module in the fixture so the tests stop
   > depending on ambient environment. **Do not** fold it into feature work, and do not
   > silently treat these 9 as environmental: the rule "before calling a test failure
   > environmental, check ambient `.env` inheritance" is exactly what exposed it.

#### Methodological correction worth preserving

The table-carrier reviewer's first baseline used `git archive` and reported **57**
failures at base. That was a measurement artifact: two publication tests shell out to
`git check-ignore`, which is impossible without a `.git` directory. Re-running in a
proper detached worktree (since removed and pruned) produced the true **9**. Any future
baseline must be taken in a real worktree, never from `git archive`.

### 7.4 Outstanding validation gaps

- No **live native-rule AIS rerun** has occurred.
- No **client-side live HTTP arm-F** run has occurred.
- The live local database is **one Alembic revision behind**: current `f4b8c2e97d31`,
  repository head `a1c5f0b3e284`. **No migration was applied.**
- Full combined backend + both frontend suites have not been run against current `main`
  on a machine with a complete environment.

---

## 8. Current dirty / in-flight work

### 8.1 Classification

86 normal status entries = 48 ` M` + 35 `??` + 3 ` D`; 87 exhaustive.

| Class | Count | Meaning |
|---|---:|---|
| Genuine tracked modifications (safe source) | 42 | Real uncommitted work from the pre-adoption tree |
| Synthetic ` M` | 6 | Adoption-B artifacts (§2.4) — **not** reverts |
| Synthetic ` D` | 3 | Adoption-B artifacts (§2.4) — **not** deletions |
| Untracked new source/test/migration/UI files | 34 | Real new work |
| Untracked local tool state | 2 | `.serena\.gitignore`, `.serena\project.yml` — **excluded** |

The publisher's `safe-inflight-paths.txt` enumerates **76** safe source paths
(42 tracked + 34 untracked). Its `msg-snapshot.txt` states: *"Includes 42 modifications
to tracked files and 34 previously untracked source, test, migration and UI files.
Bytes are taken verbatim from the shared checkout and were verified against the
pre-adoption hashes. Excludes local tool state under `.serena`, and carries none of the
secret, runtime data, dependency, build or session material that the repository already
ignores."*

### 8.2 The five mixed paths — hunk-level merge required

These carry a mixture of already-committed and still-uncommitted hunks. They are the
reason wholesale staging is unsafe:

1. `src\policy_platform\api\app.py`
2. `src\policy_platform\infrastructure\projection\policy_rule_slice.py`
3. `src\policy_platform\infrastructure\search\policy_index.py`
4. `tests\unit\test_no_m2_code_is_shaped_around_a_corpus.py`
5. `tests\unit\test_the_corpus_is_indexed_in_one_language.py`

### 8.3 Untracked new work (34 safe paths)

Backend: `alembic\versions\a1c5f0b3e284_policy_index_builds.py`,
`alembic\versions\f4b8c2e97d31_api_subscription_keys.py`,
`src\policy_platform\api\routers\integration.py`,
`src\policy_platform\api\routers\policy_index_console.py`,
`src\policy_platform\infrastructure\errors.py`,
`src\policy_platform\infrastructure\ingestion\mixed_script_text.py`,
`src\policy_platform\infrastructure\ingestion\upload_progress.py`,
`src\policy_platform\infrastructure\ingestion\visual_page_reading.py`,
`src\policy_platform\infrastructure\persistence\subscription_keys.py`,
`src\policy_platform\infrastructure\projection\llm_reasoning_view.py` *(withdrawn
experiment — archive, do not ship as product)*,
`src\policy_platform\infrastructure\search\policy_index_build_progress.py`.

Frontend: `apps\web\src\IntegrationPage.tsx` (+ test),
`apps\web\src\PolicyIndexConsolePage.tsx` (+ test),
`apps\web\src\components\PolicyIndexBuildHistoryTable.tsx`,
`apps\web\src\components\PolicyIndexProgressPanel.tsx` (+ test),
`apps\web\src\components\UploadProgressPanel.tsx` (+ test),
`apps\web\src\operationId.ts`,
`apps\web\src\integrationCapabilityIsAskedOnlyAfterSignIn.test.tsx`,
`apps\web\src\policyIndexSurfaceScope.test.tsx`.

Tests: `test_a_flagged_page_is_read_again.py`,
`test_a_generated_key_survives_a_rendering.py`,
`test_a_literal_survives_a_rendering.py`, `test_a_number_survives_a_rendering.py`,
`test_a_recovered_reading_order_is_replayable.py`,
`test_an_administrator_can_issue_an_api_key.py`,
`test_an_upload_reports_its_own_progress.py`, `test_error_descriptions.py`,
`test_interleaved_extraction_is_reported.py`,
`test_one_index_build_runs_at_a_time.py`, `test_the_model_reads_a_reasoning_view.py`.

### 8.4 Excluded material — never published

Excluded because the repository already ignores it, or because it is local-only:

- **Secrets:** `.env`, `.env.*`, `*.env`, `apps\web\.env`,
  `apps\consume-demo\.env.local`, `services\policy-decision-api\.env`,
  `.local-accounts.txt`, `.local-signing-key*`, `*.pem`, `*token*.txt`,
  `*token*.json`, `*.token`, `.azure\*` (except `deployment-plan.md`).
- **Runtime data:** `data\documents\`, `data\backups\`, `App_Data\`,
  `.mutation-check.lock`.
- **Dependencies/build:** `.venv\`, `.venv-graph\`, `venv\`, `node_modules\`,
  `apps\web\node_modules\`, `apps\consume-demo\node_modules\`, `dist\`, `build\`,
  `*.egg-info\`, `src\policy_platform.egg-info\`.
- **Caches:** `__pycache__\` (≈45 directories), `*.pyc`, `.pytest_cache\`,
  `.serena\cache\`, `.coverage`, `htmlcov\`.
- **Local session/agent material:** `AGENT_PROGRESS.md`, `HANDOVER*`, `handover*`,
  `docs\SESSION_HANDOFF.md`, `docs\adr\`, `docs\handoff\`, `docs\handover\`,
  `docs\internal\`, `docs\failures\`, `todo\`, `todos\`, `TODO.md`, `.impeccable\`,
  `.github\skills\`, `skills\`, `.playwright-mcp\`, `.artifacts\`, `.private\`,
  `Instructions for Claude Opus 5_*.md`, `.serena\project.local.yml`.
- **Logs and scratch:** `*.log`, `backend_stdout.log`, `backend_stderr.log`,
  `apps\web\vite.out.log`, `apps\web\vite.err.log`, screenshot PNGs at the repo root.

95 ignored entries were present at snapshot.

### 8.5 How the publisher must merge pre-adoption dirty intent

**This is the core reconciliation rule and it must survive the host move.**

The archival snapshot `cf2d0f10…` was written against **`3414811`** — the base the
dirty bytes were actually authored on. Merging into `d3bb0f94…` with merge base
`3414811` means the two feature commits appear as **additions on one side only**, so
the newly committed feature files (`ranking_telemetry.py`,
`test_a_ranking_says_which_component_ranked_it.py`,
`test_a_table_keeps_its_shape.py`) **survive untouched instead of reading as
deletions**. Choosing any other base — or replacing wholesale — would delete them.

At snapshot the publisher had produced merge commit `b13f168…` and hand-resolved four
additive-on-both-sides conflicts:

| File | Resolution |
|---|---|
| `canonical_rebuild` | The table carrier generalised sidecar handling to any namespaced provenance entry, which is exactly what the reading-order record is; the recovered order now travels through the general filter, so both the grid and the replay proof come back on rebuild. |
| `document_extraction` | A clause appends **both** records to its provenance. |
| `search_client` | Keeps the retry helper **and** the serving path's deliberate refusal to use it, and keeps the ranking record around that same call, which the code below the merge already depended on. |
| corpus-shape guard (`test_no_m2_code_is_shaped_around_a_corpus.py`) | Lists every newly authored module from **both** sides. |

Rules for any repeat of this on the new host:
1. Merge base **must** be `3414811752cc2cb08bf26b87dd8d8fa2c22baf65`.
2. Reconcile **by hunk**, never by wholesale replacement.
3. Never delete the new feature files to "resolve" a synthetic `D`.
4. Keep `.serena\**` and every §8.4 class out.
5. `llm_reasoning_view.py` and its test travel as **archival in-flight source**, not as
   shipped product.

---

## 9. Azure status

**Deployment is halted by user instruction.** The Azure Deploy successor
(`d185704d-4bd4-4a2a-b2f4-8a6fa3f25961`) completed read-only verification, made no
mutations, and was archived.

| Item | State |
|---|---|
| Separate checkout *(historical, source host only)* | `C:\Users\taomar\Downloads\policy-extractor-azure-deploy` — **not required on the target host**; the commit's content is vendored at `handover/artifacts/azure/AZURE_3815866.patch` |
| Branch / HEAD | `azure-deploy` @ `381586688f0337be15dcc1d42d2be7d4b0fe4936` |
| Working tree | **clean** — 0 status entries (verified) |
| Commit subject | "Add production local authentication" |
| Parent | `a17525cad24b3af262290826eb9846f90acea9ae` ("Fix reproducible Azure deployment", the explicitly authorized preservation commit) |
| Pushed? | **No** |
| Deployed? | **No** |

> **`381586688f0337be15dcc1d42d2be7d4b0fe4936` must never be deployed, pushed, or
> merged without new explicit authorization.** It is preserved separately on purpose.

Scope of that commit (historical): explicit `local|entra` human-auth modes independent
of machine API mode; Key Vault-backed Argon2 credentials; RBAC; token/key rotation;
bounded last-known-good behaviour; secure HttpOnly cookies; CSRF; stale-cookie logout;
spoof-resistant limiter containment; one-replica local-mode enforcement; nginx
Host/SNI routing fix; Entra private Blob token store; private endpoint/DNS; secure SAS
flow; v2 issuer/audience/scope predeploy validation; one cookie/CSRF-aware fetch seam
for all direct SPA calls; production docs/OpenAPI exposure disabled.

Live-infrastructure facts (**historical**, verified 2026-09-04; re-verify before
trusting): the Azure deployment was live and billing, Entra sign-in disabled, API
`/health` and `/docs` HTTP 200, web root HTTP 200. Live Azure AI Search then showed
`ais-e2e` 39 policy docs / 293 rule docs and `hw-policy` 60 / 189, both manifests ready
and quality-passed under scope `all_published_rules_v1`.

Future Azure/application merge constraint: preserve **one** async `_headers` definition
and its **eight** awaited callers while retaining Search retry behaviour.

---

## 10. Criterion provenance successor

**Vendored in full at:**
`handover/artifacts/provenance/criterion-provenance-successor-v1.0.0/` — 86 files,
structure preserved, internal hashes still valid.
*(Historical source-host location:
`C:\Users\taomar\.copilot\session-state\71c6d508-6a53-4419-8513-eb812f72ca69\files\criterion-provenance-successor-v1.0.0` — non-actionable.)*

| Field | Value |
|---|---|
| Bundle | `consume-api-provenance-harness-v3.1.0` |
| Harness | `consume-api-provenance-harness/3.1.0` (predecessor `3.0.0`) |
| Rubric | `3.1.0` (schema `consume-api-evaluation-rubric/3`; predecessor `3.0.0`) |
| Manifest | `2.1.0` (schema `consume-api-matrix-manifest/2`; predecessor `2.0.0`) |
| Version decision | minor additive — provenance added under unchanged major schemas |
| Canonical bundle SHA-256 | `037a40264acdde60c2b769f37e3eba5fe4af01dc980292d90fd4cab03c569c75` |
| Canonical record format | sorted UTF-8 relative path + NUL + lowercase file SHA-256 + LF |
| Included | 80 files, 2,068,536 bytes |
| Status | `ready_for_immediate_offline_adoption_execution_disabled` |
| **Execution** | **disabled** (`execution.enabled: false`, `pending_manifest_authorized: false`) |

### 10.1 Counts

| Metric | Value |
|---|---:|
| Criteria total | 128 |
| Scorable | 20 |
| Unscorable | 95 |
| Unresolved | 13 |
| Unscorable findings | 108 |
| Changed criteria | 18 |
| Newly scorable | 5 |
| Partition size validated | 113 (pairwise disjoint; 0 omissions, 0 overlaps, 0 extras) |

### 10.2 Source classifications

| Classification | Count |
|---|---:|
| Mechanically source-supported | 5 |
| Semantic support **pending human confirmation** | **19** |
| Product-decision-required | 8 |
| Structural/harness — not product law | 80 |
| Unsupported or contradicted rubric | 1 |

### 10.3 Key output hashes

| Artifact | SHA-256 |
|---|---|
| `provenance/criterion-provenance-merged-overlay.json` | `41b66da713ca9c49b454c7958b94fb229a4f7b7d0420c2b471be50ba05ec8e88` |
| `provenance/criterion-provenance-merged-ledger.json` | `80f785a0f989b25f490c84bd0b1b32f98622c3d64da818a42aed061c6e15f185` |
| `evaluation-rubric.json` | `a2b547b74b8d7e44d853c128593aa45e475140929b55e127a2e56ad2fd3a7792` |
| `manifest.pending.json` | `3e7c24a0e6c93bf3205874d63361e0fa1dbe3e52405887a983d3d1efb34cb80b` |
| `consume_matrix_runner.py` | `58c6c180e4e49f4a1cc8213ef4bbfc3c8cd0771d5120b1bf3867675007651aba` |
| `rubric_provenance.py` | `1298c04b99cf6b9ba3d87ae9eac09a4dbd0d9d4f78a622ff87d4287c82e96507` |
| `provenance/SOURCE_NON_MUTATION.json` | `43c0e9dd97b5c4248998d9af39b286f5d624dac7bb06e387a12faaeef91396b9` |

### 10.4 Remaining open items

1. **19 semantic-pending criteria require independent human confirmation** — 12
   unresolved + 7 unscorable. **PENDING — human, not AI.**
2. **`HW-03:manual-1`** remains unsupported/contradicted and unresolved. **BLOCKED.**
3. 2 criteria require authoritative **product decisions** (the classification bucket
   carries 8 product-decision-required criteria overall).
4. Structural and harness criteria remain non-product-law by design.
5. Historical replay remains contextual and non-equivalent.
6. **Execution remains disabled.** Do not run the matrix without new authorization.

### 10.5 Predecessor no-merge package (retained)

`criterion-provenance-merge-blocked-v1.0.0` (7 files, 171,548 bytes, tree sha256
`ce5e46c0df9c4415c3f446f66ec647a93e171ecb5d785c0d0e9c4c84f7607bac`) records the
correct fail-closed refusal caused by the Batch 2 / Batch 3 partition defect. Keep it —
it is the evidence that partition validation precedes overlay application. Note that
`HANDOFF_HASH_MANIFEST.json` at the session `files` root belongs to that **blocked**
stage and still reports `successor_artifacts.created: false`; it does **not** describe
the successor bundle.

### 10.6 Corrected evaluation position (authoritative)

27 true product failures, 11 rubric errors, 0 unresolved, 0 proven regressions. The 11
rubric errors were AIS-06 ×6 (unsupported requirement that overtime approval be
written) and AIS-02 ×5 (unsupported pre-leave certificate requirement). The remaining
AIS-02 call was a genuine reasoning defect: entitlement did not establish immediate
operational approval (§6.3). Matrix totals: 180 calls, all HTTP 200; combined
historical reconciliation 109 PASS / 71 FAIL; valid-policy baseline A/C/E 52 PASS / 38
FAIL; defective old rule mode B/D/F 57 PASS / 33 FAIL, excluded from rule-only
conclusions.

---

## 11. Pending decisions and actions — target host

**Authoritative machine-readable list:** `handover/PENDING_DECISIONS_AND_TASKS.json`,
tasks `T-01` onward. This section is the narrative companion. Work the tasks in order;
each gate must pass before the next begins.

### Stage A — Clone and verify (`T-01` … `T-03`)

1. **`T-01`** Authenticate to GitHub as `taomar`, clone
   `https://github.com/taomar/PolicyVerbAItim`, confirm a clean tree, then verify
   `handover/HANDOVER_HASHES.sha256` recursively — **0 mismatches** — and confirm every
   path declared in `handover/artifacts/BUNDLED_ARTIFACTS.json` exists and matches.
   A `Repository not found` error means unauthenticated or non-member; fix
   authentication before concluding anything about the repository.
2. **`T-02`** Reconcile what you cloned against the recorded publication chain
   (`cf2d0f10… → b13f168… → 8bc0657…`) and against the nine-commit product line in §3.1.
   This package deliberately asserts **no** final remote SHA — it was written while the
   publication was still in flight, and `publication.final_remote_sha` is `null` with
   `push_status: "UNVERIFIED"`. Record the SHA you actually got.
3. **`T-03`** Confirm the off-main Azure content is present as
   `handover/artifacts/azure/AZURE_3815866.patch` plus its overlap analysis. Do not
   apply it.

> There is no "copy the old host" step. If you find yourself looking for one, re-read §0.

### Stage B — Decide whether the system must run (`T-04` … `T-06`)

4. **`T-04`** Decide explicitly. Reading, reviewing and auditing need nothing further.
5. **`T-05`** *(only if running)* Restore secrets and runtime data **out of band** —
   `.env` family, local account store, signing key, `*.pem`, file-borne tokens, Azure
   CLI local env, and the runtime document store. Never commit any of them. Restoring
   the document store is what removes the 12 baseline errors; leaving it absent is a
   valid, recordable choice.
6. **`T-06`** *(only if running)* Recreate the Python and Node environments. Approved
   feeds: PyPI `packagefeedproxy.microsoft.io/pypi/simple`, NuGet
   `packagefeedproxy.microsoft.io/nuget/v3/index.json`.

### Stage C — Validate (`T-07`)

7. **`T-07`** Establish the baseline **in a real worktree** — never via `git archive`,
   which strips `.git` and makes two publication tests that shell out to
   `git check-ignore` fail spuriously (this produced a false 57-failure reading once
   already). Expect **9 failed / 23 skipped / 12 errors** on a complete environment, and
   compare **node IDs**, not just counts. Do not run the backend suite and both frontend
   suites concurrently.

### Stage D — Separately authorized work (`T-08` … `T-15`)

8. **`T-08`** Fix the test-harness defect in
   `src/policy_platform/api/routers/ai.py` — the harness never patches `get_settings`
   on that module, so 9 tests read ambient configuration and fail with 503. Own commit,
   own review; do **not** fold it into feature work and do **not** write it off as
   environmental.
9. **`T-09`** Decide the canonical `origin` remote deliberately.
10. **`T-10`** Resolve the residual in-flight source: decide per-hunk what is product and
    what stays archival, treat the five mixed paths carefully, and explicitly settle the
    fate of the **withdrawn** `llm_reasoning_view` experiment and its test. If you ever
    re-derive this history, merge base **must** be `3414811752cc2cb08bf26b87dd8d8fa2c22baf65`.
11. **`T-11`** Decide on the pending database migration. Do not migrate a live database
    without authorization.
12. **`T-12`** Complete the human provenance review — 19 semantic-pending criteria and
    `HW-03:manual-1`. **AI review must never be represented as human confirmation.**
    Harness execution stays disabled.
13. **`T-13`** Azure remains halted. Never deploy, push or merge
    `381586688f0337be15dcc1d42d2be7d4b0fe4936`.
14. **`T-14`** Close the outstanding validation gaps: live retrieval rerun, client-side
    arm-F run, and a full combined backend + frontend run on a complete environment.
15. **`T-15`** *(optional)* If a zero-whitespace-warning policy is enforced, clean and
    rebase ordinals 01 and 02 **together** and re-run every gate.

### Stage E — Process (`T-16`, `T-17`)

16. **`T-16`** Fix the review-seeding defect before commissioning any new review
    workflow: assert and verify the exact base SHA, and refuse to proceed on mismatch.
17. **`T-17`** Any push of product history requires **new** authorization. The prior
    one-push authorization covered the source host's archival publication only.

## 12. Security

**Classes and paths only. No secret value appears anywhere in this package.**

| Class | Locations (paths only) |
|---|---|
| Environment secrets | `.env`, `.env.*`, `*.env`, `apps\web\.env`, `apps\consume-demo\.env.local`, `services\policy-decision-api\.env`, `infra\parameters\baseline.env` |
| Local credential store | `.local-accounts.txt`, `.local-accounts*`, `local-accounts*`, `*.local-accounts*` |
| Token-signing key | `.local-signing-key*` |
| Certificates / private keys | `*.pem` (published exception: `*.example.pem`) |
| Bearer/session tokens written to files | `*token*.txt`, `*token*.json`, `*.token`, `.token`, `.tokens` |
| Azure Developer CLI local environments | `.azure\*` (published exception: `.azure\deployment-plan.md`) |
| Key Vault-held credentials | Azure Key Vault (referenced by the preserved `azure-deploy` branch; **never** materialised into the repository) |
| Generated API subscription keys | Runtime + database only; `src\policy_platform\infrastructure\persistence\subscription_keys.py` is the code, not a store |
| Runtime document store | `data\documents\`, `data\backups\`, `App_Data\` |
| Live endpoints / connection strings | Only in the environment-secret class above |
| Local session/agent records | `AGENT_PROGRESS.md`, `HANDOVER*`, `docs\SESSION_HANDOFF.md`, `docs\adr\`, `docs\handoff\`, `docs\internal\`, `docs\failures\`, `.impeccable\`, `skills\`, `.github\skills\`, `.private\`, `.artifacts\` |

Controls that are in force and must stay in force:

- Never print, log, echo, or preserve secrets from `.env`, Key Vault, request headers,
  logs, connection strings, tokens, or generated subscription keys.
- `test_publication_excludes_private_material` asserts that credential-shaped files
  stay unpublished **and** that legitimately named source
  (`test_a_model_call_reports_its_token_cost.py`, `key-vault-secrets.bicep`) stays
  published. Keep both assertions.
- The six-unit candidate secret/content scan reported **0** high-confidence secrets,
  **0** live endpoints, and **0** raw source-policy or live-corpus text.
- The provenance leakage scan reported **0** hits across 167 source-literal candidates
  and 20 question literals, with 0 rubric-ID, question-ID or provision-fixture hits in
  production guards.
- Malformed-response diagnostics in Consume Demo expose structural summaries only and
  must never copy raw policy/rule content into the support clipboard.
- Publication guards require real Git metadata to execute (`git check-ignore`), so they
  can only be validated in a true worktree.
- Transfer every class above **outside Git** on a separate secure channel.

---

## 13. Package layout and machine-readable ledgers

All paths below are **repository-relative**. `hosthandover.md` sits at the repository
root; every supporting artifact lives under `handover/`.

| Path | Contents |
|---|---|
| `hosthandover.md` | This document — the primary deep narrative handover |
| `handover/RESUME_FIRST.md` | Clone-and-verify first actions for the target host |
| `handover/SESSION_LEDGER.json` | Session hierarchy, roles, states, handoffs *(source-host provenance)* |
| `handover/GIT_AND_WORKTREE_LEDGER.json` | Remotes, refs, full commit ledger, adoption transitions, status classification, worktrees, reachability, publication status |
| `handover/PENDING_DECISIONS_AND_TASKS.json` | **Authoritative** portable task list, `T-01` onward |
| `handover/ARTIFACT_INVENTORY.json` | What is bundled, why, what was excluded and why |
| `handover/HANDOVER_HASHES.sha256` | Recursive SHA-256 over `hosthandover.md` and everything under `handover/`, excluding itself |
| `handover/artifacts/BUNDLED_ARTIFACTS.json` | Per-file manifest: relative path, bytes, SHA-256, role, source provenance |
| `handover/artifacts/` | Vendored continuity evidence — 186 files |

Vendored artifact sets:

| Directory | Files | Role |
|---|---:|---|
| `handover/artifacts/migration/` | 7 | the original migration handovers |
| `handover/artifacts/parent/` | 9 | oversight narrative, 5 checkpoints, feature-adoption START/RESULT |
| `handover/artifacts/six-unit/` | 40 | validated decomposition artifacts + adoption records and commit patches |
| `handover/artifacts/rule-foundation/` | 10 | ordinal-00 reconstruction |
| `handover/artifacts/consume-foundation/` | 17 | ordinals 03/04 reconstruction and approval evidence |
| `handover/artifacts/payload/` | 6 | payload track handover, blueprint, regression study, rubric |
| `handover/artifacts/provenance/` | 86 | complete criterion-provenance successor v1.0.0 |
| `handover/artifacts/azure/` | 2 | off-main Azure commit patch + overlap analysis |
| `handover/artifacts/publisher/` | 6 | in-flight capture, reconciliation messages, secret-scan baseline |
| `handover/artifacts/historical/` | 3 | frozen source-host ledgers *(NON-ACTIONABLE)* |

*Historical provenance: this package was authored on the source host under
`C:\Users\taomar\.copilot\session-state\8476596b-1943-4577-8a2c-10e0d7553606\files\`.
That path is a record of origin and is **not** required by any target-host step.*

> **Placement note for whoever writes these into the repository.** `.gitignore` contains
> `HANDOVER*`, `handover*` and `docs/handover/`. A `handover/` directory at the
> repository root **will be ignored by Git** unless the ignore rules are amended or the
> files are force-added. `hosthandover.md` itself does **not** match those patterns and
> is not ignored. This handover session made no repository change; the authorized writer
> must resolve it.

---

## 14. Known unknowns

| # | Unknown | Why | Resolve by |
|---|---|---|---|
| 1 | Final remote SHA of the archival publication | The publication commit cannot contain its own SHA; §15.4 directs you to treat the remote ref itself as the receipt | `git ls-remote base refs/heads/main` after cloning, then compare to `git rev-parse HEAD`; task `T-02` |
| 2 | ~~Whether `taomar/PolicyVerbAItim` exists / is reachable~~ | **RESOLVED by §15.4.** The `Repository not found` seen from this session was an identity mismatch: the ambient `GH_TOKEN` belongs to `taomar_microsoft`, which gets a private-repository 404. Authentication must use the keyring token for GitHub user `taomar`. | authenticate as `taomar` |
| 3 | Whether `8bc0657…` is the final publication tip | §15.2 records it as the publisher's clean HEAD *before* the handover files were added, so the published tip is expected to be a later commit adding this package | compare `ls-remote base refs/heads/main` against the recorded chain; task `T-02` |
| 4 | Current live Azure / database / Search state | Last verified 2026-09-04; no live calls made by this session | re-verify read-only, only when authorized; task `T-13` |
| 5 | Canonical `origin` for the archival clone | The source host's temporary repoint was never reverted | owner decision; task `T-09` |
| 6 | Adjudication of the vendored detect-scan findings | §15.3 records 110 candidates triaged with **zero high-confidence secrets**; individual candidate dispositions were not re-derived here | review `handover/artifacts/publisher/detect-secrets-scan.json` if a fresh audit is wanted |
| 7 | Disposition of residual in-flight source that is archival rather than product | Deliberately deferred; the archive preserves it either way | task `T-10` |

> Items previously listed here about copying old worktrees and old absolute paths have
> been removed: they are no longer unknowns, because the target host does not use them
> (§0).

---

## 15. Recovery and publication addendum

This section supersedes only the publication-status statements in §§1.2, 1.3, 3.3,
5, 11 Phase 2, and 14. It does not replace their historical evidence.

### 15.1 Handover worker recovery

The original handover worker terminated after producing this narrative,
`handover\RESUME_FIRST.md`, and `handover\SESSION_LEDGER.json`. The parent recovered
those files and completed the missing machine-readable ledgers without changing
product source. The package layout required by the owner is:

```text
hosthandover.md
handover\
  RESUME_FIRST.md
  SESSION_LEDGER.json
  GIT_AND_WORKTREE_LEDGER.json
  PENDING_DECISIONS_AND_TASKS.json
  ARTIFACT_INVENTORY.json
  HANDOVER_HASHES.sha256
```

### 15.2 Final archival publisher state before this package was added

The isolated publisher worktree was clean at:

| Field | Value |
|---|---|
| Branch | `taomar-microsoft-private-base-publisher` |
| HEAD | `8bc0657a7076e8bf85b0a5f1b5ea009911829040` |
| Tree | `64cad6a0c472ff49d4fe8895c5aacb5513d3190f` |
| Snapshot commit | `cf2d0f104c55f5a961d4634e692b9ebbe49e2aa7` |
| Feature-reconciliation merge | `b13f168db44f2dd0218b3deea0bba1bf186fb27e` |
| Ignored-skill-assets commit | `8bc0657a7076e8bf85b0a5f1b5ea009911829040` |

The archival branch includes:

- all history through local main `d3bb0f94d58d1810a1ff24cacf8118d82f9c554f`;
- all 76 pre-feature-adoption in-flight source paths: 42 tracked modifications and
  34 untracked source/test/migration/UI files, byte-verified against
  `feature-adoption\START_STATE.json`;
- both validated feature capabilities, with nine feature-only blobs verified
  byte-identical to `d3bb0f94`;
- 101 intentionally ignored `.github\skills\**` source, reference, font, license,
  and test assets;
- no synthetic feature deletion from the dirty shared checkout.

Four merge conflicts were reconciled additively:

1. `canonical_rebuild.py`: generic namespaced sidecars plus reading-order recovery;
2. `document_extraction.py`: both table-structure and reading-order provenance;
3. `search_client.py`: existing retry boundary plus ranking telemetry, while
   preserving the serving path's deliberate no-retry behavior;
4. `test_no_m2_code_is_shaped_around_a_corpus.py`: all applicable authored-module
   registrations.

### 15.3 Publication safety evidence

- Detect-secrets scan: 110 candidates triaged; **zero high-confidence secrets**.
- File-size gate: largest reachable blob 456,759 bytes; zero blobs over 50 MiB or
  100 MiB.
- Excluded from the archival branch: `.serena\**`, secret-bearing `.env` files,
  local account/signing material, `.private\**`, local `.azure\**`, runtime
  documents/backups, virtual environments, `node_modules`, build/cache/coverage
  output, logs, screenshots, and local agent/session records.
- Targeted combined feature/guard tests: **219 passed** in the publisher's final
  branch and **211 passed** in the parent's two-feature integration candidate.
- Full backend on the publisher branch: **5,658 passed, 23 skipped, 9 failed,
  12 errors**. The same 9 failures and 12 errors occur at the exact baseline:
  the known Azure-settings test-harness defect and absent gitignored corpus
  artifacts. No new failing/erroring node ID was introduced.
- The publisher worktree was clean before the handover files were added.

### 15.4 Final private publication

The authorized target is the private repository:

```text
https://github.com/taomar/PolicyVerbAItim
```

Only `base/main` is authorized. `origin` must not be pushed. Authentication must
use the keyring token for GitHub user `taomar`; the ambient `GH_TOKEN` belongs to
`taomar_microsoft` and returns a private-repository 404.

The final publication commit necessarily cannot contain its own SHA. On the new
host, treat the remote ref itself as the publication receipt:

```powershell
git ls-remote base refs/heads/main
git rev-parse HEAD
```

Those values must match after cloning. If `base/main` is absent, publication did
not complete; do not infer success from local publisher commits.
