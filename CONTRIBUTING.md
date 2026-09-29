# Contributing

Start with a real material-data failure and a small synthetic example. Explain the expected operational outcome, current behavior and evidence. Never submit customer ERP exports, vendor contracts, supplier identities, credentials or copyrighted model weights.

## Development loop

1. Follow [native development](docs/development.md), create a branch and keep changes focused.
2. Add a regression test for a new computational rule or bug. Include boundary and missing-evidence cases.
3. Keep numerical and workflow logic in `src/materialmaster`, not HTTP handlers or React components.
4. Run backend lint/tests and relevant frontend/browser checks. Include measured results, not guessed performance.
5. Update schemas/dictionary and an ADR when the data contract or architectural tradeoff changes.
6. Check licenses and vulnerabilities for added dependencies. Core features must remain runnable without paid APIs or proprietary AI services.

## Review principles

Every finding needs supporting evidence and a clear human action. Similarity scores must not be marketed as truth probabilities. Model text must not calculate KPI values or own state transitions. New state-changing endpoints need typed inputs, server permissions, idempotency, optimistic version handling where applicable, and audit history.

All contributors retain copyright to their contributions. By contributing you agree to license your contribution under the project's Apache-2.0 license. No CLA or invented maintainer identity is required by this repository.

Please follow [the Code of Conduct](CODE_OF_CONDUCT.md). Report security issues through [SECURITY.md](SECURITY.md), not a public issue containing private data.
