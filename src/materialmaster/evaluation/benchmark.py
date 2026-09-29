"""Reproducible synthetic ground-truth evaluation. No LLM is in the scoring path."""

import csv
import importlib.metadata
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from materialmaster.ai.embeddings import SentenceEmbedder
from materialmaster.domain.engine import analyze
from materialmaster.domain.generator import generate
from materialmaster.domain.validation import validate_rows


def metrics(predicted: set, truth: set, universe: int) -> dict:
    tp, fp, fn = len(predicted & truth), len(predicted - truth), len(truth - predicted)
    tn = max(0, universe - tp - fp - fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "accuracy": (tp + tn) / universe if universe else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def benchmark(count: int, seed: int, destination: Path, model_path: str | None = None) -> dict:
    started = time.perf_counter()
    raw, truth = generate(count, seed)
    generated = time.perf_counter()
    report = validate_rows(raw)
    validated = time.perf_counter()
    embedder = SentenceEmbedder(model_path) if model_path else None
    scan_start = time.perf_counter()
    findings, metadata = analyze(report.records, embedder=embedder)
    analyzed = time.perf_counter()
    duplicate_pred = {tuple(sorted(item.material_ids)) for item in findings if item.kind == "duplicate"}
    values = {
        "duplicate": metrics(
            duplicate_pred, {tuple(sorted(pair)) for pair in truth["duplicates"]}, count * (count - 1) // 2
        )
    }
    for kind in ("uom", "price", "purchasing", "lifecycle", "lead_time"):
        predicted = {mid for item in findings if item.kind == kind for mid in item.material_ids}
        values[kind] = metrics(predicted, set(truth[kind]), count)
    true_affected = {mid for pair in truth["duplicates"] for mid in pair} | set().union(
        *(set(truth[kind]) for kind in ("uom", "price", "purchasing", "lifecycle", "lead_time"))
    )
    pred_affected = {mid for item in findings for mid in item.material_ids}
    values["any_finding"] = metrics(pred_affected, true_affected, count)
    peak_memory = None
    try:
        import resource

        memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_memory = round(memory / (1024 * 1024 if sys.platform == "darwin" else 1024), 2)
    except ImportError:
        pass
    result = {
        "benchmark": "synthetic-injected-v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "count": count,
        "seed": seed,
        "findings": len(findings),
        "invalid_rows": report.invalid_count,
        "hardware": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
        },
        "dependencies": {
            name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn", "pydantic")
        },
        "model": {"llm": "disabled", "embedding": metadata["embedding_model"]},
        "timing_seconds": {
            "generation": round(generated - started, 4),
            "validation": round(validated - generated, 4),
            "model_loading": round(scan_start - validated, 4),
            "analysis": round(analyzed - scan_start, 4),
            "total": round(analyzed - started, 4),
        },
        "peak_process_rss_mib": peak_memory,
        "metrics": values,
        "engine": metadata,
        "review_throughput": {
            "human_reviews_per_hour": None,
            "note": "Not measured: requires timed human user study. Run scripts/review_throughput.py for database decision-write throughput, not human productivity.",
        },
        "limitations": [
            "Synthetic data uses known injection patterns; these scores are not estimates of real ERP performance.",
            "Duplicate FPR uses all possible record pairs, most blocked out before scoring; report precision/recall alongside it.",
            "Default generator identity anchors make duplicates easy; adversarial holdout cases are in unit tests.",
            "Peak RSS covers the whole benchmark process, including generation and libraries; database/UI are excluded.",
        ],
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    with (destination / "metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["category", *next(iter(values.values())).keys()])
        writer.writeheader()
        writer.writerows({"category": key, **value} for key, value in values.items())
    lines = [
        "# Measured synthetic benchmark",
        "",
        f"Run: {result['timestamp']}. Dataset: **{count:,}** records; seed **{seed}**.",
        "",
        f"Hardware: `{result['hardware']}`",
        "",
        f"Embedding: `{metadata['embedding_model']}`. LLM: disabled.",
        "",
        "| Category | Precision | Recall | Accuracy | False-positive rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, value in values.items():
        lines.append(
            "| "
            + category
            + " | "
            + " | ".join(
                f"{value[key]:.6f}" if value[key] is not None else "N/A"
                for key in ("precision", "recall", "accuracy", "false_positive_rate")
            )
            + " |"
        )
    lines += [
        "",
        f"Analysis: **{result['timing_seconds']['analysis']} s**. Full generation + validation + analysis: **{result['timing_seconds']['total']} s**. Peak process RSS: **{peak_memory} MiB**.",
        "",
        "Human review throughput: **not measured**.",
        "",
        "## Interpretation",
        "",
        *["- " + item for item in result["limitations"]],
    ]
    (destination / "summary.md").write_text("\n".join(lines) + "\n")
    return result
