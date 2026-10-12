import unittest

from core.exceptions import AiResponseParseError
from core.models import DocumentContentModel, Heading, Table, WorkbookContentModel
from core.schema_validator import SchemaValidator, parse_json_response, strip_code_fence

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

DOC = {"schema_version": "1.0", "metadata": {"title": "T", "language": "ar"},
       "blocks": [{"type": "heading", "text": "عنوان", "level": 1},
                  {"type": "paragraph", "text": "Mixed نص"},
                  {"type": "list", "items": ["a", "b"]},
                  {"type": "table", "headers": ["h"], "rows": [["1"]]}]}


class ParsingTests(unittest.TestCase):
    def test_fence_removed_only_when_present(self):
        self.assertEqual(strip_code_fence('```json\n{"a": 1}\n```'), '{"a": 1}')
        self.assertEqual(strip_code_fence(' {"a": 1} '), '{"a": 1}')

    def test_parse_ok_and_error(self):
        self.assertEqual(parse_json_response('```\n{"a":1}\n```'), {"a": 1})
        with self.assertRaises(AiResponseParseError):
            parse_json_response("not json")


class ModelTests(unittest.TestCase):
    def test_document_roundtrip(self):
        model = DocumentContentModel.from_dict(DOC)
        self.assertIsInstance(model.blocks[0], Heading)
        self.assertIsInstance(model.blocks[3], Table)
        self.assertEqual(model.metadata.language, "ar")
        self.assertEqual(DocumentContentModel.from_dict(model.to_dict()).blocks, model.blocks)

    def test_workbook_cells_typed(self):
        wb = WorkbookContentModel.from_dict({"sheets": [{"name": "S", "columns": ["a"], "rows": [
            [{"type": "number", "value": -5}], [{"type": "text", "value": "=1+1"}]]}]})
        self.assertEqual(wb.sheets[0].rows[1][0].type, "text")


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.v = SchemaValidator()

    def test_valid_document(self):
        self.assertEqual(self.v.validate(DOC, "document_content.schema.json"), [])

    def test_invalid_document_reports_path(self):
        bad = {**DOC, "blocks": [{"type": "heading"}]}
        self.assertTrue(self.v.validate(bad, "document_content.schema.json"))

    def test_workbook_typed_cells(self):
        ok = {"schema_version": "1.0", "metadata": {"title": "x"}, "sheets": [
            {"name": "S", "columns": ["a"], "rows": [[{"type": "number", "value": 1}]]}]}
        self.assertEqual(self.v.validate(ok, "workbook_content.schema.json"), [])
        ok["sheets"][0]["rows"][0][0]["value"] = "1"
        self.assertTrue(self.v.validate(ok, "workbook_content.schema.json"))


if __name__ == "__main__":
    unittest.main()
