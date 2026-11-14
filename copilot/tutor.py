"""The Kangaroo trainer: pick the next problem, react to the student's answer.

The student picks a topic and solves problems, tier 1 to 3. A right answer
moves them one tier up. A wrong answer moves them one tier down, explains the
trap behind the chosen option (copilot/traps.py), and offers an easier problem
on the same topic. The correct answer is never shown in the feedback.

No language model in the loop, so every step is instant. Kept apart from
predict.py and copilot/pipeline.py, so the official run never changes.
Owner: coder B.

Student profiles live in SQLite (data/student.db), on the board, so progress
survives a restart and never leaves the device. A student is just a name
typed on the page: one file holds every student, one row per student and topic.

TODO(B):
- Pick the easier problem from the nearest neighbours (copilot/rag.py
  Index.search) instead of at random.
"""
import json
import os
import random
import sqlite3
import threading
import time
from contextlib import contextmanager

from .traps import explain_trap

STUDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS tiers (     -- the student's current tier on each topic
    student TEXT, topic TEXT, tier INTEGER,
    PRIMARY KEY (student, topic)
);
CREATE TABLE IF NOT EXISTS seen (      -- problems already shown, never repeated
    student TEXT, problem_id TEXT,
    PRIMARY KEY (student, problem_id)
);
CREATE TABLE IF NOT EXISTS answers (   -- every answer, for the Teach metric and the demo
    student TEXT, problem_id TEXT, topic TEXT, problem_tier INTEGER,
    letter TEXT, correct INTEGER, new_tier INTEGER, answered_at REAL
);
"""

MAX_NAME = 40


def student_name(student):
    """Normalize the name typed on the page: trimmed, lowercase, not empty."""
    name = str(student).strip().lower()
    if not name or len(name) > MAX_NAME:
        raise ValueError(f"A student name needs 1 to {MAX_NAME} characters")
    return name


class Trainer:
    """Problems come from data/map.db (topic, tier) joined with the JSONL files (text, options).

    Methods take the student's name; their profile is read from and written to student_db.
    """

    def __init__(self, map_db="data/map.db", inputs=("data/train.jsonl",), language="eng", seed=42,
                 student_db="data/student.db"):
        texts = {}
        for path in inputs:
            with open(path, encoding="utf-8") as f:
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

        self.student_db = student_db
        os.makedirs(os.path.dirname(student_db) or ".", exist_ok=True)
        # The web server may answer two students at once: one lock makes each
        # read-then-write step atomic, and each step opens its own connection.
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(STUDENT_SCHEMA)

    @contextmanager
    def _db(self):
        """One connection per step, committed at the end (rolled back on an error)."""
        with self._lock:
            db = sqlite3.connect(self.student_db)
            try:
                with db:
                    yield db
            finally:
                db.close()

    def topics(self):
        """Return {topic: number of problems}, for the topic menu."""
        counts = {}
        for p in self.problems.values():
            counts[p["topic"]] = counts.get(p["topic"], 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _tier(db, student, topic):
        row = db.execute("SELECT tier FROM tiers WHERE student = ? AND topic = ?", (student, topic)).fetchone()
        return row[0] if row else 1

    @staticmethod
    def _seen(db, student):
        return {pid for (pid,) in db.execute("SELECT problem_id FROM seen WHERE student = ?", (student,))}

    @staticmethod
    def _mark_seen(db, student, problem_id):
        db.execute("INSERT OR IGNORE INTO seen VALUES (?, ?)", (student, problem_id))

    def _pick(self, seen, topic, tier):
        pool = [p for p in self.problems.values()
                if p["topic"] == topic and p["tier"] == tier and p["id"] not in seen]
        return self.random.choice(pool) if pool else None

    def profile(self, student):
        """Return {topic: tier} for the topics the student has started, and how many problems they've seen."""
        student = student_name(student)
        with self._db() as db:
            tiers = dict(db.execute("SELECT topic, tier FROM tiers WHERE student = ? ORDER BY topic", (student,)))
            seen = db.execute("SELECT COUNT(*) FROM seen WHERE student = ?", (student,)).fetchone()[0]
        return {"student": student, "tiers": tiers, "seen": seen}

    def next_problem(self, student, topic):
        """Return the next problem for the student on this topic, or None when the topic runs out."""
        student = student_name(student)
        with self._db() as db:
            tier, seen = self._tier(db, student, topic), self._seen(db, student)
            for t in (tier, tier - 1, tier + 1, 1, 2, 3):
                if 1 <= t <= 3:
                    problem = self._pick(seen, topic, t)
                    if problem:
                        self._mark_seen(db, student, problem["id"])
                        return public(problem)
        return None

    def submit(self, student, problem_id, letter):
        """Check an answer and return the feedback for the page and the LED matrix."""
        student = student_name(student)
        problem = self.problems[problem_id]
        letter = str(letter).strip().upper()
        topic, correct = problem["topic"], letter == problem["label"]
        with self._db() as db:
            tier = self._tier(db, student, topic)
            new_tier = min(3, tier + 1) if correct else max(1, tier - 1)
            db.execute("INSERT OR REPLACE INTO tiers VALUES (?, ?, ?)", (student, topic, new_tier))
            self._mark_seen(db, student, problem_id)
            db.execute("INSERT INTO answers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (student, problem_id, topic, problem["tier"], letter, int(correct), new_tier, time.time()))
            feedback = {"correct": correct, "tier": new_tier, "trap": None, "easier_problem": None}
            if not correct:
                feedback["trap"] = explain_trap(problem, letter)
                easier = self._pick(self._seen(db, student), topic, max(1, problem["tier"] - 1))
                if easier:
                    self._mark_seen(db, student, easier["id"])
                    feedback["easier_problem"] = public(easier)
        return feedback

    def reset(self, student):
        """Forget a student: tier 1 everywhere, every problem new again. Handy before each demo run."""
        student = student_name(student)
        with self._db() as db:
            for table in ("tiers", "seen", "answers"):
                db.execute(f"DELETE FROM {table} WHERE student = ?", (student,))


def public(problem):
    """What the page may show: never the label."""
    return {k: problem[k] for k in ("id", "language", "level", "text", "options", "topic", "tier")}
