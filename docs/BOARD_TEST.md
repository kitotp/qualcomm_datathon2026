# Test the trainer and the AI coach on the board

A first run of everything together on the Arduino UNO Q: the web page, the trap rules, and the coach that uses the language model. Nothing here has run on the board yet. The page and the coach were tested on a laptop through `tools/dev_server.py`; the coach button was not tried in a browser.

## What runs on the board

| Part | How it runs | Model |
|---|---|---|
| The trainer's web page and its API | `tools/dev_server.py`, port 7000 | none |
| The trap rules after a wrong answer | Python code, instant | none |
| The AI coach, on the coach button | the `math-llm` service, port 8081 | Qwen3.5 0.8B, the one already on the board |
| Reason (`predict.py`) | run apart from the page | none: the option prior |

One model is enough. This first test does not use App Lab, so the LED matrix stays off and the page shows its emulator. The App Lab app (`app.yaml`, `python/main.py`, `sketch.ino`) is not written yet: do it after this test passes.

## Before you start

- The board is on, set up through README steps 0 to 12, and in the same Wi-Fi network as the laptop.
- You know the board's IP address (App Lab shows it) and `ssh arduino@<ip>` works.
- Tell the team in the chat: the model has one slot, so nobody runs `eval.py` on the board during the test.

## Steps

### 1. Build the problem map on the laptop

```bash
python3 tools/build_map.py --no-embed
```

It writes `data/map.db` from `data/train.jsonl` and `data/val.jsonl`. Both stay out of Git.

### 2. Copy everything and start the page

```bash
board/deploy_trainer.sh <board-ip>
```

The script copies the code, `data/train.jsonl`, and `data/map.db` to `~/work/trainer` on the board, checks that the model answers, and starts the page. Leave that terminal open.

If it says the model is not running, on the board: `sudo systemctl start math-llm`, then `systemctl status math-llm`.

### 3. Try it as a student

Open `http://<board-ip>:7000` on a phone in the same network.

1. Choose a language, a grade, a name, a topic.
2. Answer a problem wrong on purpose.
3. Check that the trap text appears at once, when a rule matches.
4. Press the coach button, and time it with a stopwatch.
5. Repeat for five problems in English and five in Catalan.

### 4. Measure the coach without the page

In a second terminal on the laptop (use a problem ID that the page showed, from the browser's network tab, or take one from `data/map.db`):

```bash
time curl -s "http://<board-ip>:7000/api/coach/eng/6/<problem-id>/B"
```

Run it for five problems. The first call is slower, because the model reads the system prompt for the first time.

### 5. Check memory while the coach runs

On the board: `free -h`. The model, the embedding server, and the page must fit in 4 GB with room to spare.

## What to write down

| Check | Expected | If not |
|---|---|---|
| The page opens from a phone | yes | The board's firewall or `--host`; the script starts it on `0.0.0.0` |
| A wrong answer shows a trap text | in about 4 of 10 wrong answers | Rules match 42% of wrong options; the others show the general text |
| The coach answers | about 15 s, at most about 25 s (an estimate from token counts) | Write the real times down. Over 40 s: shorten the prompt, or show a "thinking" screen |
| The coach's text | "Read this part again: …" with a sentence of the problem, in the page's language | A fixed general text means the problem has one sentence, or the model timed out |
| Free memory during a coach call | several hundred MB | Stop the embedding server if the page does not need it: `sudo systemctl stop math-embed` |
| `status` of `predict.py` after the test | all `ok` | Run `python3 predict.py --input data/sample_problems.jsonl --output results/check.csv` |

Put the measured times and the memory numbers in the README and in the pitch: they are the Teach metric for "works on the board".

## After the test

- If the times are fine: write the App Lab app, so the page starts with the board and the LED matrix shows the tier and the answer.
- Stop the page with Ctrl+C in the terminal of step 2. Nothing else on the board changes: the script only writes to `~/work/trainer`.
