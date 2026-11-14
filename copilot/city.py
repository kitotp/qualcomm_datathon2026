"""The class city: every student owns a house that grows as they solve problems.

Rewards, decided here so the page and the board agree:

- A right answer earns coins equal to the problem's tier (1 to 3).
- Floors cost more and more right answers: the 2nd floor needs 3, the 3rd 4
  more, the 4th 5 more, and so on, up to MAX_FLOORS.
- Coins buy decorations from SHOP (trees, solar panels, ...), shown on the 3D city page.
- A wrong answer costs nothing: the trainer already moves the student one tier down.

Why these numbers: M3Kang has 1,747 problems over 8 levels, about 220 per
grade, fewer with readable options, and the trainer never shows a student the
same problem twice. So one grade gives a student at most about 220 right
answers and about 440 coins (2 per answer on average). MAX_FLOORS = 15 needs
133 right answers: the top floors are for students who work through most of
their grade, and no house turns into a needle. The whole shop costs 280 coins,
so it is complete only after most of a grade too.

One SQLite file (data/city.db), one row per resident, a few hundred bytes each,
so a whole class costs the board almost nothing. The 3D drawing happens in the
browser on the laptop, never on the board. Owner: coder B.
"""
import os
import re
import sqlite3
import threading
import time
from contextlib import contextmanager

from .tutor import student_name

FIRST_FLOOR_COST = 3   # right answers for the 2nd floor; each next floor costs one more
MAX_FLOORS = 15        # see the module docstring; coins still count above it
MAX_RESIDENTS = 50     # houses per city (one class): keeps the map and the 3D scene small
DEFAULT_COLOR = "#e07a5f"

# An eco-friendly shop: plants, clean energy, and a pool. Each roof item has its
# own corner of the roof (see app/math-trainer/assets/city.js), so any mix fits.
SHOP = {
    "trees": {"price": 20, "label": "Trees"},
    "rain_tank": {"price": 25, "label": "Rainwater tank"},
    "roof_garden": {"price": 35, "label": "Roof garden"},
    "solar": {"price": 50, "label": "Solar panels"},
    "pool": {"price": 70, "label": "Swimming pool"},
    "wind": {"price": 80, "label": "Wind turbine"},
}


def answers_for(floors):
    """Right answers needed to own this many floors: 1 -> 0, 2 -> 3, 3 -> 7, 4 -> 12, ... 15 -> 133."""
    n = floors - 1
    return n * (2 * FIRST_FLOOR_COST + n - 1) // 2


def floors_for(correct):
    floors = 1
    while floors < MAX_FLOORS and answers_for(floors + 1) <= correct:
        floors += 1
    return floors

SCHEMA = """
CREATE TABLE IF NOT EXISTS residents (
    student TEXT PRIMARY KEY, color TEXT, coins INTEGER, floors INTEGER,
    correct INTEGER, answered INTEGER, items TEXT, joined_at REAL
);
"""

_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})$")


def house_color(color):
    """Normalize a color typed or picked on the page to "#rrggbb"."""
    match = _COLOR.match(str(color or "").strip())
    if not match:
        raise ValueError("A house color looks like #e07a5f")
    return "#" + match.group(1).lower()


class City:
    def __init__(self, db_path="data/city.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        """One connection per step, committed at the end, behind one lock (as in copilot/tutor.py)."""
        with self._lock:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    @staticmethod
    def _public(row):
        # Items no longer in the shop (an older version sold them) are simply not shown
        items = [i for i in (row["items"] or "").split(",") if i in SHOP]
        floors, correct = row["floors"], row["correct"]
        top = floors >= MAX_FLOORS
        return {
            "student": row["student"], "color": row["color"], "coins": row["coins"],
            "floors": floors, "max_floors": MAX_FLOORS, "correct": correct, "answered": row["answered"],
            "items": items,
            # Progress towards the next floor, for the bar on the page (None at the top)
            "next_floor_in": None if top else answers_for(floors + 1) - correct,
            "floor_step": None if top else answers_for(floors + 1) - answers_for(floors),
        }

    @staticmethod
    def _row(db, student):
        return db.execute("SELECT * FROM residents WHERE student = ?", (student,)).fetchone()

    def _ensure(self, db, student, color=None):
        row = self._row(db, student)
        if row is None:
            if db.execute("SELECT COUNT(*) FROM residents").fetchone()[0] >= MAX_RESIDENTS:
                raise ValueError(f"The city is full: {MAX_RESIDENTS} houses at most")
            db.execute("INSERT INTO residents VALUES (?, ?, 0, 1, 0, 0, '', ?)",
                       (student, house_color(color or DEFAULT_COLOR), time.time()))
        elif color:
            db.execute("UPDATE residents SET color = ? WHERE student = ?", (house_color(color), student))
        return self._row(db, student)

    def join(self, student, color=None):
        """Register a student (or log them back in), optionally repainting their house."""
        student = student_name(student)
        with self._db() as db:
            return self._public(self._ensure(db, student, color))

    def resident(self, student):
        student = student_name(student)
        with self._db() as db:
            row = self._row(db, student)
        return self._public(row) if row else None

    def residents(self):
        """Every house, in the order the students joined: the page lays out the lots in this order."""
        with self._db() as db:
            rows = db.execute("SELECT * FROM residents ORDER BY joined_at").fetchall()
        return [self._public(r) for r in rows]

    def reward(self, student, correct, tier):
        """Apply one answer: coins and maybe a new floor. Returns what changed, for the page."""
        student = student_name(student)
        with self._db() as db:
            row = self._ensure(db, student)
            coins, new_floor = 0, False
            right = row["correct"]
            floors = row["floors"]
            if correct:
                coins = max(1, min(3, int(tier or 1)))
                right += 1
                new_floor = floors_for(right) > floors
                floors = floors_for(right)
            db.execute("UPDATE residents SET coins = coins + ?, correct = ?, floors = ?, answered = answered + 1 "
                       "WHERE student = ?", (coins, right, floors, student))
            return {"coins_earned": coins, "new_floor": new_floor, "resident": self._public(self._row(db, student))}

    def buy(self, student, item):
        """Spend coins on a decoration. Raises ValueError when it can't be bought."""
        student = student_name(student)
        if item not in SHOP:
            raise ValueError(f"Unknown item: {item}")
        with self._db() as db:
            row = self._ensure(db, student)
            items = [i for i in (row["items"] or "").split(",") if i]
            if item in items:
                raise ValueError("You already have it")
            if row["coins"] < SHOP[item]["price"]:
                raise ValueError("Not enough coins yet")
            items.append(item)
            db.execute("UPDATE residents SET coins = coins - ?, items = ? WHERE student = ?",
                       (SHOP[item]["price"], ",".join(items), student))
            return self._public(self._row(db, student))

    def grant(self, student, coins):
        """Add coins by hand, for testing the shop (tools/give_coins.py). Not exposed on the web API."""
        student = student_name(student)
        with self._db() as db:
            self._ensure(db, student)
            db.execute("UPDATE residents SET coins = MAX(0, coins + ?) WHERE student = ?", (int(coins), student))
            return self._public(self._row(db, student))

    def reset(self, student):
        """Remove a student's house. Handy before each demo run."""
        student = student_name(student)
        with self._db() as db:
            db.execute("DELETE FROM residents WHERE student = ?", (student,))
