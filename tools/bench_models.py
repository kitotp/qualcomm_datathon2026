#!/usr/bin/env python3
"""Compare language models on val: accuracy, tokens, and time on the board.

For each model it downloads the GGUF, measures how fast the laptop CPU reads
and writes with it, and then answers the val problems that have options in
two modes:

  letter  one letter with no working (the baseline prompt)
  think   working that fills the board's time budget, then the letter
  free    working of up to 300 tokens with no time limit: what the model
          could do if the board were faster (acc_no_limit in the table)

The laptop is much faster than the board, so time is not measured here: it
is estimated. The 0.8B model's speeds on the board are known (README step 6:
reads 11.3 tokens per second, writes 5.9). The laptop measures every model
the same way, and the ratio between a model and the 0.8B model on the laptop
is applied to the board's numbers. Bigger models are likely slower on the
board than this estimate, because the board has less memory bandwidth, so
confirm the winner on the board.

    python3 tools/bench_models.py --models qwen35-0.8b,qwen35-2b --gpu
    python3 tools/bench_models.py --report            # print the leaderboard again

Results go to results/bench/: one JSON line per problem and per mode (no
problem text), speeds.json, and leaderboard.csv.
"""
import argparse
import concurrent.futures
import csv
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from copilot import option_prior  # noqa: E402
from copilot.client import post  # noqa: E402
from copilot.config import CONFIG  # noqa: E402
from copilot.llm import build_messages  # noqa: E402
import solve_match  # noqa: E402

LETTERS = "ABCDE"
OUT = os.path.join(ROOT, "results", "bench")
MODELS_DIR = os.path.expanduser(CONFIG["MODELS_DIR"])
SERVER = os.path.join(os.path.expanduser(CONFIG["LLAMA_CPP_DIR"]), "build", "bin", "llama-server")
REFERENCE = "qwen35-0.8b"                    # the model whose board speeds are known
BOARD_READ, BOARD_WRITE = 11.3, 5.9          # tokens per second for the reference on the board
FREE_SAMPLE, FREE_TOKENS = 80, 300           # the "free" mode: problems, and tokens of working
TIME_LIMIT = 57.0                            # 60 s minus the margin that pipeline.py keeps

MODELS = {  # alias: (Hugging Face repository, file)
    "qwen35-0.8b": ("bartowski/Qwen_Qwen3.5-0.8B-GGUF", "Qwen_Qwen3.5-0.8B-Q8_0.gguf"),
    "qwen35-2b": ("bartowski/Qwen_Qwen3.5-2B-GGUF", "Qwen_Qwen3.5-2B-Q4_K_M.gguf"),
    "qwen35-4b": ("bartowski/Qwen_Qwen3.5-4B-GGUF", "Qwen_Qwen3.5-4B-Q4_K_M.gguf"),
    "gemma3-1b": ("bartowski/google_gemma-3-1b-it-GGUF", "google_gemma-3-1b-it-Q8_0.gguf"),
    "gemma3-4b": ("bartowski/google_gemma-3-4b-it-GGUF", "google_gemma-3-4b-it-Q4_K_M.gguf"),
    "lfm2-1.2b": ("LiquidAI/LFM2-1.2B-GGUF", "LFM2-1.2B-Q8_0.gguf"),
    "qwen25-math-1.5b": ("bartowski/Qwen2.5-Math-1.5B-Instruct-GGUF", "Qwen2.5-Math-1.5B-Instruct-Q8_0.gguf"),
    "qwen3-1.7b": ("bartowski/Qwen_Qwen3-1.7B-GGUF", "Qwen_Qwen3-1.7B-Q6_K.gguf"),
    "smollm3-3b": ("bartowski/HuggingFaceTB_SmolLM3-3B-GGUF", "HuggingFaceTB_SmolLM3-3B-Q4_K_M.gguf"),
    "phi4-mini": ("bartowski/microsoft_Phi-4-mini-instruct-GGUF", "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf"),
}

# Neutral text of about 300 tokens for the speed probe (not from M3Kang)
PROBE = ("A school library keeps its books on shelves. Each shelf holds a fixed number of books, "
         "and the librarian counts them every week. " * 12 +
         "Describe in detail how the librarian could organize the count.")


LOCAL = {}  # alias: path, for models given as name=/path/to/file.gguf


def download(alias):
    if alias in LOCAL:
        return LOCAL[alias]
    repo, name = MODELS[alias]
    path = os.path.join(MODELS_DIR, name)
    if not os.path.exists(path):
        print(f"[{alias}] downloading {name}", file=sys.stderr)
        subprocess.run(["curl", "-sL", "--fail", "-o", path + ".part",
                        f"https://huggingface.co/{repo}/resolve/main/{name}"], check=True)
        os.rename(path + ".part", path)
    return path


class Server:
    """llama-server for one model. gpu=False matches the board (CPU, 4 threads)."""

    def __init__(self, path, port, gpu, jobs=1):
        self.base = f"http://127.0.0.1:{port}"
        self.log = open(os.path.join(OUT, "server.log"), "w")
        self.proc = subprocess.Popen(
            [SERVER, "-m", path, "--host", "127.0.0.1", "--port", str(port), "--threads", "4",
             "--ctx-size", str(4096 * jobs), "--parallel", str(jobs), "--cache-ram", "0",
             "--ctx-checkpoints", "2",
             "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
             "--n-gpu-layers", "99" if gpu else "0"],
            stdout=self.log, stderr=subprocess.STDOUT)

    def __enter__(self):
        for _ in range(180):
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server stopped: see results/bench/server.log")
            try:
                with urllib.request.urlopen(self.base + "/health", timeout=2) as r:
                    if json.load(r).get("status") == "ok":
                        return self
            except OSError:
                pass
            time.sleep(1)
        raise RuntimeError("llama-server did not start")

    def __exit__(self, *_):
        self.proc.terminate()
        self.proc.wait()
        self.log.close()


def probe_speed(base):
    """Tokens per second that this machine reads and writes, on a prompt with nothing cached."""
    best = None
    for i in range(2):  # the first run also loads the model into memory
        r = post(base + "/v1/chat/completions", {
            "messages": [{"role": "user", "content": f"Note {i}. {PROBE}"}],
            "max_tokens": 48, "temperature": 0, "cache_prompt": False}, timeout=600)
        best = r["timings"]
    return best["prompt_per_second"], best["predicted_per_second"]


def load_speeds():
    path = os.path.join(OUT, "speeds.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def board_speeds(alias, speeds):
    """Estimated (read, write) tokens per second on the board for this model."""
    ref, own = speeds[REFERENCE], speeds[alias]
    return (BOARD_READ * own["laptop_read"] / ref["laptop_read"],
            BOARD_WRITE * own["laptop_write"] / ref["laptop_write"])


def for_each(problems, answer, out, jobs, label):
    """Answer the problems, several at a time, and write one row each."""
    lock, done = threading.Lock(), [0]

    def one(pr):
        row = {"id": pr["id"], "language": pr.get("language", ""), "label": pr["label"], **answer(pr)}
        with lock:
            out.write(json.dumps(row) + "\n")
            out.flush()
            done[0] += 1
            if done[0] % 50 == 0:
                print(f"  {label} {done[0]}/{len(problems)}", file=sys.stderr)

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        list(pool.map(one, problems))


def letter_answer(base, read, write):
    def answer(pr):
        r = post(base + "/v1/chat/completions", {
            "messages": build_messages(pr), "grammar": "root ::= [A-E]", "max_tokens": 1,
            "temperature": 0, "seed": int(CONFIG["SEED"]), "cache_prompt": True}, timeout=600)
        tokens = r["usage"]["prompt_tokens"]
        return {"answer": r["choices"][0]["message"]["content"].strip(), "prompt_tokens": tokens,
                "written_tokens": 1, "board_s": round(tokens / read + 1 / write, 1)}
    return answer


def think_answer(base, read, write, max_tokens, budget):
    def answer(pr):
        result, _working = solve_match.solve(pr, base, max_tokens, budget, read=read, write=write)
        return {"answer": result["by_letter"], "by_number": result["by_number"],
                "prompt_tokens": result["prompt_tokens"], "written_tokens": result["written_tokens"],
                "working_limit": result["working_limit"], "board_s": result["board_s"]}
    return answer


def bench(alias, args, with_options, sample):
    os.makedirs(OUT, exist_ok=True)
    path = download(alias)
    speeds = load_speeds()
    for name in dict.fromkeys([REFERENCE, alias]):  # the reference first, once
        if name not in speeds:
            with Server(download(name), args.port, gpu=False) as server:
                read, write = probe_speed(server.base)
            speeds[name] = {"laptop_read": round(read, 1), "laptop_write": round(write, 1),
                            "file_gb": round(os.path.getsize(download(name)) / 2 ** 30, 2)}
            with open(os.path.join(OUT, "speeds.json"), "w") as f:
                json.dump(speeds, f, indent=1)
    read, write = board_speeds(alias, speeds)
    print(f"[{alias}] board estimate: reads {read:.1f} tok/s, writes {write:.1f} tok/s", file=sys.stderr)
    with Server(path, args.port, gpu=args.gpu, jobs=args.jobs) as server:
        for mode in args.modes.split(","):
            with open(os.path.join(OUT, f"{alias}-{mode}.jsonl"), "w") as out:
                if mode == "letter":
                    for_each(with_options, letter_answer(server.base, read, write), out, args.jobs, mode)
                elif mode == "think":
                    for_each(sample, think_answer(server.base, read, write, args.max_tokens, True),
                             out, args.jobs, mode)
                else:  # free: what the model could do with no time limit
                    for_each(sample[:FREE_SAMPLE], think_answer(server.base, read, write, FREE_TOKENS, False),
                             out, args.jobs, mode)
    if not args.keep and alias != REFERENCE and alias not in LOCAL:
        os.remove(path)


def summarize(val):
    """One leaderboard row per model and mode, from the files in results/bench/."""
    by_key = {(p["id"], p.get("language", "")): p for p in val}
    with_options = [p for p in val if set(p.get("options") or {}) == set(LETTERS)]
    prior_all = sum(option_prior.pick(p) == p["label"] for p in val)
    speeds = load_speeds()
    table = []
    for name in sorted(os.listdir(OUT)):
        if not name.endswith(".jsonl"):
            continue
        alias, mode = name[:-len(".jsonl")].rsplit("-", 1)
        rows = [json.loads(line) for line in open(os.path.join(OUT, name)) if line.strip()]
        if not rows or alias not in speeds:
            continue
        n = len(rows)
        prior = [option_prior.pick(by_key[(r["id"], r["language"])]) for r in rows]
        late = [r["board_s"] > TIME_LIMIT for r in rows]
        model_hits = sum(r["answer"] == r["label"] for r in rows)
        prior_hits = sum(p == r["label"] for p, r in zip(prior, rows))
        # On the board a problem that runs out of time gets the prior's answer
        board_hits = sum((p if slow else r["answer"]) == r["label"] for p, slow, r in zip(prior, late, rows))
        times = sorted(r["board_s"] for r in rows)
        read, write = board_speeds(alias, speeds)
        table.append({
            "model": alias, "mode": mode, "n": n,
            "acc_no_limit": round(100 * model_hits / n, 1),
            "acc_board": round(100 * board_hits / n, 1),
            "prior_same": round(100 * prior_hits / n, 1),
            # Full val: the prior everywhere, except this model on the problems with options
            "full_val": round(100 * (prior_all + (board_hits - prior_hits) * len(with_options) / n) / len(val), 1),
            "late_pct": round(100 * sum(late) / n),
            "board_s_mean": round(sum(times) / n), "board_s_p90": round(times[int(0.9 * (n - 1))]),
            "written": round(sum(r["written_tokens"] for r in rows) / n),
            "read_tps": round(read, 1), "write_tps": round(write, 1),
            "file_gb": speeds[alias]["file_gb"],
        })
    table.sort(key=lambda row: -row["full_val"])
    if table:
        with open(os.path.join(OUT, "leaderboard.csv"), "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
        print(f"prior alone on the full val: {100 * prior_all / len(val):.1f}%\n")
        cols = list(table[0])
        print("  ".join(f"{c:>12s}" if i > 1 else f"{c:<17s}" for i, c in enumerate(cols)))
        for row in table:
            print("  ".join(f"{str(row[c]):>12s}" if i > 1 else f"{str(row[c]):<17s}" for i, c in enumerate(cols)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", default="",
                   help="aliases joined by commas (see MODELS in this file), or name=/path/to/file.gguf")
    p.add_argument("--modes", default="letter,think")
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--sample", type=int, default=150, help="problems for the think mode; 0 means all")
    p.add_argument("--max-tokens", type=int, default=400, help="upper limit for the working")
    p.add_argument("--port", type=int, default=8092)
    p.add_argument("--jobs", type=int, default=1, help="problems answered at the same time")
    p.add_argument("--gpu", action="store_true", help="answer on the laptop GPU: faster, same model")
    p.add_argument("--keep", action="store_true", help="keep the downloaded model file")
    p.add_argument("--report", action="store_true", help="only print the leaderboard")
    args = p.parse_args()

    with open(args.input) as f:
        val = [json.loads(line) for line in f if line.strip()]
    with_options = [pr for pr in val if set(pr.get("options") or {}) == set(LETTERS)]
    sample = with_options
    if args.sample and args.sample < len(with_options):
        sample = random.Random(0).sample(with_options, args.sample)
    if not args.report:
        for alias in filter(None, args.models.split(",")):
            if "=" in alias:  # a GGUF of our own, such as a fine-tuned model
                alias, path = alias.split("=", 1)
                LOCAL[alias] = os.path.expanduser(path)
            try:
                bench(alias, args, with_options, sample)
            except Exception as error:  # one broken model must not stop the others
                print(f"[{alias}] failed: {error}", file=sys.stderr)
    summarize(val)


if __name__ == "__main__":
    main()
