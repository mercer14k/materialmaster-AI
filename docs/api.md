# API conventions

Base path: `/api/v1`. Live schemas: `/openapi.json`, interactive reference `/docs`. Liveness `/health`; database readiness `/ready`. `X-Trace-ID` is returned and written to structured request logs. Safe supplied trace IDs are accepted; malformed values are replaced.

## Reads

| Method | Path | Purpose |
|---|---|---|
| GET | `/config` | Current demo/auth, embedding and language-model modes |
| GET | `/datasets` | Imported dataset metadata and validation counts |
| GET | `/overview?dataset_id=...` | Current computed metrics, review counts and real scan history |
| GET | `/ai/models` | Local runtime inventory and availability; no default selection |
| GET | `/materials?dataset_id=...&search=...&group=...&source=...` | Filterable normalized material records and provenance |
| GET | `/findings?dataset_id=...&kind=...&status=...&search=...` | Prioritized review queue |
| GET | `/findings/{id}` | Evidence, raw records and complete review history |
| GET | `/datasets/{id}/validation` | Quarantined rows and error reasons |
| GET | `/remediation?dataset_id=...` | Proposed actions requiring human approval |
| GET | `/audit` | Workspace-wide audit history |
| GET | `/export/findings.csv?dataset_id=...` | Spreadsheet-safe findings export |
| POST | `/validate` | Read-only bulk schema validation, up to 10,000 records |

List endpoints use `limit` (1–200, defaults 30 or 50) and `offset` (>=0). Responses contain `items`, `total`, `limit`, `offset`. The default dataset is the latest import. Audit/history are explicitly workspace-wide; this release has no tenant isolation. Remediation/export are full-snapshot outputs, not paginated.

## Commands

All commands require `Idempotency-Key`: 8–100 letters, numbers, `_`, `.`, `:` or `-`. Scope is the authenticated role identity. Exact replay returns the original result; a different payload using the same key returns 409. Concurrent first-use races can return 409; retry the same request after the competing transaction completes.

| Method | Path | Body |
|---|---|---|
| POST | `/commands/import` | Multipart `file`: JSON/JSONL/CSV, <=20 MiB |
| POST | `/commands/datasets/{id}/scan` | No body |
| POST | `/commands/findings/{id}/review` | `decision`, `reason`, `expected_version` |
| POST | `/commands/findings/{id}/explain` | Required body: `runtime` (`ollama` / `llamacpp`) and `model` (exact installed ID); no defaults |

Review decisions are `accepted`, `rejected` or `deferred`. Reasons are 5–1000 characters; the optimistic version is read from the finding. Server actor identity is not client-supplied. Acceptance means the issue is acknowledged, never that it has been repaired.

Successful commands return `{"result": ...}`. Mutations and audit/idempotency writes share a database transaction; commit occurs before returning success.

## Errors

```json
{"error":{"code":"conflict","message":"Finding was updated by another reviewer; reload before deciding","trace_id":"..."}}
```

422 for schema/envelope failures, 415 for unsupported files, 413 for size violations, 401/403 for access failures, 404 for missing IDs, 409 for concurrent versions/reused keys. Internal errors expose a trace ID, not SQL statements or stack traces. Quarantined rows are not HTTP errors when the file envelope is valid; inspect the import result's invalid count.

## Selecting a local explanation model

Read `/api/v1/ai/models`, let the user choose, and POST that exact runtime/model to `/api/v1/commands/findings/{id}/explain` with a fresh idempotency key. The model must still be installed when the command executes. Missing selection / uninstalled or non-completion model: 422; disabled or changed runtime: 409; unverifiable inventory: 503. Inference failures after verification return a structured abstention and telemetry without modifying findings. Reusing a command key with a different model is a conflict. Model choice is not saved as a workspace default. No runtime URL, filesystem path or download command is accepted from the request.

Workplace import mapping and scope: [data-sources.md](data-sources.md). The bundled [CSV template](../data/sample/import-template.csv) is a synthetic example of the accepted contract.
