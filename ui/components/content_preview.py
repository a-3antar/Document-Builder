"""Plain-text preview of structured content (until the structured editor exists)."""
from __future__ import annotations

from core.models import (DocumentContentModel, Heading, ListBlock, Paragraph, Table,
                         WorkbookContentModel)
from core.workbook_spec import WorkbookSpec

_PREVIEW_ROWS = 20


def _spec_lines(spec: WorkbookSpec) -> list[str]:
    """Readable outline of a workbook spec (formula columns are marked)."""
    out: list[str] = []
    for sh in spec.sheets:
        out.append(f"[Sheet:{sh.role}] {sh.name}")
        for k in sh.kpis:
            out.append(f"  KPI: {k.label} = {k.agg}({k.source}.{k.column})")
        for t in sh.tables:
            out.append(f"  Table {t.name}" + (f" - {t.title}" if t.title else ""))
            out.append("  " + " | ".join(c.title + (" (formula)" if c.formula else "")
                                         for c in t.columns))
            for row in t.rows[:_PREVIEW_ROWS]:
                out.append("  " + " | ".join("" if v is None else str(v) for v in row))
            if len(t.rows) > _PREVIEW_ROWS:
                out.append(f"  ... {len(t.rows) - _PREVIEW_ROWS} more rows")
            if t.totals:
                out.append("  Totals: " + ", ".join(f"{agg}({key})" for key, agg in t.totals))
        for s in sh.summaries:
            metrics = ", ".join(f"{m.agg}({m.column})" for m in s.metrics)
            out.append(f"  Summary {s.name}: {s.source} grouped by {s.group_by} -> {metrics}")
        for c in sh.charts:
            out.append(f"  Chart [{c.type}] {c.title}: {c.category} vs {', '.join(c.values)} ({c.source})")
        out += [f"  Note: {n}" for n in sh.notes]
        out.append("")
    return out


def render_preview(content: DocumentContentModel | WorkbookContentModel | WorkbookSpec) -> str:
    """Return a readable text rendering of validated content."""
    lines: list[str] = [f"Title: {content.metadata.title}", ""]
    if isinstance(content, DocumentContentModel):
        for block in content.blocks:
            if isinstance(block, Heading):
                lines.append(f"{'#' * block.level} {block.text}")
            elif isinstance(block, Paragraph):
                lines.append(block.text)
            elif isinstance(block, ListBlock):
                lines += [f"{i}. {t}" if block.ordered else f"- {t}"
                          for i, t in enumerate(block.items, 1)]
            elif isinstance(block, Table):
                if block.caption:
                    lines.append(f"Table: {block.caption}")
                lines.append(" | ".join(block.headers))
                lines += [" | ".join(row) for row in block.rows]
            lines.append("")
    elif isinstance(content, WorkbookSpec):
        lines += _spec_lines(content)
    else:
        for sheet in content.sheets:
            lines.append(f"[Sheet] {sheet.name}")
            lines.append(" | ".join(sheet.columns))
            for row in sheet.rows:
                lines.append(" | ".join("" if c.type == "blank" or c.value is None else str(c.value)
                                        for c in row))
            lines.append("")
        for chart in content.charts:
            lines.append(f"[Chart:{chart.type}] {chart.title} - {chart.sheet}: "
                         f"{chart.category_column} vs {', '.join(chart.value_columns)}")
    return "\n".join(lines).rstrip() + "\n"