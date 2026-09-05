# Consume API Rubric Provenance Migration v3

This controlled-adoption successor is rubric version `3.0.0`, manifest version
`2.0.0`, and harness version `consume-api-provenance-harness/3.0.0`. It is built
from the hash-locked authoritative baseline and the exact 16-file v2 overlay;
it does not reinterpret or mutate any frozen run, live data, or adjudication.

Rubric v3 retains criterion-level evidence pointers and fail-closed scoring.
Only active `rule_body` criteria with validated, non-zero, hash-bound normative
support may produce `product_fail`. Unsupported, heading-derived,
question-inferred, withdrawn, and zero-support criteria are unscorable and emit
`rubric_error` while preserving the observation.

The corrected historical population remains 27 `product_fail`, 11
`rubric_error`, and 0 unresolved. Arms B, D, and F remain observed baselines and
are excluded from actionable target-rule conclusions. Old-rubric replay is
explicitly non-equivalent.

The production guard remains schema-driven and corpus-neutral. Benchmark names,
question IDs, provision fixtures, and the AIS-specific semantic resolution exist
only in immutable migration evidence and tests, never in guard logic.
