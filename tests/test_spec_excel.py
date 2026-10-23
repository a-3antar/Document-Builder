import copy
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from config.constants import ContentKind
from core.exceptions import ExportValidationError
from core.schema_validator import SchemaValidator
from core.workbook_spec import WorkbookSpec
from document.excel_spec_exporter import SpecExcelExporter
from document.spec_rules import check_spec
from document.template_registry import Template

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

TPL = Template("t", "T", "d", ContentKind.WORKBOOK, "workbook_spec.schema.json", {},
               {"header_fill": "1F4E78"}, {})

SPEC = {
    "schema_version": "2.0",
    "metadata": {"title": "Sales", "language": "en"},
    "sheets": [
        {"name": "Dashboard", "role": "dashboard",
         "kpis": [{"label": "Revenue", "source": "sales", "column": "total", "agg": "sum"}],
         "charts": [{"type": "column", "title": "By region", "source": "by_region",
                     "category": "region", "values": ["sum_total"]}]},
        {"name": "Data", "tables": [{
            "name": "sales",
            "columns": [
                {"key": "date", "title": "Date", "type": "date"},
                {"key": "region", "title": "Region", "options": ["North", "South"]},
                {"key": "qty", "title": "Qty", "type": "integer",
                 "conditional": {"kind": "data_bar"}},
                {"key": "price", "title": "Price", "type": "currency"},
                {"key": "total", "title": "Total", "type": "currency", "formula": "{qty}*{price}"}],
            "rows": [["2026-01-05", "North", 2, 10.5, None],
                     ["2026-01-06", "South", 3, 20, None],
                     ["2026-01-07", "North", 1, 5, None]],
            "totals": {"qty": "sum", "total": "sum"}}]},
        {"name": "Summary", "role": "calc", "summaries": [{
            "name": "by_region", "source": "sales", "group_by": "region",
            "metrics": [{"column": "total", "agg": "sum", "title": "Total by region"}]}]},
    ],
}


def _spec(mutate=None) -> WorkbookSpec:
    data = copy.deepcopy(SPEC)
    if mutate:
        mutate(data)
    return WorkbookSpec.from_dict(data)


class SpecExportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.out = Path(self.dir.name) / "o.xlsx"

    def tearDown(self):
        self.dir.cleanup()

    def test_full_workbook(self):
        res = SpecExcelExporter(TPL).export(_spec(), self.out)
        wb = load_workbook(self.out)
        data, summary, dash = wb["Data"], wb["Summary"], wb["Dashboard"]
        self.assertEqual(data["E2"].value, "=C2*D2")
        self.assertEqual(data["C5"].value, "=SUBTOTAL(109,C2:C4)")
        self.assertEqual(data["A5"].value, "Total")
        self.assertIn("tbl_sales", data.tables)
        self.assertEqual(data.freeze_panes, "A2")
        self.assertEqual(len(data.data_validations.dataValidation), 1)
        self.assertTrue(len(data.conditional_formatting) > 0)
        self.assertEqual(summary["A2"].value, "North")
        self.assertEqual(summary["B2"].value, "=SUMIFS('Data'!$E$2:$E$4,'Data'!$B$2:$B$4,$A2)")
        self.assertEqual(summary["B4"].value, "=SUBTOTAL(109,B2:B3)")
        self.assertEqual(dash["A4"].value, "=SUBTOTAL(109,'Data'!$E$2:$E$4)")
        self.assertEqual(len(dash._charts), 1)
        self.assertEqual(res.warnings, ())

    def test_untrusted_text_stays_text(self):
        def patch(d):
            d["sheets"] = [{"name": "S", "tables": [{
                "name": "t", "columns": [{"key": "a", "title": "A"}], "rows": [["=1+1"], ["-5"]]}]}]
        SpecExcelExporter(TPL).export(_spec(patch), self.out)
        ws = load_workbook(self.out)["S"]
        self.assertEqual((ws["A2"].value, ws["A2"].data_type), ("=1+1", "s"))
        self.assertEqual(ws["A3"].data_type, "s")

    def test_invalid_number_becomes_text_with_warning(self):
        def patch(d):
            d["sheets"][1]["tables"][0]["rows"][0][2] = "two"
        res = SpecExcelExporter(TPL).export(_spec(patch), self.out)
        self.assertEqual(load_workbook(self.out)["Data"]["C2"].data_type, "s")
        self.assertTrue(res.warnings)

    def test_invalid_spec_is_rejected(self):
        def patch(d):
            d["sheets"][0]["charts"][0]["source"] = "nope"
        with self.assertRaises(ExportValidationError):
            SpecExcelExporter(TPL).export(_spec(patch), self.out)


class SpecRulesTests(unittest.TestCase):
    def _issues(self, mutate):
        return [str(i) for i in check_spec(_spec(mutate))]

    def test_valid(self):
        self.assertEqual(check_spec(_spec()), [])

    def test_bad_formulas(self):
        def unknown_key(d):
            d["sheets"][1]["tables"][0]["columns"][4]["formula"] = "{missing}*2"

        def forbidden_function(d):
            d["sheets"][1]["tables"][0]["columns"][4]["formula"] = 'HYPERLINK("x")'

        def leading_equals(d):
            d["sheets"][1]["tables"][0]["columns"][4]["formula"] = "={qty}*2"
        for patch in (unknown_key, forbidden_function, leading_equals):
            self.assertTrue(self._issues(patch), patch.__name__)

    def test_reference_problems(self):
        def row_length(d):
            d["sheets"][1]["tables"][0]["rows"][0] = ["2026-01-05"]

        def text_in_chart(d):
            d["sheets"][0]["charts"][0].update(source="sales", category="date", values=["region"])

        def bad_total(d):
            d["sheets"][1]["tables"][0]["totals"] = {"region": "sum"}

        def pie_two_series(d):
            d["sheets"][0]["charts"][0].update(type="pie", values=["sum_total", "sum_total"])
        for patch in (row_length, text_in_chart, bad_total, pie_two_series):
            self.assertTrue(self._issues(patch), patch.__name__)


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
class SpecSchemaTests(unittest.TestCase):
    def test_sample_is_valid_and_bad_is_rejected(self):
        v = SchemaValidator()
        self.assertEqual(v.validate(SPEC, "workbook_spec.schema.json"), [])
        bad = copy.deepcopy(SPEC)
        bad["sheets"][1]["tables"][0]["columns"][0]["type"] = "money"
        self.assertTrue(v.validate(bad, "workbook_spec.schema.json"))


if __name__ == "__main__":
    unittest.main()

