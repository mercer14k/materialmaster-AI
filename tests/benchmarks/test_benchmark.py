import json

from materialmaster.evaluation.benchmark import benchmark, metrics


def test_metrics_include_false_positives_and_missing_predictions():
    result = metrics({"a", "b"}, {"a", "c"}, 10)
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["false_positive_rate"] == 0.125
    assert metrics(set(), set(), 10)["precision"] is None


def test_reproducible_machine_readable_outputs(tmp_path):
    result = benchmark(240, 42, tmp_path)
    assert result["metrics"]["duplicate"]["precision"] == 1
    assert json.loads((tmp_path / "result.json").read_text())["count"] == 240
    assert (tmp_path / "metrics.csv").read_text().startswith("category,tp,fp")
    assert "Human review throughput: **not measured**" in (tmp_path / "summary.md").read_text()
