"""Structured Review: edit content in the structured editor, then export."""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from config.constants import OutputFormat
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from core.interfaces import ExportResult
from core.models import DocumentContentModel, WorkbookContentModel
from document.template_registry import Template
from services.app_services import AppServices
from services.task_service import EventKind, TaskContext, TaskEvent
from ui.components.content_preview import render_preview
from ui.components.structured_editor import StructuredEditor
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text

_FORMAT_LABELS = {OutputFormat.DOCX: "Word", OutputFormat.XLSX: "Excel", OutputFormat.PDF: "PDF"}
Content = DocumentContentModel | WorkbookContentModel


class ReviewView(BaseView):
    title = "Structured Review"
    subtitle = "Check and edit the content, then export it."

    def __init__(self, parent: Any, services: AppServices,
                 get_settings: Callable[[], AppSettings]) -> None:
        super().__init__(parent)
        self._svc, self._get_settings = services, get_settings
        self._template: Template | None = None
        self._workbook: WorkbookContentModel | None = None
        self._last_path: Path | None = None
        self._by_label = {label: fmt for fmt, label in _FORMAT_LABELS.items()}

        self._info = tk.StringVar()
        ttk.Label(self, textvariable=self._info, style="Subtle.TLabel", wraplength=800,
                  justify="left").pack(anchor="w")
        self._holder = ttk.Frame(self)
        self._holder.pack(fill="both", expand=True, pady=PAD)
        self._empty = ttk.Label(self._holder, text="Nothing to review yet. "
                                "Generate a document or run OCR first.")
        self._empty.pack(anchor="nw")
        self._editor = StructuredEditor(self._holder)
        self._preview_frame, self._preview = self._make_preview(self._holder)

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Output").pack(side="left")
        self._fmt = tk.StringVar(value=_FORMAT_LABELS[OutputFormat.DOCX])
        ttk.Combobox(bar, textvariable=self._fmt, state="readonly", width=10,
                     values=list(_FORMAT_LABELS.values())).pack(side="left", padx=PAD)
        self._export_btn = ttk.Button(bar, text="Export...", command=self._export, state="disabled")
        self._export_btn.pack(side="left")
        self._folder_btn = ttk.Button(bar, text="Open folder", command=self._open_folder,
                                      state="disabled")
        self._folder_btn.pack(side="left", padx=PAD)
        self._progress = ttk.Progressbar(bar, maximum=100, length=180)
        self._progress.pack(side="left", padx=PAD)
        self._status = tk.StringVar()
        ttk.Label(bar, textvariable=self._status).pack(side="left")

    @staticmethod
    def _make_preview(parent: Any) -> tuple[ttk.Frame, tk.Text]:
        frame = ttk.Frame(parent)
        text = tk.Text(frame, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        return frame, text

    # --- loading ---
    def load(self, content: Content, template: Template, source: str = "") -> None:
        """Show content for review (called by other views through MainWindow)."""
        self._template = template
        for widget in (self._empty, self._editor, self._preview_frame):
            widget.pack_forget()
        note = "Review and correct the content before exporting."
        if content.needs_review:
            note = "This content came from OCR or AI and needs review. " + note
        if isinstance(content, DocumentContentModel):
            self._workbook = None
            self._editor.set_content(content)
            self._editor.pack(fill="both", expand=True)
            fmt = OutputFormat(self._get_settings().output_format)
        else:
            self._workbook = content
            self._preview.configure(state="normal")
            self._preview.delete("1.0", "end")
            self._preview.insert("1.0", render_preview(content))
            self._preview.configure(state="disabled")
            self._preview_frame.pack(fill="both", expand=True)
            fmt = OutputFormat.XLSX
            note = ("Workbook content is read-only here (table and chart editing comes later). "
                    + note)
        self._fmt.set(_FORMAT_LABELS[fmt])
        self._info.set(f"Template: {template.name}" + (f" | Source: {source}" if source else "")
                       + f". {note}")
        self._status.set("")
        self._export_btn.state(["!disabled"])

    # --- export ---
    def _prepare(self) -> Content | None:
        """Run editor and schema checks; None means the export must not continue."""
        if self._workbook is not None:
            return self._workbook
        issues = self._editor.issues()
        content = self._editor.get_content()
        blocking = [i for i in issues if i.blocking]
        if blocking:
            messagebox.showerror("Fix these first", "\n".join(f"- {i}" for i in blocking[:10]))
            return None
        try:
            schema = self._svc.review.validate_document(content)
        except DocumentBuilderError as exc:
            messagebox.showerror("Validation unavailable", error_text(exc))
            return None
        if schema:
            messagebox.showerror("Invalid content", "\n".join(f"- {i}" for i in schema[:10]))
            return None
        notes = [i for i in issues if not i.blocking]
        if notes and not messagebox.askyesno(
                "Review notes", "\n".join(f"- {i}" for i in notes[:10]) + "\n\nExport anyway?"):
            return None
        return content

    def _export(self) -> None:
        template = self._template
        content = self._prepare() if template else None
        if content is None or template is None:
            return
        fmt = self._by_label[self._fmt.get()]
        options: dict[str, Any] = {
            "title": "Export document", "defaultextension": f".{fmt.value}",
            "filetypes": [(_FORMAT_LABELS[fmt], f"*.{fmt.value}")],
            "initialfile": self._svc.documents.suggest_filename(content, fmt)}
        folder = self._get_settings().output_dir
        if folder and Path(folder).is_dir():
            options["initialdir"] = folder
        chosen = filedialog.asksaveasfilename(**options)  # asks before overwriting
        if not chosen:
            return
        self._busy(True, "Exporting...")
        self._svc.tasks.submit(self._export_work, content, template, fmt, Path(chosen),
                               on_event=self._on_exported)

    def _export_work(self, ctx: TaskContext, content: Content, template: Template,
                     fmt: OutputFormat, path: Path) -> ExportResult:
        """Worker thread: overwrite was already confirmed in the save dialog."""
        ctx.progress(30, "Creating file...")
        return self._svc.documents.export(content, template, fmt, path, overwrite=True)

    def _busy(self, busy: bool, message: str = "") -> None:
        self._export_btn.state(["disabled" if busy else "!disabled"])
        self._progress["value"] = 0
        if message:
            self._status.set(message)

    def _on_exported(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS:
            self._progress["value"] = event.payload
            self._status.set(event.message)
            return
        self._busy(False)
        if event.kind is EventKind.ERROR:
            self._status.set("Export failed.")
            messagebox.showerror("Export failed", error_text(event.payload))
        elif event.kind is EventKind.CANCELLED:
            self._status.set("Cancelled.")
        else:
            res: ExportResult = event.payload
            self._progress["value"] = 100
            self._last_path = res.path
            self._folder_btn.state(["!disabled"])
            self._status.set(f"Saved {res.path.name} ({res.size_bytes / 1024:.1f} KB).")
            if res.warnings:
                messagebox.showwarning("Export notes", "\n".join(f"- {w}" for w in res.warnings))

    def _open_folder(self) -> None:
        if self._last_path and hasattr(os, "startfile"):  # Windows only
            os.startfile(self._last_path.parent)  # noqa: S606