"""Vision-model OCR (Gemini or Ollama) through the AiProvider interface."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ai.prompts import build_vision_prompt
from config.constants import OCR_UNCERTAIN_OPEN
from core.exceptions import OcrError
from core.interfaces import AiProvider, OcrEngine
from core.models import OCRResult, OcrSegment
from core.schema_validator import strip_code_fence
from image_processing.base_ocr import temp_png


class VisionOcrEngine(OcrEngine):
    """No confidence is reported; uncertain text is flagged via [? ?] markers."""

    def __init__(self, engine_id: str, provider: AiProvider, model: str,
                 temp_dir: Path | None = None) -> None:
        self.id, self._provider, self._model, self._tmp = engine_id, provider, model, temp_dir

    def is_available(self) -> tuple[bool, str]:
        return self._provider.check_connection()

    def extract(self, image: Image.Image, languages: str) -> OCRResult:
        with temp_png(image, self._tmp) as png:
            try:
                raw = self._provider.analyze_image(png, build_vision_prompt(languages), self._model)
            except NotImplementedError as exc:
                raise OcrError(f"{self._provider.id} does not support image analysis.") from exc
        text = strip_code_fence(raw).strip()
        segments = [OcrSegment(line, None, OCR_UNCERTAIN_OPEN in line)
                    for line in text.splitlines() if line.strip()]
        return OCRResult("", self.id, text, segments=segments)