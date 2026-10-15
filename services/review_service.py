"""Schema validation of reviewed (user-edited) document content."""
from __future__ import annotations

from core.models import DocumentContentModel
from core.schema_validator import SchemaValidator, ValidationIssue

DOCUMENT_SCHEMA = "document_content.schema.json"


class ReviewService:
    """Checks edited content against the real JSON Schema before export."""

    def __init__(self, validator: SchemaValidator) -> None:
        self._validator = validator

    def validate_document(self, content: DocumentContentModel) -> list[ValidationIssue]:
        """Empty list means valid; raises DependencyMissingError without jsonschema."""
        return self._validator.validate(content.to_dict(), DOCUMENT_SCHEMA)
