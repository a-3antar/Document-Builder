"""Export orchestration: format -> exporter, overwrite policy, content adaptation."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping

from config.constants import OutputFormat
from core.exceptions import ExportError, OutputExistsError
from core.interfaces import BaseExporter, ExportResult
from core.models import DocumentContentModel, WorkbookContentModel
from core.workbook_spec import WorkbookSpec
from document.content_converter import adapt_content
from document.template_registry import Template

ExporterFactory = Callable[[Template], BaseExporter]
Content = DocumentContentModel | WorkbookContentModel | WorkbookSpec

_ILLEGAL_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(title: str, fmt: OutputFormat, default: str = "document") -> str:
    """Windows-safe file name for a document title."""
    stem = _ILLEGAL_RE.sub("_", title).strip(" .")[:80] or default
    if stem.split(".")[0].upper() in _RESERVED:
        stem = f"_{stem}"
    return f"{stem}.{fmt.value}"


def unique_path(path: Path) -> Path:
    """First free 'name (n).ext' next to an existing file."""
    n = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


class DocumentService:
    """`factories` serve classic content; `spec_factory` serves WorkbookSpec (Excel only)."""

    def __init__(self, factories: Mapping[OutputFormat, ExporterFactory],
                 spec_factory: ExporterFactory | None = None) -> None:
        self._factories = dict(factories)
        self._spec_factory = spec_factory

    def suggest_filename(self, content: Content, fmt: OutputFormat | str) -> str:
        return safe_filename(content.metadata.title, OutputFormat(fmt))

    def export(self, content: Content, template: Template, fmt: OutputFormat | str,
               output_path: Path | str, *, overwrite: bool = False) -> ExportResult:
        """Export content; never replaces an existing file unless overwrite=True."""
        fmt = OutputFormat(fmt)
        path = Path(output_path)
        adapted, notes = adapt_content(content, fmt)
        factory = (self._spec_factory if isinstance(adapted, WorkbookSpec)
                   else self._factories.get(fmt))
        if factory is None:
            raise ExportError(f"No exporter is registered for '{fmt.value}'.")
        if path.exists() and not overwrite:
            raise OutputExistsError(f"'{path.name}' already exists.",
                                    hint=f"Choose another name, for example '{unique_path(path).name}'.")
        result = factory(template).export(adapted, path)
        return replace(result, warnings=(*notes, *result.warnings))