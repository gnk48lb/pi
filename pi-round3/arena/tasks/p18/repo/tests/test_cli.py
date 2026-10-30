import contextlib
import io
import unittest

from shopcore.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(list(argv)), 0)
        return out.getvalue()

    def test_quote_in_euro(self):
        self.assertEqual(self.run_cli("quote", "A-1", "2"), "A-1 x 2 = EUR 25.00\n")

    def test_quote_in_usd(self):
        self.assertEqual(self.run_cli("quote", "A-1", "2", "--currency", "USD"), "A-1 x 2 = USD 27.50\n")


if __name__ == "__main__":
    unittest.main()
