"""Sidebar navigation: shows only implemented views."""
from __future__ import annotations

from tkinter import ttk
from typing import Callable

from config.constants import SIDEBAR_WIDTH
from ui.theme import PAD


class Sidebar(ttk.Frame):
    def __init__(self, parent, items: list[tuple[str, str]], on_select: Callable[[str], None]) -> None:
        super().__init__(parent, width=SIDEBAR_WIDTH, padding=PAD // 2)
        self.pack_propagate(False)
        for key, label in items:
            ttk.Button(self, text=label, style="Nav.TButton",
                       command=lambda k=key: on_select(k)).pack(fill="x", pady=2)
