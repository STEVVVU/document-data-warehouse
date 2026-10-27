import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: Identifier
    invoice_id: Identifier
    supplier_id: Identifier
    supplier_name: Label
    invoice_date: date
    sku: Identifier
    description: Label
    category: Label
    country: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    quantity: int = Field(ge=1, le=1_000_000)
    unit_price_cents: int = Field(ge=0, le=1_000_000_000)
    revision: int = Field(ge=1, default=1)
    deleted: bool = False

    @field_validator("invoice_date", mode="before")
    @classmethod
    def iso_date(cls, value):
        if type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("expected ISO date YYYY-MM-DD")
        return date.fromisoformat(value)

    @field_validator("quantity", "unit_price_cents", "revision", mode="before")
    @classmethod
    def exact_integer(cls, value):
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
        if type(value) is not int:
            raise ValueError("expected integer, not a boolean or floating point number")
        return value


class ExtractedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[Line] = Field(min_length=1, max_length=10000)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Identifier
    path: str
    kind: Literal["csv", "json", "document"]
    fixture_response: str | None = None
    mime_type: str | None = None


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[Source] = Field(min_length=1, max_length=100)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def confined(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("source paths must be existing files inside the manifest directory")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("source exceeds the 20 MiB bound")
    return path
