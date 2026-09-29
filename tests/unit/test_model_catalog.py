import json

import httpx
import pytest

from materialmaster.ai.catalog import ModelSelection, ModelUnavailable, discover_models, verify_selection


@pytest.fixture
def runtime_http(monkeypatch):
    original = httpx.Client
    requests = []

    def install(handler):
        def record(request):
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(
            "materialmaster.ai.catalog.httpx.Client",
            lambda **kwargs: original(transport=httpx.MockTransport(record), **kwargs),
        )
        return requests

    return install


def test_disabled_and_invalid_configuration_never_contact_runtime(runtime_http):
    requests = runtime_http(lambda _: pytest.fail("No runtime call allowed"))
    assert discover_models("disabled", "http://localhost:11434").status == "disabled"
    assert discover_models("other", "http://localhost").status == "unavailable"
    assert discover_models("ollama", "https://example.com").status == "unavailable"
    assert requests == []


def test_ollama_inventory_keeps_metadata_excludes_remote_aliases(runtime_http):
    requests = runtime_http(
        lambda _: httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "chosen:7b",
                        "size": 4000,
                        "digest": "sha256:abc",
                        "details": {"parameter_size": "7B", "quantization_level": "Q4_K_M"},
                    },
                    {"name": "remote:cloud"},
                    {"name": "alias", "remote_host": "https://example.com"},
                    {"name": "remote-alias", "remote_model": "cloud-model"},
                ]
            },
        )
    )
    result = discover_models("ollama", "http://localhost:11434")
    assert result.status == "ready"
    assert [model.id for model in result.models] == ["chosen:7b"]
    assert result.models[0].digest == "sha256:abc"
    assert result.models[0].quantization == "Q4_K_M"
    assert requests[0].url.path == "/api/tags"
    assert "selected" not in result.model_dump()


def test_llamacpp_lists_server_models_without_guessing_alias(runtime_http):
    requests = runtime_http(lambda _: httpx.Response(200, json={"data": [{"id": "my-approved-gguf"}]}))
    selection = ModelSelection(runtime="llamacpp", model="my-approved-gguf")
    assert verify_selection(selection, "http://localhost:8080").id == selection.model
    assert [request.url.path for request in requests] == ["/v1/models"]


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"models": []}, "empty"),
        ({"models": {}}, "unavailable"),
        ({"models": [None]}, "unavailable"),
        ({"models": [{"name": ""}]}, "unavailable"),
        ({}, "unavailable"),
    ],
)
def test_empty_and_malformed_inventories(runtime_http, payload, status):
    runtime_http(lambda _: httpx.Response(200, json=payload))
    assert discover_models("ollama", "http://localhost:11434").status == status


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(302, headers={"location": "https://remote.test"}),
        httpx.Response(200, content="not json"),
    ],
)
def test_runtime_error_or_redirect_fails_closed(runtime_http, response):
    requests = runtime_http(lambda _: response)
    assert discover_models("ollama", "http://localhost:11434").status == "unavailable"
    assert len(requests) == 1


def test_runtime_timeout(runtime_http):
    def unavailable(_):
        raise httpx.ConnectTimeout("offline")

    runtime_http(unavailable)
    with pytest.raises(ModelUnavailable):
        verify_selection(ModelSelection(runtime="ollama", model="chosen"), "http://localhost:11434")


@pytest.mark.parametrize(
    "info,accepted",
    [
        ({"capabilities": ["completion"]}, True),
        ({"capabilities": ["embedding"]}, False),
        ({}, False),
        ({"capabilities": ["completion"], "remote_host": "https://cloud.test"}, False),
        ({"capabilities": ["completion"], "remote_model": "alias"}, False),
    ],
)
def test_selected_ollama_model_metadata_verified_before_inference(runtime_http, info, accepted):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "chosen"}]})
        assert request.url.path == "/api/show"
        assert json.loads(request.content) == {"model": "chosen"}
        return httpx.Response(200, json=info)

    requests = runtime_http(handler)
    selection = ModelSelection(runtime="ollama", model="chosen")
    if accepted:
        assert verify_selection(selection, "http://localhost:11434").id == "chosen"
    else:
        with pytest.raises(ValueError):
            verify_selection(selection, "http://localhost:11434")
    assert len(requests) == 2


def test_unknown_model_never_calls_show_or_chat(runtime_http):
    requests = runtime_http(lambda _: httpx.Response(200, json={"models": [{"name": "installed"}]}))
    with pytest.raises(ValueError, match="not installed"):
        verify_selection(ModelSelection(runtime="ollama", model="guessed"), "http://localhost:11434")
    assert len(requests) == 1


def test_model_disappearing_between_inventory_and_show(runtime_http):
    runtime_http(
        lambda request: (
            httpx.Response(200, json={"models": [{"name": "chosen"}]})
            if request.url.path == "/api/tags"
            else httpx.Response(404)
        )
    )
    with pytest.raises(ModelUnavailable):
        verify_selection(ModelSelection(runtime="ollama", model="chosen"), "http://localhost:11434")
