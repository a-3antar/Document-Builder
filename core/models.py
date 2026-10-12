"""Typed domain models, separate from raw AI responses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from config.constants import SCHEMA_VERSION

CellType = Literal["text", "number", "date", "boolean", "blank", "formula"]


@dataclass(frozen=True)
class Metadata:
    title: str = ""
    language: str = "en"  # "en", "ar", or "mixed"
    author: str = ""


@dataclass(frozen=True)
class Heading:
    text: str
    level: int = 1


@dataclass(frozen=True)
class Paragraph:
    text: str
    direction: Literal["auto", "ltr", "rtl"] = "auto"


@dataclass(frozen=True)
class ListBlock:
    items: tuple[str, ...]
    ordered: bool = False


@dataclass(frozen=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    caption: str = ""


Block = Heading | Paragraph | ListBlock | Table


@dataclass
class DocumentContentModel:
    metadata: Metadata = field(default_factory=Metadata)
    blocks: list[Block] = field(default_factory=list)
    needs_review: bool = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, needs_review: bool = False) -> "DocumentContentModel":
        """Build from schema-validated data."""
        meta = data.get("metadata", {})
        blocks: list[Block] = []
        for raw in data.get("blocks", []):
            kind = raw["type"]
            if kind == "heading":
                blocks.append(Heading(raw["text"], raw.get("level", 1)))
            elif kind == "paragraph":
                blocks.append(Paragraph(raw["text"], raw.get("direction", "auto")))
            elif kind == "list":
                blocks.append(ListBlock(tuple(raw["items"]), raw.get("ordered", False)))
            elif kind == "table":
                blocks.append(Table(
                    tuple(raw["headers"]),
                    tuple(tuple(r) for r in raw["rows"]),
                    raw.get("caption", ""),
                ))
        return cls(
            Metadata(meta.get("title", ""), meta.get("language", "en"), meta.get("author", "")),
            blocks,
            needs_review,
            data.get("schema_version", SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for b in self.blocks:
            if isinstance(b, Heading):
                out.append({"type": "heading", "text": b.text, "level": b.level})
            elif isinstance(b, Paragraph):
                out.append({"type": "paragraph", "text": b.text, "direction": b.direction})
            elif isinstance(b, ListBlock):
                out.append({"type": "list", "items": list(b.items), "ordered": b.ordered})
            elif isinstance(b, Table):
                out.append({"type": "table", "headers": list(b.headers),
                            "rows": [list(r) for r in b.rows], "caption": b.caption})
        return {
            "schema_version": self.schema_version,
            "metadata": {"title": self.metadata.title, "language": self.metadata.language,
                         "author": self.metadata.author},
            "blocks": out,
        }


@dataclass(frozen=True)
class Cell:
    type: CellType
    value: Any = None
    number_format: str = ""


@dataclass(frozen=True)
class Sheet:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    freeze_header: bool = True


@dataclass
class WorkbookContentModel:
    metadata: Metadata = field(default_factory=Metadata)
    sheets: list[Sheet] = field(default_factory=list)
    needs_review: bool = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, needs_review: bool = False) -> "WorkbookContentModel":
        meta = data.get("metadata", {})
        sheets = [
            Sheet(
                s["name"],
                tuple(s["columns"]),
                tuple(tuple(Cell(c["type"], c.get("value"), c.get("number_format", "")) for c in row)
                      for row in s["rows"]),
                s.get("freeze_header", True),
            )
            for s in data.get("sheets", [])
        ]
        return cls(Metadata(meta.get("title", ""), meta.get("language", "en"), meta.get("author", "")),
                   sheets, needs_review, data.get("schema_version", SCHEMA_VERSION))


@dataclass(frozen=True)
class OcrSegment:
    text: str
    confidence: float | None = None  # None when the engine gives none
    uncertain: bool = False


@dataclass
class OCRResult:
    """Original OCR text kept apart from AI-corrected text."""
    source: str
    engine: str
    original_text: str
    corrected_text: str | None = None
    segments: list[OcrSegment] = field(default_factory=list)
