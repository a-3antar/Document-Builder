import copy
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from ai.model_registry import ProviderRegistry
from config.constants import ContentKind, OutputFormat
from core.exceptions import ExportError, TemplateValidationError
from core.interfaces import AiProvider
from core.schema_validator import SchemaValidator
from core.workbook_spec import WorkbookSpec
from document.excel_exporter import ExcelExporter
from document.excel_spec_exporter import SpecExcelExporter
from document.template_registry import Template, TemplateRegistry
from services.ai_service import AiService
from services.document_service import DocumentService
from tests.test_spec_excel import SPEC
from ui.components.content_preview import render_preview

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

TEMPLATE = Template("t", "T", "d", ContentKind.SPREADSHEET, "workbook_spec.schema.json",
                    {}, {"header_fill": "1F4E78"}, {}, "GUIDE-X")
GOOD = json.dumps(SPEC)
_bad = copy.deepcopy(SPEC)
_bad["sheets"][0]["charts"][0]["source"] = "nope"
BAD = json.dumps(_bad)


class _Scripted(AiProvider):
    id = "fake"

    def __init__(self, responses):
        self.responses, self.prompts = list(responses), []

    def check_connection(self):
        return True, "ok"

    def list_models(self):
        return []

    def generate_text(self, prompt, model, **options):
        self.prompts.append(prompt)
        return self.responses.pop(0)


class RegistryTests(unittest.TestCase):
    def test_builtin_spreadsheet_templates(self):
        reg = TemplateRegistry(SchemaValidator())
        reg.load()
        self.assertIs(reg.get("production_report").content_kind, ContentKind.SPREADSHEET)
        self.assertIs(reg.get("data_report").content_kind, ContentKind.SPREADSHEET)
        self.assertTrue(reg.get("production_report").guidance)

    def test_incompatible_schema_for_spreadsheet(self):
        data = {"id": "t", "name": "T", "description": "d", "content_kind": "spreadsheet",
                "schema": "document_content.schema.json", "word": {}, "excel": {}, "pdf": {}}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "t.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(TemplateValidationError, "incompatible"):
                TemplateRegistry(SchemaValidator(), Path(d)).load()


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
class AiServiceSpecTests(unittest.TestCase):
    def _run(self, responses):
        prov = _Scripted(responses)
        reg = ProviderRegistry()
        reg.register("fake", lambda: prov)
        result = AiService(reg, SchemaValidator()).generate_structured("fake", "m", "make", TEMPLATE)
        return result, prov

    def test_valid_first_try_with_guidance(self):
        result, prov = self._run([GOOD])
        self.assertTrue(result.ok)
        self.assertIsInstance(result.content, WorkbookSpec)
        self.assertIn("GUIDE-X", prov.prompts[0])
        self.assertIn("computed columns", prov.prompts[0])

    def test_semantic_error_triggers_one_repair(self):
        result, prov = self._run([BAD, GOOD])
        self.assertTrue(result.ok)
        self.assertEqual(len(prov.prompts), 2)
        self.assertIn("nope", prov.prompts[1])

    def test_still_invalid_keeps_raw(self):
        result, prov = self._run([BAD, BAD])
        self.assertFalse(result.ok)
        self.assertIsNone(result.content)
        self.assertEqual(result.raw, BAD)
        self.assertEqual(len(prov.prompts), 2)


class DocumentServiceSpecTests(unittest.TestCase):
    def setUp(self):
        self.svc = DocumentService({OutputFormat.XLSX: ExcelExporter}, spec_factory=SpecExcelExporter)
        self.spec = WorkbookSpec.from_dict(SPEC)

    def test_spec_exports_to_excel(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.xlsx"
            self.svc.export(self.spec, TEMPLATE, "xlsx", out)
            self.assertEqual(load_workbook(out).sheetnames, ["Dashboard", "Data", "Summary"])

    def test_spec_rejects_word_and_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            for fmt in ("docx", "pdf"):
                with self.assertRaises(ExportError):
                    self.svc.export(self.spec, TEMPLATE, fmt, Path(d) / f"o.{fmt}")


class PreviewTests(unittest.TestCase):
    def test_spec_preview(self):
        text = render_preview(WorkbookSpec.from_dict(SPEC))
        for part in ("[Sheet:data] Data", "Total (formula)", "KPI: Revenue",
                     "Summary by_region", "Chart [column]"):
            self.assertIn(part, text)


if __name__ == "__main__":
    unittest.main()
