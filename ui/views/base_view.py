"""Common view base class."""
from __future__ import annotations

from tkinter import ttk

from ui.theme import PAD


class BaseView(ttk.Frame):
    title = ""
    subtitle = ""

    def __init__(self, parent) -> None:
        super().__init__(parent, padding=PAD * 2)
        ttk.Label(self, text=self.title, style="Title.TLabel").pack(anchor="w")
        if self.subtitle:
            ttk.Label(self, text=self.subtitle, style="Subtle.TLabel").pack(anchor="w", pady=(0, PAD))

    def on_show(self) -> None:
        """Called each time the view becomes visible."""
