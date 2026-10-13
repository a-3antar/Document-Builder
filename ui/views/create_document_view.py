"""Create Document: instructions -> AI -> validated structured content preview."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from config.constants import ProviderId
from config.settings import AppSettings
from document.template_registry import Template
from services.ai_service import StructuredResult
from services.app_services import AppServices
from services.task_service import EventKind, TaskContext, TaskEvent
from ui.components.content_preview import render_preview
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text


class CreateDocumentView(BaseView):
    title = "Create Document"
    subtitle = "Describe the document you need. The AI returns structured content for review."

    def __init__(self, parent: Any, services: AppServices,
                 get_settings: Callable[[], AppSettings]) -> None:
        super().__init__(parent)
        self._svc, self._get_settings = services, get_settings
        self.last_result: StructuredResult | None = None
        self._by_name = {t.name: t for t in services.templates.all()}

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

    def set_template(self, template_id: str) -> None:
        self._tpl.set(self._svc.templates.get(template_id).name)

    def on_show(self) -> None:
        s = self._get_settings()
        model = s.models.get(s.provider)
        self._engine.set(f"Using {s.provider} / {model}" if model
                         else "No model selected - open AI Settings")

    def _write(self, text: str) -> None:
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.insert("1.0", text)
        self._out.configure(state="disabled")

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
        self._btn.state(["disabled"])
        self._progress["value"] = 0
        self._status.set("Starting...")
        self._svc.tasks.submit(self._work, s.provider, model, instructions,
                               self._by_name[self._tpl.get()], on_event=self._on_event)

    def _work(self, ctx: TaskContext, provider: str, model: str, instructions: str,
              template: Template) -> StructuredResult:
        """Worker thread: validate the model, then generate and validate content."""
        self._svc.models.require(provider, model)
        return self._svc.ai.generate_structured(provider, model, instructions, template, ctx)

    def _on_event(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS:
            self._progress["value"] = event.payload
            self._status.set(event.message)
            return
        self._btn.state(["!disabled"])
        self._progress["value"] = 100 if event.kind is EventKind.RESULT else 0
        if event.kind is EventKind.ERROR:
            self._status.set("Failed.")
            messagebox.showerror("Generation failed", error_text(event.payload))
        elif event.kind is EventKind.CANCELLED:
            self._status.set("Cancelled.")
        else:
            self._show_result(event.payload)

    def _show_result(self, result: StructuredResult) -> None:
        self.last_result = result
        if result.ok:
            self._write(render_preview(result.content))
            self._status.set("Content generated. Review it below.")
        else:
            issues = "\n".join(f"- {i}" for i in result.issues)
            self._write(f"The AI output did not match the schema:\n{issues}\n\n"
                        f"Original response:\n{result.raw}")
            self._status.set("Validation failed - retry or adjust your instructions.")
