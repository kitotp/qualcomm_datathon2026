"""Frames for the board's 8x13 LED matrix, as plain lists of brightness values 0 to 7.

No numpy here, so the laptop dev server can draw the same frames in its
emulator. On the board, main.py turns a frame into bytes with
Frame(np.array(grid, dtype=np.uint8)).to_board_bytes().

Layout of the answer frame (13 columns):

    cols 0-1   tier bar, filled from the bottom (tier 1, 2, 3)
    cols 3-7   the chosen letter, 5x7
    cols 9-12  a tick or a cross, 4x4
"""
ROWS, COLS = 8, 13

FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
}
TICK = ["...#", "..#.", "#.#.", ".#.."]
CROSS = ["#..#", ".##.", ".##.", "#..#"]
TIER_ROWS = {1: 3, 2: 5, 3: 8}


def blank():
    return [[0] * COLS for _ in range(ROWS)]


def _stamp(grid, pattern, top, left, value):
    for r, line in enumerate(pattern):
        for c, pixel in enumerate(line):
            if pixel == "#":
                grid[top + r][left + c] = value


def answer_frame(tier, letter, correct):
    """Tier bar, chosen letter, tick or cross."""
    grid = blank()
    for r in range(ROWS - TIER_ROWS.get(tier, 0), ROWS):
        grid[r][0] = grid[r][1] = 4
    _stamp(grid, FONT.get(str(letter).upper(), FONT["?"]), 0, 3, 7)
    _stamp(grid, TICK if correct else CROSS, 2, 9, 7)
    return grid


def question_frame(tier):
    """Waiting for an answer: tier bar and a question mark."""
    grid = blank()
    for r in range(ROWS - TIER_ROWS.get(tier, 0), ROWS):
        grid[r][0] = grid[r][1] = 4
    _stamp(grid, FONT["?"], 0, 6, 7)
    return grid
