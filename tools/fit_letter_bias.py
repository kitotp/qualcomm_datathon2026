#!/usr/bin/env python3
"""Fit a per-letter bias on train, and compare debias strategies on val.

Reads the caches written by tools/collect_letter_probs.py. No model needed:
runs in seconds, so rerun it whenever the data changes.

A strategy turns the five letter log probabilities of a problem into one
letter. The bias strategies add a number per letter before the argmax:
    answer = argmax_L ( logp(L) + bias[L] )
The bias is fitted on train only (coordinate search for the best accuracy),
separately for problems with and without OCR options when asked.

    python3 tools/fit_letter_bias.py
    python3 tools/fit_letter_bias.py --save copilot/letter_bias.json --mode prefill
"""
import argparse
import json
import math
from collections import Counter, defaultdict

LETTERS = "ABCDE"
GRID = [x / 4 for x in range(-40, 41)]  # -10 .. 10 in steps of 0.25


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize(lp):
    """Log softmax over the five letters, so the two modes are comparable."""
    m = max(lp.values())
    z = m + math.log(sum(math.exp(v - m) for v in lp.values()))
    return {k: v - z for k, v in lp.items()}


def scores(row, mode):
    if mode == "both":
        a, b = normalize(row["wide"]), normalize(row["prefill"])
        return {k: a[k] + b[k] for k in LETTERS}
    return normalize(row[mode])


def pick(sc, bias):
    return max(LETTERS, key=lambda k: (sc[k] + bias.get(k, 0.0), -ord(k)))


def accuracy(rows, mode, bias):
    if not rows:
        return 0.0
    return sum(pick(scores(r, mode), bias) == r["label"] for r in rows) / len(rows)


def fit_bias(rows, mode, rounds=4):
    """Coordinate search: A stays at 0, B..E move on a grid, best train accuracy."""
    bias = {k: 0.0 for k in LETTERS}
    cached = [scores(r, mode) for r in rows]
    labels = [r["label"] for r in rows]

    def acc(b):
        return sum(pick(s, b) == y for s, y in zip(cached, labels))

    best = acc(bias)
    for _ in range(rounds):
        improved = False
        for k in "BCDE":
            for v in GRID:
                trial = dict(bias, **{k: v})
                a = acc(trial)
                if a > best:
                    best, bias, improved = a, trial, True
        if not improved:
            break
    return bias


def fit_prior(rows, mode, steps=300, lr=0.5):
    """Bias that makes the predicted letter counts match the label counts.

    Unlike fit_bias, it can't collapse onto the most common letter: it removes
    the model's taste for some letters and keeps whatever signal is left.
    """
    target = Counter(r["label"] for r in rows)
    cached = [scores(r, mode) for r in rows]
    bias = {k: 0.0 for k in LETTERS}
    for _ in range(steps):
        got = Counter(pick(s, bias) for s in cached)
        for k in LETTERS:
            bias[k] += lr * (math.log(target[k] + 1) - math.log(got[k] + 1)) / 4
    return bias


def report(name, rows, predict):
    hits = [predict(r) == r["label"] for r in rows]
    by_opt = defaultdict(list)
    by_lang = defaultdict(list)
    for r, h in zip(rows, hits):
        by_opt[r["has_options"]].append(h)
        by_lang[r["language"]].append(h)
    letters = Counter(predict(r) for r in rows)
    pct = lambda xs: f"{100 * sum(xs) / len(xs):5.1f}%" if xs else "   - "
    print(f"{name:34} {pct(hits)}  opts {pct(by_opt[True])}  no-opts {pct(by_opt[False])}  "
          f"eng {pct(by_lang['eng'])}  cat {pct(by_lang['cat'])}  "
          + " ".join(f"{k}{letters[k]}" for k in LETTERS))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default="results/letters-train.jsonl")
    p.add_argument("--val", default="results/letters-val.jsonl")
    p.add_argument("--save", default="", help="write the chosen bias as JSON")
    p.add_argument("--mode", default="prefill", choices=["wide", "prefill", "both"],
                   help="the mode whose bias --save writes")
    args = p.parse_args()

    train, val = load(args.train), load(args.val)
    tr_opt = [r for r in train if r["has_options"]]
    tr_no = [r for r in train if not r["has_options"]]
    print(f"train {len(train)} ({len(tr_opt)} with options), val {len(val)}")
    print("val labels:", " ".join(f"{k}{Counter(r['label'] for r in val)[k]}" for k in LETTERS))
    best_const = Counter(r["label"] for r in tr_no).most_common(1)[0][0]
    print(f"most common train label without options: {best_const}\n")

    report("always D", val, lambda r: "D")
    saved = {}
    for mode in ["wide", "prefill", "both"]:
        report(f"{mode}: argmax", val, lambda r, m=mode: pick(scores(r, m), {}))
        b_all = fit_bias(train, mode)
        report(f"{mode}: bias (one for all)", val, lambda r, m=mode, b=b_all: pick(scores(r, m), b))
        b_opt, b_no = fit_bias(tr_opt, mode), fit_bias(tr_no, mode)
        split = lambda r, m=mode: pick(scores(r, m), b_opt if r["has_options"] else b_no)
        report(f"{mode}: bias (split by options)", val, split)
        hybrid = lambda r, m=mode: pick(scores(r, m), b_opt) if r["has_options"] else best_const
        report(f"{mode}: bias opts, const no-opts", val, hybrid)
        print(f"   bias opts {fmt(b_opt)}   no-opts {fmt(b_no)}")
        p_opt = fit_prior(tr_opt, mode)
        prior = lambda r, m=mode: pick(scores(r, m), p_opt) if r["has_options"] else best_const
        report(f"{mode}: prior-match opts, const", val, prior)
        print(f"   prior opts {fmt(p_opt)}")
        saved[mode] = {"with_options": b_opt, "without_options": b_no, "one_for_all": b_all,
                       "prior_with_options": p_opt, "constant_without_options": best_const}

    if args.save:
        chosen = saved[args.mode]  # the strategy copilot/debias.py uses
        prior = {k: round(v, 3) for k, v in chosen["prior_with_options"].items()}
        out = {"mode": args.mode, "prior_with_options": prior,
               "constant_without_options": chosen["constant_without_options"],
               "fitted_on": f"{len(train)} train rows, {len(tr_opt)} with options"}
        with open(args.save, "w") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        print(f"\nWrote {args.save}")


def fmt(b):
    return " ".join(f"{k}{b[k]:+.2f}" for k in LETTERS)


if __name__ == "__main__":
    main()
