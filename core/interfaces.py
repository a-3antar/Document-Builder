"""Abstract interfaces implemented in later stages."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelInfo:
    name: str
    supports_vision: bool | None = None  # None = unknown


class AiProvider(ABC):
    """Strategy interface for AI backends."""

    id: str

    @abstractmethod
    def check_connection(self) -> tuple[bool, str]: ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    def generate_text(self, prompt: str, model: str, **options: Any) -> str: ...

    def analyze_image(self, image: Path, prompt: str, model: str, **options: Any) -> str:
        raise NotImplementedError(f"{self.id} does not support image analysis")


class OcrEngine(ABC):
    id: str

    @abstractmethod
    def is_available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def extract(self, image: Path, languages: str) -> Any: ...


@dataclass(frozen=True)
class ExportResult:
    path: Path
    size_bytes: int
    duration_seconds: float


class BaseExporter(ABC):
    @abstractmethod
    def export(self, content: Any, output_path: Path) -> ExportResult: ...

    @abstractmethod
    def supports(self, feature: str) -> bool: ...
