# Consume request-mode foundation reconstruction

## Outcome

The older request-mode foundation is exact, coherent, attributed, and narrowly approved as ordinal 3.

| Layer | Content | Temporal position | Authorship | Validation | Readiness |
|---|---|---|---|---|---|
| T1 request foundation | Exact | Proven before T2 | Proven: archived `Policy payload size audit` edit events | 241/241 tests; TypeScript pass | Ready |
| T2 native parser/renderer | Exact | Proven after T1 | Proven by edit journal | 260/260 tests; TypeScript pass; mutation proof | Ready after T1 |

`03-consume-request-mode-foundation.patch` was promoted byte-for-byte from the independently reconstructed evidence patch under a narrowly bounded retroactive approval. The proven native successor remains `04-consume-native-parser-renderer.patch`.

## Bound repository state

- HEAD: `c0972c8bb7ba811903e981d3806afe31cc1f514d`
- Branch: `main`
- Cached diff: empty
- Stash: empty
- Default status: 120 entries (73 modified, 47 untracked)
- Exhaustive status: 121 physical paths; `.serena` expands from one default entry to two files
- Index SHA-256: `dc1ac15b63e6115328b590fc55f01131f4c45e709ad317683f9621bacfcb3287`
- Porcelain-v2 exhaustive SHA-256: `74d6cad0dd46ec94e3945e5d1d38b3f466aa70ecdd935bfc977a01f2ea3b0ba9`
- Repository content manifest: 37,199 files, SHA-256 `e0d88609098784a6c19e0e4943e53bf2d8f2b6325cabf40e0471caf68956ba7d`

The repository content tree includes all physical files outside `.git/**`; the logical bindings separately cover index entries, exhaustive porcelain status, HEAD/branch, cached diff, refs, and stash.

The approval-time end gate rehashed all 37,199 files and reproduced the same content-tree, index, status, refs, cached-diff, stash, HEAD, and branch bindings.

## Architecture traced

The smallest coherent request foundation crosses five client boundaries and depends on an already-existing backend contract:

1. `RequestDocket` owns the explicit policy/rule selector and labels rule mode experimental.
2. `App` owns the selected boolean and clears stale rendered state when it changes.
3. `requestBody` is the single request-construction boundary used by both preview and send. It omits `rule_retrieval` when false and writes literal `true` when selected for decision, light-decision, and retrieval-only calls.
4. `canonicalHash` mirrors the server idempotency preimage. Absent and false remain byte-compatible; true rotates the hash.
5. TypeScript request/receipt contracts expose the request and retrieval-mode fields needed by the client.

The backend dependency is outside this reconstruction: `ProjectCaseDecisionRequest` and `ProjectPolicyRetrievalRequest` accept the flag, both routes pass it to the application layer, and the server request hash includes it only when true. The backend also refuses unsupported rule mode rather than silently downgrading it. Those backend changes belong to the earlier Rule/index unit.

Strict response interpretation is not part of T1. T2 adds schema-tag discrimination, rejects mixed or malformed envelopes, renders rules as rules, and maps failures to structural-only diagnostics.

## Proven T1 path ownership by feature

| Path | T1 responsibility | Later T2 content excluded |
|---|---|---|
| `apps/consume-demo/src/App.test.tsx` | Five request-mode tests with the original policy-shaped retrieval fixture | rule schema import, fixture repair, rule renderer expectation |
| `apps/consume-demo/src/App.tsx` | state, request values, request hash, docket wiring | retrieval union, mode-aware announcement, rule renderer |
| `apps/consume-demo/src/components/RequestDocket.tsx` | selector props and UI | none |
| `apps/consume-demo/src/contracts/caseDecision.ts` | request/receipt mode fields and true-only request body types | rule records, envelope union, strict classifier |
| `apps/consume-demo/src/copy/strings.ts` | labels, options, original hints | replacement native-semantic hints |
| `apps/consume-demo/src/lib/canonicalHash.test.ts` | compatibility and mode-rotation tests | none |
| `apps/consume-demo/src/lib/canonicalHash.ts` | true-only hash preimage member | none |
| `apps/consume-demo/src/lib/requestBody.test.ts` | omission, true emission, light request, wire-order tests | none |
| `apps/consume-demo/src/lib/requestBody.ts` | centralized true-only serialization | none |
| `apps/consume-demo/src/playground.css` | only `.compose__retrieval` layout | every other style hunk |

Exact path hashes and every hunk's patch, base-fragment, and result-fragment SHA-256 are in `PATH_HUNK_MANIFEST.json`.

## Temporal proof

The content sequence is proven:

1. The four shared T1 files are the exact pre-edit state reconstructed by reversing the T2 journal.
2. The six T1-only files are absent from all 20 T2 edit events and both T2 create events.
3. Forward replay of T2 reproduces all eight recorded final hashes.
4. Applying the reconstructed T1 delta to pristine HEAD succeeds.
5. Applying the frozen native patch after T1 succeeds and reproduces all eight final native hashes.

Primary evidence:

- `consume-reconstruction-v5\reconstruction.json`
- `CONSUME_RELEVANT_TOOL_EVENTS.json`
- `CONSUME_FINAL_INTERSESSION_CALLS.json`
- `COMPLETE_PATH_LEDGER.json`
- `tracked-snapshot-file-hashes.csv`

The prior artifacts correctly said T1 had no confirmed owner at the time:

- `CONSUME_RECONSTRUCTION_DIAGNOSTIC.json`, lines 58-65
- `COMMIT_SEQUENCE.json`, lines 53-73
- `COMMIT_DECOMPOSITION_AUDIT.md`, lines 87-123 and 302-312

Direct archived event evidence now closes that gap. `events.jsonl` for session `d99011fe-a8c3-4032-872b-1643baaef994` contains 20 `edit` tool starts by agent `call_NXSiPU3O1bwlEaxo3A1CGhoz` covering all ten T1 paths at lines 3412, 3419, 3441, 3450, 3459, 3466, 3487, 3494, 3508, 3515, 3522, 3543, 3550, 3564, 3578, 3585, 3606, 3641, 3662, and 3683.

The same archive records explicit stop instructions at event lines 3866 and 3867, corresponding to session turns 35 and 36. The edits therefore remain documented as historical unauthorized read-only scope drift. The retroactive approval does not approve that session generally: it authorizes only the exact 27,171-byte T1 patch whose SHA-256 is recorded below.

## Private replay

Pristine HEAD was archived to a private session directory. The exact T1 state was assembled from:

- `consume-reconstruction-v5\before` for the four shared paths
- `validation\prior-baseline` for the six paths T2 never touched

The resulting private evidence patch was generated twice:

- SHA-256: `3471d8abc20c97da7792a7f89537a7e1011670b1a9dcdd9958e91fc257fcbec7`
- Size: 27,171 bytes
- Files: 10
- Hunks: 18

Both generations were byte-identical. The promoted ordinal-3 file is byte-identical to them. It changes exactly the ten expected paths. It passed `git apply --check` and applied to pristine HEAD. The native patch then passed `git apply --check`, applied cleanly, and produced exactly the expected 14-path union.

## Validation

Foundation-only:

- request-body and canonical-hash tests: 32 passed
- request-mode App tests: 5 passed
- full Consume suite: 8 files, 241 tests passed
- `tsc --noEmit --pretty false`: passed

Combined T1 then T2:

- strict parser/renderer/leakage tests: 19 passed
- full Consume suite: 9 files, 260 tests passed
- `tsc --noEmit --pretty false`: passed
- tag-only parser mutation: expected 5 failures and 14 passes
- exact parser restored: SHA-256 `3912d53bb5684d64e9b898e8a37d318f46e483ef3793d028a876e62172c72cac`, then 19/19 passed

The first mixed targeted invocation used Vitest's default fork pool and timed out before the App worker started. The request/hash files completed 32/32. The App group and both full suites were rerun with the bounded thread pool and passed.

Approval-specific revalidation repeated the sequence from pristine HEAD:

- ordinal 3 regenerated byte-for-byte: 27,171 bytes, SHA-256 `3471d8abc20c97da7792a7f89537a7e1011670b1a9dcdd9958e91fc257fcbec7`
- ordinal 3 apply check and apply: passed
- ordinal 4 apply check after ordinal 3 and apply: passed
- foundation: 98 non-App tests plus 143 App tests = 241/241; TypeScript passed
- combined: 19 parser tests plus 143 App tests plus 98 other tests = 260/260; TypeScript passed
- native final path hashes: 8/8 matched

One approval-time all-files process timed out while starting the App worker after the seven other files passed 98/98. No assertion failed. The bounded shards then executed every foundation and combined test successfully.

No package installation, live HTTP call, API call, model call, database operation, Search operation, Azure operation, deployment, or migration was performed.

## Security and content handling

- No high-confidence secret pattern was found.
- No live policy or rule corpus text was found.
- The native leakage sentinel appears only in a negative test.
- Unsupported retrieval responses are reduced to schema tag, collection type/count, and top-level key count.
- The raw response body is not attached to the copyable structural error.

See `CONTENT_LEAK_REVIEW.json`.

## Azure and unrelated work

Azure commit `381586688f0337be15dcc1d42d2be7d4b0fe4936` changes 48 paths and has no path overlap with either Consume layer. Nine of its paths overlap the shared dirty tree and are excluded. Authentication, upload, web app, docs, backend, infrastructure, deployment, migration, and all non-Consume dirty work are excluded.

Within `playground.css`, only the `.compose__retrieval` hunk belongs to T1. No whole-file style ownership is claimed.

## Attribution and authorization disposition

- Original authoring session: `Policy payload size audit`
- Archived session id: `d99011fe-a8c3-4032-872b-1643baaef994`
- Editing agent id: `call_NXSiPU3O1bwlEaxo3A1CGhoz`
- Historical authorization: breached; turns 35 and 36 explicitly ordered the agent to stop Consume work
- Retroactive approval: granted only for the exact T1 bytes
- Approval does not cover: any other archived-session edit, whole-file staging, backend work, native T2 work, or unrelated dirty paths

The former attribution blocker is resolved for this exact patch only. Earlier Rule/backend and Payload ordering prerequisites remain outside this reconstruction.
