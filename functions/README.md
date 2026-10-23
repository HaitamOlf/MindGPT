# functions/ — Scheduled cleanup (Azure Functions, Python timer trigger)

A data-retention job that runs as a **timer trigger**, deliberately **not** an HTTP
endpoint — there is no inbound HTTP surface to spoof into triggering a privileged
data-deletion job. Authenticates to Cosmos via the Function App's **managed identity**
(`DefaultAzureCredential`), never a key.

## What it does

Two sweeps, both in `cleanup.py`:

- **Conversation retention** — deletes Cosmos `conversations` whose last activity
  (`updatedAt`) is older than the retention window.
- **Orphaned-image cleanup** — removes Blob `uploads` objects whose owning conversation no
  longer exists (and stale `temp/` uploads past a cutoff), so an image can't outlive the
  conversation it belonged to. Enabled when `BLOB_ENDPOINT` is set.

## Safety posture

- **Dry-run safe by default in code** — if `CLEANUP_DRY_RUN` is unset/misconfigured the job
  logs what it *would* delete and deletes nothing; a cleanup job must never be dangerous by
  default. The deployed app runs `CLEANUP_DRY_RUN=false` (armed) only after the logic and its
  tests were verified in Phase 6 ([`../docs/SECURITY_VALIDATION.md`](../docs/SECURITY_VALIDATION.md) §3).
- A **non-positive `RETENTION_DAYS` is refused** outright, so a bad env value can never
  resolve to a cutoff that selects the entire store.
- Each delete is **isolated**: one failure is logged and the run continues.
- Source is committed; there is no compiled build artifact. `local.settings.json` is
  gitignored.

## Why Python

The entire backend is Python, so the cleanup reuses the exact Cosmos access pattern
(container name, `userId` partition key, managed-identity credential) already verified
against the real `azure-cosmos` SDK in [`../backend/app/data/cosmos_client.py`](../backend/app/data/cosmos_client.py),
and the logic is unit-tested with the same pytest tooling as the rest of the repo rather
than a second Node toolchain. A regression test (`tests/test_cleanup.py`) asserts the
container/partition constants stay in lockstep with the backend.

## Layout

```
functions/
├─ function_app.py   # @app.timer_trigger — the thin runtime wrapper
├─ cleanup.py        # retention logic, runtime-free so it is directly unit-testable
├─ host.json         # Functions host config (extension bundle v4)
├─ requirements.txt  # azure-functions + azure-cosmos/-identity/-storage-blob, aligned w/ backend
└─ tests/
   └─ test_cleanup.py  # 10 tests: conversation + orphaned-image sweeps, dry-run, per-item
                        # partition key, cutoff math, safety lock, error isolation,
                        # backend-constant lockstep
```

## Configuration (App Settings)

| Setting | Required | Default | Meaning |
|---|---|---|---|
| `COSMOS_ENDPOINT` | ✅ | — | Cosmos account endpoint URI |
| `COSMOS_DATABASE_NAME` | | `mindgpt` | database name |
| `AZURE_CLIENT_ID` | | — | user-assigned managed identity client id |
| `BLOB_ENDPOINT` | | — | enables the orphaned-image sweep when set |
| `RETENTION_DAYS` | | `90` | delete conversations idle longer than this |
| `CLEANUP_DRY_RUN` | | `true` in code; **`false`** as deployed | code is safe-by-default; the live app is armed (Phase 6) |

Schedule: `0 0 3 * * *` (NCRONTAB) — 03:00 UTC daily.

## Running the tests

```bash
python -m venv .venv
.venv\Scripts\activate   # or: source .venv/bin/activate
pip install -r requirements.txt pytest
pytest
```

## Deployment status

The timer function **is deployed** to the live Function App (Flex Consumption, `FC1`) and
**armed** (`CLEANUP_DRY_RUN=false`) — see [`../docs/SECURITY_VALIDATION.md`](../docs/SECURITY_VALIDATION.md)
§3. The Function App's managed identity holds the Cosmos data-plane role via
`infra/modules/build/cosmos-db.bicep` and Blob Data Owner on the uploads account. The delete
paths are unit-tested against mocked containers (10 tests); the first *live* scheduled runs
(03:00 UTC daily) are observable in Application Insights.
