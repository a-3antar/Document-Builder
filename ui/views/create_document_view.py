"""Create Document: instructions -> AI -> validated content preview -> export."""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from config.settings import AppSettings
from core.interfaces import ExportResult
from core.models import DocumentContentModel, WorkbookContentModel
from document.template_registry import Template
from services.ai_service import StructuredResult
from services.app_services import AppServices
from services.task_service import EventKind, TaskContext, TaskEvent
from ui.components.content_preview import render_preview
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text
from config.constants import ContentKind, OutputFormat, ProviderId

_FORMAT_LABELS = {OutputFormat.DOCX: "Word", OutputFormat.XLSX: "Excel", OutputFormat.PDF: "PDF"}


class CreateDocumentView(BaseView):
    title = "Create Document"
    subtitle = "Describe the document you need. The AI returns structured content for review."

    def __init__(self, parent: Any, services: AppServices,
                 get_settings: Callable[[], AppSettings]) -> None:
        super().__init__(parent)
        self._svc, self._get_settings = services, get_settings
        self.last_result: StructuredResult | None = None
        self._last_template: Template | None = None
        self._last_path: Path | None = None
        self._by_name = {t.name: t for t in services.templates.all()}
        self._by_label = {label: fmt for fmt, label in _FORMAT_LABELS.items()}

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Template").pack(side="left")
        self._tpl = tk.StringVar()
        combo = ttk.Combobox(top, textvariable=self._tpl, state="readonly",
                             values=list(self._by_name), width=28)
        combo.pack(side="left", padx=PAD)
        if self._by_name:
            combo.current(0)
        self._engine = tk.StringVar()
        ttk.Label(top, textvariable=self._engine, style="Subtle.TLabel").pack(side="left")

        ttk.Label(self, text="Instructions").pack(anchor="w", pady=(PAD, 0))
        self._instr = tk.Text(self, height=6, wrap="word")
        self._instr.pack(fill="x")

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=PAD)
        self._btn = ttk.Button(bar, text="Generate", command=self._generate)
        self._btn.pack(side="left")
        self._progress = ttk.Progressbar(bar, maximum=100, length=220)
        self._progress.pack(side="left", padx=PAD)
        self._status = tk.StringVar()
        ttk.Label(bar, textvariable=self._status).pack(side="left")

        ttk.Label(self, text="Result").pack(anchor="w")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self._out = tk.Text(frame, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, command=self._out.yview)
        self._out.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._out.pack(side="left", fill="both", expand=True)

        export = ttk.Frame(self)
        export.pack(fill="x", pady=(PAD, 0))
        ttk.Label(export, text="Output").pack(side="left")
        self._fmt = tk.StringVar(value=_FORMAT_LABELS[OutputFormat.DOCX])
        ttk.Combobox(export, textvariable=self._fmt, state="readonly", width=10,
                     values=list(_FORMAT_LABELS.values())).pack(side="left", padx=PAD)
        self._export_btn = ttk.Button(export, text="Export...", command=self._export,
                                      state="disabled")
        self._export_btn.pack(side="left")
        self._folder_btn = ttk.Button(export, text="Open folder", command=self._open_folder,
                                      state="disabled")
        self._folder_btn.pack(side="left", padx=PAD)

    def set_template(self, template_id: str) -> None:
        self._tpl.set(self._svc.templates.get(template_id).name)

    def on_show(self) -> None:
        s = self._get_settings()
        model = s.models.get(s.provider)
        self._engine.set(f"Using {s.provider} / {model}" if model
                         else "No model selected - open AI Settings")
        self._fmt.set(_FORMAT_LABELS[OutputFormat(s.output_format)])

    def _write(self, text: str) -> None:
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.insert("1.0", text)
        self._out.configure(state="disabled")

    # --- generation ---
    def _generate(self) -> None:
        s = self._get_settings()
        model = s.models.get(s.provider)
        instructions = self._instr.get("1.0", "end").strip()
        if not model:
            messagebox.showinfo("Create Document", "Select a model in AI Settings first.")
            return
        if not instructions or self._tpl.get() not in self._by_name:
            messagebox.showinfo("Create Document", "Choose a template and enter instructions.")
            return
        if s.provider == ProviderId.GEMINI.value and not messagebox.askokcancel(
                "Cloud processing", "Your instructions will be sent to Google Gemini. Continue?"):
            return
        self._busy(True, "Starting...")
        self._export_btn.state(["disabled"])
        template = self._by_name[self._tpl.get()]
        self._svc.tasks.submit(self._work, s.provider, model, instructions, template,
                               on_event=lambda e: self._on_generated(e, template))

    def _work(self, ctx: TaskContext, provider: str, model: str, instructions: str,
              template: Template) -> StructuredResult:
        """Worker thread: validate the model, then generate and validate content."""
        self._svc.models.require(provider, model)
        return self._svc.ai.generate_structured(provider, model, instructions, template, ctx)

    def _busy(self, busy: bool, message: str = "") -> None:
        self._btn.state(["disabled" if busy else "!disabled"])
        self._progress["value"] = 0
        if message:
            self._status.set(message)

    def _on_generated(self, event: TaskEvent, template: Template) -> None:
        if event.kind is EventKind.PROGRESS:
            self._progress["value"] = event.payload
            self._status.set(event.message)
            return
        self._busy(False)
        if event.kind is EventKind.ERROR:
            self._status.set("Failed.")
            messagebox.showerror("Generation failed", error_text(event.payload))
        elif event.kind is EventKind.CANCELLED:
            self._status.set("Cancelled.")
        else:
            self._progress["value"] = 100
            self._last_template = template
            self._show_result(event.payload)

    def _show_result(self, result: StructuredResult) -> None:
        self.last_result = result
        if result.ok:
            self._write(render_preview(result.content))
            if self._last_template and self._last_template.content_kind is ContentKind.WORKBOOK:
                self._fmt.set(_FORMAT_LABELS[OutputFormat.XLSX])  # workbook content belongs in Excel
            self._status.set("Content generated. Review it below, then export.")
            self._export_btn.state(["!disabled"])
        else:
            issues = "\n".join(f"- {i}" for i in result.issues)
            self._write(f"The AI output did not match the schema:\n{issues}\n\n"
                        f"Original response:\n{result.raw}")
            self._status.set("Validation failed - retry or adjust your instructions.")

    # --- export ---
    def _export(self) -> None:
        result, template = self.last_result, self._last_template
        if not (result and result.ok and template):
            return
        content: DocumentContentModel | WorkbookContentModel = result.content
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
        self._export_btn.state(["disabled"])
        self._svc.tasks.submit(self._export_work, content, template, fmt, Path(chosen),
                               on_event=self._on_exported)

    def _export_work(self, ctx: TaskContext, content: Any, template: Template,
                     fmt: OutputFormat, path: Path) -> ExportResult:
        """Worker thread: the user already confirmed overwrite in the save dialog."""
        ctx.progress(30, "Creating file...")
        return self._svc.documents.export(content, template, fmt, path, overwrite=True)

    def _on_exported(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS:
            self._progress["value"] = event.payload
            self._status.set(event.message)
            return
        self._busy(False)
        self._export_btn.state(["!disabled"])
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
