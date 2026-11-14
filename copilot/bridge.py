"""Solve a problem through its English version when the input file has one.

M3Kang gives the same problem in many languages under the same id. Qwen3.5
0.8B answers better in English (29.5% against 22.8% for Catalan on
validation), and bge-small is an English model. So when the input holds the
English version of a problem, we attach it as problem["pivot"], and the
copilot reads that instead.

The pivot uses only what the input file gives (text and options), never a
label. When the English options are empty but this language's aren't, we
keep this language's options: they are mostly numbers.

Problems with no English sibling in the input are left as they are, so the
official run works on any file.
"""
LETTERS = "ABCDE"


def add_pivots(problems, pivot_language="eng"):
    """Attach problem["pivot"] in place. Returns the number of problems that got one."""
    english = {}
    for p in problems:
        if p.get("language") == pivot_language:
            english.setdefault(p["id"], p)
    count = 0
    for p in problems:
        sibling = english.get(p["id"])
        if sibling is None or sibling is p:
            continue
        options = sibling.get("options") or p.get("options") or {}
        p["pivot"] = {"id": p["id"], "language": pivot_language, "text": sibling["text"],
                      "options": dict(options)}
        count += 1
    return count


def solvable(problem):
    """The version of the problem the copilot should read."""
    return problem.get("pivot") or problem
