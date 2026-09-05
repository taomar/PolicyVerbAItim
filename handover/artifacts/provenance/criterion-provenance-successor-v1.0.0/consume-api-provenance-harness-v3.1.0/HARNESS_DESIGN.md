# Six-Arm Consume API Harness Design

Status: design frozen; execution disabled.

## Goals

The harness must:

1. execute 20 exact questions, split 10 AIS and 10 HW
2. execute each question three times across arms A-F
3. make each logical call independently resumable
4. preserve exact byte evidence and normalized contract fields
5. prevent mode downgrade and accidental execution
6. survive process failure, service timeouts, and workstation suspension
7. produce source-grounded per-call evaluation and per-arm repeat consistency

## Verified Arm Contract

| Arm | Surface | Path | `rule_retrieval` | Persists | Token usage | Latency |
| --- | --- | --- | --- | --- | --- | --- |
| A | Decision Light | `POST /api/policy-decisions/{key}/case/light` | `false` | yes | `trace.token_usage` | top-level `latency_ms` plus wall |
| B | Decision Light | `POST /api/policy-decisions/{key}/case/light` | `true` | yes | `trace.token_usage` | top-level `latency_ms` plus wall |
| C | full Decision | `POST /api/policy-decisions/{key}/case` | `false` | yes | `trace.token_usage` | wall plus trace stage timings |
| D | full Decision | `POST /api/policy-decisions/{key}/case` | `true` | yes | `trace.token_usage` | wall plus trace stage timings |
| E | JSON-only policy retrieval | `POST /api/policy-decisions/{key}/policies` | `false` | no | top-level `token_usage` | top-level `latency_ms` plus wall |
| F | JSON-only policy retrieval | `POST /api/policy-decisions/{key}/policies` | `true` | no | top-level `token_usage` | top-level `latency_ms` plus wall |

All six arms must send `provision_id: null`. A-D use one distinct idempotency key
per logical call; retries of that logical call reuse it. E-F omit idempotency.

The response `SizeRef` is a character count and is never reported as bytes.

HTTP 503 `rule-not-ready` is a terminal measured outcome. The harness records it
and does not retry as policy mode, remove the rule flag, or otherwise downgrade.

Current A/B responses do not yet echo the requested mode. B cannot execute until
the stabilized contract supplies an echo that the adapter can validate.

## Frozen Inputs and Authorization

The run manifest snapshots:

- endpoint-contract version and SHA-256
- ordered question set and SHA-256
- rubric and SHA-256
- source-evidence snapshot and SHA-256
- arm configuration
- retry and watchdog policy
- schedule seed
- model/reasoning request settings

Live execution requires a separate `authorization.json` containing:

- parent session ID
- run ID
- manifest SHA-256
- contract SHA-256
- question-set SHA-256
- rubric SHA-256
- source-snapshot SHA-256
- `rule_retrieval_stable: true`
- `authorized: true`

The controller validates all hashes before reading the base URL or credential
environment variables. A command-line confirmation is also required. The
authorization file contains no credential.

## Job Plan and Ordering

The logical job key is:

`{run_id}/{arm}/{question_id}/r{1..3}`

The plan contains exactly 360 unique jobs. It uses concurrency one and a
deterministic six-arm cyclic Latin rotation. For each question/repetition block,
the first arm advances by one position. This distributes order positions across
arms while keeping all modes interleaved in time.

No unrecorded warm-up decision is allowed. If a smoke call is needed, it must be
explicitly authorized, tagged `purpose: smoke`, stored outside the 360-job
matrix, and excluded from report statistics.

## Resumability and Persistence

Each job has these artifacts:

```text
runs/{run_id}/
  manifest.snapshot.json
  authorization.snapshot.json
  plan.json
  events.jsonl
  requests/{job_id}.body
  responses/{job_id}.wire
  responses/{job_id}.decoded
  records/{job_id}.json
  attempts/{job_id}/{attempt}.json
  derived/evaluations/{job_id}.json
  derived/consistency/{arm}/{question_id}.json
  reports/
```

Writes use a same-directory temporary file, `flush`, `fsync`, and atomic
`os.replace`. A job is complete only when its record validates and every
referenced artifact hash matches. On resume:

1. validate the frozen manifest and authorization
2. scan completed records
3. quarantine no file automatically; report malformed/incomplete files
4. skip valid completed jobs
5. resume the first incomplete job in plan order

No monolithic result array is rewritten during collection.

## Request and Response Byte Accounting

For every call, record separately:

- `question_utf8_bytes`: UTF-8 length of the exact question
- `request_body_bytes`: exact serialized entity body sent
- `request_body_sha256`
- request `Content-Length` if set
- `wire_body_bytes`: exact bytes read from the HTTP response stream before
  content decoding
- `decoded_body_bytes`: bytes after HTTP content decoding and before JSON parse
- `logical_json_bytes`: compact UTF-8 JSON serialization for a
  representation-level comparison
- response `Content-Length` header, when present
- wire and decoded SHA-256 values
- `Content-Encoding`

The report never substitutes file size, character count, `SizeRef`, or
`Content-Length` for a measured body byte count.

## Timing and Watchdogs

Every attempt runs in a child process so the controller can terminate a hung
HTTP worker without losing the run.

Initial defaults, to be frozen with the stabilized contract:

- connect timeout: 10 seconds
- write timeout: 30 seconds
- decision read timeout: 180 seconds
- retrieval read timeout: 90 seconds
- decision hard attempt watchdog: 240 seconds
- retrieval hard attempt watchdog: 120 seconds
- maximum attempts: 3
- maximum active run time: 6 hours
- maximum wall time: 8 hours
- controller heartbeat: 1 second
- suspension flag threshold: heartbeat gap greater than 10 seconds

Only explicitly retryable transport failures, HTTP 429, and contract-approved
5xx statuses retry. HTTP 503 `rule-not-ready` is terminal. Retry-After is
honored with a capped delay. Semantic, schema, integrity, and mode-echo failures
are terminal contract failures.

If workstation suspension is detected during a call, preserve the response and
correctness evidence but set `latency_valid_for_comparison: false`. Never delete
or silently replace the call.

## Normalization

The adapter maps surface-specific fields into one record:

- exact answer/information/verdict fields
- outcome statuses
- retrieval mode and mode echo
- retained policies and rules
- citations and quoted source evidence
- token calls, prompt, completion, reasoning, and total tokens
- stage timing map
- server latency where the contract exposes it

For E/F, answer/information/verdict fields are explicitly marked
`not_exposed_by_contract`; they are not emitted as empty answers.

## Correctness and Integrity

Raw evidence is immutable. Evaluation is a derived artifact keyed by the raw
record SHA-256.

The finalized rubric must define per question:

- authoritative source references and source snapshot hashes
- required answer facts
- allowed status/verdict variants
- forbidden or unsupported claims
- expected relevant policy/rule identifiers when stable
- citation requirements
- handling for irrelevant or underdetermined questions

Per-call evaluation records:

- information correctness
- verdict correctness
- required-fact coverage
- unsupported claims
- source entailment
- citation completeness and integrity
- overall pass/fail/needs-review
- evidence and adjudication notes

Deterministic integrity checks include:

- response parses as the expected schema
- requested and echoed retrieval modes agree
- no rule-mode downgrade occurred
- response hash/receipt identity validates where exposed
- cited policy/rule identifiers belong to returned/retained evidence
- quoted citations contain source text and valid source identifiers
- token arithmetic is internally consistent
- byte counts and hashes match stored artifacts
- C/D trace timings use duration units

## Three-Repeat Consistency

For every arm/question group, derive:

- completion count and status distribution
- exact outcome/status agreement
- normalized verdict agreement
- required-fact coverage-vector agreement
- correctness pass rate
- citation policy/rule set intersection, union, and Jaccard score
- answer variation notes
- min, median, max, and dispersion for latency, tokens, input bytes, and output
  bytes
- number of suspension-invalid or retried observations

Consistency does not mean identical prose. It means stable contract outcomes,
source-grounded conclusions, and evidence coverage.

## Abort Conditions

Abort the run without downgrading when:

- a frozen input hash changes
- an endpoint returns an unexpected schema
- mode echo is absent or mismatched where required
- credentials appear in an artifact candidate
- policy/source version changes during the run
- the active or wall watchdog expires
- repeated rate limiting exceeds the frozen retry budget
- Rule Retrieval reports not ready

Completed records remain valid evidence unless the source/version drift rule
invalidates the whole comparison epoch.

## Planned Offline Validation Before Execution

1. Validate manifest, question, rubric, and raw-result schemas.
2. Prove there are exactly 360 unique jobs and 60 jobs per arm.
3. Prove 10 AIS and 10 HW questions, each with repetitions 1-3.
4. Prove balanced arm order positions.
5. Replay adapters against the four full receipt fixtures and supporting
   Decision Light/policy-retrieval fixtures.
6. Inject timeout, malformed JSON, missing token usage, mode mismatch,
   rule-not-ready 503, partial file, and workstation-suspension simulations.
7. Prove resume skips only hash-valid complete jobs.
8. Scan generated fixtures for secret leakage.

Only then may the parent authorize live execution.
