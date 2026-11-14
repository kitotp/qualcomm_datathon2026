"""Pick the letter from the model's letter probabilities, minus its letter bias.

Qwen3.5 0.8B has a strong taste for some letters: with the [A-E] grammar it
answers D or B most of the time and almost never C or E. Here we:

1. start the assistant turn with PREFILL, so the next token is the letter, and
   read the log probability of each letter A to E (one forward pass, a few
   tokens more than the baseline prompt);
2. add a per-letter bias fitted on train (tools/fit_letter_bias.py), chosen so
   that the predicted letters are as frequent as the true ones;
3. take the best letter.

Problems without OCR options get the most common train answer for such
problems, with no model call: the model can't see the options, and on
validation it did no better than that constant.

The numbers live in copilot/letter_bias.json. Refit them when the data changes:
    python3 tools/collect_letter_probs.py ...   # see that script
    python3 tools/fit_letter_bias.py --save copilot/letter_bias.json
"""
import json
import os

from .client import post
from .config import CONFIG
from .llm import URL, build_messages

LETTERS = "ABCDE"
PREFILL = "The correct option is"
MISSING = -30.0  # a letter that didn't make the top list
TOP_N = 40
BIAS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letter_bias.json")

_bias = None


def bias():
    global _bias
    if _bias is None:
        with open(BIAS_PATH) as f:
            _bias = json.load(f)
    return _bias


def letter_logprobs(top):
    """Map a top_logprobs list to {letter: logprob}, tokens like " B" or "**C" included."""
    out = {}
    for t in top:
        key = t["token"].strip().strip("*(")
        if key in LETTERS and len(key) == 1:
            out[key] = max(out.get(key, MISSING), t["logprob"])
    return {k: out.get(k, MISSING) for k in LETTERS}


def ask_letter_logprobs(messages, timeout, url=URL, top_n=TOP_N):
    """One forward pass after PREFILL. Returns ({letter: logprob}, timings)."""
    response = post(url, {
        "messages": messages + [{"role": "assistant", "content": PREFILL}],
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "logprobs": True,
        "top_logprobs": top_n,
        "cache_prompt": True,
    }, timeout=timeout)
    top = response["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    return letter_logprobs(top), response.get("timings", {})


def debiased_letter(problem, examples=(), timeout=60, url=URL):
    """Return (letter, timings). timings is {} when no model call was needed."""
    b = bias()
    if not problem.get("options"):
        return b["constant_without_options"], {}
    scores, timings = ask_letter_logprobs(build_messages(problem, examples), timeout, url)
    shift = b["prior_with_options"]
    letter = max(LETTERS, key=lambda k: (scores[k] + shift.get(k, 0.0), -ord(k)))
    return letter, timings
