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


MESSAGES = {
    "eng": {
        "off_by_one": "This is off by one. Check whether you counted both ends, or one item too many or too few.",
        "double": "This is twice too big. Is there a step where you should divide by 2?",
        "half": "This is half of what you need. Did you forget a step that doubles something?",
        "sum_all": "This is what you get by adding all the numbers in the problem. Read again what the question asks.",
        "product_all": "This is what you get by multiplying all the numbers in the problem. Is every number used that way?",
        "given": "This number is already in the problem. The answer usually needs a step of calculation.",
        "square": "This looks like a square of the right quantity. Check whether you squared a number by mistake.",
        "sum_two": "This is {a} + {b}, two numbers from the problem. Is one addition the whole solution?",
        "difference_two": "This is {a} − {b}, two numbers from the problem. Is one subtraction the whole solution?",
        "product_two": "This is {a} × {b}, two numbers from the problem. Is one multiplication the whole solution?",
        "ratio_two": "This is {a} ÷ {b}, two numbers from the problem. Is one division the whole solution?",
    },
    "cat": {
        "off_by_one": "T'has desviat d'una unitat. Comprova si has comptat els dos extrems, o un element de més o de menys.",
        "double": "És el doble del que toca. Hi ha algun pas on calgui dividir per 2?",
        "half": "És la meitat del que cal. T'has deixat algun pas que duplica alguna cosa?",
        "sum_all": "Això és el que surt si sumes tots els nombres de l'enunciat. Torna a llegir què demana la pregunta.",
        "product_all": "Això és el que surt si multipliques tots els nombres de l'enunciat. Tots s'han de fer servir així?",
        "given": "Aquest nombre ja surt a l'enunciat. La resposta normalment demana algun càlcul.",
        "square": "Sembla el quadrat de la quantitat correcta. Comprova si has elevat un nombre al quadrat per error.",
        "sum_two": "Això és {a} + {b}, dos nombres de l'enunciat. Amb una sola suma n'hi ha prou?",
        "difference_two": "Això és {a} − {b}, dos nombres de l'enunciat. Amb una sola resta n'hi ha prou?",
        "product_two": "Això és {a} × {b}, dos nombres de l'enunciat. Amb una sola multiplicació n'hi ha prou?",
        "ratio_two": "Això és {a} ÷ {b}, dos nombres de l'enunciat. Amb una sola divisió n'hi ha prou?",
    },
}
MAX_GIVEN = 8  # with more numbers in the text, a pair that gives the chosen value is likely a coincidence


def _show(value):
    """A Fraction as the student would write it: 7, 2.5, or 1/3."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):g}" if value.denominator in (2, 4, 5, 10, 20, 25, 50, 100) else str(value)


def _rules(chosen, correct, given):
    """Yield (rule, numbers) for each rule that turns the problem into the chosen value.

    Every message states a fact that code has checked, and none lets the
    student work the correct value out from the two-number rules.
    """
    if abs(chosen - correct) == 1:
        yield "off_by_one", {}
    if correct and chosen == correct * 2:
        yield "double", {}
    if correct and chosen * 2 == correct:
        yield "half", {}
    if len(given) >= 2:
        if chosen == sum(given):
            yield "sum_all", {}
        if chosen == math.prod(given):
            yield "product_all", {}
    if chosen in given:
        yield "given", {}
    if correct and chosen == correct ** 2:
        yield "square", {}
    if 2 <= len(given) <= MAX_GIVEN:
        pairs = [(a, b) for i, a in enumerate(given) for b in given[i + 1:]]
        for a, b in pairs:
            if chosen == a + b:
                yield "sum_two", {"a": _show(a), "b": _show(b)}
        for a, b in pairs:
            for big, small in ((a, b), (b, a)):
                if big > small and chosen == big - small:
                    yield "difference_two", {"a": _show(big), "b": _show(small)}
        for a, b in pairs:
            if 1 not in (a, b) and chosen == a * b:
                yield "product_two", {"a": _show(a), "b": _show(b)}
        for a, b in pairs:
            for top, bottom in ((a, b), (b, a)):
                if bottom not in (0, 1) and chosen == top / bottom:
                    yield "ratio_two", {"a": _show(top), "b": _show(bottom)}


def explain_trap(problem, letter):
    """Return a short message about the chosen wrong option, in the problem's language, or None.

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
    messages = MESSAGES.get(problem.get("language", "eng"), MESSAGES["eng"])
    for rule, numbers in _rules(chosen, correct, given):
        return messages[rule].format(**numbers)
    return None
