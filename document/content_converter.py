"""Adapt content to the requested output format (document <-> workbook)."""
from __future__ import annotations

import re

from config.constants import OutputFormat
from core.models import (Cell, DocumentContentModel, Heading, ListBlock, Paragraph, Sheet, Table,
                         WorkbookContentModel)

_BAD_SHEET_RE = re.compile(r"[\[\]:*?/\\]")


def _cell_text(cell: Cell) -> str:
    if cell.type == "blank" or cell.value is None:
        return ""
    if isinstance(cell.value, bool):
        return "TRUE" if cell.value else "FALSE"
    if isinstance(cell.value, float) and cell.value.is_integer():
        return str(int(cell.value))
    return str(cell.value)


def workbook_to_document(wb: WorkbookContentModel) -> DocumentContentModel:
    """Each sheet becomes a level-2 heading followed by a table (values as text)."""
    blocks: list = []
    for sheet in wb.sheets:
        blocks.append(Heading(sheet.name, 2))
        blocks.append(Table(tuple(sheet.columns),
                            tuple(tuple(_cell_text(c) for c in row) for row in sheet.rows)))
    return DocumentContentModel(wb.metadata, blocks, wb.needs_review, wb.schema_version)


def document_to_workbook(doc: DocumentContentModel) -> WorkbookContentModel:
    """Each table becomes a sheet; headings/paragraphs/list items go to a 'Content' sheet.

    Cells stay text: types are never guessed from strings.
    """
    sheets: list[Sheet] = []
    text_rows: list[tuple[Cell, ...]] = []
    for block in doc.blocks:
        if isinstance(block, Table):
            name = _BAD_SHEET_RE.sub("_", block.caption or f"Table {len(sheets) + 1}")[:31]
            rows = tuple(tuple(Cell("text", c) for c in r) for r in block.rows)
            sheets.append(Sheet(name, tuple(block.headers), rows))
        elif isinstance(block, Heading):
            text_rows.append((Cell("text", "Heading"), Cell("text", block.text)))
        elif isinstance(block, Paragraph):
            text_rows.append((Cell("text", "Paragraph"), Cell("text", block.text)))
        elif isinstance(block, ListBlock):
            text_rows += [(Cell("text", "List item"), Cell("text", i)) for i in block.items]
    if text_rows or not sheets:
        sheets.insert(0, Sheet("Content", ("Type", "Text"), tuple(text_rows)))
    return WorkbookContentModel(doc.metadata, sheets, doc.needs_review, doc.schema_version)


def adapt_content(content: DocumentContentModel | WorkbookContentModel, fmt: OutputFormat
                  ) -> tuple[DocumentContentModel | WorkbookContentModel, list[str]]:
    """Return content matching the format plus user-facing notes about any conversion."""
    if fmt is OutputFormat.XLSX and isinstance(content, DocumentContentModel):
        return document_to_workbook(content), [
            "Document content was converted to a workbook: tables became sheets, "
            "other text went to the 'Content' sheet."]
    if fmt is not OutputFormat.XLSX and isinstance(content, WorkbookContentModel):
        return workbook_to_document(content), [
            "Workbook content was converted to a document: each sheet became a table; "
            "formulas are shown as text."]
    return content, []
