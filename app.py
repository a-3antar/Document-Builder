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
from image_processing.easyocr_engine import EasyOcrEngine
from image_processing.image_preprocessor import ImagePreprocessor
from image_processing.pdf_loader import PdfLoader
from image_processing.processing_pipeline import ProcessingPipeline
from image_processing.tesseract_ocr import TesseractEngine
from repositories.settings_repository import SecretStore, SettingsRepository
from services.ai_service import AiService
from services.app_services import AppServices
from services.dependency_service import DependencyService
from services.document_service import DocumentService
from services.ocr_service import OcrService
from services.task_service import TaskService
from ui.main_window import MainWindow
from services.review_service import ReviewService


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


def build_ocr_services(repo: SettingsRepository, providers: ProviderRegistry,
                       models: ModelRegistry) -> tuple[OcrService, DependencyService]:
    """Wire OCR engines, pipeline and dependency checks."""
    tesseract = TesseractEngine(lambda: repo.load().tesseract_path, temp_dir=paths.temp_dir())
    pdf = PdfLoader(lambda: repo.load().poppler_path)
    pipeline = ProcessingPipeline(ImagePreprocessor(), pdf)
    ocr = OcrService(providers, models, pipeline, tesseract, EasyOcrEngine(), pdf, paths.temp_dir())
    deps = DependencyService(repo.load, lambda: providers.create(ProviderId.OLLAMA.value), tesseract)
    return ocr, deps


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
    models = ModelRegistry(providers)
    ocr, deps = build_ocr_services(repo, providers, models)
    services = AppServices(repo, TaskService(), templates, providers, models,
                           AiService(providers, validator), secrets, build_document_service(),
                           ocr, deps, ReviewService(validator))
    MainWindow(root, settings, services)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())