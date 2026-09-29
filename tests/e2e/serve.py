"""Isolated browser-test server; never points at the normal workspace database."""

import os
import sys
import tempfile
from pathlib import Path

import uvicorn

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix="materialmaster-e2e-") as directory:
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(directory) / "browser.db")
    os.environ["AUTH_MODE"] = "demo"
    os.environ["LLM_RUNTIME"] = "disabled"
    os.environ["SEED_DEMO"] = "true"
    uvicorn.run("apps.api.main:app", host="127.0.0.1", port=8121, log_level="warning")
