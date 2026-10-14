"""PDF exporter (ReportLab only). Arabic: arabic-reshaper + python-bidi, applied once per line."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterator
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus import Table as RLTable
from reportlab.platypus import TableStyle

from config.constants import DEFAULT_ACCENT_HEX, PDF_LATIN_FONTS
from core.exceptions import ExportError
from core.models import DocumentContentModel, Heading, ListBlock, Paragraph, Table
from document.arabic_text import ArabicShaper, TextShaper
from document.base_exporter import FileExporter
from document.fonts import find_arabic_font
from document.template_registry import Template
from document.text_utils import clean_text, has_arabic, normalize_table, resolve_direction

_BODY_PT = 10.5
_MARKER_W = 18


def _iter_texts(content: DocumentContentModel) -> Iterator[str]:
    yield content.metadata.title
    for b in content.blocks:
        if isinstance(b, (Heading, Paragraph)):
            yield b.text
        elif isinstance(b, ListBlock):
            yield from b.items
        elif isinstance(b, Table):
            yield b.caption
            yield from b.headers
            for row in b.rows:
                yield from row


class PdfExporter(FileExporter):
    extension = ".pdf"
    content_type = DocumentContentModel
    features = frozenset({"headings", "paragraphs", "lists", "tables", "rtl", "mixed_direction",
                          "page_numbers"})

    def __init__(self, template: Template, font_dir: Path | None = None,
                 shaper: TextShaper | None = None) -> None:
        cfg = template.pdf
        self._latin = str(cfg.get("font", "Helvetica"))
        bold = dict(PDF_LATIN_FONTS).get(self._latin)
        if bold is None:
            raise ExportError(f"PDF font '{self._latin}' is not supported.",
                              hint="Use one of: " + ", ".join(n for n, _ in PDF_LATIN_FONTS))
        self._latin_bold = bold
        self._margin = float(cfg.get("margins_cm", 2.0)) * cm
        self._header, self._footer = bool(cfg.get("header", True)), bool(cfg.get("footer", True))
        hex_ = str(template.excel.get("header_fill", DEFAULT_ACCENT_HEX)).lstrip("#")
        try:
            self._accent = colors.HexColor("#" + hex_)
        except ValueError:
            self._accent = colors.HexColor("#" + DEFAULT_ACCENT_HEX)
        self._font_dir, self._shaper = font_dir, shaper or ArabicShaper()
        self._ar = self._ar_bold = ""

    # --- FileExporter hooks ---
    def _write(self, content: DocumentContentModel, path: Path, warnings: list[str]) -> None:
        if any(has_arabic(clean_text(t)) for t in _iter_texts(content)):
            self._ensure_arabic_font()
        meta = content.metadata
        doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=self._margin,
                                rightMargin=self._margin, topMargin=self._margin,
                                bottomMargin=self._margin, title=meta.title,
                                author=meta.author or "Document Builder AI")
        story = self._story(content, A4[0] - 2 * self._margin, warnings) or [Spacer(1, 1)]
        deco = self._decorator(content)
        doc.build(story, onFirstPage=deco, onLaterPages=deco)

    def _verify(self, path: Path) -> None:
        reader = PdfReader(str(path))
        if reader.is_encrypted or len(reader.pages) < 1:
            raise ValueError("PDF is encrypted or has no pages")

    # --- fonts ---
    def _ensure_arabic_font(self) -> None:
        if self._ar:
            return
        font = find_arabic_font(self._font_dir)
        self._ar, self._ar_bold = self._register(font.regular), self._register(font.bold)

    @staticmethod
    def _register(path: Path) -> str:
        name = f"DB-{path.stem}-{hashlib.md5(str(path).encode()).hexdigest()[:8]}"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return name

    # --- styles and text ---
    def _styles(self) -> dict[str, ParagraphStyle]:
        body = ParagraphStyle("body", fontName=self._latin, fontSize=_BODY_PT, leading=15,
                              spaceAfter=6)
        out = {"body": body,
               "title": ParagraphStyle("title", parent=body, fontName=self._latin_bold,
                                       fontSize=20, leading=25, spaceAfter=12, keepWithNext=1),
               "caption": ParagraphStyle("caption", parent=body, fontSize=9, leading=12,
                                         textColor=colors.grey, spaceAfter=3, keepWithNext=1),
               "cell": ParagraphStyle("cell", parent=body, fontSize=9.5, leading=13, spaceAfter=0),
               "head": ParagraphStyle("head", parent=body, fontName=self._latin_bold, fontSize=9.5,
                                      leading=13, spaceAfter=0, textColor=colors.white)}
        for level, size in zip((1, 2, 3, 4), (16, 13.5, 12, 11)):
            out[f"h{level}"] = ParagraphStyle(f"h{level}", parent=body, fontName=self._latin_bold,
                                              fontSize=size, leading=size + 4, spaceBefore=10,
                                              spaceAfter=6, keepWithNext=1)
        return out

    def _flow(self, text: str, style: ParagraphStyle, width: float, hint: str = "auto",
              bold: bool = False) -> list[Any]:
        """Return flowables for one text block (one Paragraph per line when Arabic)."""
        text = clean_text(text)
        direction = resolve_direction(text, hint)
        if not has_arabic(text):
            if direction == "rtl":
                style = ParagraphStyle("r", parent=style, alignment=TA_RIGHT)
            return [RLParagraph(escape(text).replace("\n", "<br/>"), style)]
        font = self._ar_bold if bold or style.fontName == self._latin_bold else self._ar
        align = TA_RIGHT if direction == "rtl" else TA_LEFT
        usable = width - style.leftIndent - style.rightIndent - 2  # slack avoids re-wrapping
        lines: list[str] = []
        for logical in text.split("\n"):
            shaped = self._shaper.reshape(logical)  # wrap in logical order...
            lines += simpleSplit(shaped, font, style.fontSize, usable) or [""]
        out = []
        for i, line in enumerate(lines):
            line_style = ParagraphStyle(
                "ar", parent=style, fontName=font, alignment=align,
                spaceBefore=style.spaceBefore if i == 0 else 0,
                spaceAfter=style.spaceAfter if i == len(lines) - 1 else 0)
            # ...then reorder each line exactly once.
            out.append(RLParagraph(escape(self._shaper.to_visual(line, direction)), line_style))
        return out

    # --- story ---
    def _story(self, content: DocumentContentModel, width: float, warnings: list[str]) -> list[Any]:
        st, story = self._styles(), []
        if content.metadata.title:
            story += self._flow(content.metadata.title, st["title"], width)
        for block in content.blocks:
            if isinstance(block, Heading):
                story += self._flow(block.text, st[f"h{min(max(block.level, 1), 4)}"], width)
            elif isinstance(block, Paragraph):
                story += self._flow(block.text, st["body"], width, block.direction)
            elif isinstance(block, ListBlock):
                story += self._list(block, st["body"], width)
            elif isinstance(block, Table):
                story += self._table(block, st, width, content.metadata.language == "ar", warnings)
        return story

    def _list(self, block: ListBlock, body: ParagraphStyle, width: float) -> list[Any]:
        item_style = ParagraphStyle("item", parent=body, spaceAfter=2)
        out = []
        for n, item in enumerate(block.items, 1):
            rtl = resolve_direction(clean_text(item)) == "rtl"
            marker = RLParagraph(f"{n}." if block.ordered else "&bull;",
                                 ParagraphStyle("m", parent=body, spaceAfter=0,
                                                alignment=TA_RIGHT if rtl else TA_LEFT))
            text = self._flow(item, item_style, width - _MARKER_W)
            cells, widths = ([text, marker], [width - _MARKER_W, _MARKER_W]) if rtl \
                else ([marker, text], [_MARKER_W, width - _MARKER_W])
            row = RLTable([cells], colWidths=widths)
            row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                     ("TOPPADDING", (0, 0), (-1, -1), 0),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            out.append(row)
        out.append(Spacer(1, 4))
        return out

    def _table(self, block: Table, st: dict[str, ParagraphStyle], width: float, rtl_doc: bool,
               warnings: list[str]) -> list[Any]:
        headers, rows, note = normalize_table(block.headers, block.rows)
        if note and note not in warnings:
            warnings.append(note)
        rtl = rtl_doc or resolve_direction(" ".join(headers)) == "rtl"
        col_w = width / len(headers)
        inner = col_w - 12  # default 6 pt padding each side

        def cells(row: list[str], style: ParagraphStyle, bold: bool) -> list[Any]:
            flows = [self._flow(t, style, inner, bold=bold) for t in row]
            return flows[::-1] if rtl else flows  # first column on the right for RTL

        data = [cells(headers, st["head"], True)] + [cells(r, st["cell"], False) for r in rows]
        table = RLTable(data, colWidths=[col_w] * len(headers), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self._accent),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        out = self._flow(block.caption, st["caption"], width) if block.caption else []
        return out + [table, Spacer(1, 10)]

    # --- header / footer ---
    def _decorator(self, content: DocumentContentModel) -> Any:
        title = clean_text(content.metadata.title)[:80]
        ar_doc = content.metadata.language == "ar" or has_arabic(title)

        def draw(canvas: Any, doc: Any) -> None:
            width, height = A4
            canvas.saveState()
            canvas.setFillGray(0.4)
            if self._header and title:
                font, text, direction = self._latin, title, "ltr"
                if has_arabic(title):
                    direction = resolve_direction(title)
                    font = self._ar
                    text = self._shaper.to_visual(self._shaper.reshape(title), direction)
                canvas.setFont(font, 8)
                y = height - self._margin / 2
                if direction == "rtl":
                    canvas.drawRightString(width - self._margin, y, text)
                else:
                    canvas.drawString(self._margin, y, text)
            if self._footer:
                canvas.setFont(self._latin, 8)
                label = str(doc.page) if ar_doc else f"Page {doc.page}"
                canvas.drawCentredString(width / 2, self._margin / 2, label)
            canvas.restoreState()

        return draw
