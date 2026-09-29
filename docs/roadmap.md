# Roadmap

The current core is import → validation → detection → evidence review → audit/remediation. Further work should preserve the deterministic/no-LLM path.

## Next five meaningful improvements

1. **Independent semantic evaluation.** Build held-out positive/negative material pairs with missing IDs, engineering-spec hard negatives, abbreviations and multiple languages. Compare pinned MiniLM and alternative permissive encoders against the lexical baseline; publish both recall and compute.
2. **Restartable background jobs.** Stream imports, chunk validation, checkpoint scans and expose typed job status, cancellation and failure recovery. Bound memory and measure concurrent workloads before claiming scale.
3. **Purchasing-context model.** Normalize vendor/plant/organization info records separately from material identity. Add effective-dated prices, tiers, supplier pack conversions and explicitly approved equivalence mappings.
4. **Operational hardening.** Introduce Alembic migrations, OIDC per-person roles, retention/deletion policies, backup/restore tests and verifiable audit exports. Remove fresh-schema-only assumptions.
5. **Persistent candidate retrieval.** Add pgvector only with a labeled recall/latency experiment. Persist embedding/model fingerprints, support incremental updates and expose retrieval completeness to reviewers.

## Later, after core evidence improves

Active-learning sampling with calibrated uncertainty, schema-drift monitoring, material taxonomy classification and cross-ERP reconciliation mappings. No silent auto-merge is planned. Any ERP connector must be optional and kept outside the local open-source demo path.
