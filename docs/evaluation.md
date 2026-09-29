# Reproducible evaluation

Run `materialmaster benchmark --count 100000 --seed 42 --output output/benchmark` in an isolated process. `result.json`, `metrics.csv` and `summary.md` are generated from the actual engine. Hardware, Python/dependency versions, seed, model configuration and algorithm parameters are embedded in the JSON.

## Scoring

- Duplicate detection is **pairwise**: predictions are unordered material-ID pairs, compared with all seeded duplicate pairs. TP, FP and FN are explicit. Recall includes candidates missed during blocking or below the similarity threshold.
- UOM, price, purchasing, lifecycle and lead-time metrics are **per material ID**. Precision = TP/(TP+FP); recall = TP/(TP+FN); accuracy = (TP+TN)/N; FPR = FP/(FP+TN).
- `any_finding` compares distinct affected material IDs, avoiding double-counting records with multiple findings.
- Undefined precision/recall is emitted as `null`, not a misleading perfect value.
- Duplicate pair FPR uses N(N−1)/2 as the universe. Because most pairs are trivially negative, do not use pairwise accuracy or FPR alone to claim duplicate quality.

## Actual baseline

The [committed 100k result](benchmarks/100k/result.json) used seed 42, 512-dimension character hashing, cosine threshold 0.80 and no LLM. It produced 18,332 findings and recovered 5,832 of 7,500 duplicate pairs, with no false-positive pairs in this synthetic fixture. The 1,668 missed pairs predominantly involve abbreviation changes in fastener descriptions without a manufacturer part-number anchor.

The perfect UOM/price injection scores reflect deliberate, easily separable anomalies. They do not predict field accuracy. The generator and detector are developed together; this is a reproducibility and regression baseline, not independent scientific validation. Unit fixtures separately cover wrong engineering sizes, conflicting part numbers, currency/UOM cohort boundaries, missing peers and oversized blocks.

## Performance measurement

`timing_seconds.analysis` covers computational analysis only. `total` includes generation and schema validation; optional model loading is separate. Peak process RSS is the operating system's maximum resident set for the entire process, not an incremental engine allocation. On Windows, RSS is `null` where the `resource` interface is unavailable. Memory is not an estimate of browser or PostgreSQL usage.

For repeatability, record CPU power mode, other workload and thread environment. Run several processes and report all runs or their distribution; never overwrite evidence to select a favorable headline. The committed result is one measured run, not a latency SLA.

## Review throughput

`python scripts/review_throughput.py` measures 500 individual committed review transactions against an isolated temporary SQLite WAL database. The recorded 2,908.46 decisions/second is database/service write throughput on the authoring host, not API concurrency or human productivity. Human reviews/hour is intentionally `null`.

A valid human study should measure time from first evidence view to committed decision, correct vs incorrect adjudications, uncertainty and reopening rate, with multiple stewards and a held-out labeled corpus. A speed claim without correctness would reward rushed reviewing.

## Next evaluation set

Add independently authored positive/negative pairs, multilingual description variants, UOM aliases, legitimate price tiers and currency changes, heterogeneous groups, missing manufacturer IDs and corrections across snapshots. Hold the test set apart from threshold calibration. Benchmark the same blocks with lexical and semantic encoders and publish both recall and compute cost.
