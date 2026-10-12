# Document Builder AI

Windows desktop app (Tkinter) that builds Word/Excel/PDF documents with AI and OCR.
**Status: Batch 1 - MVP foundation (Stage 2).** AI providers, OCR, and exporters come in later batches.

## Setup
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Tests
```
python -m pytest        # or: python -m unittest discover -s tests -t .
```

## Layout
- `config/` constants, paths, settings, logging (with secret redaction)
- `core/` exceptions, typed models, interfaces, JSON-Schema validation, DI container
- `document/` template registry (declarative templates in `resources/templates/`)
- `services/` `TaskService` (worker threads -> queue -> Tk `after` polling)
- `repositories/` JSON settings (atomic write), keyring `SecretStore`
- `ui/` sidebar shell; only implemented views are shown

## Not yet implemented
Providers (Ollama/Gemini), OCR engines, exporters, structured editor, dependency checks, packaging.
