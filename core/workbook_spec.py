"""Table-centric workbook spec (v2): the AI describes, the exporter builds."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from core.models import Metadata

SPEC_VERSION = "2.0"
ColType = Literal["text", "number", "integer", "currency", "percent", "date", "boolean"]
NUMERIC_TYPES = frozenset({"number", "integer", "currency", "percent"})


@dataclass(frozen=True)
class Theme:
    primary: str = ""
    accent: str = ""


@dataclass(frozen=True)
class Conditional:
    kind: Literal["color_scale", "data_bar", "cell_rule"]
    op: str = ""
    value: float | None = None
    tone: Literal["good", "warn", "bad"] = "bad"


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    type: ColType = "text"
    format: str = ""
    formula: str = ""  # row template such as "{qty}*{price}" (no leading '=')
    options: tuple[str, ...] = ()
    conditional: Conditional | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Any, ...], ...]
    totals: tuple[tuple[str, str], ...] = ()  # (column key, aggregation)
    title: str = ""


@dataclass(frozen=True)
class Metric:
    column: str
    agg: str
    title: str = ""


@dataclass(frozen=True)
class SummarySpec:
    """Group-by table built with SUMIFS/COUNTIFS/AVERAGEIFS formulas."""
    name: str
    source: str
    group_by: str
    metrics: tuple[Metric, ...]
    title: str = ""


@dataclass(frozen=True)
class Kpi:
    label: str
    source: str
    column: str
    agg: str
    format: str = ""


@dataclass(frozen=True)
class ChartSpec:
    """Chart bound to a table or summary; never carries its own data."""
    type: Literal["column", "bar", "line", "pie"]
    title: str
    source: str
    category: str
    values: tuple[str, ...]
    x_title: str = ""
    y_title: str = ""


@dataclass(frozen=True)
class SheetSpec:
    name: str
    role: Literal["data", "calc", "dashboard", "notes"] = "data"
    tables: tuple[TableSpec, ...] = ()
    summaries: tuple[SummarySpec, ...] = ()
    kpis: tuple[Kpi, ...] = ()
    charts: tuple[ChartSpec, ...] = ()
    notes: tuple[str, ...] = ()


def _column(d: dict[str, Any]) -> Column:
    c = d.get("conditional")
    cond = Conditional(c["kind"], c.get("op", ""), c.get("value"), c.get("tone", "bad")) if c else None
    return Column(d["key"], d["title"], d.get("type", "text"), d.get("format", ""),
                  d.get("formula", ""), tuple(d.get("options", ())), cond)


def _table(d: dict[str, Any]) -> TableSpec:
    return TableSpec(d["name"], tuple(_column(c) for c in d["columns"]),
                     tuple(tuple(r) for r in d["rows"]),
                     tuple(d.get("totals", {}).items()), d.get("title", ""))


def _summary(d: dict[str, Any]) -> SummarySpec:
    metrics = tuple(Metric(m["column"], m["agg"], m.get("title", "")) for m in d["metrics"])
    return SummarySpec(d["name"], d["source"], d["group_by"], metrics, d.get("title", ""))


def _sheet(d: dict[str, Any]) -> SheetSpec:
    return SheetSpec(
        d["name"], d.get("role", "data"),
        tuple(_table(t) for t in d.get("tables", [])),
        tuple(_summary(s) for s in d.get("summaries", [])),
        tuple(Kpi(k["label"], k["source"], k["column"], k["agg"], k.get("format", ""))
              for k in d.get("kpis", [])),
        tuple(ChartSpec(c["type"], c["title"], c["source"], c["category"], tuple(c["values"]),
                        c.get("x_title", ""), c.get("y_title", "")) for c in d.get("charts", [])),
        tuple(d.get("notes", ())))


@dataclass
class WorkbookSpec:
    metadata: Metadata = field(default_factory=Metadata)
    sheets: list[SheetSpec] = field(default_factory=list)
    theme: Theme = field(default_factory=Theme)
    needs_review: bool = False
    schema_version: str = SPEC_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, needs_review: bool = False) -> "WorkbookSpec":
        """Build from schema-validated data."""
        meta, theme = data.get("metadata", {}), data.get("theme", {})
        return cls(Metadata(meta.get("title", ""), meta.get("language", "en"), meta.get("author", "")),
                   [_sheet(s) for s in data.get("sheets", [])],
                   Theme(theme.get("primary", ""), theme.get("accent", "")),
                   needs_review, data.get("schema_version", SPEC_VERSION))