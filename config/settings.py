"""Runtime user settings (non-secret). Secrets live in keyring."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

from config.constants import (
    DEFAULT_MAX_IMAGE_EDGE_PX,
    DEFAULT_TESSERACT_LANGS,
    DEFAULT_TIMEOUT_SECONDS,
    OcrMethod,
    OutputFormat,
    ProviderId,
)
from core.exceptions import SettingsValidationError


@dataclass
class AppSettings:
    provider: str = ProviderId.OLLAMA.value
    models: dict[str, str] = field(default_factory=dict)  # provider -> model
    ocr_method: str = OcrMethod.TESSERACT.value
    ocr_languages: str = DEFAULT_TESSERACT_LANGS
    output_format: str = OutputFormat.DOCX.value
    output_dir: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_image_edge_px: int = DEFAULT_MAX_IMAGE_EDGE_PX
    tesseract_path: str = ""
    poppler_path: str = ""
    verbose_logging: bool = False

    def validate(self) -> None:
        """Raise SettingsValidationError on invalid values."""
        errors: list[str] = []
        for name, enum in (("provider", ProviderId), ("ocr_method", OcrMethod), ("output_format", OutputFormat)):
            if getattr(self, name) not in {e.value for e in enum}:
                errors.append(f"Invalid {name}: {getattr(self, name)!r}")
        if not 5 <= self.timeout_seconds <= 3600:
            errors.append("timeout_seconds must be between 5 and 3600")
        if not 200 <= self.max_image_edge_px <= 10000:
            errors.append("max_image_edge_px must be between 200 and 10000")
        if not self.ocr_languages.strip():
            errors.append("ocr_languages must not be empty")
        if errors:
            raise SettingsValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """Build from a dict, ignoring unknown keys; defaults fill gaps."""
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        settings.validate()
        return settings
