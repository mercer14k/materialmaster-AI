import csv
import io
import json
import logging
import os
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from materialmaster.ai.catalog import (
    ModelCatalog,
    ModelSelection,
    ModelUnavailable,
    discover_models,
    verify_selection,
)
from materialmaster.ai.embeddings import SentenceEmbedder
from materialmaster.ai.explanations import LlamaCppRuntime, OllamaRuntime, explain
from materialmaster.domain.generator import generate
from materialmaster.domain.models import Finding, Page, ReviewCommand, utc_iso
from materialmaster.domain.validation import parse_upload, validate_rows
from materialmaster.services.storage import (
    Audit,
    Base,
    Dataset,
    Issue,
    MaterialRow,
    ModelEvent,
    RejectedRow,
    Review,
    database,
)
from materialmaster.services.workflow import (
    Conflict,
    dashboard,
    ingest,
    learned_priority,
    remember,
    replay,
    review,
    scan,
)

logger = logging.getLogger("materialmaster")
logging.basicConfig(level=logging.INFO, format="%(message)s")
MAX_UPLOAD = 20 * 1024 * 1024


class BulkRequest(BaseModel):
    records: list[Any] = Field(max_length=10000)


class MutationResult(BaseModel):
    result: dict[str, Any]


def create_app(database_url: str | None = None, seed_demo: bool | None = None) -> FastAPI:
    engine, sessions = database(database_url)
    read_engine, read_sessions = (
        database(os.getenv("READ_DATABASE_URL"))
        if os.getenv("READ_DATABASE_URL") and database_url is None
        else (engine, sessions)
    )
    seed_demo = os.getenv("SEED_DEMO", "true").lower() == "true" if seed_demo is None else seed_demo

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with sessions.begin() as session:
            if seed_demo and not session.scalar(select(func.count()).select_from(Dataset)):
                rows, _ = generate(1200, 42)
                result = ingest(session, rows, "Manufacturing demo · seed 42", actor="system")
                scan(session, result["dataset_id"], actor="system")
        yield
        engine.dispose()
        if read_engine is not engine:
            read_engine.dispose()

    app = FastAPI(
        title="MaterialMaster AI",
        version="0.1.0",
        description="Evidence-first material master quality. Local AI is optional. Read endpoints are separate from auditable commands.",
        lifespan=lifespan,
    )
    app.state.sessions = sessions
    app.state.engine = engine

    @app.middleware("http")
    async def observe(request, call_next):
        start = time.perf_counter()
        supplied = request.headers.get("x-trace-id", "")
        request.state.trace_id = (
            supplied if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", supplied) else uuid.uuid4().hex
        )
        # Limit every request body, including chunked transfers, before parsing it.
        if request.method in {"POST", "PUT", "PATCH"}:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > MAX_UPLOAD + 65536):
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "body_too_large",
                            "message": "Maximum request size is 20 MiB",
                            "trace_id": request.state.trace_id,
                        }
                    },
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_UPLOAD + 65536:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "body_too_large",
                                "message": "Maximum request size is 20 MiB",
                                "trace_id": request.state.trace_id,
                            }
                        },
                    )
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "event": "http.request",
                    "trace_id": request.state.trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": f"http_{error.status_code}",
                    "message": str(error.detail),
                    "trace_id": getattr(request.state, "trace_id", "unknown"),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "schema_validation",
                    "message": "Request did not match the API schema",
                    "details": [
                        {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                        for item in error.errors()
                    ],
                    "trace_id": request.state.trace_id,
                }
            },
        )

    @app.exception_handler(Conflict)
    @app.exception_handler(IntegrityError)
    async def conflict_error(request, error):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "conflict",
                    "message": str(error)
                    if isinstance(error, Conflict)
                    else "Concurrent write or repeated key; reload and retry",
                    "trace_id": request.state.trace_id,
                }
            },
        )

    @app.exception_handler(LookupError)
    async def missing_error(request, error):
        return JSONResponse(
            status_code=404,
            content={
                "error": {"code": "not_found", "message": str(error), "trace_id": request.state.trace_id}
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(request, error):
        logger.error(
            json.dumps(
                {
                    "event": "http.error",
                    "trace_id": request.state.trace_id,
                    "error_type": type(error).__name__,
                }
            )
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred; use the trace ID for diagnosis",
                    "trace_id": request.state.trace_id,
                }
            },
        )

    def session_dependency():
        with sessions.begin() as session:
            yield session

    DB = Annotated[Session, Depends(session_dependency, scope="function")]

    def read_dependency():
        with read_sessions.begin() as session:
            yield session

    ReadDB = Annotated[Session, Depends(read_dependency, scope="function")]

    def reader(request: Request, authorization: str = Header(default="")):
        if os.getenv("AUTH_MODE", "demo") == "demo":
            return "demo-steward"
        if os.getenv("AUTH_MODE") != "token":
            raise HTTPException(503, "Invalid server authentication configuration")
        token = authorization.removeprefix("Bearer ")
        write_token, read_token = os.getenv("WRITE_TOKEN", ""), os.getenv("READ_TOKEN", "")
        if write_token and secrets.compare_digest(token, write_token):
            return "token-steward"
        if read_token and secrets.compare_digest(token, read_token):
            return "token-reader"
        raise HTTPException(401, "Valid bearer token required")

    def writer(actor: str = Depends(reader)):
        if actor == "token-reader":
            raise HTTPException(403, "Steward permission required")
        return actor

    def idem_key(value: str = Header(alias="Idempotency-Key")):
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{8,100}", value):
            raise HTTPException(422, "Idempotency-Key must be 8–100 safe characters")
        return value

    def latest_id(session: Session, dataset_id: str | None):
        if dataset_id:
            if not session.get(Dataset, dataset_id):
                raise LookupError("Dataset not found")
            return dataset_id
        value = session.scalar(select(Dataset.id).order_by(Dataset.created_at.desc()).limit(1))
        if not value:
            raise LookupError("Import a dataset to get started")
        return value

    @app.get("/health", tags=["operations"])
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/ready", tags=["operations"])
    def ready(session: ReadDB):
        session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}

    @app.get("/api/v1/config", dependencies=[Depends(reader)], tags=["read"])
    def config():
        return {
            "auth_mode": os.getenv("AUTH_MODE", "demo"),
            "llm_runtime": os.getenv("LLM_RUNTIME", "disabled"),
            "embedding_mode": "semantic" if os.getenv("EMBEDDING_MODEL_PATH") else "lexical",
            "version": "0.1.0",
            "max_upload_mb": 20,
        }

    @app.get("/api/v1/ai/models", response_model=ModelCatalog, dependencies=[Depends(reader)], tags=["read"])
    def local_models():
        return discover_models(
            os.getenv("LLM_RUNTIME", "disabled"), os.getenv("LLM_URL", "http://localhost:11434")
        )

    @app.get("/api/v1/datasets", dependencies=[Depends(reader)], response_model=Page, tags=["read"])
    def datasets(session: ReadDB, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        rows = list(
            session.scalars(select(Dataset).order_by(Dataset.created_at.desc()).offset(offset).limit(limit))
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "total": row.total,
                    "valid": row.valid,
                    "invalid": row.invalid,
                    "status": row.status,
                    "created_at": utc_iso(row.created_at),
                }
                for row in rows
            ],
            "total": session.scalar(select(func.count()).select_from(Dataset)),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/overview", dependencies=[Depends(reader)], tags=["read"])
    def overview(session: ReadDB, dataset_id: str | None = None):
        return dashboard(session, latest_id(session, dataset_id))

    @app.get("/api/v1/materials", dependencies=[Depends(reader)], response_model=Page, tags=["read"])
    def materials(
        session: ReadDB,
        dataset_id: str | None = None,
        search: str = Query("", max_length=200),
        group: str | None = None,
        source: str | None = None,
        limit: int = Query(30, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        query = select(MaterialRow).where(MaterialRow.dataset_id == latest_id(session, dataset_id))
        if search:
            query = query.where(
                or_(
                    MaterialRow.description.icontains(search, autoescape=True),
                    MaterialRow.id.icontains(search, autoescape=True),
                )
            )
        if group:
            query = query.where(MaterialRow.material_group == group)
        if source:
            query = query.where(MaterialRow.source_system == source)
        count = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.scalars(query.order_by(MaterialRow.id).offset(offset).limit(limit))
        return {
            "items": [
                {
                    **row.data,
                    "dataset_id": row.dataset_id,
                    "ingested_at": utc_iso(row.ingested_at),
                    "validation_status": row.validation_status,
                }
                for row in rows
            ],
            "total": count,
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/findings", dependencies=[Depends(reader)], response_model=Page, tags=["read"])
    def findings(
        session: ReadDB,
        dataset_id: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        search: str = Query("", max_length=200),
        limit: int = Query(30, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        query = select(Issue).where(Issue.dataset_id == latest_id(session, dataset_id), Issue.active == 1)
        if kind:
            query = query.where(Issue.kind == kind)
        if status:
            query = query.where(Issue.status == status)
        rows = list(session.scalars(query))
        if search:
            rows = [row for row in rows if search.lower() in json.dumps(row.payload).lower()]
        priorities = learned_priority(session)
        severity = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        rows.sort(
            key=lambda row: (
                severity[row.severity],
                -(priorities.get(row.payload["method"], 0.5) if row.kind == "duplicate" else 0.5),
                row.id,
            )
        )
        return {
            "items": [
                {
                    **row.payload,
                    "id": row.id,
                    "status": row.status,
                    "version": row.version,
                    "learned_priority": round(priorities.get(row.payload["method"], 0.5), 4)
                    if row.kind == "duplicate"
                    else 0.5,
                }
                for row in rows[offset : offset + limit]
            ],
            "total": len(rows),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/findings/{issue_id}", dependencies=[Depends(reader)], tags=["read"])
    def finding_detail(issue_id: str, session: ReadDB):
        issue = session.get(Issue, issue_id)
        if not issue:
            raise LookupError("Finding not found")
        records = session.scalars(
            select(MaterialRow).where(
                MaterialRow.dataset_id == issue.dataset_id, MaterialRow.id.in_(issue.payload["material_ids"])
            )
        )
        reviews = session.scalars(
            select(Review).where(Review.finding_id == issue_id).order_by(Review.created_at.desc())
        )
        return {
            **issue.payload,
            "id": issue.id,
            "status": issue.status,
            "version": issue.version,
            "records": [
                {
                    "raw": row.raw,
                    "normalized": row.data,
                    "dataset_id": row.dataset_id,
                    "ingested_at": utc_iso(row.ingested_at),
                    "validation_status": row.validation_status,
                }
                for row in records
            ],
            "reviews": [
                {
                    "decision": row.decision,
                    "reason": row.reason,
                    "actor": row.actor,
                    "at": utc_iso(row.created_at),
                }
                for row in reviews
            ],
        }

    @app.get(
        "/api/v1/datasets/{dataset_id}/validation",
        dependencies=[Depends(reader)],
        response_model=Page,
        tags=["read"],
    )
    def validation_report(
        dataset_id: str, session: ReadDB, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0)
    ):
        latest_id(session, dataset_id)
        query = select(RejectedRow).where(RejectedRow.dataset_id == dataset_id)
        rows = session.scalars(query.order_by(RejectedRow.row_number).offset(offset).limit(limit))
        return {
            "items": [
                {
                    "row_number": row.row_number,
                    "raw": row.raw,
                    "errors": row.errors,
                    "validation_status": "invalid",
                    "ingested_at": utc_iso(row.ingested_at),
                }
                for row in rows
            ],
            "total": session.scalar(select(func.count()).select_from(query.subquery())),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/audit", dependencies=[Depends(reader)], response_model=Page, tags=["read"])
    def audit_events(session: ReadDB, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0)):
        rows = session.scalars(select(Audit).order_by(Audit.id.desc()).offset(offset).limit(limit))
        return {
            "items": [
                {
                    "id": row.id,
                    "action": row.action,
                    "actor": row.actor,
                    "entity_id": row.entity_id,
                    "trace_id": row.trace_id,
                    "data": row.data,
                    "at": utc_iso(row.created_at),
                }
                for row in rows
            ],
            "total": session.scalar(select(func.count()).select_from(Audit)),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/remediation", dependencies=[Depends(reader)], tags=["read"])
    def remediation(session: ReadDB, dataset_id: str | None = None):
        rows = list(
            session.scalars(
                select(Issue).where(
                    Issue.dataset_id == latest_id(session, dataset_id),
                    Issue.active == 1,
                    Issue.status.in_(["open", "accepted", "deferred"]),
                )
            )
        )
        return {
            "status": "proposed_only",
            "items": [
                {
                    "id": row.id,
                    "kind": row.kind,
                    "severity": row.severity,
                    "material_ids": row.payload["material_ids"],
                    "action": row.payload["proposed_action"],
                    "review_status": row.status,
                    "owner_role": "Master-data steward"
                    if row.kind == "duplicate"
                    else "Purchasing data owner",
                    "requires_approval": True,
                }
                for row in rows
            ],
        }

    @app.get("/api/v1/export/findings.csv", dependencies=[Depends(reader)], tags=["read"])
    def export(session: ReadDB, dataset_id: str | None = None):
        rows = session.scalars(
            select(Issue).where(Issue.dataset_id == latest_id(session, dataset_id), Issue.active == 1)
        )
        stream = io.StringIO()
        writer_csv = csv.writer(stream)
        writer_csv.writerow(["finding_id", "kind", "severity", "status", "material_ids", "proposed_action"])
        for row in rows:
            values = [
                row.id,
                row.kind,
                row.severity,
                row.status,
                ";".join(row.payload["material_ids"]),
                row.payload["proposed_action"],
            ]
            writer_csv.writerow(
                [
                    "'" + str(value)
                    if str(value).lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else value
                    for value in values
                ]
            )
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="materialmaster-findings.csv"'},
        )

    @app.post("/api/v1/validate", dependencies=[Depends(reader)], tags=["validation"])
    def validate(body: BulkRequest):
        return validate_rows(body.records).model_dump(mode="json", exclude={"records"})

    @app.post("/api/v1/commands/import", response_model=MutationResult, tags=["commands"])
    def import_file(
        request: Request,
        session: DB,
        file: UploadFile = File(),
        actor: str = Depends(writer),
        key: str = Depends(idem_key),
    ):
        name = Path((file.filename or "upload.json").replace("\\", "/")).name
        name = re.sub(r"[^\w. -]", "_", name)[:150]
        suffix = Path(name).suffix.lower()
        if suffix not in {".json", ".jsonl", ".csv"} or file.content_type not in {
            "application/json",
            "application/x-ndjson",
            "application/jsonl",
            "text/csv",
            "text/plain",
            "application/octet-stream",
        }:
            raise HTTPException(415, "Upload a UTF-8 JSON, JSONL or CSV file")
        content = file.file.read(MAX_UPLOAD + 1)
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "File exceeds 20 MiB limit")
        try:
            rows = parse_upload(content, suffix)
        except (ValueError, UnicodeError, csv.Error) as error:
            raise HTTPException(422, f"Could not parse file: {error}") from error
        if not rows or len(rows) > 100000:
            raise HTTPException(422, "Import must contain 1–100,000 rows")
        body = {"operation": "import", "rows": rows, "name": name}
        scoped = actor + ":" + key
        cached = replay(session, scoped, body)
        if cached:
            return {"result": cached}
        result = ingest(session, rows, name, actor, request.state.trace_id)
        remember(session, scoped, body, result)
        return {"result": result}

    @app.post("/api/v1/commands/datasets/{dataset_id}/scan", response_model=MutationResult, tags=["commands"])
    def scan_dataset(
        dataset_id: str,
        request: Request,
        session: DB,
        actor: str = Depends(writer),
        key: str = Depends(idem_key),
    ):
        body, scoped = {"operation": "scan", "dataset_id": dataset_id}, actor + ":" + key
        cached = replay(session, scoped, body)
        if cached:
            return {"result": cached}
        model_path = os.getenv("EMBEDDING_MODEL_PATH")
        embedder = SentenceEmbedder(model_path) if model_path else None
        result = scan(session, dataset_id, actor, request.state.trace_id, embedder)
        remember(session, scoped, body, result)
        return {"result": result}

    @app.post("/api/v1/commands/findings/{issue_id}/review", response_model=MutationResult, tags=["commands"])
    def decide(
        issue_id: str,
        body: ReviewCommand,
        request: Request,
        session: DB,
        actor: str = Depends(writer),
        key: str = Depends(idem_key),
    ):
        value, scoped = {"operation": "review", "id": issue_id, **body.model_dump()}, actor + ":" + key
        cached = replay(session, scoped, value)
        if cached:
            return {"result": cached}
        result = review(session, issue_id, body, actor, request.state.trace_id)
        remember(session, scoped, value, result)
        return {"result": result}

    @app.post(
        "/api/v1/commands/findings/{issue_id}/explain", response_model=MutationResult, tags=["commands"]
    )
    def explanation(
        issue_id: str,
        selection: ModelSelection,
        request: Request,
        session: DB,
        actor: str = Depends(writer),
        key: str = Depends(idem_key),
    ):
        body, scoped = {"operation": "explain", "id": issue_id, **selection.model_dump()}, actor + ":" + key
        cached = replay(session, scoped, body)
        if cached:
            return {"result": cached}
        issue = session.get(Issue, issue_id)
        if not issue:
            raise LookupError("Finding not found")
        mode = os.getenv("LLM_RUNTIME", "disabled")
        if selection.runtime != mode:
            raise HTTPException(409, "Local runtime is disabled or has changed. Refresh the model list.")
        url = os.getenv("LLM_URL", "http://localhost:11434")
        try:
            selected_model = verify_selection(selection, url)
        except ModelUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        adapter = OllamaRuntime if mode == "ollama" else LlamaCppRuntime
        runtime = adapter(url, selection.model)
        records = session.scalars(
            select(MaterialRow).where(
                MaterialRow.dataset_id == issue.dataset_id, MaterialRow.id.in_(issue.payload["material_ids"])
            )
        )
        result, telemetry = explain(
            Finding.model_validate(issue.payload), [row.data for row in records], runtime
        )
        telemetry["selected_model"] = selected_model.model_dump()
        session.add(ModelEvent(trace_id=request.state.trace_id, data=telemetry))
        from materialmaster.services.workflow import audit

        audit(session, "finding.explained", issue_id, telemetry, actor, request.state.trace_id)
        response = {"explanation": result.model_dump(mode="json"), "telemetry": telemetry}
        remember(session, scoped, body, response)
        return {"result": response}

    return app


app = create_app()
