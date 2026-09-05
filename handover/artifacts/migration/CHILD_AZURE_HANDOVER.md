# Child Mapping: Azure Deploy

## Model

Use GPT-5.6 Sol or Claude Opus 5, maximum reasoning, long context.

## Maps from

- Project session `bb2a8cbc-e4f0-44ac-ba5e-cc8e80b1c15f`

## Read first

1. `C:\Users\taomar\.copilot\session-state\bb2a8cbc-e4f0-44ac-ba5e-cc8e80b1c15f\files\AZURE_DEPLOY_SESSION_HANDOVER.md`
2. `AZURE_DEPLOY_RUN_LOG.md`
3. `AZURE_DEPLOY_VERIFICATION.md`
4. Parent successor handover.

## Verified deployed state

- Subscription `5a03d84f-151a-4ad3-9568-063e4e502bf0`
- Sweden Central
- Resource group `rg-pvai-swc`
- Tag `SecurityControl=Ignore`
- `LOCAL=true`, direct mode, no APIM
- API:
  `https://ca-pvaiswc-api-k6pmkx.thankfulrock-18993f62.swedencentral.azurecontainerapps.io`
- Web:
  `https://ca-pvaiswc-web-k6pmkx.thankfulrock-18993f62.swedencentral.azurecontainerapps.io`
- API health/docs and web root directly rechecked HTTP 200.
- `azd up` succeeded twice.

## Changes to preserve

Nine uncommitted deployment-kit files on Azure checkout/branch at `90fe48f`.
The detailed handover names every file and exact diff.

Fixed:

1. azd Docker relative paths.
2. root Docker context bloat.
3. Linux npm lock entries.
4. unmatched azd service behavior.
5. Container App job image override.
6. missing async managed-identity transport dependency.
7. `LOCAL` derives from no APIM.
8. resource-group tag survives repeated provision.

## Risks

- Files are uncommitted and load-bearing.
- Resources remain live and billing.
- Entra sign-in is disabled.
- Integration router was absent from deployed branch/OpenAPI.
- Shared application and Azure branch must be merged carefully.
- Preserve async Search header invariant: one definition, eight awaited callers.

## Assignment

1. Do not redeploy or tear down immediately.
2. Verify the separate deployment checkout path and its nine-file diff.
3. Ask parent/user for commit, merge and keep/teardown decisions.
4. After application/integration merge, rerun prepare/validate/preview/azd up and
   live endpoint/RBAC tests.
5. Use `azd down` only when explicitly authorized for the exact environment/RG;
   prove no stray resources afterward.
