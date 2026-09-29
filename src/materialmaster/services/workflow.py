import hashlib
import json
import time
import uuid
from collections import Counter, defaultdict

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from materialmaster.domain.engine import analyze
from materialmaster.domain.models import Material, ReviewCommand, utc_iso
from materialmaster.domain.validation import validate_rows
from materialmaster.services.storage import (
    Audit,
    Dataset,
    Idempotency,
    Issue,
    MaterialRow,
    RejectedRow,
    Review,
    Snapshot,
)


class Conflict(Exception):
    pass


def audit(session: Session, action: str, entity: str, data: dict, actor="local-steward", trace="cli"):
    session.add(Audit(action=action, actor=actor, entity_id=entity, data=data, trace_id=trace))


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def replay(session: Session, key: str, request: dict) -> dict | None:
    stored = session.get(Idempotency, key)
    if stored:
        if stored.request_hash != fingerprint(request):
            raise Conflict("Idempotency key was already used with a different request")
        return stored.response
    return None


def remember(session: Session, key: str, request: dict, response: dict):
    session.add(Idempotency(key=key, request_hash=fingerprint(request), response=response))


def ingest(session: Session, rows: list, name: str, actor="local-steward", trace="cli") -> dict:
    report = validate_rows(rows)
    dataset_id = str(uuid.uuid4())
    dataset = Dataset(
        id=dataset_id,
        name=name,
        total=report.total,
        valid=report.valid_count,
        invalid=report.invalid_count,
        meta={"schema_version": "1.0", "content_sha256": fingerprint(rows)},
    )
    session.add(dataset)
    session.flush()
    rejected_numbers = {row.row_number for row in report.rejected}
    raw_valid = [raw for index, raw in enumerate(rows, 1) if index not in rejected_numbers]
    session.add_all(
        [
            MaterialRow(
                dataset_id=dataset_id,
                id=row.material_id,
                source_system=row.source_system,
                material_group=row.material_group,
                description=row.description,
                raw=raw,
                data=row.model_dump(mode="json"),
            )
            for row, raw in zip(report.records, raw_valid, strict=True)
        ]
    )
    session.add_all(
        [
            RejectedRow(
                dataset_id=dataset_id, row_number=row.row_number, raw={"value": row.raw}, errors=row.errors
            )
            for row in report.rejected
        ]
    )
    result = {
        "dataset_id": dataset_id,
        "total": report.total,
        "valid_count": report.valid_count,
        "invalid_count": report.invalid_count,
        "validation_status": "partial" if report.invalid_count else "valid",
    }
    audit(session, "dataset.imported", dataset_id, result, actor, trace)
    session.flush()
    return result


def scan(session: Session, dataset_id: str, actor="local-steward", trace="cli", embedder=None) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise LookupError("Dataset not found")
    version = dataset.scan_version
    changed = session.execute(
        update(Dataset)
        .where(Dataset.id == dataset_id, Dataset.scan_version == version)
        .values(scan_version=version + 1, status="scanning")
    )
    if changed.rowcount != 1:
        raise Conflict("Another scan is in progress; reload and retry")
    started = time.perf_counter()
    records = [
        Material.model_validate(row.data)
        for row in session.scalars(select(MaterialRow).where(MaterialRow.dataset_id == dataset_id))
    ]
    findings, metadata = analyze(records, embedder=embedder)
    existing = {row.id: row for row in session.scalars(select(Issue).where(Issue.dataset_id == dataset_id))}
    for issue in existing.values():
        issue.active = 0
    for finding in findings:
        key = dataset_id + ":" + finding.finding_id
        payload = finding.model_dump(mode="json")
        if key in existing:
            existing[key].payload, existing[key].active = payload, 1
        else:
            session.add(
                Issue(
                    id=key,
                    dataset_id=dataset_id,
                    kind=finding.kind,
                    severity=finding.severity,
                    payload=payload,
                )
            )
    affected = {mid for item in findings for mid in item.material_ids}
    cohorts = defaultdict(lambda: {"total": 0, "affected": 0})
    sources = defaultdict(lambda: {"total": 0, "affected": 0})
    for row in records:
        for bucket, key in ((cohorts, row.material_group), (sources, row.source_system)):
            bucket[key]["total"] += 1
            bucket[key]["affected"] += int(row.material_id in affected)
    for bucket in (cohorts, sources):
        for value in bucket.values():
            value["quality_score"] = round(100 * (1 - value["affected"] / value["total"]), 2)
    metrics = {
        "total_materials": len(records),
        "affected_materials": len(affected),
        "quality_score": round(100 * (1 - len(affected) / len(records)), 2) if records else None,
        "findings": len(findings),
        "by_kind": dict(Counter(item.kind for item in findings)),
        "by_severity": dict(Counter(item.severity for item in findings)),
        "by_group": dict(cohorts),
        "by_source": dict(sources),
        "invalid_rows": dataset.invalid,
        "duration_seconds": round(time.perf_counter() - started, 4),
        **metadata,
    }
    dataset.status = "scanned"
    dataset.meta = {**dataset.meta, "latest_scan": metrics}
    session.add(Snapshot(dataset_id=dataset_id, metrics=metrics))
    audit(session, "dataset.scanned", dataset_id, metrics, actor, trace)
    session.flush()
    return metrics


def review(session: Session, issue_id: str, command: ReviewCommand, actor: str, trace: str) -> dict:
    issue = session.get(Issue, issue_id)
    if not issue:
        raise LookupError("Finding not found")
    if not issue.active:
        raise Conflict("Finding is no longer active")
    previous_status = issue.status
    changed = session.execute(
        update(Issue)
        .where(Issue.id == issue_id, Issue.version == command.expected_version)
        .values(status=command.decision, version=command.expected_version + 1)
    )
    if changed.rowcount != 1:
        raise Conflict("Finding was updated by another reviewer; reload before deciding")
    result = {
        "id": str(uuid.uuid4()),
        "finding_id": issue_id,
        "decision": command.decision,
        "version": command.expected_version + 1,
        "actor": actor,
        "reason": command.reason,
    }
    session.add(Review(**{key: value for key, value in result.items() if key != "version"}))
    audit(session, "finding.reviewed", issue_id, {**result, "previous_status": previous_status}, actor, trace)
    session.flush()
    return result


def feedback_summary(session: Session) -> dict:
    # Latest decision per pair only: repeat reviews cannot inflate the calibration sample.
    rows = list(
        session.scalars(
            select(Issue).where(Issue.kind == "duplicate", Issue.status.in_(["accepted", "rejected"]))
        )
    )
    counts = Counter(row.status for row in rows)
    total = sum(counts.values())
    return {
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "reviewed_pairs": total,
        "posterior_acceptance": round((counts["accepted"] + 1) / (total + 2), 4),
        "prior": "Beta(1,1)",
        "effect": "Empirical confidence by method, only for review prioritization; no suppression or merge",
    }


def learned_priority(session: Session) -> dict[str, float]:
    rows = session.execute(
        select(Issue.payload, Issue.status).where(
            Issue.kind == "duplicate", Issue.status.in_(["accepted", "rejected"])
        )
    ).all()
    groups = defaultdict(Counter)
    for payload, status in rows:
        groups[payload["method"]][status] += 1
    return {
        method: (counts["accepted"] + 1) / (sum(counts.values()) + 2) for method, counts in groups.items()
    }


def dashboard(session: Session, dataset_id: str) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise LookupError("Dataset not found")
    counts = dict(
        session.execute(
            select(Issue.status, func.count())
            .where(Issue.dataset_id == dataset_id, Issue.active == 1)
            .group_by(Issue.status)
        ).all()
    )
    history = list(session.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(30)))
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        "status": dataset.status,
        "metrics": dataset.meta.get("latest_scan", {}),
        "review_counts": counts,
        "feedback": feedback_summary(session),
        "history": [
            {"at": utc_iso(item.created_at), "dataset_id": item.dataset_id, **item.metrics}
            for item in reversed(history)
        ],
    }
