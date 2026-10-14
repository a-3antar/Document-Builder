"""Locate bundled Arabic fonts (resources/fonts)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.constants import ARABIC_FONT_FILES
from config.paths import resource_path
from core.exceptions import FontNotFoundError


@dataclass(frozen=True)
class ArabicFont:
    regular: Path
    bold: Path  # falls back to regular when no bold file exists


def find_arabic_font(font_dir: Path | None = None) -> ArabicFont:
    base = font_dir or resource_path("fonts")
    for regular, bold in ARABIC_FONT_FILES:
        if (base / regular).is_file():
            bold_path = base / bold
            return ArabicFont(base / regular, bold_path if bold_path.is_file() else base / regular)
    names = ", ".join(r for r, _ in ARABIC_FONT_FILES)
    raise FontNotFoundError("No Arabic font was found for PDF export.",
                            hint=f"Place one of [{names}] (OFL-licensed) in {base}.")
