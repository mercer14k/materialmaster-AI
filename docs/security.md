# Threat model and security boundaries

## Intended deployment

The default is a single-user localhost demo using synthetic data. Compose publishes only loopback ports; PostgreSQL and Ollama have no host-published port. `AUTH_MODE=demo` deliberately grants a local steward role. It is not an internet-facing authentication scheme. The frontend visibly labels demo access.

`AUTH_MODE=token` requires bearer credentials. `READ_TOKEN` authorizes read/validation requests; `WRITE_TOKEN` authorizes imports, scans, reviews and explanations. Roles are assigned by the server, not trusted from request fields. Use unique strong values and TLS before sharing. Tokens are kept in browser memory, not local storage. The sample database passwords are explicit public demo values, not production secrets.

## Assets and attackers

Assets: supplier pricing, source descriptions, lineage, review decisions, credentials, model artifacts and quality metrics. Attackers may supply malformed files, hostile descriptions, incorrect citations, stale decisions or abusive API requests. Trusted operators control local model paths, runtime configuration and database credentials.

| Threat | Implemented boundary | Residual risk |
|---|---|---|
| Malformed upload or resource exhaustion | 20 MiB HTTP/file bounds, 100k row import cap, 10k bulk-validation cap, MIME/extension checks, UTF-8 parsing, schema limits, bounded candidate blocks | Multiple simultaneous imports or long scans need gateway rate limits and job scheduling |
| Filename traversal | Basename extraction and safe-character replacement; uploads are parsed in memory, never saved under supplied paths | Filename metadata is not an authenticity signal |
| SQL injection | SQLAlchemy bound queries and escaped substring searches; no model-generated SQL | Trusted DB admins remain privileged |
| Prompt injection | Retrieved fields treated as untrusted data, strict citations/schema, no tools available to model | Narrative can still be misleading; human evidence review is required |
| Cross-user write escalation | Server read/steward roles, write dependencies on every command | Shared tokens identify roles rather than individual people; OIDC is future work |
| Duplicate/replayed commands | Actor-scoped idempotency key with payload hash in the same transaction | Simultaneous first-use conflicts return 409; callers must retry |
| Lost review update | Version-guarded atomic SQL update; 409 on stale expected version | Reviewer must reopen updated evidence |
| Model corruption of source state | Explanation returns text only; deterministic state is never assigned from it | A human can still act on bad advice outside the app |
| SSRF through local model URL | Fixed local host allowlist, HTTP only, environment proxy disabled; no runtime URL in request body | Operator-controlled local services are trusted; this is not a hardened tenant isolation boundary |
| XSS / spreadsheet formula injection | React escapes source text; production CSP, no raw HTML rendering, formula-prefixed export cells escaped | Review downstream CSV consumers and future new export columns |
| Unnecessary database privileges | Compose app role is non-superuser; GET routes use a separate SELECT-only role | App role creates the fresh schema and could alter its own tables if compromised |
| Sensitive logs | HTTP logs contain path/status/trace/time, not raw uploaded records or tokens; model failures store error types | IDs/metadata can still be sensitive; local DB files need access protection |
| Supply-chain vulnerabilities | Exact installed constraints, pnpm lockfile, pip-audit/pnpm audit CI, license inventory | Advisories and transitive dependencies change; no scan guarantees absence of vulnerabilities |

## Audit and retention

Every successful import, scan and review produces an audit event in the same transaction. Explanations log runtime/config and validation telemetry even when they abstain. Application APIs provide no audit update/delete endpoint. This is **not cryptographic tamper evidence**: DB owners can edit history. Back up the database, apply filesystem permissions, and define retention before using real records.

Rejected rows intentionally retain original content for steward correction. Do not ingest secrets. Retention/deletion tooling, row-level tenancy, per-person identity and signed exports are not implemented in version 0.1.

## Operations checklist

Keep `.env`, local databases, model weights and generated full datasets out of Git. Use `.env.example` only for public defaults. URL-encode database passwords used in connection URLs; prefer simple generated URL-safe values for this demo. Changing role passwords in `.env` after database initialization does not update existing database roles; rotate via controlled database administration.

Install dependencies only from trusted package indexes and verify downloaded model artifacts/licenses. Never execute model-proposed shell or SQL. No model-side mutation tools are configured. Review dependencies and container image updates before releases; container tags are explicit but not digest-pinned yet.

Report reproducible vulnerabilities using [SECURITY.md](../SECURITY.md), with synthetic data only.

## Local model discovery

Inventory is read only from the operator-configured, allowlisted local runtime URL. HTTP redirects and environment proxy inheritance are disabled. The client submits an explicit runtime/model; it cannot submit a URL, pull models or execute commands. Inventory is revalidated before inference, and Ollama show metadata rejects cloud-backed aliases and non-completion models before source data is sent. The configured runtime remains a trusted operator boundary. Browser model selection is session-only, not a global default. Read-token users can list inventory; generating explanations remains a steward command.
