"""PDF input: text probe (pypdf) and page rendering (pdf2image + Poppler)."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from config.constants import PDF_MIN_CHARS_PER_PAGE, PDF_RENDER_DPI, POPPLER_URL
from core.exceptions import OcrDependencyNotInstalledError, PdfRenderError


@dataclass(frozen=True)
class PdfProbe:
    page_count: int
    text: str
    has_text: bool


def find_poppler_bin(configured: str = "", which: Callable[..., str | None] = shutil.which) -> Path | None:
    """Folder containing pdftoppm: configured folder (or its bin dirs), else PATH."""
    if configured.strip():
        base = Path(configured.strip())
        search = os.pathsep.join(str(p) for p in (base, base / "bin", base / "Library" / "bin"))
        found = which("pdftoppm", path=search)
    else:
        found = which("pdftoppm")
    return Path(found).parent if found else None

class PdfLoader:
    """Reads PDFs defensively; rendering is per page to limit memory."""

    def __init__(self, poppler_path: Callable[[], str] = lambda: "") -> None:
        self._poppler = poppler_path

    @staticmethod
    def _reader(path: Path) -> PdfReader:
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted and not reader.decrypt(""):
                raise PdfRenderError(f"'{path.name}' is password-protected.",
                                     hint="Remove the password and try again.")
            return reader
        except (PdfReadError, OSError, ValueError) as exc:
            raise PdfRenderError(f"'{path.name}' is not a readable PDF.",
                                 hint="The file may be damaged.") from exc

    def page_count(self, path: Path) -> int:
        return len(self._reader(path).pages)

    def probe(self, path: Path) -> PdfProbe:
        """Extract embedded text; `has_text` is False for scanned PDFs."""
        reader = self._reader(path)
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - pypdf raises many types
                parts.append("")
        text = "\n\n".join(parts).strip()
        meaningful = len(re.sub(r"\s+", "", text))
        return PdfProbe(len(parts), text, meaningful >= PDF_MIN_CHARS_PER_PAGE * max(len(parts), 1))

    def render_page(self, path: Path, page: int, dpi: int = PDF_RENDER_DPI) -> Image.Image:
        """Render one page (1-based) to an image."""
        try:
            from pdf2image import convert_from_path
            from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
        except ImportError as exc:
            raise OcrDependencyNotInstalledError("The 'pdf2image' package is not installed.",
                                                 hint="Run: pip install pdf2image") from exc
        poppler = find_poppler_bin(self._poppler())
        try:
            pages = convert_from_path(str(path), dpi=dpi, first_page=page, last_page=page,
                                      poppler_path=str(poppler) if poppler else None)
        except PDFInfoNotInstalledError as exc:
            raise PdfRenderError("Poppler was not found.",
                                 hint=f"Install it from {POPPLER_URL} or set its folder in Application Settings.") from exc
        except (PDFPageCountError, PDFSyntaxError) as exc:
            raise PdfRenderError(f"Page {page} of '{path.name}' could not be rendered.") from exc
        if not pages:
            raise PdfRenderError(f"Page {page} of '{path.name}' produced no image.")
        return pages[0]