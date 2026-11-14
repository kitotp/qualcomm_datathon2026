# Team plan: the Kangaroo trainer

24 hours, one Arduino UNO Q, two people who code (A and B) and one who doesn't (C). About 70% of our effort goes to the **Teach** track, where originality scores, and about 30% to **Reason**, because every team's `predict.py` is scored on the hidden test set. Team rules for branches and pushes are in [CONTRIBUTING.md](../CONTRIBUTING.md).

## What we build

**A Kangaroo trainer with a trap detector.** We map every M3Kang problem to a **topic** (arithmetic, geometry, counting, …) and to one of **3 tiers**, taken from the real Kangaroo point blocks: the problem's position in its exam, the last part of its id (`lvl-0_2015_13` is problem 13).

The student picks a topic and solves problems:

- **Right answer:** one tier up.
- **Wrong answer:** the copilot doesn't show the answer. It names the trap behind the chosen option ("this is twice too big: is there a step where you should divide by 2?"), offers an easier problem on the same topic, and moves one tier down.
- The LED matrix shows the tier (1 to 3), a tick or a cross, and the chosen letter.

There's no language model in the loop, so every step takes well under a second.

**One-line pitch:** we mapped M3Kang by topic and Kangaroo tier, and our copilot doesn't give the answer: it tells you which trap you fell into.

## Definition of done

1. **A live demo on the board, Wi-Fi off:** a web page on port 7000 to pick a topic and solve problems, with the trap explanation and an easier problem after a mistake, and the LED matrix showing tier, tick or cross, and letter.
2. **The M3Kang map:** topic and tier for every problem, with topic accuracy checked against 30 hand labels (a number such as 25/30).
3. **The trap detector:** coverage (the share of wrong options a rule explains) and quality (20 explanations judged by hand).
4. **`predict.py` above the 22.5% baseline** on the same 50 problems, confirmed on the whole validation set (`--limit 0`), every run logged in `results/ablations.csv`.
5. **Error analysis** by topic, language, and level, with the number of problems next to each accuracy, and 10 wrong answers explained.
6. **A public repository with a README, an Arduino Project Hub write-up** (the M3Kang check from the `publish-project` skill passes), **a 3-minute pitch**, and **a backup video** of the demo.
7. Stretch: **"Teach the AI"**: 10 to 15 precomputed wrong solutions by the model, where the student finds the mistake.

## Who does what

### A: data and reasoning (map, traps, Reason)

| # | Task | Files | Branch |
| --- | --- | --- | --- |
| A1 | Topic list, `tier_of()`; check the tier boundaries against the real Kangaroo point blocks per level | `copilot/topics.py` | `feature/problem-map` |
| A2 | The map: embeddings of the English version, nearest topic description plus keyword bonus, copied to every language by id → `data/map.db` | `tools/build_map.py` | `feature/problem-map` |
| A3 | Trap rules in `explain_trap()`, and a coverage script | `copilot/traps.py`, `tools/eval_traps.py` | `feature/traps` |
| A4 | Reason: fix the letter bias (`logprobs` and the letter prior from train), then RAG with a similarity threshold. One change per run: `eval.py --limit 50 --name …`, then commit | `copilot/llm.py`, `copilot/pipeline.py` | `experiment/letter-debias`, `experiment/rag-threshold` |
| A5 | Error report: `results/eval-*.csv` joined with `data/map.db` → tables by topic, language, level | `tools/error_report.py` | `feature/error-report` |
| A6 | Stretch: precompute the model's wrong solutions for the demo | `tools/precompute_wrong.py` | `feature/teach-the-ai` |

### B: the product (trainer, app, LED matrix)

| # | Task | Files | Branch |
| --- | --- | --- | --- |
| B1 | Trainer logic: student profile in SQLite (`data/student.db`), easier problem from the nearest neighbours (`copilot/rag.py` `Index.search`) | `copilot/tutor.py` | `feature/tutor` |
| B2 | Web page prototype on the laptop, a standard-library server like `explorer/server.py` | `app/math-trainer/assets/`, `tools/dev_server.py` | `ui/web-page` |
| B3 | App Lab app from the `unoq-hardware-ui` skill's template. **First**, check that the app reaches `127.0.0.1:8081` and `8082` and can read `copilot/` and `data/map.db`; if not, copy them into `python/` with a deploy script | `app/math-trainer/` | `ui/app-lab` |
| B4 | LED matrix: tier bars, tick or cross, letter, "thinking" | `app/math-trainer/python/main.py` | `ui/app-lab` |
| B5 | Teach metric: simulated students (for example, always right below tier 2): where the tier settles, time per step | `tools/simulate_students.py` | `feature/tutor` |

### C: quality and story (no code)

| # | Task | Time |
| --- | --- | --- |
| C1 | Agree the topic list (6 to 8 topics with short descriptions) in the first hour; A puts it in `copilot/topics.py` | 30 min |
| C2 | Hand-label the topics of 30 problems in the explorer on the laptop, in a sheet of `id → topic` (no problem text). This is the reference that checks the map | 40 min |
| C3 | Judge 20 trap explanations: correct? clear? | 1 h |
| C4 | Explain 10 wrong answers by the model, one sentence each, in the explorer | 1 h |
| C5 | Test the trainer as a student; choose the demo problems | ongoing |
| C6 | README and Project Hub write-up with Claude and the `publish-project` skill; photos, screenshots, architecture diagram | 3–4 h |
| C7 | Pitch script (20 s problem, 90 s demo, 40 s numbers, 30 s lessons), slides, rehearsals, backup video | 3 h |

## Interfaces between A and B

These are in the repository already as starting code. Change them only with a heads-up in the team chat.

- `copilot/topics.py`: `TOPICS` (description and keywords per topic), `qnum_of(id)`, `tier_of(problem, exam_size) -> 1 | 2 | 3 | None`, `keyword_scores(text)`.
- `data/map.db`, table `problems(id, language, level, year, qnum, tier, topic, topic_score, has_options, text_only)`, built by `tools/build_map.py`.
- `copilot/traps.py`: `explain_trap(problem, letter) -> str | None`. Never includes the correct value.
- `copilot/tutor.py`: `Trainer(map_db, inputs).topics()`, `.next_problem(student, topic)`, `.submit(student, problem_id, letter) -> {correct, tier, trap, easier_problem}`. Problems sent to the page never include the label.
- For the MVP, the trainer only uses problems with options OCR read and `text_only` true, so no image is needed.
- The trainer never touches `predict.py` or `copilot/pipeline.py`.

## Schedule

| Hours | A | B | C | Board |
| --- | --- | --- | --- | --- |
| 0–2 | Everyone: board steps 0–12, baseline, index. Agree topics and interfaces | | | everyone |
| 2–8 | A1–A3 | B1–B2 on the laptop | C1–C2 on the laptop | A builds the map (minutes) |
| 8–14 | A4, topics vs. hand labels, trap coverage | B3–B4 on the board | C3, start C6 | **Book it:** A's eval runs and B's app tests never at the same time |
| 14–20 | Full validation run (`--limit 0`, ~45 min), A5, A6 | Integration, B5, demo problems with C | C4, C5, C6 | Nothing else during the full run |
| 20–24 | **Feature freeze.** Everyone: rehearse with Wi-Fi off, record the video, finish README and Project Hub, run the M3Kang check, publish | | | demo |

**Board rules:** the language model has one slot, so two requests at once ruin the latency numbers. Say so in the team chat before an eval run or a service restart. Each person works in their own clone, `~/work/<name>/`.

## Checks

- After every change: `python3 predict.py --input data/sample_problems.jsonl --output results/check.csv`, and every row has a letter.
- `python3 tools/build_map.py --no-embed` works without the model servers, for a quick test on the laptop.
- Before every push: `git status`, and no `data/*.jsonl` or `*.db` in `git ls-files`.
