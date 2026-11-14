#!/usr/bin/env python3
"""Build the M3Kang map: a topic and a tier (1-3) for every problem.

    python3 tools/build_map.py                     # data/train.jsonl + data/val.jsonl -> data/map.db
    python3 tools/build_map.py --no-embed          # keywords only, no embedding server needed

Each problem id gets one topic, taken from its English version and copied to
every language: the embedding model (bge-small) is English. The topic is the
one whose description in copilot/topics.py is closest to the problem, plus a
small bonus per keyword hit. Owner: coder A.

data/map.db holds no problem text, but it's derived from M3Kang: don't commit
it (.gitignore already excludes *.db).
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.topics import TOPICS, exam_of, keyword_scores, qnum_of, tier_of  # noqa: E402

KEYWORD_BONUS = 0.03  # added to the cosine similarity per keyword hit; tune it on the hand labels

SCHEMA = """
CREATE TABLE problems (
    id TEXT, language TEXT, level INTEGER, year INTEGER, qnum INTEGER, tier INTEGER,
    topic TEXT, topic_score REAL, has_options INTEGER, text_only INTEGER,
    PRIMARY KEY (id, language)
)"""


def load(paths):
    problems = []
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                problems += [json.loads(line) for line in f if line.strip()]
        else:
            print(f"Skipping {path}: not found")
    return problems


def topics_by_id(problems, use_embeddings):
    """Return {id: (topic, score)} from one text per id, English when there is one."""
    text_of = {}
    for p in problems:
        if p["id"] not in text_of or p["language"] == "eng":
            text_of[p["id"]] = p["text"]
    ids = sorted(text_of)
    names = list(TOPICS)

    similarity = {i: {t: 0.0 for t in names} for i in ids}
    if use_embeddings:
        from copilot.embed import embed
        topic_vecs = embed([TOPICS[t]["description"] for t in names], query=True)
        for start in range(0, len(ids), 16):
            chunk = ids[start:start + 16]
            for i, vec in zip(chunk, embed([text_of[i] for i in chunk])):
                for t, tv in zip(names, topic_vecs):
                    similarity[i][t] = sum(a * b for a, b in zip(vec, tv))
            print(f"\r{min(start + 16, len(ids))}/{len(ids)} problems embedded", end="", flush=True)
        print()

    result = {}
    for i in ids:
        hits = keyword_scores(text_of[i])
        scores = {t: similarity[i][t] + KEYWORD_BONUS * hits[t] for t in names}
        best = max(scores, key=scores.get)
        result[i] = (best, round(scores[best], 4))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inputs", nargs="+", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--db", default="data/map.db")
    p.add_argument("--no-embed", action="store_true", help="keywords only")
    args = p.parse_args()

    problems = load(args.inputs)
    if not problems:
        sys.exit("No problems found. Run laptop/prepare_m3kang.py and copy the data first.")

    exam_size = defaultdict(int)
    for x in problems:
        exam = exam_of(x["id"])
        if exam:
            exam_size[exam] = max(exam_size[exam], qnum_of(x["id"]))

    topics = topics_by_id(problems, use_embeddings=not args.no_embed)

    if os.path.exists(args.db):
        os.remove(args.db)
    db = sqlite3.connect(args.db)
    db.execute(SCHEMA)
    db.executemany("INSERT OR REPLACE INTO problems VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (x["id"], x["language"], x.get("level"), x.get("year"), qnum_of(x["id"]),
         tier_of(x, exam_size.get(exam_of(x["id"]))), *topics[x["id"]],
         int(bool(x.get("options"))), int(bool(x.get("text_only"))))
        for x in problems])
    db.commit()

    print(f"Wrote {args.db}: {len(problems)} rows, {len(topics)} problem ids")
    for topic, n in db.execute("SELECT topic, COUNT(DISTINCT id) FROM problems GROUP BY topic ORDER BY 2 DESC"):
        print(f"  {topic:12} {n}")
    for tier, n in db.execute("SELECT tier, COUNT(DISTINCT id) FROM problems GROUP BY tier ORDER BY 1"):
        print(f"  tier {tier}: {n}")
    db.close()


if __name__ == "__main__":
    main()
