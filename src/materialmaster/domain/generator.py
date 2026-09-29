"""Fixed-seed synthetic ERP snapshots with a separate, never-ingested truth file."""

import json
import random
from pathlib import Path

GROUPS = [
    ("Fasteners", "Hex bolt zinc plated", "EA", 2.4),
    ("Bearings", "Deep groove ball bearing", "EA", 28.0),
    ("Electrical", "Shielded control cable", "M", 4.8),
    ("Hydraulics", "Hydraulic pressure hose", "M", 16.0),
    ("Packaging", "Corrugated shipping carton", "EA", 3.2),
    ("Raw materials", "Stainless steel wire", "KG", 9.0),
]


def generate(count: int = 1200, seed: int = 42) -> tuple[list[dict], dict]:
    if not 20 <= count <= 1_000_000:
        raise ValueError("count must be between 20 and 1,000,000")
    rng = random.Random(seed)
    records = []
    truth: dict = {
        "seed": seed,
        "generator_version": "1.0",
        "duplicates": [],
        "uom": [],
        "price": [],
        "purchasing": [],
        "lifecycle": [],
        "lead_time": [],
    }
    sources = ["ERP-NORTH", "ERP-EU", "LEGACY-MRP"]
    for index in range(count):
        group, description, uom, price = GROUPS[index % len(GROUPS)]
        row = {
            "material_id": f"MAT-{index + 1:07d}",
            "source_system": sources[index % 3],
            "description": f"{description} {1000 + index} grade A",
            "material_group": group,
            "manufacturer": f"MFG-{index % 17:03d}",
            "manufacturer_part_number": f"P-{index + 10000}",
            "base_uom": uom,
            "order_uom": uom,
            "order_to_base_factor": "1",
            "unit_price": str(round(price * rng.uniform(0.85, 1.15), 2)),
            "price_unit": "1",
            "currency": "USD",
            "supplier_id": f"SUP-{index % 31:03d}",
            "purchasing_org": f"PO-{index % 4 + 1:02d}",
            "lead_time_days": rng.randint(4, 48),
            "minimum_order_qty": "1",
            "lifecycle": "ACTIVE",
            "procurement_blocked": False,
            "provenance": {"source_row": index + 1, "synthetic": True},
        }
        mode = index % 40
        if mode in (1, 2):
            original = records[index - mode]
            row = {
                **original,
                "material_id": row["material_id"],
                "source_system": sources[mode],
                "provenance": row["provenance"],
            }
            if mode == 2:
                row["description"] = (
                    original["description"]
                    .replace("Hex bolt", "Hexagonal blt")
                    .replace("Deep groove", "Deep-groove")
                    .replace("grade A", "GR A")
                )
                # Legacy source omits the part number: this pair must use text similarity.
                row["manufacturer_part_number"] = ""
            for previous in range(index - mode, index):
                truth["duplicates"].append(sorted([records[previous]["material_id"], row["material_id"]]))
        elif mode == 7:
            row["order_uom"] = "L" if uom != "KG" else "EA"
            truth["uom"].append(row["material_id"])
        elif mode == 12:
            row["unit_price"] = str(round(float(row["unit_price"]) * 14, 2))
            truth["price"].append(row["material_id"])
        elif mode == 18:
            row["supplier_id"] = None
            row["purchasing_org"] = None
            truth["purchasing"].append(row["material_id"])
        elif mode == 24:
            row["lifecycle"] = "OBSOLETE"
            truth["lifecycle"].append(row["material_id"])
        elif mode == 31:
            row["lead_time_days"] = 780
            truth["lead_time"].append(row["material_id"])
        records.append(row)
    truth["count"] = count
    return records, truth


def write_dataset(destination: Path, count: int, seed: int) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    records, truth = generate(count, seed)
    with (destination / "materials.jsonl").open("w") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    (destination / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    return {"records": count, "seed": seed, "path": str(destination)}
