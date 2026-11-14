#!/usr/bin/env python3
"""How many problems have their options A to E, by language, level, year and source.

    python3 tools/data_report.py                          # data/train.jsonl + data/val.jsonl
    python3 tools/data_report.py --compare data/v1        # also show the change from an older run

Prints counts only, never problem text, so the output is safe to paste into
the write-up.
"""
import argparse
import json
import os
import re
from collections import defaultdict

NUMERIC = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def load(folder):
    rows = []
    for name in ("train.jsonl", "val.jsonl"):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            with open(path) as f:
                rows += [json.loads(line) for line in f if line.strip()]
    return rows


def table(title, rows, key, old=None):
    groups, old_groups = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in rows:
        g = groups[key(r)]
        g[0] += bool(r["options"])
        g[1] += 1
    for r in old or []:
        g = old_groups[key(r)]
        g[0] += bool(r["options"])
        g[1] += 1
    print(f"\n{title}")
    for k in sorted(groups, key=str):
        have, n = groups[k]
        line = f"  {str(k):16} {have:5}/{n:<5} {100 * have / n:5.1f}%"
        if old is not None and old_groups[k][1]:
            line += f"   (was {100 * old_groups[k][0] / old_groups[k][1]:5.1f}%)"
        print(line)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data")
    p.add_argument("--compare", default="", help="folder with an older train.jsonl and val.jsonl")
    args = p.parse_args()

    rows = load(args.data)
    old = load(args.compare) if args.compare else None
    table("All problems", rows, lambda r: "all", old)
    table("By language", rows, lambda r: r["language"], old)
    table("By level", rows, lambda r: r["level"], old)
    table("Text only (no picture needed)", rows, lambda r: r.get("text_only"), old)
    table("By year", rows, lambda r: r.get("year"), old)

    sources = defaultdict(int)
    for r in rows:
        sources[r.get("options_source", "ocr" if r["options"] else "none")] += 1
    print("\nWhere the options come from")
    for k, n in sorted(sources.items()):
        print(f"  {k:16} {n:5}")

    with_options = [r for r in rows if r["options"]]
    numeric = sum(1 for r in with_options if all(NUMERIC.match(v.strip()) for v in r["options"].values()))
    print(f"\nAll five options are plain numbers: {numeric}/{len(with_options)} problems with options")


if __name__ == "__main__":
    main()
