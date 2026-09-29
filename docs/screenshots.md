# Reproduce the actual product screenshots

The committed screenshots are browser captures of the running app using the 1,200-record synthetic dataset, seed 42. They are not generated UI mockups. Runtime timestamps and scan durations can differ.

```bash
# From the repository root with the Python environment active:
cd apps/web
pnpm install --frozen-lockfile
pnpm exec playwright install chromium
pnpm test:e2e
```

The suite starts an isolated temporary database/API on 8121 and frontend on 5297, then writes:

- `docs/assets/dashboard.png`: desktop overview at 1512px, full page.
- `docs/assets/evidence.png`: duplicate evidence drawer with an explicitly unselected local model (1512 × 1500 viewport).
- `docs/assets/local-models.png`: actual local-model settings panel with no configured runtime or default model.
- `docs/assets/mobile.png`: 390px responsive overview.

The tests also verify a review decision and reason, persisted history, CSV download, audit event, material search, import quarantine and a subsequent scan. If capture fails, inspect `apps/web/test-results` and the Playwright trace; do not replace failed captures with an invented screenshot.

For a manual capture: start the native app, open `http://localhost:5178`, select the seeded demo and wait for computed metrics. Use a 1512px viewport. For the evidence screenshot open Review queue → Potential duplicate → any finding. The drawer distinguishes raw records, detection evidence and generated narrative.
