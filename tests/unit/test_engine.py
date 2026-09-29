from decimal import Decimal

import pytest

from materialmaster.ai.embeddings import LexicalEmbedder
from materialmaster.domain.engine import EngineConfig, analyze, normalized_price, uom_issues
from materialmaster.domain.generator import generate
from materialmaster.domain.models import Material
from materialmaster.domain.validation import parse_upload, validate_rows


def record(**updates):
    rows, _ = generate(20)
    return Material.model_validate({**rows[0], **updates})


def test_seed_is_reproducible():
    assert generate(400, 42) == generate(400, 42)
    assert generate(400, 42) != generate(400, 43)


def test_injected_truth_detected():
    rows, truth = generate(1200)
    findings, metadata = analyze(validate_rows(rows).records)
    assert metadata["truncated_blocks"] == 0
    predicted = {tuple(item.material_ids) for item in findings if item.kind == "duplicate"}
    actual = {tuple(pair) for pair in truth["duplicates"]}
    assert predicted <= actual  # Precision on this fixture; recall is measured, not assumed.
    assert len(predicted) / len(actual) >= 0.75
    assert any(item.method == "lexical_embedding" for item in findings)
    for kind in ("uom", "price", "purchasing", "lifecycle", "lead_time"):
        assert {item.material_ids[0] for item in findings if item.kind == kind} == set(truth[kind])


def test_engine_is_order_independent():
    rows = validate_rows(generate(240)[0]).records
    assert analyze(rows)[0] == analyze(list(reversed(rows)))[0]


@pytest.mark.parametrize(
    ("base", "order", "factor", "valid"),
    [
        ("KG", "G", ".001", True),
        ("G", "KG", "1000", True),
        ("EA", "BOX", "12", True),
        ("EA", "EA", "12", False),
        ("EA", "L", "1", False),
        ("KG", "EA", "1", False),
        ("M", "CM", ".01", True),
        ("EA", "ZZ", "1", False),
        ("EA", "BOX", None, False),
    ],
)
def test_uom_dimensions_and_conversion(base, order, factor, valid):
    row = record(base_uom=base, order_uom=order, order_to_base_factor=factor)
    assert bool(uom_issues(row)) is not valid


def test_price_unit_and_pack_conversion():
    row = record(unit_price="240", price_unit="10", base_uom="EA", order_uom="BOX", order_to_base_factor="12")
    assert normalized_price(row) == 2


def test_incompatible_uom_never_enters_price_cohort():
    assert normalized_price(record(order_uom="L")) is None


def test_no_comparable_peers_no_price_inference():
    findings, _ = analyze([record(unit_price="999999")])
    assert not any(item.kind == "price" for item in findings)


def test_cohorts_do_not_mix_currency_or_base_unit():
    rows = [
        record(material_id=f"P{i}", manufacturer_part_number=f"P{i}", description=f"Part {i}", unit_price="5")
        for i in range(12)
    ]
    rows += [
        record(material_id="EUR", unit_price="1000", currency="EUR"),
        record(material_id="KG", unit_price="1000", base_uom="KG", order_uom="KG"),
    ]
    assert not any(item.kind == "price" for item in analyze(rows)[0])


def test_known_part_conflict_vetoes_embedding_match():
    left = record(description="Stainless bolt 20 mm", manufacturer_part_number="ABC-1")
    right = record(material_id="OTHER", description="Stainless bolt 20 mm", manufacturer_part_number="ABC-2")
    assert not any(item.kind == "duplicate" for item in analyze([left, right])[0])


def test_numeric_specification_block_prevents_size_merge():
    left = record(description="Steel bolt 20 mm", manufacturer_part_number="")
    right = record(material_id="OTHER", description="Steel bolt 25 mm", manufacturer_part_number="")
    assert not any(item.kind == "duplicate" for item in analyze([left, right])[0])


def test_lexical_embedding_produces_review_candidate_without_identity_anchor():
    left = record(description="Steel hydraulic hose 20 mm reinforced", manufacturer_part_number="")
    right = record(
        material_id="OTHER", description="Reinforced steel hydraulic hose 20 mm", manufacturer_part_number=""
    )
    findings, _ = analyze([left, right])
    assert findings[0].method == "lexical_embedding"
    assert findings[0].evidence["review_required"] is True


def test_semantic_adapter_contract_uses_same_hard_rules():
    class StubSemantic(LexicalEmbedder):
        kind = "semantic_embedding"
        name = "test-only-semantic-stub"

    left = record(description="Stainless hose 20 mm reinforced", manufacturer_part_number="")
    right = record(
        material_id="OTHER", description="Reinforced stainless hose 20 mm", manufacturer_part_number=""
    )
    result = analyze([left, right], embedder=StubSemantic())[0]
    assert result[0].method == "semantic_embedding"


def test_oversized_blocks_emit_recall_warning():
    rows = [record(material_id=f"M{i}") for i in range(100)]
    _, metadata = analyze(rows, EngineConfig(max_block_size=10))
    assert metadata["truncated_blocks"] > 0
    assert metadata["warning"]


def test_obsolete_blocked_is_not_lifecycle_conflict():
    assert not any(
        item.kind == "lifecycle"
        for item in analyze([record(lifecycle="OBSOLETE", procurement_blocked=True)])[0]
    )


def test_zero_price_flagged_and_none_is_missing():
    rows = [
        record(
            material_id=f"R{i}", description=f"Bolt {i}", manufacturer_part_number=f"P{i}", unit_price="10"
        )
        for i in range(15)
    ]
    rows[0] = rows[0].model_copy(update={"unit_price": Decimal(0)})
    rows[1] = rows[1].model_copy(update={"unit_price": None})
    findings = analyze(rows)[0]
    assert any(item.kind == "price" and item.material_ids == ["R0"] for item in findings)
    assert any(item.kind == "purchasing" and item.material_ids == ["R1"] for item in findings)


def test_invalid_rows_and_id_collisions_never_disappear():
    raw = record().model_dump(mode="json")
    report = validate_rows([raw, {**raw, "unit_price": "NaN"}, raw, {"bad": "row"}])
    assert (report.total, report.valid_count, report.invalid_count) == (4, 1, 3)
    assert [row.row_number for row in report.rejected] == [2, 3, 4]


def test_malformed_jsonl_is_quarantined():
    rows = parse_upload(b'{"bad": 1}\nnot-json\n', ".jsonl")
    assert validate_rows(rows).invalid_count == 2


def test_csv_duplicate_headers_rejected():
    with pytest.raises(ValueError, match="unique"):
        parse_upload(b"material_id,material_id\na,b\n", ".csv")


@pytest.mark.parametrize("count", [0, 19, 1_000_001])
def test_generator_bounds(count):
    with pytest.raises(ValueError):
        generate(count)
