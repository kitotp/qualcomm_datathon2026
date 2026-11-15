#!/usr/bin/env python3
"""Give coins to students by hand, to test the shop without solving problems.

    python tools/give_coins.py                          # every student in the demo city: enough for the whole shop
    python tools/give_coins.py --student anna --coins 50
    python tools/give_coins.py --db data/city.db --student anna --coins 50

Works while the dev server is running: the page shows the new balance on its
next refresh (the City tab looks every few seconds). It's a command-line tool
on purpose, so students can't reach it from the web page.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot.city import SHOP, City  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=os.path.join(ROOT, "data", "dev_city.db"), help="default: the --demo city")
    p.add_argument("--student", help="one student (default: everyone in the city)")
    p.add_argument("--coins", type=int, default=sum(item["price"] for item in SHOP.values()),
                   help="coins to add, negative to take away (default: the price of the whole shop)")
    args = p.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"{args.db} not found. Start the dev server and create a student first.")
    city = City(args.db)
    students = [args.student] if args.student else [r["student"] for r in city.residents()]
    for name in students:
        r = city.grant(name, args.coins)
        print(f"{r['student']}: {r['coins']} coins")


if __name__ == "__main__":
    main()
