"""Hidden acceptance tests for p18: every entry point of the package, in every currency.

Expected values come from an independent exact-arithmetic oracle written from the README."""
import inspect
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import shopcore  # noqa: E402
from shopcore import Cart, Order, export, legacy, order_total, pricing, promotions, reports  # noqa: E402


class EntryPoints(unittest.TestCase):
    def test_currency_is_a_required_keyword_only_parameter(self):
        for fn in (pricing.price_for, pricing.price_bulk):
            p = inspect.signature(fn).parameters["currency"]
            self.assertIs(p.kind, inspect.Parameter.KEYWORD_ONLY, fn.__name__)
            self.assertIs(p.default, inspect.Parameter.empty, fn.__name__)
            with self.assertRaises(TypeError):
                fn("A-1", 1)
            with self.assertRaises(TypeError):
                fn("A-1", 1, "EUR")

    def test_package_level_names_follow_the_change(self):
        self.assertIs(shopcore.price_for, pricing.price_for)
        self.assertIs(shopcore.price_bulk, pricing.price_bulk)
        self.assertIs(shopcore.unit_price, pricing.price_for)
        self.assertIs(inspect.signature(shopcore.unit_price).parameters["currency"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_price_functions_in_every_currency(self):
        for sku, qty, cur, want_std, want_bulk in [["A-1", 1, "EUR", 1250, 1250], ["A-1", 1, "USD", 1375, 1375], ["A-1", 1, "GBP", 1063, 1063], ["A-1", 1, "CHF", 1200, 1200], ["A-1", 3, "EUR", 3750, 3750], ["A-1", 3, "USD", 4125, 4125], ["A-1", 3, "GBP", 3188, 3188], ["A-1", 3, "CHF", 3600, 3600], ["A-1", 9, "EUR", 11250, 11250], ["A-1", 9, "USD", 12375, 12375], ["A-1", 9, "GBP", 9563, 9563], ["A-1", 9, "CHF", 10800, 10800], ["A-1", 10, "EUR", 12500, 11000], ["A-1", 10, "USD", 13750, 12100], ["A-1", 10, "GBP", 10625, 9350], ["A-1", 10, "CHF", 12000, 10560], ["A-1", 20, "EUR", 25000, 22000], ["A-1", 20, "USD", 27500, 24200], ["A-1", 20, "GBP", 21250, 18700], ["A-1", 20, "CHF", 24000, 21120], ["A-1", 49, "EUR", 61250, 53900], ["A-1", 49, "USD", 67375, 59290], ["A-1", 49, "GBP", 52063, 45815], ["A-1", 49, "CHF", 58800, 51744], ["A-1", 50, "EUR", 62500, 47500], ["A-1", 50, "USD", 68750, 52250], ["A-1", 50, "GBP", 53125, 40375], ["A-1", 50, "CHF", 60000, 45600], ["A-1", 99, "EUR", 123750, 94050], ["A-1", 99, "USD", 136125, 103455], ["A-1", 99, "GBP", 105188, 79943], ["A-1", 99, "CHF", 118800, 90288], ["A-1", 100, "EUR", 125000, 95000], ["A-1", 100, "USD", 137500, 104500], ["A-1", 100, "GBP", 106250, 80750], ["A-1", 100, "CHF", 120000, 91200], ["A-1", 101, "EUR", 126250, 95950], ["A-1", 101, "USD", 138875, 105545], ["A-1", 101, "GBP", 107313, 81558], ["A-1", 101, "CHF", 121200, 92112], ["B-2", 1, "EUR", 799, 799], ["B-2", 1, "USD", 879, 879], ["B-2", 1, "GBP", 679, 679], ["B-2", 1, "CHF", 767, 767], ["B-2", 3, "EUR", 2397, 2397], ["B-2", 3, "USD", 2637, 2637], ["B-2", 3, "GBP", 2037, 2037], ["B-2", 3, "CHF", 2301, 2301], ["B-2", 9, "EUR", 7191, 7191], ["B-2", 9, "USD", 7910, 7910], ["B-2", 9, "GBP", 6112, 6112], ["B-2", 9, "CHF", 6903, 6903], ["B-2", 10, "EUR", 7990, 7990], ["B-2", 10, "USD", 8789, 8789], ["B-2", 10, "GBP", 6792, 6792], ["B-2", 10, "CHF", 7670, 7670], ["B-2", 20, "EUR", 15980, 14000], ["B-2", 20, "USD", 17578, 15400], ["B-2", 20, "GBP", 13583, 11900], ["B-2", 20, "CHF", 15341, 13440], ["B-2", 49, "EUR", 39151, 34300], ["B-2", 49, "USD", 43066, 37730], ["B-2", 49, "GBP", 33278, 29155], ["B-2", 49, "CHF", 37585, 32928], ["B-2", 50, "EUR", 39950, 35000], ["B-2", 50, "USD", 43945, 38500], ["B-2", 50, "GBP", 33958, 29750], ["B-2", 50, "CHF", 38352, 33600], ["B-2", 99, "EUR", 79101, 69300], ["B-2", 99, "USD", 87011, 76230], ["B-2", 99, "GBP", 67236, 58905], ["B-2", 99, "CHF", 75937, 66528], ["B-2", 100, "EUR", 79900, 70000], ["B-2", 100, "USD", 87890, 77000], ["B-2", 100, "GBP", 67915, 59500], ["B-2", 100, "CHF", 76704, 67200], ["B-2", 101, "EUR", 80699, 70700], ["B-2", 101, "USD", 88769, 77770], ["B-2", 101, "GBP", 68594, 60095], ["B-2", 101, "CHF", 77471, 67872], ["C-3", 1, "EUR", 15000, 15000], ["C-3", 1, "USD", 16500, 16500], ["C-3", 1, "GBP", 12750, 12750], ["C-3", 1, "CHF", 14400, 14400], ["C-3", 3, "EUR", 45000, 45000], ["C-3", 3, "USD", 49500, 49500], ["C-3", 3, "GBP", 38250, 38250], ["C-3", 3, "CHF", 43200, 43200], ["C-3", 9, "EUR", 135000, 135000], ["C-3", 9, "USD", 148500, 148500], ["C-3", 9, "GBP", 114750, 114750], ["C-3", 9, "CHF", 129600, 129600], ["C-3", 10, "EUR", 150000, 150000], ["C-3", 10, "USD", 165000, 165000], ["C-3", 10, "GBP", 127500, 127500], ["C-3", 10, "CHF", 144000, 144000], ["C-3", 20, "EUR", 300000, 300000], ["C-3", 20, "USD", 330000, 330000], ["C-3", 20, "GBP", 255000, 255000], ["C-3", 20, "CHF", 288000, 288000], ["C-3", 49, "EUR", 735000, 735000], ["C-3", 49, "USD", 808500, 808500], ["C-3", 49, "GBP", 624750, 624750], ["C-3", 49, "CHF", 705600, 705600], ["C-3", 50, "EUR", 750000, 750000], ["C-3", 50, "USD", 825000, 825000], ["C-3", 50, "GBP", 637500, 637500], ["C-3", 50, "CHF", 720000, 720000], ["C-3", 99, "EUR", 1485000, 1485000], ["C-3", 99, "USD", 1633500, 1633500], ["C-3", 99, "GBP", 1262250, 1262250], ["C-3", 99, "CHF", 1425600, 1425600], ["C-3", 100, "EUR", 1500000, 1500000], ["C-3", 100, "USD", 1650000, 1650000], ["C-3", 100, "GBP", 1275000, 1275000], ["C-3", 100, "CHF", 1440000, 1440000], ["C-3", 101, "EUR", 1515000, 1515000], ["C-3", 101, "USD", 1666500, 1666500], ["C-3", 101, "GBP", 1287750, 1287750], ["C-3", 101, "CHF", 1454400, 1454400], ["D-4", 1, "EUR", 5, 5], ["D-4", 1, "USD", 6, 6], ["D-4", 1, "GBP", 4, 4], ["D-4", 1, "CHF", 5, 5], ["D-4", 3, "EUR", 15, 15], ["D-4", 3, "USD", 17, 17], ["D-4", 3, "GBP", 13, 13], ["D-4", 3, "CHF", 14, 14], ["D-4", 9, "EUR", 45, 45], ["D-4", 9, "USD", 50, 50], ["D-4", 9, "GBP", 38, 38], ["D-4", 9, "CHF", 43, 43], ["D-4", 10, "EUR", 50, 50], ["D-4", 10, "USD", 55, 55], ["D-4", 10, "GBP", 43, 43], ["D-4", 10, "CHF", 48, 48], ["D-4", 20, "EUR", 100, 100], ["D-4", 20, "USD", 110, 110], ["D-4", 20, "GBP", 85, 85], ["D-4", 20, "CHF", 96, 96], ["D-4", 49, "EUR", 245, 245], ["D-4", 49, "USD", 270, 270], ["D-4", 49, "GBP", 208, 208], ["D-4", 49, "CHF", 235, 235], ["D-4", 50, "EUR", 250, 250], ["D-4", 50, "USD", 275, 275], ["D-4", 50, "GBP", 213, 213], ["D-4", 50, "CHF", 240, 240], ["D-4", 99, "EUR", 495, 495], ["D-4", 99, "USD", 545, 545], ["D-4", 99, "GBP", 421, 421], ["D-4", 99, "CHF", 475, 475], ["D-4", 100, "EUR", 500, 400], ["D-4", 100, "USD", 550, 440], ["D-4", 100, "GBP", 425, 340], ["D-4", 100, "CHF", 480, 384], ["D-4", 101, "EUR", 505, 404], ["D-4", 101, "USD", 556, 444], ["D-4", 101, "GBP", 429, 343], ["D-4", 101, "CHF", 485, 388]]:
            self.assertEqual(pricing.price_for(sku, qty, currency=cur), want_std, (sku, qty, cur))
            self.assertEqual(pricing.price_bulk(sku, qty, currency=cur), want_bulk, (sku, qty, cur))

    def test_an_unknown_currency_reaches_pricing_from_every_entry_point(self):
        cart = Cart("XXX")
        cart.add("A-1", 2)
        order = Order("N-9", "XXX", [("A-1", 2)])
        calls = {
            "Cart.total": lambda: cart.total(),
            "order_total": lambda: order_total(order),
            "promotions.quote standard": lambda: promotions.quote("standard", "A-1", 2, "XXX"),
            "promotions.quote bulk": lambda: promotions.quote("bulk", "A-1", 2, "XXX"),
            "promotions.cart_quote": lambda: promotions.cart_quote(cart),
            "promotions.cart_quote bulk": lambda: promotions.cart_quote(cart, "bulk"),
            "reports.list_prices": lambda: reports.list_prices(["A-1"], "XXX"),
            "reports.revenue_by_currency": lambda: reports.revenue_by_currency([order]),
            "export.export_rows for": lambda: export.export_rows([order]),
            "export.export_rows bulk": lambda: export.export_rows([order], "bulk"),
            "legacy.legacy_total": lambda: legacy.legacy_total(cart),
        }
        wrong = []
        for name, call in calls.items():
            try:
                call()
            except ValueError:
                continue
            except Exception as exc:  # a TypeError means the call site was not updated
                wrong.append("%s: %s: %s" % (name, type(exc).__name__, exc))
            else:
                wrong.append("%s: no error, the currency was not used" % name)
        self.assertEqual(wrong, [])

    def test_cart_total_in_every_currency(self):
        carts = {"mixed": [["A-1", 2], ["B-2", 1], ["D-4", 3]], "bulk-sized": [["A-1", 10], ["B-2", 20], ["D-4", 100]], "tiers": [["A-1", 50], ["A-1", 9], ["D-4", 99]], "single": [["C-3", 1]]}
        for name, cur, want in [["mixed", "EUR", 3314], ["mixed", "USD", 3646], ["mixed", "GBP", 2817], ["mixed", "CHF", 3181], ["bulk-sized", "EUR", 28980], ["bulk-sized", "USD", 31878], ["bulk-sized", "GBP", 24633], ["bulk-sized", "CHF", 27821], ["tiers", "EUR", 74245], ["tiers", "USD", 81670], ["tiers", "GBP", 63109], ["tiers", "CHF", 71275], ["single", "EUR", 15000], ["single", "USD", 16500], ["single", "GBP", 12750], ["single", "CHF", 14400]]:
            cart = Cart(cur)
            for sku, qty in carts[name]:
                cart.add(sku, qty)
            self.assertEqual(cart.total(), want, (name, cur))

    def test_order_total_in_the_order_currency(self):
        for number, cur, lines, want in [["N-1", "EUR", [["A-1", 2], ["B-2", 1], ["D-4", 3]], 3314], ["N-2", "USD", [["A-1", 10], ["B-2", 20], ["D-4", 100]], 31878], ["N-3", "GBP", [["A-1", 50], ["A-1", 9], ["D-4", 99]], 63109], ["N-4", "CHF", [["A-1", 2], ["B-2", 1], ["D-4", 3]], 3181], ["N-5", "USD", [["C-3", 1]], 16500]]:
            self.assertEqual(order_total(Order(number, cur, [tuple(l) for l in lines])), want, (number, cur))

    def test_revenue_by_currency(self):
        orders = [Order(n, c, [tuple(l) for l in lines]) for n, c, lines in [["N-1", "EUR", [["A-1", 2], ["B-2", 1], ["D-4", 3]]], ["N-2", "USD", [["A-1", 10], ["B-2", 20], ["D-4", 100]]], ["N-3", "GBP", [["A-1", 50], ["A-1", 9], ["D-4", 99]]], ["N-4", "CHF", [["A-1", 2], ["B-2", 1], ["D-4", 3]]], ["N-5", "USD", [["C-3", 1]]]]]
        self.assertEqual(reports.revenue_by_currency(orders), {"EUR": 3314, "USD": 48378, "GBP": 63109, "CHF": 3181})

    def test_quote_through_the_pricer_registry(self):
        for kind, sku, qty, cur, want in [["standard", "A-1", 2, "EUR", "A-1 x 2 = EUR 25.00"], ["standard", "A-1", 2, "USD", "A-1 x 2 = USD 27.50"], ["standard", "A-1", 2, "GBP", "A-1 x 2 = GBP 21.25"], ["standard", "A-1", 2, "CHF", "A-1 x 2 = CHF 24.00"], ["standard", "A-1", 10, "EUR", "A-1 x 10 = EUR 125.00"], ["standard", "A-1", 10, "USD", "A-1 x 10 = USD 137.50"], ["standard", "A-1", 10, "GBP", "A-1 x 10 = GBP 106.25"], ["standard", "A-1", 10, "CHF", "A-1 x 10 = CHF 120.00"], ["standard", "B-2", 25, "EUR", "B-2 x 25 = EUR 199.75"], ["standard", "B-2", 25, "USD", "B-2 x 25 = USD 219.73"], ["standard", "B-2", 25, "GBP", "B-2 x 25 = GBP 169.79"], ["standard", "B-2", 25, "CHF", "B-2 x 25 = CHF 191.76"], ["standard", "C-3", 1, "EUR", "C-3 x 1 = EUR 150.00"], ["standard", "C-3", 1, "USD", "C-3 x 1 = USD 165.00"], ["standard", "C-3", 1, "GBP", "C-3 x 1 = GBP 127.50"], ["standard", "C-3", 1, "CHF", "C-3 x 1 = CHF 144.00"], ["standard", "D-4", 3, "EUR", "D-4 x 3 = EUR 0.15"], ["standard", "D-4", 3, "USD", "D-4 x 3 = USD 0.17"], ["standard", "D-4", 3, "GBP", "D-4 x 3 = GBP 0.13"], ["standard", "D-4", 3, "CHF", "D-4 x 3 = CHF 0.14"], ["standard", "D-4", 100, "EUR", "D-4 x 100 = EUR 5.00"], ["standard", "D-4", 100, "USD", "D-4 x 100 = USD 5.50"], ["standard", "D-4", 100, "GBP", "D-4 x 100 = GBP 4.25"], ["standard", "D-4", 100, "CHF", "D-4 x 100 = CHF 4.80"], ["bulk", "A-1", 2, "EUR", "A-1 x 2 = EUR 25.00"], ["bulk", "A-1", 2, "USD", "A-1 x 2 = USD 27.50"], ["bulk", "A-1", 2, "GBP", "A-1 x 2 = GBP 21.25"], ["bulk", "A-1", 2, "CHF", "A-1 x 2 = CHF 24.00"], ["bulk", "A-1", 10, "EUR", "A-1 x 10 = EUR 110.00"], ["bulk", "A-1", 10, "USD", "A-1 x 10 = USD 121.00"], ["bulk", "A-1", 10, "GBP", "A-1 x 10 = GBP 93.50"], ["bulk", "A-1", 10, "CHF", "A-1 x 10 = CHF 105.60"], ["bulk", "B-2", 25, "EUR", "B-2 x 25 = EUR 175.00"], ["bulk", "B-2", 25, "USD", "B-2 x 25 = USD 192.50"], ["bulk", "B-2", 25, "GBP", "B-2 x 25 = GBP 148.75"], ["bulk", "B-2", 25, "CHF", "B-2 x 25 = CHF 168.00"], ["bulk", "C-3", 1, "EUR", "C-3 x 1 = EUR 150.00"], ["bulk", "C-3", 1, "USD", "C-3 x 1 = USD 165.00"], ["bulk", "C-3", 1, "GBP", "C-3 x 1 = GBP 127.50"], ["bulk", "C-3", 1, "CHF", "C-3 x 1 = CHF 144.00"], ["bulk", "D-4", 3, "EUR", "D-4 x 3 = EUR 0.15"], ["bulk", "D-4", 3, "USD", "D-4 x 3 = USD 0.17"], ["bulk", "D-4", 3, "GBP", "D-4 x 3 = GBP 0.13"], ["bulk", "D-4", 3, "CHF", "D-4 x 3 = CHF 0.14"], ["bulk", "D-4", 100, "EUR", "D-4 x 100 = EUR 4.00"], ["bulk", "D-4", 100, "USD", "D-4 x 100 = USD 4.40"], ["bulk", "D-4", 100, "GBP", "D-4 x 100 = GBP 3.40"], ["bulk", "D-4", 100, "CHF", "D-4 x 100 = CHF 3.84"]]:
            self.assertEqual(promotions.quote(kind, sku, qty, cur), want, (kind, sku, qty, cur))

    def test_cart_quote_through_the_pricer_registry(self):
        carts = {"mixed": [["A-1", 2], ["B-2", 1], ["D-4", 3]], "bulk-sized": [["A-1", 10], ["B-2", 20], ["D-4", 100]], "tiers": [["A-1", 50], ["A-1", 9], ["D-4", 99]], "single": [["C-3", 1]]}
        for name, kind, cur, want in [["mixed", "standard", "EUR", 3314], ["mixed", "standard", "USD", 3646], ["mixed", "standard", "GBP", 2817], ["mixed", "standard", "CHF", 3181], ["mixed", "bulk", "EUR", 3314], ["mixed", "bulk", "USD", 3646], ["mixed", "bulk", "GBP", 2817], ["mixed", "bulk", "CHF", 3181], ["bulk-sized", "standard", "EUR", 28980], ["bulk-sized", "standard", "USD", 31878], ["bulk-sized", "standard", "GBP", 24633], ["bulk-sized", "standard", "CHF", 27821], ["bulk-sized", "bulk", "EUR", 25400], ["bulk-sized", "bulk", "USD", 27940], ["bulk-sized", "bulk", "GBP", 21590], ["bulk-sized", "bulk", "CHF", 24384], ["tiers", "standard", "EUR", 74245], ["tiers", "standard", "USD", 81670], ["tiers", "standard", "GBP", 63109], ["tiers", "standard", "CHF", 71275], ["tiers", "bulk", "EUR", 59245], ["tiers", "bulk", "USD", 65170], ["tiers", "bulk", "GBP", 50359], ["tiers", "bulk", "CHF", 56875], ["single", "standard", "EUR", 15000], ["single", "standard", "USD", 16500], ["single", "standard", "GBP", 12750], ["single", "standard", "CHF", 14400], ["single", "bulk", "EUR", 15000], ["single", "bulk", "USD", 16500], ["single", "bulk", "GBP", 12750], ["single", "bulk", "CHF", 14400]]:
            cart = Cart(cur)
            for sku, qty in carts[name]:
                cart.add(sku, qty)
            self.assertEqual(promotions.cart_quote(cart, kind), want, (name, kind, cur))
            if kind == "standard":
                self.assertEqual(promotions.cart_quote(cart), want, (name, cur))

    def test_list_prices_with_a_partial(self):
        for cur, skus, want in [["EUR", ["A-1", "B-2", "C-3", "D-4"], ["EUR 12.50", "EUR 7.99", "EUR 150.00", "EUR 0.05"]], ["USD", ["A-1", "B-2", "C-3", "D-4"], ["USD 13.75", "USD 8.79", "USD 165.00", "USD 0.06"]], ["GBP", ["A-1", "B-2", "C-3", "D-4"], ["GBP 10.63", "GBP 6.79", "GBP 127.50", "GBP 0.04"]], ["CHF", ["A-1", "B-2", "C-3", "D-4"], ["CHF 12.00", "CHF 7.67", "CHF 144.00", "CHF 0.05"]]]:
            self.assertEqual(reports.list_prices(skus, cur), want, cur)

    def test_export_rows_picks_the_pricing_function_by_name(self):
        orders = [Order(n, c, [tuple(l) for l in lines]) for n, c, lines in [["N-1", "EUR", [["A-1", 2], ["B-2", 1], ["D-4", 3]]], ["N-2", "USD", [["A-1", 10], ["B-2", 20], ["D-4", 100]]], ["N-3", "GBP", [["A-1", 50], ["A-1", 9], ["D-4", 99]]], ["N-4", "CHF", [["A-1", 2], ["B-2", 1], ["D-4", 3]]], ["N-5", "USD", [["C-3", 1]]]]]
        for mode, want in [["for", ["N-1,A-1,2,2500", "N-1,B-2,1,799", "N-1,D-4,3,15", "N-2,A-1,10,13750", "N-2,B-2,20,17578", "N-2,D-4,100,550", "N-3,A-1,50,53125", "N-3,A-1,9,9563", "N-3,D-4,99,421", "N-4,A-1,2,2400", "N-4,B-2,1,767", "N-4,D-4,3,14", "N-5,C-3,1,16500"]], ["bulk", ["N-1,A-1,2,2500", "N-1,B-2,1,799", "N-1,D-4,3,15", "N-2,A-1,10,12100", "N-2,B-2,20,15400", "N-2,D-4,100,440", "N-3,A-1,50,40375", "N-3,A-1,9,9563", "N-3,D-4,99,421", "N-4,A-1,2,2400", "N-4,B-2,1,767", "N-4,D-4,3,14", "N-5,C-3,1,16500"]]]:
            self.assertEqual(export.export_rows(orders, mode), want, mode)
        self.assertEqual(export.export_rows(orders), ["N-1,A-1,2,2500", "N-1,B-2,1,799", "N-1,D-4,3,15", "N-2,A-1,10,13750", "N-2,B-2,20,17578", "N-2,D-4,100,550", "N-3,A-1,50,53125", "N-3,A-1,9,9563", "N-3,D-4,99,421", "N-4,A-1,2,2400", "N-4,B-2,1,767", "N-4,D-4,3,14", "N-5,C-3,1,16500"])

    def test_legacy_total_with_the_module_level_alias(self):
        carts = {"mixed": [["A-1", 2], ["B-2", 1], ["D-4", 3]], "bulk-sized": [["A-1", 10], ["B-2", 20], ["D-4", 100]], "tiers": [["A-1", 50], ["A-1", 9], ["D-4", 99]], "single": [["C-3", 1]]}
        for name, cur, want in [["mixed", "EUR", 3314], ["mixed", "USD", 3646], ["mixed", "GBP", 2817], ["mixed", "CHF", 3181], ["bulk-sized", "EUR", 28980], ["bulk-sized", "USD", 31878], ["bulk-sized", "GBP", 24633], ["bulk-sized", "CHF", 27821], ["tiers", "EUR", 74245], ["tiers", "USD", 81670], ["tiers", "GBP", 63109], ["tiers", "CHF", 71275], ["single", "EUR", 15000], ["single", "USD", 16500], ["single", "GBP", 12750], ["single", "CHF", 14400]]:
            cart = Cart(cur)
            for sku, qty in carts[name]:
                cart.add(sku, qty)
            self.assertEqual(legacy.legacy_total(cart), want, (name, cur))

    def test_command_line_in_a_fresh_process(self):
        for argv, want in [[["quote", "C-3", "2", "--kind", "bulk", "--currency", "GBP"], "C-3 x 2 = GBP 255.00\n"], [["quote", "A-1", "50", "--kind", "bulk", "--currency", "CHF"], "A-1 x 50 = CHF 456.00\n"], [["quote", "D-4", "3", "--currency", "USD"], "D-4 x 3 = USD 0.17\n"], [["list-prices", "A-1", "D-4", "B-2", "--currency", "CHF"], "CHF 12.00\nCHF 0.05\nCHF 7.67\n"], [["list-prices", "C-3", "--currency", "GBP"], "GBP 127.50\n"], [["list-prices", "A-1", "B-2"], "EUR 12.50\nEUR 7.99\n"]]:
            r = subprocess.run([sys.executable, "-m", "shopcore"] + argv, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual((r.returncode, r.stdout), (0, want), (argv, r.stderr[-300:]))

    def test_the_visible_tests_pass(self):
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT, capture_output=True, text=True, timeout=120)
        names = [line.split(" ")[1] for line in r.stderr.splitlines() if line.startswith(("FAIL: ", "ERROR: "))]
        self.assertEqual(r.returncode, 0, "the tests in tests/ fail: " + ", ".join(names))


if __name__ == "__main__":
    unittest.main()
