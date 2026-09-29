# Complete source repository tree

Generated local data, installed dependencies, temporary databases and build outputs are intentionally ignored. The locally generated 100k data is in `data/generated/100k/`.

```text
materialmaster-ai/
├── .dockerignore
├── .env.example
├── .gitattributes
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── bug_report.md
│   ├── pull_request_template.md
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── NOTICE
├── README.md
├── SECURITY.md
├── apps/
│   ├── __init__.py
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── __init__.py
│   │   └── main.py
│   └── web/
│       ├── .npmrc
│       ├── Dockerfile
│       ├── eslint.config.js
│       ├── index.html
│       ├── nginx.conf
│       ├── package.json
│       ├── playwright.config.ts
│       ├── pnpm-lock.yaml
│       ├── pnpm-workspace.yaml
│       ├── public/
│       │   └── favicon.svg
│       ├── src/
│       │   ├── App.tsx
│       │   ├── LocalModelPicker.tsx
│       │   ├── api.test.ts
│       │   ├── api.ts
│       │   ├── main.tsx
│       │   ├── styles.css
│       │   └── types.ts
│       ├── tsconfig.json
│       └── vite.config.ts
├── data/
│   ├── sample/
│   │   ├── ground_truth.json
│   │   ├── import-template.csv
│   │   └── materials.jsonl
│   └── schemas/
│       └── material.schema.json
├── docker-compose.yml
├── docs/
│   ├── adr/
│   │   ├── 001-local-first-computation.md
│   │   ├── 002-portable-persistence.md
│   │   └── 003-bounded-embeddings.md
│   ├── ai-design.md
│   ├── api.md
│   ├── architecture.diagram.json
│   ├── architecture.md
│   ├── assets/
│   │   ├── dashboard.png
│   │   ├── evidence.png
│   │   ├── local-models.png
│   │   └── mobile.png
│   ├── benchmarks/
│   │   ├── 100k/
│   │   │   ├── metrics.csv
│   │   │   ├── result.json
│   │   │   └── summary.md
│   │   └── review-throughput.json
│   ├── data-model.md
│   ├── data-sources.md
│   ├── dependency-inventory.json
│   ├── development.md
│   ├── evaluation.md
│   ├── open-source-licenses.md
│   ├── release-checklist.md
│   ├── repository-tree.md
│   ├── roadmap.md
│   ├── screenshots.md
│   ├── security.md
│   └── verification.json
├── models/
│   └── .gitkeep
├── pyproject.toml
├── requirements-lock.txt
├── scripts/
│   ├── check_release.py
│   ├── dependency_inventory.py
│   ├── init-db.sh
│   └── review_throughput.py
├── src/
│   └── materialmaster/
│       ├── __init__.py
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── catalog.py
│       │   ├── embeddings.py
│       │   └── explanations.py
│       ├── cli.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── generator.py
│       │   ├── models.py
│       │   └── validation.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   └── benchmark.py
│       └── services/
│           ├── __init__.py
│           ├── storage.py
│           └── workflow.py
└── tests/
    ├── benchmarks/
    │   └── test_benchmark.py
    ├── conftest.py
    ├── e2e/
    │   ├── serve.py
    │   └── workflow.spec.ts
    ├── integration/
    │   ├── test_ai_selection.py
    │   └── test_api.py
    └── unit/
        ├── test_ai.py
        ├── test_cli.py
        ├── test_engine.py
        └── test_model_catalog.py
```
