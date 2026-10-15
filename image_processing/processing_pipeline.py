"""Pipeline: load -> preprocess -> OCR engine -> merge (UI/AI independent)."""
from __future__ import annotations

from typing import Callable, Sequence
from pathlib import Path

from config.constants import (OCR_CONFIDENCE_THRESHOLD, PDF_RENDER_DPI,
                              SUPPORTED_IMAGE_EXTENSIONS)
from core.exceptions import OcrLowConfidenceError, UnsupportedImageFormatError
from core.interfaces import OcrEngine
from core.models import OCRResult, OcrSegment
from image_processing.base_ocr import flag_uncertain, mean_confidence
from image_processing.image_preprocessor import ImagePreprocessor, PreprocessOptions
from image_processing.pdf_loader import PdfLoader

Progress = Callable[[float, str], None]
_Job = tuple[Path, int | None]  # (file, 1-based PDF page or None for images)


class ProcessingPipeline:
    def __init__(self, preprocessor: ImagePreprocessor, pdf: PdfLoader) -> None:
        self._pre, self._pdf = preprocessor, pdf

    def _jobs(self, sources: Sequence[Path]) -> list[_Job]:
        jobs: list[_Job] = []
        for src in sources:
            ext = src.suffix.lower()
            if ext == ".pdf":
                jobs += [(src, n) for n in range(1, self._pdf.page_count(src) + 1)]
            elif ext in SUPPORTED_IMAGE_EXTENSIONS:
                jobs.append((src, None))
            else:
                raise UnsupportedImageFormatError(
                    f"'{src.name}' is not a supported image or PDF.",
                    hint="Use PNG, JPG, BMP, TIFF, WEBP or PDF.")
        return jobs

    def run(self, sources: Sequence[Path], engine: OcrEngine, languages: str,
            options: PreprocessOptions = PreprocessOptions(), *, pdf_dpi: int = PDF_RENDER_DPI,
            confidence_threshold: float = OCR_CONFIDENCE_THRESHOLD, strict_confidence: bool = False,
            on_progress: Progress | None = None) -> OCRResult:
        """OCR every image/page and merge. `on_progress` may raise to cancel."""
        jobs = self._jobs(sources)
        texts: list[str] = []
        segments: list[OcrSegment] = []
        for i, (path, page) in enumerate(jobs):
            label = path.name if page is None else f"{path.name} (page {page})"
            if on_progress:
                on_progress(100 * i / len(jobs), f"Reading {label}...")
            raw = (self._pre.load(path) if page is None
                   else self._pdf.render_page(path, page, pdf_dpi))
            part = engine.extract(self._pre.process(raw, options), languages)
            texts.append(part.original_text)
            segments += part.segments
        segments = flag_uncertain(segments, confidence_threshold)
        result = OCRResult(", ".join(p.name for p in sources), engine.id,
                           "\n\n".join(texts), segments=segments)
        mean = mean_confidence(segments)
        if strict_confidence and mean is not None and mean < confidence_threshold:
            raise OcrLowConfidenceError(
                f"Average OCR confidence is {mean:.0%}, below {confidence_threshold:.0%}.",
                hint="Improve the image, try another engine, or lower the threshold.", result=result)
        if on_progress:
            on_progress(100, "Done.")
        return result