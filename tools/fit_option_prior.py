#!/usr/bin/env python3
"""Fit the weights of copilot/option_prior.py on train, and report on val.

No language model and no extra packages: it takes a few seconds, so rerun it
whenever the data changes (for example after a better OCR of the options).

    python3 tools/fit_option_prior.py                 # report only
    python3 tools/fit_option_prior.py --save          # also write copilot/option_prior.json

The model is a small softmax over the five letters. Each letter's score is
the sum of the weights of its features (see copilot/option_prior.py), and the
weights are fitted on train only, by gradient descent on the log loss.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot import option_prior  # noqa: E402
from copilot.option_prior import LETTERS, features, numeric_options, pick  # noqa: E402


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def fit(problems, steps=400, rate=1.0, l2=1.0):
    rows = [(features(p), p["label"]) for p in problems]
    weights = Counter()
    n = len(rows)
    for _ in range(steps):
        grad = Counter()
        for on, label in rows:
            sc = {k: sum(weights[name] for name in on[k]) for k in LETTERS}
            top = max(sc.values())
            total = sum(math.exp(v - top) for v in sc.values())
            for k in LETTERS:
                error = math.exp(sc[k] - top) / total - (k == label)
                for name in on[k]:
                    grad[name] += error
        for name in grad:
            weights[name] -= rate * (grad[name] + l2 * weights[name]) / n
    return {name: round(w, 4) for name, w in sorted(weights.items())}


def accuracy(problems, weights):
    if not problems:
        return "   -"
    hits = sum(pick(p, weights) == p["label"] for p in problems)
    return f"{100 * hits / len(problems):5.1f}% ({hits}/{len(problems)})"


def report(name, problems, weights):
    numeric = [p for p in problems if numeric_options(p)]
    other = [p for p in problems if p.get("options") and not numeric_options(p)]
    blind = [p for p in problems if not p.get("options")]
    common = Counter(p["label"] for p in problems).most_common(1)[0]
    print(f"{name}: all {accuracy(problems, weights)}   numeric options {accuracy(numeric, weights)}   "
          f"other options {accuracy(other, weights)}   no options {accuracy(blind, weights)}   "
          f"always {common[0]}: {100 * common[1] / len(problems):.1f}%")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default="data/train.jsonl")
    p.add_argument("--val", default="data/val.jsonl")
    p.add_argument("--save", action="store_true", help="write copilot/option_prior.json")
    args = p.parse_args()

    train, val = load(args.train), load(args.val)
    weights = fit(train)
    report("train", train, weights)
    report("val  ", val, weights)
    print("\nweights")
    for name, w in weights.items():
        print(f"  {name:22s} {w:+.2f}")
    if args.save:
        with open(option_prior.WEIGHTS_PATH, "w") as f:
            json.dump({"fitted_on": f"{args.train} ({len(train)} problems)", "weights": weights}, f, indent=1)
            f.write("\n")
        print(f"\nsaved {option_prior.WEIGHTS_PATH}")


if __name__ == "__main__":
    main()
