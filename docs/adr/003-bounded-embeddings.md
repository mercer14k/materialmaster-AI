# ADR 003 — Bounded local vectors before a vector database

Status: accepted.

**Context:** Global all-pairs duplicate comparison does not scale. Requiring a downloaded semantic model or pgvector on first run would obstruct the no-model demo.

**Decision:** Use deterministic engineering-spec/manufacturer blocks, a capped 80-record block size and scikit-learn character hashing vectors as a transparent lexical baseline. Optional sentence-transformers replaces only the encoder. Keep conflicts in known part numbers as hard vetoes. Report truncation rather than claiming complete retrieval.

**Consequences:** No pgvector extension is required in version 0.1. Missing numeric specs and abbreviations may reduce recall; published benchmarks expose those misses. Vectors are recomputed and not persisted. pgvector is a future adapter justified by measured retrieval needs, not a decorative dependency.

**Recommended-stack deviation:** Polars is deferred because this snapshot's constraints, Decimal normalization and bounded records are simpler in typed Python plus NumPy. The 100k benchmark measures this choice. Add a streaming/columnar execution path only with memory/runtime evidence and schema-equivalence tests.
