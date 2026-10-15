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

OLLAMA_INSTALL_URL: Final = "https://ollama.com/download"
GEMINI_KEY_URL: Final = "https://aistudio.google.com/apikey"
GEMINI_ENV_VARS: Final = ("ALT_GEMINI_KEY", "GEMINI_API_KEY")
GEMINI_SECRET_NAME: Final = "gemini"

# --- Export (Stage 5) ---
# (regular, bold) file names looked up in resources/fonts; first match wins.
ARABIC_FONT_FILES: Final = (
    ("Amiri-Regular.ttf", "Amiri-Bold.ttf"),
    ("NotoNaskhArabic-Regular.ttf", "NotoNaskhArabic-Bold.ttf"),
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
)
# Built-in PDF fonts allowed in templates -> bold variant.
PDF_LATIN_FONTS: Final = (
    ("Helvetica", "Helvetica-Bold"),
    ("Times-Roman", "Times-Bold"),
    ("Courier", "Courier-Bold"),
)
FORMULA_MAX_LENGTH: Final = 255
FORMULA_ALLOWED_FUNCTIONS: Final = frozenset(
    {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA", "ROUND", "ABS", "IF"})
EXCEL_TABLE_STYLE: Final = "TableStyleMedium2"
EXCEL_MAX_COL_WIDTH: Final = 60
DEFAULT_ACCENT_HEX: Final = "1F4E78"

# --- OCR (Stage 4) ---
TESSERACT_URL: Final = "https://github.com/UB-Mannheim/tesseract/wiki"
POPPLER_URL: Final = "https://github.com/oschwartz10612/poppler-windows/releases"
TESSERACT_WIN_PATHS: Final = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
OCR_MAX_EDGE_PX: Final = 3000
PDF_RENDER_DPI: Final = 200
OCR_CONFIDENCE_THRESHOLD: Final = 0.6
OCR_SUBPROCESS_TIMEOUT: Final = 120
OCR_UNCERTAIN_OPEN: Final = "[?"
OCR_UNCERTAIN_CLOSE: Final = "?]"
PDF_MIN_CHARS_PER_PAGE: Final = 10
TESSERACT_TO_EASYOCR: Final = {"ara": "ar", "eng": "en"}
EASYOCR_DETECTOR_FILE: Final = "craft_mlt_25k.pth"
EASYOCR_WEIGHT_FILES: Final = {"ar": "arabic.pth", "en": "english_g2.pth"}
LANGUAGE_NAMES: Final = {"ara": "Arabic", "eng": "English"}
