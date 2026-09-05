# Child Mapping: Integration and Index Progress

## Model

Use Claude Opus 5, maximum reasoning, long context.

## Maps from

- Project session `bb565e7e-96a3-44c4-94dd-85d5f9d2f0dc`
- Index-progress task agent implementation

## Read first

1. `C:\Users\taomar\.copilot\session-state\bb565e7e-96a3-44c4-94dd-85d5f9d2f0dc\files\HANDOVER.md`
2. `VERIFICATION_FINDINGS.md`
3. `migration_probe2.py`
4. Parent successor handover.

## Completed implementation

- One durable `policy_index_builds` table/model for history, live progress and
  global slot.
- Cross-process unique nullable `active_slot`, lease heartbeat and reclaim.
- Shared orchestrator for publish and manual rebuild.
- Admin all-project index console.
- Publisher project progress/history/retry.
- Server-authority resume, accessible progress UI, no fabricated percentages.
- Correct route bands and documented role-only boundary.

## Verification already performed

- Backend 5,334 passed / 18 skipped.
- Frontend 151 files / 1,896 tests passed.
- TypeScript clean.
- Scratch PostgreSQL migration chain and lock refusal/control passed.
- One model, one migration, 36/36 model-migration columns.

## Current blockers/limitations

- Live local DB remains at `f4b8c2e97d31`; head is `a1c5f0b3e284`.
- Do not apply migration without explicit parent/user authorization.
- Authorization is role-only, not project ACL.
- Concurrent builds are refused, not queued.
- Deferred publish builds have no draining worker.
- Check the omitted-operation-ID generation path directly.

## Assignment

1. Verify no later Rule Retrieval changes broke combined imports/tests.
2. Inspect exact diff; do not rewrite sound task-agent code.
3. Re-run targeted backend/frontend/typecheck serially.
4. With authorization, apply migration and live-test:
   progress, history, one-build conflict, lease release, publish-deferred and
   retry.
5. Update exact API/path/tag/documented SQL counts after any edits.

## Coordination

Do not edit `case_decision.py`, `policy_case_decision.py`, `App.tsx`, `api.ts`, or
shared route schemas concurrently with Rule Retrieval. Parent must serialize
ownership.
