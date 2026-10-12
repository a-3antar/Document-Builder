"""ttk styling."""
from __future__ import annotations

from tkinter import ttk

PAD = 12
FONT = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUB = ("Segoe UI", 10)


def apply_theme(root) -> None:
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", font=FONT)
    style.configure("Title.TLabel", font=FONT_TITLE)
    style.configure("Subtle.TLabel", foreground="#555555")
    style.configure("Nav.TButton", anchor="w", padding=(PAD, 8))
    style.configure("Card.TLabelframe", padding=PAD)
