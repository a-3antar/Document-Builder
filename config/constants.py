"""Global immutable constants. No mutable runtime state here."""
from __future__ import annotations

from enum import StrEnum
from typing import Final

APP_NAME: Final = "Document Builder AI"
APP_DIR_NAME: Final = "DocumentBuilderAI"
APP_VERSION: Final = "0.1.0"
SCHEMA_VERSION: Final = "1.0"

SETTINGS_FILE_NAME: Final = "settings.json"
KEYRING_SERVICE: Final = "DocumentBuilderAI"

OLLAMA_DEFAULT_URL: Final = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS: Final = 120
DEFAULT_MAX_IMAGE_EDGE_PX: Final = 1600
QUEUE_POLL_INTERVAL_MS: Final = 100

WINDOW_MIN_SIZE: Final = (1000, 650)
SIDEBAR_WIDTH: Final = 200


class OutputFormat(StrEnum):
    DOCX = "docx"
    XLSX = "xlsx"
    PDF = "pdf"


class ProviderId(StrEnum):
    OLLAMA = "ollama"
    GEMINI = "gemini"


class OcrMethod(StrEnum):
    GEMINI_VISION = "gemini_vision"
    OLLAMA_VISION = "ollama_vision"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    OCR_PLUS_AI = "ocr_plus_ai"


class ContentKind(StrEnum):
    DOCUMENT = "document"
    WORKBOOK = "workbook"


SUPPORTED_IMAGE_EXTENSIONS: Final = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"})
SUPPORTED_INPUT_EXTENSIONS: Final = SUPPORTED_IMAGE_EXTENSIONS | {".pdf", ".docx", ".xlsx"}
DEFAULT_TESSERACT_LANGS: Final = "ara+eng"
DEFAULT_EASYOCR_LANGS: Final = ("ar", "en")
