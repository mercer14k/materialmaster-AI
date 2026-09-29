# ADR 001 — Deterministic core, optional local narrative

Status: accepted.

**Context:** Master-data errors can cause purchase-order mistakes. A stochastic model must not decide prices, conversion factors, workflow state or quality scores.

**Decision:** Use typed Python/Decimal rules and explicit statistics. Put local embeddings behind a protocol. Put explanations behind a separate local-runtime protocol with strict validation and abstention. Disable narrative by default. Models get no mutation tools.

**Consequences:** Offline/no-model demonstrations remain complete. Narratives can fail without corrupting deterministic findings. Domain owners must still calibrate peer groups and review outputs. Local models add latency and hardware requirements only when enabled.
