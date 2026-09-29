"""Portable local release smoke checks; never publishes or modifies remote systems."""

import subprocess
import sys

for command in (
    [sys.executable, "-m", "ruff", "check", "src", "apps/api", "tests", "scripts"],
    [sys.executable, "-m", "pytest"],
    [
        sys.executable,
        "-m",
        "materialmaster.cli",
        "benchmark",
        "--count",
        "1200",
        "--output",
        "output/release-benchmark",
    ],
):
    subprocess.run(command, check=True)
print("Backend checks passed. Run frontend checks and the Docker smoke test from docs/release-checklist.md.")
