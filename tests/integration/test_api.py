import json
import uuid

from sqlalchemy import func, select

from materialmaster.domain.generator import generate
from materialmaster.services.storage import MaterialRow, ModelEvent


def key():
    return {"Idempotency-Key": uuid.uuid4().hex}


def test_health_ready_and_openapi(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "ReviewCommand" in schema["components"]["schemas"]


def test_import_scan_review_export_and_audit(client, loaded):
    summary = client.get("/api/v1/overview").json()
    assert summary["metrics"]["total_materials"] == 240
    issue = client.get("/api/v1/findings?kind=duplicate&limit=1").json()["items"][0]
    detail = client.get("/api/v1/findings/" + issue["id"]).json()
    assert len(detail["records"]) == 2
    result = client.post(
        "/api/v1/commands/findings/" + issue["id"] + "/review",
        json={
            "decision": "accepted",
            "reason": "Supplier specification and identifiers verified",
            "expected_version": 0,
        },
        headers=key(),
    )
    assert result.status_code == 200
    assert client.get("/api/v1/overview").json()["feedback"]["accepted"] == 1
    assert client.get("/api/v1/findings?kind=duplicate").json()["items"][0]["learned_priority"] > 0.5
    assert "accepted" in client.get("/api/v1/export/findings.csv").text
    assert any(item["action"] == "finding.reviewed" for item in client.get("/api/v1/audit").json()["items"])
    assert client.get("/api/v1/remediation").json()["status"] == "proposed_only"
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MaterialRow)) == 240


def test_import_idempotency_and_payload_mismatch(client):
    rows = generate(20)[0]
    headers = key()
    upload = {"file": ("source.json", json.dumps(rows), "application/json")}
    a = client.post("/api/v1/commands/import", files=upload, headers=headers)
    b = client.post("/api/v1/commands/import", files=upload, headers=headers)
    assert a.json() == b.json()
    rows[0]["description"] = "Changed row"
    c = client.post(
        "/api/v1/commands/import",
        files={"file": ("source.json", json.dumps(rows), "application/json")},
        headers=headers,
    )
    assert c.status_code == 409
    assert client.get("/api/v1/datasets").json()["total"] == 1


def test_review_replay_and_optimistic_conflict(client, loaded):
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    url = "/api/v1/commands/findings/" + issue["id"] + "/review"
    headers, body = (
        key(),
        {
            "decision": "rejected",
            "reason": "Verified separate engineering specification",
            "expected_version": 0,
        },
    )
    first = client.post(url, json=body, headers=headers)
    assert client.post(url, json=body, headers=headers).json() == first.json()
    assert client.post(url, json=body, headers=key()).status_code == 409
    assert len(client.get("/api/v1/findings/" + issue["id"]).json()["reviews"]) == 1


def test_rescan_preserves_review_and_adds_real_trend(client, loaded):
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    client.post(
        "/api/v1/commands/findings/" + issue["id"] + "/review",
        json={"decision": "deferred", "reason": "Awaiting supplier response", "expected_version": 0},
        headers=key(),
    )
    client.post(f"/api/v1/commands/datasets/{loaded}/scan", headers=key())
    assert client.get("/api/v1/findings/" + issue["id"]).json()["status"] == "deferred"
    assert len(client.get("/api/v1/overview").json()["history"]) == 2


def test_missing_selection_preserves_database_without_inference(client, loaded):
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    before = client.get("/api/v1/findings/" + issue["id"]).json()
    result = client.post("/api/v1/commands/findings/" + issue["id"] + "/explain", headers=key())
    assert result.status_code == 422
    assert client.get("/api/v1/findings/" + issue["id"]).json() == before
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ModelEvent)) == 0


def test_malformed_rows_preserved_and_filename_sanitized(client):
    content = json.dumps([generate(20)[0][0], {"bad": "raw data"}])
    result = client.post(
        "/api/v1/commands/import",
        files={"file": ("../../sensitive/materials.json", content, "application/json")},
        headers=key(),
    ).json()["result"]
    assert result["invalid_count"] == 1
    report = client.get(f"/api/v1/datasets/{result['dataset_id']}/validation").json()
    assert report["items"][0]["raw"]["value"] == {"bad": "raw data"}
    assert client.get("/api/v1/datasets").json()["items"][0]["name"] == "materials.json"


def test_validation_read_only_endpoint_and_error_format(client):
    response = client.post("/api/v1/validate", json={"records": [{"bad": "record"}]})
    assert response.json()["invalid_count"] == 1
    assert client.get("/api/v1/datasets").json()["total"] == 0
    malformed = client.post("/api/v1/validate", json={"records": "not a list"})
    assert malformed.status_code == 422
    assert malformed.json()["error"]["trace_id"] == malformed.headers["x-trace-id"]


def test_authz_token_reader_cannot_mutate(client, loaded, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("READ_TOKEN", "read-only-test")
    monkeypatch.setenv("WRITE_TOKEN", "steward-test")
    assert client.get("/api/v1/overview").status_code == 401
    headers = {"Authorization": "Bearer read-only-test", **key()}
    assert client.get("/api/v1/overview", headers=headers).status_code == 200
    assert client.post(f"/api/v1/commands/datasets/{loaded}/scan", headers=headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/commands/datasets/{loaded}/scan",
            headers={"Authorization": "Bearer steward-test", **key()},
        ).status_code
        == 200
    )


def test_upload_rejections_and_pagination_limits(client):
    assert (
        client.post(
            "/api/v1/commands/import",
            files={"file": ("script.html", "<script>x</script>", "text/html")},
            headers=key(),
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/v1/commands/import",
            files={"file": ("bad.json", "not-json", "application/json")},
            headers=key(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/commands/import", files={"file": ("empty.json", "[]", "application/json")}, headers=key()
        ).status_code
        == 422
    )
    assert client.get("/api/v1/datasets?limit=99999").status_code == 422
    assert client.get("/api/v1/datasets?offset=-1").status_code == 422
    assert client.get("/api/v1/findings/nonexistent").status_code == 404
    assert client.post("/api/v1/validate", content=b" " * (21 * 1024 * 1024)).status_code == 413


def test_search_filter_pagination_and_sql_payload(client, loaded):
    first = client.get("/api/v1/materials?limit=10&offset=0").json()
    second = client.get("/api/v1/materials?limit=10&offset=10").json()
    assert first["total"] == 240 and first["items"][0] != second["items"][0]
    assert (
        client.get("/api/v1/materials", params={"search": "'; DROP TABLE materials;--"}).json()["total"] == 0
    )
    assert client.get("/api/v1/materials?group=Bearings").json()["total"] > 0


def test_model_timeout_keeps_persisted_finding_unchanged(client, loaded, monkeypatch):
    class FailedRuntime:
        name, model = "test-runtime", "unavailable-model"

        def __init__(self, *_):
            pass

        def complete(self, *_):
            raise TimeoutError("Synthetic model outage")

    from materialmaster.ai.catalog import LocalModel

    monkeypatch.setattr("apps.api.main.verify_selection", lambda *_: LocalModel(id="unavailable-model"))
    monkeypatch.setattr("apps.api.main.OllamaRuntime", FailedRuntime)
    monkeypatch.setenv("LLM_RUNTIME", "ollama")
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    before = client.get("/api/v1/findings/" + issue["id"]).json()
    response = client.post(
        "/api/v1/commands/findings/" + issue["id"] + "/explain",
        headers=key(),
        json={"runtime": "ollama", "model": "unavailable-model"},
    )
    result = response.json()["result"]
    assert result["explanation"]["status"] == "abstained"
    assert result["telemetry"]["validation_failures"] == ["TimeoutError", "TimeoutError"]
    assert client.get("/api/v1/findings/" + issue["id"]).json() == before


def test_extra_csv_columns_are_retained_as_invalid_rows(client):
    response = client.post(
        "/api/v1/commands/import",
        files={"file": ("extra.csv", "material_id,description\na,example,unexpected\n", "text/csv")},
        headers=key(),
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["invalid_count"] == 1
    assert client.get(f"/api/v1/datasets/{result['dataset_id']}/validation").json()["items"][0]["raw"][
        "value"
    ]["_extra_columns"] == ["unexpected"]


def test_non_finite_json_upload_rejected(client):
    assert (
        client.post(
            "/api/v1/commands/import",
            files={"file": ("bad.json", '[{"unit_price": NaN}]', "application/json")},
            headers=key(),
        ).status_code
        == 422
    )


def test_persisted_timestamps_are_explicit_utc(client, loaded):
    assert client.get("/api/v1/datasets").json()["items"][0]["created_at"].endswith("+00:00")
    assert client.get("/api/v1/audit").json()["items"][0]["at"].endswith("+00:00")
