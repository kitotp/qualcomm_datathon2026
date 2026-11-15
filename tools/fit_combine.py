#!/usr/bin/env python3
"""Fit the weight and letter bias of copilot/combine.py on train, and report on val.

Reads the letter log probabilities cached by tools/collect_letter_probs.py
(the "prefill" field, the request the copilot makes) and joins them with the
problems, which the option prior needs. No model needed: it runs in seconds.

For each weight on a grid, the letter bias is fitted so that the predicted
letters are as frequent as the true ones on train (as in copilot/debias.py).
The weight with the lowest log loss on train wins: train accuracy is almost
flat across weights and too noisy to choose by. Val is only reported, never fitted.

    python3 tools/fit_combine.py
    python3 tools/fit_combine.py --save          # also write copilot/combine.json
"""
import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot import combine, option_prior  # noqa: E402
from copilot.combine import LETTERS, has_options, normalize  # noqa: E402

WEIGHTS = [x / 4 for x in range(0, 17)]  # 0 .. 4: 0 is the model alone (debias.py)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def join(letters_path, problems_path):
    """Rows with five options: (problem, (normalized letter log probabilities, prior scores)).

    Both are computed once here, so the fitting loops only add numbers.
    """
    problems = {(p["id"], p["language"]): p for p in load_jsonl(problems_path)}
    rows = []
    for r in load_jsonl(letters_path):
        p = problems.get((r["id"], r["language"]))
        if p is not None and has_options(p):
            rows.append((p, (normalize(r["prefill"]), option_prior.scores(p))))
    return rows


def predict(rows, weight, bias):
    """Same arithmetic as combine.pick(), on the precomputed scores."""
    out = []
    for _, (lp, prior) in rows:
        sc = {k: lp[k] + bias.get(k, 0.0) + weight * prior[k] for k in LETTERS}
        out.append(max(LETTERS, key=lambda k: (sc[k], -ord(k))))
    return out


def fit_bias(rows, weight, steps=300, lr=0.5):
    """Bias that makes the predicted letter counts match the label counts on train."""
    target = Counter(p["label"] for p, _ in rows)
    bias = {k: 0.0 for k in LETTERS}
    for _ in range(steps):
        got = Counter(predict(rows, weight, bias))
        for k in LETTERS:
            bias[k] += lr * (math.log(target[k] + 1) - math.log(got[k] + 1)) / 4
    return bias


def log_loss(rows, weight, bias):
    """Mean -log P(true letter), with P the softmax of the combined scores.

    Smoother than accuracy, which on a thousand rows moves in noisy steps, so
    it picks the weight more reliably.
    """
    total = 0.0
    for p, (lp, prior) in rows:
        sc = {k: lp[k] + bias.get(k, 0.0) + weight * prior[k] for k in LETTERS}
        m = max(sc.values())
        z = m + math.log(sum(math.exp(v - m) for v in sc.values()))
        total += z - sc[p["label"]]
    return total / max(1, len(rows))


def accuracy(rows, answers):
    return sum(a == p["label"] for (p, _), a in zip(rows, answers)) / max(1, len(rows))


def report(name, rows, answers):
    by_lang = defaultdict(list)
    for (p, _), a in zip(rows, answers):
        by_lang[p["language"]].append(a == p["label"])
    pct = lambda xs: f"{100 * sum(xs) / len(xs):5.1f}%" if xs else "   - "
    hits = [a == p["label"] for (p, _), a in zip(rows, answers)]
    letters = Counter(answers)
    print(f"{name:28} {pct(hits)} ({sum(hits)}/{len(hits)})  eng {pct(by_lang['eng'])}  "
          f"cat {pct(by_lang['cat'])}  " + " ".join(f"{k}{letters[k]}" for k in LETTERS))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default="data/train.jsonl")
    p.add_argument("--val", default="data/val.jsonl")
    p.add_argument("--train-letters", default="results/letters-train.jsonl")
    p.add_argument("--val-letters", default="results/letters-val.jsonl")
    p.add_argument("--save", action="store_true", help="write copilot/combine.json")
    args = p.parse_args()

    train, val = join(args.train_letters, args.train), join(args.val_letters, args.val)
    print(f"train {len(train)} rows, val {len(val)} rows (problems with five options)\n")

    print("weight  train loss  train acc  val acc")
    results = []
    for w in WEIGHTS:
        bias = fit_bias(train, w)
        loss = log_loss(train, w, bias)
        tr, va = accuracy(train, predict(train, w, bias)), accuracy(val, predict(val, w, bias))
        results.append((loss, w, bias))
        print(f"{w:6.2f}  {loss:10.4f}  {100 * tr:8.1f}%  {100 * va:6.1f}%")
    _, weight, bias = min(results, key=lambda x: (x[0], x[1]))
    print(f"\nchosen on train (lowest log loss): weight {weight}, bias "
          + " ".join(f"{k}{bias[k]:+.2f}" for k in LETTERS) + "\n")

    report("val: always D", val, ["D"] * len(val))
    report("val: prior only", val, [option_prior.pick(pr) for pr, _ in val])
    w0_bias = next(b for _, w, b in results if w == 0)
    report("val: model only (weight 0)", val, predict(val, 0.0, w0_bias))
    report("val: model raw argmax", val, [max(LETTERS, key=lambda k: lp[k]) for _, (lp, _p) in val])
    report(f"val: combined (weight {weight})", val, predict(val, weight, bias))

    if args.save:
        out = {"weight": weight, "bias": {k: round(v, 3) for k, v in bias.items()},
               "fitted_on": f"{args.train} ({len(train)} rows with five options)"}
        with open(combine.WEIGHTS_PATH, "w") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        print(f"\nWrote {combine.WEIGHTS_PATH}")


if __name__ == "__main__":
    main()
