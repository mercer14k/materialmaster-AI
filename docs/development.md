# Native development

Use Python 3.12, Node 24 and pnpm 11.25.0 for the tested baseline. No global database server or AI runtime is necessary. `.env` is read by Docker Compose; native processes use their environment variables directly.

## macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2'
pip install -c requirements-lock.txt -e '.[dev]'
uvicorn apps.api.main:app --host 127.0.0.1 --port 8120
```

Second terminal:

```bash
cd apps/web
npm install -g pnpm@11.25.0
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:5178`. For native Ollama, `LLM_URL` is `http://localhost:11434`, not the Compose service hostname. Native SQLite writes `materialmaster.db` in the repository root, which is ignored by Git. Stop the API before replacing a development DB; preserve real imported data.

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade 'pip>=26.2'
pip install -c requirements-lock.txt -e '.[dev]'
uvicorn apps.api.main:app --host 127.0.0.1 --port 8120
```

In another PowerShell terminal:

```powershell
cd apps/web
npm install -g pnpm@11.25.0
pnpm install --frozen-lockfile
pnpm dev
```

If script activation is restricted, use `.\.venv\Scripts\python.exe` and `.\.venv\Scripts\uvicorn.exe` directly. No system execution-policy change is required. Linux Docker Engine inside WSL2 is an open-source Compose path on Windows; native mode avoids a VM entirely.

## Tests and screenshots

Activate the Python environment before starting Playwright so `python` refers to the installed backend. Browser tests launch isolated servers on 8121 and 5297 and use a temporary database, preserving the normal demo.

```bash
ruff check src apps/api tests scripts
pytest --cov=materialmaster --cov=apps.api
cd apps/web
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

On Windows, `python` resolves through the activated virtual environment. On Linux CI, Playwright's `install --with-deps chromium` installs OS prerequisites. Browser binaries are test tooling and are not included in the runtime image.

## Dependency and schema changes

Keep `requirements-lock.txt` and `pnpm-lock.yaml` reviewed with package updates. The Python file is a constraints snapshot containing development packages; Docker installs only the base project's declared dependencies under those constraints. After changing Pydantic fields regenerate `data/schemas/material.schema.json` and update the dictionary. This version supports fresh schema creation, not automatic schema upgrades; preserve data and introduce a migration before deploying a changed schema over an existing database.

## Troubleshooting

- Port already occupied: set `API_PROXY` and use a different `uvicorn --port`; Vite accepts `pnpm dev --port <number>`. Do not terminate unrelated services.
- Model unavailable: deterministic workflows still work. Explanation requests return structured abstention and telemetry.
- Import too large: use the CLI. Reported 100k runtime measures analysis, not database persistence.
- Read-only token cannot review: expected; use a steward token configured on the server.
- Price score absent: cohorts need eight valid active records with comparable group/currency/base UOM. Missing evidence is not replaced with invented comparisons.
- Compose password changes after first run: initialized DB roles retain their old passwords. Rotate credentials through controlled database administration, not volume deletion.
