#!/usr/bin/env python3
"""Build the team's text-only test set from the organizers' demo parquet.

The demo parquet has 50 problems in English and Catalan (100 rows). Ten
problems need their figure, so this script keeps only the 40 text-only
problems (80 rows) and writes them to data/demo/test.jsonl.

It runs laptop/prepare_m3kang.py --text-only (OCR of the options A to E) on
the parquet and renames the result. The data is never committed: M3Kang is
for research use only. Each teammate runs this script to get the same file.

Usage:
    python3 laptop/make_demo_test.py --parquet data/demo-00000-of-00001.parquet
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--parquet", default="data/demo-00000-of-00001.parquet")
    p.add_argument("--languages", default="eng,cat")
    p.add_argument("--out", default="data/demo")
    p.add_argument("--save-images", action="store_true", help="keep a PNG of each problem")
    args = p.parse_args()

    if not os.path.exists(args.parquet):
        sys.exit(f"{args.parquet} not found. Download the demo parquet from the organizers first.")

    cmd = [sys.executable, os.path.join(HERE, "prepare_m3kang.py"), "--parquet", args.parquet,
           "--languages", args.languages, "--val-fraction", "0", "--text-only", "--out", args.out]
    if args.save_images:
        cmd.append("--save-images")
    # UTF-8 so the problem text writes correctly on Windows too
    subprocess.run(cmd, check=True, env={**os.environ, "PYTHONUTF8": "1"})

    # --val-fraction 0 puts every row in train.jsonl; it is our test set
    os.replace(os.path.join(args.out, "train.jsonl"), os.path.join(args.out, "test.jsonl"))
    os.remove(os.path.join(args.out, "val.jsonl"))
    print(f"\nRenamed it to {args.out}/test.jsonl")


if __name__ == "__main__":
    main()
