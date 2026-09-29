import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from materialmaster.services.storage import ModelEvent


@pytest.fixture
def local_runtime(monkeypatch):
    monkeypatch.setenv("LLM_RUNTIME", "ollama")
    monkeypatch.setenv("LLM_URL", "http://localhost:11434")
    monkeypatch.setenv("LLM_MODEL", "must-never-be-used")
    original = httpx.Client
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "installed-a", "digest": "digest-a"}, {"name": "installed-b"}]}
            )
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        evidence = json.loads(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": {
                    "content": json.dumps(
                        {
                            "status": "explained",
                            "summary": "Review the supplied records.",
                            "evidence_ids": evidence["allowed_evidence_ids"],
                        }
                    )
                },
            },
        )

    monkeypatch.setattr(
        "materialmaster.ai.catalog.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    return requests


def test_disabled_catalog_and_model_request(client, loaded):
    catalog = client.get("/api/v1/ai/models").json()
    assert catalog["status"] == "disabled"
    assert catalog["models"] == []
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    result = client.post(
        f"/api/v1/commands/findings/{issue['id']}/explain",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json={"runtime": "ollama", "model": "installed-a"},
    )
    assert result.status_code == 409


def test_explicit_model_used_audited_and_idempotent(client, loaded, local_runtime):
    catalog = client.get("/api/v1/ai/models").json()
    assert [item["id"] for item in catalog["models"]] == ["installed-a", "installed-b"]
    assert "selected_model" not in catalog
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    path = f"/api/v1/commands/findings/{issue['id']}/explain"
    headers = {"Idempotency-Key": uuid.uuid4().hex}
    body = {"runtime": "ollama", "model": "installed-a"}
    result = client.post(path, headers=headers, json=body)
    assert result.status_code == 200, result.text
    telemetry = result.json()["result"]["telemetry"]
    assert telemetry["model"] == telemetry["runtime_model"] == "installed-a"
    assert telemetry["selected_model"]["digest"] == "digest-a"
    count = len(local_runtime)
    assert client.post(path, headers=headers, json=body).json() == result.json()
    assert len(local_runtime) == count
    assert client.post(path, headers=headers, json={**body, "model": "installed-b"}).status_code == 409
    assert len(local_runtime) == count
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ModelEvent)) == 1


@pytest.mark.parametrize(
    "body,status",
    [
        ({}, 422),
        ({"runtime": "ollama", "model": ""}, 422),
        ({"runtime": "ollama", "model": "not-installed"}, 422),
        ({"runtime": "llamacpp", "model": "installed-a"}, 409),
        ({"runtime": "ollama", "model": "installed-a", "url": "https://evil.test"}, 422),
    ],
)
def test_selection_rejections_never_send_evidence(client, loaded, local_runtime, body, status):
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    result = client.post(
        f"/api/v1/commands/findings/{issue['id']}/explain",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json=body,
    )
    assert result.status_code == status
    assert all(request.url.path == "/api/tags" for request in local_runtime)
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ModelEvent)) == 0


def test_unavailable_model_catalog_returns_service_error_without_mutating_findings(
    client, loaded, monkeypatch
):
    from materialmaster.ai.catalog import ModelUnavailable

    def unavailable(*_):
        raise ModelUnavailable("Cannot verify local inventory")

    monkeypatch.setenv("LLM_RUNTIME", "ollama")
    monkeypatch.setattr("apps.api.main.verify_selection", unavailable)
    issue = client.get("/api/v1/findings?limit=1").json()["items"][0]
    before = client.get(f"/api/v1/findings/{issue['id']}").json()
    response = client.post(
        f"/api/v1/commands/findings/{issue['id']}/explain",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json={"runtime": "ollama", "model": "installed-a"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["trace_id"]
    assert client.get(f"/api/v1/findings/{issue['id']}").json() == before
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ModelEvent)) == 0


def test_catalog_and_generation_authorization(client, loaded, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("READ_TOKEN", "reader-test-value")
    monkeypatch.setenv("WRITE_TOKEN", "steward-test-value")
    assert client.get("/api/v1/ai/models").status_code == 401
    headers = {"Authorization": "Bearer reader-test-value", "Idempotency-Key": uuid.uuid4().hex}
    assert client.get("/api/v1/ai/models", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/commands/findings/any-id/explain",
            headers=headers,
            json={"runtime": "ollama", "model": "installed-a"},
        ).status_code
        == 403
    )
