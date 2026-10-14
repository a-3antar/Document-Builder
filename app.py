"""Application entry point and composition root."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import messagebox

from ai.gemini_provider import GeminiProvider
from ai.model_registry import ModelRegistry, ProviderRegistry
from ai.ollama_provider import OllamaProvider
from config import paths
from config.constants import GEMINI_SECRET_NAME, OutputFormat, ProviderId
from config.logging_config import setup_logging
from core.exceptions import DocumentBuilderError
from core.schema_validator import SchemaValidator
from document.excel_exporter import ExcelExporter
from document.pdf_exporter_reportlab import PdfExporter
from document.template_registry import TemplateRegistry
from document.word_exporter import WordExporter
from repositories.settings_repository import SecretStore, SettingsRepository
from services.ai_service import AiService
from services.app_services import AppServices
from services.document_service import DocumentService
from services.task_service import TaskService
from ui.main_window import MainWindow


def build_providers(repo: SettingsRepository, secrets: SecretStore) -> ProviderRegistry:
    """Register provider factories; settings are re-read per creation so changes apply at once."""
    providers = ProviderRegistry()
    providers.register(ProviderId.OLLAMA.value,
                       lambda: OllamaProvider(timeout=repo.load().timeout_seconds))
    providers.register(ProviderId.GEMINI.value,
                       lambda: GeminiProvider(lambda: secrets.get(GEMINI_SECRET_NAME),
                                              timeout=repo.load().timeout_seconds))
    return providers


def build_document_service() -> DocumentService:
    """Register one exporter factory per output format."""
    return DocumentService({
        OutputFormat.DOCX: WordExporter,
        OutputFormat.XLSX: ExcelExporter,
        OutputFormat.PDF: PdfExporter,
    })


def main() -> int:
    paths.ensure_dirs(paths.config_dir(), paths.logs_dir(), paths.temp_dir())
    repo = SettingsRepository(paths.config_dir())
    settings = repo.load()
    setup_logging(paths.logs_dir(), settings.verbose_logging)
    log = logging.getLogger("app")

    validator = SchemaValidator()
    templates = TemplateRegistry(validator)
    root = tk.Tk()
    try:
        templates.load()
    except DocumentBuilderError as exc:
        log.error("Template load failed: %s", exc)
        messagebox.showerror("Template error", str(exc))
        root.destroy()
        return 1

    secrets = SecretStore()
    providers = build_providers(repo, secrets)
    services = AppServices(repo, TaskService(), templates, providers,
                           ModelRegistry(providers), AiService(providers, validator), secrets,
                           build_document_service())
    MainWindow(root, settings, services)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
