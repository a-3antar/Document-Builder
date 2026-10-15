"""Detect external dependencies and explain how to fix them."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

from config.constants import (EASYOCR_WEIGHT_FILES, OLLAMA_INSTALL_URL, POPPLER_URL,
                              TESSERACT_URL, TESSERACT_WIN_PATHS)
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from core.interfaces import AiProvider
from core.subprocess_utils import run_quiet
from image_processing.base_ocr import split_languages
from image_processing.easyocr_engine import easyocr_models_present
from image_processing.pdf_loader import find_poppler_bin
from image_processing.tesseract_ocr import TesseractEngine, locate_tesseract
from typing import Sequence, Mapping, Callable
import os


class DependencyStatus(StrEnum):
    AVAILABLE = "Available"
    NOT_FOUND = "Not Found"
    MISCONFIGURED = "Misconfigured"


@dataclass(frozen=True)
class DependencyReport:
    name: str
    status: DependencyStatus
    message: str


class DependencyService:
    """Each check is read-only and never starts inference or downloads."""
    def __init__(self, get_settings: Callable[[], AppSettings], ollama: Callable[[], AiProvider],
                 tesseract: TesseractEngine, runner=run_quiet, which=shutil.which,
                 easyocr_model_dir: Path | None = None, env: Mapping[str, str] = os.environ,
                 common_paths: Sequence[str] = TESSERACT_WIN_PATHS) -> None:
        self._settings, self._ollama, self._tess = get_settings, ollama, tesseract
        self._run, self._which, self._model_dir = runner, which, easyocr_model_dir
        self._env, self._common = env, common_paths

    def check_tesseract(self) -> DependencyReport:
        settings = self._settings()
        configured = settings.tesseract_path.strip()
        exe = locate_tesseract(configured, self._which, self._env, self._common)
        if exe is None:
            if configured:
                return DependencyReport("Tesseract OCR", DependencyStatus.MISCONFIGURED,
                                        f"Configured path is invalid: {configured}")
            return DependencyReport("Tesseract OCR", DependencyStatus.NOT_FOUND,
                                    f"Not installed. Windows installer: {TESSERACT_URL}")
        try:
            langs = self._tess.installed_languages(exe)
        except DocumentBuilderError as exc:
            return DependencyReport("Tesseract OCR", DependencyStatus.MISCONFIGURED, str(exc))
        version = self._first_line([exe, "--version"])
        wanted = split_languages(settings.ocr_languages)
        missing = [c for c in wanted if c not in langs]
        note = f" Missing language data: {', '.join(missing)}." if missing else ""
        return DependencyReport("Tesseract OCR", DependencyStatus.AVAILABLE,
                                f"{version} | languages: {', '.join(langs) or 'none'}.{note}")

    def check_poppler(self) -> DependencyReport:
        configured = self._settings().poppler_path.strip()
        folder = find_poppler_bin(configured, self._which)
        if folder is None:
            if configured:
                return DependencyReport("Poppler", DependencyStatus.MISCONFIGURED,
                                        f"pdftoppm not found in: {configured}")
            return DependencyReport("Poppler", DependencyStatus.NOT_FOUND,
                                    f"Needed for scanned-PDF OCR. Download: {POPPLER_URL}")
        version = self._first_line([folder / "pdftoppm", "-v"])
        return DependencyReport("Poppler", DependencyStatus.AVAILABLE, f"{version} ({folder})".strip())

    def check_all(self) -> list[DependencyReport]:
        return [self.check_ollama(), self.check_tesseract(), self.check_easyocr(), self.check_poppler()]

    def _first_line(self, args: list) -> str:
        try:
            proc = self._run(args, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return ""
        return next(iter((proc.stdout + "\n" + proc.stderr).strip().splitlines()), "")

    def check_ollama(self) -> DependencyReport:
        ok, msg = self._ollama().check_connection()
        if ok:
            return DependencyReport("Ollama", DependencyStatus.AVAILABLE, msg)
        if self._which("ollama"):
            return DependencyReport("Ollama", DependencyStatus.MISCONFIGURED,
                                    "Installed but the service is not responding. Start Ollama, then Re-check.")
        return DependencyReport("Ollama", DependencyStatus.NOT_FOUND,
                                f"Not installed. Download: {OLLAMA_INSTALL_URL}")

   
    def check_easyocr(self) -> DependencyReport:
        if importlib.util.find_spec("easyocr") is None:
            return DependencyReport("EasyOCR", DependencyStatus.NOT_FOUND,
                                    "Not installed. Run: pip install easyocr")
        present = easyocr_models_present(list(EASYOCR_WEIGHT_FILES), self._model_dir)
        note = ("Model weights present." if present else
                "Installed. Model weights are not downloaded yet; the first use needs internet.")
        return DependencyReport("EasyOCR", DependencyStatus.AVAILABLE, note)

