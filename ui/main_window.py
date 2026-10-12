"""Main window: sidebar + workspace + task-queue polling."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from config.constants import APP_NAME, QUEUE_POLL_INTERVAL_MS, WINDOW_MIN_SIZE
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from document.template_registry import Template, TemplateRegistry
from repositories.settings_repository import SettingsRepository
from services.task_service import TaskService
from ui.navigation import Sidebar
from ui.theme import apply_theme
from ui.views.app_settings_view import AppSettingsView
from ui.views.base_view import BaseView
from ui.views.home_view import HomeView

log = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, root: tk.Tk, settings: AppSettings, repo: SettingsRepository,
                 registry: TemplateRegistry, tasks: TaskService) -> None:
        self.root, self._settings, self._repo = root, settings, repo
        self._registry, self._tasks = registry, tasks
        self._views: dict[str, BaseView] = {}
        self._current: str | None = None

        root.title(APP_NAME)
        root.minsize(*WINDOW_MIN_SIZE)
        apply_theme(root)

        self._status = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self._status, anchor="w", relief="sunken").pack(side="bottom", fill="x")
        Sidebar(root, [("home", "Home"), ("settings", "Application Settings")], self.show).pack(side="left", fill="y")
        self._workspace = ttk.Frame(root)
        self._workspace.pack(side="left", fill="both", expand=True)

        self._views["home"] = HomeView(self._workspace, registry, self._on_template)
        self._views["settings"] = AppSettingsView(self._workspace, settings, self._save_settings)
        self.show("home")

        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(QUEUE_POLL_INTERVAL_MS, self._poll)

    def show(self, key: str) -> None:
        if self._current:
            self._views[self._current].pack_forget()
        self._views[key].pack(fill="both", expand=True)
        self._views[key].on_show()
        self._current = key

    def _on_template(self, template: Template) -> None:
        self._status.set(f"Selected template: {template.name}")

    def _save_settings(self, settings: AppSettings) -> None:
        try:
            self._repo.save(settings)
        except DocumentBuilderError as exc:
            messagebox.showerror("Could not save", f"{exc}\n\n{exc.hint}")
            return
        self._settings = settings
        self._status.set("Settings saved")

    def _poll(self) -> None:
        """Main-thread consumer of worker events."""
        try:
            self._tasks.poll()
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("Event dispatch failed")
        self.root.after(QUEUE_POLL_INTERVAL_MS, self._poll)

    def _close(self) -> None:
        self._tasks.shutdown()
        self.root.destroy()
