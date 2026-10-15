"""Turn reviewed OCR text into document content."""
from __future__ import annotations

import re

from core.models import DocumentContentModel, Metadata, Paragraph
from document.text_utils import has_arabic


def ocr_text_to_document(text: str, title: str) -> DocumentContentModel:
    """Blank-line separated paragraphs; always flagged as needing review."""
    blocks = [Paragraph(p.strip("\n")) for p in re.split(r"\n\s*\n", text) if p.strip()]
    latin = re.search("[A-Za-z]", text) is not None
    lang = "mixed" if has_arabic(text) and latin else "ar" if has_arabic(text) else "en"
    return DocumentContentModel(Metadata(title, lang), blocks, needs_review=True)
    