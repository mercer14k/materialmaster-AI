# Data model and dictionary

The external contract is [material.schema.json](../data/schemas/material.schema.json), generated from `domain/models.py`. Extra fields are rejected visibly rather than silently ignored. Decimal values may be strings to preserve source precision.

| Field | Meaning / constraint |
|---|---|
| `material_id` | Stable, source-qualified ID; unique within an imported dataset, 1–80 safe identifier characters |
| `source_system` | Origin identifier, e.g. synthetic `ERP-NORTH`; not a claim of an installed ERP integration |
| `description` | Raw material description; 3–500 characters; always treated as untrusted content |
| `material_group` | Quality/price cohort and analytical grouping |
| `manufacturer` | Optional manufacturer identity; normalized only for candidate comparison |
| `manufacturer_part_number` | Optional engineering identity anchor; conflicting known numbers veto text-only duplicate candidates |
| `base_uom` | Stock/base unit: EA, PC, BOX, KG, G, M, CM, MM, L, ML supported by current mapping |
| `order_uom` | Purchasing unit; schema accepts unknown codes so the UOM rule can flag them visibly |
| `order_to_base_factor` | Number of base units per one order unit; positive Decimal, nullable for missing-evidence detection |
| `unit_price` | Price for `price_unit` order units; non-negative Decimal, nullable |
| `price_unit` | Number of order units covered by quoted price; positive, defaults to 1 |
| `currency` | Three uppercase letters; grouped separately, no FX conversion |
| `supplier_id` | Supplier identity; missing active-material value raises a purchasing finding |
| `purchasing_org` | Responsible purchasing organization; required by the active-material rule |
| `lead_time_days` | Integer calendar-day assumption, 0–3650; >365 triggers review |
| `minimum_order_qty` | Positive quantity, retained for review; not currently optimized or benchmarked |
| `lifecycle` | ACTIVE, PHASE_OUT or OBSOLETE |
| `procurement_blocked` | Boolean; obsolete and unblocked creates a lifecycle conflict |
| `provenance` | Optional metadata object, retained as data and never executed |

The persisted representation adds `dataset_id`, `ingested_at`, `validation_status`, raw fields and normalized fields. Invalid rows retain row number, raw content, errors, dataset link and ingestion time. Duplicate IDs are quarantined after the first valid occurrence; this is explicit in the validation report.

## Table responsibilities

| Table | Purpose |
|---|---|
| datasets | Immutable source snapshot identity, content hash, counts and scan metadata |
| materials | Raw/normalized records, compound dataset/material primary key |
| rejected_rows | Visible row-level failures, original content and reasons |
| findings | Stable evidence, detection method, review state, active flag and optimistic version |
| reviews | Every submitted decision, reason, server-assigned actor and time |
| audit_events | Import, scan, review and explanation events with trace IDs |
| quality_snapshots | Actual scan quality, group/source cohorts and algorithm settings |
| idempotency_keys | Actor-scoped request fingerprint and original command response |
| model_events | Model/configuration, citations, latency, retry and validation-failure telemetry |

## Synthetic data

Seed 42 is the default; source IDs are stable for a fixed row count. Every 40-row block includes two duplicate variants, an incompatible UOM, a 14× price outlier, missing purchasing attributes, an obsolete-but-unblocked material and a long lead time. The near duplicate omits its part-number anchor. Ground truth is written separately to `ground_truth.json` and is not fed to detection. These deliberate injection patterns are not a representative commercial price distribution.

The current flattened record represents one purchasing context per material. Separate multi-supplier/plant info records, price-validity intervals and tier pricing are future schema work.
