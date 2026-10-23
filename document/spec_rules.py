"""Semantic checks for WorkbookSpec: the schema checks shape, this checks references."""
from __future__ import annotations

from core.exceptions import FormulaPolicyError
from core.schema_validator import ValidationIssue
from core.workbook_spec import NUMERIC_TYPES, Column, TableSpec, WorkbookSpec
from document.formula_template import template_keys, validate_template

_MAX_OPTIONS_CHARS = 250


def _agg_problem(agg: str, col: Column) -> str | None:
    if agg != "count" and col.type not in NUMERIC_TYPES:
        return f"'{agg}' needs a numeric column, but '{col.key}' is {col.type}"
    return None


def _check_column(p: str, col: Column, by_key: dict[str, Column], bad) -> None:
    if col.formula:
        try:
            validate_template(col.formula)
        except FormulaPolicyError as exc:
            bad(p, str(exc))
        else:
            for key in template_keys(col.formula):
                ref = by_key.get(key)
                if ref is None:
                    bad(p, f"formula uses unknown column '{key}'")
                elif ref.formula:
                    bad(p, f"formula may not use computed column '{key}'")
    if col.options:
        if col.type != "text":
            bad(p, "options are only allowed on text columns")
        elif (any("," in o or '"' in o for o in col.options)
              or sum(len(o) + 1 for o in col.options) > _MAX_OPTIONS_CHARS):
            bad(p, "options must not contain commas or quotes and must stay short")
    cond = col.conditional
    if cond and col.type not in NUMERIC_TYPES:
        bad(p, "conditional formatting needs a numeric column")
    if cond and cond.kind == "cell_rule" and (not cond.op or cond.value is None):
        bad(p, "cell_rule needs 'op' and 'value'")


def _check_table(p: str, t: TableSpec, bad) -> None:
    keys = [c.key for c in t.columns]
    titles = [c.title.strip().lower() for c in t.columns]
    if len(set(keys)) != len(keys):
        bad(p, "duplicate column keys")
    if len(set(titles)) != len(titles):
        bad(p, "duplicate column titles")
    by_key = {c.key: c for c in t.columns}
    for i, col in enumerate(t.columns):
        _check_column(f"{p}/columns/{i}", col, by_key, bad)
    for i, row in enumerate(t.rows):
        if len(row) != len(t.columns):
            bad(f"{p}/rows/{i}", f"expected {len(t.columns)} values, got {len(row)}")
    for key, agg in t.totals:
        col = by_key.get(key)
        if col is None:
            bad(f"{p}/totals", f"unknown column '{key}'")
        elif (problem := _agg_problem(agg, col)):
            bad(f"{p}/totals", problem)


def check_spec(spec: WorkbookSpec) -> list[ValidationIssue]:
    """Return every reference/consistency problem; an empty list means OK."""
    issues: list[ValidationIssue] = []

    def bad(path: str, message: str) -> None:
        issues.append(ValidationIssue(path, message))

    sheets: set[str] = set()
    tables: dict[str, TableSpec] = {}
    sources: dict[str, dict[str, str]] = {}  # source name -> {column key: type}
    has_rows: dict[str, bool] = {}

    # Pass 1: sheets and tables (all must exist before anything references them).
    for si, sh in enumerate(spec.sheets):
        if sh.name.strip().lower() in sheets:
            bad(f"sheets/{si}", f"duplicate sheet name '{sh.name}'")
        sheets.add(sh.name.strip().lower())
        for ti, t in enumerate(sh.tables):
            p = f"sheets/{si}/tables/{ti}"
            if t.name.lower() in sources:
                bad(p, f"duplicate table/summary name '{t.name}'")
            tables[t.name.lower()] = t
            sources[t.name.lower()] = {c.key: c.type for c in t.columns}
            has_rows[t.name.lower()] = bool(t.rows)
            _check_table(p, t, bad)

    # Pass 2: summaries (they become chart sources).
    for si, sh in enumerate(spec.sheets):
        for mi, s in enumerate(sh.summaries):
            p = f"sheets/{si}/summaries/{mi}"
            if s.name.lower() in sources:
                bad(p, f"duplicate table/summary name '{s.name}'")
            src = tables.get(s.source.lower())
            if src is None:
                bad(p, f"source table '{s.source}' not found")
                continue
            by_key = {c.key: c for c in src.columns}
            group = by_key.get(s.group_by)
            if group is None:
                bad(p, f"group_by column '{s.group_by}' not found")
            elif group.formula:
                bad(p, "group_by cannot be a computed column")
            seen: set[str] = set()
            types = {s.group_by: group.type if group else "text"}
            for m in s.metrics:
                col = by_key.get(m.column)
                if col is None:
                    bad(p, f"metric column '{m.column}' not found")
                elif (problem := _agg_problem(m.agg, col)):
                    bad(p, problem)
                key = f"{m.agg}_{m.column}"
                if key in seen:
                    bad(p, f"duplicate metric '{key}'")
                seen.add(key)
                types[key] = "number"
            sources[s.name.lower()] = types
            has_rows[s.name.lower()] = bool(src.rows)

    # Pass 3: KPIs and charts.
    for si, sh in enumerate(spec.sheets):
        for ki, k in enumerate(sh.kpis):
            p = f"sheets/{si}/kpis/{ki}"
            src = tables.get(k.source.lower())
            col = next((c for c in src.columns if c.key == k.column), None) if src else None
            if src is None or col is None:
                bad(p, f"KPI '{k.label}' references an unknown table or column")
            elif (problem := _agg_problem(k.agg, col)):
                bad(p, problem)

        for ci, c in enumerate(sh.charts):
            p = f"sheets/{si}/charts/{ci}"
            cols = sources.get(c.source.lower())
            if cols is None:
                bad(p, f"chart '{c.title}': source '{c.source}' not found")
                continue
            if not has_rows.get(c.source.lower()):
                bad(p, f"chart '{c.title}': source has no data rows")
            if c.category not in cols:
                bad(p, f"chart '{c.title}': category '{c.category}' not found")
            if c.type == "pie" and len(c.values) != 1:
                bad(p, f"chart '{c.title}': a pie chart needs exactly one value column")
            for v in c.values:
                if v not in cols:
                    bad(p, f"chart '{c.title}': value column '{v}' not found")
                elif cols[v] not in NUMERIC_TYPES:
                    bad(p, f"chart '{c.title}': value column '{v}' is not numeric")
    return issues
