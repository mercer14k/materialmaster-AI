# Architecture

MaterialMaster is a synchronous, locally runnable reference implementation. It is designed around immutable imported snapshots and human review, not ERP write-back.

## Dependency direction

`apps/web → apps/api → services → domain`. Embedding/explanation adapters implement narrow interfaces in `ai`. Domain models and the computational engine do not depend on FastAPI, React, a database or a language model.

1. Ingestion parses a UTF-8 envelope, validates individual records and retains both raw and normalized representations. Schema-invalid rows are separately queryable. Dataset content hashes make provenance inspectable.
2. The engine performs UOM/purchasing/lifecycle/lead-time checks, price normalization and peer statistics, and bounded duplicate candidate generation. A pure function returns findings and algorithm metadata.
3. A scan transaction persists stable finding IDs and a quality snapshot. Existing review decisions survive rescans. Absent findings are marked inactive, never erased.
4. Reviews update an issue using a version-guarded SQL update. The decision and audit event commit in the same transaction before an HTTP success is returned. Request fingerprints prevent idempotency keys from being reused with different payloads.
5. Optional model calls receive existing evidence and return schema-validated narrative. They cannot change findings, materials or review state. Telemetry persists independently of explanation success.

## Storage and consistency

SQLite WAL is the native development default; PostgreSQL is the Compose path. The same SQLAlchemy services run against both. Compose creates a non-superuser application role plus a read-only role for GET routes. Bootstrap credentials are confined to database initialization. The app creates the initial schema as the app role; version 0.1 requires a fresh schema. Migrations are a documented next step.

Dataset IDs scope material IDs. A source-qualified stable material identifier is required if ERP systems reuse local numbers. A finding key combines dataset ID, rule kind and sorted material IDs. Audit is append-only through application APIs, not immutable against database administrators.

## Scale and performance

Candidate blocks use canonical manufacturer/part IDs, exact descriptions, and group/manufacturer/numeric-spec signatures. Within-block cosine scoring is bounded to 80 records; truncation is surfaced. No global all-pairs similarity matrix is allocated. Generator, validation and analysis timings are measured separately.

Version 0.1 loads a snapshot and its findings into memory. Uploads cap at 20 MiB; bulk CLI imports have no browser size limit. Review queue search and learned ordering are in-process before response pagination. There are no claims of million-record interactive latency or horizontally scalable background jobs.

## Quality semantics

`quality = 100 × (1 − distinct affected valid material IDs / valid material count)`. Empty valid datasets return `null`, not a fabricated perfect score. Invalid rows are separate. Accepting/rejecting a finding does not change source quality; importing corrected data changes the measured baseline. History consists only of actual scan snapshots and includes group/source breakdowns. Comparisons across snapshots require equivalent scope.

## Operational boundaries

The default demo binds only to loopback. Hosted deployment requires TLS, per-user identity, gateway limits and backups. No proprietary ERP adapter, proprietary AI service, remote model inference, analytics beacon or paid API exists in the default path.
