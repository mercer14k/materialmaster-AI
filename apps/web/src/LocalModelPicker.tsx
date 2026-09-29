import { useCallback, useEffect, useId, useRef, useState } from "react";
import { LoaderCircle, RefreshCw } from "lucide-react";
import { api } from "./api";

type Catalog = {
  runtime: string;
  status: "disabled" | "ready" | "empty" | "unavailable";
  message: string;
  models: {
    id: string;
    parameter_size: string | null;
    quantization: string | null;
  }[];
};
type Selection = { runtime: "ollama" | "llamacpp"; model: string };

export function useLocalModels(revision: number) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Catalog>("/ai/models");
      if (generation.current !== request) return;
      setCatalog(result);
      setSelection((current) =>
        current?.runtime === result.runtime &&
        result.models.some((item) => item.id === current.model)
          ? current
          : null,
      );
    } catch (e) {
      if (generation.current !== request) return;
      setCatalog(null);
      setSelection(null);
      setError(e instanceof Error ? e.message : "Could not read local models.");
    } finally {
      if (generation.current === request) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    return () => {
      generation.current += 1;
    };
  }, [refresh, revision]);
  const choose = (model: string) => {
    if (
      !catalog ||
      !["ollama", "llamacpp"].includes(catalog.runtime) ||
      !catalog.models.some((item) => item.id === model)
    ) {
      setSelection(null);
      return;
    }
    setSelection({ runtime: catalog.runtime as Selection["runtime"], model });
  };
  return { catalog, selection, loading, error, refresh, choose };
}

export function LocalModelPicker({
  state,
  disabled = false,
}: {
  state: ReturnType<typeof useLocalModels>;
  disabled?: boolean;
}) {
  const id = useId();
  const { catalog, selection, loading, error, refresh, choose } = state;
  return (
    <section className="model-picker" aria-label="Local model selection">
      <label className="field-label" htmlFor={id}>
        Explanation model
        <span>
          {catalog?.runtime === "llamacpp"
            ? "llama.cpp"
            : catalog?.runtime === "ollama"
              ? "Ollama"
              : "Local runtime"}
        </span>
      </label>
      <div className="model-picker-controls">
        <select
          id={id}
          value={selection?.model || ""}
          onChange={(event) => choose(event.target.value)}
          disabled={disabled || loading || catalog?.status !== "ready"}
          aria-describedby={id + "-help"}
        >
          <option value="">No model selected</option>
          {catalog?.models.map((model) => (
            <option value={model.id} key={model.id}>
              {model.id}
              {model.parameter_size ? ` · ${model.parameter_size}` : ""}
              {model.quantization ? ` · ${model.quantization}` : ""}
            </option>
          ))}
        </select>
        <button
          className="button"
          onClick={() => void refresh()}
          disabled={disabled || loading}
          aria-label="Refresh local models"
        >
          {loading ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <RefreshCw size={15} />
          )}
        </button>
      </div>
      <p id={id + "-help"} className="small muted" role="status">
        {loading
          ? "Looking for models in your local runtime…"
          : error || catalog?.message}
      </p>
      {selection && (
        <p className="small muted">
          Selected for this session. Reloading starts with no model selected.
        </p>
      )}
    </section>
  );
}
