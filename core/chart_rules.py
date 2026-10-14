"""Semantic chart checks: the schema checks shape, this checks references."""
from __future__ import annotations

from core.models import ChartSpec, Sheet, WorkbookContentModel
from core.schema_validator import ValidationIssue


def norm(name: str) -> str:
    """Case/space-insensitive key for sheet and column names."""
    return name.strip().lower()


def find_sheet(wb: WorkbookContentModel, name: str) -> Sheet | None:
    return next((s for s in wb.sheets if norm(s.name) == norm(name)), None)


def find_column(sheet: Sheet, name: str) -> int | None:
    """Zero-based index of the first matching column, or None."""
    target = norm(name)
    return next((i for i, c in enumerate(sheet.columns) if norm(c) == target), None)


def _numeric_problem(sheet: Sheet, index: int) -> str | None:
    used = [row[index] for row in sheet.rows
            if index < len(row) and row[index].type != "blank" and row[index].value is not None]
    if not used:
        return "has no values"
    if any(c.type != "number" for c in used):
        return "contains non-numeric cells"
    return None


def chart_problems(sheet: Sheet | None, spec: ChartSpec) -> list[str]:
    """Reasons the chart cannot be drawn; empty list means OK."""
    if sheet is None:
        return [f"sheet '{spec.sheet}' does not exist"]
    problems: list[str] = []
    if not sheet.rows:
        problems.append("the sheet has no data rows")
    if find_column(sheet, spec.category_column) is None:
        problems.append(f"category column '{spec.category_column}' not found")
    if spec.type == "pie" and len(spec.value_columns) != 1:
        problems.append("a pie chart needs exactly one value column")
    for name in spec.value_columns:
        idx = find_column(sheet, name)
        if idx is None:
            problems.append(f"value column '{name}' not found")
        elif (issue := _numeric_problem(sheet, idx)):
            problems.append(f"value column '{name}' {issue}")
    return problems


def check_charts(wb: WorkbookContentModel) -> list[ValidationIssue]:
    """Validate every chart against the workbook data."""
    return [ValidationIssue(f"charts/{i}", f"Chart '{spec.title}': {problem}")
            for i, spec in enumerate(wb.charts)
            for problem in chart_problems(find_sheet(wb, spec.sheet), spec)]