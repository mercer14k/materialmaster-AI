"""ERP-neutral, explicitly scoped material/purchasing contract."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> datetime:
    return datetime.now(UTC)


def utc_iso(value: datetime) -> str:
    """SQLite strips timezone metadata; every persisted timestamp is UTC."""
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


class Material(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    material_id: str = Field(min_length=1, max_length=80, pattern=r"^[\w.:-]+$")
    source_system: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=3, max_length=500)
    material_group: str = Field(min_length=1, max_length=80)
    manufacturer: str = Field(default="", max_length=100)
    manufacturer_part_number: str = Field(default="", max_length=100)
    base_uom: str = Field(min_length=1, max_length=10)
    order_uom: str = Field(min_length=1, max_length=10)
    order_to_base_factor: Decimal | None = Field(default=None, gt=0, le=1_000_000)
    unit_price: Decimal | None = Field(default=None, ge=0, le=1_000_000_000)
    price_unit: Decimal = Field(default=Decimal(1), gt=0, le=1_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    supplier_id: str | None = Field(default=None, max_length=80)
    purchasing_org: str | None = Field(default=None, max_length=40)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    minimum_order_qty: Decimal = Field(default=Decimal(1), gt=0, le=1_000_000)
    lifecycle: Literal["ACTIVE", "PHASE_OUT", "OBSOLETE"] = "ACTIVE"
    procurement_blocked: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("base_uom", "order_uom", mode="before")
    @classmethod
    def uppercase_uom(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class Finding(BaseModel):
    finding_id: str
    kind: Literal["duplicate", "uom", "price", "purchasing", "lifecycle", "lead_time"]
    severity: Literal["critical", "high", "medium", "low"]
    material_ids: list[str]
    title: str
    evidence: dict[str, Any]
    proposed_action: str
    method: Literal["rule", "statistical", "lexical_embedding", "semantic_embedding"] = "rule"
    score: float = Field(default=1, ge=0, le=1)


class InvalidRow(BaseModel):
    row_number: int
    raw: Any
    errors: list[dict[str, Any]]


class ValidationReport(BaseModel):
    total: int
    valid_count: int
    invalid_count: int
    records: list[Material]
    rejected: list[InvalidRow]


class ReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accepted", "rejected", "deferred"]
    reason: str = Field(min_length=5, max_length=1000)
    expected_version: int = Field(ge=0)


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["explained", "abstained"]
    summary: str = Field(max_length=2000)
    evidence_ids: list[str] = Field(max_length=20)
    normalization_suggestions: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    offset: int
    limit: int
