#!/usr/bin/env python3
"""Build the files for fine-tuning a small model on Kangaroo-style problems.

Two sources, written in the same chat format:

  M3Kang train   data/train.jsonl, every language it holds
  AQuA-RAT       about 97,000 English word problems with five options A to E
                 and a written solution (Apache 2.0, github.com/google-deepmind/AQuA).
                 Converted to the fields of train.jsonl, and cut to --aqua rows.

Two training sets, each with the exact prompt that the copilot sends:

  letters    the predict.py prompt (copilot/llm.py), answered with one letter
  solutions  the think prompt (tools/solve_match.py), answered with a short
             solution that ends with "Answer: X". M3Kang problems are only
             in this set when data/finetune/teacher.jsonl has a solution for
             them (tools/teacher_solutions.py writes it).

    python3 tools/make_finetune_data.py
    python3 tools/make_finetune_data.py --aqua 20000

Everything is written under data/finetune/, which Git ignores: the files hold
M3Kang text and must never be committed. val.jsonl is never read, so the
validation score stays honest. The last 5% of each set is a dev file for
early stopping.
"""
import argparse
import json
import os
import random
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from copilot.llm import build_messages  # noqa: E402
from solve_match import think_messages  # noqa: E402

LETTERS = "ABCDE"
AQUA_URL = "https://raw.githubusercontent.com/google-deepmind/AQuA/master/train.json"
OPTION = re.compile(r"^\s*([A-E])\s*\)\s*(.+?)\s*$", re.S)
# "The answer is E.", "Answer: E", "ANSWER:E", "Ans - E", "Correct option: E" at the end of a solution
ANSWER_TAIL = re.compile(
    r"\s*(?:so|hence|therefore|thus)?[\s,]*(?:the\s+)?(?:correct\s+)?(?:answer|ans|option|choice)"
    r"[\s\w]*?(?:is|:|-|=)?\s*\(?[A-E]\)?[\s.!]*$", re.I)


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def aqua_problems(path, limit, max_question, max_solution, seed):
    """AQuA rows as problems with the fields of train.jsonl, plus "solution"."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"downloading {AQUA_URL}", file=sys.stderr)
        urllib.request.urlretrieve(AQUA_URL, path)
    problems, seen = [], set()
    for n, row in enumerate(load_jsonl(path)):
        parts = [OPTION.match(o) for o in row.get("options", [])]
        if len(parts) != 5 or not all(parts) or "".join(m.group(1) for m in parts) != LETTERS:
            continue
        question, label = row["question"].strip(), row.get("correct", "").strip()
        solution = ANSWER_TAIL.sub("", row.get("rationale", "").strip()).strip()
        if (label not in LETTERS or question in seen or len(question) > max_question
                or not 20 <= len(solution) <= max_solution):
            continue
        seen.add(question)
        problems.append({"id": f"aqua-{n}", "language": "eng", "text_only": True, "text": question,
                         "options": {m.group(1): m.group(2) for m in parts}, "label": label,
                         "solution": solution})
    random.Random(seed).shuffle(problems)
    return problems[:limit]


def letter_example(problem):
    return {"id": problem["id"],
            "messages": build_messages(problem) + [{"role": "assistant", "content": problem["label"]}]}


def solution_example(problem, solution):
    return {"id": problem["id"],
            "messages": think_messages(problem) + [
                {"role": "assistant", "content": f"{solution}\nAnswer: {problem['label']}"}]}


def write(name, examples, out, seed):
    random.Random(seed).shuffle(examples)
    dev = max(1, len(examples) // 20)
    for suffix, rows in (("", examples[dev:]), ("-dev", examples[:dev])):
        with open(os.path.join(out, f"{name}{suffix}.jsonl"), "w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    chars = sum(len(m["content"]) for row in examples for m in row["messages"])
    print(f"{name}: {len(examples) - dev} train + {dev} dev examples, about {chars // 4:,} tokens")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default="data/train.jsonl")
    p.add_argument("--aqua", type=int, default=20000, help="AQuA problems to keep; 0 for none")
    p.add_argument("--aqua-file", default="data/external/aqua_train.json")
    p.add_argument("--teacher", default="data/finetune/teacher.jsonl",
                   help="solutions for M3Kang train problems, if the file exists")
    p.add_argument("--out", default="data/finetune")
    p.add_argument("--max-question", type=int, default=600, help="characters")
    p.add_argument("--max-solution", type=int, default=400, help="characters")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    kangaroo = load_jsonl(args.train)
    aqua = aqua_problems(args.aqua_file, args.aqua, args.max_question, args.max_solution, args.seed) \
        if args.aqua else []
    teacher = {}
    if os.path.exists(args.teacher):
        teacher = {row["id"]: row["solution"] for row in load_jsonl(args.teacher)}
    print(f"M3Kang train {len(kangaroo)} problems, AQuA {len(aqua)}, teacher solutions {len(teacher)}")

    write("letters", [letter_example(pr) for pr in kangaroo + aqua], args.out, args.seed)
    solved = [solution_example(pr, teacher[pr["id"]]) for pr in kangaroo
              if pr["id"] in teacher and set(pr.get("options") or {}) == set(LETTERS)]
    write("solutions", solved + [solution_example(pr, pr["solution"]) for pr in aqua], args.out, args.seed)
    print(f"  of which M3Kang problems with a teacher solution: {len(solved)}")


if __name__ == "__main__":
    main()
