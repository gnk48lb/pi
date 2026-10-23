import unittest

from invtrack import reports
from invtrack.store import load_orders


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.orders = load_orders("data/sample.json")

    def test_sales_report_orders_biggest_first(self):
        rows = reports.sales_report(self.orders)
        self.assertEqual([r[0] for r in rows], ["A-101", "A-102", "A-100"])

    def test_sales_report_with_tax(self):
        rows = dict(reports.sales_report(self.orders, tax=0.1))
        self.assertEqual(rows["A-101"], 242.0)

    def test_revenue_by_category(self):
        revenue = reports.revenue_by_category(self.orders)
        self.assertEqual(list(revenue), ["electrical", "furniture", "office"])
        self.assertEqual(revenue["office"], 29.5)

    def test_grand_total(self):
        self.assertEqual(reports.grand_total(self.orders, tax=0.2), 444.48)
