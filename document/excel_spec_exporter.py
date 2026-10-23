"""Spec-driven XLSX exporter: tables, computed columns, totals, summaries, KPIs, charts."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.table import Table, TableStyleInfo

from config.constants import DEFAULT_ACCENT_HEX, EXCEL_MAX_COL_WIDTH
from core.exceptions import ExportValidationError
from core.workbook_spec import (NUMERIC_TYPES, ChartSpec, Column, SheetSpec, SummarySpec,
                                TableSpec, Theme, WorkbookSpec)
from document.base_exporter import FileExporter
from document.formula_safety import write_text_cell
from document.formula_template import resolve_template
from document.spec_rules import check_spec
from document.template_registry import Template

_SUBTOTAL = {"sum": 109, "average": 101, "count": 103, "min": 105, "max": 104}
_DEFAULT_FMT = {"number": "#,##0.00", "integer": "#,##0", "currency": "#,##0.00",
                "percent": "0.0%", "date": "yyyy-mm-dd"}
_TONE_FILL = {"good": "C6EFCE", "warn": "FFEB9C", "bad": "FFC7CE"}
_TONE_FONT = {"good": "006100", "warn": "9C5700", "bad": "9C0006"}
_OPS = {"gt": "greaterThan", "gte": "greaterThanOrEqual", "lt": "lessThan",
        "lte": "lessThanOrEqual", "eq": "equal", "neq": "notEqual"}
_LABELS = {"ar": ("الإجمالي", "ملاحظات")}  # language -> (total, notes)
_TABLE_STYLE = "TableStyleLight1"
_CRITERIA_RE = re.compile(r"^[<>=]|[*?~]")
_MAX_GROUPS = 200
_CHART_W_CM, _CHART_H_CM, _CHART_ROW_STEP = 16, 8.5, 19
_SERIES_COLORS = ("70AD47", "ED7D31", "7F7F7F", "FFC000")
_BAD_TITLE_RE = re.compile(r"[\[\]:*?/\\]")


def _hex(value: Any, default: str) -> str:
    text = str(value or "").lstrip("#").upper()
    return text if re.fullmatch(r"[0-9A-F]{6}", text) else default


def _tint(color: str, amount: float) -> str:
    """Blend a hex color toward white."""
    chan = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(c + (255 - c) * amount):02X}" for c in chan)


def _quote(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _parse_date(text: str) -> date | datetime:
    text = text.strip()
    if len(text) == 10:
        return date.fromisoformat(text)
    return datetime.fromisoformat(text).replace(tzinfo=None)  # Excel has no time zones


@dataclass(frozen=True)
class _Palette:
    primary: str
    accent: str
    light: str

    @classmethod
    def build(cls, theme: Theme, default_primary: str) -> "_Palette":
        primary = _hex(theme.primary, default_primary)
        return cls(primary, _hex(theme.accent, "2E75B6"), _tint(primary, 0.88))


@dataclass(frozen=True)
class _Placed:
    """Where a table/summary landed, so formulas and charts can reference it."""
    ws: Any
    header_row: int
    first_row: int
    last_row: int
    columns: dict[str, int]  # key -> 1-based column

    @property
    def empty(self) -> bool:
        return self.last_row < self.first_row

    def rng(self, key: str) -> str:
        """Absolute cross-sheet data range of one column."""
        letter = get_column_letter(self.columns[key])
        return f"{_quote(self.ws.title)}!${letter}${self.first_row}:${letter}${self.last_row}"


class _Builder:
    """Builds one workbook from a validated spec (passes: tables, summaries, extras)."""

    def __init__(self, spec: WorkbookSpec, palette: _Palette, warnings: list[str]) -> None:
        self.spec, self.pal, self.warn = spec, palette, warnings
        lang = spec.metadata.language
        self.total_label, self.notes_label = _LABELS.get(lang, ("Total", "Notes"))
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.sheets: dict[str, Any] = {}
        self.tables: dict[str, TableSpec] = {}
        self.placed: dict[str, _Placed] = {}
        self.cursor: dict[str, int] = {}
        self.start: dict[str, int] = {}
        self.widths: dict[str, dict[int, int]] = {}

    def build(self) -> Workbook:
        used: set[str] = set()
        for sh in self.spec.sheets:
            self._open(sh, used)
        for sh in self.spec.sheets:
            for table in sh.tables:
                self._table(sh, table)
        for sh in self.spec.sheets:
            for summary in sh.summaries:
                self._summary(sh, summary)
        for sh in self.spec.sheets:
            self._kpis(sh)
            self._charts(sh)
            self._notes(sh)
            self._finish(sh)
        return self.wb

    # --- sheet setup ---
    @staticmethod
    def _title(name: str, used: set[str]) -> str:
        base = (_BAD_TITLE_RE.sub("_", name).strip() or "Sheet")[:31]
        title, n = base, 2
        while title.lower() in used:
            suffix = f" ({n})"
            title, n = base[:31 - len(suffix)] + suffix, n + 1
        used.add(title.lower())
        return title

    def _open(self, sh: SheetSpec, used: set[str]) -> None:
        ws = self.wb.create_sheet(self._title(sh.name, used))
        self.sheets[sh.name] = ws
        if self.spec.metadata.language == "ar":
            ws.sheet_view.rightToLeft = True
        ws.sheet_properties.tabColor = {"dashboard": self.pal.accent, "calc": "7F7F7F",
                                        "notes": "BFBFBF"}.get(sh.role, self.pal.primary)
        if sh.role == "dashboard":
            ws.sheet_view.showGridLines = False
            cell = ws.cell(1, 1)
            write_text_cell(cell, self.spec.metadata.title)
            cell.font = Font(size=16, bold=True, color=self.pal.primary)
        self.start[sh.name] = self.cursor[sh.name] = 7 if sh.kpis else (3 if sh.role == "dashboard" else 1)

    def _width(self, sheet: str, col: int, size: int) -> None:
        cols = self.widths.setdefault(sheet, {})
        cols[col] = max(cols.get(col, 0), size)

    # --- cell helpers ---
    def _header(self, cell: Any, text: str) -> None:
        write_text_cell(cell, text)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color=self.pal.primary)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _caption(self, ws: Any, row: int, text: str) -> int:
        cell = ws.cell(row, 1)
        write_text_cell(cell, text)
        cell.font = Font(bold=True, size=12, color=self.pal.primary)
        return row + 1

    def _set(self, cell: Any, col: Column, value: Any, where: str) -> int:
        """Write one typed value; invalid values become inert text plus a warning."""
        if value is None or value == "":
            return 0
        fmt = col.format or _DEFAULT_FMT.get(col.type, "")
        try:
            if col.type == "text":
                write_text_cell(cell, str(value))
                return len(str(value))
            if col.type in NUMERIC_TYPES:
                ok = (isinstance(value, (int, float)) and not isinstance(value, bool)
                      and math.isfinite(value))
                if not ok or (col.type == "integer" and float(value) != int(value)):
                    raise ValueError("not a valid number")
                cell.value = value
            elif col.type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError("not a boolean")
                cell.value = value
            else:  # date
                cell.value = _parse_date(str(value))
                if not col.format and isinstance(cell.value, datetime):
                    fmt = "yyyy-mm-dd hh:mm"
        except (ValueError, TypeError) as exc:
            write_text_cell(cell, str(value))
            self.warn.append(f"{where}: {col.type} value written as text ({exc}).")
            return len(str(value))
        if fmt:
            cell.number_format = fmt
        return len(str(value))

    def _total_style(self, ws: Any, row: int, ncols: int) -> None:
        for j in range(1, ncols + 1):
            cell = ws.cell(row, j)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", start_color=self.pal.light)
            cell.border = Border(top=Side(style="thin", color=self.pal.primary))

    # --- tables ---
    def _table(self, sh: SheetSpec, t: TableSpec) -> None:
        ws, name = self.sheets[sh.name], sh.name
        row = self.cursor[name]
        if t.title:
            row = self._caption(ws, row, t.title)
        head, first = row, row + 1
        last = head + len(t.rows)
        letters = {c.key: get_column_letter(j) for j, c in enumerate(t.columns, 1)}
        for j, col in enumerate(t.columns, 1):
            self._header(ws.cell(head, j), col.title)
            self._width(name, j, len(col.title))
        for i, raw in enumerate(t.rows):
            r = first + i
            refs = {k: f"{letter}{r}" for k, letter in letters.items()}
            for j, col in enumerate(t.columns, 1):
                cell = ws.cell(r, j)
                if col.formula:  # template already passed the formula policy
                    cell.value = resolve_template(col.formula, refs)
                    fmt = col.format or _DEFAULT_FMT.get(col.type, "")
                    if fmt:
                        cell.number_format = fmt
                    self._width(name, j, 12)
                else:
                    size = self._set(cell, col, raw[j - 1] if j <= len(raw) else None,
                                     f"{ws.title}!{letters[col.key]}{r}")
                    self._width(name, j, size)
        if t.rows:
            ref = f"A{head}:{get_column_letter(len(t.columns))}{last}"
            table = Table(displayName=f"tbl_{t.name}", ref=ref)
            table.tableStyleInfo = TableStyleInfo(name=_TABLE_STYLE, showRowStripes=True)
            ws.add_table(table)
            for col in t.columns:
                rng = f"{letters[col.key]}{first}:{letters[col.key]}{last}"
                self._conditional(ws, col, rng)
                self._validation(ws, col, rng)
        end = last
        if t.totals and t.rows:
            end = last + 1
            totals = dict(t.totals)
            for j, col in enumerate(t.columns, 1):
                cell, agg = ws.cell(end, j), totals.get(col.key)
                if agg:
                    letter = letters[col.key]
                    cell.value = f"=SUBTOTAL({_SUBTOTAL[agg]},{letter}{first}:{letter}{last})"
                    cell.number_format = ("#,##0" if agg == "count"
                                          else col.format or _DEFAULT_FMT.get(col.type, "General"))
                elif j == 1:
                    write_text_cell(cell, self.total_label)
            self._total_style(ws, end, len(t.columns))
        self.tables[t.name.lower()] = t
        self.placed[t.name.lower()] = _Placed(
            ws, head, first, last, {c.key: j for j, c in enumerate(t.columns, 1)})
        self.cursor[name] = end + 3

    def _conditional(self, ws: Any, col: Column, rng: str) -> None:
        cond = col.conditional
        if cond is None:
            return
        if cond.kind == "color_scale":
            ws.conditional_formatting.add(rng, ColorScaleRule(
                start_type="min", start_color="FFFFFF", end_type="max", end_color=self.pal.accent))
        elif cond.kind == "data_bar":
            ws.conditional_formatting.add(rng, DataBarRule(
                start_type="min", end_type="max", color=self.pal.accent, showValue=True))
        elif cond.kind == "cell_rule" and cond.op in _OPS and cond.value is not None:
            fill = PatternFill(start_color=_TONE_FILL[cond.tone], end_color=_TONE_FILL[cond.tone],
                               fill_type="solid")
            ws.conditional_formatting.add(rng, CellIsRule(
                operator=_OPS[cond.op], formula=[repr(float(cond.value))], fill=fill,
                font=Font(color=_TONE_FONT[cond.tone])))

    @staticmethod
    def _validation(ws: Any, col: Column, rng: str) -> None:
        if not col.options:
            return
        dv = DataValidation(type="list", formula1='"' + ",".join(col.options) + '"',
                            allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(rng)

    # --- summaries ---
    @staticmethod
    def _labels(table: TableSpec, index: int) -> list[Any]:
        """Unique group values in first-appearance order (taken from the data, never invented)."""
        seen: set[Any] = set()
        out: list[Any] = []
        for row in table.rows:
            value = row[index] if index < len(row) else None
            if value is not None and value != "" and value not in seen:
                seen.add(value)
                out.append(value)
        return out

    def _summary(self, sh: SheetSpec, s: SummarySpec) -> None:
        ws, name = self.sheets[sh.name], sh.name
        src, table = self.placed[s.source.lower()], self.tables[s.source.lower()]
        by_key = {c.key: c for c in table.columns}
        labels = self._labels(table, src.columns[s.group_by] - 1)
        if src.empty or not labels or len(labels) > _MAX_GROUPS:
            self.warn.append(f"Summary '{s.name}' was skipped: no usable groups "
                             f"(needs 1-{_MAX_GROUPS} distinct values).")
            return
        row = self.cursor[name]
        if s.title:
            row = self._caption(ws, row, s.title)
        head, first = row, row + 1
        last = head + len(labels)
        group = by_key[s.group_by]
        self._header(ws.cell(head, 1), group.title)
        columns = {s.group_by: 1}
        for j, m in enumerate(s.metrics, 2):
            title = m.title or f"{m.agg.capitalize()} of {by_key[m.column].title}"
            self._header(ws.cell(head, j), title)
            columns[f"{m.agg}_{m.column}"] = j
            self._width(name, j, max(len(title), 14))
        self._width(name, 1, len(group.title))
        grp = src.rng(s.group_by)
        for i, label in enumerate(labels):
            r = first + i
            size = self._set(ws.cell(r, 1), group, label, f"{ws.title}!A{r}")
            self._width(name, 1, size)
            if _CRITERIA_RE.search(str(label)):
                self.warn.append(f"Summary '{s.name}': group '{label}' contains criteria "
                                 "characters and may be matched incorrectly.")
            for j, m in enumerate(s.metrics, 2):
                val = src.rng(m.column)
                cell = ws.cell(r, j)
                if m.agg == "sum":
                    cell.value = f"=SUMIFS({val},{grp},$A{r})"
                elif m.agg == "average":
                    cell.value = f'=IFERROR(AVERAGEIFS({val},{grp},$A{r}),"")'
                else:
                    cell.value = f"=COUNTIFS({grp},$A{r})"
                col = by_key[m.column]
                cell.number_format = ("#,##0" if m.agg == "count"
                                      else col.format or _DEFAULT_FMT.get(col.type, "General"))
        end = last
        if any(m.agg in ("sum", "count") for m in s.metrics):
            end = last + 1
            write_text_cell(ws.cell(end, 1), self.total_label)
            for j, m in enumerate(s.metrics, 2):
                if m.agg in ("sum", "count"):
                    letter = get_column_letter(j)
                    cell = ws.cell(end, j)
                    cell.value = f"=SUBTOTAL(109,{letter}{first}:{letter}{last})"
                    cell.number_format = ws.cell(first, j).number_format
            self._total_style(ws, end, len(s.metrics) + 1)
        self.placed[s.name.lower()] = _Placed(ws, head, first, last, columns)
        self.cursor[name] = end + 3

    # --- KPI cards, charts, notes ---
    def _kpis(self, sh: SheetSpec) -> None:
        ws, name = self.sheets[sh.name], sh.name
        for k, kpi in enumerate(sh.kpis, 1):
            src, table = self.placed[kpi.source.lower()], self.tables[kpi.source.lower()]
            if src.empty:
                self.warn.append(f"KPI '{kpi.label}' was skipped: its table has no rows.")
                continue
            col = next(c for c in table.columns if c.key == kpi.column)
            label, value = ws.cell(3, k), ws.cell(4, k)
            write_text_cell(label, kpi.label)
            value.value = f"=SUBTOTAL({_SUBTOTAL[kpi.agg]},{src.rng(kpi.column)})"
            value.number_format = kpi.format or ("#,##0" if kpi.agg == "count"
                                                 else _DEFAULT_FMT.get(col.type, "#,##0"))
            label.font = Font(size=9, color="595959")
            value.font = Font(size=20, bold=True, color=self.pal.primary)
            side = Side(style="thick", color="FFFFFF")
            for cell in (label, value):
                cell.fill = PatternFill("solid", start_color=self.pal.light)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = Border(left=side, right=side)
            self._width(name, k, 22)
        ws.row_dimensions[4].height = 34

    def _make_chart(self, spec: ChartSpec) -> Any:
        if spec.type == "pie":
            chart = PieChart()
            chart.dataLabels = DataLabelList()
            chart.dataLabels.showPercent = True
        elif spec.type == "line":
            chart = LineChart()
        else:
            chart = BarChart()
            chart.type = "col" if spec.type == "column" else "bar"
        chart.title = spec.title
        if spec.type != "pie":
            chart.x_axis.title = spec.x_title or None
            chart.y_axis.title = spec.y_title or None
            chart.x_axis.delete = chart.y_axis.delete = False  # axes are hidden otherwise
        chart.width, chart.height = _CHART_W_CM, _CHART_H_CM
        return chart

    def _color_series(self, chart: Any, spec: ChartSpec) -> None:
        if spec.type == "pie":
            return
        palette = (self.pal.primary, self.pal.accent, *_SERIES_COLORS)
        for series, color in zip(chart.series, palette):
            if spec.type == "line":
                series.graphicalProperties.line.solidFill = color
                series.smooth = False
            else:
                series.graphicalProperties.solidFill = color

    def _charts(self, sh: SheetSpec) -> None:
        ws, name = self.sheets[sh.name], sh.name
        has_data = bool(sh.tables or sh.summaries)
        if sh.charts and not has_data:
            for col in range(1, 9):  # even grid so side-by-side charts do not overlap
                self._width(name, col, 22)
        for slot, spec in enumerate(sh.charts):
            src = self.placed.get(spec.source.lower())
            if src is None or src.empty:
                self.warn.append(f"Chart '{spec.title}' was skipped: its source has no data.")
                continue
            chart = self._make_chart(spec)
            for key in spec.values:
                chart.add_data(Reference(src.ws, min_col=src.columns[key],
                                         min_row=src.header_row, max_row=src.last_row),
                               titles_from_data=True)
            chart.set_categories(Reference(src.ws, min_col=src.columns[spec.category],
                                           min_row=src.first_row, max_row=src.last_row))
            self._color_series(chart, spec)
            if has_data:  # to the right of the tables
                col = max(self.widths.get(name, {1: 1})) + 2
                anchor = f"{get_column_letter(col)}{self.start[name] + slot * _CHART_ROW_STEP}"
            else:  # two-per-row dashboard grid
                col = 1 if slot % 2 == 0 else 5
                anchor = f"{get_column_letter(col)}{self.start[name] + (slot // 2) * _CHART_ROW_STEP}"
            ws.add_chart(chart, anchor)

    def _notes(self, sh: SheetSpec) -> None:
        if not sh.notes:
            return
        ws, name = self.sheets[sh.name], sh.name
        row = self._caption(ws, self.cursor[name], self.notes_label)
        for text in sh.notes:
            cell = ws.cell(row, 1)
            write_text_cell(cell, text)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            self._width(name, 1, min(len(text), 80))
            row += 1
        self.cursor[name] = row + 1

    def _finish(self, sh: SheetSpec) -> None:
        ws = self.sheets[sh.name]
        for col, size in self.widths.get(sh.name, {}).items():
            ws.column_dimensions[get_column_letter(col)].width = max(
                10, min(size + 2, EXCEL_MAX_COL_WIDTH))
        if len(sh.tables) == 1 and not (sh.summaries or sh.kpis or sh.notes):
            placed = self.placed[sh.tables[0].name.lower()]
            if not placed.empty:
                ws.freeze_panes = f"A{placed.first_row}"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


class SpecExcelExporter(FileExporter):
    extension = ".xlsx"
    content_type = WorkbookSpec
    features = frozenset({"tables", "computed_columns", "totals", "summaries", "kpis", "charts",
                          "data_validation", "conditional_formatting", "rtl"})

    def __init__(self, template: Template) -> None:
        self._default_primary = _hex(template.excel.get("header_fill"), DEFAULT_ACCENT_HEX)

    def _write(self, content: WorkbookSpec, path: Path, warnings: list[str]) -> None:
        issues = check_spec(content)
        if issues:
            raise ExportValidationError("Invalid workbook spec: " + "; ".join(str(i) for i in issues[:5]))
        palette = _Palette.build(content.theme, self._default_primary)
        wb = _Builder(content, palette, warnings).build()
        wb.properties.title = content.metadata.title
        wb.properties.creator = content.metadata.author or "Document Builder AI"
        wb.save(str(path))

    def _verify(self, path: Path) -> None:
        wb = load_workbook(str(path))
        try:
            if not wb.sheetnames:
                raise ValueError("workbook has no sheets")
        finally:
            wb.close()