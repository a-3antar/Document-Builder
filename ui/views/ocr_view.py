"""Image & OCR: import files, run OCR, review text, export."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from config.constants import (OCR_UNCERTAIN_CLOSE, OCR_UNCERTAIN_OPEN, OcrMethod, OutputFormat,
                              ProviderId, SUPPORTED_IMAGE_EXTENSIONS)
from config.settings import AppSettings
from core.exceptions import OcrModelDownloadRequiredError
from core.interfaces import ExportResult
from core.models import OCRResult
from document.ocr_converter import ocr_text_to_document
from image_processing.image_preprocessor import PreprocessOptions
from services.app_services import AppServices
from services.ocr_service import OcrRequest
from services.task_service import EventKind, TaskContext, TaskEvent
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text

_METHODS = {"Gemini Vision (cloud)": OcrMethod.GEMINI_VISION,
            "Ollama Vision (local)": OcrMethod.OLLAMA_VISION,
            "Tesseract (local)": OcrMethod.TESSERACT,
            "EasyOCR (local)": OcrMethod.EASYOCR,
            "OCR + AI formatting": OcrMethod.OCR_PLUS_AI}
_BASE = {"Tesseract": OcrMethod.TESSERACT, "EasyOCR": OcrMethod.EASYOCR}
_VISION_PROVIDER = {OcrMethod.GEMINI_VISION: ProviderId.GEMINI.value,
                    OcrMethod.OLLAMA_VISION: ProviderId.OLLAMA.value}
_FORMATS = {"Word": OutputFormat.DOCX, "Excel": OutputFormat.XLSX, "PDF": OutputFormat.PDF}
_MARKER_RE = rf"\{OCR_UNCERTAIN_OPEN[0]}\{OCR_UNCERTAIN_OPEN[1]}.*?\{OCR_UNCERTAIN_CLOSE[0]}\{OCR_UNCERTAIN_CLOSE[1]}"


class OcrView(BaseView):
    title = "Image & OCR"
    subtitle = "Import images or PDFs, extract text, review it, then export."

    def __init__(self, parent: Any, services: AppServices,
                 get_settings: Callable[[], AppSettings]) -> None:
        super().__init__(parent)
        self._svc, self._get_settings = services, get_settings
        self._files: list[Path] = []
        self._task: int | None = None
        self._result: OCRResult | None = None
        self._build()

    # --- layout ---
    def _build(self) -> None:
        files = ttk.Frame(self)
        files.pack(fill="x")
        self._list = tk.Listbox(files, height=4)
        self._list.pack(side="left", fill="x", expand=True)
        col = ttk.Frame(files)
        col.pack(side="left", padx=PAD)
        for text, cmd in (("Add files...", self._add), ("Remove", self._remove), ("Clear", self._clear)):
            ttk.Button(col, text=text, command=cmd).pack(fill="x", pady=1)

        opts = ttk.Frame(self)
        opts.pack(fill="x", pady=PAD)
        self._method = tk.StringVar(value=list(_METHODS)[2])
        method = ttk.Combobox(opts, textvariable=self._method, state="readonly",
                              values=list(_METHODS), width=24)
        self._lang = tk.StringVar(value=self._get_settings().ocr_languages)
        self._base = tk.StringVar(value="Tesseract")
        self._base_box = ttk.Combobox(opts, textvariable=self._base, state="readonly",
                                      values=list(_BASE), width=12)
        ttk.Label(opts, text="Method").grid(row=0, column=0, sticky="w")
        method.grid(row=0, column=1, padx=PAD)
        ttk.Label(opts, text="Languages (e.g. ara+eng)").grid(row=0, column=2)
        ttk.Entry(opts, textvariable=self._lang, width=12).grid(row=0, column=3, padx=PAD)
        self._base_label = ttk.Label(opts, text="Base OCR")
        self._base_label.grid(row=0, column=4)
        self._base_box.grid(row=0, column=5, padx=PAD)
        method.bind("<<ComboboxSelected>>", lambda _e: self._method_changed())

        self._flags = {k: tk.BooleanVar(value=v) for k, v in (
            ("auto_orient", True), ("grayscale", True), ("autocontrast", True),
            ("denoise", False), ("preserve", True))}
        flags = ttk.Frame(self)
        flags.pack(fill="x")
        for key, text in (("auto_orient", "Auto-orient"), ("grayscale", "Grayscale"),
                          ("autocontrast", "Enhance contrast"), ("denoise", "Reduce noise"),
                          ("preserve", "Keep original wording (AI step)")):
            ttk.Checkbutton(flags, text=text, variable=self._flags[key]).pack(side="left", padx=(0, PAD))

        run = ttk.Frame(self)
        run.pack(fill="x", pady=PAD)
        self._run_btn = ttk.Button(run, text="Run OCR", command=self._run)
        self._run_btn.pack(side="left")
        self._cancel_btn = ttk.Button(run, text="Cancel", command=self._cancel, state="disabled")
        self._cancel_btn.pack(side="left", padx=PAD // 2)
        self._progress = ttk.Progressbar(run, maximum=100, length=200)
        self._progress.pack(side="left", padx=PAD)
        self._status = tk.StringVar()
        ttk.Label(run, textvariable=self._status).pack(side="left")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self._orig = self._pane(panes, "Original OCR text (read-only)", editable=False)
        self._edit = self._pane(panes, "Reviewed text (editable)", editable=True)

        export = ttk.Frame(self)
        export.pack(fill="x", pady=(PAD, 0))
        ttk.Label(export, text="Title").pack(side="left")
        self._title_var = tk.StringVar(value="OCR result")
        ttk.Entry(export, textvariable=self._title_var, width=28).pack(side="left", padx=PAD)
        self._fmt = tk.StringVar(value="Word")
        ttk.Combobox(export, textvariable=self._fmt, state="readonly", width=8,
                     values=list(_FORMATS)).pack(side="left")
        self._export_btn = ttk.Button(export, text="Export...", command=self._export, state="disabled")
        self._export_btn.pack(side="left", padx=PAD)
        self._method_changed()

    def _pane(self, panes: ttk.PanedWindow, label: str, editable: bool) -> tk.Text:
        frame = ttk.Labelframe(panes, text=label)
        text = tk.Text(frame, wrap="word", height=12, state="normal" if editable else "disabled")
        text.tag_configure("uncertain", background="#FFE08A")
        text.pack(fill="both", expand=True)
        panes.add(frame, weight=1)
        return text

    def settings_changed(self, settings: AppSettings) -> None:
        self._lang.set(settings.ocr_languages)

    def _method_changed(self) -> None:
        show = _METHODS[self._method.get()] is OcrMethod.OCR_PLUS_AI
        for w in (self._base_label, self._base_box):
            w.grid() if show else w.grid_remove()

    # --- files ---
    def _add(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_IMAGE_EXTENSIONS | {".pdf"}))
        for name in filedialog.askopenfilenames(filetypes=[("Images and PDF", exts)]):
            if Path(name) not in self._files:
                self._files.append(Path(name))
                self._list.insert("end", name)
        if self._files and self._title_var.get() == "OCR result":
            self._title_var.set(self._files[0].stem)

    def _remove(self) -> None:
        for i in reversed(self._list.curselection()):
            self._list.delete(i)
            del self._files[i]

    def _clear(self) -> None:
        self._list.delete(0, "end")
        self._files.clear()

    # --- run ---
    def _request(self) -> OcrRequest | None:
        s = self._get_settings()
        method = _METHODS[self._method.get()]
        provider = _VISION_PROVIDER.get(method, s.provider)
        model = s.models.get(provider, "")
        needs_ai = method in _VISION_PROVIDER or method is OcrMethod.OCR_PLUS_AI
        if needs_ai and not model:
            messagebox.showinfo("Image & OCR", f"Select a {provider} model in AI Settings first.")
            return None
        if needs_ai and provider == ProviderId.GEMINI.value and not messagebox.askokcancel(
                "Cloud processing", "Image content will be sent to Google Gemini. Continue?"):
            return None
        opts = PreprocessOptions(auto_orient=self._flags["auto_orient"].get(),
                                 grayscale=self._flags["grayscale"].get(),
                                 autocontrast=self._flags["autocontrast"].get(),
                                 denoise=self._flags["denoise"].get())
        return OcrRequest(tuple(self._files), method, self._lang.get().strip(), opts,
                          _BASE[self._base.get()], provider, model, self._flags["preserve"].get())

    def _run(self) -> None:
        if not self._files:
            messagebox.showinfo("Image & OCR", "Add at least one image or PDF.")
            return
        req = self._request()
        if req is None:
            return
        self._busy(True, "Starting...")
        if all(f.suffix.lower() == ".pdf" for f in self._files):
            self._task = self._svc.tasks.submit(self._probe_work, list(self._files),
                                                on_event=lambda e: self._on_probe(e, req))
        else:
            self._start_ocr(req)

    def _start_ocr(self, req: OcrRequest) -> None:
        self._task = self._svc.tasks.submit(lambda ctx: self._svc.ocr.run(req, ctx),
                                            on_event=self._on_event)

    def _probe_work(self, ctx: TaskContext, files: list[Path]) -> list:
        return [(f, self._svc.ocr.probe_pdf(f)) for f in files]

    def _on_probe(self, event: TaskEvent, req: OcrRequest) -> None:
        if event.kind is not EventKind.RESULT:
            self._on_event(event)
            return
        probes = event.payload
        if all(p.has_text for _, p in probes) and messagebox.askyesno(
                "Text-based PDF", "These PDFs contain selectable text. Use the embedded text "
                                  "instead of OCR?"):
            text = "\n\n".join(p.text for _, p in probes)
            self._busy(False)
            self._show(OCRResult(", ".join(f.name for f, _ in probes), "pypdf", text))
            return
        self._start_ocr(req)

    def _cancel(self) -> None:
        if self._task is not None:
            self._svc.tasks.cancel(self._task)

    def _busy(self, busy: bool, message: str = "") -> None:
        self._run_btn.state(["disabled" if busy else "!disabled"])
        self._cancel_btn.state(["!disabled" if busy else "disabled"])
        self._progress["value"] = 0
        if message:
            self._status.set(message)

    def _on_event(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS:
            self._progress["value"] = event.payload
            self._status.set(event.message)
            return
        self._busy(False)
        self._svc.ocr.easyocr.allow_download = False  # permission is per run
        if event.kind is EventKind.ERROR:
            self._on_error(event.payload)
        elif event.kind is EventKind.CANCELLED:
            self._status.set("Cancelled.")
        else:
            self._show(event.payload)

    def _on_error(self, exc: BaseException) -> None:
        self._status.set("Failed.")
        if isinstance(exc, OcrModelDownloadRequiredError) and messagebox.askyesno(
                "Download required", f"{exc}\n\nDownload the model files now?"):
            self._svc.ocr.easyocr.allow_download = True
            self._run()
            return
        messagebox.showerror("OCR failed", error_text(exc))

    # --- review ---
    def _show(self, result: OCRResult) -> None:
        self._result = result
        self._progress["value"] = 100
        self._set_text(self._orig, result.original_text, editable=False)
        self._set_text(self._edit, result.corrected_text or result.original_text, editable=True)
        flagged = [s for s in result.segments if s.uncertain]
        for seg in flagged:
            self._mark(self._orig, seg.text)
        self._mark(self._edit, _MARKER_RE, regex=True)
        self._status.set(f"Done. {len(flagged)} uncertain line(s) highlighted - review before export."
                         if flagged else "Done. Review the text before export.")
        self._export_btn.state(["!disabled"])

    @staticmethod
    def _set_text(widget: tk.Text, text: str, editable: bool) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.tag_remove("uncertain", "1.0", "end")
        if not editable:
            widget.configure(state="disabled")

    @staticmethod
    def _mark(widget: tk.Text, pattern: str, regex: bool = False) -> None:
        if not pattern:
            return
        start, count = "1.0", tk.IntVar()
        while pos := widget.search(pattern, start, "end", count=count, regexp=regex):
            end = f"{pos}+{count.get()}c"
            widget.tag_add("uncertain", pos, end)
            start = end

    # --- export ---
    def _export(self) -> None:
        text = self._edit.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Export", "There is no text to export.")
            return
        left = text.count(OCR_UNCERTAIN_OPEN)
        if left and not messagebox.askyesno(
                "Unresolved markers", f"The text still has {left} uncertain marker(s). Export anyway?"):
            return
        fmt = _FORMATS[self._fmt.get()]
        content = ocr_text_to_document(text, self._title_var.get().strip() or "OCR result")
        template = self._svc.templates.get("blank_structured")
        folder = self._get_settings().output_dir
        options: dict[str, Any] = {"defaultextension": f".{fmt.value}",
                                   "filetypes": [(self._fmt.get(), f"*.{fmt.value}")],
                                   "initialfile": self._svc.documents.suggest_filename(content, fmt)}
        if folder and Path(folder).is_dir():
            options["initialdir"] = folder
        chosen = filedialog.asksaveasfilename(**options)  # asks before overwriting
        if not chosen:
            return
        self._busy(True, "Exporting...")
        self._svc.tasks.submit(
            lambda ctx: self._svc.documents.export(content, template, fmt, Path(chosen), overwrite=True),
            on_event=self._on_exported)

    def _on_exported(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS:
            return
        self._busy(False)
        if event.kind is EventKind.ERROR:
            self._status.set("Export failed.")
            messagebox.showerror("Export failed", error_text(event.payload))
        elif event.kind is EventKind.RESULT:
            res: ExportResult = event.payload
            self._status.set(f"Saved {res.path.name} ({res.size_bytes / 1024:.1f} KB).")
            if res.warnings:
                messagebox.showwarning("Export notes", "\n".join(f"- {w}" for w in res.warnings))