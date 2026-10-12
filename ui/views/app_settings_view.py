"""Application settings: output defaults and OCR languages."""
from __future__ import annotations

from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from typing import Callable

from config.constants import OcrMethod, OutputFormat
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from ui.theme import PAD
from ui.views.base_view import BaseView


class AppSettingsView(BaseView):
    title = "Application Settings"
    subtitle = "Defaults for output and OCR."

    def __init__(self, parent, settings: AppSettings, on_save: Callable[[AppSettings], None]) -> None:
        super().__init__(parent)
        self._settings = settings
        self._on_save = on_save
        self._vars = {
            "output_format": tk.StringVar(value=settings.output_format),
            "output_dir": tk.StringVar(value=settings.output_dir),
            "ocr_method": tk.StringVar(value=settings.ocr_method),
            "ocr_languages": tk.StringVar(value=settings.ocr_languages),
            "tesseract_path": tk.StringVar(value=settings.tesseract_path),
            "poppler_path": tk.StringVar(value=settings.poppler_path),
        }
        form = ttk.Frame(self)
        form.pack(anchor="w")
        self._row(form, 0, "Default output format", ttk.Combobox(
            form, textvariable=self._vars["output_format"], state="readonly",
            values=[f.value for f in OutputFormat], width=18))
        self._row(form, 1, "Output folder", self._path_entry(form, "output_dir", folder=True))
        self._row(form, 2, "OCR method", ttk.Combobox(
            form, textvariable=self._vars["ocr_method"], state="readonly",
            values=[m.value for m in OcrMethod], width=18))
        self._row(form, 3, "OCR languages (Tesseract)", ttk.Entry(form, textvariable=self._vars["ocr_languages"], width=20))
        self._row(form, 4, "Tesseract path (optional)", self._path_entry(form, "tesseract_path"))
        self._row(form, 5, "Poppler folder (optional)", self._path_entry(form, "poppler_path", folder=True))
        ttk.Button(self, text="Save", command=self._save).pack(anchor="w", pady=PAD)

    @staticmethod
    def _row(form, row: int, label: str, widget) -> None:
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, PAD), pady=4)
        widget.grid(row=row, column=1, sticky="w", pady=4)

    def _path_entry(self, form, key: str, folder: bool = False) -> ttk.Frame:
        frame = ttk.Frame(form)
        ttk.Entry(frame, textvariable=self._vars[key], width=42).pack(side="left")

        def browse() -> None:
            chosen = filedialog.askdirectory() if folder else filedialog.askopenfilename()
            if chosen:
                self._vars[key].set(chosen)

        ttk.Button(frame, text="Browse", command=browse).pack(side="left", padx=4)
        return frame

    def _save(self) -> None:
        values = {k: v.get().strip() for k, v in self._vars.items()}
        updated = AppSettings.from_dict({**self._settings.to_dict(), **values}) \
            if self._valid(values) else None
        if updated:
            self._settings = updated
            self._on_save(updated)

    def _valid(self, values: dict[str, str]) -> bool:
        try:
            AppSettings.from_dict({**self._settings.to_dict(), **values})
            return True
        except DocumentBuilderError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return False
