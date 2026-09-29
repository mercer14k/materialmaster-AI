import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from materialmaster.domain.generator import generate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("LLM_RUNTIME", "disabled")
    # TEST_DATABASE_URL allows exactly the same API integration suite against PostgreSQL.
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    app = create_app(url, seed_demo=False)
    if os.getenv("TEST_DATABASE_URL"):
        from materialmaster.services.storage import Base

        Base.metadata.drop_all(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"Idempotency-Key": uuid.uuid4().hex}


@pytest.fixture
def loaded(client):
    rows, _ = generate(240)
    response = client.post(
        "/api/v1/commands/import",
        files={"file": ("materials.json", json.dumps(rows), "application/json")},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text
    dataset_id = response.json()["result"]["dataset_id"]
    response = client.post(
        f"/api/v1/commands/datasets/{dataset_id}/scan", headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert response.status_code == 200, response.text
    return dataset_id
