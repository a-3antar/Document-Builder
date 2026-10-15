"""Shared OCR helpers."""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Iterator, Sequence

from PIL import Image

from config.constants import TESSERACT_TO_EASYOCR
from core.exceptions import OcrLanguageNotSupportedError
from core.models import OcrSegment


def split_languages(languages: str) -> list[str]:
    """'ara+eng' -> ['ara', 'eng']."""
    codes = [c.strip() for c in languages.replace(",", "+").split("+") if c.strip()]
    if not codes:
        raise OcrLanguageNotSupportedError("No OCR language selected.",
                                           hint="Choose at least one language, e.g. ara+eng.")
    return codes


def to_easyocr_codes(languages: str) -> list[str]:
    """Map Tesseract-style codes to EasyOCR codes."""
    out = []
    for code in split_languages(languages):
        mapped = TESSERACT_TO_EASYOCR.get(code)
        if mapped is None:
            raise OcrLanguageNotSupportedError(
                f"EasyOCR is not configured for language '{code}'.",
                hint="Use ara and/or eng, or switch to Tesseract.")
        out.append(mapped)
    return out


@contextmanager
def temp_png(image: Image.Image, directory: Path | None = None) -> Iterator[Path]:
    """Save the image to a temporary PNG and delete it afterwards."""
    fd, name = tempfile.mkstemp(suffix=".png", dir=directory)
    os.close(fd)
    path = Path(name)
    try:
        image.save(path, format="PNG")
        yield path
    finally:
        path.unlink(missing_ok=True)


def mean_confidence(segments: Sequence[OcrSegment]) -> float | None:
    """Average of real engine confidences; None when the engine gives none."""
    values = [s.confidence for s in segments if s.confidence is not None]
    return sum(values) / len(values) if values else None


def flag_uncertain(segments: Sequence[OcrSegment], threshold: float) -> list[OcrSegment]:
    """Mark segments below the threshold as uncertain (never invents confidence)."""
    return [replace(s, uncertain=s.uncertain or (s.confidence is not None and s.confidence < threshold))
            for s in segments]