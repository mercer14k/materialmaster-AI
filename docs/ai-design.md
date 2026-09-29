# Local AI, bounded responsibilities

## Three distinct kinds of output

1. **Rule/statistical evidence:** deterministic checks, Decimal price normalization, median/MAD statistics and workflow state.
2. **Model predictions:** lexical or semantic cosine similarity. A score is not a probability and never authorizes a merge.
3. **Generated narrative:** an optional explanation with required evidence IDs and human-readable suggestions. It is labeled separately in the UI.

The default character hashing encoder uses scikit-learn, 512 dimensions, character word-boundary 3–5 grams and L2 normalization. It is lexical, requires no model download and is never described as semantic understanding. Stable block keys constrain candidates; known part-number conflicts are a hard veto.

## Optional semantic embeddings

Install the optional dependency and download an approved local model once:

```bash
pip install '.[semantic]'
python -c "from huggingface_hub import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2', local_dir='models/embedding')"
```

Record the exact upstream revision in your experiment notes; use `revision=<approved commit>` when pinning a download. The runtime itself uses `local_files_only=True` and `trust_remote_code=False`. It does not silently download weights. For native API execution, set `EMBEDDING_MODEL_PATH` to the absolute model folder, then run a scan. In Compose, set `INSTALL_SEMANTIC=true` and `EMBEDDING_MODEL_PATH=/models/embedding`, then rebuild the API.

```bash
materialmaster benchmark --count 100000 --seed 42 --model-path models/embedding --output output/minilm
```

The local adapter honors the same hard candidate rules. It cannot recover pairs excluded during blocking. MiniLM is [Apache-2.0 according to its model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). A live model download/run was not part of the authoring-machine verification.

## Local language-model runtimes

The `Runtime` protocol returns text plus observable runtime metadata. `OllamaRuntime` calls `/api/chat` with a JSON Schema. `LlamaCppRuntime` calls local `/v1/chat/completions` using llama.cpp's documented `json_object` plus `schema` format. These are local adapters, not cloud SDK dependencies.

### Explicit selection; no default model

The app never downloads, preselects or falls back to a language model. The sidebar's **Local AI models** panel and the finding's **Explanation model** picker start at **No model selected**. A user must choose a model from the configured runtime. Selection is held in browser memory and cleared on reload; refreshing preserves only an explicitly selected model that remains available in the same runtime.

`GET /api/v1/ai/models` discovers Ollama's `/api/tags` or llama.cpp's `/v1/models`. Responses distinguish disabled, unavailable, empty and ready states. They contain no default-model field. Every explanation request must supply `{ "runtime": "ollama", "model": "<exact installed name>" }`. The server rechecks the live inventory, rejects provider changes or unknown models, and includes the choice in its idempotency fingerprint and audit telemetry. `LLM_MODEL` is not used.

Ollama cloud entries are filtered using remote metadata and cloud tags. Before sending records, `/api/show` verifies the selected model has completion capability and no remote host/model. Ollama should also run with `OLLAMA_NO_CLOUD=1` (already set in the optional Compose service). The runtime is an operator-controlled trust boundary; do not point the app at a proxy that forwards local requests elsewhere.

### Use models already on your device

Start your local Ollama runtime with cloud features disabled. Install only weights whose exact license and hardware needs you have reviewed; the app does not choose these for you. Native API environment:

```bash
export LLM_RUNTIME=ollama
export LLM_URL=http://localhost:11434
uvicorn apps.api.main:app --host 127.0.0.1 --port 8120
```

PowerShell equivalents: `$env:LLM_RUNTIME="ollama"` and `$env:LLM_URL="http://localhost:11434"`, then the same uvicorn command. Native uvicorn does not automatically read `.env`; set these environment variables or use an explicit environment loader.

For a Docker API using your existing host runtime, set `LLM_RUNTIME=ollama` and `LLM_URL=http://host.docker.internal:11434` in `.env`, then `docker compose up -d api`. On Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` to the API service in a Compose override. Host runtime binding/firewall settings must permit the container to reach it; do not expose the runtime publicly. A native API is the simplest way to use a loopback-only host runtime.

Open **Local AI models → Refresh local models** and select the installed model by its exact name. No inference occurs until you click **Generate explanation** on a finding. An embedding-only model cannot generate explanations; the server rejects it.

### Use a separate containerized model library

```bash
docker compose --profile ai up -d ollama
# Inspect what is already installed in this container:
docker compose exec ollama ollama list
# If needed, manually install YOUR chosen, licensed model:
# docker compose exec ollama ollama pull <your-chosen-model>
```

Set `LLM_RUNTIME=ollama` and `LLM_URL=http://ollama:11434` in `.env`, then run `docker compose up -d api`. The container volume does not automatically contain models installed in a desktop Ollama library. The UI still requires explicit selection after installation.

### llama.cpp

Start an open-source `llama-server` with your approved GGUF file and chat template on loopback. Configure `LLM_RUNTIME=llamacpp` and `LLM_URL=http://localhost:8080` for native execution (or the appropriate allowed local container hostname). Refresh the selector and choose the ID/alias advertised by `/v1/models`. There is no guessed model alias and no automatic choice even if only one model is loaded.

Model-family names do not imply identical licenses across sizes or quantizations. Keep the exact chosen model's license with redistributed weights. Qwen2.5 7B Instruct and MiniLM are examples documented in the [license inventory](open-source-licenses.md), not application defaults. No weights are committed here.

References: [Ollama model inventory](https://docs.ollama.com/api/tags), [Ollama v0.13.5 inventory/show metadata](https://github.com/ollama/ollama/blob/v0.13.5/api/types.go), [Ollama structured outputs](https://ollama.com/blog/structured-outputs), [llama.cpp server contract](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Evidence and failure policy

The service abstains before inference if required records or finding evidence are absent. Runtime failures, malformed JSON, extra fields, unknown citations or incomplete evidence citations trigger at most one retry, then abstention. A valid JSON schema does not prove factual correctness; the UI preserves evidence alongside narrative for human verification.

Source descriptions and provenance are serialized as untrusted data. A system instruction explicitly rejects embedded instructions. There are no tools available to the model: no SQL, shell, file execution, external retrieval or state-changing functions. Prompt injection may still corrupt prose; it cannot own business state. Server authorization and deterministic code remain the enforcement boundary.

Recorded telemetry includes trace ID, runtime, model identifier, prompt template version, source material IDs, temperature, seed, retries, validation error types, latency, available token counts, algorithm version and an empty tool-call list. No private chain-of-thought is requested or persisted.

## Learning from review

For each detection method, the latest accepted/rejected state per finding updates a Beta(1,1) estimate: `(accepted + 1)/(accepted + rejected + 2)`. This adjusts queue priority within severity. Deferred decisions do not train it, repeated decisions do not add duplicate votes, rescans preserve state, and no candidate is hidden or auto-merged. This is modest feedback calibration, not an active-learning claim or a calibrated truth probability.

## Comparing runtimes

Use identical finding IDs, source snapshots, prompt version and generation settings. Collect `model_events` and `audit_events` from an isolated benchmark database. Compare schema success, citation validity, abstention, latency and human-rated factuality. Semantic similarity metrics come from the CLI benchmark; free-form model output never supplies benchmark truth. Live runtime comparison remains unmeasured in the committed baseline.
