# Kangaroo trainer: a math copilot on the Arduino UNO Q

A project for the Datathon FME 2026, Qualcomm challenge "Math on the Edge". It runs fully offline on an Arduino UNO Q (4 GB).

## What it does

A student picks a language, a grade, and a topic, and solves Kangaroo problems from [M3Kang](https://huggingface.co/datasets/qualcomm/M3Kang) on a web page served by the board.

- **Right answer:** the student moves one tier up and earns coins for a house in the class city.
- **Wrong answer:** the copilot never shows the answer. It names the trap behind the chosen option ("This is 120 − 70, two numbers from the problem. Is one subtraction the whole solution?") and offers an easier problem on the same topic.
- **Coach button:** the language model on the board picks the sentence of the problem the student most likely missed, and the page shows it word for word.

The same repository holds `predict.py`, which answers a Kangaroo problem with one letter for the organizers' hidden test.

> **To add before publishing:** a photo or a short video of the page and the board working.

## What we found

We spent most of our Reason time measuring what a model that fits the board can do. The short version:

- **A small model does not solve Kangaroo problems.** Qwen3.5 0.8B answers at the level of guessing, with one letter or with written working. So do four other models up to 2B, and two fine-tuned models.
- **Models that do reason (4B) need 3 to 5 minutes per problem on the board**, against a limit of 60 seconds.
- **When the small model writes a hint in its own words, about 40% of its specific hints state something false** (read by hand on 19 hints).

So the trainer does not ask the model to solve or to explain. Code checks the answer and explains the mistake, and the model only chooses where the student should look. The full evidence is in [docs/REASON_RESEARCH.md](docs/REASON_RESEARCH.md).

## Architecture

Everything runs on the board's Linux side. The laptop only prepares the data.

```
Laptop (once)                         Arduino UNO Q, Linux
---------------------                 -------------------------------------------------
laptop/prepare_m3kang.py              tools/dev_server.py  --> web page on port 7000
  M3Kang + OCR of the options           app/math-trainer/assets   the page
  -> data/train.jsonl, val.jsonl        app/math-trainer/python   the API
tools/build_map.py                    copilot/tutor.py     next problem, tiers, profile (SQLite)
  topic and tier of each problem      copilot/traps.py     trap rules, plain Python
  -> data/map.db                      copilot/coach.py     coach --> llama-server, port 8081
                                                           (Qwen3.5 0.8B, one slot)
                                      predict.py           the official run, apart from the page
```

| Part | File | Uses the model |
|---|---|---|
| Topic and tier of each problem | `copilot/topics.py`, `tools/build_map.py` | no (keywords; embeddings optional) |
| Next problem, tiers, student profile | `copilot/tutor.py` | no |
| Explanation of a wrong option | `copilot/traps.py` | no |
| Coach: which sentence to read again | `copilot/coach.py` | yes, one token |
| Class city, coins, shop | `copilot/city.py` | no |
| One letter for a problem | `predict.py`, `copilot/pipeline.py` | yes |

**How it uses M3Kang.** Every problem gets one of 8 topics and one of 3 tiers. The tier comes from the problem's position in its exam, which follows the real Kangaroo blocks of 3, 4, and 5 points. The trainer only shows problems that need no picture and whose options OCR could read.

**The LED matrix.** The page draws the matrix frames (tier, tick or cross, chosen letter) in an emulator. The App Lab app that sends them to the real matrix over the Bridge is not written yet.

## How to replicate it

Start from a board set up with steps 0 to 12 of the datathon guide: [docs/SETUP.md](docs/SETUP.md). Older notes in this repository call that guide "the README".

**1. On the laptop, prepare M3Kang.** The data is for research use only and is not part of this repository.

```bash
pip install -r laptop/requirements.txt
python3 laptop/prepare_m3kang.py --languages eng,cat
```

You should see `Wrote data/train.jsonl and data/val.jsonl` and the share of options read by OCR (about 60%).

**2. Copy the data to the board**, into the `data/` folder of the repository there (step 10 of the guide).

**3. On the board, build the problem map.**

```bash
python3 tools/build_map.py --no-embed
```

You should see `Wrote data/map.db: 3494 rows, 1747 problem ids` and a count per topic and tier.

**4. On the board, check the model and start the page.**

```bash
curl -s http://127.0.0.1:8081/health      # {"status":"ok"}; if not: sudo systemctl start math-llm
python3 tools/dev_server.py --host 0.0.0.0 --port 7000
```

Open `http://<board-ip>:7000` on a phone in the same network. [docs/BOARD_TEST.md](docs/BOARD_TEST.md) lists what to check and what to write down.

**5. The official run.**

```bash
python3 predict.py --input data/sample_problems.jsonl --output results/check.csv
python3 eval.py --limit 0 --name my-run
```

Every row of `results/check.csv` must hold one letter and the status `ok`.

To try the page with no M3Kang data: `python3 tools/dev_server.py --demo` uses problems we wrote ourselves.

## Results

All numbers below were measured on a laptop with the same models and settings as the board. **Times on the board are not measured yet.**

### Reason: accuracy of `predict.py`

On the M3Kang validation set: 562 rows, which are 281 problems in English and Catalan. One standard error is about 1.9 points.

| Run | Accuracy |
|---|---|
| Always D | 23.1% |
| Baseline: Qwen3.5 0.8B, one letter | 23.1% |
| Baseline with 1 retrieved example | 23.0% |
| Qwen3.5 2B, one letter | 24.7% |
| Option prior, no model | 27.6% |
| Gemma 3 1B after fine-tuning on answer letters | 19.2% |
| Qwen3-VL 2B on the full images, after LoRA | 22.8% |

On the organizers' demo set in the final format: 100 rows, 50 new problems in two languages, every letter correct equally often.

| Run | Accuracy |
|---|---|
| Random choice | 20% |
| Option prior, no model | 18% |
| Qwen3.5 0.8B with letter calibration: **the default of `predict.py`** | 24% |
| Qwen3.5 0.8B writes working, then the letter | 25% |

The option prior learned a pattern of M3Kang (the answer is rarely the smallest or the largest number) that the new problems do not have. That is why it is not the default. All three runs on the demo set are within the noise of guessing.

### Teach: what the student gets after a wrong answer

Measured on the trainer's problems (text only, with options), over every wrong option.

| Measure | English | Catalan |
|---|---|---|
| Problems in the trainer | 514 | 534 |
| Wrong options that a trap rule explains | 42% (856 of 2,056) | 41% (884 of 2,136) |
| Coach gives a sentence of the problem | 39 of 44 tried (the other 5 problems have one sentence) | same code |

The coach's estimated time on the board is about 15 seconds, from token counts and the board's speeds in the setup guide.

> **To add before publishing:** the coach's measured time on the board, free memory while it runs, and the latency of `predict.py` on the board.

## Error analysis

The baseline (Qwen3.5 0.8B, one letter) on the 562 validation rows:

| Group | Problems | Accuracy |
|---|---|---|
| English | 281 | 22.4% |
| Catalan | 281 | 23.8% |
| Options read by OCR | 339 | 21.5% |
| No options: the model answers blind | 223 | 25.6% |
| Level 0 (grade 5) | 40 | 32.5% |
| Level 1 | 34 | 38.2% |
| Level 2 | 58 | 37.9% |
| Level 3 | 24 | 12.5% |
| Level 4 | 124 | 23.4% |
| Level 5 | 106 | 20.8% |
| Level 6 | 98 | 11.2% |
| Level 7 | 78 | 21.8% |

- **Language makes no difference.** The model guesses equally in both.
- **Reading the options does not help the model.** It is no better with them than without.
- **The model has a letter bias.** It answered D 249 times, B 159, A 139, E 11, and C 4, while the true answers are spread over all five letters. The calibration in `copilot/debias.py` corrects this.
- **Levels 0 to 2 look better**, but with 34 to 58 problems each the difference is not reliable.

Four causes of wrong answers, from reading the model's written solutions:

1. The problem needs an idea, not a calculation. The model starts correctly and then guesses.
2. It misreads the problem and solves a different one.
3. It runs out of tokens: with 160 tokens of working, 59% of the solutions were cut before the end.
4. OCR damaged the text, or the problem needs a picture the model does not see.

When the 0.8B model computed a number, it matched one of the options 56% of the time, but the right option only 18% of the time. Kangaroo's wrong options are typical mistakes, and the model makes them.

We have no accuracy by topic yet.

## What didn't work

- **A bigger model with one letter** (2B: 24.7%).
- **Written working within the time limit**, for five models from 0.8B to 2B.
- **Retrieved examples in the prompt** (RAG): only 10 of 281 validation problems have a near copy in train.
- **Fine-tuning** Gemma 3 1B on M3Kang answer letters: it memorized train and did not improve on validation.
- **A vision model on the full images** (Qwen3-VL 2B), before and after LoRA.
- **Structured tools**: 32 verified answers on 60 problems we wrote, none on the real validation set.
- **A coach that writes its own hint.** When it knew the answer it gave it away in half of the hints. When it was told to hide it, about 40% of the specific hints stated something false.
- **The option prior on new problems**: 27.6% on M3Kang, 18% on the organizers' demo set.

What we would try next:

- Measure a 4B model on the board on short problems only, where it may fit the time limit.
- Add trap rules: they are the only part that explains a mistake, and they are silent on 58% of wrong options.
- Write the App Lab app, so the page starts with the board and the LED matrix shows the tier and the answer.
- Have a teacher read a sample of the trap messages and the coach's quotes.

## Repository

| Folder | Content |
|---|---|
| `app/math-trainer/` | The web page and its API |
| `copilot/` | The trainer, the trap rules, the coach, and the `predict.py` pipeline |
| `tools/` | The problem map, the laptop server, the model benchmark, the fitting scripts |
| `laptop/` | Data preparation: download and OCR |
| `board/` | Board setup scripts and service files |
| `docs/` | The setup guide, the plan, the research write-up, the board test |

`config.env` pins the models (repository, revision, file, SHA256) and the llama.cpp commit.

## The team

Andrey Sliva, Victor Balaniouk, Igor Pisarenko.

Team rules for branches and pull requests are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

- The starting code and the setup guide: [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq), by the organizers.
- **M3Kang**: Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218). Research use only: no M3Kang problem is part of this repository. See the [dataset card](https://huggingface.co/datasets/qualcomm/M3Kang).
- **Qwen3.5 0.8B** by the Qwen team, GGUF by bartowski. **bge-small-en-v1.5** by BAAI, GGUF by CompendiumLabs.
- **llama.cpp** by ggml-org. **three.js** for the class city (license in `app/math-trainer/assets/vendor/`).
