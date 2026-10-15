"""Main window: sidebar + workspace + task-queue polling."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from config.constants import APP_NAME, QUEUE_POLL_INTERVAL_MS, WINDOW_MIN_SIZE
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from core.models import DocumentContentModel, WorkbookContentModel
from document.template_registry import Template
from services.app_services import AppServices
from ui.navigation import Sidebar
from ui.theme import apply_theme
from ui.views.ai_settings_view import AiSettingsView
from ui.views.app_settings_view import AppSettingsView
from ui.views.base_view import BaseView, error_text
from ui.views.create_document_view import CreateDocumentView
from ui.views.dependencies_view import DependenciesView
from ui.views.home_view import HomeView
from ui.views.ocr_view import OcrView
from ui.views.review_view import ReviewView

log = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, root: tk.Tk, settings: AppSettings, services: AppServices) -> None:
        self.root, self._settings, self._svc = root, settings, services
        self._views: dict[str, BaseView] = {}
        self._current: str | None = None

        root.title(APP_NAME)
        root.minsize(*WINDOW_MIN_SIZE)
        apply_theme(root)

        self._status = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self._status, anchor="w", relief="sunken").pack(side="bottom", fill="x")
        Sidebar(root, [("home", "Home"), ("create", "Create Document"), ("ocr", "Image & OCR"),
                       ("review", "Structured Review"), ("ai", "AI Settings"),
                       ("settings", "Application Settings"), ("deps", "Dependencies")],
                self.show).pack(side="left", fill="y")
        self._workspace = ttk.Frame(root)
        self._workspace.pack(side="left", fill="both", expand=True)

        get_settings = lambda: self._settings  # noqa: E731
        self._review = ReviewView(self._workspace, services, get_settings)
        self._views["home"] = HomeView(self._workspace, services.templates, self._on_template)
        self._views["create"] = CreateDocumentView(self._workspace, services, get_settings,
                                                   self.open_review)
        self._views["ocr"] = OcrView(self._workspace, services, get_settings, self.open_review)
        self._views["review"] = self._review
        self._views["ai"] = AiSettingsView(self._workspace, settings, services, self._save_settings)
        self._views["settings"] = AppSettingsView(self._workspace, settings, self._save_settings)
        self._views["deps"] = DependenciesView(self._workspace, services, lambda: self.show("settings"))
        self.show("home")

        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(QUEUE_POLL_INTERVAL_MS, self._poll)

    def show(self, key: str) -> None:
        if self._current:
            self._views[self._current].pack_forget()
        self._views[key].pack(fill="both", expand=True)
        self._views[key].on_show()
        self._current = key

    def open_review(self, content: DocumentContentModel | WorkbookContentModel,
                    template: Template, source: str = "") -> None:
        """Load content into Structured Review and switch to it."""
        self._review.load(content, template, source)
        self._status.set(f"Reviewing content from {source or 'unknown source'}")
        self.show("review")

    def _on_template(self, template: Template) -> None:
        self._views["create"].set_template(template.id)  # type: ignore[attr-defined]
        self._status.set(f"Selected template: {template.name}")
        self.show("create")

    def _save_settings(self, settings: AppSettings) -> None:
        try:
            self._svc.settings_repo.save(settings)
        except DocumentBuilderError as exc:
            messagebox.showerror("Could not save", error_text(exc))
            return
        self._settings = settings
        for view in self._views.values():
            view.settings_changed(settings)
        self._status.set("Settings saved")

    def _poll(self) -> None:
        """Main-thread consumer of worker events."""
        try:
            self._svc.tasks.poll()
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("Event dispatch failed")
        self.root.after(QUEUE_POLL_INTERVAL_MS, self._poll)

    def _close(self) -> None:
        self._svc.tasks.shutdown()
        self.root.destroy()