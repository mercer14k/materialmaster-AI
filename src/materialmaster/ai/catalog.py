"""Read the configured local runtime's inventory; never select or download a model."""

from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from materialmaster.ai.explanations import validate_local_url


class ModelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    runtime: Literal["ollama", "llamacpp"]
    model: str = Field(min_length=1, max_length=256, pattern=r"^[^\s\x00-\x1f]+$")


class LocalModel(BaseModel):
    id: str
    size_bytes: int | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    digest: str | None = None


class ModelCatalog(BaseModel):
    runtime: str
    status: Literal["disabled", "ready", "empty", "unavailable"]
    models: list[LocalModel] = Field(default_factory=list)
    message: str


class ModelUnavailable(Exception):
    """Inventory could not be verified without sending source evidence."""


def is_remote(item: dict) -> bool:
    name = str(item.get("model") or item.get("name") or item.get("id") or "").lower()
    return bool(item.get("remote_host") or item.get("remote_model") or name.endswith((":cloud", "-cloud")))


def discover_models(mode: str, url: str) -> ModelCatalog:
    if mode == "disabled":
        return ModelCatalog(
            runtime=mode,
            status="disabled",
            message="Connect a local Ollama or llama.cpp runtime to see your installed models.",
        )
    if mode not in {"ollama", "llamacpp"}:
        return ModelCatalog(
            runtime=mode, status="unavailable", message="Unsupported local runtime configuration."
        )
    try:
        validate_local_url(url)
        with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
            response = client.get(url.rstrip("/") + ("/api/tags" if mode == "ollama" else "/v1/models"))
            response.raise_for_status()
            entries = response.json()["models" if mode == "ollama" else "data"]
            if not isinstance(entries, list):
                raise ValueError("Invalid model inventory")
            models = {}
            for item in entries:
                if is_remote(item):
                    continue
                identifier = item.get("model") or item.get("name") if mode == "ollama" else item.get("id")
                selection = ModelSelection(runtime=mode, model=identifier)
                details = item.get("details") or {}
                models[selection.model] = LocalModel(
                    id=selection.model,
                    size_bytes=item.get("size"),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    digest=item.get("digest"),
                )
        return ModelCatalog(
            runtime=mode,
            status="ready" if models else "empty",
            models=sorted(models.values(), key=lambda item: item.id),
            message="Choose a model explicitly. Nothing is selected or downloaded automatically."
            if models
            else "No local models found. Install a model in your runtime, then refresh.",
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return ModelCatalog(
            runtime=mode,
            status="unavailable",
            message="Could not read the local runtime. Check that it is running and reachable, then refresh.",
        )


def verify_selection(selection: ModelSelection, url: str) -> LocalModel:
    catalog = discover_models(selection.runtime, url)
    if catalog.status == "unavailable":
        raise ModelUnavailable(catalog.message)
    model = next((item for item in catalog.models if item.id == selection.model), None)
    if model is None:
        raise ValueError(
            "Selected model is not installed in the configured local runtime. Refresh and choose again."
        )
    if selection.runtime == "ollama":
        # Verify metadata before sending any source records, including aliased cloud models.
        try:
            with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
                response = client.post(url.rstrip("/") + "/api/show", json={"model": selection.model})
                response.raise_for_status()
                info = response.json()
                if not isinstance(info, dict):
                    raise TypeError("Invalid model metadata")
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise ModelUnavailable(
                "Could not verify the selected local model. Refresh and try again."
            ) from error
        if is_remote(info):
            raise ValueError("Cloud-backed models are not allowed. Choose locally installed weights.")
        if "completion" not in (info.get("capabilities") or []):
            raise ValueError("This model does not advertise text completion. Choose a local chat model.")
    return model
