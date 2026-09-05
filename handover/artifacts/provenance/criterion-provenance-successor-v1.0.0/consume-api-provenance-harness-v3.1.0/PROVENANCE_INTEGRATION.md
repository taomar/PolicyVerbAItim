# Provenance Successor Integration

## Reproduction

From the package root, create a new output directory:

```powershell
python -B .\build_criterion_provenance_successor.py `
  --inputs <private-resume-inputs-path> `
  --output-package <new-empty-output-package-path>
```

The builder verifies the canonical v3.0.0 payload, the repaired 113-ID
partition, every evidence pointer/body/rule/span hash, source non-mutation, and
the repository baseline. It builds twice, runs validation twice with outbound
network calls blocked, and accepts only byte-identical packages.

## Adoption

Use this bundle only for offline validation, planning, provenance preflight,
and derived scoring. `manifest.pending.json` remains execution-disabled. The
13 unresolved criteria require a separate hash-bound human-confirmation
artifact before any future scoring upgrade.

## Rollback

No product or data rollback is needed. Stop using `consume-api-provenance-harness/3.1.0` and
return to the exact canonical v3.0.0 bundle at payload SHA-256
`fcc3cdfd8a823aa2349c5c7a033e1ea38b39b40e42831ab02a3d249e9516448c`. Do not reverse changes into canonical, historical,
source, repository, or live artifacts.
