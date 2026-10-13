"""Home: template gallery."""
from __future__ import annotations

from tkinter import ttk
from typing import Callable

from document.template_registry import Template, TemplateRegistry
from ui.theme import PAD
from ui.views.base_view import BaseView


class HomeView(BaseView):
    title = "Home"
    subtitle = "Choose a template to start a new document."

    def __init__(self, parent, registry: TemplateRegistry, on_pick: Callable[[Template], None]) -> None:
        super().__init__(parent)
        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)
        for col, tpl in enumerate(registry.all()):
            card = ttk.Labelframe(grid, text=tpl.name, style="Card.TLabelframe")
            card.grid(row=0, column=col, padx=PAD // 2, pady=PAD // 2, sticky="n")
            ttk.Label(card, text=tpl.description, wraplength=200, justify="left").pack(anchor="w")
            ttk.Button(card, text="Select", command=lambda t=tpl: on_pick(t)).pack(anchor="e", pady=(PAD, 0))
