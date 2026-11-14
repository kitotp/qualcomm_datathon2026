"""The Kangaroo trainer: pick the next problem, react to the student's answer.

The student picks a topic and solves problems, tier 1 to 3. A right answer
moves them one tier up. A wrong answer moves them one tier down, explains the
trap behind the chosen option (copilot/traps.py), and offers an easier problem
on the same topic. The correct answer is never shown in the feedback.

No language model in the loop, so every step is instant. Kept apart from
predict.py and copilot/pipeline.py, so the official run never changes.
Owner: coder B.

TODO(B):
- Keep the student profile in SQLite (data/student.db) instead of memory.
- Pick the easier problem from the nearest neighbours (copilot/rag.py
  Index.search) instead of at random.
"""
import json
import random
import sqlite3

from .traps import explain_trap


class Trainer:
    """Problems come from data/map.db (topic, tier) joined with the JSONL files (text, options)."""

    def __init__(self, map_db="data/map.db", inputs=("data/train.jsonl",), language="eng", seed=42):
        texts = {}
        for path in inputs:
            with open(path) as f:
                for line in f:
                    if line.strip():
                        p = json.loads(line)
                        if p["language"] == language:
                            texts[p["id"]] = p
        db = sqlite3.connect(map_db)
        # MVP: only problems a student can solve from text, with options OCR read
        rows = db.execute("SELECT id, topic, tier FROM problems WHERE language = ? AND has_options = 1 "
                          "AND text_only = 1 AND tier IS NOT NULL", (language,)).fetchall()
        db.close()
        self.problems = {}  # id -> problem dict with "topic" and "tier"
        for pid, topic, tier in rows:
            if pid in texts:
                self.problems[pid] = {**texts[pid], "topic": topic, "tier": tier}
        self.random = random.Random(seed)

    def topics(self):
        """Return {topic: number of problems}, for the topic menu."""
        counts = {}
        for p in self.problems.values():
            counts[p["topic"]] = counts.get(p["topic"], 0) + 1
        return dict(sorted(counts.items()))

    def _pick(self, student, topic, tier):
        pool = [p for p in self.problems.values()
                if p["topic"] == topic and p["tier"] == tier and p["id"] not in student["seen"]]
        return self.random.choice(pool) if pool else None

    def next_problem(self, student, topic):
        """Return the next problem for the student on this topic, or None when the topic runs out."""
        tier = student["tier"].setdefault(topic, 1)
        for t in (tier, tier - 1, tier + 1, 1, 2, 3):
            if 1 <= t <= 3:
                problem = self._pick(student, topic, t)
                if problem:
                    student["seen"].add(problem["id"])
                    return public(problem)
        return None

    def submit(self, student, problem_id, letter):
        """Check an answer and return the feedback for the page and the LED matrix."""
        problem = self.problems[problem_id]
        topic, correct = problem["topic"], letter == problem["label"]
        tier = student["tier"].setdefault(topic, 1)
        student["tier"][topic] = min(3, tier + 1) if correct else max(1, tier - 1)
        feedback = {"correct": correct, "tier": student["tier"][topic], "trap": None, "easier_problem": None}
        if not correct:
            feedback["trap"] = explain_trap(problem, letter)
            easier = self._pick(student, topic, max(1, problem["tier"] - 1))
            if easier:
                student["seen"].add(easier["id"])
                feedback["easier_problem"] = public(easier)
        return feedback


def new_student():
    return {"tier": {}, "seen": set()}


def public(problem):
    """What the page may show: never the label."""
    return {k: problem[k] for k in ("id", "language", "level", "text", "options", "topic", "tier")}
