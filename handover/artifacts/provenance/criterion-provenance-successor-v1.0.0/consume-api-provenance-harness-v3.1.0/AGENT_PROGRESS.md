# Agent Progress

## Active Milestone

Deterministic `consume-api-provenance-harness/3.1.0` successor assembled and validated.

## Architectural Context

### System Boundary

Offline rubric provenance, fail-closed scoring, and controlled local adoption.

### Important Invariants

- Exactly one batch owns each of the canonical 113 finding IDs.
- Only active, source-bound, mechanically proven or independently
  human-confirmed criteria may be scorable.
- Structural and harness checks never become product-law failures.
- AI-authored artifacts never count as human confirmation.
- Execution remains disabled.

## Architectural Signals

- The predecessor ownership overlap/omission was corrected by a separate
  hash-bound artifact.
- Batch2's original source attestation remains the normative evidence source.
- The correction attestation remains audit-only.

## Root-Cause Analysis

- Prior symptom: 113 entries represented only 112 unique owners.
- Root cause: inconsistent exact ownership at positions 39 and 77.
- Correction: repaired Batch2 owns positions 39-76; Batch3 owns 77-113.

## Impact Analysis

- Changed criteria: 18
- Newly scorable: 5
- Result: 20 scorable, 95 unscorable, 13 unresolved
- Schema impact: none
- Live/data impact: none
- Rollback: select the immutable v3.0.0 predecessor

## Architecture Decisions

### Decision: Minor additive version

- Context: provenance and evidence expanded without a schema break
- Decision: harness/rubric 3.1.0 and manifest 2.1.0
- Rationale: additive compatible behavior under unchanged major schemas
- Validation: native load, self-test, unit/mutation suite, hash inventory, and
  two-pass byte-identical regeneration
