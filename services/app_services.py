"""Bundle of shared services passed to the UI (explicit DI, no globals)."""
from __future__ import annotations

from dataclasses import dataclass

from ai.model_registry import ModelRegistry, ProviderRegistry
from document.template_registry import TemplateRegistry
from repositories.settings_repository import SecretStore, SettingsRepository
from services.ai_service import AiService
from services.document_service import DocumentService
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
