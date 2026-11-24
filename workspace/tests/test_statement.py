import pathlib
import unittest

from export import build_holds_report, build_statement
from sim import fixtures

GOLDEN = pathlib.Path(__file__).parent / "golden"


class StatementTests(unittest.TestCase):
    def setUp(self):
        self.directory, self.kestrel, self.tern = fixtures.build()

    def build(self, member_id):
        return build_statement(member_id, "2026-02", directory=self.directory,
                               kestrel=self.kestrel, tern=self.tern)

    def test_legacy_member_matches_golden(self):
        expected = (GOLDEN / "member_1001_2026-02.csv").read_text()
        self.assertEqual(self.build("1001"), expected)

    def test_large_legacy_account_is_complete(self):
        lines = [l for l in self.build("1002").splitlines() if l.startswith("K-1002-C,")]
        self.assertEqual(len(lines), 60)

    def test_tern_account_is_included(self):
        text = self.build("1003")
        lines = [l for l in text.splitlines() if l.startswith("T-1003-C,")]
        self.assertEqual(len(lines), 4)
        self.assertIn("T-1003-C,2026-02-01,TP00000,Payroll deposit,125.00", text)
        self.assertIn("subtotal,T-1003-C,,,522.50", text)

    def test_holds_report_lists_every_hold(self):
        text = build_holds_report("1002", directory=self.directory, kestrel=self.kestrel)
        self.assertEqual(len(text.splitlines()), 1 + 6)
        self.assertIn("K-1002-C,2026-02-10,KH00000,Card authorization,40.00", text)


if __name__ == "__main__":
    unittest.main()
