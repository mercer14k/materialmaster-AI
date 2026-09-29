"""Pure deterministic rules, robust peer statistics and bounded duplicate candidates."""

import hashlib
import itertools
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from materialmaster.ai.embeddings import Embedder, LexicalEmbedder
from materialmaster.domain.models import Finding, Material

ALGORITHM_VERSION = "rules-1.0"
UOMS = {
    "EA": ("count", 1),
    "PC": ("count", 1),
    "BOX": ("count", None),
    "KG": ("mass", 1),
    "G": ("mass", 0.001),
    "M": ("length", 1),
    "CM": ("length", 0.01),
    "MM": ("length", 0.001),
    "L": ("volume", 1),
    "ML": ("volume", 0.001),
}
SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(frozen=True)
class EngineConfig:
    similarity_threshold: float = 0.80
    max_block_size: int = 80
    min_price_peers: int = 8
    price_ratio: float = 3.0
    modified_z_threshold: float = 6.0


def canonical(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def finding_id(kind: str, ids: list[str]) -> str:
    return hashlib.sha256((kind + "|" + "|".join(sorted(ids))).encode()).hexdigest()[:24]


def uom_issues(row: Material) -> list[str]:
    issues = []
    base, order = UOMS.get(row.base_uom), UOMS.get(row.order_uom)
    if not base or not order:
        return ["Unknown UOM code; steward mapping required"]
    if base[0] != order[0]:
        issues.append("Order and base units have incompatible dimensions")
    elif row.order_to_base_factor is None:
        issues.append("Missing order-to-base conversion factor")
    elif base[1] is not None and order[1] is not None:
        expected = Decimal(str(order[1])) / Decimal(str(base[1]))
        if abs(row.order_to_base_factor - expected) > Decimal("0.000001"):
            issues.append(f"Conversion must be {expected} base units per order unit")
    return issues


def normalized_price(row: Material) -> float | None:
    if row.unit_price is None or uom_issues(row) or row.order_to_base_factor is None:
        return None
    return float(row.unit_price / (row.price_unit * row.order_to_base_factor))


def analyze(
    records: list[Material], config: EngineConfig | None = None, embedder: Embedder | None = None
) -> tuple[list[Finding], dict]:
    config, embedder = config or EngineConfig(), embedder or LexicalEmbedder()
    findings: dict[str, Finding] = {}

    def emit(kind, severity, rows, title, evidence, action, method="rule", score=1.0):
        ids = sorted(row.material_id for row in rows)
        item = Finding(
            finding_id=finding_id(kind, ids),
            kind=kind,
            severity=severity,
            material_ids=ids,
            title=title,
            evidence=evidence,
            proposed_action=action,
            method=method,
            score=score,
        )
        findings[item.finding_id] = item

    peers = defaultdict(list)
    blocks: dict[tuple, list[Material]] = defaultdict(list)
    for row in records:
        issues = uom_issues(row)
        if issues:
            emit(
                "uom",
                "critical",
                [row],
                "Inconsistent unit of measure",
                {
                    "base_uom": row.base_uom,
                    "order_uom": row.order_uom,
                    "factor": str(row.order_to_base_factor),
                    "violations": issues,
                },
                "Verify the supplier pack specification; approve a dimensionally valid conversion before purchasing.",
            )
        missing = [
            key
            for key in ("supplier_id", "purchasing_org", "lead_time_days", "unit_price")
            if getattr(row, key) is None or getattr(row, key) == ""
        ]
        if row.lifecycle == "ACTIVE" and missing:
            emit(
                "purchasing",
                "high",
                [row],
                "Incomplete purchasing record",
                {"missing_fields": missing, "lifecycle": row.lifecycle},
                "Request missing purchasing attributes from the responsible buyer; validate against the supplier agreement.",
            )
        if row.lifecycle == "OBSOLETE" and not row.procurement_blocked:
            emit(
                "lifecycle",
                "critical",
                [row],
                "Obsolete material is open for purchasing",
                {"lifecycle": row.lifecycle, "procurement_blocked": row.procurement_blocked},
                "Confirm open orders and replacement material; have the ERP owner approve a purchasing block.",
            )
        if row.lead_time_days is not None and row.lead_time_days > 365:
            emit(
                "lead_time",
                "medium",
                [row],
                "Lead time exceeds review threshold",
                {"lead_time_days": row.lead_time_days, "threshold_days": 365},
                "Confirm calendar vs working days and replenishment assumptions with the supplier.",
            )
        price = normalized_price(row)
        if price is not None and row.lifecycle == "ACTIVE":
            peers[(row.material_group, row.currency, row.base_uom)].append((row, price))
        if row.manufacturer and row.manufacturer_part_number:
            blocks[("part", canonical(row.manufacturer), canonical(row.manufacturer_part_number))].append(row)
        blocks[("description", row.material_group, canonical(row.description))].append(row)
        # Numeric engineering specifications constrain candidate generation; never compare an all-pairs matrix.
        numbers = tuple(sorted(re.findall(r"\d+(?:\.\d+)?", row.description)))
        if numbers:
            blocks[("similar", row.material_group, canonical(row.manufacturer), numbers)].append(row)

    for (group, currency, base), cohort in peers.items():
        if len(cohort) < config.min_price_peers:
            continue
        values = [price for _, price in cohort]
        center = median(values)
        mad = median(abs(price - center) for price in values)
        scale = max(mad / 0.6745, abs(center) * 0.01, 0.000001)
        for row, price in cohort:
            z = abs(price - center) / scale
            ratio = price / center if center else (float("inf") if price else 1)
            if z >= config.modified_z_threshold and (
                ratio >= config.price_ratio or ratio <= 1 / config.price_ratio
            ):
                emit(
                    "price",
                    "high",
                    [row],
                    "Price outside comparable peer range",
                    {
                        "normalized_price": price,
                        "peer_median": center,
                        "peer_mad": mad,
                        "robust_z": round(z, 3),
                        "peer_count": len(cohort),
                        "currency": currency,
                        "base_uom": base,
                        "material_group": group,
                        "formula": "unit_price / (price_unit × order_to_base_factor)",
                        "cohort": "active materials, same group/currency/base UOM",
                        "ratio_threshold": config.price_ratio,
                    },
                    "Check price-unit scaling, pack conversion, currency and contract validity before proposing a corrected price.",
                    "statistical",
                )

    seen = set()
    truncated_blocks, candidates = 0, 0
    for block_key, rows in sorted(blocks.items(), key=lambda item: str(item[0])):
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda row: row.material_id)
        if len(rows) > config.max_block_size:
            truncated_blocks += 1
            rows = rows[: config.max_block_size]
        vectors = embedder.encode([row.description for row in rows]) if block_key[0] == "similar" else None
        for (a, left), (b, right) in itertools.combinations(enumerate(rows), 2):
            pair = tuple(sorted((left.material_id, right.material_id)))
            if pair in seen:
                continue
            # Different known part numbers are a hard veto for lexical/semantic-only proposals.
            known_conflict = bool(
                left.manufacturer_part_number
                and right.manufacturer_part_number
                and canonical(left.manufacturer_part_number) != canonical(right.manufacturer_part_number)
            )
            part_match = bool(
                left.manufacturer
                and right.manufacturer
                and left.manufacturer_part_number
                and right.manufacturer_part_number
                and canonical(left.manufacturer) == canonical(right.manufacturer)
                and canonical(left.manufacturer_part_number) == canonical(right.manufacturer_part_number)
            )
            exact = canonical(left.description) == canonical(right.description)
            if known_conflict and not part_match:
                continue
            candidates += 1
            score = float(vectors[a] @ vectors[b]) if vectors is not None else (1.0 if exact else 0.97)
            if not part_match and not exact and score < config.similarity_threshold:
                continue
            seen.add(pair)
            method = "rule" if part_match or exact else embedder.kind
            emit(
                "duplicate",
                "high" if part_match else "medium",
                [left, right],
                "Potential duplicate material",
                {
                    "left_description": left.description,
                    "right_description": right.description,
                    "manufacturer_part_match": part_match,
                    "normalized_description_match": exact,
                    "base_uom_match": left.base_uom == right.base_uom,
                    "lifecycle_match": left.lifecycle == right.lifecycle,
                    "sources": [left.source_system, right.source_system],
                    "similarity": round(min(score, 1), 4),
                    "embedding_model": embedder.name if method != "rule" else None,
                    "threshold": config.similarity_threshold,
                    "review_required": True,
                },
                "Compare technical specifications, stock, open orders and approved vendors. Propose a surviving record only after steward approval; no automatic merge.",
                method,
                min(max(score, 0), 1),
            )
    ordered = sorted(
        findings.values(), key=lambda item: (SEVERITY[item.severity], item.kind, item.finding_id)
    )
    return ordered, {
        "algorithm_version": ALGORITHM_VERSION,
        "embedding_model": embedder.name,
        "records": len(records),
        "candidate_pairs": candidates,
        "truncated_blocks": truncated_blocks,
        "config": vars(config),
        "warning": "Oversized candidate blocks were truncated; recall may be reduced"
        if truncated_blocks
        else None,
    }
