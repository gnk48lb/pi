"""Command line entry point: python3 -m invtrack.cli <command> <file> [--tax RATE]"""
import argparse
import sys

from . import export, reports, store, utils


def build_parser():
    parser = argparse.ArgumentParser(prog="invtrack")
    parser.add_argument("command", choices=["total", "report", "csv"])
    parser.add_argument("file")
    parser.add_argument("--tax", type=float, default=0.0)
    return parser


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    orders = store.load_orders(args.file)
    price = utils.pricing_function()
    if args.command == "total":
        total = round(sum(price(o["items"], args.tax) for o in orders), 2)
        out.write("Total: %s\n" % utils.money(total))
    elif args.command == "report":
        for order_id, total in reports.sales_report(orders, tax=args.tax):
            out.write("%s  %s\n" % (order_id, utils.money(total)))
    else:
        out.write(export.to_csv(orders, tax=args.tax))
    return 0


if __name__ == "__main__":
    sys.exit(main())
