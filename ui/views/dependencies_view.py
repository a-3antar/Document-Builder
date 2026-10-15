"""Dependencies: status of Ollama, Tesseract, EasyOCR and Poppler."""
from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable

from services.app_services import AppServices
from services.task_service import EventKind, TaskEvent
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text


class DependenciesView(BaseView):
    title = "Dependencies"
    subtitle = "External tools used by AI and OCR. The app works without the ones you do not need."

    def __init__(self, parent: Any, services: AppServices, open_settings: Callable[[], None]) -> None:
        super().__init__(parent)
        self._svc = services
        self._tree = ttk.Treeview(self, columns=("status", "details"), show="tree headings", height=6)
        for col, text, width in (("#0", "Component", 150), ("status", "Status", 110),
                                 ("details", "Details", 620)):
            self._tree.heading(col, text=text)
            self._tree.column(col, width=width, anchor="w")
        self._tree.pack(fill="x")
        bar = ttk.Frame(self)
        bar.pack(anchor="w", pady=PAD)
        self._btn = ttk.Button(bar, text="Re-check", command=self._recheck)
        self._btn.pack(side="left")
        ttk.Button(bar, text="Set paths in Application Settings", command=open_settings).pack(
            side="left", padx=PAD // 2)
        self._note = ttk.Label(self, style="Subtle.TLabel", wraplength=800, justify="left")
        self._note.pack(anchor="w")

    def on_show(self) -> None:
        self._recheck()

    def _recheck(self) -> None:
        self._btn.state(["disabled"])
        self._note.configure(text="Checking...")
        self._svc.tasks.submit(lambda ctx: self._svc.deps.check_all(), on_event=self._on_done)

    def _on_done(self, event: TaskEvent) -> None:
        self._btn.state(["!disabled"])
        if event.kind is not EventKind.RESULT:
            self._note.configure(text=error_text(event.payload) if event.kind is EventKind.ERROR
                                 else "Cancelled.")
            return
        self._tree.delete(*self._tree.get_children())
        for report in event.payload:
            self._tree.insert("", "end", text=report.name,
                              values=(report.status.value, report.message))
        self._note.configure(text="")