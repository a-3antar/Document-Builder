"""Bundle of shared services passed to the UI (explicit DI, no globals)."""
from __future__ import annotations

from dataclasses import dataclass

from ai.model_registry import ModelRegistry, ProviderRegistry
from document.template_registry import TemplateRegistry
from repositories.settings_repository import SecretStore, SettingsRepository
from services.ai_service import AiService
from services.dependency_service import DependencyService
from services.document_service import DocumentService
from services.ocr_service import OcrService
from services.review_service import ReviewService
from services.task_service import TaskService


@dataclass(frozen=True)
class AppServices:
    settings_repo: SettingsRepository
    tasks: TaskService
    templates: TemplateRegistry
    providers: ProviderRegistry
    models: ModelRegistry
    ai: AiService
    secrets: SecretStore
    documents: DocumentService
    ocr: OcrService
    deps: DependencyService
    review: ReviewService