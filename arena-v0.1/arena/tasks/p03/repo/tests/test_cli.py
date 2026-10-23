import io
import unittest

from invtrack import cli


def run(*argv):
    out = io.StringIO()
    code = cli.main(list(argv), out=out)
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def test_total(self):
        code, text = run("total", "data/sample.json", "--tax", "0.2")
        self.assertEqual(code, 0)
        self.assertEqual(text, "Total: 444.48\n")

    def test_report(self):
        _, text = run("report", "data/sample.json")
        self.assertEqual(text.splitlines()[0], "A-101  220.00")

    def test_csv(self):
        _, text = run("csv", "data/sample.json")
        self.assertEqual(text.splitlines()[0], "id,items,total")
        self.assertEqual(len(text.splitlines()), 4)
