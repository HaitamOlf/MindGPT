# MindGPT: Security-First AI Emotional Support Platform (Azure)

A full-stack AI emotional-support companion built on **Microsoft Azure**, designed with security, privacy, and safety as primary engineering goals across the pipeline, the web frontend, cloud storage, and user data. MindGPT grounds an LLM on a curated behavioral knowledge base, runs every message through a layered safety pipeline, and stores sensitive personal data using least-privilege, keyless authentication and per-user data isolation.

**Author:** Haitam Oualif

> **Status:** Built, deployed, and validated live. The full stack runs end-to-end against Azure cloud services: Entra External ID authentication, the chat and safety pipeline, RAG retrieval, Cosmos DB persistence, private Blob image uploads, and Azure OpenAI (`gpt-5-mini`) inference. The backend is deployed on Azure Container Apps and the frontend is hosted on Vercel.

---

## Core Security & Privacy Principles

MindGPT processes sensitive user conversations regarding emotional well-being (classified as special-category health data under GDPR Article 9). Because untrusted user text directly interacts with a generative model, security and privacy requirements directly guide the system design:

- **Identity over secrets:** Managed identities are used across all services; shared access keys and connection strings are disabled on Cosmos DB, Blob Storage, and Azure OpenAI.
- **Per-user isolation:** Data is strictly partitioned by `userId`. Authorization is enforced server-side on every request to prevent unauthorized cross-user access.
- **Untrusted input handling:** Requests pass through Azure AI Content Safety Prompt Shields, structured prompt templates, and output moderation. Images are scanned for sensitive content before storage.
- **Privacy by default:** Personally Identifiable Information (PII) is detected and redacted before persistence or logging.
- **Security as code:** Infrastructure is defined in Bicep templates and validated through automated security scanning in CI/CD.

The [threat model](./docs/THREAT_MODEL.md) evaluates this surface through STRIDE and the OWASP LLM Top 10, while the [architecture](./docs/ARCHITECTURE.md) maps each control to specific Azure services.

## Documentation

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md): Azure architecture, core security pillars, request flow, and infrastructure design.
- [`docs/THREAT_MODEL.md`](./docs/THREAT_MODEL.md): STRIDE threat analysis, OWASP LLM Top 10 mitigations, and residual risk assessment.
- [`docs/SECURITY_VALIDATION.md`](./docs/SECURITY_VALIDATION.md): Validation evidence, including prompt injection testing, DAST security scans, and deployed cloud controls.
- [`docs/ENTRA_SETUP.md`](./docs/ENTRA_SETUP.md): Microsoft Entra External ID (CIAM) tenant and application registration guide.
- [`infra/README.md`](./infra/README.md): Bicep infrastructure deployment and CI/CD workflow details.

## Repository Structure

```
MindGPT/
├─ docs/           # Architecture, threat model, and setup guides
├─ frontend/       # React + TypeScript + Vite (Entra External ID / MSAL)
├─ backend/        # FastAPI on Azure Container Apps (managed identity, Azure SDKs)
├─ infra/          # Bicep IaC (core application and security infrastructure)
├─ functions/      # Timer-triggered retention cleanup (no inbound HTTP surface)
└─ datasets/       # Behavioral knowledge base (emotions, cognitive patterns, coping strategies)
```

## Architecture & Implementation Overview

| Area | Implementation | Status |
|---|---|---|
| Identity | Entra External ID (MSAL), JWT validation, single-tenant application registrations | Validated live |
| Chat Pipeline | Deterministic crisis check → RAG search → gpt-5-mini → output moderation → persistence | Validated live |
| Safety & Privacy | Azure Content Safety (Prompt Shields, severity thresholds), PII redaction (Azure Language) | Validated live |
| Data Persistence | Azure Cosmos DB (conversations, user profile, memory, wellness) partitioned by `/userId` | Validated live |
| Object Storage | Private Azure Blob Storage with owner-scoped user delegation SAS tokens | Validated live |
| Infrastructure | Modular Bicep IaC, automated deployment workflows with GitHub Actions OIDC | Deployed |
| Hosting | Backend on Azure Container Apps, frontend on Vercel, Azure OpenAI `gpt-5-mini` | Deployed live |
| Security Testing | Prompt injection test suite, automated DAST checks, Defender cloud posture | Verified |

## Running Locally

### Backend Setup

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env            # Configure endpoint URLs; use Azure CLI login for local auth
./.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env            # Pre-filled with CIAM identifiers; set VITE_API_BASE_URL
npm run dev                     # Accessible at http://localhost:5173
```

Authentication relies on Microsoft Entra External ID. Refer to [`docs/ENTRA_SETUP.md`](./docs/ENTRA_SETUP.md) for identity setup instructions, and the respective README files in `frontend/` and `backend/` for local details.

## Safety & Ethics Notice

MindGPT is designed as an educational and technical demonstration of AI safety practices. It is not a clinical or medical diagnostic tool and is not a substitute for professional mental health services. Deterministic crisis safeguards are implemented to route emergency inquiries directly to certified support hotlines.
