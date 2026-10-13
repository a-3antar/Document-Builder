import unittest

from core.models import DocumentContentModel, WorkbookContentModel
from ui.components.content_preview import render_preview


class PreviewTests(unittest.TestCase):
    def test_document(self):
        model = DocumentContentModel.from_dict({
            "metadata": {"title": "T"},
            "blocks": [{"type": "heading", "text": "H", "level": 2},
                       {"type": "list", "items": ["a", "b"], "ordered": True},
                       {"type": "table", "headers": ["x", "y"], "rows": [["1", "2"]]}]})
        text = render_preview(model)
        for part in ("Title: T", "## H", "1. a", "2. b", "x | y", "1 | 2"):
            self.assertIn(part, text)

    def test_workbook(self):
        model = WorkbookContentModel.from_dict({
            "metadata": {"title": "W"},
            "sheets": [{"name": "S", "columns": ["a", "b"],
                        "rows": [[{"type": "number", "value": 5}, {"type": "blank"}]]}]})
        text = render_preview(model)
        self.assertIn("[Sheet] S", text)
        self.assertIn("5 | ", text)


if __name__ == "__main__":
    unittest.main()
