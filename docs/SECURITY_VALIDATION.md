# MindGPT: Security Validation Report

This report documents the testing and verification of the security controls described in [`ARCHITECTURE.md`](./ARCHITECTURE.md) and [`THREAT_MODEL.md`](./THREAT_MODEL.md). Verification covers deployed infrastructure, automated testing suites, runtime protection mechanisms, and architectural design evaluations.

**Author:** Haitam Oualif  
**Status Legend:**
- **Validated & Deployed:** Provisioned, running in Azure, and tested live.
- **Validated & Scaled to Free/Idle:** Deployed via Bicep to verify functionality, then scaled down for cost control.
- **Architectural Design:** Documented enterprise topology with identified deployment prerequisites.

---

## 1. Scope of Verification

Validation covers three core layers:
1. **Infrastructure Security:** Enterprise edge controls, managed identities, and keyless service configurations.
2. **Application & AI Safety:** Automated prompt injection resilience, deterministic safety boundaries, and token handling.
3. **Dynamic Security Testing (DAST):** Live API endpoint auditing, HTTP transport headers, and attack surface reduction.

---

## 2. Infrastructure & Enterprise Controls

### 2.1 API Management (APIM Edge Gateway) - Validated & Deployed

`infra/modules/document/apim.bicep` was deployed on the **Consumption** SKU (pay-per-call, zero idle cost) to act as a **JWT-validating edge gateway** in front of the Container Apps backend:
- An inbound `validate-jwt` policy checks the Entra External ID (CIAM) access token against the tenant OpenID configuration and the API audience before traffic reaches the container.
- CORS policy is restricted to approved frontend origins.
- `subscriptionRequired` is set to `false`, allowing standard OAuth bearer tokens without exposing static API keys in the client bundle.

| Verification Check | Method | Expected / Actual Result | Status |
|---|---|---|---|
| Gateway deployment | Azure CLI provisioning state | `Succeeded` | Pass |
| Unauthenticated request | `GET /api/health` without token | HTTP 401: `"A valid Entra token is required."` | Pass |
| Malformed token handling | Bearer token with invalid signature | HTTP 401 | Pass |
| CORS preflight from allowed origin | `OPTIONS` from `https://mindgpt-h8am.vercel.app` | HTTP 200 with matching `Access-Control-Allow-Origin` | Pass |

Gateway Endpoint: `https://mindgpt-build-rdye3f7vd4bkg-apim.azure-api.net`  
Frontend routing can target this gateway by setting `VITE_API_BASE_URL` to the APIM endpoint in Vercel project settings.

*Rate Limiting Note:* Because the APIM Consumption tier does not support keyless per-client rate-limiting policies without subscriptions, request throttling is handled at the application level within FastAPI. Higher APIM SKUs (Standard or Premium) can enforce network-level throttling if upgraded.

### 2.2 Microsoft Defender for Cloud - Validated via IaC

`infra/modules/document/defender.bicep` was deployed at the subscription scope with `pricingTier=Standard` to verify template validity and plan activation across core resources (Cosmos DB, Storage, Key Vault, and App Services). The plans were subsequently returned to `Free` to prevent ongoing credit consumption.

Basic Cloud Security Posture Management (CSPM) remains active on the subscription, providing continuous recommendations through the Azure Portal.

### 2.3 Virtual Network & Private Endpoints - Architectural Design

`vnet-private-endpoints.bicep` details the enterprise network isolation topology. In a full production deployment, the following prerequisites apply:
1. **Private DNS Zones:** Requires `privatelink.*` zones, virtual network links, and DNS zone groups to resolve private endpoints internally.
2. **Container Apps Environment:** VNet integration must be established at environment creation time (`vnetConfiguration.infrastructureSubnetId`).
3. **AI Search Tier:** Requires Azure AI Search Basic tier or higher (the Free SKU does not support private endpoints).

Because retrofitting VNet integration would require recreating the active Container Apps environment and upgrading free-tier resources, this design is maintained as an enterprise reference.

### 2.4 Azure Front Door & WAF - Architectural Design

`infra/modules/document/front-door-waf.bicep` defines a global Web Application Firewall (WAF) using Microsoft managed rule sets (OWASP Core Rule Set and Bot Protection).

When deploying to an Azure for Students subscription, Front Door resource creation is restricted at the tenant subscription level:
`BadRequest: Free Trial and Student account is forbidden for Azure Frontdoor resources.`

In the current live deployment, frontend edge services (TLS termination, edge caching, and global DNS) are managed by Vercel, with the Bicep template serving as the enterprise deployment model for standard enterprise subscriptions.

---

## 3. Keyless Azure Functions Deployment (Flex Consumption)

The scheduled retention cleanup job was implemented using an Azure Function on the **Flex Consumption (`FC1`)** plan. Unlike classic Consumption plans that require connection strings for Azure Files storage mounts, Flex Consumption supports keyless managed identities for deployment artifacts and runtime storage.

| Configuration Item | Setting |
|---|---|
| Hosting Plan | Flex Consumption (`FC1`) |
| Deployment Storage Authentication | User-Assigned Managed Identity |
| Storage Account Shared Key Access | Disabled (`allowSharedKeyAccess: false`) |
| Runtime Environment | Python 3.11 |
| Function Trigger | Timer Trigger (`retention_cleanup`, daily at 03:00 UTC) |

The cleanup script deletes conversations older than 90 days and removes orphaned image blobs. The function was initially validated with `CLEANUP_DRY_RUN=true` and subsequently set to active mode (`CLEANUP_DRY_RUN=false`).

---

## 4. Prompt Injection & AI Safety Validation

The automated test suite in `backend/tests/test_injection_suite.py` contains **41 test cases** verifying resilience against common LLM adversarial techniques, such as instruction overrides, persona hijacking, forged system markers, and prompt leakage.

| Invariant Tested | Asserted Behavior | Test Outcome |
|---|---|---|
| Input Independence | `build_system_prompt()` output is static and immutable by user content | Pass |
| Strict Turn Separation | User inputs are contained inside user conversation turns | Pass (8 payloads) |
| Disjoint Channels | System and user role namespaces cannot be blended | Pass (8 payloads) |
| Indirect Injection Containment | Retrieved knowledge base context is wrapped in explicit attribution markers | Pass |
| Conversation History Isolation | Injections in previous messages cannot escalate privilege in later turns | Pass |
| Crisis Detection Priority | Deterministic crisis rules trigger even if input contains prompt injection framing | Pass (4 test cases) |
| False Positive Separation | Benign injection-like strings do not trigger crisis responses | Pass (8 test cases) |
| Fail-Closed Content Safety | Inputs flagged by Prompt Shields abort processing immediately with HTTP 400 | Pass (8 test cases) |
| Execution Order | Safety checks run before model invocation to prevent token consumption on blocked requests | Pass |
| Support Continuity | Standard emotional support questions are not erroneously blocked | Pass |

This suite runs alongside unit and integration tests in CI/CD, giving a total of 159 passing automated backend tests.

---

## 5. Dynamic Application Security Testing (DAST)

A custom security probe script (`security/dast_probe.py`) performs 14 automated runtime checks against the live Container App API and APIM gateway.

| Test Category | Initial Status | Remediated Status |
|---|---|---|
| HTTPS Transport Verification | Pass (HTTP 200) | Pass (HTTP 200) |
| Authentication Enforcement (`/chat`, `/conversations`, `/profile`) | Pass (HTTP 401) | Pass (HTTP 401) |
| APIM Edge Gateway Authentication | Pass (HTTP 401) | Pass (HTTP 401) |
| Insecure HTTP to HTTPS Redirection | Pass (HTTP 301) | Pass (HTTP 301) |
| Error Message Sanitization (malformed input) | Pass (HTTP 422, no tracebacks) | Pass (HTTP 422, no tracebacks) |
| CORS Origin Validation (unauthorized domain) | Pass (No CORS header returned) | Pass (No CORS header returned) |
| Unsupported HTTP Verbs (e.g. TRACE) | Pass (HTTP 405 Method Not Allowed) | Pass (HTTP 405 Method Not Allowed) |
| Server Software Version Disclosure | Pass (Generic server identifier) | Pass (Generic server identifier) |
| Strict-Transport-Security (HSTS) Header | Warning (Header missing) | Pass (Header present) |
| X-Content-Type-Options: nosniff Header | Warning (Header missing) | Pass (Header present) |
| Interactive API Documentation Protection | Warning (`/docs` accessible) | Pass (HTTP 404 in production) |
| **Overall Summary** | **11 Pass / 3 Warning** | **14 Pass / 0 Warning / 0 Fail** |

### Remediations Applied

1. **Security Headers:** Added custom FastAPI middleware enforcing `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
2. **API Reconnaissance Reduction:** Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI schema endpoints are disabled by default in production, controllable via the `ENABLE_API_DOCS` configuration setting.

Unit tests in `backend/tests/test_health.py` verify that these headers remain enforced on all endpoints.

---

## 6. Summary of Controls

| Control | Implementation Level | Verification Status |
|---|---|---|
| APIM Edge Gateway & CORS | Cloud Edge | Validated & Deployed (HTTP 401 edge rejection verified) |
| Defender for Cloud Security Plans | Subscription / Cloud | Validated via IaC (reverted to free tier) |
| Virtual Network & Private Endpoints | Network Layer | Architectural Design (documented prerequisites) |
| Azure Front Door & WAF | Global Edge | Architectural Design (restricted on student accounts) |
| Keyless Scheduled Functions | Serverless Compute | Validated & Deployed (Flex Consumption, active) |
| Prompt Injection Resistance | Application Pipeline | Validated (41 automated test cases passing) |
| Runtime Security Headers | Application Gateway / API | Validated & Deployed (14 DAST checks passing) |
| PII Redaction & Content Safety | AI Pipeline | Validated Live (Azure Language & Content Safety) |
