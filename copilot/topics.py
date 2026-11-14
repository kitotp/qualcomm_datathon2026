"""Topics and difficulty tiers for M3Kang problems.

M3Kang has no topic field, so we derive one. This module holds the topic list
(agreed by the team) and the rules that need no model:

- tier_of(): 1, 2 or 3 from the problem's position in its exam. Kangaroo exams
  are split into blocks of 3, 4 and 5 points, harder towards the end, and the
  position is the last part of the id ("lvl-0_2015_13" is problem 13).
- keyword_scores(): a cheap keyword vote per topic.

tools/build_map.py combines the keyword vote with embeddings and writes the
result to data/map.db. Owner: coder A. Check any change against the team's
hand labels before you trust it.
"""
import re

# Edit the descriptions to tune the embedding match: they are what each problem
# is compared with. Keep keywords lowercase; they match whole words or prefixes.
TOPICS = {
    "arithmetic": {
        "description": "Arithmetic: adding, subtracting, multiplying and dividing numbers, "
                       "fractions, percentages, money and simple word problems with quantities.",
        "keywords": ["sum", "total", "how much", "fraction", "half", "percent", "price", "cost", "euro", "coins"],
    },
    "numbers": {
        "description": "Number theory: digits, divisibility, even and odd numbers, primes, "
                       "remainders, multiples and the properties of whole numbers.",
        "keywords": ["digit", "divisible", "prime", "even", "odd", "remainder", "multiple", "integer"],
    },
    "geometry": {
        "description": "Plane geometry: shapes, triangles, squares, rectangles, circles, angles, "
                       "lengths, perimeters and areas of figures.",
        "keywords": ["triangle", "square", "rectangle", "circle", "angle", "area", "perimeter", "side", "length"],
    },
    "spatial": {
        "description": "Spatial reasoning: cubes, dice, folding paper, nets, views of solids, "
                       "mirrors, rotations and building blocks in three dimensions.",
        "keywords": ["cube", "dice", "die", "fold", "net", "mirror", "rotate", "view", "block"],
    },
    "counting": {
        "description": "Counting and combinatorics: how many ways, arrangements, paths, "
                       "choosing objects, probability and listing all the cases.",
        "keywords": ["how many ways", "different ways", "arrange", "paths", "choose", "probability", "possible"],
    },
    "logic": {
        "description": "Logic puzzles: truth-tellers and liars, ordering people by clues, "
                       "who did what, statements that are true or false, deduction.",
        "keywords": ["true", "false", "liar", "lies", "statement", "clue", "exactly one", "taller", "older"],
    },
    "patterns": {
        "description": "Patterns and sequences: rules that repeat, number sequences, "
                       "the next figure in a pattern and growing patterns.",
        "keywords": ["sequence", "pattern", "next", "repeat", "continues", "row", "position"],
    },
    "measurement": {
        "description": "Measurement: time, clocks, calendars, days of the week, speed, distance, "
                       "weight and units of measure.",
        "keywords": ["clock", "hour", "minute", "day", "week", "calendar", "speed", "km", "kg", "o'clock"],
    },
}

_QNUM = re.compile(r"_(\d+)$")


def qnum_of(problem_id):
    """Return the problem's position in its exam ("lvl-0_2015_13" -> 13), or None."""
    match = _QNUM.search(problem_id)
    return int(match.group(1)) if match else None


def exam_of(problem_id):
    """Return the exam a problem belongs to ("lvl-0_2015_13" -> "lvl-0_2015"), or None."""
    return problem_id.rsplit("_", 1)[0] if qnum_of(problem_id) else None


def tier_of(problem, exam_size):
    """Return 1, 2 or 3: the third of the exam the problem sits in, or None.

    exam_size is the number of problems in its exam. tools/build_map.py
    measures it from the data (the highest position seen per exam), so the
    tiers follow each level's real length. TODO(A): check the block
    boundaries against the Kangaroo point blocks for each level.
    """
    q = qnum_of(problem["id"])
    if not q or not exam_size:
        return None
    return min(3, 1 + (q - 1) * 3 // exam_size)


def keyword_scores(text):
    """Return {topic: number of keyword hits} for an English problem text."""
    text = text.lower()
    return {topic: sum(1 for k in spec["keywords"] if re.search(r"\b" + re.escape(k), text))
            for topic, spec in TOPICS.items()}
