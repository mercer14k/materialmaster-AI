import json
import subprocess
import sys

from materialmaster.domain.generator import generate


def test_cli_generate_validate_and_import(tmp_path):
    source = tmp_path / "data"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "materialmaster.cli",
            "generate",
            "--count",
            "80",
            "--seed",
            "7",
            "--output",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "materialmaster.cli",
            "validate",
            str(source / "materials.jsonl"),
            "--analyze",
            "--output",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(report.read_text())["findings"]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "materialmaster.cli",
            "import",
            str(source / "materials.jsonl"),
            "--database-url",
            "sqlite:///" + str(tmp_path / "cli.db"),
            "--scan",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["scan"]["total_materials"] == 80


def test_cli_invalid_rows_nonzero_and_visible(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps([generate(20)[0][0], {"invalid": "preserved"}]))
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-m", "materialmaster.cli", "validate", str(source), "--output", str(report)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert json.loads(report.read_text())["rejected"][0]["raw"] == {"invalid": "preserved"}


def test_cli_malformed_file_reports_error(tmp_path):
    source = tmp_path / "broken.json"
    source.write_text("not-json")
    result = subprocess.run(
        [sys.executable, "-m", "materialmaster.cli", "validate", str(source)], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "Cannot read input" in result.stderr
