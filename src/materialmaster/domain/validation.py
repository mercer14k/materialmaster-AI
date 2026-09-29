import csv
import io
import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from materialmaster.domain.models import InvalidRow, Material, ValidationReport


def strict_json(value: str):
    def reject_constant(constant):
        raise ValueError(f"Non-finite JSON number {constant} is not allowed")

    return json.loads(value, parse_constant=reject_constant)


def validate_rows(rows: Iterable[Any]) -> ValidationReport:
    records, rejected = [], []
    seen: set[str] = set()
    for number, raw in enumerate(rows, 1):
        try:
            value = Material.model_validate(raw)
            if value.material_id in seen:
                raise ValueError("Duplicate material_id within dataset; use a source-qualified identifier")
            seen.add(value.material_id)
            records.append(value)
        except (ValidationError, ValueError) as error:
            errors = (
                error.errors(include_url=False, include_context=False, include_input=False)
                if isinstance(error, ValidationError)
                else [{"msg": str(error), "type": "duplicate_id"}]
            )
            rejected.append(InvalidRow(row_number=number, raw=raw, errors=errors))
    return ValidationReport(
        total=len(records) + len(rejected),
        valid_count=len(records),
        invalid_count=len(rejected),
        records=records,
        rejected=rejected,
    )


def parse_upload(content: bytes, suffix: str) -> list[Any]:
    text = content.decode("utf-8-sig")
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV requires unique column headers")
        output = []
        for row in reader:
            cleaned = {
                key if key is not None else "_extra_columns": (None if value == "" else value)
                for key, value in row.items()
            }
            for field in ("manufacturer", "manufacturer_part_number"):
                if field in cleaned and cleaned[field] is None:
                    cleaned[field] = ""
            if isinstance(cleaned.get("provenance"), str):
                try:
                    cleaned["provenance"] = strict_json(cleaned["provenance"])
                except ValueError:
                    pass  # The schema reports this row visibly as invalid.
            output.append(cleaned)
        return output
    if suffix == ".jsonl":
        output = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                output.append(strict_json(line))
            except ValueError:
                output.append({"_invalid_json_line": number, "_raw": line})
        return output
    value = strict_json(text)
    if not isinstance(value, list):
        raise ValueError("JSON must contain an array of material records")
    return value
