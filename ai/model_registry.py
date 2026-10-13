"""Provider factory and discovered-model cache."""
from __future__ import annotations

from typing import Callable

from core.exceptions import ModelNotAvailableError, ProviderError
from core.interfaces import AiProvider, ModelInfo


class ProviderRegistry:
    """Factory: provider id -> new provider (so fresh settings apply)."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], AiProvider]] = {}

    def register(self, provider_id: str, factory: Callable[[], AiProvider]) -> None:
        self._factories[provider_id] = factory

    def create(self, provider_id: str) -> AiProvider:
        try:
            factory = self._factories[provider_id]
        except KeyError:
            raise ProviderError(f"Unknown provider '{provider_id}'.") from None
        return factory()


class ModelRegistry:
    """Caches discovered models; refresh is always explicit."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers
        self._cache: dict[str, list[ModelInfo]] = {}

    def refresh(self, provider_id: str) -> list[ModelInfo]:
        models = self._providers.create(provider_id).list_models()
        self._cache[provider_id] = models
        return models

    def cached(self, provider_id: str) -> list[ModelInfo]:
        return list(self._cache.get(provider_id, []))

    def require(self, provider_id: str, model: str, *, vision: bool = False) -> ModelInfo:
        """Validate a model before use; unknown vision support is allowed (caller may warn)."""
        models = self._cache.get(provider_id) or self.refresh(provider_id)
        info = next((m for m in models if m.name == model), None)
        if info is None:
            raise ModelNotAvailableError(f"Model '{model}' is not available for {provider_id}.",
                                         hint="Refresh the model list and choose another model.")
        if vision and info.supports_vision is False:
            raise ModelNotAvailableError(f"Model '{model}' does not support image input.",
                                         hint="Choose a vision-capable model.")
        return info
