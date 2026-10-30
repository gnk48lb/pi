import argparse

from . import promotions, reports


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shopcore")
    sub = parser.add_subparsers(dest="cmd", required=True)
    quote = sub.add_parser("quote", help="price a sku")
    quote.add_argument("sku")
    quote.add_argument("qty", type=int)
    quote.add_argument("--kind", default="standard", choices=sorted(promotions.PRICERS))
    quote.add_argument("--currency", default="EUR")
    listing = sub.add_parser("list-prices", help="unit prices")
    listing.add_argument("skus", nargs="+")
    listing.add_argument("--currency", default="EUR")
    args = parser.parse_args(argv)
    if args.cmd == "quote":
        print(promotions.quote(args.kind, args.sku, args.qty, args.currency))
    else:
        print("\n".join(reports.list_prices(args.skus, args.currency)))
    return 0
