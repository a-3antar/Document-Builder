"""Structured generation: parse -> validate -> one repair retry -> review."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai.model_registry import ProviderRegistry
from ai.prompts import build_generation_prompt, build_repair_prompt
from config.constants import ContentKind
from core.chart_rules import check_charts
from core.exceptions import AiResponseParseError, ProviderError
from core.models import DocumentContentModel, WorkbookContentModel
from core.schema_validator import SchemaValidator, ValidationIssue, parse_json_response
from core.workbook_spec import WorkbookSpec
from document.spec_rules import check_spec
from document.template_registry import Template
from services.task_service import TaskContext

log = logging.getLogger(__name__)

Content = DocumentContentModel | WorkbookContentModel | WorkbookSpec


@dataclass
class StructuredResult:
    """content is None when validation failed; raw is always preserved."""
    content: Content | None
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
        kind = template.content_kind
        self._progress(ctx, 10, "Generating content...")
        raw = provider.generate_text(
            build_generation_prompt(instructions, schema, kind, template.guidance),
            model, json_mode=True)

        self._progress(ctx, 60, "Validating...")
        data, issues = self._check(raw, template)
        if not issues:
            return StructuredResult(self._build(data, template), raw)

        log.info("Validation failed (%d issues); one repair attempt", len(issues))
        self._progress(ctx, 70, "Repairing invalid output...")
        try:
            repaired = provider.generate_text(
                build_repair_prompt(schema, raw, [str(i) for i in issues], kind),
                model, json_mode=True)
        except ProviderError as exc:  # keep the original answer so the user can review it
            log.warning("Repair call failed: %s", type(exc).__name__)
            note = ValidationIssue("", f"Repair attempt failed: {exc} {exc.hint}".strip())
            return StructuredResult(None, raw, [*issues, note])
        data, issues = self._check(repaired, template)
        if not issues:
            return StructuredResult(self._build(data, template), raw, repair_raw=repaired)
        return StructuredResult(None, raw, issues, repaired)  # user must review/retry

    def _check(self, raw: str, template: Template) -> tuple[Any, list[ValidationIssue]]:
        """Parse, validate against the schema, then run semantic reference checks."""
        try:
            data = parse_json_response(raw)
        except AiResponseParseError as exc:
            return None, [ValidationIssue("", str(exc))]
        issues = self._validator.validate(data, template.schema)
        if not issues:
            kind = template.content_kind
            if kind is ContentKind.WORKBOOK:
                issues = check_charts(WorkbookContentModel.from_dict(data))
            elif kind is ContentKind.SPREADSHEET:
                issues = check_spec(WorkbookSpec.from_dict(data))
        return data, issues

    @staticmethod
    def _build(data: Any, template: Template) -> Content:
        model_cls = {ContentKind.DOCUMENT: DocumentContentModel,
                     ContentKind.WORKBOOK: WorkbookContentModel,
                     ContentKind.SPREADSHEET: WorkbookSpec}[template.content_kind]
        return model_cls.from_dict(data)

    @staticmethod
    def _progress(ctx: TaskContext | None, pct: float, msg: str) -> None:
        if ctx:
            ctx.progress(pct, msg)
            