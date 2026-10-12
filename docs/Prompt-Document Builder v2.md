
# Master Development Prompt — Document Builder AI (v2)

## 1. Role and Mission

Act as a Senior Python Software Architect, Desktop Application Engineer,
AI Integration Specialist, and UI/UX Designer.

Design and develop **Document Builder AI**, a professional Windows desktop
application that uses artificial intelligence and OCR to create, transform,
review, and export Word, Excel, and PDF documents.

The application must be suitable for non-technical users while following
modern software engineering practices. It must be modular, maintainable,
testable, secure, and extensible.

Do not build merely a UI prototype. Implement functional features with real
file generation, real AI integrations, robust error handling, and automated
tests.

If an existing project repository is available, inspect its structure and
current implementation before making changes. Preserve working features
unless there is a clear technical reason to modify them.

## 2. Technology Stack

Use the following technologies and select compatible, maintained libraries
where necessary:

- Python 3.11 or 3.12 (avoid versions not yet supported by all listed libraries).
- Tkinter and ttk for the desktop GUI.
- CustomTkinter as an OPTIONAL enhancement layer for a modern look. The
  application must remain functional with plain Tkinter/ttk if CustomTkinter
  is unavailable.
- `python-docx` for Word document generation.
- `openpyxl` for Excel workbook creation and formatting.
- `xlsxwriter` as an optional secondary Excel writer ONLY when openpyxl
  cannot express a required feature (e.g., some advanced chart styles).
- ReportLab as the DEFAULT PDF generator, combined with:
    - `arabic-reshaper` and `python-bidi` for correct Arabic shaping and
      bidirectional layout.
    - An embedded Arabic font (e.g., Amiri, Cairo, or Noto Naskh Arabic)
      shipped in `resources/fonts/`.
- WeasyPrint as an OPTIONAL alternative PDF backend, selectable in settings,
  for users who need better RTL mixed-text layout via HTML/CSS. Document
  clearly that WeasyPrint on Windows requires GTK3.
- Pillow for image loading and preprocessing.
- Tesseract OCR and EasyOCR as selectable OCR engines.
- Ollama for local language-model and vision-model integration.
- Google Gemini API for cloud-based AI and vision capabilities.
- `keyring` for secure API-key storage using the operating-system credential
  store (Windows Credential Locker, macOS Keychain, Linux Secret Service).
- `pandas` as an OPTIONAL dependency used only for aggregation and summary
  table generation (see §7.4 on Pivot Tables).
- `matplotlib` for generating chart images to embed in Word and PDF.
- SQLite (via the standard `sqlite3` module) for local application history.
- PyInstaller for Windows executable packaging.
- pytest and pytest-mock for automated testing.

Verify package compatibility before implementation. Avoid unnecessary
dependencies. Pin versions in `requirements.txt`.

The application interface must be in **English only**, but it must support
creating documents containing Arabic and English content, including
right-to-left text and mixed LTR/RTL paragraphs.

## 3. Core Functional Requirements

### 3.1 Document Creation

Allow users to describe the document they need using natural language.

Example requests:
- Create a professional business report.
- Prepare a production report containing tables and conclusions.
- Generate a structured Excel worksheet for production monitoring.
- Convert a handwritten meeting note into an editable Word document.
- Extract a scanned document and export its contents as PDF.

Users must select the required output type:

1. Word (`.docx`)
2. Excel (`.xlsx`)
3. PDF (`.pdf`)

Additionally, users must be able to pick a **document template** (§3.4)
that determines default structure, styling, fonts, colors, and layout.

The application must generate valid files that can be opened by the
corresponding applications.

### 3.2 Supported Input Sources

Support the following input types where relevant to the selected task:

- User-entered text and instructions.
- Images and photographs.
- Handwritten notes and paper documents.
- Scanned and text-based PDF files.
- Word documents.
- Excel workbooks.

Provide appropriate validation and clear error messages for unsupported,
damaged, or encrypted files.

Imported files must not be silently overwritten. The user must explicitly
select the output location and filename, with an option to choose a
different filename when a file already exists.

### 3.3 Document Review Workflow

Implement the following default workflow:

1. Select a task, template, or create a new document.
2. Enter instructions or import source files.
3. Select the AI provider, model, and image-processing method.
4. Configure relevant processing options.
5. Run the operation with progress reporting.
6. Review and edit the extracted or generated content in a structured
   editor (see §3.5).
7. Select the output format and export location.
8. Generate the document and verify that the file was saved successfully.

For OCR tasks, provide a review stage before final export so users can
correct recognition errors.

### 3.4 Document Templates

The application must ship with a small set of built-in templates that
pre-configure structure, styling, and defaults. Templates are not just
visual themes; they also influence the JSON schema requested from the AI.

Built-in templates (initial set):

- **Business Report** — title page, TOC, executive summary, sections,
  tables, charts, conclusions.
- **Internal Memo** — header block (To/From/Date/Subject), body, action
  items.
- **Invoice** — header with logo placeholder, line items table, totals,
  payment terms.
- **Contract / Agreement** — parties, clauses, signature block.
- **Production Report** — KPIs, tables, charts, observations.
- **Meeting Minutes** — attendees, agenda, decisions, action items.
- **Blank Structured** — free-form structured content.

Each template must define:
- A JSON schema variant for AI output (§3.5).
- Default Word styles (fonts, headings, margins).
- Default Excel layout (sheet names, column widths, freeze panes).
- Default PDF layout (margins, fonts, header/footer).

Templates must be stored as declarative files (JSON or YAML) under
`resources/templates/`, loaded by a `TemplateRegistry`, and must NOT
require code changes to add a new template.

Users must be able to:
- Choose a built-in template.
- Start from "Blank Structured".
- Save the current document structure as a user template (optional, may
  be deferred to a later stage).

### 3.5 Structured Content Schema (Critical)

The application must NOT rely on free-form AI text as the source of truth
for document generation. Instead, the AI must be instructed to return a
**structured JSON document** conforming to a schema defined by the
selected template.

Minimum required schema (illustrative, not exhaustive):

```json
{
  "document_type": "business_report",
  "language": "ar",
  "title": "…",
  "subtitle": "…",
  "author": "…",
  "date": "2026-10-12",
  "sections": [
    {
      "heading": "…",
      "level": 1,
      "paragraphs": ["…"],
      "lists": [
        { "type": "bullet", "items": ["…", "…"] },
        { "type": "numbered", "items": ["…"] }
      ],
      "tables": [
        {
          "caption": "…",
          "headers": ["…", "…"],
          "rows": [["…", "…"]],
          "column_formats": ["text", "number", "date"],
          "totals_row": true
        }
      ],
      "charts": [
        {
          "type": "bar",
          "title": "…",
          "x_axis": "…",
          "y_axis": "…",
          "series": [
            { "name": "…", "values": [1, 2, 3] }
          ],
          "data_source_table": 0
        }
      ],
      "images": [
        { "placeholder": "logo", "caption": "…" }
      ]
    }
  ],
  "metadata": {
    "generated_by": "Document Builder AI",
    "template": "business_report",
    "ai_provider": "ollama",
    "ai_model": "…"
  }
}
```

Requirements:
- The AI prompt sent to Ollama/Gemini must request JSON only, with a
  schema summary appended.
- The response must be parsed with a tolerant JSON parser that:
  - Strips markdown code fences if present.
  - Validates against the expected schema.
  - Raises a recoverable error with a clear message if validation fails.
- A **fallback path** must exist: if the AI returns free-form text, the
  application must attempt a best-effort conversion to the schema and
  flag the result for user review.
- The user review step (§3.3, step 6) must present the content in a
  structured editor showing sections, tables, and lists, NOT a raw
  JSON text box.

### 3.6 Images and Media in Documents

- Word: embed images via `python-docx` `add_picture()` with captions.
- PDF: embed images via ReportLab `Image()` or WeasyPrint HTML `<img>`.
- Excel: embed images via `openpyxl.drawing.image.Image`.
- Charts generated with `matplotlib` must be saved as PNG in a temporary
  directory and embedded; they must not be treated as editable charts in
  Word/PDF.
- Excel charts must be native `openpyxl.chart` objects where possible.
- Large images must be downscaled before embedding to keep file sizes
  reasonable. Default: max 1600 px on the long edge unless the user
  overrides.
- Images embedded in documents must preserve aspect ratio.

## 4. AI Provider Architecture

Support two primary AI providers:

- Ollama — local AI processing.
- Google Gemini — cloud-based AI processing.

The provider selection and model selection must be independent and
configurable through the application interface.

Create a common provider interface or abstract base class. Each provider
must implement the operations it actually supports, including text
generation, vision analysis, model discovery, connectivity checks, and
applicable error handling.

Use appropriate design patterns, such as Strategy, Factory, and Adapter,
where they improve maintainability.

Do not implement every provider directly inside the GUI.

### 4.1 Dynamic Model Discovery

The application must not depend on a hardcoded, permanently fixed model list.

For Ollama:
- Detect whether Ollama is installed or accessible via the CLI or the
  HTTP API on the default port (11434).
- Check whether its local service is running.
- Discover locally installed models via `ollama.list()` or the
  `/api/tags` endpoint.
- Refresh the model list on demand.
- Identify whether a discovered model supports the selected task when
  this information is available in its metadata.
- Verify actual capabilities when model metadata is insufficient, e.g.,
  by attempting a small vision request against models whose name suggests
  vision capability (`llava`, `bakllava`, `llama3.2-vision`, `moondream`,
  `qwen2-vl`, etc.).
- Distinguish text-generation models from vision-capable models where
  possible.

For Gemini:
- Support secure API-key configuration via `keyring`.
- Retrieve available models via the Google Gen AI SDK
  (`google-genai`) using the supported `models.list` operation.
- Check whether the configured model supports the required operation
  (e.g., `generateContent` with image input).
- Handle permission, quota, authentication, and connectivity errors
  distinctly and with actionable messages.
- Refresh the available-model list when requested.

Never assume that every installed model supports image input, or that
every available cloud model supports every operation.

If model discovery fails, preserve the application interface and explain
the problem rather than crashing.

### 4.2 Provider Settings

Provide an AI Settings screen containing:

- Active provider.
- Available models for that provider.
- Model refresh action.
- Connection or service status.
- API-key configuration for Gemini (stored via `keyring`).
- Default model preferences.
- Timeout and applicable generation settings.
- Clear descriptions of local and cloud processing.

Do not log API keys or other secrets. Do not hardcode API keys in source
files or package them into the executable.

### 4.3 External Dependency Detection

A dedicated module (`services/dependency_service.py`) must detect and
report the availability of external dependencies:

- **Ollama**: check executable on PATH, check service on
  `http://localhost:11434`, retrieve version.
- **Tesseract**: check executable on PATH, check common Windows install
  paths (`C:\Program Files\Tesseract-OCR\tesseract.exe`, per-user
  installs), allow manual path override in Application Settings,
  retrieve version and available languages via `tesseract --list-langs`.
- **Ghostscript** (if required by any PDF-to-image path used for OCR).
- **GTK3** (only if WeasyPrint backend is selected).

Each dependency must have:
- A clear status indicator (Available / Not Found / Misconfigured).
- A specific user-facing message explaining what to install and where
  to obtain it (official URL).
- A "Re-check" action.
- A manual path override where applicable.

The application must remain fully usable for tasks that do not require
a missing dependency.

## 5. Image Processing and OCR

This is a major feature. Users must be able to select their preferred
processing method from the interface.

Support the following methods:

### Method A — Gemini Vision
Send supported images to a compatible Gemini vision model for image
understanding, handwriting recognition, text extraction, and document
interpretation. Inform the user that image content is sent to a cloud
provider.

### Method B — Ollama Vision
Use a locally installed vision-capable Ollama model when the local
service and model are available.

### Method C — Tesseract OCR
Extract text from supported images and scanned documents using Tesseract.
Provide configurable preprocessing options and language availability
checks via `tesseract --list-langs`.

### Method D — EasyOCR
Use EasyOCR for supported languages and image sources. Make its language
configuration explicit and report missing dependencies, missing model
weights, and required first-time downloads clearly. Warn the user that
EasyOCR may require an internet connection the first time a language
model is used.

### Method E — Traditional OCR Followed by AI Formatting
Use the following pipeline:

1. Image preprocessing.
2. Text extraction with Tesseract or EasyOCR.
3. AI-based correction and formatting when requested.
4. User review and manual correction.
5. Export to the selected document format.

### 5.1 OCR User Controls

Allow users to select:

- Processing method.
- AI provider for AI-assisted processing.
- Compatible model.
- OCR language settings, including English and Arabic where supported.
- Image preprocessing options.
- Whether to preserve the original wording or correct obvious OCR
  recognition errors.
- Whether to preserve detected tables, paragraphs, headings, and lists
  where practical.
- Whether to include a confidence indicator when the selected engine
  exposes meaningful confidence information.

Clearly distinguish the original extracted text from any AI-corrected
version.

Do not silently invent missing words or facts. If handwriting or an
image is ambiguous, flag the uncertain portions and allow the user to
review them.

### 5.2 Image Preprocessing

Where relevant, support:

- Image rotation and orientation correction.
- Grayscale conversion.
- Contrast enhancement.
- Noise reduction.
- Thresholding.
- Resizing and resolution checks.
- Multi-image processing.
- PDF page rendering for OCR via `pdf2image` (documented as requiring
  Poppler on Windows).

Apply preprocessing according to the selected method, with sensible
defaults. Avoid destructive modification of the original source files.

Provide a preview of the source image and extracted text where practical.

### 5.3 OCR Error Handling

Define specific exception types and user-facing messages for:

- `OcrEngineNotFoundError` — Tesseract or EasyOCR binary not found.
- `OcrLanguageNotSupportedError` — requested language not installed.
- `OcrLowConfidenceError` — result confidence below threshold.
- `OcrModelDownloadRequiredError` — EasyOCR needs to download weights.
- `PdfRenderError` — PDF could not be rendered to images.
- `UnsupportedImageFormatError` — image format not handled.

Each error must offer the user an actionable next step: install a
dependency, choose a different language, try another engine, or lower
the confidence threshold.

### 5.4 Processing Pipeline Design

Implement image conversion and OCR as a modular pipeline.

Separate the components for file loading, image preprocessing, OCR
execution, optional AI post-processing, and document export.

Adding another OCR engine or image-processing method in the future must
not require major changes to the existing GUI or unrelated modules.

## 6. Ollama Detection and Setup Guidance

**Required behavior: detect Ollama and its installed models; provide
installation guidance when needed.**

Do not bundle Ollama or large AI models inside the application's EXE.

When the user selects Ollama:

1. Check whether the Ollama executable or service is available.
2. Check whether the local service responds.
3. Retrieve the installed-model list.
4. Check whether the selected model is available and appropriate for the
   requested operation.
5. Display actionable guidance when Ollama is missing, stopped, or has
   no suitable installed model.
6. Provide a refresh or retry option after the user completes the setup.
7. Explain when a compatible vision model is required for image
   understanding.

Do not automatically download large models without explicit user action.

Provide safe links to official installation documentation and explain
that model downloads require sufficient disk space and may require an
internet connection.

The application must remain usable for Gemini-based tasks even when
Ollama is unavailable.

## 7. Document Export Architecture

Create a common export interface and separate implementations for Word,
Excel, and PDF. All exporters consume the structured schema from §3.5
and the active template from §3.4.

```python
class BaseExporter(ABC):
    @abstractmethod
    def export(self, document: DocumentModel, output_path: Path) -> ExportResult:
        ...

    @abstractmethod
    def supports(self, feature: str) -> bool:
        ...
```

Exporters must declare which schema features they support so the UI can
warn the user when a feature is unavailable in the selected format.

### 7.1 Word Exporter

Support:

- Headings and subheadings with automatic numbering when the template
  requests it.
- Paragraphs and lists (bullet and numbered).
- Tables with headers, borders, and optional totals row.
- Page margins and page breaks.
- Headers and footers with page numbering.
- Consistent typography and spacing driven by template styles.
- Embedded images with captions.
- Embedded chart images.
- Table of contents placeholder (marked as "update field in Word").
- Arabic text and right-to-left layout:
    - Set `paragraph_format.bidi = True` for Arabic paragraphs.
    - Set `alignment = RIGHT` when appropriate.
    - Set `run.font.rtl = True`.
    - Handle mixed LTR/RTL at paragraph level, not run level.
- Style presets driven by templates, using named styles in the document
  so users can adjust globally in Word.

### 7.2 Excel Exporter

Support:

- Multiple worksheets with meaningful names.
- Structured Excel tables (`openpyxl.worksheet.table.Table`) with
  display names and styles.
- Column widths and row heights.
- Number, date, and percentage formatting.
- Formulas where appropriate.
- AutoFilter and freeze panes.
- Conditional formatting (color scales, data bars, cell rules).
- Charts (native `openpyxl.chart` objects) driven by the schema's
  `charts` array.
- RTL sheet view when the document language is Arabic.
- Data validation where applicable.
- Sheet protection and cell locking when the template requests it.

Do not place the entire AI-generated result into a single cell when the
content is more appropriately represented by multiple rows, columns, or
worksheets. The schema from §3.5 enforces this.

**Formula injection prevention (mandatory):**
Any string value from AI output or imported content that begins with
`=`, `+`, `-`, `@`, or a tab character must be written as text by
prefixing it with a single quote or by setting the cell's data type to
`string`. This must be enforced in a shared helper, not repeated inline.

### 7.3 PDF Exporter

Two backends, selectable in Application Settings:

**Backend A — ReportLab (default):**
- Readable page layouts.
- Paragraphs, headings, and tables.
- Page breaks and margins.
- Arabic font embedding and RTL support via `arabic-reshaper` and
  `python-bidi`. Apply reshaping to the full paragraph string, then
  apply bidi, then pass to ReportLab.
- Searchable text-based PDF generation.
- Embedded images and chart images.

**Backend B — WeasyPrint (optional):**
- Convert the document model to HTML/CSS.
- Use `direction: rtl` and `unicode-bidi: isolate` for mixed content.
- Document clearly that GTK3 is required on Windows.

Do not assume that basic font selection alone guarantees correct Arabic
shaping or bidirectional text. Document known limitations for each
backend in the README.

### 7.4 Pivot Tables and Data Analysis

`openpyxl` cannot create new Pivot Tables. The application must provide
the following alternatives, clearly labeled:

**Default — Summary Tables:**
Generate aggregated tables using `pandas.pivot_table` or `groupby` and
write them as plain structured tables. Support sums, counts, averages,
min/max, and multi-level grouping.

**Advanced — Template-Based Pivot Tables:**
Ship optional Excel templates that contain pre-built Pivot Tables
referencing a named range or a `Source` sheet. The application writes
raw data into `Source`, and the Pivot Table refreshes when the user
opens the file in Excel. Document that a manual refresh may be required.

**Optional — Excel COM (Windows only):**
If Excel is installed and the user explicitly enables it, use `pywin32`
to create real Pivot Tables. This path must be:
- Off by default.
- Clearly labeled as requiring Microsoft Excel.
- Guarded by a try/except that falls back to Summary Tables.

The UI must not present "Pivot Table" as a guaranteed feature. It must
present "Summary Table" as the default, and "Pivot Table" as an
advanced option with clear caveats.

### 7.5 Charts and Visualizations

Charts requested in the schema must be handled per exporter:

- **Excel**: native `openpyxl.chart` objects (bar, column, line, pie,
  area, scatter, combined). Prefer native charts so users can edit them.
- **Word**: generate the chart with `matplotlib`, save as PNG, embed as
  image. Charts are not editable in Word.
- **PDF (ReportLab)**: generate with `matplotlib`, save as PNG, embed.
- **PDF (WeasyPrint)**: generate with `matplotlib` as PNG and embed in
  HTML, OR render simple charts with inline SVG when practical.

Chart data must come from a real data source in the schema (a table or
an explicit `series` array). Never invent data points.

Default chart styling must follow the active template's color palette
when available.

### 7.6 Export Validation

After creating a document:

- Verify that the output file exists.
- Verify that it is non-empty.
- Re-open the file with the appropriate library to confirm it is valid
  (`Document()` for docx, `load_workbook()` for xlsx, `PdfReader` for
  pdf).
- Catch and report export failures with specific error types.
- Avoid reporting success before the operation has actually completed.
- Write to a temporary file in the same directory, then use
  `os.replace()` for atomic replacement.
- If the target file exists, prompt the user to confirm overwrite or
  choose a new name.
- Provide an action to open the output folder.
- Log the export duration and file size in diagnostics.

## 8. Software Architecture — Mandatory Requirements

Use an object-oriented, modular design following SOLID principles and
sound software engineering practices.

The goal is long-term maintainability, easier debugging, and future
feature development.

### 8.1 Centralized Constants and Configuration

Place shared constants in a centralized module, such as
`config/constants.py`.

Examples include:
- Application name and version references.
- Supported file extensions.
- Default output formats.
- Configuration keys.
- Application directory names.
- Supported provider identifiers.
- Supported OCR method identifiers.
- Supported template identifiers.
- Timeout defaults.
- Shared UI dimensions or other genuinely global constants.

Use a separate settings module for runtime configuration and `keyring`
for API credentials.

Do not duplicate constants throughout the codebase.

Avoid turning the constants file into a repository for mutable
application state. Keep constants, user settings, and runtime state
separate.

Use environment-aware paths suitable for development and a
PyInstaller-built executable.

### 8.2 OOP and SOLID

Implement:

- Classes with clear, limited responsibilities.
- Abstract interfaces for providers, OCR engines, exporters, and
  templates.
- Dependency injection or an equivalent explicit dependency-management
  approach.
- Composition instead of unnecessary inheritance.
- Type hints for public APIs and important data structures.
- Dataclasses or validated models (e.g., Pydantic) for structured
  configuration, DocumentModel, and operation results.
- Custom exception classes for meaningful failure categories.
- Clear separation between presentation, business logic,
  infrastructure, and persistence.

Avoid monolithic classes, global mutable state, circular imports,
repeated business logic, and excessive coupling between modules.

### 8.3 Background Tasks (Mandatory Pattern)

All long-running operations (AI calls, OCR, file conversion, export)
must run in worker threads.

The application must use a Producer-Consumer pattern:

- Worker threads push progress and result events into a `queue.Queue`.
- The Tk main thread consumes events via `root.after(interval, ...)`.
- Tk widgets must NEVER be updated directly from a worker thread.

A shared `TaskService` must provide:
- Task submission with an ID.
- Progress reporting (0–100 or step-based).
- Cancellation support where safe.
- Result and error delivery through the queue.
- Cleanup and thread-join on application shutdown.

### 8.4 Error Handling and Logging

Implement consistent exception handling across the application.

Use structured logging with appropriate levels and useful diagnostic
context.

Requirements:
- Provide understandable user-facing messages.
- Record technical details in diagnostic logs.
- Never log API keys or sensitive credentials.
- Avoid swallowing exceptions silently.
- Identify recoverable errors and provide retry or fallback options.
- Ensure failed background operations return the application to a
  usable state.

### 8.5 Testability

Business logic must be testable independently of Tkinter.

Use dependency injection and mocks so tests do not require live Gemini
requests, a running Ollama service, or large OCR models.

Create tests for:
- Provider discovery and connection failures.
- Dynamic model-list refresh.
- OCR engine selection and error conditions.
- Preprocessing pipeline behavior.
- Document schema validation (valid, invalid, partial).
- Formula-injection prevention in the Excel exporter.
- Document generation for all three formats.
- Export validation and atomic replacement.
- Settings validation and persistence.
- File naming and output-path handling.
- Background task errors and cancellation.
- Template loading and registry behavior.

GUI tests are explicitly out of scope for full coverage. Test the
ViewModels or Controller-level logic instead. If GUI tests are added,
they must use a headless approach and must not be required for CI.

## 9. Recommended Project Structure

```text
document_builder/
├── app.py
├── requirements.txt
├── pyproject.toml
├── README.md
├── config/
│   ├── constants.py
│   ├── settings.py
│   └── logging_config.py
├── core/
│   ├── interfaces.py
│   ├── exceptions.py
│   ├── models.py                 # DocumentModel, Section, Table, Chart, etc.
│   ├── schema_validator.py       # Validates AI JSON against template schema
│   └── dependency_container.py
├── ui/
│   ├── main_window.py
│   ├── navigation.py
│   ├── views/
│   │   ├── home_view.py
│   │   ├── create_document_view.py
│   │   ├── ocr_view.py
│   │   ├── ai_settings_view.py
│   │   ├── app_settings_view.py
│   │   └── history_view.py
│   ├── dialogs/
│   ├── components/
│   │   ├── structured_editor.py
│   │   ├── progress_panel.py
│   │   └── template_picker.py
│   └── theme.py                  # ttk / CustomTkinter theme definitions
├── ai/
│   ├── base_provider.py
│   ├── ollama_provider.py
│   ├── gemini_provider.py
│   ├── prompts.py                # Schema-aware prompt templates
│   ├── model_registry.py
│   └── model_discovery.py
├── image_processing/
│   ├── base_ocr.py
│   ├── gemini_vision.py
│   ├── ollama_vision.py
│   ├── tesseract_ocr.py
│   ├── easyocr_engine.py
│   ├── image_preprocessor.py
│   └── processing_pipeline.py
├── document/
│   ├── base_exporter.py
│   ├── template_registry.py
│   ├── word_exporter.py
│   ├── excel_exporter.py
│   ├── pdf_exporter_reportlab.py
│   ├── pdf_exporter_weasyprint.py
│   ├── chart_renderer.py         # matplotlib-based chart image generation
│   └── formula_safety.py         # Shared formula-injection prevention
├── services/
│   ├── document_service.py
│   ├── ocr_service.py
│   ├── ai_service.py
│   ├── task_service.py
│   └── dependency_service.py
├── repositories/
│   ├── settings_repository.py
│   └── history_repository.py
├── resources/
│   ├── fonts/
│   │   ├── Amiri-Regular.ttf
│   │   └── NotoNaskhArabic-Regular.ttf
│   ├── icons/
│   └── templates/
│       ├── business_report.json
│       ├── internal_memo.json
│       ├── invoice.json
│       ├── contract.json
│       ├── production_report.json
│       └── meeting_minutes.json
├── tests/
├── scripts/
│   └── build_windows.py
└── build/
```

Keep build output and runtime-generated data separate from source code.
Include only files that serve a real purpose.

## 10. User Interface and UX

Build a modern, professional desktop interface using Tkinter and ttk,
optionally enhanced with CustomTkinter.

The interface must be English-only and easy for a user with limited
technical experience.

Preferred layout:
- Left navigation sidebar.
- Main workspace.
- Clear page titles and concise instructions.
- Consistent spacing and typography.
- Subtle borders and restrained color use.
- Clear primary and secondary actions.
- Useful empty states.
- Contextual tooltips where they genuinely help.
- Dialogs for errors, confirmations, and configuration.

Provide the following screens or equivalent clearly organized views:

1. **Home** — create a document, import files, or reopen a recent task.
   Includes a template gallery.
2. **Create Document** — enter instructions, pick template, select
   output type, and configure the AI task.
3. **Image & OCR** — import images or PDFs, select a processing method,
   configure OCR, and review extracted content.
4. **Structured Review** — edit generated sections, tables, lists, and
   charts in a structured editor before export.
5. **AI Settings** — select provider and model, refresh available
   models, check connection status.
6. **Application Settings** — configure OCR language preferences,
   output defaults, paths, PDF backend, and dependency paths.
7. **Dependencies** — view status of Ollama, Tesseract, EasyOCR,
   Poppler, GTK3, and provide manual path overrides.
8. **History** — display prior operations and allow users to reopen
   available files or rerun a task.

Use the Producer-Consumer background-task pattern from §8.3. Do not
update Tkinter widgets directly from worker threads.

Show progress indicators and meaningful status messages during lengthy
operations. Allow cancellation where it can be implemented safely.

## 11. Settings and Local Data

Store non-sensitive settings in a suitable local configuration file
(e.g., JSON in `%APPDATA%\DocumentBuilderAI\settings.json`) and persist
them where appropriate.

Store API keys exclusively via `keyring`. Provide a fallback
mechanism only if `keyring` is unavailable, and document it clearly as
less secure.

If application history is implemented, use SQLite with a repository
layer rather than embedding database queries throughout the interface.

Keep application settings, operation history, temporary files,
generated documents, and logs in suitable user-specific directories:

- `%APPDATA%\DocumentBuilderAI\settings.json`
- `%APPDATA%\DocumentBuilderAI\history.db`
- `%LOCALAPPDATA%\DocumentBuilderAI\logs\`
- `%LOCALAPPDATA%\DocumentBuilderAI\temp\`
- User-selected output directory for generated documents.

Use Windows-compatible paths and handle missing directories, permission
errors, and unavailable disk space.

Provide safe defaults and validate configuration on startup.

## 12. Performance, Reliability, and Security

- Do not freeze the main GUI during AI calls, OCR, file conversion, or
  document export.
- Apply reasonable timeouts to external operations.
- Report network failures, quota limitations, missing dependencies, and
  unavailable models clearly.
- Avoid unnecessary memory copies of large images and PDF pages.
- Validate imported file types and handle malformed files defensively.
- Clean up temporary files when safe.
- Do not execute generated Python, shell commands, or arbitrary code
  from AI output.
- Do not treat content imported from user files as trusted instructions.
- Prevent formula injection in Excel exports (see §7.2).
- Clearly inform users when a workflow sends document content to a cloud
  provider.
- Keep local processing local when the user explicitly chooses a
  local-only operation.
- Do not claim perfect OCR accuracy or perfect preservation of complex
  document formatting.
- Never log API keys, file contents, or extracted personal data at INFO
  level; use DEBUG only when the user explicitly enables verbose
  logging.

## 13. Windows EXE Packaging

Prepare the project for Windows distribution using PyInstaller.

Requirements:
- A documented build command or build script
  (`scripts/build_windows.py`).
- A suitable `.spec` file.
- Correct handling of packaged resources and writable user-data
  directories.
- Clear dependency installation instructions.
- Appropriate handling or documentation of OCR executables and external
  model files.
- Startup and error diagnostics that remain useful in packaged mode.
- A clean distinction between files bundled into the executable and
  external prerequisites.
- Inclusion of Arabic fonts in `resources/fonts/` via the `.spec` file's
  `datas` section.
- Proper handling of `matplotlib` and `pandas` in the spec (both can
  require hidden imports).

Do not attempt to package the entire Ollama installation or large local
AI models into the EXE.

The README must explain:
- Ollama requires separate installation and compatible models must be
  present locally.
- How to configure Gemini and where to obtain a valid API key from its
  official service.
- Tesseract must be installed separately, with a link to the official
  Windows installer.
- EasyOCR may require an internet connection the first time a language
  model is downloaded.
- Poppler is required for PDF-to-image OCR.
- GTK3 is required only if the WeasyPrint PDF backend is enabled.

## 14. Development Workflow

Work in controlled stages. Each stage must produce working, testable
results.

### Stage 1 — Repository Inspection and Architecture
- Inspect existing files and requirements.
- Identify important unknowns.
- Present the proposed architecture and key technical decisions.
- Ask a concise set of clarifying questions only if genuinely blocking
  decisions remain.
- Otherwise state sensible assumptions and proceed.

### Stage 2 — Application Foundation
- Establish the package structure.
- Implement centralized constants, configuration, logging, exceptions,
  and core interfaces.
- Implement the `DocumentModel` schema and validator.
- Create the main GUI shell and navigation.
- Implement the Producer-Consumer `TaskService`.
- Verify application startup and settings persistence.

### Stage 3 — AI Providers
- Implement Ollama connectivity checks and installed-model discovery.
- Implement Gemini configuration and model discovery.
- Add model compatibility handling, connection diagnostics, and test
  doubles.
- Implement the schema-aware prompt templates.

### Stage 4 — Image Processing and OCR
- Implement preprocessing and OCR interfaces.
- Integrate each selected OCR engine.
- Build the selectable processing pipeline.
- Implement OCR-specific exceptions and error surfaces.
- Add text review and error handling.
- Test unavailable models and OCR dependencies.

### Stage 5 — Document Export
- Implement the template registry and built-in templates.
- Implement Word, Excel, and PDF exporters.
- Implement the chart renderer and formula-safety helper.
- Support Arabic and English output.
- Verify generated files with file-format-aware tests.
- Add export validation and overwrite protection.

### Stage 6 — Workflow Integration
- Connect the UI, providers, OCR pipeline, document services, and
  history.
- Implement the structured review editor.
- Implement progress reporting and cancellation.
- Test complete workflows from user input to exported file.

### Stage 7 — Hardening and Packaging
- Run unit and integration tests.
- Fix errors and regressions.
- Test missing Ollama, missing models, invalid API keys, network
  failures, missing Tesseract, missing Poppler, and export errors.
- Build the Windows executable.
- Test the packaged application, not just the development version.
- Complete setup and troubleshooting documentation.

Do not proceed by creating many untested modules in a single step. Keep
the project runnable at each meaningful milestone.

## 15. Definition of Done

The application is not complete until all applicable acceptance
criteria are met:

1. The application launches without an unhandled exception.
2. The English UI is clear, organized, and usable by a non-technical
   user.
3. Users can choose Word, Excel, or PDF as the output format.
4. Users can choose a document template from a built-in gallery.
5. Users can select an AI provider and a compatible available model.
6. Ollama is detected when available, and missing installations or
   models produce actionable guidance.
7. Gemini can be configured without exposing credentials in source code
   or logs.
8. Users can choose among the supported image-processing and OCR methods.
9. Handwriting and scanned documents can be processed, reviewed, and
   exported, subject to the capabilities of the chosen engine.
10. Long-running work does not freeze the interface.
11. Word, Excel, and PDF output files are valid and contain the expected
    content, verified by re-opening each file with its library.
12. Arabic and English content is handled appropriately for the selected
    exporter, including mixed LTR/RTL paragraphs.
13. Excel exports support structured tables, formulas, conditional
    formatting, and native charts.
14. Excel exports are protected against formula injection.
15. Word and PDF exports include embedded chart images when requested.
16. Summary Tables are generated for data-aggregation requests; Pivot
    Tables are offered only as an advanced, clearly documented option.
17. Errors are logged and presented clearly, without silent failures.
18. Automated tests cover important business logic and failure paths.
19. The project is documented and can be built into a Windows EXE using
    the supplied instructions.
20. Adding a new AI provider, OCR engine, export format, or document
    template can be achieved primarily by implementing the relevant
    interface or dropping a declarative file, not by rewriting the
    application.

## 16. Final Deliverables

Provide:

- Complete source code with meaningful file and class names.
- A clear, maintainable package structure.
- Dependency and environment setup instructions.
- A README covering installation, settings, supported workflows, known
  limitations, and troubleshooting.
- Automated tests and instructions for running them.
- PyInstaller configuration or a reproducible build script.
- A description of the architecture and the extension points for future
  development.
- A final verification report that distinguishes implemented and tested
  features from incomplete features or unverified behavior.

Never claim that a feature works unless it has been implemented and
appropriately tested.

Do not replace real functionality with placeholders or simulated
responses. If a dependency, API, model, or environment is unavailable,
implement the appropriate integration boundary, report the limitation,
and explain precisely how it can be verified.

**Primary objective:** deliver a dependable, professionally designed
Document Builder AI application with a clean user experience, strict
separation of concerns, dynamic provider and model selection, selectable
OCR pipelines, a structured content schema, reusable document templates,
and a codebase that can be maintained and extended for years.
```

---

## التغييرات الرئيسية التي أجريتها

| المجال | ما كان في الأصل | ما أصبح الآن |
|---|---|---|
| **الواجهة الرسومية** | Tkinter فقط | Tkinter + CustomTkinter اختياري |
| **PDF** | ReportLab فقط | ReportLab افتراضي + WeasyPrint اختياري، مع `arabic-reshaper` و`python-bidi` وخط عربي مدمج |
| **التبعيات الخارجية** | مذكورة عابرة | قسم كامل §4.3 لاكتشاف Ollama وTesseract وPoppler وGTK3 مع مسارات يدوية |
| **المهام الخلفية** | عامة | نمط Producer-Consumer إلزامي مع `queue.Queue` و`root.after()` |
| **مفاتيح API** | "مخزن آمن" | `keyring` صراحةً |
| **بنية المحتوى** | نص AI حر | JSON Schema إلزامي مع Validator وFallback |
| **القوالب** | غير مذكورة | قسم كامل §3.4 مع 7 قوالب مدمجة |
| **المخططات** | "عند الطلب" | §7.5 تفصيلي: أصلية في Excel، صور matplotlib في Word/PDF |
| **الجداول المحورية** | غير مذكورة | §7.4 مع ثلاث استراتيجيات بديلة |
| **الصور** | غير مذكورة | §3.6 مع ضغط تلقائي وتسميات |
| **حقن الصيغ** | إشارة عابرة | §7.2 مع helper مشترك |
| **النصوص المختلطة** | "دعم العربية" | §7.1 + §7.3 مع Bidi على مستوى الفقرة |
| **اختبار الواجهة** | وعد غير واقعي | §8.5: اختبار ViewModels بدلاً من Tkinter |
| **التحقق من التصدير** | عام | §7.6 مع إعادة فتح الملف بـ `os.replace()` الذري |
| **معايير القبول** | 15 معيار | 20 معيارًا مع تغطية للميزات الجديدة |

---

## أسئلة توضيحية قبل التنفيذ

قبل أن تعتمد هذه النسخة، أحتاج إجاباتك على النقاط التالية — لأنها قرارات تصميمية لا يمكنني حسمها نيابة عنك:

### 1. نطاق المنصات
هل التطبيق **Windows فقط** (كما يوحي العنوان)، أم يجب أن يعمل على Linux/macOS أيضًا؟ هذا يؤثر على:
- اختيار `keyring` backend
- مسارات الملفات (`%APPDATA%` vs `~/.config`)
- تعقيد PyInstaller
- دعم Ollama

### 2. WeasyPrint كخيار PDF
هل أنت مستعد لتحمّل تعقيد توزيع GTK3 على Windows مقابل دعم RTL أفضل؟ أم تفضّل الاكتفاء بـ ReportLab مع `arabic-reshaper` + `python-bidi` وتوثيق القيود؟

### 3. الجداول المحورية
أي مسار تفضّل كافتراضي؟
- **(أ)** Summary Tables فقط (آمن، لا يحتاج Excel)
- **(ب)** Summary Tables + قوالب Excel بـ Pivot جاهز (يحتاج إعداد قوالب)
- **(ج)** Summary Tables + Win32 COM اختياري (يحتاج Excel مثبتًا)

### 4. القوالب المدمجة
هل القائمة المقترحة (تقرير أعمال، مذكرة، فاتورة، عقد، تقرير إنتاج، محضر اجتماع، فارغ منظم) مناسبة؟ هل تريد إضافة/حذف قوالب؟

### 5. محرر المراجعة المنظم
هل تريد محررًا مرئيًا كاملًا (شجرة أقسام + جداول قابلة للتحرير)، أم يكفي محرر نصي مع Markdown منظّم في المرحلة الأولى؟

### 6. النماذج المحلية مقابل السحابية
هل يجب أن يعمل التطبيق **بدون إنترنت إطلاقًا** في وضع Ollama المحلي؟ هذا يؤثر على تصميم التدفق الافتراضي والرسائل.

### 7. اللغة الافتراضية لـ OCR
هل الافتراضي هو العربية، الإنجليزية، أم كلتاهما (`ara+eng`)؟

### 8. الميزانية والحدود
هل هناك قيود على استخدام Gemini API (مثل الالتزام بالطبقة المجانية)؟ هذا قد يفرض قيودًا على أحجام الملفات أو عدد الطلبات.

### 9. حجم المشروع المستهدف
هل هذا مشروع فردي (Solo)، فريق صغير، أم مشروع مفتوح المصدر طويل الأمد؟ هذا يحدد مستوى التوثيق والاختبارات المطلوبة.

### 10. المكتبة المفضلة لـ Gemini
هل تفضّل `google-generativeai` (المكتبة القديمة) أم `google-genai` (المكتبة الجديدة الموحدة)؟ الأخيرة هي الموصى بها حاليًا لكنها أحدث.

---

بمجرد إجابتك على هذه الأسئلة، يمكنني تثبيت النسخة النهائية من الـ Prompt وإزالة الافتراضات المؤقتة.