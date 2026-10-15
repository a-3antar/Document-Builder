"""OCR orchestration: engine selection, validation, optional AI correction."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ai.model_registry import ModelRegistry, ProviderRegistry
from ai.prompts import build_ocr_correction_prompt
from config.constants import OCR_CONFIDENCE_THRESHOLD, OcrMethod
from core.exceptions import OcrError
from core.interfaces import OcrEngine
from core.models import OCRResult
from core.schema_validator import strip_code_fence
from image_processing.easyocr_engine import EasyOcrEngine
from image_processing.image_preprocessor import PreprocessOptions
from image_processing.pdf_loader import PdfLoader, PdfProbe
from image_processing.processing_pipeline import ProcessingPipeline
from image_processing.tesseract_ocr import TesseractEngine
from image_processing.vision_ocr import VisionOcrEngine
from services.task_service import TaskContext

_VISION = (OcrMethod.GEMINI_VISION, OcrMethod.OLLAMA_VISION)


@dataclass(frozen=True)
class OcrRequest:
    sources: tuple[Path, ...]
    method: OcrMethod
    languages: str
    preprocess: PreprocessOptions = PreprocessOptions()
    base_engine: OcrMethod = OcrMethod.TESSERACT  # used by OCR_PLUS_AI
    provider: str = ""                            # AI provider for vision / correction
    model: str = ""
    preserve_wording: bool = True
    confidence_threshold: float = OCR_CONFIDENCE_THRESHOLD


class OcrService:
    def __init__(self, providers: ProviderRegistry, models: ModelRegistry,
                 pipeline: ProcessingPipeline, tesseract: TesseractEngine,
                 easyocr: EasyOcrEngine, pdf: PdfLoader, temp_dir: Path | None = None) -> None:
        self._providers, self._models, self._pipeline = providers, models, pipeline
        self._tess, self.easyocr, self._pdf, self._tmp = tesseract, easyocr, pdf, temp_dir

    def probe_pdf(self, path: Path) -> PdfProbe:
        return self._pdf.probe(path)

    def _engine(self, req: OcrRequest) -> OcrEngine:
        if req.method in _VISION:
            self._models.require(req.provider, req.model, vision=True)
            return VisionOcrEngine(req.method.value, self._providers.create(req.provider),
                                   req.model, self._tmp)
        base = req.method
        if req.method is OcrMethod.OCR_PLUS_AI:
            self._models.require(req.provider, req.model)
            base = req.base_engine
        if base is OcrMethod.TESSERACT:
            return self._tess
        if base is OcrMethod.EASYOCR:
            return self.easyocr
        raise OcrError(f"Unsupported OCR engine: {base.value}")

    def run(self, req: OcrRequest, ctx: TaskContext | None = None) -> OCRResult:
        """Worker-thread entry point; the original text is never overwritten."""
        def progress(pct: float, msg: str) -> None:
            if ctx:
                ctx.progress(pct * 0.85, msg)

        result = self._pipeline.run(req.sources, self._engine(req), req.languages, req.preprocess,
                                    confidence_threshold=req.confidence_threshold,
                                    on_progress=progress)
        if req.method is OcrMethod.OCR_PLUS_AI and result.original_text.strip():
            if ctx:
                ctx.progress(90, "Correcting with AI...")
            raw = self._providers.create(req.provider).generate_text(
                build_ocr_correction_prompt(result.original_text, req.preserve_wording), req.model)
            result.corrected_text = strip_code_fence(raw).strip()
        return result