"""Combine the model's letter probabilities with the option prior.

copilot/debias.py reads the model's log probability for each letter and
removes its letter bias. copilot/option_prior.py scores each option from the
options alone (the smallest and largest numbers are rarely right). Each one
uses half of the evidence. Here both go into one score per letter:

    score(L) = logp(L) + bias(L) + weight * prior(L)

logp is the log softmax over the five letters, bias is a per-letter shift,
and prior is option_prior.scores(). weight and bias are fitted together on
train by tools/fit_combine.py and stored in combine.json.

It costs the same as copilot/debias.py: one forward pass. Problems without
their five options get the prior's answer, with no model call.

Turn it on with ANSWER_MODE=combined in config.env.
"""
import json
import math
import os

from . import option_prior
from .debias import ask_letter_logprobs
from .llm import URL, build_messages

LETTERS = "ABCDE"
WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combine.json")

_fit = None


def load_fit():
    global _fit
    if _fit is None:
        with open(WEIGHTS_PATH) as f:
            _fit = json.load(f)
    return _fit


def normalize(lp):
    """Log softmax over the five letters."""
    m = max(lp.values())
    z = m + math.log(sum(math.exp(v - m) for v in lp.values()))
    return {k: v - z for k, v in lp.items()}


def has_options(problem):
    return set(problem.get("options") or {}) == set(LETTERS)


def scores(problem, letter_logprobs, weight, bias):
    """One score per letter; the highest wins."""
    lp = normalize(letter_logprobs)
    prior = option_prior.scores(problem)
    return {k: lp[k] + bias.get(k, 0.0) + weight * prior[k] for k in LETTERS}


def pick(problem, letter_logprobs, weight, bias):
    sc = scores(problem, letter_logprobs, weight, bias)
    return max(LETTERS, key=lambda k: (sc[k], -ord(k)))


def combined_letter(problem, examples=(), timeout=60, url=URL):
    """Return (letter, timings). timings is {} when no model call was needed."""
    if not has_options(problem):
        return option_prior.pick(problem), {}
    fit = load_fit()
    lp, timings = ask_letter_logprobs(build_messages(problem, examples), timeout, url)
    return pick(problem, lp, fit["weight"], fit["bias"]), timings
