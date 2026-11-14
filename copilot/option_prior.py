"""Pick a letter from the options alone, with no language model.

Kangaroo options carry information of their own. When the five options are
numbers, the smallest and the largest are rarely the answer (about 10% each
on train), and the middle one is the answer about 30% of the time. A number
that already appears in the problem text is less often the answer.

Each option gets a score, the sum of the weights of its features, and the
best score wins. The weights are fitted on train by
tools/fit_option_prior.py and stored in option_prior.json. This runs in
well under a millisecond, so it costs nothing against the time limit.
"""
import json
import os
import re

LETTERS = "ABCDE"
WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "option_prior.json")

UNIT = r"\s*(?:cm|mm|km|m|kg|g|€|euros?|%|°|min|h|s)?\.?\s*"
NUMBER = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)" + UNIT + r"$", re.I)
IN_TEXT = re.compile(r"\d+(?:[.,]\d+)?")

_weights = None


def value(text):
    """'12', '12 cm', '3,5' -> float; anything else -> None."""
    m = NUMBER.match(str(text))
    return float(m.group(1).replace(",", ".")) if m else None


def numeric_options(problem):
    """The five options as numbers, or None when any of them is not a plain number."""
    options = problem.get("options") or {}
    if set(options) != set(LETTERS):
        return None
    values = {k: value(v) for k, v in options.items()}
    return values if all(v is not None for v in values.values()) else None


def features(problem):
    """The names of the features that are on, for each letter."""
    group = "options" if problem.get("options") else "no-options"
    on = {k: [f"letter:{group}:{k}"] for k in LETTERS}
    values = numeric_options(problem)
    if values:
        by_size = sorted(LETTERS, key=lambda k: (values[k], k))
        in_text = {float(x.replace(",", ".")) for x in IN_TEXT.findall(problem.get("text", ""))}
        for k in LETTERS:
            on[k].append(f"rank:{by_size.index(k)}")
            if values[k] in in_text:
                on[k].append("in-text")
    return on


def scores(problem, weights=None):
    """A score per letter; higher is more likely. Add model scores to these to combine both."""
    weights = load_weights() if weights is None else weights
    return {k: sum(weights.get(name, 0.0) for name in names) for k, names in features(problem).items()}


def pick(problem, weights=None):
    sc = scores(problem, weights)
    return max(LETTERS, key=lambda k: sc[k])


def load_weights():
    global _weights
    if _weights is None:
        with open(WEIGHTS_PATH) as f:
            _weights = json.load(f)["weights"]
    return _weights
