"""The baseline copilot: one problem in, one letter out.

This is the file to change first. predict.py and eval.py both call solve(),
so whatever you build here is exactly what the official run measures.
"""
import socket
import time
import urllib.error

from . import option_prior, think
from .config import CONFIG
from .llm import URL, answer_letter

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
ANSWER_MODE = CONFIG.get("ANSWER_MODE", "model")
THINK_SPEEDS = (float(CONFIG.get("THINK_READ_TPS", 11.3)), float(CONFIG.get("THINK_WRITE_TPS", 5.9)))
THINK_MAX_TOKENS = int(CONFIG.get("THINK_MAX_TOKENS", 300))


def has_options(problem):
    return set(problem.get("options") or {}) == set("ABCDE")
MARGIN = 3.0  # seconds kept free for Python and for writing the answer


def solve(problem, index=None, k=0, exclude_id=None, image_b64=None, llm_url=URL,
          time_limit=TIME_LIMIT):
    """Return {"answer", "seconds", "status", ...} for one problem.

    index and k turn on retrieval: the k most similar solved problems are
    added to the prompt as examples. Each example costs reading time.
    image_b64 and llm_url send the problem image to a vision server.
    """
    start = time.perf_counter()
    result = {"answer": FALLBACK, "status": "ok", "prompt_tokens": 0, "retrieved": "", "examples": []}
    if ANSWER_MODE in ("prior", "think"):
        # The prior is the answer whenever the model can't give a better one
        result["answer"] = option_prior.pick(problem)
        if ANSWER_MODE == "prior" or not has_options(problem):
            result["seconds"] = round(time.perf_counter() - start, 2)
            return result
        return solve_think(problem, result, start, llm_url, time_limit)
    try:
        examples = []
        if index is not None and k > 0:
            hits = index.search(problem, k=k, exclude_id=exclude_id)
            examples = [p for _score, p in hits]
            result["examples"] = hits
            result["retrieved"] = ";".join(f"{p['id']}:{s:.2f}" for s, p in hits)
        remaining = time_limit - (time.perf_counter() - start) - MARGIN
        letter, timings = answer_letter(problem, examples, timeout=max(remaining, 1.0),
                                        image_b64=image_b64, url=llm_url)
        result["answer"] = letter
        result["prompt_tokens"] = timings.get("prompt_n", 0)
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result


def solve_think(problem, result, start, llm_url, time_limit):
    """The think mode. result["answer"] already holds the prior's answer."""
    deadline = start + time_limit - MARGIN
    try:
        letter, details = think.answer_think(problem, llm_url, deadline, *THINK_SPEEDS, THINK_MAX_TOKENS,
                                             int(CONFIG["SEED"]))
        result["answer"] = letter
        result["prompt_tokens"] = details["prompt_tokens"]
        result["working_tokens"] = details["working_tokens"]
    except think.NoTime as reason:
        result["status"] = f"ok: prior ({reason})"[:80]
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
