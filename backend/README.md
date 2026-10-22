# backend/ — FastAPI on Azure Container Apps

The MindGPT API. See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) and
[`../docs/THREAT_MODEL.md`](../docs/THREAT_MODEL.md).

**Modules:** `auth/` (Entra JWT validation); `safety/` (Prompt Shields, output + image
moderation, PII redaction, deterministic crisis detection); `rag/` (behavioral corpus,
Azure AI Search, retrieval, prompt assembly); `llm/` (provider interface + Azure OpenAI
`gpt-5-mini` + a local stub for CI); `data/` (Cosmos stores + Blob store); `analysis/` (AI
Language sentiment, fail-open); and `routers/` wiring it together — `chat.py` (the full
pipeline), `conversations.py` (history CRUD), `profile.py`/`memory.py`/`wellness.py` (the
account-dashboard data APIs), and `uploads.py` (image upload). Scheduled cleanup lives in
[`../functions/`](../functions) as a timer trigger.

```
backend/
├─ app/
│  ├─ core/
│  │  └─ config.py         # Settings — mirrors infra's container-apps.bicep env vars exactly
│  ├─ auth/
│  │  ├─ entra.py          # JWT validation (issuer/audience/signature/expiry), PyJWT + JWKS
│  │  └─ dependency.py     # FastAPI dependency → user_id, generic 401 on any failure
│  ├─ safety/
│  │  ├─ crisis.py         # deterministic keyword detection + vetted hotline
│  │  ├─ content_safety.py # Prompt Shields + harm-category moderation (text + images)
│  │  └─ pii.py            # PII detection/redaction, fails closed (Azure AI Language)
│  ├─ rag/
│  │  ├─ grounding.py      # psychological grounding text
│  │  ├─ guardrails.py     # safety guardrail text
│  │  ├─ corpus.py         # the 14-doc corpus (8 emotional patterns + 6 response strategies)
│  │  ├─ search_client.py  # Azure AI Search index/upload/query
│  │  ├─ retrieval.py      # query → formatted "[RETRIEVED INTERPRETIVE SCAFFOLDING]" text
│  │  └─ prompt_assembly.py # structured, spotlighted prompt assembly
│  ├─ llm/
│  │  └─ provider.py       # LLMProvider interface; AzureOpenAIProvider (gpt-5-mini, Entra
│  │                        # auth) + LocalStubProvider (CI, no live model)
│  ├─ data/
│  │  ├─ _client.py        # shared managed-identity Cosmos container accessor
│  │  ├─ cosmos_client.py  # conversation persistence, partition key = userId
│  │  ├─ profile_store.py  # one profile doc/user (id == userId)
│  │  ├─ memory_store.py   # user memory-bank notes
│  │  ├─ wellness_store.py # daily sentiment aggregates (derived score only, no text)
│  │  └─ blob_store.py     # private image upload + owner-scoped user-delegation SAS
│  ├─ analysis/
│  │  └─ sentiment.py      # AI Language sentiment → [-1,1] score; FAILS OPEN (ancillary)
│  ├─ routers/
│  │  ├─ health.py         # unauthenticated liveness/readiness probe
│  │  ├─ chat.py           # POST /chat — the full pipeline, see below
│  │  ├─ conversations.py  # create / list / read messages / delete — all partition-scoped
│  │  ├─ profile.py        # GET/PUT /profile
│  │  ├─ memory.py         # GET/POST/DELETE /memory
│  │  ├─ wellness.py       # GET /wellness — daily sentiment series
│  │  └─ uploads.py        # POST /uploads — validated, scanned, private image upload
│  └─ main.py               # FastAPI app factory + CORS middleware
├─ scripts/
│  └─ ingest_corpus.py     # one-off: push the 14-doc corpus into Azure AI Search
├─ tests/                   # 115 tests — mocked Azure clients (CI-safe) + pure-logic tests
│                            # + real-crypto JWT tests + real-pipeline integration tests
├─ requirements.txt          # pinned, runtime deps only
├─ requirements-dev.txt      # + pytest, httpx2 (not httpx — see comment in the file)
└─ Dockerfile                # non-root, base image pinned by digest
```

## Running locally

```bash
python -m venv .venv
.venv\Scripts\activate   # or: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env     # /health works with no env vars; the rest needs real endpoints
uvicorn app.main:app --reload
pytest
```

Everything that touches Azure (`safety/`, `rag/search_client.py`, `data/`, `llm/`,
`analysis/`) needs live endpoints in `.env` and an `az login` with the right data-plane
roles. `DefaultAzureCredential` falls back to your CLI session when no managed identity is
present — the same code path that uses the managed identity in Container Apps. Leaving
`AZURE_CLIENT_ID` blank selects the az-CLI identity locally.

## `POST /chat` — the pipeline

```
auth (JWT → userId)
  → validate any attached image reference is owner-prefixed
  → crisis check            — short-circuits here; no Shields, no model call
  → Prompt Shields           — 400, no persistence, on a detected injection
  → PII redaction            — for storage/logs only; retrieval + prompt assembly
                                still use the original message text
  → retrieval + prompt assembly
  → LLMProvider.generate     — gpt-5-mini (AzureOpenAIProvider), stub in CI
  → output moderation        — fails closed: a flagged reply never reaches the user
  → persist (Cosmos, partition = userId)
  → record wellness sentiment sample (fail-open) → respond
```

Request: `{"message": str, "conversationId": str | null, "imageBlobName": str | null}`.
Response: `{"reply": str, "conversationId": str}`. Omit `conversationId` to start a new
conversation; an unknown ID (including one belonging to a different user — the Cosmos read
is partition-scoped, so it fails closed by construction) returns 404. An `imageBlobName`
that isn't under the caller's own blob prefix is rejected (`400`) before anything is
persisted.

**Validated live, not just unit-tested.** The full pipeline has been exercised end-to-end
against the real deployed services — a real browser sign-in produces a token the API
accepts, a real injection attempt is caught (400), PII is redacted in persisted messages,
retrieval runs, **gpt-5-mini** returns a real reply, and the conversation persists to
Cosmos. The committed test suite (115 tests) drives every Azure call mocked so CI needs no
credentials; `tests/test_entra_auth.py` does real RS256 signature verification with a
self-generated keypair (wrong audience/issuer, expired, and a differently-signed token are
all rejected).

## `/conversations` — history CRUD

| Method | Path | Returns |
|---|---|---|
| `POST` | `/conversations` | `201` → `{id, title, createdAt, updatedAt}` (new, empty) |
| `GET` | `/conversations` | `200` → that user's conversations, newest-activity first |
| `GET` | `/conversations/{id}/messages` | `200` → ordered `{id, role, text, timestamp, imageUrl?}[]` |
| `DELETE` | `/conversations/{id}` | `204` on delete, `404` if not in the caller's partition |

Every endpoint takes `userId` from the validated JWT (`get_current_user_id`), never from
the path or body, and every Cosmos access is scoped to that user's partition — so an ID
belonging to another user is simply "not found" (`404`). A conversation's `title` is
derived from its first (already PII-redacted) user message; there is no rename endpoint, so
no unused write surface ships. `message.id` is synthesized from `{conversationId}-{index}`
for a stable client key — messages are an ordered array inside the conversation document,
not separately-identified records. A message's `imageUrl`, when present, is a freshly
minted short-lived read SAS (never a stored URL), produced only for the owning caller.

## `/profile`, `/memory`, `/wellness` — account-dashboard data

The dashboard reads and writes through the API only (no direct database access from the
browser), each endpoint partition-scoped to the JWT's `userId`:

| Method | Path | Returns |
|---|---|---|
| `GET` / `PUT` | `/profile` | the user's `{fullName, dateOfBirth, country}` (`404` until first set) |
| `GET` | `/memory` | user memory-bank notes, newest first |
| `POST` | `/memory` | create a note (always `source: "user"` — a client can't forge `"model"`) |
| `DELETE` | `/memory/{id}` | `204` / `404` if not in the caller's partition |
| `GET` | `/wellness?days=N` | daily `{date, averageSentiment}` series (sentiment in `[-1,1]`) |

**Wellness data is produced by chatting**, not written directly: `POST /chat` scores each
user message with AI Language sentiment (`app/analysis/sentiment.py`) and folds it into the
day's running average (`wellness_store.record_sentiment`). This step **fails open** — a
Language outage logs and skips the sample, never breaking the chat response — the
deliberate opposite of PII redaction's fail-closed. Only the derived score is stored, never
the message text. `memory`'s `"model"` source is reserved for a future server-side
extraction step and is not written yet.

## `POST /uploads` — image upload

Multipart `file` (+ optional `conversationId`). The order of checks is security-first:
auth → size/MIME validation (JPEG/PNG, ≤10 MB) → conversation-ownership check → **Content
Safety image moderation** (a flagged image is rejected and never written) → store to the
private `uploads` container via managed identity under `{userId}/...` → return
`{blobName, url}` where `url` is a short-lived (≤1 h) owner-scoped user-delegation SAS.
The blob is private; it is only ever served through a freshly minted read SAS (here and
when listing a conversation's messages), never a public URL — the account has
`allowBlobPublicAccess:false` and `allowSharedKeyAccess:false`, so a user-delegation SAS is
the only way in at all.

## Auth — validated live

`app/auth/entra.py` was built against the real deployed Entra External ID tenant: the OIDC
discovery doc, the `jwks_uri`, and the exact `issuer` string
(`https://<tenant-id>.ciamlogin.com/<tenant-id>/v2.0`, using the tenant-ID subdomain, not
the friendly `mindgpt.ciamlogin.com` one used for the login endpoints) were all fetched
live and confirmed before writing the validation code. A real browser sign-in through the
frontend has since been exercised end-to-end: the token it produces is accepted by this
API, closing the loop from MSAL config → CIAM authorization → API scope → JWT validation.
Both app registrations must be **single-tenant** (`signInAudience: AzureADMyOrg`) — Entra
External ID only supports single-tenant apps, and a multi-tenant one fails token issuance
with `AADSTS500207`.

## Non-negotiables (from the threat model)
- Managed identity for all Azure calls; no keys/connection strings in code.
- `userId` derived only from the validated token, never from the request body.
- Pydantic request models; length/size/MIME validation; generic error responses.
- Cleanup runs as an Azure Functions **timer trigger**, not an HTTP endpoint.
- CORS allow-list is exactly one origin from `Settings.cors_allowed_origin`, never a
  wildcard — the frontend lives on Vercel, outside the Azure tenant (`docs/ARCHITECTURE.md`
  §10); `allow_credentials` stays `False` since auth is a bearer JWT, not a cookie.
- Crisis messages are intercepted in code (`app/safety/crisis.py`) before the model is ever
  called — a vetted hotline, never a model-generated one.
- PII redaction fails closed: a Language-service error blocks persistence/logging, it never
  silently falls back to the unredacted text.
