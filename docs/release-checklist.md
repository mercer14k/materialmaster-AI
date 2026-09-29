# Release checklist and verification status

This document distinguishes supplied code from executed verification. It is not a declaration that an unrun CI job passed.

## Verified locally

- [x] Deterministic generator writes 1,200-row sample and 100,000-row performance dataset, with separate ground truth.
- [x] Backend unit/integration tests run against a real SQLite database.
- [x] Computational core includes UOM/price/duplicate regression and missing-evidence tests.
- [x] API rejects malformed envelopes, preserves invalid rows, checks authorization, handles idempotency and stale review versions.
- [x] No model is preselected; missing API selection is rejected; core no-model explanations abstain and failing model fixtures do not mutate deterministic findings.
- [x] Installed Ollama models discovered on the authoring device; preview connected with no model selected. No live inference was requested.
- [x] Workplace CSV template validates; source and field-mapping guide documents export-based ingestion.
- [x] Frontend lint, TypeScript, unit tests and production build run.
- [x] Actual 100k benchmark JSON, CSV and Markdown recorded with hardware/configuration.
- [x] Actual decision-write throughput measured; no human-productivity claim.
- [x] Mermaid diagram passes static skill validation (not a GitHub-render proof).
- [x] Compose, CI and pnpm YAML parse successfully (syntax only, not container execution).
- [x] README, data dictionary, architecture, AI design, threat model, ADRs and license inventory supplied.

## Final local gates

Local run: 89 backend tests, 3 frontend unit tests, 5 browser workflow tests; dashboard and local-model dialog WCAG 2 A/AA and WCAG 2.1 AA checks report no axe violations. Backend coverage is 89.47% (computational engine 100%). Automated accessibility checks do not replace assistive-technology user testing.

- [x] Browser E2E workflow and mobile no-overflow assertion pass on the final source.
- [x] Final dependency audit has no known findings; regenerate inventory after updates.
- [x] Final screenshots reflect the checked source.
- [x] Publishable files were inspected; credential-pattern scan found no matches, and local databases, .env, model weights and generated 100k data are ignored.

## Requires external runtime or publication

- [ ] On a Docker-capable host: `cp .env.example .env` then `docker compose up --build --wait`.
- [ ] Confirm `http://localhost:3000`, `http://localhost:8120/ready`, database persistence across restart and SELECT-only read-role permissions.
- [ ] Execute the PostgreSQL integration suite using a disposable database via `TEST_DATABASE_URL` (the test fixture clears that test schema).
- [ ] Optional: explicitly select approved local model files; run semantic and Ollama/llama.cpp live comparisons and retain model revision/runtime metadata.
- [ ] Create the public GitHub remote, replace the clone placeholder and push the local repository.
- [ ] Confirm all four GitHub Actions jobs pass on that remote. No remote CI run has been claimed locally.
- [ ] Enable private vulnerability reporting, configure maintainer contact and review branch protections.
- [ ] Review dependency/license notices and container image digests before a tagged release.

The authoring host did not have Docker/Compose or a PostgreSQL server installed. Those gates remain unverified. The native demo is independently runnable and does not require them.
