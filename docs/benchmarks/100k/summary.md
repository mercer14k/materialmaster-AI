# Measured synthetic benchmark

Run: 2026-09-28T01:35:30.871181+00:00. Dataset: **100,000** records; seed **42**.

Hardware: `{'os': 'macOS-26.6.2-arm64-arm-64bit', 'machine': 'arm64', 'processor': 'arm', 'logical_cpus': 10, 'python': '3.12.14'}`

Embedding: `sklearn-hashing-char-3-5/512-v1`. LLM: disabled.

| Category | Precision | Recall | Accuracy | False-positive rate |
|---|---:|---:|---:|---:|
| duplicate | 1.000000 | 0.777600 | 1.000000 | 0.000000 |
| uom | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| price | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| purchasing | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| lifecycle | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| lead_time | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| any_finding | 1.000000 | 0.958300 | 0.991660 | 0.000000 |

Analysis: **1.2403 s**. Full generation + validation + analysis: **1.8705 s**. Peak process RSS: **768.31 MiB**.

Human review throughput: **not measured**.

## Interpretation

- Synthetic data uses known injection patterns; these scores are not estimates of real ERP performance.
- Duplicate FPR uses all possible record pairs, most blocked out before scoring; report precision/recall alongside it.
- Default generator identity anchors make duplicates easy; adversarial holdout cases are in unit tests.
- Peak RSS covers the whole benchmark process, including generation and libraries; database/UI are excluded.
