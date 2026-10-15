import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ai.model_registry import ProviderRegistry
from config.constants import ContentKind  # noqa: F401
from config.settings import AppSettings
from core.exceptions import (OcrDependencyNotInstalledError, OcrLanguageNotSupportedError,
                             OcrLowConfidenceError, OcrModelDownloadRequiredError,
                             TesseractNotFoundError, UnsupportedImageFormatError)
from core.interfaces import AiProvider, OcrEngine
from core.models import OCRResult, OcrSegment
from document.ocr_converter import ocr_text_to_document
from image_processing.easyocr_engine import EasyOcrEngine, _Box, group_lines
from image_processing.image_preprocessor import ImagePreprocessor, PreprocessOptions
from image_processing.processing_pipeline import ProcessingPipeline
from image_processing.tesseract_ocr import TesseractEngine, locate_tesseract, parse_tsv
from image_processing.vision_ocr import VisionOcrEngine
from services.dependency_service import DependencyService, DependencyStatus

HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
TSV = HEADER + "\n".join([
    "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t90\tHello",
    "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t70\tworld",
    "5\t1\t1\t2\t1\t1\t0\t0\t1\t1\t50\tNext",
    "5\t1\t1\t2\t1\t2\t0\t0\t1\t1\t-1\t ",
])


def _proc(out="", code=0, err=""):
    return subprocess.CompletedProcess([], code, out, err)


class TsvTests(unittest.TestCase):
    def test_parse(self):
        text, segs = parse_tsv(TSV)
        self.assertEqual(text, "Hello world\n\nNext")
        self.assertAlmostEqual(segs[0].confidence, 0.8)
        self.assertEqual(len(segs), 2)


class TesseractTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.exe = Path(self.dir.name) / "tesseract.exe"
        self.exe.write_text("x")
        self.img = Image.new("RGB", (10, 10), "white")

    def tearDown(self):
        self.dir.cleanup()

    def _engine(self, langs="List of available languages (2):\neng\nara\n"):
        def runner(args, timeout):
            return _proc(langs) if "--list-langs" in args else _proc(TSV)
        return TesseractEngine(lambda: str(self.exe), runner=runner, temp_dir=Path(self.dir.name))

    def test_extract(self):
        res = self._engine().extract(self.img, "ara+eng")
        self.assertEqual(res.engine, "tesseract")
        self.assertIn("Hello world", res.original_text)

    def test_missing_language(self):
        with self.assertRaises(OcrLanguageNotSupportedError):
            self._engine("List of available languages (1):\neng\n").extract(self.img, "ara+eng")

    def test_missing_or_invalid_path(self):
        with self.assertRaises(TesseractNotFoundError):
            TesseractEngine(lambda: "C:/nope/tesseract.exe").extract(self.img, "eng")
        self.assertIsNone(locate_tesseract("C:/nope/tesseract.exe"))
        self.assertEqual(locate_tesseract(str(self.exe)), self.exe)


class PreprocessTests(unittest.TestCase):
    def test_process_is_non_destructive(self):
        src = Image.new("RGBA", (4000, 2000), (255, 0, 0, 128))
        out = ImagePreprocessor().process(src, PreprocessOptions(threshold=128))
        self.assertEqual(max(out.size), 3000)
        self.assertEqual(out.mode, "L")
        self.assertEqual(src.size, (4000, 2000))

    def test_unsupported_and_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "a.png"
            bad.write_bytes(b"not an image")
            with self.assertRaises(UnsupportedImageFormatError):
                ImagePreprocessor().load(bad)
            with self.assertRaises(UnsupportedImageFormatError):
                ImagePreprocessor().load(Path(d) / "a.txt")


class _FakeEngine(OcrEngine):
    id = "fake"

    def is_available(self):
        return True, "ok"

    def extract(self, image, languages):
        return OCRResult("", self.id, "page", segments=[OcrSegment("page", 0.3)])


class _FakePdf:
    def page_count(self, path):
        return 2

    def render_page(self, path, page, dpi):
        return Image.new("RGB", (20, 20), "white")


class PipelineTests(unittest.TestCase):
    def test_images_and_pdf_pages_merge_with_progress(self):
        with tempfile.TemporaryDirectory() as d:
            png = Path(d) / "a.png"
            Image.new("RGB", (20, 20)).save(png)
            events = []
            res = ProcessingPipeline(ImagePreprocessor(), _FakePdf()).run(
                [png, Path(d) / "b.pdf"], _FakeEngine(), "eng",
                on_progress=lambda p, m: events.append(p))
            self.assertEqual(res.original_text, "page\n\npage\n\npage")
            self.assertTrue(all(s.uncertain for s in res.segments))  # 0.3 < 0.6
            self.assertEqual(events[-1], 100)

    def test_strict_low_confidence_keeps_result(self):
        with tempfile.TemporaryDirectory() as d:
            png = Path(d) / "a.png"
            Image.new("RGB", (20, 20)).save(png)
            with self.assertRaises(OcrLowConfidenceError) as ctx:
                ProcessingPipeline(ImagePreprocessor(), _FakePdf()).run(
                    [png], _FakeEngine(), "eng", strict_confidence=True)
            self.assertEqual(ctx.exception.result.original_text, "page")

    def test_unsupported_source(self):
        with self.assertRaises(UnsupportedImageFormatError):
            ProcessingPipeline(ImagePreprocessor(), _FakePdf()).run(
                [Path("x.docx")], _FakeEngine(), "eng")


class _Vision(AiProvider):
    id = "fake"

    def check_connection(self):
        return True, "ok"

    def list_models(self):
        return []

    def generate_text(self, prompt, model, **options):
        return ""

    def analyze_image(self, image, prompt, model, **options):
        return "```\nline one\nbad [?word?]\n```"


class VisionTests(unittest.TestCase):
    def test_uncertain_flagged_without_confidence(self):
        res = VisionOcrEngine("gemini_vision", _Vision(), "m").extract(Image.new("RGB", (5, 5)), "eng")
        self.assertEqual([s.uncertain for s in res.segments], [False, True])
        self.assertTrue(all(s.confidence is None for s in res.segments))

    def test_provider_without_vision(self):
        class NoVision(_Vision):
            def analyze_image(self, *a, **k):
                raise NotImplementedError
        with self.assertRaises(Exception):
            VisionOcrEngine("x", NoVision(), "m").extract(Image.new("RGB", (5, 5)), "eng")


class EasyOcrTests(unittest.TestCase):
    def test_download_required_without_permission(self):
        with tempfile.TemporaryDirectory() as d:
            engine = EasyOcrEngine(Path(d), reader_factory=lambda c, dl: None)
            with self.assertRaises(OcrModelDownloadRequiredError):
                engine.extract(Image.new("RGB", (5, 5)), "ara+eng")

    def test_unknown_language(self):
        with self.assertRaises(OcrLanguageNotSupportedError):
            EasyOcrEngine().extract(Image.new("RGB", (5, 5)), "fra")

    def test_group_lines_rtl_order(self):
        boxes = [_Box(10, 10, 10, "right-end", .9), _Box(90, 11, 10, "first", .9),
                 _Box(50, 40, 10, "second-line", .9)]
        lines = group_lines(boxes, rtl=True)
        self.assertEqual([b.text for b in lines[0]], ["first", "right-end"])
        self.assertEqual(len(lines), 2)


class DependencyTests(unittest.TestCase):
    def _svc(self, **settings):
        ollama = type("O", (), {"check_connection": lambda s: (False, "down")})()
        return DependencyService(lambda: AppSettings(**settings), lambda: ollama,
                                 TesseractEngine(), runner=lambda a, timeout: _proc(),
                                 which=lambda name, path=None: None, env={}, common_paths=())

    def test_not_found_vs_misconfigured(self):
        self.assertEqual(self._svc().check_tesseract().status, DependencyStatus.NOT_FOUND)
        self.assertEqual(self._svc(tesseract_path="C:/bad.exe").check_tesseract().status,
                         DependencyStatus.MISCONFIGURED)
        self.assertEqual(self._svc().check_poppler().status, DependencyStatus.NOT_FOUND)
        self.assertEqual(self._svc(poppler_path="C:/bad").check_poppler().status,
                         DependencyStatus.MISCONFIGURED)
        self.assertEqual(self._svc().check_ollama().status, DependencyStatus.NOT_FOUND)

class ConverterTests(unittest.TestCase):
    def test_ocr_to_document(self):
        doc = ocr_text_to_document("مرحبا\nسطر\n\nHello", "T")
        self.assertEqual(len(doc.blocks), 2)
        self.assertEqual(doc.metadata.language, "mixed")
        self.assertTrue(doc.needs_review)


if __name__ == "__main__":
    unittest.main()