# Consume API Rubric Provenance Migration

This is a new rubric version. It does not reinterpret or modify any frozen run,
raw evidence, or finalized adjudication artifact.

The migration adds criterion-level provenance, corpus-support state, source
provision/rule identifiers, and hash-pinned evidence pointers. Only active
criteria derived from normative body/rule evidence with validated non-zero
support may produce product failures.

AIS-02's pre-leave-certificate criteria and AIS-06's written-approval criteria
are withdrawn from scoring but preserved with `validated_unsupported` metadata.
AIS-03 is rewritten as a known source-to-served-rule ordinality limitation.
AIS-02 entitlement is answered, but present approval is
`not_settled_by_rules` under the general entitlement-versus-execution boundary;
the observed immediate `allowed` result is a source-provenanced product failure.

Heading-derived, question-inferred, unsupported, zero-support, missing-source,
and unknown-provenance criteria are never converted into product failures.
Semantic support that is not mechanically provable requires an explicit
human-confirmation record tied to hash-verified evidence.

Arms B, D, and F remain preserved as observed baseline evidence but are excluded
from actionable target-rule conclusions. Historical old-rubric replay remains
visible only as a non-equivalent contextual result.
