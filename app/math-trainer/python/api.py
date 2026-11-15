"""The trainer's web API, shared by the laptop dev server and the App Lab app.

Every route is a GET with path parameters, the pattern the web_ui brick's
ui.expose_api() supports, so tools/dev_server.py and python/main.py serve the
same page from the same table:

    for path, handler in api.routes():
        ui.expose_api("GET", path, safe(handler))    # on the board
        # tools/dev_server.py matches the same paths on the laptop

The student picks a language and a grade once (the page remembers them), then
a topic. Each (language, grade) pair gets its own Trainer, built on first use,
so only the problems somebody actually practises sit in memory.

Handlers return dicts that become JSON. Problems never include the label.
Every handler is quick (no language model), so none needs a thread.
"""
import hmac
import sqlite3
import threading
import time

from copilot.city import MAX_FLOORS, SHOP
from copilot.coach import coach_hint
from copilot.tutor import Trainer
from matrix_frames import answer_frame, blank, question_frame

# Test mapping from school grade to M3Kang level (the README says level 0 is
# grade 5). TODO(B): check it against the Kangaroo categories with the team.
GRADE_OF_LEVEL = {level: 5 + level for level in range(8)}

LANGUAGE_NAMES = {   # code -> (name in that language, name in English)
    "eng": ("English", "English"), "cat": ("Català", "Catalan"), "esp": ("Español", "Spanish"),
    "fra": ("Français", "French"), "deu": ("Deutsch", "German"), "ita": ("Italiano", "Italian"),
    "por": ("Português", "Portuguese"), "ukr": ("Українська", "Ukrainian"), "rus": ("Русский", "Russian"),
    "pol": ("Polski", "Polish"), "nld": ("Nederlands", "Dutch"), "ron": ("Română", "Romanian"),
}


class TrainerPool:
    """One Trainer per (language, grade), created on first use and kept."""

    def __init__(self, map_db, inputs, student_db):
        self.map_db, self.inputs, self.student_db = map_db, list(inputs), student_db
        self._trainers = {}
        self._lock = threading.Lock()
        db = sqlite3.connect(map_db)
        # Same filter as Trainer: problems a student can solve from the text, with options
        self.levels = {}   # language -> sorted levels
        for language, level in db.execute(
                "SELECT DISTINCT language, level FROM problems WHERE has_options = 1 AND text_only = 1 "
                "AND tier IS NOT NULL ORDER BY language, level"):
            self.levels.setdefault(language, []).append(level)
        db.close()

    def languages(self):
        return list(self.levels)

    def grades(self, language):
        return sorted({GRADE_OF_LEVEL[lv] for lv in self.levels.get(language, []) if lv in GRADE_OF_LEVEL})

    def get(self, language, grade):
        grade = int(grade)
        if grade not in self.grades(language):
            raise ValueError("No problems for this language and grade")
        key = (language, grade)
        with self._lock:
            if key not in self._trainers:
                trainer = Trainer(self.map_db, self.inputs, language=language, student_db=self.student_db)
                levels = {lv for lv, g in GRADE_OF_LEVEL.items() if g == grade}
                trainer.problems = {pid: p for pid, p in trainer.problems.items() if p["level"] in levels}
                self._trainers[key] = trainer
            return self._trainers[key]

    def any(self):
        """A trainer for student-wide calls (profile, reset): they only touch student_db."""
        language = self.languages()[0]
        return self.get(language, self.grades(language)[0])


class TrainerAPI:
    def __init__(self, pool, city, on_frame=None, teacher_pin=None):
        """on_frame(grid) is called with every new LED matrix frame (the board sends it over the Bridge).

        teacher_pin protects "start over": only the teacher can wipe a student's
        progress. It comes from the environment, never from the repository.
        Without one, starting over is switched off.
        """
        self.teacher_pin = str(teacher_pin) if teacher_pin else None
        self.pool = pool
        self.city = city
        self.on_frame = on_frame
        self.frame = blank()

    def routes(self):
        return [
            ("/api/languages", self.languages),
            ("/api/grades/{language}", self.grades),
            ("/api/topics/{language}/{grade}", self.topics),
            ("/api/shop", self.shop),
            ("/api/city", self.city_view),
            ("/api/matrix", self.matrix),
            ("/api/join/{student}/{color}", self.join),
            ("/api/me/{student}", self.me),
            ("/api/next/{student}/{language}/{grade}/{topic}", self.next),
            ("/api/submit/{student}/{language}/{grade}/{problem_id}/{letter}", self.submit),
            ("/api/coach/{language}/{grade}/{problem_id}/{letter}", self.coach),
            ("/api/buy/{student}/{item}", self.buy),
            ("/api/reset/{student}/{pin}", self.reset),
        ]

    def _show(self, grid):
        self.frame = grid
        if self.on_frame:
            self.on_frame(grid)

    def languages(self):
        return {"languages": [{"code": code, "name": LANGUAGE_NAMES.get(code, (code, code))[0],
                               "english": LANGUAGE_NAMES.get(code, (code, code))[1]}
                              for code in self.pool.languages()]}

    def grades(self, language):
        return {"grades": self.pool.grades(language)}

    def topics(self, language, grade):
        trainer = self.pool.get(language, grade)
        return {"topics": [{"name": t, "count": n} for t, n in trainer.topics().items()]}

    def shop(self):
        return {"items": SHOP, "max_floors": MAX_FLOORS}

    def city_view(self):
        return {"residents": self.city.residents()}

    def matrix(self):
        return {"frame": self.frame}

    def join(self, student, color):
        return {"resident": self.city.join(student, color)}

    def me(self, student):
        return {"profile": self.pool.any().profile(student), "resident": self.city.resident(student)}

    def next(self, student, language, grade, topic):
        problem = self.pool.get(language, grade).next_problem(student, topic)
        if problem:
            self._show(question_frame(problem["tier"]))
        return {"problem": problem}

    def submit(self, student, language, grade, problem_id, letter):
        trainer = self.pool.get(language, grade)
        if problem_id not in trainer.problems:
            raise ValueError("Unknown problem")
        letter = str(letter).strip().upper()
        if letter not in ("A", "B", "C", "D", "E"):
            raise ValueError("Choose A to E")
        feedback = trainer.submit(student, problem_id, letter)
        reward = self.city.reward(student, feedback["correct"], trainer.problems[problem_id]["tier"])
        self._show(answer_frame(feedback["tier"], letter, feedback["correct"]))
        return {**feedback, "reward": reward, "frame": self.frame}

    def coach(self, language, grade, problem_id, letter):
        """One guiding question from the language model, after a wrong answer.

        It takes about 30 seconds on the board, so the page asks only when the
        student presses the coach button. The hint never holds the answer:
        copilot/coach.py checks it and falls back to a fixed text.
        """
        trainer = self.pool.get(language, grade)
        if problem_id not in trainer.problems:
            raise ValueError("Unknown problem")
        letter = str(letter).strip().upper()
        if letter not in ("A", "B", "C", "D", "E"):
            raise ValueError("Choose A to E")
        result = coach_hint(trainer.problems[problem_id], letter)
        return {"hint": result["hint"], "from_model": result["source"].startswith("model")}

    def buy(self, student, item):
        return {"resident": self.city.buy(student, item)}

    def reset(self, student, pin):
        if not self.teacher_pin:
            raise ValueError("Starting over is off: the teacher has to set a PIN on the server")
        if not hmac.compare_digest(str(pin).encode(), self.teacher_pin.encode()):
            time.sleep(1)   # slows down guessing a short PIN
            raise ValueError("Wrong teacher PIN")
        self.pool.any().reset(student)
        self.city.reset(student)
        self._show(blank())
        return {"ok": True}


def safe(handler):
    """Wrap a handler so a bad request becomes {"error": ...} instead of a crash."""
    def wrapped(**params):
        try:
            return handler(**params)
        except (ValueError, KeyError) as error:
            return {"error": str(error).strip("'\"")}
    return wrapped
