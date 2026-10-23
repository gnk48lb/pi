import ast
import inspect
import os
import pathlib
import re
import subprocess
import sys
import unittest
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITEMS = [{"sku": "a", "price": 10.0, "qty": 2, "category": "x"}, {"sku": "b", "price": 0.5, "qty": 3, "category": "y"}]
ORIGINAL_TEST_COUNT = 12


def py_files(sub):
    return sorted(p for p in (ROOT / sub).rglob("*.py") if "__pycache__" not in p.parts)


class NewFunction(unittest.TestCase):
    def test_values_and_signature(self):
        from invtrack.pricing import compute_order_total
        self.assertEqual(compute_order_total(ITEMS), 21.5)
        self.assertEqual(compute_order_total(ITEMS, 0.2), 25.8)
        self.assertEqual(compute_order_total(ITEMS, tax_rate=0.2), 25.8)
        params = inspect.signature(compute_order_total).parameters
        self.assertEqual(list(params), ["items", "tax_rate"])
        self.assertEqual(params["tax_rate"].default, 0.0)

    def test_no_warning_from_the_new_function(self):
        from invtrack.pricing import compute_order_total
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            compute_order_total(ITEMS, tax_rate=0.1)


class DeprecatedAlias(unittest.TestCase):
    def call(self, *args, **kwargs):
        from invtrack.pricing import calc_total
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = calc_total(*args, **kwargs)          # <- the warning must point at this line's file
        return value, [w for w in caught if issubclass(w.category, DeprecationWarning)]

    def test_alias_still_works_positionally_and_by_keyword(self):
        self.assertEqual(self.call(ITEMS)[0], 21.5)
        self.assertEqual(self.call(ITEMS, 0.2)[0], 25.8)
        self.assertEqual(self.call(ITEMS, tax=0.2)[0], 25.8)

    def test_alias_warns_and_names_the_replacement(self):
        _, warns = self.call(ITEMS, tax=0.2)
        self.assertEqual(len(warns), 1)
        self.assertIn("compute_order_total", str(warns[0].message))

    def test_warning_is_attributed_to_the_caller(self):
        _, warns = self.call(ITEMS)
        self.assertTrue(os.path.samefile(warns[0].filename, __file__), warns[0].filename)


class NothingInternalUsesTheOldName(unittest.TestCase):
    def test_package_files_do_not_mention_the_old_name(self):
        bad = []
        for path in py_files("invtrack"):
            if path.name == "pricing.py":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "calc_total" in line:
                    bad.append("%s:%d: %s" % (path.relative_to(ROOT), n, line.strip()))
        self.assertEqual(bad, [], "old name still mentioned")

    def test_pricing_module_only_defines_the_alias(self):
        tree = ast.parse((ROOT / "invtrack" / "pricing.py").read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "calc_total"]
        self.assertEqual(calls, [])

    def test_configured_pricing_function_is_the_new_one(self):
        from invtrack import config, pricing, utils
        self.assertTrue(callable(getattr(pricing, config.PRICING_FUNCTION)))
        self.assertNotEqual(config.PRICING_FUNCTION, "calc_total")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(utils.pricing_function()(ITEMS, 0.2), 25.8)


class BehaviourUnchanged(unittest.TestCase):
    def cli(self, *argv):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        r = subprocess.run([sys.executable, "-W", "error::DeprecationWarning", "-m", "invtrack.cli"] + list(argv),
                           cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_cli_total(self):
        self.assertEqual(self.cli("total", "data/sample.json", "--tax", "0.2"), "Total: 444.48\n")

    def test_cli_report(self):
        self.assertEqual(self.cli("report", "data/sample.json"), "A-101  220.00\nA-102  120.90\nA-100  29.50\n")

    def test_cli_csv(self):
        self.assertEqual(self.cli("csv", "data/sample.json", "--tax", "0.2"),
                         "id,items,total\nA-100,2,35.40\nA-101,1,264.00\nA-102,2,145.08\n")

    def test_library_calls_do_not_warn(self):
        from invtrack import export, reports
        from invtrack.store import load_orders
        orders = load_orders(str(ROOT / "data" / "sample.json"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(dict(reports.sales_report(orders, tax=0.1))["A-101"], 242.0)
            self.assertEqual(reports.revenue_by_category(orders, tax=0.0)["office"], 29.5)
            self.assertEqual(reports.grand_total(orders, tax=0.2), 444.48)
            self.assertEqual(export.to_csv(orders).splitlines()[1], "A-100,2,29.50")


class DocsAndTests(unittest.TestCase):
    def test_docs_use_the_new_name(self):
        for rel in ("README.md", "docs/pricing.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("compute_order_total", text, rel)
            for line in text.splitlines():            # the alias's own signature may still show `tax=`
                if "calc_total" not in line:
                    self.assertNotIn("tax=", line.replace("--tax", ""), rel + " still shows the old keyword: " + line)
            if "calc_total" in text:
                self.assertRegex(text, r"(?i)deprecat", rel + " mentions the old name without saying it is deprecated")

    def test_tests_were_kept_updated_and_extended(self):
        files = py_files("tests")
        count = sum(len(re.findall(r"^\s*def test_", f.read_text(encoding="utf-8"), re.M)) for f in files)
        self.assertGreater(count, ORIGINAL_TEST_COUNT, "the existing tests must stay and a test for the alias must be added")
        mentions = [f for f in files if "calc_total" in f.read_text(encoding="utf-8")]
        self.assertTrue(mentions, "no test exercises the deprecated alias")
        for f in mentions:
            text = f.read_text(encoding="utf-8")
            self.assertTrue(re.search(r"assertWarns|catch_warnings|pytest\.warns", text),
                            "%s uses the old name without checking the warning" % f.name)


if __name__ == "__main__":
    unittest.main()
