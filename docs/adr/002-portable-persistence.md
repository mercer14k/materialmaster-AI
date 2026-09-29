# ADR 002 — PostgreSQL deployment, SQLite native development

Status: accepted.

**Context:** The demo must run through Compose but also be accessible to contributors without a database service.

**Decision:** Use SQLAlchemy services with PostgreSQL in Compose and SQLite WAL for native work. Use a non-superuser app role and a SELECT-only read role in Compose. Establish idempotency and audit records within transaction boundaries. Version 0.1 creates only fresh schemas.

**Consequences:** The same integration suite can target both backends via `TEST_DATABASE_URL`. SQLite contention and in-memory scans are explicit limitations. Production migration and concurrency infrastructure are future work. `create_all` is not represented as a migration engine.
