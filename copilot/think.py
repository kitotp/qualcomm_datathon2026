"""Let the model write a short solution, then answer with a letter.

The baseline asks for one letter with no working. In this mode the model
first writes a solution, as long as the time left allows, and a second call
that reuses the cached prompt forces "Answer: X" with a grammar. It is meant
for a model fine-tuned on this prompt (tools/finetune_lora.py): the training
data uses think_messages() below, so keep the prompt in this one place.

The length of the working comes from the board's speed for the model in use
(THINK_READ_TPS and THINK_WRITE_TPS in config.env), not from the machine it
runs on. So a run on the laptop gives the answers the board would give, and
on the board the real timeouts still apply.
"""
import time

from .client import post

LETTERS = "ABCDE"
SYSTEM = ("You solve math competition problems for school students. Solve the problem step by step. "
          "Be concise: do not restate the problem, go straight to the calculation.")
ASK_LETTER = "Final answer, the letter of the option only:"
# The model starts its reply with words, so a bare letter as the first token is unreliable
LETTER_GRAMMAR = 'root ::= "Answer: " [A-E]'

TEMPLATE_TOKENS = 45     # system prompt and chat template around the problem
FOLLOW_UP_TOKENS = 15    # new prompt tokens of the second call
LETTER_TOKENS = 8        # "Answer: X": up to 8 tokens under the grammar, depending on the model
MIN_WORKING_TOKENS = 30  # below this the working is too short to help


class NoTime(Exception):
    """Not enough time left for a useful solution."""


def problem_text(problem):
    return "\n".join([problem["text"].strip()] + [f"{k}) {problem['options'][k]}" for k in LETTERS])


def think_messages(problem):
    """The prompt of the think mode. Fine-tuning data must use the same one."""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": problem_text(problem)}]


def working_budget(prompt_tokens, seconds_left, read_tps, write_tps, max_tokens):
    """Tokens of working that fit, after reading the prompt and before the letter."""
    fixed = (prompt_tokens + FOLLOW_UP_TOKENS) / read_tps + LETTER_TOKENS / write_tps
    return max(0, min(max_tokens, int((seconds_left - fixed) * write_tps)))


def answer_think(problem, url, deadline, read_tps, write_tps, max_tokens, seed):
    """Return (letter, details). deadline is a time.perf_counter() value.

    Raises NoTime when the problem is too long to leave room for working,
    and the usual socket or URL errors when a call runs out of time.
    """
    base = url.rsplit("/v1/", 1)[0]
    messages = think_messages(problem)
    tokens = len(post(base + "/tokenize", {"content": problem_text(problem)}, timeout=5)["tokens"])
    budget = working_budget(tokens + TEMPLATE_TOKENS, deadline - time.perf_counter(), read_tps, write_tps,
                            max_tokens)
    if budget < MIN_WORKING_TOKENS:
        raise NoTime(f"{tokens} prompt tokens leave {budget} tokens of working")
    common = {"temperature": 0, "seed": seed, "cache_prompt": True}
    first = post(url, {"messages": messages, "max_tokens": budget, **common},
                 timeout=max(deadline - time.perf_counter(), 1.0))
    working = first["choices"][0]["message"]["content"]
    second = post(url, {"messages": messages + [{"role": "assistant", "content": working},
                                                {"role": "user", "content": ASK_LETTER}],
                        "max_tokens": 2 * LETTER_TOKENS, "grammar": LETTER_GRAMMAR, **common},
                  timeout=max(deadline - time.perf_counter(), 1.0))
    letter = second["choices"][0]["message"]["content"].strip()[-1:]
    if letter not in LETTERS:
        raise NoTime(f"no letter in the reply: {second['choices'][0]['message']['content']!r}")
    return letter, {"working": working, "working_limit": budget,
                    "prompt_tokens": first.get("usage", {}).get("prompt_tokens", 0),
                    "working_tokens": first.get("usage", {}).get("completion_tokens", 0)}
