#!/usr/bin/env python3
"""Let the model write a short solution, then take the answer from it.

The baseline asks for one letter with no working, which is close to guessing.
Here the model first writes a few lines of working, and the answer comes from
follow-up calls that reuse the cached prompt:

  number  for options that are plain numbers: a grammar forces a number, and
          it counts only if it equals exactly one option
  letter  for any problem with options: a grammar forces one letter, A to E

    python3 tools/solve_match.py --limit 5 --port 8093
    python3 tools/solve_match.py --subset options --board-budget --output results/solve-val.jsonl

--board-budget cuts the working so that the whole problem fits the board's
60 seconds, using the board's speeds for the 0.8B model (README step 6:
reads about 11 tokens per second, writes about 6). The laptop is about ten
times faster, so without it the accuracy here would not be the board's.

Writes one JSON line per problem (id, language, label, answers, tokens,
estimated board seconds), without the problem text or the model's solution,
so the file is safe to keep. --raw also writes the solutions, for reading
errors; keep that file out of git.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot.client import post  # noqa: E402
from copilot.config import CONFIG  # noqa: E402

LETTERS = "ABCDE"
UNIT = r"\s*(?:cm|mm|km|m|kg|g|€|euros?|%|°|min|h|s)?\.?\s*"
NUMBER = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)" + UNIT + r"$", re.I)

SYSTEM = ("You solve math competition problems for school students. "
          "Be very brief: at most 4 short lines of working, no restating the problem.")
ASK_NUMBER = "Final answer, as a number only:"
ASK_LETTER = "Final answer, the letter of the option only:"
NUMBER_GRAMMAR = 'root ::= "-"? [0-9]+ ("." [0-9]+)?'

# Board speeds for Qwen3.5 0.8B, in tokens per second (README step 6)
BOARD_READ, BOARD_WRITE = 11.0, 5.9
BOARD_BUDGET_S = 50      # leaves 10 s of the 60 s limit as a margin
TEMPLATE_TOKENS = 45     # system prompt and chat template around the problem
FOLLOW_UP_TOKENS = 15    # new prompt tokens of each follow-up call
MIN_WORKING_TOKENS = 30  # below this the working is too short to help


def value(text):
    """'12', '12 cm', '3,5' -> float; anything else -> None."""
    m = NUMBER.match(str(text))
    return float(m.group(1).replace(",", ".")) if m else None


def numeric_options(problem):
    opts = problem.get("options") or {}
    if set(opts) != set(LETTERS):
        return None
    vals = {k: value(v) for k, v in opts.items()}
    return vals if all(v is not None for v in vals.values()) else None


def match(number, vals):
    hits = [k for k, v in vals.items() if abs(v - number) < 1e-6]
    return hits[0] if len(hits) == 1 else None


def board_seconds(prompt_tokens, written_tokens, follow_ups):
    return (prompt_tokens + FOLLOW_UP_TOKENS * follow_ups) / BOARD_READ + written_tokens / BOARD_WRITE


def working_budget(base, text, max_tokens, follow_ups):
    """How many tokens of working fit in the board's time for this problem."""
    tokens = len(post(base + "/tokenize", {"content": text}, timeout=30)["tokens"]) + TEMPLATE_TOKENS
    left = BOARD_BUDGET_S - board_seconds(tokens, 6 * follow_ups, follow_ups)
    return max(0, min(max_tokens, int(left * BOARD_WRITE)))


def solve(problem, base, max_tokens, board_budget):
    """Return the answers of one problem and what they cost."""
    url = base + "/v1/chat/completions"
    text = "\n".join([problem["text"].strip()] + [f"{k}) {problem['options'][k]}" for k in LETTERS])
    vals = numeric_options(problem)
    follow_ups = 2 if vals else 1
    if board_budget:
        max_tokens = working_budget(base, text, max_tokens, follow_ups)
    common = {"temperature": 0, "seed": int(CONFIG["SEED"]), "cache_prompt": True}
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
    written = 0

    def call(extra, **options):
        nonlocal written
        response = post(url, {"messages": messages + extra, **options, **common}, timeout=120)
        written += response.get("usage", {}).get("completion_tokens", 0)
        return response

    working, prompt_tokens = "", 0
    if max_tokens >= MIN_WORKING_TOKENS:
        r = call([], max_tokens=max_tokens)
        working = r["choices"][0]["message"]["content"]
        prompt_tokens = r.get("usage", {}).get("prompt_tokens", 0)
    done = [{"role": "assistant", "content": working}] if working else []

    number = by_number = None
    if vals and working:
        r = call(done + [{"role": "user", "content": ASK_NUMBER}], max_tokens=12, grammar=NUMBER_GRAMMAR)
        number = float(r["choices"][0]["message"]["content"].strip())
        by_number = match(number, vals)
    r = call(done + [{"role": "user", "content": ASK_LETTER}], max_tokens=1, grammar="root ::= [A-E]")
    by_letter = r["choices"][0]["message"]["content"].strip()
    prompt_tokens = prompt_tokens or r.get("usage", {}).get("prompt_tokens", 0)

    return {"number": number, "by_number": by_number, "by_letter": by_letter,
            "prompt_tokens": prompt_tokens, "written_tokens": written, "working_limit": max_tokens,
            "board_s": round(board_seconds(prompt_tokens, written, follow_ups), 1)}, working


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--output", default="")
    p.add_argument("--raw", default="", help="also write the model's solutions here (not for git)")
    p.add_argument("--port", type=int, default=int(CONFIG["LLM_PORT"]))
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--max-tokens", type=int, default=160, help="limit for the working")
    p.add_argument("--subset", default="numeric", choices=["numeric", "options"],
                   help="numeric: text only with numeric options; options: every problem with options")
    p.add_argument("--board-budget", action="store_true",
                   help="cut the working so the problem fits the board's time limit")
    args = p.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    with open(args.input) as f:
        problems = [json.loads(line) for line in f if line.strip()]
    if args.subset == "numeric":
        todo = [pr for pr in problems if pr.get("text_only") and numeric_options(pr)]
    else:
        todo = [pr for pr in problems if set(pr.get("options") or {}) == set(LETTERS)]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} of {len(problems)} problems selected ({args.subset})", file=sys.stderr)

    out = open(args.output, "w") if args.output else None
    raw = open(args.raw, "w") if args.raw else None
    rows = []
    for i, pr in enumerate(todo, 1):
        start = time.time()
        result, working = solve(pr, base, args.max_tokens, args.board_budget)
        row = {"id": pr["id"], "language": pr.get("language", ""), "level": pr.get("level"),
               "text_only": bool(pr.get("text_only")), "numeric": numeric_options(pr) is not None,
               "label": pr.get("label"), **result, "laptop_s": round(time.time() - start, 1)}
        rows.append(row)
        if out:
            out.write(json.dumps(row) + "\n")
            out.flush()
        if raw:
            raw.write(json.dumps({**row, "working": working}, ensure_ascii=False) + "\n")
            raw.flush()
        print(f"[{i}/{len(todo)}] {row['id']} {row['language']} number={row['by_number']} "
              f"letter={row['by_letter']} label={row['label']} board~{row['board_s']}s", file=sys.stderr)
    report(rows)


def report(rows):
    n = len(rows)
    if not n:
        return
    def share(hits, of=n):
        return f"{hits}/{of} ({100 * hits / max(of, 1):.1f}%)"
    matched = [r for r in rows if r["by_number"]]
    print(f"\nproblems {n}")
    print(f"number matched an option     {share(len(matched))}")
    print(f"  correct among matched      {share(sum(r['by_number'] == r['label'] for r in matched), len(matched))}")
    print(f"letter after working         {share(sum(r['by_letter'] == r['label'] for r in rows))}")
    print(f"number, else letter          {share(sum((r['by_number'] or r['by_letter']) == r['label'] for r in rows))}")
    times = sorted(r["board_s"] for r in rows)
    print(f"board time estimate (0.8B)   mean {sum(times) / n:.0f}s  worst {times[-1]:.0f}s  "
          f"over 60s: {sum(t > 60 for t in times)}")


if __name__ == "__main__":
    main()
