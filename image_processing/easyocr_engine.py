"""EasyOCR engine with explicit model-download control."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from PIL import Image

from config.constants import (EASYOCR_DETECTOR_FILE, EASYOCR_WEIGHT_FILES, OcrMethod)
from core.exceptions import (OcrDependencyNotInstalledError, OcrLanguageNotSupportedError,
                             OcrModelDownloadRequiredError)
from core.interfaces import OcrEngine
from core.models import OCRResult, OcrSegment
from image_processing.base_ocr import to_easyocr_codes

ReaderFactory = Callable[[list[str], bool], Any]
_DEFAULT_MODEL_DIR = Path.home() / ".EasyOCR" / "model"


def easyocr_models_present(codes: Sequence[str], model_dir: Path | None = None) -> bool:
    """True when the detector and the known recognizer weights exist locally."""
    base = model_dir or _DEFAULT_MODEL_DIR
    needed = [EASYOCR_DETECTOR_FILE, *(EASYOCR_WEIGHT_FILES[c] for c in codes if c in EASYOCR_WEIGHT_FILES)]
    return all((base / name).is_file() for name in needed)


def _default_factory(codes: list[str], download: bool) -> Any:
    try:
        import easyocr
    except ImportError as exc:
        raise OcrDependencyNotInstalledError("EasyOCR is not installed.",
                                             hint="Run: pip install easyocr") from exc
    try:
        return easyocr.Reader(codes, gpu=False, download_enabled=download, verbose=False)
    except ValueError as exc:
        raise OcrLanguageNotSupportedError(str(exc), hint="Choose a compatible language set.") from exc
    except FileNotFoundError as exc:
        raise OcrModelDownloadRequiredError("EasyOCR model files are missing.",
                                            hint="Allow the one-time download and retry.") from exc


@dataclass(frozen=True)
class _Box:
    x: float
    y: float
    h: float
    text: str
    conf: float


def group_lines(boxes: Sequence[_Box], rtl: bool) -> list[list[_Box]]:
    """Cluster boxes into lines by vertical position; order each line by direction."""
    lines: list[list[_Box]] = []
    for box in sorted(boxes, key=lambda b: b.y):
        if lines and abs(box.y - lines[-1][0].y) <= 0.5 * max(box.h, lines[-1][0].h):
            lines[-1].append(box)
        else:
            lines.append([box])
    return [sorted(line, key=lambda b: b.x, reverse=rtl) for line in lines]


class EasyOcrEngine(OcrEngine):
    id = OcrMethod.EASYOCR.value

    def __init__(self, model_dir: Path | None = None, reader_factory: ReaderFactory = _default_factory) -> None:
        self.allow_download = False  # set by the UI only after the user agrees
        self._model_dir, self._factory = model_dir, reader_factory
        self._readers: dict[tuple[str, ...], Any] = {}
        self._lock = threading.Lock()

    def is_available(self) -> tuple[bool, str]:
        import importlib.util
        if importlib.util.find_spec("easyocr") is None:
            return False, "EasyOCR is not installed. Run: pip install easyocr"
        return True, "EasyOCR is installed."

    def _reader(self, codes: list[str]) -> Any:
        key = tuple(codes)
        with self._lock:
            if key not in self._readers:
                if not self.allow_download and not easyocr_models_present(codes, self._model_dir):
                    raise OcrModelDownloadRequiredError(
                        "EasyOCR needs to download its model files (internet required, one time).",
                        hint="Confirm the download, or use Tesseract instead.")
                self._readers[key] = self._factory(codes, self.allow_download)
            return self._readers[key]

    def extract(self, image: Image.Image, languages: str) -> OCRResult:
        codes = to_easyocr_codes(languages)
        reader = self._reader(codes)
        try:
            import numpy as np
        except ImportError as exc:
            raise OcrDependencyNotInstalledError("NumPy is not installed.",
                                                 hint="Run: pip install numpy") from exc
        boxes = []
        for bbox, text, conf in reader.readtext(np.array(image.convert("RGB"))):
            xs, ys = [p[0] for p in bbox], [p[1] for p in bbox]
            boxes.append(_Box(sum(xs) / len(xs), sum(ys) / len(ys), max(ys) - min(ys),
                              str(text).strip(), float(conf)))
        lines = group_lines([b for b in boxes if b.text], rtl=codes[0] == "ar")
        segments = [OcrSegment(" ".join(b.text for b in ln), sum(b.conf for b in ln) / len(ln))
                    for ln in lines]
        return OCRResult("", self.id, "\n".join(s.text for s in segments), segments=segments)