"""Explain the trap behind a wrong option, without giving the answer away.

Kangaroo distractors are often the result of a typical mistake: off by one,
adding instead of multiplying, forgetting to halve. When a student picks a
wrong option, explain_trap() looks for a rule that turns the problem's numbers
or the correct value into the chosen value, and names the mistake.

No model: plain Python on the numbers, so it answers instantly. Owner: coder A.
Add rules, and measure coverage with tools/eval_traps.py. Every message must
leave the correct value out.
"""
import math
import re
from fractions import Fraction

_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def number(text):
    """The first number in a text as a Fraction ("81 cm²" -> 81), or None."""
    match = _NUMBER.search(str(text))
    return Fraction(match.group(0).replace(",", ".")) if match else None


def numbers_in(text):
    return [Fraction(m.replace(",", ".")) for m in _NUMBER.findall(text)]


def _rules(chosen, correct, given):
    """Yield (message) for each rule that turns the problem into the chosen value."""
    if abs(chosen - correct) == 1:
        yield "This is off by one. Check whether you counted both ends, or one item too many or too few."
    if correct and chosen == correct * 2:
        yield "This is twice too big. Is there a step where you should divide by 2?"
    if correct and chosen * 2 == correct:
        yield "This is half of what you need. Did you forget a step that doubles something?"
    if len(given) >= 2:
        if chosen == sum(given):
            yield "This is what you get by adding all the numbers in the problem. Read again what the question asks."
        if chosen == math.prod(given):
            yield "This is what you get by multiplying all the numbers in the problem. Is every number used that way?"
    if chosen in given:
        yield "This number is already in the problem. The answer usually needs a step of calculation."
    if correct and chosen == correct ** 2:
        yield "This looks like a square of the right quantity. Check whether you squared a number by mistake."


def explain_trap(problem, letter):
    """Return a short English message about the chosen wrong option, or None.

    Returns None when the option is correct, when the options aren't numbers
    (or OCR didn't read them), or when no rule matches.
    """
    options = problem.get("options") or {}
    if letter == problem.get("label") or letter not in options or problem.get("label") not in options:
        return None
    chosen, correct = number(options[letter]), number(options[problem["label"]])
    if chosen is None or correct is None:
        return None
    given = numbers_in(problem["text"])
    # The problem number at the start of the text ("13. For 3 days...") isn't data
    if given and re.match(r"\s*\d+\.\s", problem["text"]):
        given = given[1:]
    for message in _rules(chosen, correct, given):
        return message
    return None
