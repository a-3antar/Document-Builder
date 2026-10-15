"""Generate Arabic/English samples for visual verification.

Usage (project root):
    python scripts/arabic_pdf_check.py [output.pdf] [--font-dir FOLDER] [--png] [--docx]
                                       [--poppler FOLDER]

Font order: --font-dir, then resources/fonts, then a system font (check only).
--png renders each page to PNG (needs pdf2image + Poppler) for screenshots.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.exceptions import FontNotFoundError
from core.schema_validator import SchemaValidator
from document.fonts import find_arabic_font
from document.pdf_exporter_reportlab import PdfExporter
from document.template_registry import TemplateRegistry
from document.word_exporter import WordExporter
from tests.arabic_samples import CHECKLIST, build_content
from tests.font_helper import prepare_font_dir


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


def render_png(pdf: Path, poppler: str = "", dpi: int = 110) -> list[Path]:
    """Render pages to PNG next to the PDF; raises on missing pdf2image/Poppler."""
    from pdf2image import convert_from_path
    from image_processing.pdf_loader import find_poppler_bin

    folder = find_poppler_bin(poppler)
    pages = convert_from_path(str(pdf), dpi=dpi, poppler_path=str(folder) if folder else None)
    out = []
    for n, image in enumerate(pages, 1):
        path = pdf.with_name(f"{pdf.stem}_p{n}.png")
        image.save(path)
        out.append(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="arabic_check.pdf")
    parser.add_argument("--font-dir", type=Path)
    parser.add_argument("--png", action="store_true", help="also render pages to PNG")
    parser.add_argument("--docx", action="store_true", help="also create a Word sample")
    parser.add_argument("--poppler", default="", help="Poppler bin folder for --png")
    args = parser.parse_args()

    registry = TemplateRegistry(SchemaValidator())
    registry.load()
    template = registry.get("blank_structured")
    try:
        font_dir, source = pick_font_dir(args.font_dir)
    except FontNotFoundError as exc:
        print(f"{exc} {exc.hint}")
        return 1
    out = Path(args.output).resolve()
    result = PdfExporter(template, font_dir).export(build_content(), out)
    print(f"Font: {source}\nCreated {result.path} ({result.size_bytes} bytes)")
    if args.docx:
        docx = WordExporter(template).export(build_content(), out.with_suffix(".docx"))
        print(f"Created {docx.path} ({docx.size_bytes} bytes)")
    if args.png:
        try:
            for png in render_png(out, args.poppler):
                print(f"Screenshot: {png}")
        except Exception as exc:  # noqa: BLE001 - optional step, explain and continue
            print(f"PNG rendering skipped: {exc} (install pdf2image and Poppler)")
    print("\n" + CHECKLIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())