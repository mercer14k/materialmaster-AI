# Open-source dependency and model licenses

MaterialMaster source and synthetic fixtures: **Apache-2.0**, see [LICENSE](../LICENSE). No proprietary cloud AI or paid API is required for core features. Locally served fonts and code avoid external browser trackers/CDNs.

This is a practical inventory, not legal advice. Dependencies and optional models retain their original licenses. Check the exact distributed artifacts and notices when redistributing binaries or weights. `requirements-lock.txt` and `apps/web/pnpm-lock.yaml` record package versions; [dependency-inventory.json](dependency-inventory.json) captures installed Python/frontend metadata, including transitive packages.

| Material dependency | License | Purpose / obligations |
|---|---|---|
| Python | PSF-2.0 | Backend interpreter; preserve applicable notices |
| FastAPI | MIT | HTTP API |
| Starlette | BSD-3-Clause | ASGI framework |
| Pydantic / pydantic-core | MIT | Contracts and structured-output validation |
| SQLAlchemy | MIT | Parameterized persistence |
| Psycopg / psycopg-binary | LGPL-3.0 | PostgreSQL driver; preserve LGPL notices and applicable replacement/relinking rights when distributing it |
| libpq / PostgreSQL 17 | PostgreSQL License | Database/client; separate upstream notices |
| SQLite | Public domain | Native demo database |
| NumPy / SciPy / scikit-learn | BSD-3-Clause | Vectors, numerical operations and local lexical embeddings; wheels may bundle additional BLAS/runtime licenses |
| HTTPX | BSD-3-Clause | Local runtime HTTP client |
| Uvicorn | BSD-3-Clause | ASGI server |
| python-multipart | Apache-2.0 | Bounded multipart parsing |
| sentence-transformers (optional) | Apache-2.0 | Semantic encoder adapter |
| PyTorch (optional/transitive) | BSD-3-Clause | Encoder execution; inspect accelerator and wheel-specific notices |
| Transformers / huggingface-hub (optional) | Apache-2.0 | Model loading; weights licensed separately |
| all-MiniLM-L6-v2 weights (optional) | Apache-2.0 | [Model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2); download separately and pin revision |
| Qwen2.5-7B-Instruct weights (optional) | Apache-2.0 | [Model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct); no inference API required |
| Ollama (optional local runtime) | MIT | [Source license](https://github.com/ollama/ollama/blob/main/LICENSE); local profile only, cloud disabled |
| llama.cpp (optional local runtime) | MIT | [Source license](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE); no weights bundled |
| React / React DOM | MIT | Interface |
| Vite / pnpm / Vitest | MIT | Frontend tooling |
| TypeScript | Apache-2.0 | Type checking |
| Radix UI Dialog | MIT | Focus management, modal/drawer accessibility |
| Lucide | ISC | Interface icons |
| DM Sans / IBM Plex Mono font files | SIL OFL-1.1 | Bundled fonts; font licenses remain applicable |
| NGINX / unprivileged container config | BSD-2-Clause / Apache-2.0 | Static serving and API proxy; base-image packages have their own licenses |
| pytest / pytest-cov / Ruff / ESLint | MIT | Testing and linting |
| Playwright | Apache-2.0 | Browser verification; Chromium has its own bundled notices |
| axe-core / @axe-core/playwright | MPL-2.0 | Automated accessibility checks, development only |
| Prettier | MIT | Source formatting, development only |
| pip-audit | Apache-2.0 | Python dependency advisory checks |
| Docker Engine (Moby) / Compose / Colima | Apache-2.0 / Apache-2.0 / MIT | Open-source local execution options; Docker Desktop is not required |
| GitHub Actions runner/actions | MIT, per individual action | CI recipes can also be reproduced locally; hosted GitHub itself is optional infrastructure |

The app does not imply that every model carrying a family name has the same license. Qwen2.5 7B is a license example, not a selected or default model. Users explicitly choose their installed model and must check the exact artifact’s terms. API compatibility with an OpenAI-style endpoint does not require OpenAI software, accounts or services.

Regenerate installed metadata after changing dependencies:

```bash
python scripts/dependency_inventory.py
```

Metadata fields are not a substitute for upstream LICENSE/NOTICE files. Optional AI dependencies absent from the default environment are identified above; install that extra and regenerate the inventory before distributing an AI-enabled environment.
