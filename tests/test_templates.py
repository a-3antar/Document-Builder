import json
import tempfile
import unittest
from pathlib import Path

from config.paths import resource_path
from core.exceptions import TemplateValidationError
from core.schema_validator import SchemaValidator
from document.template_registry import TemplateRegistry


def _good(**over):
    base = {"id": "t", "name": "T", "description": "d", "content_kind": "document",
            "schema": "document_content.schema.json", "word": {}, "excel": {}, "pdf": {}}
    return {**base, **over}


class TemplateRegistryTests(unittest.TestCase):
    def _load(self, data):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "t.json").write_text(json.dumps(data), encoding="utf-8")
            TemplateRegistry(SchemaValidator(), Path(d)).load()

    def test_builtin_templates_load(self):
        reg = TemplateRegistry(SchemaValidator())
        reg.load()
        self.assertEqual({t.id for t in reg.all()},
                         {"blank_structured", "business_report", "production_report"})

    def test_missing_schema_names_template(self):
        with self.assertRaisesRegex(TemplateValidationError, "Template 'T'.*not found"):
            self._load(_good(schema="missing.schema.json"))

    def test_incompatible_schema(self):
        with self.assertRaisesRegex(TemplateValidationError, "incompatible"):
            self._load(_good(content_kind="workbook"))

    def test_missing_keys(self):
        data = _good()
        del data["pdf"]
        with self.assertRaisesRegex(TemplateValidationError, "missing keys"):
            self._load(data)

    def test_schema_files_are_valid_json(self):
        for p in resource_path("schemas").glob("*.json"):
            json.loads(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
