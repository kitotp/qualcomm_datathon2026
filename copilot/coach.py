"""The AI coach: one guiding question after a wrong answer, written by the model.

The small model can't solve Kangaroo problems (docs/REASON_RESEARCH.md), so it
is never asked to. It gets the problem, the option the student chose, and the
correct option, and writes one short question that sends the student back to
the step they got wrong. The correct answer is known from the dataset; the
model only has to talk about it without giving it away.

Code checks every hint before the student sees it: it must not name the
correct letter or contain the correct value, and it must be short. A hint
that fails gets a fixed fallback text, so the page always has something safe
to show. On the board a hint takes about 30 seconds, so the page asks for it
only when the student presses the coach button.
"""
import re
import time

from .client import post
from .config import CONFIG
from .llm import URL

LETTERS = "ABCDE"
LANGUAGES = {"eng": "English", "cat": "Catalan", "spa": "Spanish"}
SYSTEM = ("You are a kind math coach for school students. The student chose a wrong option. "
          "Do not solve the problem. Write ONE short question, at most 25 words, that points the student "
          "to the part of the problem they should read again or the step they should check. "
          "Never give an answer and never name an option letter.")
FALLBACK = {
    "eng": "Read the question again: what exactly does it ask for? Check each step of your calculation.",
    "cat": "Torna a llegir la pregunta: què demana exactament? Revisa cada pas del teu càlcul.",
    "spa": "Vuelve a leer la pregunta: ¿qué pide exactamente? Revisa cada paso de tu cálculo.",
}
MAX_TOKENS = 50
MAX_WORDS = 40
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def coach_messages(problem, letter):
    options = problem["options"]
    lines = [problem["text"].strip()] + [f"{k}) {options[k]}" for k in LETTERS if k in options]
    language = LANGUAGES.get(problem.get("language", "eng"), "English")
    # The model is not told the correct answer: it gave it away in half of the hints when it knew it
    lines.append(f"\nThe student chose {options[letter]}, and that is wrong.")
    lines.append(f"Write your one question in {language}.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def leaks(hint, problem):
    """Why the hint may not be shown, or None when it is safe."""
    correct = str(problem["options"][problem["label"]])
    if len(hint.split()) > MAX_WORDS or len(hint.split()) < 3:
        return "length"
    if not hint.rstrip().endswith("?"):
        return "not a question"
    if re.search(r"(?i)\bthe student\b|\bwhy did you (choose|pick|select)\b", hint):
        return "empty question"  # talks about the student, or only repeats their choice
    if re.search(rf"\b{problem['label']}\)", hint) or re.search(
            rf"(?i)\b(option|answer|opció|resposta|opción|respuesta)\s+{problem['label']}\b", hint):
        return "letter"
    numbers = {n.replace(",", ".") for n in NUMBER.findall(hint)}
    secret = {n.replace(",", ".") for n in NUMBER.findall(correct)}
    in_text = {n.replace(",", ".") for n in NUMBER.findall(problem["text"])}
    if secret and (secret - in_text) & numbers:  # a number of the answer that the problem itself doesn't show
        return "value"
    if not secret and len(correct) > 3 and correct.lower() in hint.lower():
        return "value"
    return None


def coach_hint(problem, letter, url=URL, timeout=50):
    """Return {"hint", "source", "seconds"}. source is "model", or "fallback" with the reason."""
    start = time.perf_counter()
    language = problem.get("language", "eng")
    result = {"hint": FALLBACK.get(language, FALLBACK["eng"]), "source": "fallback: no options"}
    if letter in (problem.get("options") or {}) and problem.get("label") in problem["options"]:
        try:
            response = post(url, {"messages": coach_messages(problem, letter), "max_tokens": MAX_TOKENS,
                                  "temperature": 0, "seed": int(CONFIG["SEED"]), "cache_prompt": True},
                            timeout=timeout)
            hint = response["choices"][0]["message"]["content"].strip().split("\n")[0].strip()
            reason = leaks(hint, problem)
            if reason:
                result["source"] = f"fallback: {reason}"
            else:
                result.update(hint=hint, source="model")
            result["tokens"] = response.get("usage", {})
        except OSError as error:  # timeouts and a server that is down
            result["source"] = f"fallback: {type(error).__name__}"
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
