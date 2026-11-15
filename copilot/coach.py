"""The AI coach: after a wrong answer, point the student at the condition they missed.

The small model can't solve Kangaroo problems (docs/REASON_RESEARCH.md), and
when it writes a hint in its own words it states false things in about 40% of
the hints that sound specific (read by hand on 19 English hints). So it does
not write. Code splits the problem into its sentences, and the model, which
is told the correct answer and the student's choice, only picks the number of
the sentence the student most likely missed. Code then shows that sentence,
word for word, inside a fixed text.

So a hint can't say anything false and can't give the answer away: it holds
only the problem's own words. It reads the same in every language, because
the fixed text is translated here and the quote is in the problem's language.
On the board the model reads the problem and writes one token.
"""
import re
import time

from .client import post
from .config import CONFIG
from .llm import URL

LETTERS = "ABCDE"
SYSTEM = ("You help a math coach for school students. You get a problem split into numbered parts, the correct "
          "answer, and the wrong answer a student chose. Reply with the number of the part that the student "
          "most likely missed or misused.")
TEMPLATE = {
    "eng": "Read this part again: “{quote}” Did you use it?",
    "cat": "Torna a llegir aquesta part: “{quote}” L'has tinguda en compte?",
    "spa": "Vuelve a leer esta parte: “{quote}” ¿La has tenido en cuenta?",
}
FALLBACK = {
    "eng": "Read the question again: what exactly does it ask for? Check each step of your calculation.",
    "cat": "Torna a llegir la pregunta: què demana exactament? Revisa cada pas del teu càlcul.",
    "spa": "Vuelve a leer la pregunta: ¿qué pide exactamente? Revisa cada paso de tu cálculo.",
}
NUMBERING = re.compile(r"^\s*\d{1,2}\s*[.)]\s+")           # "17. " in front of the problem
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[^\s\d])")     # not after "4." in "4. 5 km"
MIN_WORDS, MAX_PARTS = 4, 9


def parts_of(text):
    """The problem's sentences, without its number. Short fragments join the sentence before them."""
    parts = []
    for piece in SENTENCE_END.split(NUMBERING.sub("", " ".join(text.split()))):
        piece = piece.strip()
        if parts and len(piece.split()) < MIN_WORDS:
            parts[-1] += " " + piece
        elif piece:
            parts.append(piece)
    return parts[:MAX_PARTS]


def coach_messages(problem, letter, parts):
    options = problem["options"]
    lines = [f"{n}. {part}" for n, part in enumerate(parts, 1)]
    lines.append(f"\nCorrect answer: {options[problem['label']]}")
    lines.append(f"The student chose: {options[letter]}")
    lines.append("Which part did the student most likely miss? Reply with its number.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def coach_hint(problem, letter, url=URL, timeout=50):
    """Return {"hint", "source", "seconds"}. source is "model", or "fallback" with the reason."""
    start = time.perf_counter()
    language = problem.get("language", "eng")
    result = {"hint": FALLBACK.get(language, FALLBACK["eng"]), "source": "fallback: no options"}
    options = problem.get("options") or {}
    if letter in options and problem.get("label") in options:
        parts = parts_of(problem["text"])
        if len(parts) < 2:
            result["source"] = "fallback: one sentence"
        else:
            try:
                response = post(url, {
                    "messages": coach_messages(problem, letter, parts),
                    "grammar": f"root ::= [1-{len(parts)}]", "max_tokens": 1,
                    "temperature": 0, "seed": int(CONFIG["SEED"]), "cache_prompt": True}, timeout=timeout)
                picked = int(response["choices"][0]["message"]["content"].strip())
                template = TEMPLATE.get(language, TEMPLATE["eng"])
                result.update(hint=template.format(quote=parts[picked - 1]), source="model", part=picked,
                              parts=len(parts), tokens=response.get("usage", {}))
            except (OSError, ValueError) as error:  # timeouts, a server that is down, no number
                result["source"] = f"fallback: {type(error).__name__}"
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
