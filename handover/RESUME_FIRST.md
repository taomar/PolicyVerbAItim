# RESUME FIRST — PolicyVerbAItim, new host

You need **nothing from the old machine**. Everything required to resume is either in
the private Git repository or in `handover/artifacts/` inside this repository.

Read this page, then `hosthandover.md` at the repository root.

---

## 0. The lock — still in force

**ALL FEATURE DEVELOPMENT IS STOPPED.** No edits, no staging, no commits, no push,
no deploy, no migration, no live API/DB/Search/Azure calls — until the human owner
lifts the lock explicitly.

Permitted now: cloning, reading, hashing, verifying.

---

## 1. Canonical restore path

```
1. Authenticate to GitHub as user  taomar
2. git clone https://github.com/taomar/PolicyVerbAItim
3. cd PolicyVerbAItim
4. Verify remote main + recursive handover hashes  (section 2)
5. Work from this clean archival clone
```

That is the whole restore. **Do not** attempt to copy an old local checkout, an old
worktree, or any agent session-state directory. None of them are required, and none of
them will exist on this host.

> **Identity trap — this already happened once.** The repository is private and owned by
> `taomar`. An ambient `GH_TOKEN` belonging to `taomar_microsoft` gets a
> **404 `Repository not found`**, which looks exactly like the repository not existing.
> Use the keyring token for GitHub user `taomar`.
>
> Only `base/main` is an authorized push target. `origin` must not be pushed.

---

## 2. Verify before trusting anything

### 2.1 Remote and branch

```bash
git rev-parse HEAD
git log --oneline -12
git remote -v
git status --porcelain=v1        # expect: clean
```

Expected: a clean tree on the archival `main` of `taomar/PolicyVerbAItim`.

**Record the SHA you actually cloned.** The publication commit cannot contain its own
SHA, so treat the **remote ref itself** as the receipt:

```bash
git ls-remote base refs/heads/main    # or the clone URL directly
git rev-parse HEAD
```

Those must match. If `base/main` is absent, publication did not complete — do **not**
infer success from local publisher commits. Recorded chain for comparison:
`cf2d0f10… → b13f168… → 8bc0657…`, with the published tip expected to be a later commit
that adds this handover package. See `hosthandover.md` §15 and task `T-02`.

### 2.2 Handover integrity — recursive, mandatory

From the repository root:

**PowerShell**
```powershell
$ok=0; $bad=0
Get-Content handover/HANDOVER_HASHES.sha256 |
  Where-Object { $_ -and -not $_.StartsWith('#') } | ForEach-Object {
    $p=$_ -split '\s+',3
    $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $p[2]).Hash.ToLower()
    if ($h -eq $p[0]) { $ok++ } else { $bad++; "MISMATCH $($p[2])" }
  }
"verified=$ok  mismatched=$bad"
```

**bash**
```bash
awk '!/^#/ && NF {print $1"  "$3}' handover/HANDOVER_HASHES.sha256 | sha256sum -c -
```

`mismatched` must be **0**. Every path in that file is relative and uses forward
slashes, so it verifies identically on Windows, macOS and Linux.

Then confirm the vendored evidence is complete:

```powershell
$b = Get-Content handover/artifacts/BUNDLED_ARTIFACTS.json -Raw | ConvertFrom-Json
$b.files | ForEach-Object { if (-not (Test-Path "handover/artifacts/$($_.path)")) { "MISSING $($_.path)" } }
"declared=$($b.file_count)  bytes=$($b.total_bytes)"
```

---

## 3. What is in the clone

| Location | Contents |
|---|---|
| repository source tree | the reconciled product source, including the previously uncommitted in-flight bytes |
| `hosthandover.md` | the full narrative handover |
| `handover/` | ledgers, task list, inventory, checksums |
| `handover/artifacts/` | vendored continuity evidence — patches, reconstructions, adoption records, the provenance package, publisher records |

`handover/artifacts/` is the only continuity source you need. It contains:

```
migration/            7 original migration handovers
parent/               parent handover, 5 checkpoints, feature-adoption START/RESULT
six-unit/             final-artifacts (25) + adoption records and 6 commit patches
rule-foundation/      ordinal-00 patches, manifests, validation
consume-foundation/   ordinal-03/04 patches, approval + non-mutation evidence
payload/              payload handover, blueprint, regression study, rubric
provenance/           complete 86-file criterion-provenance successor v1.0.0
azure/                off-main Azure commit patch + overlap analysis
publisher/            safe path list, pathspec, commit messages, secret-scan baseline
historical/           frozen source-host ledgers (NON-ACTIONABLE)
```

> **Absolute `C:\Users\taomar\...` paths appear only as historical provenance** — in
> `handover/artifacts/historical/`, in `source_path` fields, and in labelled historical
> sections of `hosthandover.md`. They describe the machine the work was done on. They
> are **never** an instruction and **never** a dependency.

---

## 4. The one thing that will destroy work

The source host's working tree was deliberately left dirty while `main` adopted two
feature commits, so its `git status` showed **synthetic** entries: 3 apparent deletions
and 6 apparent modifications that were neither.

**In the archival clone this is already reconciled** — the archive was merged with
merge base `3414811752cc2cb08bf26b87dd8d8fa2c22baf65`, which is what made the feature
files survive as one-sided additions instead of reading as deletions.

You therefore inherit the *result*, not the hazard. But if you ever re-derive, re-merge,
or re-split that history:

- merge base **must** be `3414811752cc2cb08bf26b87dd8d8fa2c22baf65`
- reconcile **by hunk**, never by wholesale replacement
- never delete a feature file to "resolve" an apparent deletion

Full explanation: `hosthandover.md` §2.4 and §8.5.

---

## 5. Baseline test numbers you must not misread

On a complete environment the backend unit suite is expected to report:

```
9 failed    23 skipped    12 errors
```

- **12 errors** — the gitignored runtime document store is absent. Expected by design.
  They disappear only if that store is restored out of band.
- **9 failures** — HTTP 503 from Azure OpenAI, caused by a **real test-harness defect**:
  the harness never patches `get_settings` on `src/policy_platform/api/routers/ai.py`,
  so those tests read the ambient environment. Pre-existing and unrelated to any work in
  this programme; deliberately left unfixed. Task `T-08`.

Failing and erroring node IDs were programmatically diffed and are **identical** at the
base and at both feature commits — zero regressions.

Take any new baseline in a **real worktree**. Never use `git archive`: it strips `.git`,
and two publication tests shell out to `git check-ignore`, producing a false
57-failure result.

---

## 6. First actions, in order

1. Authenticate as `taomar`; clone the private repository.
2. Verify remote HEAD and run the recursive checksum verification (§2). **0 mismatches.**
3. Verify `BUNDLED_ARTIFACTS.json` completeness.
4. Read `hosthandover.md` — start with "Portable target-host operating model".
5. Read `handover/PENDING_DECISIONS_AND_TASKS.json` and work `T-01` onward in order.
6. Restore secrets and runtime data **out of band only if you need to run the system**
   (see §7). Reading and reviewing needs neither.
7. Recreate the Python and Node environments.
8. Run targeted validation, then the full suite; compare against §5.
9. Do not push, deploy, migrate, or run the provenance harness without new explicit
   authorization.

---

## 7. Out-of-band restoration (only if you must run the system)

None of these are in Git, and none may ever be committed:

| Class | Examples |
|---|---|
| Environment secrets | `.env`, `.env.*`, `apps/web/.env`, `apps/consume-demo/.env.local`, `services/policy-decision-api/.env` |
| Local credential store | `.local-accounts.txt` |
| Token-signing key | `.local-signing-key*` |
| Certificates / private keys | `*.pem` |
| Tokens written to files | `*token*.txt`, `*token*.json`, `*.token` |
| Azure CLI local env | `.azure/*` |
| Runtime corpus | `data/documents/`, `data/backups/` |

Obtain them from the owner over a secure channel, or regenerate them. If you only need
to read, review, or reason about the codebase, skip this entirely.

---

## 8. Hard prohibitions

- Never deploy, push, or merge the preserved Azure local-auth commit
  `381586688f0337be15dcc1d42d2be7d4b0fe4936`. It is off-main; its content travels as
  `handover/artifacts/azure/AZURE_3815866.patch` only.
- Never run the provenance harness — `execution.enabled: false`.
- Never apply the pending Alembic revision without authorization.
- Never commit `llm_reasoning_view` or its test as product — the experiment is
  **withdrawn**; it exists in the archive as in-flight source only.
- Never commit anything from §7.
- Never treat an absolute `C:\Users\taomar\...` path as an instruction.
