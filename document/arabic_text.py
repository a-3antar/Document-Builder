"""Arabic shaping for ReportLab: ONE path = arabic-reshaper, then python-bidi."""
from __future__ import annotations

from typing import Protocol

from core.exceptions import DependencyMissingError
from document.text_utils import Direction


class TextShaper(Protocol):
    def reshape(self, text: str) -> str: ...
    def to_visual(self, line: str, direction: Direction) -> str: ...


class ArabicShaper:
    """Reshape in logical order (wrap here), convert each line to visual order once."""

    def __init__(self) -> None:
        self._reshape = None
        self._display = None

    def _load(self) -> None:
        if self._reshape:
            return
        try:
            import arabic_reshaper
            try:
                from bidi import get_display
            except ImportError:  # python-bidi < 0.5
                from bidi.algorithm import get_display
        except ImportError as exc:
            raise DependencyMissingError(
                "Arabic PDF export needs 'arabic-reshaper' and 'python-bidi'.",
                hint="Run: pip install arabic-reshaper python-bidi") from exc
        self._reshape, self._display = arabic_reshaper.reshape, get_display

    def reshape(self, text: str) -> str:
        self._load()
        return self._reshape(text)

    def to_visual(self, line: str, direction: Direction) -> str:
        self._load()
        return self._display(line, base_dir="R" if direction == "rtl" else "L")
