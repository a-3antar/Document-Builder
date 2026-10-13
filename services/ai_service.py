"""Structured generation: parse -> validate -> one repair retry -> review."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai.model_registry import ProviderRegistry
from ai.prompts import build_generation_prompt, build_repair_prompt
from config.constants import ContentKind
from core.exceptions import AiResponseParseError
from core.models import DocumentContentModel, WorkbookContentModel
from core.schema_validator import SchemaValidator, ValidationIssue, parse_json_response
from document.template_registry import Template
from services.task_service import TaskContext

log = logging.getLogger(__name__)


@dataclass
class StructuredResult:
    """content is None when validation failed; raw is always preserved."""
    content: DocumentContentModel | WorkbookContentModel | None
    raw: str
    issues: list[ValidationIssue] = field(default_factory=list)
    repair_raw: str = ""

    @property
    def ok(self) -> bool:
        return self.content is not None and not self.issues


class AiService:
    def __init__(self, providers: ProviderRegistry, validator: SchemaValidator) -> None:
        self._providers = providers
        self._validator = validator

    def generate_structured(self, provider_id: str, model: str, instructions: str,
                            template: Template, ctx: TaskContext | None = None) -> StructuredResult:
        """Run on a worker thread; progress goes through ctx."""
        provider = self._providers.create(provider_id)
        schema = self._validator.schema(template.schema)
        self._progress(ctx, 10, "Generating content...")
        raw = provider.generate_text(build_generation_prompt(instructions, schema), model, json_mode=True)

        self._progress(ctx, 60, "Validating...")
        data, issues = self._check(raw, template.schema)
        if not issues:
            return StructuredResult(self._build(data, template), raw)

        log.info("Validation failed (%d issues); one repair attempt", len(issues))
        self._progress(ctx, 70, "Repairing invalid output...")
        repaired = provider.generate_text(
            build_repair_prompt(schema, raw, [str(i) for i in issues]), model, json_mode=True)
        data, issues = self._check(repaired, template.schema)
        if not issues:
            return StructuredResult(self._build(data, template), raw, repair_raw=repaired)
        return StructuredResult(None, raw, issues, repaired)  # user must review/retry

    def _check(self, raw: str, schema_file: str) -> tuple[Any, list[ValidationIssue]]:
        try:
            data = parse_json_response(raw)
        except AiResponseParseError as exc:
            return None, [ValidationIssue("", str(exc))]
        return data, self._validator.validate(data, schema_file)

    @staticmethod
    def _build(data: Any, template: Template) -> DocumentContentModel | WorkbookContentModel:
        model_cls = (DocumentContentModel if template.content_kind is ContentKind.DOCUMENT
                     else WorkbookContentModel)
        return model_cls.from_dict(data)

    @staticmethod
    def _progress(ctx: TaskContext | None, pct: float, msg: str) -> None:
        if ctx:
            ctx.progress(pct, msg)
