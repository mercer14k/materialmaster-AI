# Bring your own workplace data

**The demo data is entirely synthetic. Your workplace's source of truth is your ERP, purchasing system, MDM platform or governed data warehouse.** MaterialMaster reads snapshots you export and prepare; it does not connect to a public material database, access your ERP automatically or send your data to a cloud AI service.

## What can I connect today?

| Source | Supported path today | Typical records |
|---|---|---|
| ERP systems such as SAP, Oracle, Microsoft Dynamics or Odoo | An authorized export, mapped to the material contract, then CSV / JSON / JSONL import | Material/item master, units, status and classification |
| Procurement / supplier systems | An authorized export joined to your material snapshot | Supplier, purchasing organization, lead time, order quantity, purchase price |
| MDM platform or data warehouse | A governed view or scheduled extract that you prepare | Consolidated, source-qualified material and purchasing records |
| Existing spreadsheets | Map columns and save as UTF-8 CSV | A steward-managed material register or correction candidate list |
| Your own integration job | Bulk validation API; file import and scan command API, or CLI | Repeatable checks against prepared source snapshots |

These are source categories, **not shipped native connectors**. No SAP RFC/BAPI, Oracle, Dynamics, Odoo or live database adapter is bundled. `.xlsx` workbooks are not directly supported; export the chosen worksheet to UTF-8 CSV. The app does not write changes back into an ERP.

## Practical first import

1. Ask your data owner for an approved export. Start with one purchasing organization and one plant / supplier context. Include your material master, purchasing attributes and unit conversions at a consistent point in time.
2. Use [import-template.csv](../data/sample/import-template.csv) as a header template. The two example rows are synthetic; replace them with your own records. Rename and transform your source columns to the contract below. The app does not guess mappings.
3. Join source tables using their documented business keys. Verify join cardinality before export: one-to-many joins must not silently duplicate a material. This release accepts **one purchasing context per material per snapshot**. Use separate equivalent-scope snapshots for other plants or suppliers; it cannot compare a complete many-vendor pricing hierarchy.
4. Validate locally, inspect the visible errors, then import through **Import dataset → Validate & import**. Run the quality scan and review its evidence. Invalid rows stay in the report and are excluded from computed quality scores.
5. Export findings or the proposed remediation plan. Make approved corrections using your organization's normal ERP change process. Import a new comparable snapshot to measure the next result.

```bash
materialmaster validate data/sample/import-template.csv --analyze --output output/template-validation.json
# Persist a prepared snapshot and scan it in the configured database:
materialmaster import your-materials.csv --scan
```

For repeatable integrations, see the [versioned API](api.md). The browser accepts files up to 20 MiB; the bulk validation endpoint accepts up to 10,000 rows per call. Larger local files can use the CLI, subject to machine memory. Every import receives a dataset ID and ingestion timestamp; raw values, normalized values, rejected rows and review history are retained.

## Map business meaning, not just column names

| Destination | Source data to use | Important interpretation |
|---|---|---|
| `material_id` | Stable material / item number | Prefix with the source system, e.g. `ERP-A:100045`; unique within the snapshot, max 80 characters. Preserve leading zeros. |
| `source_system` | Your source identifier | Use a stable label; this is provenance, not a connector selection. |
| `description` | Item / material description | Raw text, 3–500 characters. Never include credentials or personal data. |
| `material_group` | Material group / commodity / item category | Map to comparable groups. Broad groups weaken price peer comparisons. |
| `manufacturer`, `manufacturer_part_number` | Engineering / manufacturer references | Keep these separate from supplier IDs and supplier-specific catalog numbers. |
| `base_uom`, `order_uom` | Stock unit and purchasing unit | Required; normalize ERP codes explicitly. Current known units: EA, PC, BOX, KG, G, M, CM, MM, L, ML. Unknown codes are flagged. |
| `order_to_base_factor` | Purchasing-unit conversion | Base units per one order unit. If an export says numerator/denominator, calculate the ratio deterministically. A box of 100 pieces means `100`. |
| `unit_price`, `price_unit`, `currency` | Current purchase price and its pricing basis | `unit_price` is the amount for `price_unit` **order units**. For 25 USD per box of 100 pieces: 25 / (1 × 100) = 0.25 USD per base unit. Do not mix stock valuation or sales prices with purchase prices. |
| `supplier_id`, `purchasing_org` | Vendor and responsible purchasing organization | Required by active-material purchasing rules; source them from the selected purchasing context. |
| `lead_time_days`, `minimum_order_qty` | Planned delivery time and MOQ | Calendar days; retain the order-quantity basis consistently. No workday/calendar conversion or MOQ optimization is provided. |
| `lifecycle`, `procurement_blocked` | Mapped item status and purchase block | Map statuses explicitly to ACTIVE / PHASE_OUT / OBSOLETE and true / false. Do not infer a block from a label alone. |
| `provenance` | Optional source keys, extract date, mapping version | Structured object in JSON / JSONL; omit from CSV or use a JSON-encoded object. Treated as data only. |

The six structural fields `material_id`, `source_system`, `description`, `material_group`, `base_uom` and `order_uom` are required to import a valid row. Additional fields supply operational checks. Schema defaults include USD, ACTIVE, unblocked and a price unit of 1; **populate these explicitly from real exports** so defaults do not misrepresent business facts. Missing price, conversion or purchasing values should be left null, not replaced with invented values. See the complete [data dictionary](data-model.md) and [JSON Schema](../data/schemas/material.schema.json).

Prices are compared within material group, currency and base-unit cohorts. No exchange-rate conversion, contract validity, freight/tax normalization or quantity-tier pricing is implemented. Restrict your extracts to a comparable commercial context; a statistical outlier is a review suggestion, not proof of an incorrect purchase price.

## Local processing and ownership

Your imported records remain in the configured local database. Selecting a local explanation model sends the cited evidence to the runtime on the **API host**; opening the app in another computer's browser does not make inference run on that browser's device. Treat the API host and runtime as your data-processing boundary. Models do not become data sources or create authoritative master records.

Use approved extracts and local access controls for real company data. Keep production exports out of Git; files outside the ignored generated-data directories need their own ignore rules. [Security and deployment boundaries](security.md) describe token roles and the limits of the default localhost demo.
