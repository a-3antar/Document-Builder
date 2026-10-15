"""Generate an Arabic/English PDF sample for visual verification.

Usage (project root):
    python scripts/arabic_pdf_check.py [output.pdf] [--font-dir FOLDER]

Font order: --font-dir, then resources/fonts, then a system font (check only).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.exceptions import FontNotFoundError
from core.models import DocumentContentModel, Heading, ListBlock, Metadata, Paragraph, Table
from core.schema_validator import SchemaValidator
from document.fonts import find_arabic_font
from document.pdf_exporter_reportlab import PdfExporter
from document.template_registry import TemplateRegistry
from tests.font_helper import prepare_font_dir

CHECKLIST = """\
Open the PDF and confirm:
 1. Arabic letters are joined (not isolated) and read right-to-left.
 2. Punctuation sits at the correct end: ، ؟ ( ) .
 3. Numbers (123 and ١٢٣) keep their digit order inside Arabic text.
 4. The mixed paragraph keeps English words readable and in order.
 5. Long Arabic paragraphs wrap without reversed or duplicated lines.
 6. Ordered list markers are on the right for Arabic items.
 7. Table columns run right-to-left for the Arabic table.
 8. Header shows the Arabic title; footer shows the page number.
"""


def build_content() -> DocumentContentModel:
    return DocumentContentModel(Metadata("اختبار التقرير العربي", "ar", "Document Builder AI"), [
        Heading("مقدمة", 1),
        Paragraph("مرحبا بالعالم، كيف حالك؟ هذا اختبار (للتأكد) من اتصال الحروف واتجاه النص."),
        Paragraph("اختبار Document Builder AI في القاهرة عام 2026 برقم ١٢٣٤٥ و 6789."),
        Paragraph("This is an English paragraph to confirm left-to-right layout."),
        Paragraph("نص عربي طويل لاختبار التفاف الأسطر. " * 25),
        Heading("قائمة", 2),
        ListBlock(("البند الأول", "البند الثاني مع English", "البند الثالث"), True),
        Table(("العمود الأول", "العمود الثاني", "Total"),
              (("١", "قيمة", "10"), ("٢", "قيمة أخرى", "20")), "جدول تجريبي"),
    ])


def pick_font_dir(explicit: Path | None) -> tuple[Path | None, str]:
    """Return (font_dir or None for resources/fonts, description)."""
    if explicit:
        font = find_arabic_font(explicit)
        return explicit, f"folder {explicit} ({font.regular.name})"
    try:
        return None, f"bundled font {find_arabic_font().regular.name}"
    except FontNotFoundError:
        pass
    found = prepare_font_dir()
    if found is None:
        raise FontNotFoundError(
            "No system font with Arabic glyphs was found.",
            hint="Install Simplified Arabic / Arial, or pass --font-dir with a .ttf font.")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="arabic_check.pdf")
    parser.add_argument("--font-dir", type=Path)
    args = parser.parse_args()

    registry = TemplateRegistry(SchemaValidator())
    registry.load()
    try:
        font_dir, source = pick_font_dir(args.font_dir)
    except FontNotFoundError as exc:
        print(f"{exc} {exc.hint}")
        return 1
    out = Path(args.output).resolve()
    result = PdfExporter(registry.get("blank_structured"), font_dir).export(build_content(), out)
    print(f"Font: {source}\nCreated {result.path} ({result.size_bytes} bytes)\n")
    print(CHECKLIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())