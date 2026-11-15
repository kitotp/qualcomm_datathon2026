#!/usr/bin/env python3
"""Run the trainer's web page on the laptop, the way the board will serve it.

    python tools/dev_server.py --demo        # invented problems (English grades 5-6, some Spanish), no M3Kang data
    python tools/dev_server.py               # data/map.db + data/train.jsonl (tools/build_map.py --no-embed)

Then open http://127.0.0.1:7000. The page comes from app/math-trainer/assets/
and the API from app/math-trainer/python/api.py, the same files the App Lab
app uses, so whatever works here moves to the board without changes. The LED
matrix is drawn on the page as an emulator. Standard library only.
"""
import argparse
import json
import mimetypes
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app", "math-trainer")
ASSETS = os.path.join(APP, "assets")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(APP, "python"))

from api import TrainerAPI, TrainerPool, safe  # noqa: E402
from copilot.city import City  # noqa: E402

DEMO_PROBLEMS = os.path.join(ROOT, "tools", "demo_problems.jsonl")
MAP_SCHEMA = """
CREATE TABLE problems (
    id TEXT, language TEXT, level INTEGER, year INTEGER, qnum INTEGER, tier INTEGER,
    topic TEXT, topic_score REAL, has_options INTEGER, text_only INTEGER,
    PRIMARY KEY (id, language)
)"""


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="use tools/demo_problems.jsonl instead of M3Kang")
    p.add_argument("--map", default="data/map.db")
    p.add_argument("--inputs", nargs="+", default=["data/train.jsonl"])
    p.add_argument("--student-db", default="data/student.db")
    p.add_argument("--city-db", default="data/city.db")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7000, help="7000, as the board's web_ui brick")
    p.add_argument("--teacher-pin", default=os.environ.get("KC_TEACHER_PIN"),
                   help="PIN for 'start over' (default: $KC_TEACHER_PIN; 1234 with --demo)")
    return p.parse_args()


def build_demo_map(path):
    """Write a map.db for the demo problems, whose topic and tier are in the file."""
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.execute(MAP_SCHEMA)
    with open(DEMO_PROBLEMS, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                db.execute("INSERT INTO problems VALUES (?, ?, ?, NULL, NULL, ?, ?, 1.0, 1, 1)",
                           (p["id"], p["language"], p["level"], p["tier"], p["topic"]))
    db.commit()
    db.close()


def compile_routes(routes):
    """"/api/next/{student}/{topic}" -> a regex with named groups, as web_ui's path parameters."""
    compiled = []
    for path, handler in routes:
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        compiled.append((re.compile("^" + pattern + "$"), safe(handler)))
    return compiled


def make_handler(routes):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("  " + fmt % args + "\n")

        def send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path.startswith("/api/"):
                for pattern, handler in routes:
                    match = pattern.match(path)
                    if match:
                        params = {k: unquote(v) for k, v in match.groupdict().items()}
                        return self.send(200, handler(**params))
                return self.send(404, {"error": "not found"})
            # Static files, only from inside assets/
            name = "index.html" if path == "/" else unquote(path.lstrip("/"))
            file = os.path.normpath(os.path.join(ASSETS, name))
            if file.startswith(ASSETS + os.sep) and os.path.isfile(file):
                kind = mimetypes.guess_type(file)[0] or "application/octet-stream"
                if kind.startswith("text/") or kind.endswith("javascript"):
                    kind += "; charset=utf-8"
                with open(file, "rb") as f:
                    return self.send(200, f.read(), kind)
            return self.send(404, {"error": "not found"})

    return Handler


def main():
    args = parse_args()
    os.chdir(ROOT)
    mimetypes.add_type("text/javascript", ".js")  # Windows may map .js to something else
    if args.demo:
        os.makedirs("data", exist_ok=True)
        build_demo_map("data/dev_map.db")
        pool = TrainerPool("data/dev_map.db", [DEMO_PROBLEMS], student_db="data/dev_student.db")
        city = City("data/dev_city.db")
    else:
        pool = TrainerPool(args.map, args.inputs, student_db=args.student_db)
        city = City(args.city_db)
    pin = args.teacher_pin or ("1234" if args.demo else None)
    api = TrainerAPI(pool, city, teacher_pin=pin)
    print("Languages and grades: " + ", ".join(f"{lang} {pool.grades(lang)}" for lang in pool.languages()))
    print(f"{len(city.residents())} houses in the city")
    print("Teacher PIN for 'start over': " + ("1234 (demo)" if pin == "1234" and args.demo and not args.teacher_pin
                                              else "set" if pin else "not set, so starting over is off"))
    print(f"Open http://{args.host}:{args.port} (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer((args.host, args.port), make_handler(compile_routes(api.routes()))).serve_forever()


if __name__ == "__main__":
    main()
