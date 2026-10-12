"""Declarative template loading and validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.constants import ContentKind
from config.paths import resource_path
from core.exceptions import TemplateValidationError
from core.schema_validator import SchemaValidator

_REQUIRED_KEYS = ("id", "name", "description", "content_kind", "schema", "word", "excel", "pdf")


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    content_kind: ContentKind
    schema: str
    word: dict[str, Any]
    excel: dict[str, Any]
    pdf: dict[str, Any]


class TemplateRegistry:
    """Load every *.json in the template dir; fail loudly with the template name."""

    def __init__(self, validator: SchemaValidator, template_dir: Path | None = None) -> None:
        self._validator = validator
        self._dir = template_dir or resource_path("templates")
        self._templates: dict[str, Template] = {}

    def load(self) -> None:
        self._templates.clear()
        for path in sorted(self._dir.glob("*.json")):
            template = self._parse(path)
            if template.id in self._templates:
                raise TemplateValidationError(f"Template '{template.name}': duplicate id '{template.id}'")
            self._templates[template.id] = template

    def _parse(self, path: Path) -> Template:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TemplateValidationError(f"Template file '{path.name}' is unreadable: {exc}") from exc
        name = data.get("name", path.stem)
        missing = [k for k in _REQUIRED_KEYS if k not in data]
        if missing:
            raise TemplateValidationError(f"Template '{name}': missing keys {missing}")
        try:
            kind = ContentKind(data["content_kind"])
        except ValueError as exc:
            raise TemplateValidationError(
                f"Template '{name}': unknown content_kind '{data['content_kind']}'") from exc
        if not self._validator.schema_exists(data["schema"]):
            raise TemplateValidationError(f"Template '{name}': schema '{data['schema']}' not found")
        expected = "document_content" if kind is ContentKind.DOCUMENT else "workbook_content"
        if not data["schema"].startswith(expected):
            raise TemplateValidationError(
                f"Template '{name}': schema '{data['schema']}' is incompatible with {kind.value} content")
        return Template(data["id"], name, data["description"], kind, data["schema"],
                        data["word"], data["excel"], data["pdf"])

    def all(self) -> list[Template]:
        return list(self._templates.values())

    def get(self, template_id: str) -> Template:
        try:
            return self._templates[template_id]
        except KeyError:
            raise TemplateValidationError(f"Unknown template id '{template_id}'") from None
