"""Application entry point and composition root."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import messagebox

from config import paths
from config.logging_config import setup_logging
from core.exceptions import DocumentBuilderError
from core.schema_validator import SchemaValidator
from document.template_registry import TemplateRegistry
from repositories.settings_repository import SettingsRepository
from services.task_service import TaskService
from ui.main_window import MainWindow


def main() -> int:
    paths.ensure_dirs(paths.config_dir(), paths.logs_dir(), paths.temp_dir())
    repo = SettingsRepository(paths.config_dir())
    settings = repo.load()
    setup_logging(paths.logs_dir(), settings.verbose_logging)
    log = logging.getLogger("app")

    registry = TemplateRegistry(SchemaValidator())
    root = tk.Tk()
    try:
        registry.load()
    except DocumentBuilderError as exc:
        log.error("Template load failed: %s", exc)
        messagebox.showerror("Template error", str(exc))
        root.destroy()
        return 1

    MainWindow(root, settings, repo, registry, TaskService())
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
