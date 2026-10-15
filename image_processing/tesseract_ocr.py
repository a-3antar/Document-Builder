"""Tesseract engine via its CLI (TSV output gives real per-word confidence)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image

from config.constants import (OCR_SUBPROCESS_TIMEOUT, OcrMethod, TESSERACT_URL,
                              TESSERACT_WIN_PATHS)
from core.exceptions import (DocumentBuilderError, OcrError, OcrLanguageNotSupportedError,
                             TesseractNotFoundError)
from core.interfaces import OcrEngine
from core.models import OCRResult, OcrSegment
from core.subprocess_utils import run_quiet
from image_processing.base_ocr import split_languages, temp_png

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

def locate_tesseract(configured: str = "", which: Callable[..., str | None] = shutil.which,
                     env: Mapping[str, str] = os.environ,
                     common_paths: Sequence[str] = TESSERACT_WIN_PATHS) -> Path | None:
    """Explicit path must be valid; otherwise PATH, then common Windows locations."""
    if configured.strip():
        path = Path(configured.strip())
        return path if path.is_file() else None
    if found := which("tesseract"):
        return Path(found)
    candidates = [Path(p) for p in common_paths]
    if local := env.get("LOCALAPPDATA"):
        candidates.append(Path(local) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return next((c for c in candidates if c.is_file()), None)


def parse_tsv(tsv: str) -> tuple[str, list[OcrSegment]]:
    """Group words into lines (paragraph breaks -> blank line); confidence is 0-1."""
    lines: dict[tuple[int, ...], list[tuple[str, float]]] = {}
    for raw in tsv.splitlines()[1:]:
        parts = raw.split("\t", 11)
        if len(parts) < 12:
            continue
        try:
            conf, key = float(parts[10]), tuple(int(p) for p in parts[1:5])
        except ValueError:
            continue
        word = parts[11].strip()
        if word and conf >= 0:
            lines.setdefault(key, []).append((word, conf))
    out: list[str] = []
    segments: list[OcrSegment] = []
    prev: tuple[int, ...] | None = None
    for key, words in lines.items():
        if prev is not None and key[:3] != prev:
            out.append("")
        prev = key[:3]
        line = " ".join(w for w, _ in words)
        out.append(line)
        segments.append(OcrSegment(line, sum(c for _, c in words) / len(words) / 100))
    return "\n".join(out), segments


class TesseractEngine(OcrEngine):
    id = OcrMethod.TESSERACT.value

    def __init__(self, configured_path: Callable[[], str] = lambda: "", runner: Runner = run_quiet,
                 temp_dir: Path | None = None, timeout: float = OCR_SUBPROCESS_TIMEOUT,
                 psm: int = 3) -> None:
        self._configured, self._runner = configured_path, runner
        self._tmp, self._timeout, self._psm = temp_dir, timeout, psm
        self._langs: dict[Path, list[str]] = {}

    def _exe(self) -> Path:
        configured = self._configured()
        exe = locate_tesseract(configured)
        if exe is None:
            msg = ("The configured Tesseract path is invalid." if configured.strip()
                   else "Tesseract was not found.")
            raise TesseractNotFoundError(
                msg, hint=f"Install it from {TESSERACT_URL} or set its path in Application Settings.")
        return exe

    def _run(self, args: list[Any]) -> "subprocess.CompletedProcess[str]":
        try:
            return self._runner(args, timeout=self._timeout)
        except OSError as exc:
            raise TesseractNotFoundError("Tesseract could not be started.",
                                         hint=f"Reinstall it from {TESSERACT_URL}.") from exc
        except subprocess.TimeoutExpired as exc:
            raise OcrError("Tesseract timed out.",
                           hint="Try a smaller image or enable resizing.") from exc

    def is_available(self) -> tuple[bool, str]:
        try:
            return True, f"Tesseract found at {self._exe()}"
        except DocumentBuilderError as exc:
            return False, f"{exc} {exc.hint}".strip()

    def installed_languages(self, exe: Path | None = None) -> list[str]:
        """Language codes from `tesseract --list-langs` (cached per executable)."""
        exe = exe or self._exe()
        if exe not in self._langs:
            proc = self._run([exe, "--list-langs"])
            lines = (proc.stdout + "\n" + proc.stderr).splitlines()
            self._langs[exe] = sorted({ln.strip() for ln in lines
                                       if ln.strip() and "List of available" not in ln})
        return self._langs[exe]

    def extract(self, image: Image.Image, languages: str) -> OCRResult:
        exe, codes = self._exe(), split_languages(languages)
        missing = [c for c in codes if c not in set(self.installed_languages(exe))]
        if missing:
            raise OcrLanguageNotSupportedError(
                f"Tesseract language data is missing: {', '.join(missing)}.",
                hint="Install the language data in the Tesseract setup, or choose another language.")
        with temp_png(image, self._tmp) as png:
            proc = self._run([exe, png, "stdout", "-l", "+".join(codes),
                              "--psm", str(self._psm), "tsv"])
        if proc.returncode != 0:
            raise OcrError(f"Tesseract failed: {proc.stderr.strip()[:200]}")
        text, segments = parse_tsv(proc.stdout)
        return OCRResult("", self.id, text, segments=segments)