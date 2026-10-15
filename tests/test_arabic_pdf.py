"""Automatic Arabic PDF checks; they complement, not replace, the visual checklist."""
import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from document.arabic_text import ArabicShaper
from document.pdf_exporter_reportlab import PdfExporter
from tests.arabic_samples import build_content
from tests.test_exporters import FONT_DIR, TPL

try:
    import arabic_reshaper  # noqa: F401
    import bidi  # noqa: F401
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


def _font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        fonts = page["/Resources"].get_object().get("/Font")
        for ref in (fonts.get_object().values() if fonts else []):
            names.add(str(ref.get_object().get("/BaseFont", "")))
    return names


@unittest.skipUnless(HAS_LIBS and FONT_DIR, "needs arabic-reshaper, python-bidi and an Arabic font")
class ArabicPdfTests(unittest.TestCase):
    def test_shaping_then_reordering_once(self):
        shaper = ArabicShaper()
        shaped = shaper.reshape("مرحبا")
        visual = shaper.to_visual(shaped, "rtl")
        self.assertNotEqual(shaped, "مرحبا")             # joined forms were produced
        self.assertEqual(sorted(shaped), sorted(visual))  # same glyphs, only reordered
        self.assertEqual(visual[0], shaped[-1])           # reversed exactly once

    def test_sample_pdf_embeds_a_font_subset(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "arabic.pdf"
            PdfExporter(TPL, FONT_DIR).export(build_content(), out)
            reader = PdfReader(str(out))
            self.assertGreaterEqual(len(reader.pages), 1)
            names = _font_names(reader)
            self.assertTrue(any(re.match(r"^/?[A-Z]{6}\+", n) for n in names), names)


if __name__ == "__main__":
    unittest.main()