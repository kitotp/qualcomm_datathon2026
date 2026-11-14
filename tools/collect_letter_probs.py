#!/usr/bin/env python3
"""Record the model's log probability for each letter A to E, for every problem.

The letter-debias experiments fit a few numbers on train and test them on val.
Asking the model is the slow part, so this script does it once and caches the
result; the fitting (tools/fit_letter_bias.py) then runs in seconds, offline.

Two ways to read the letter distribution, both one forward pass:

- "wide": the baseline prompt, with top_logprobs over the first token. The
  server reports log probabilities before the [A-E] grammar, so the letters
  sit deep in the tail behind tokens like "To" and "Let".
- "prefill": the assistant turn starts with copilot.debias.PREFILL, so the
  next token is the letter itself (" A" ... " E"). This is exactly the
  request the copilot makes at run time.

Writes one JSON line per problem, ids and numbers only, never problem text:
    {"id", "language", "level", "has_options", "label", "wide": {A..E}, "prefill": {A..E}}

    python3 tools/collect_letter_probs.py --input data/train.jsonl --output results/letters-train.jsonl
    python3 tools/collect_letter_probs.py --input data/val.jsonl --output results/letters-val.jsonl --port 8091
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.client import post  # noqa: E402
from copilot.config import CONFIG  # noqa: E402
from copilot.debias import ask_letter_logprobs, letter_logprobs  # noqa: E402
from copilot.llm import build_messages  # noqa: E402


def ask_wide(url, messages, top_n=400):
    r = post(url, {"messages": messages, "max_tokens": 1, "temperature": 0,
                   "seed": int(CONFIG["SEED"]), "logprobs": True, "top_logprobs": top_n,
                   "cache_prompt": True}, timeout=120)
    return letter_logprobs(r["choices"][0]["logprobs"]["content"][0]["top_logprobs"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--port", type=int, default=int(CONFIG["LLM_PORT"]))
    args = p.parse_args()
    url = f"http://127.0.0.1:{args.port}/v1/chat/completions"

    done = set()
    if os.path.exists(args.output):  # resume
        with open(args.output) as f:
            done = {(r["id"], r["language"]) for r in map(json.loads, f)}
    with open(args.input) as f:
        problems = [json.loads(line) for line in f if line.strip()]
    todo = [x for x in problems if (x["id"], x["language"]) not in done]
    print(f"{len(todo)} to do, {len(done)} cached", flush=True)

    start = time.time()
    with open(args.output, "a") as out:
        for i, prob in enumerate(todo, 1):
            messages = build_messages(prob)
            row = {"id": prob["id"], "language": prob["language"], "level": prob["level"],
                   "has_options": bool(prob.get("options")), "label": prob["label"],
                   "wide": ask_wide(url, messages),
                   "prefill": ask_letter_logprobs(messages, timeout=120, url=url)[0]}
            out.write(json.dumps(row) + "\n")
            if i % 100 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}, {i / (time.time() - start):.1f}/s", flush=True)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
