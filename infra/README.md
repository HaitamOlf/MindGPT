# infra/ — Bicep IaC (Phase 2 — done)

Subscription-scoped entry point (`main.bicep`) that creates the resource group and composes
per-service modules, split into the two tiers from [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md):

- **BUILD tier** (`modules/build/`, deployed by default): user-assigned managed identities
  (one per workload), Log Analytics + App Insights, Key Vault (RBAC auth), Blob Storage
  (private, no shared key), Cosmos DB for NoSQL (`disableLocalAuth`, partition=`userId`),
  AI Search (free, `disableLocalAuth`), Content Safety (F0), AI Language (F0), Container Apps
  (the API, placeholder image until Phase 3), Functions (timer-triggered cleanup,
  identity-based storage — no keys anywhere). Static Web Apps and Azure OpenAI are each
  **optional** (`deployStaticWebApp` / `deployAzureOpenAI`, both default `false`) — see below
  and `docs/ARCHITECTURE.md` §8.
- **DOCUMENT tier** (`modules/document/`, `deployDocumentTier` default `false`): Front Door +
  WAF, API Management, VNet + Private Endpoints, Defender for Cloud plans. Deployment status
  (see [`../docs/SECURITY_VALIDATION.md`](../docs/SECURITY_VALIDATION.md)): **APIM** (Consumption,
  ~€0) is **deployed** as a live JWT-validating edge gateway (`validate-jwt` against the CIAM
  token + pinned CORS, keyless — no subscription key); **Defender** plans were
  deployed via `defender.bicep`, confirmed `Standard`, then reverted to `Free` to protect
  credit; **Front Door + WAF** (verified *forbidden* on Student accounts) and **VNet + Private
  Endpoints** remain design-only (for Private Endpoints — the Container Apps env has no VNet integration and the
  Free-SKU AI Search rejects private endpoints). Toggle the rest on only when budget allows.

## Static Web Apps region conflict

`Microsoft.Web/staticSites` only deploys into a small fixed region list:
`centralus, eastus2, westus2, westeurope, eastasia`. On a subscription with an Azure
Policy **"Allowed resource deployment regions"** assignment that doesn't include at least
one of those (common on institution-managed student tenants — the UIR Azure for Students
subscription this was built against allows only
`polandcentral, francecentral, swedencentral, germanywestcentral, norwayeast`, none of
which intersect), Static Web Apps **cannot be created at all, in any region** — this isn't
fixable by picking a different `location`.

`deployStaticWebApp` defaults to `false` for exactly this reason. The API's CORS origin
falls back to `frontendOrigin` (default `http://localhost:5173`, the Vite dev server) when
the Static Web App isn't deployed. If your subscription's allowed-regions policy does
include a supported SWA region, set `deployStaticWebApp=true` and point
`staticWebAppLocation` at it (`westeurope` by default). Otherwise, frontend hosting for a
policy-restricted subscription needs a different approach (e.g. Blob Storage static website
hosting, which has no such region restriction) — revisit this when Phase 5 does the frontend
auth migration.

## Deploying

```bash
az login
az deployment sub what-if \
  --location francecentral \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam

az deployment sub create \
  --location francecentral \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

Override any param inline, e.g. `--parameters deployAzureOpenAI=true` once Azure OpenAI
access is confirmed on the subscription.

## CI/CD prerequisites (`.github/workflows/`)

`bicep-whatif.yml` and `deploy-infra.yml` authenticate to Azure via **OIDC federated
credentials** — no client secret is ever stored in GitHub (ARCHITECTURE.md §7.1). One-time
setup:

1. Create an Entra app registration (or use an existing one) with a federated credential
   trusting this repo: `repo:<owner>/<repo>:ref:refs/heads/main` (and `:pull_request` for the
   what-if workflow), issuer `https://token.actions.githubusercontent.com`.
2. Grant its service principal **Contributor** (or a narrower custom role) on the target
   subscription — the deployment itself creates the resource group and does its own
   least-privilege RBAC assignments beneath it.
3. Set `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as repo (or
   environment-scoped) secrets/variables.
4. Create a `build` GitHub Environment and add required reviewers, so `deploy-infra.yml`
   never runs unattended (ARCHITECTURE.md §7.1 "environment protection rules").

## Pinning actions

Every workflow `uses:` is pinned to a full commit SHA (with the version as a trailing
comment), per the CI/CD hardening control in `docs/ARCHITECTURE.md` §7.1 — a moved or
compromised tag then can't silently change what runs. In particular
`aquasecurity/trivy-action`, previously referenced by the moving `@master` branch, is
pinned to a specific commit. Dependabot's `github-actions` ecosystem
(`.github/dependabot.yml`) keeps the pinned SHAs current via PRs.

## Conventions

- Modules under `modules/build/` and `modules/document/`, composed in `main.bicep`.
- Security defaults encoded in IaC: key-based auth disabled wherever the platform allows it
  (`disableLocalAuth` / `allowSharedKeyAccess: false`), one user-assigned identity per
  workload with narrowly-scoped RBAC role assignments colocated in the module that owns the
  resource, soft-delete/versioning on, public network access called out explicitly as a
  BUILD-vs-DOCUMENT gap rather than hidden.
- Scanned in CI (`security-scan.yml`: Checkov for Bicep, gitleaks, CodeQL, Trivy once a
  container image exists) and `what-if` on every PR touching `infra/**`.
