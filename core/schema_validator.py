"""JSON-Schema validation and AI response parsing."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from config.paths import resource_path
from core.exceptions import AiResponseParseError, DependencyMissingError, SchemaNotFoundError

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?```\s*$", re.DOTALL)


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path or '<root>'}: {self.message}"


def strip_code_fence(text: str) -> str:
    """Remove a surrounding Markdown fence only when present."""
    match = _FENCE_RE.match(text)
    return match.group(1) if match else text.strip()


def parse_json_response(raw: str) -> Any:
    """Parse a provider response into JSON or raise AiResponseParseError."""
    try:
        return json.loads(strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise AiResponseParseError(
            f"The AI response is not valid JSON ({exc.msg} at line {exc.lineno}).",
            hint="Retry the request or edit the content manually.",
        ) from exc


class SchemaValidator:
    """Validate data against schema files in resources/schemas."""

    def __init__(self, resolver: Callable[..., Any] = resource_path) -> None:
        self._resolve = resolver
        self._cache: dict[str, dict[str, Any]] = {}

    def schema_exists(self, schema_file: str) -> bool:
        return self._resolve("schemas", schema_file).is_file()

    def _load(self, schema_file: str) -> dict[str, Any]:
        if schema_file not in self._cache:
            path = self._resolve("schemas", schema_file)
            if not path.is_file():
                raise SchemaNotFoundError(f"Schema file not found: {schema_file}")
            self._cache[schema_file] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[schema_file]

    def validate(self, data: Any, schema_file: str) -> list[ValidationIssue]:
        """Return all issues; an empty list means valid."""
        try:
            from jsonschema import Draft202012Validator
        except ImportError as exc:
            raise DependencyMissingError(
                "The 'jsonschema' package is not installed.", hint="Run: pip install jsonschema"
            ) from exc
        validator = Draft202012Validator(self._load(schema_file))
        errors = sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path])
        return [ValidationIssue("/".join(str(p) for p in e.absolute_path), e.message) for e in errors]
