"""Plain-text preview of structured content (until the structured editor exists)."""
from __future__ import annotations

from core.models import (DocumentContentModel, Heading, ListBlock, Paragraph, Table,
                         WorkbookContentModel)


def render_preview(content: DocumentContentModel | WorkbookContentModel) -> str:
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