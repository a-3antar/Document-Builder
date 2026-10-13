"""Common view base class and shared UI helpers."""
from __future__ import annotations

from tkinter import ttk
from typing import Any

from config.settings import AppSettings
from ui.theme import PAD


def error_text(exc: BaseException) -> str:
    """User-facing message plus the next-step hint when available."""
    hint = getattr(exc, "hint", "")
    return f"{exc} {hint}".strip()


class BaseView(ttk.Frame):
    title = ""
    subtitle = ""

    def __init__(self, parent: Any) -> None:
        super().__init__(parent, padding=PAD * 2)
        ttk.Label(self, text=self.title, style="Title.TLabel").pack(anchor="w")
        if self.subtitle:
            ttk.Label(self, text=self.subtitle, style="Subtle.TLabel").pack(anchor="w", pady=(0, PAD))

    def on_show(self) -> None:
        """Called each time the view becomes visible."""

    def settings_changed(self, settings: AppSettings) -> None:
        """Called after settings were saved successfully."""
