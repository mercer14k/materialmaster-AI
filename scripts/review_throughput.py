"""Measure actual committed decision-write throughput, explicitly not human productivity."""

import json
import platform
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from materialmaster.domain.generator import generate
from materialmaster.domain.models import ReviewCommand
from materialmaster.services.storage import Base, Issue, database
from materialmaster.services.workflow import ingest, review, scan

with tempfile.TemporaryDirectory() as directory:
    engine, sessions = database("sqlite:///" + str(Path(directory) / "throughput.db"))
    Base.metadata.create_all(engine)
    with sessions.begin() as session:
        dataset = ingest(session, generate(4000)[0], "Throughput fixture")
        scan(session, dataset["dataset_id"])
    with sessions() as session:
        ids = list(session.scalars(select(Issue.id).limit(500)))
    started = time.perf_counter()
    for issue_id in ids:
        with sessions.begin() as session:
            review(
                session,
                issue_id,
                ReviewCommand(decision="accepted", reason="Synthetic throughput fixture", expected_version=0),
                "benchmark",
                uuid.uuid4().hex,
            )
    elapsed = time.perf_counter() - started
    result = {
        "measurement": "single-client SQLAlchemy + SQLite WAL, one transaction per decision, no HTTP",
        "decisions": len(ids),
        "seconds": elapsed,
        "committed_decisions_per_second": len(ids) / elapsed,
        "human_reviews_per_hour": None,
        "hardware": platform.platform(),
        "python": platform.python_version(),
    }
    destination = Path("docs/benchmarks/review-throughput.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    engine.dispose()
