# Master Development Prompt — Document Builder AI

## 1. Role and Mission

Act as a Senior Python Software Architect, Desktop Application Engineer, AI Integration Specialist, and UI/UX Designer.

Design and develop **Document Builder AI**, a professional Windows desktop application that uses artificial intelligence and OCR to create, transform, review, and export Word, Excel, and PDF documents.

The application must be suitable for non-technical users while following modern software engineering practices. It must be modular, maintainable, testable, secure, and extensible.

Do not build merely a UI prototype. Implement functional features with real file generation, real AI integrations, robust error handling, and automated tests.

If an existing project repository is available, inspect its structure and current implementation before making changes. Preserve working features unless there is a clear technical reason to modify them.

## 2. Technology Stack

Use the following technologies and select compatible, maintained libraries where necessary:

- Python 3.x, using a currently supported and compatible version.
- Tkinter and ttk for the desktop GUI.
- `python-docx` for Word document generation.
- `openpyxl` for Excel workbook creation and formatting.
- A suitable PDF library, such as ReportLab, for PDF generation.
- Pillow for image loading and preprocessing.
- Tesseract OCR and EasyOCR as selectable OCR engines.
- Ollama for local language-model and vision-model integration.
- Google Gemini API for cloud-based AI and vision capabilities.
- SQLite for local application history, if enabled.
- PyInstaller for Windows executable packaging.
- pytest for automated testing.

Verify package compatibility before implementation. Avoid unnecessary dependencies.

The application interface must be in **English only**, but it must support creating documents containing Arabic and English content, including right-to-left text where applicable.

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

The application must generate valid files that can be opened by the corresponding applications.

### 3.2 Supported Input Sources

Support the following input types where relevant to the selected task:

- User-entered text and instructions.
- Images and photographs.
- Handwritten notes and paper documents.
- Scanned and text-based PDF files.
- Word documents.
- Excel workbooks.

Provide appropriate validation and clear error messages for unsupported, damaged, or encrypted files.

Imported files must not be silently overwritten. The user must explicitly select the output location and filename, with an option to choose a different filename when a file already exists.

### 3.3 Document Review Workflow

Implement the following default workflow:

1. Select a task or create a new document.
2. Enter instructions or import source files.
3. Select the AI provider, model, and image-processing method.
4. Configure relevant processing options.
5. Run the operation with progress reporting.
6. Review and edit the extracted or generated content.
7. Select the output format and export location.
8. Generate the document and verify that the file was saved successfully.

For OCR tasks, provide a review stage before final export so users can correct recognition errors.

## 4. AI Provider Architecture

Support two primary AI providers:

- Ollama — local AI processing.
- Google Gemini — cloud-based AI processing.

The provider selection and model selection must be independent and configurable through the application interface.

Create a common provider interface or abstract base class. Each provider must implement the operations it actually supports, including text generation, vision analysis, model discovery, connectivity checks, and applicable error handling.

Use appropriate design patterns, such as Strategy, Factory, and Adapter, where they improve maintainability.

Do not implement every provider directly inside the GUI.

### 4.1 Dynamic Model Discovery

The application must not depend on a hardcoded, permanently fixed model list.

For Ollama:
- Detect whether Ollama is installed or accessible.
- Check whether its local service is running.
- Discover locally installed models dynamically.
- Refresh the model list on demand.
- Identify whether a discovered model supports the selected task when this information is available.
- Verify actual capabilities when model metadata is insufficient.
- Distinguish text-generation models from vision-capable models where possible.

For Gemini:
- Support secure API-key configuration.
- Retrieve available models through the supported API or SDK mechanisms.
- Check whether the configured model supports the required operation.
- Handle permission, quota, authentication, and connectivity errors.
- Refresh the available-model list when requested.

Never assume that every installed model supports image input, or that every available cloud model supports every operation.

If model discovery fails, preserve the application interface and explain the problem rather than crashing.

### 4.2 Provider Settings

Provide an AI Settings screen containing:

- Active provider.
- Available models for that provider.
- Model refresh action.
- Connection or service status.
- API-key configuration for Gemini.
- Default model preferences.
- Timeout and applicable generation settings.
- Clear descriptions of local and cloud processing.

Do not log API keys or other secrets. Do not hardcode API keys in source files or package them into the executable.

## 5. Image Processing and OCR

This is a major feature. Users must be able to select their preferred processing method from the interface.

Support the following methods:

### Method A — Gemini Vision

Send supported images to a compatible Gemini vision model for image understanding, handwriting recognition, text extraction, and document interpretation.

### Method B — Ollama Vision

Use a locally installed vision-capable Ollama model when the local service and model are available.

### Method C — Tesseract OCR

Extract text from supported images and scanned documents using Tesseract. Provide configurable preprocessing options and language availability checks.

### Method D — EasyOCR

Use EasyOCR for supported languages and image sources. Make its language configuration explicit and report missing dependencies or models clearly.

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
- Whether to preserve the original wording or correct obvious OCR recognition errors.
- Whether to preserve detected tables, paragraphs, headings, and lists where practical.
- Whether to include a confidence indicator when the selected engine exposes meaningful confidence information.

Clearly distinguish the original extracted text from any AI-corrected version.

Do not silently invent missing words or facts. If handwriting or an image is ambiguous, flag the uncertain portions and allow the user to review them.

### 5.2 Image Preprocessing

Where relevant, support:

- Image rotation and orientation correction.
- Grayscale conversion.
- Contrast enhancement.
- Noise reduction.
- Thresholding.
- Resizing and resolution checks.
- Multi-image processing.
- PDF page rendering for OCR.

Apply preprocessing according to the selected method, with sensible defaults. Avoid destructive modification of the original source files.

Provide a preview of the source image and extracted text where practical.

### 5.3 Processing Pipeline Design

Implement image conversion and OCR as a modular pipeline.

Separate the components for file loading, image preprocessing, OCR execution, optional AI post-processing, and document export.

Adding another OCR engine or image-processing method in the future must not require major changes to the existing GUI or unrelated modules.

## 6. Ollama Detection and Setup Guidance

**Required behavior: detect Ollama and its installed models; provide installation guidance when needed.**

Do not bundle Ollama or large AI models inside the application's EXE.

When the user selects Ollama:

1. Check whether the Ollama executable or service is available.
2. Check whether the local service responds.
3. Retrieve the installed-model list.
4. Check whether the selected model is available and appropriate for the requested operation.
5. Display actionable guidance when Ollama is missing, stopped, or has no suitable installed model.
6. Provide a refresh or retry option after the user completes the setup.
7. Explain when a compatible vision model is required for image understanding.

Do not automatically download large models without explicit user action.

Where useful, provide safe links to official installation documentation and explain that model downloads require sufficient disk space and may require an internet connection.

The application must remain usable for Gemini-based tasks even when Ollama is unavailable.

## 7. Document Export Architecture

Create a common export interface and separate implementations for Word, Excel, and PDF.

### 7.1 Word Exporter

Support:

- Headings and subheadings.
- Paragraphs and lists.
- Tables.
- Page margins and page breaks.
- Headers and footers where applicable.
- Page numbering where supported by the selected implementation.
- Consistent typography and spacing.
- Arabic text and right-to-left layout where supported by the document-generation pipeline.

### 7.2 Excel Exporter

Support:

- Multiple worksheets.
- Structured tables.
- Column widths and row heights.
- Number, date, and percentage formatting.
- Formulas where appropriate.
- Filters and freeze panes.
- Conditional formatting.
- Charts when requested and suitable.
- Meaningful worksheet names.
- Basic data validation where applicable.

Do not place the entire AI-generated result into a single cell when the content is more appropriately represented by multiple rows, columns, or worksheets.

Treat executable spreadsheet formulas and untrusted imported content carefully. Avoid unintended formula injection.

### 7.3 PDF Exporter

Support:

- Readable page layouts.
- Paragraphs, headings, and tables.
- Page breaks and margins.
- Arabic font embedding and right-to-left text where supported.
- Searchable text-based PDF generation where appropriate.
- Image-based output only when specifically required.

Use suitable fonts and PDF-rendering techniques for non-Latin scripts. Do not assume that basic font selection alone guarantees correct Arabic shaping or bidirectional text.

### 7.4 Export Validation

After creating a document:

- Verify that the output file exists.
- Verify that it is non-empty.
- Catch and report export failures.
- Avoid reporting success before the operation has actually completed.
- Use temporary files or atomic replacement where appropriate to reduce the risk of corrupt output.
- Provide an action to open the output folder.

## 8. Software Architecture — Mandatory Requirements

Use an object-oriented, modular design following SOLID principles and sound software engineering practices.

The goal is long-term maintainability, easier debugging, and future feature development.

### 8.1 Centralized Constants and Configuration

Place shared constants in a centralized module, such as `config/constants.py`.

Examples include:
- Application name and version references.
- Supported file extensions.
- Default output formats.
- Configuration keys.
- Application directory names.
- Supported provider identifiers.
- Timeout defaults.
- Shared UI dimensions or other genuinely global constants.

Use a separate settings module for runtime configuration and another secure mechanism for API credentials.

Do not duplicate constants throughout the codebase.

Avoid turning the constants file into a repository for mutable application state. Keep constants, user settings, and runtime state separate.

Use environment-aware paths suitable for development and a PyInstaller-built executable.

### 8.2 OOP and SOLID

Implement:

- Classes with clear, limited responsibilities.
- Abstract interfaces for providers, OCR engines, and exporters where appropriate.
- Dependency injection or an equivalent explicit dependency-management approach.
- Composition instead of unnecessary inheritance.
- Type hints for public APIs and important data structures.
- Dataclasses or validated models for structured configuration and operation results.
- Custom exception classes for meaningful failure categories.
- Clear separation between presentation, business logic, infrastructure, and persistence.

Avoid monolithic classes, global mutable state, circular imports, repeated business logic, and excessive coupling between modules.

### 8.3 Error Handling and Logging

Implement consistent exception handling across the application.

Use structured logging with appropriate levels and useful diagnostic context.

Requirements:
- Provide understandable user-facing messages.
- Record technical details in diagnostic logs.
- Never log API keys or sensitive credentials.
- Avoid swallowing exceptions silently.
- Identify recoverable errors and provide retry or fallback options where appropriate.
- Ensure failed background operations return the application to a usable state.

### 8.4 Testability

Business logic must be testable independently of Tkinter.

Use dependency injection and mocks so tests do not require live Gemini requests, a running Ollama service, or large OCR models.

Create tests for:
- Provider discovery and connection failures.
- Dynamic model-list refresh.
- OCR engine selection and error conditions.
- Processing-pipeline behavior.
- Document generation.
- Settings validation and persistence.
- File naming and output-path handling.
- Background task errors.
- GUI navigation and important user workflows where practical.

## 9. Recommended Project Structure

Use this as a starting point. Adjust it when justified by the actual implementation; do not create unnecessary empty modules.

```text
document_builder/
├── app.py
├── requirements.txt
├── README.md
├── pyproject.toml
├── config/
│   ├── constants.py
│   ├── settings.py
│   └── logging_config.py
├── core/
│   ├── interfaces.py
│   ├── exceptions.py
│   ├── models.py
│   └── dependency_container.py
├── ui/
│   ├── main_window.py
│   ├── navigation.py
│   ├── views/
│   ├── dialogs/
│   └── components/
├── ai/
│   ├── base_provider.py
│   ├── ollama_provider.py
│   ├── gemini_provider.py
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
│   ├── word_exporter.py
│   ├── excel_exporter.py
│   └── pdf_exporter.py
├── services/
│   ├── document_service.py
│   ├── ocr_service.py
│   ├── ai_service.py
│   └── task_service.py
├── repositories/
│   ├── settings_repository.py
│   └── history_repository.py
├── resources/
│   ├── icons/
│   └── templates/
├── tests/
├── scripts/
│   └── build_windows.py
└── build/
```

Keep build output and runtime-generated data separate from source code. Include only files that serve a real purpose.

## 10. User Interface and UX

Build a modern, professional desktop interface using Tkinter and ttk.

The interface must be English-only and easy for a user with limited technical experience.

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
2. **Create Document** — enter instructions, select output type, and configure the AI task.
3. **Image & OCR** — import images or PDFs, select a processing method, configure OCR, and review extracted content.
4. **AI Settings** — select provider and model, refresh available models, and check connection status.
5. **Application Settings** — configure language preferences for OCR, output defaults, paths, and other user preferences.
6. **History** — display prior operations and allow users to reopen available files or rerun a task.

Use standard Tkinter background-task patterns or a well-defined worker abstraction to keep the interface responsive. Do not update Tkinter widgets directly from worker threads.

Show progress indicators and meaningful status messages during lengthy operations. Allow cancellation where it can be implemented safely.

## 11. Settings and Local Data

Store non-sensitive settings in a suitable local configuration file and persist them where appropriate.

If application history is implemented, use SQLite with a repository layer rather than embedding database queries throughout the interface.

Keep application settings, operation history, temporary files, generated documents, and logs in suitable user-specific directories.

Use Windows-compatible paths and handle missing directories, permission errors, and unavailable disk space.

For credentials:
- Use an appropriate operating-system credential store where practical.
- Otherwise provide a carefully documented fallback that avoids hardcoding secrets and restricts unnecessary exposure.
- Never commit credentials or generated secrets to version control.

Provide safe defaults and validate configuration on startup.

## 12. Performance, Reliability, and Security

- Do not freeze the main GUI during AI calls, OCR, file conversion, or document export.
- Apply reasonable timeouts to external operations.
- Report network failures, quota limitations, missing dependencies, and unavailable models clearly.
- Avoid unnecessary memory copies of large images and PDF pages.
- Validate imported file types and handle malformed files defensively.
- Clean up temporary files when safe.
- Do not execute generated Python, shell commands, or arbitrary code from AI output.
- Do not treat content imported from user files as trusted instructions.
- Clearly inform users when a workflow sends document content to a cloud provider.
- Keep local processing local when the user explicitly chooses a local-only operation.
- Do not claim perfect OCR accuracy or perfect preservation of complex document formatting.

## 13. Windows EXE Packaging

Prepare the project for Windows distribution using PyInstaller.

Requirements:
- A documented build command or build script.
- A suitable `.spec` file if required.
- Correct handling of packaged resources and writable user-data directories.
- Clear dependency installation instructions.
- Appropriate handling or documentation of OCR executables and external model files.
- Startup and error diagnostics that remain useful in packaged mode.
- A clean distinction between files bundled into the executable and external prerequisites.

Do not attempt to package the entire Ollama installation or large local AI models into the EXE.

The README must explain that Ollama requires a separate installation and that compatible models must be present locally before they can be used. Explain how to configure Gemini and where to obtain a valid API key from its official service.

## 14. Development Workflow

Work in controlled stages. Each stage must produce working, testable results.

### Stage 1 — Repository Inspection and Architecture

- Inspect existing files and requirements.
- Identify important unknowns.
- Present the proposed architecture and key technical decisions.
- Ask a concise set of clarifying questions only if genuinely blocking decisions remain.
- Otherwise state sensible assumptions and proceed without unnecessary questioning.

### Stage 2 — Application Foundation

- Establish the package structure.
- Implement centralized constants, configuration, logging, exceptions, and core interfaces.
- Create the main GUI shell and navigation.
- Verify application startup and settings persistence.

### Stage 3 — AI Providers

- Implement Ollama connectivity checks and installed-model discovery.
- Implement Gemini configuration and model discovery.
- Add model compatibility handling, connection diagnostics, and test doubles.

### Stage 4 — Image Processing and OCR

- Implement preprocessing and OCR interfaces.
- Integrate each selected OCR engine.
- Build the selectable processing pipeline.
- Add text review and error handling.
- Test unavailable models and OCR dependencies.

### Stage 5 — Document Export

- Implement Word, Excel, and PDF exporters.
- Support suitable Arabic and English output.
- Verify generated files with file-format-aware tests.
- Add export validation and overwrite protection.

### Stage 6 — Workflow Integration

- Connect the UI, providers, OCR pipeline, document services, and history.
- Implement progress reporting and background tasks.
- Test complete workflows from user input to exported file.

### Stage 7 — Hardening and Packaging

- Run unit and integration tests.
- Fix errors and regressions.
- Test missing Ollama, missing models, invalid API keys, network failures, and export errors.
- Build the Windows executable.
- Test the packaged application, not just the development version.
- Complete setup and troubleshooting documentation.

Do not proceed by creating many untested modules in a single step. Keep the project runnable at each meaningful milestone.

## 15. Definition of Done

The application is not complete until all applicable acceptance criteria are met:

1. The application launches without an unhandled exception.
2. The English UI is clear, organized, and usable by a non-technical user.
3. Users can choose Word, Excel, or PDF as the output format.
4. Users can select an AI provider and a compatible available model.
5. Ollama is detected when available, and missing installations or models produce actionable guidance.
6. Gemini can be configured without exposing credentials in source code or logs.
7. Users can choose among the supported image-processing and OCR methods.
8. Handwriting and scanned documents can be processed, reviewed, and exported, subject to the capabilities of the chosen engine.
9. Long-running work does not freeze the interface.
10. Word, Excel, and PDF output files are valid and contain the expected content.
11. Arabic and English content is handled appropriately for the selected exporter.
12. Errors are logged and presented clearly, without silent failures.
13. Automated tests cover important business logic and failure paths.
14. The project is documented and can be built into a Windows EXE using the supplied instructions.
15. Adding a new AI provider, OCR engine, or export format can be achieved primarily by implementing the relevant interface and registering the component, rather than rewriting the application.

## 16. Final Deliverables

Provide:

- Complete source code with meaningful file and class names.
- A clear, maintainable package structure.
- Dependency and environment setup instructions.
- A README covering installation, settings, supported workflows, known limitations, and troubleshooting.
- Automated tests and instructions for running them.
- PyInstaller configuration or a reproducible build script.
- A description of the architecture and the extension points for future development.
- A final verification report that distinguishes implemented and tested features from incomplete features or unverified behavior.

Never claim that a feature works unless it has been implemented and appropriately tested.

Do not replace real functionality with placeholders or simulated responses. If a dependency, API, model, or environment is unavailable, implement the appropriate integration boundary, report the limitation, and explain precisely how it can be verified.

**Primary objective:** deliver a dependable, professionally designed Document Builder AI application with a clean user experience, strict separation of concerns, dynamic provider and model selection, selectable OCR pipelines, and a codebase that can be maintained and extended for years.