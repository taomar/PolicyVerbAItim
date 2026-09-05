# Successor Session Structure

## Top-level creation

The retiring oversight session cannot create an unparented session with
`create_session`, because that tool always keeps a parent-child relationship.
The top-level session is therefore created through an on-demand project workflow
bound to the app's local host:

- Project: Policy Extractor
- Host: `local`
- Local root: `C:\Users\taomar\Downloads\policy extractor`
- Model: GPT-5.6 Sol
- Reasoning: max
- Context: long
- Prompt: contents of `TOP_LEVEL_PARENT_KICKOFF.md`

No clone, fetch, push, or cloud execution is involved.

## Child map

Create four children from the new top-level parent:

| New child | Maps from | Model | Reasoning/context |
|---|---|---|---|
| Payload and Full-Cycle Verification | Payload worker + rendering/visual agents | Claude Opus 5 | max / long |
| Integration and Index Progress | Integration worker + index-progress agent | Claude Opus 5 | max / long |
| Azure Deploy | Azure Deploy worker | GPT-5.6 Sol | max / long |
| Rule Retrieval | Rule investigator + cardinality/disclosure agents | Claude Opus 5 | max / long |

Each child kickoff must include its corresponding `CHILD_*.md` verbatim or direct
it to read that file before acting.

## Required create-session mechanics

For every child:

1. Confirm no equivalent successor child already exists.
2. Call `create_session` with:
   - project ID `f8d6ba17-9121-4470-8a09-7dc2ecbe9cef`
   - `workspace_type: branch`
   - `execution_location: local`
   - `coordinate_with_creator: true`
   - `notify_on_idle: once`
   - selected SOL/Opus model
   - `reasoning_effort: max`
   - `context_tier: long_context`
3. Do not clone, fetch, push, or switch the shared checkout.

The configured project record still carries historical GitHub metadata. If the
app rejects a local child because that metadata disagrees with the local
checkout's remote, record the rejection and ask the user before changing the
remote. Do not silently convert a local-session request into cloud work.

Use `/orchestrate` from the new top-level parent to perform this hierarchy setup.

## Edit serialization

All branch sessions share one checkout. Spawned does not mean safe to edit in
parallel.

Phase A:

- Integration: verification/read-only first.
- Rule Retrieval: review partial disclosure diff read-only.
- Payload: direct audit/read-only.
- Azure: operates only in separate deployment checkout.

Phase B:

- Integration owns shared API/frontend contracts until quiet.
- Rule Retrieval may then edit decision/receipt contracts.
- Payload runs final combined tests only after both are quiet.

Never let Integration and Rule Retrieval edit `api.ts`, schemas, App routing, or
case-decision contracts concurrently.

## First parent checklist

1. Verify shared HEAD/status/origin.
2. Verify local Alembic current/head.
3. Verify both DB index rows and live Search manifests.
4. Verify source artifacts.
5. Verify only intended ports/processes.
6. Verify live Azure endpoints and separate checkout.
7. Spawn four mapped children.
8. Record each successor ID beside the old ID.
9. Require every child to distinguish direct evidence from inherited claims.
