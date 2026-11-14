#!/usr/bin/env python3
"""Fine-tune the small model with LoRA, and score it on val without llama.cpp.

Needs its own Python environment (torch, transformers, peft); the rest of the
repository uses only the standard library. Runs on an NVIDIA GPU, on Apple
silicon, or slowly on a CPU.

    # the base model before any training: must be close to the llama.cpp baseline
    python tools/finetune_lora.py --base Qwen/Qwen3.5-0.8B --eval-only

    # train on the letters set, score on val after every epoch
    python tools/finetune_lora.py --base Qwen/Qwen3.5-0.8B \
        --data data/finetune/letters.jsonl --dev data/finetune/letters-dev.jsonl \
        --out models/letters-lora

The prompt is rendered with the model's chat template with thinking off,
which is what llama-server sends with --jinja --reasoning off. Only the
assistant's reply counts in the loss. The val score is the share of problems
where the right letter has the highest probability among A to E as the first
token of the reply: the same choice that the grammar in copilot/llm.py makes.

--out/merged holds the full model with the LoRA merged in, ready for
llama.cpp's convert_hf_to_gguf.py.
"""
import argparse
import json
import math
import os
import random
import shutil
import sys
import time

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoTokenizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from copilot.llm import build_messages  # noqa: E402

LETTERS = "ABCDE"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_model(base, device, dtype):
    import transformers
    for name in ("AutoModelForImageTextToText", "AutoModelForCausalLM"):
        try:
            return getattr(transformers, name).from_pretrained(base, torch_dtype=dtype).to(device)
        except (ValueError, AttributeError, KeyError) as error:
            last = error
    raise last


def render(tokenizer, messages):
    """The prompt up to the start of the assistant's reply, as llama-server builds it."""
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)


def encode(tokenizer, example, max_length):
    """Token ids, and labels that are -100 everywhere except on the assistant's reply."""
    prompt = tokenizer(render(tokenizer, example["messages"][:-1]), add_special_tokens=False)["input_ids"]
    reply = tokenizer(example["messages"][-1]["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
    prompt = prompt[-(max_length - len(reply)):]
    return prompt + reply, [-100] * len(prompt) + reply


def batches(items, size, pad, device, shuffle):
    """Batches of similar length, padded on the right."""
    order = sorted(range(len(items)), key=lambda i: len(items[i][0]))
    groups = [order[i:i + size] for i in range(0, len(order), size)]
    if shuffle:
        random.shuffle(groups)
    for group in groups:
        width = max(len(items[i][0]) for i in group)
        ids = torch.full((len(group), width), pad)
        labels = torch.full((len(group), width), -100)
        mask = torch.zeros((len(group), width), dtype=torch.long)
        for row, i in enumerate(group):
            n = len(items[i][0])
            ids[row, :n] = torch.tensor(items[i][0])
            if items[i][1]:  # scoring passes no labels
                labels[row, :n] = torch.tensor(items[i][1])
            mask[row, :n] = 1
        yield ids.to(device), mask.to(device), labels.to(device), group


@torch.no_grad()
def score_val(model, tokenizer, problems, device, batch_size=16):
    """Accuracy when the answer is the most likely letter as the first token of the reply."""
    model.eval()
    letter_ids = [tokenizer(k, add_special_tokens=False)["input_ids"] for k in LETTERS]
    assert all(len(t) == 1 for t in letter_ids), "a letter is not one token"
    letter_ids = torch.tensor([t[0] for t in letter_ids], device=device)
    items = [(tokenizer(render(tokenizer, build_messages(p)), add_special_tokens=False)["input_ids"], [])
             for p in problems]
    answers = [None] * len(problems)
    for ids, mask, _labels, group in batches(items, batch_size, tokenizer.pad_token_id, device, False):
        logits = model(input_ids=ids, attention_mask=mask).logits
        last = mask.sum(1) - 1
        choice = logits[torch.arange(len(group)), last][:, letter_ids].float().argmax(1)
        for i, c in zip(group, choice.tolist()):
            answers[i] = LETTERS[c]
    hits = [a == p["label"] for a, p in zip(answers, problems)]
    with_options = [h for h, p in zip(hits, problems) if p.get("options")]
    counts = {k: answers.count(k) for k in LETTERS}
    return (100 * sum(hits) / len(hits), 100 * sum(with_options) / max(len(with_options), 1), counts, answers)


@torch.no_grad()
def dev_loss(model, items, pad, device, batch_size):
    model.eval()
    total, n = 0.0, 0
    for ids, mask, labels, group in batches(items, batch_size, pad, device, False):
        total += model(input_ids=ids, attention_mask=mask, labels=labels).loss.item() * len(group)
        n += len(group)
    return total / max(n, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True, help="Hugging Face id or folder of the original model")
    p.add_argument("--data", default="data/finetune/letters.jsonl")
    p.add_argument("--dev", default="data/finetune/letters-dev.jsonl")
    p.add_argument("--val", default="data/val.jsonl")
    p.add_argument("--out", default="models/lora")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--rate", type=float, default=1e-4)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--rank", type=int, default=8)
    p.add_argument("--max-length", type=int, default=768)
    p.add_argument("--limit", type=int, default=0, help="train on the first N examples only")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = load_model(args.base, device, dtype)
    val = load_jsonl(args.val)
    print(f"device {device}, {sum(p.numel() for p in model.parameters()) / 1e6:.0f}M parameters")

    def report(name):
        acc, acc_options, counts, answers = score_val(model, tokenizer, val, device)
        print(f"{name}: val {acc:.1f}%  with options {acc_options:.1f}%  letters {counts}", flush=True)
        return acc, answers

    if args.eval_only:
        report("base")
        return

    # LoRA on every linear layer of the language model, not on the vision part or the output layer
    targets = [name for name, module in model.named_modules()
               if isinstance(module, torch.nn.Linear) and "vis" not in name.lower()
               and module.out_features != model.config.get_text_config().vocab_size]
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05,
                                             target_modules=targets))
    model.print_trainable_parameters()

    train = [encode(tokenizer, ex, args.max_length) for ex in load_jsonl(args.data)]
    if args.limit:
        train = train[:args.limit]
    dev = [encode(tokenizer, ex, args.max_length) for ex in load_jsonl(args.dev)] if args.dev else []
    steps = args.epochs * math.ceil(len(train) / args.batch)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.rate)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.rate, total_steps=steps, pct_start=0.1)
    print(f"{len(train)} examples, {steps} steps", flush=True)

    os.makedirs(args.out, exist_ok=True)
    best, step, start = -1.0, 0, time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for ids, mask, labels, _group in batches(train, args.batch, tokenizer.pad_token_id, device, True):
            loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            schedule.step()
            optimizer.zero_grad()
            running += loss.item()
            step += 1
            if step % 25 == 0:
                print(f"  step {step}/{steps}  loss {running / 25:.3f}  {time.time() - start:.0f}s", flush=True)
                running = 0.0
        loss = dev_loss(model, dev, tokenizer.pad_token_id, device, args.batch) if dev else float("nan")
        acc, answers = report(f"epoch {epoch} (dev loss {loss:.3f})")
        if acc > best:
            best = acc
            model.save_pretrained(os.path.join(args.out, "adapter"))
            with open(os.path.join(args.out, "val-answers.jsonl"), "w") as f:
                for pr, a in zip(val, answers):
                    f.write(json.dumps({"id": pr["id"], "language": pr.get("language", ""),
                                        "label": pr["label"], "answer": a}) + "\n")

    merged = model.merge_and_unload()
    target = os.path.join(args.out, "merged")
    merged.save_pretrained(target)
    tokenizer.save_pretrained(target)
    if os.path.isdir(args.base):  # files that the GGUF converter expects next to the weights
        for name in os.listdir(args.base):
            if name.endswith((".json", ".jinja", ".txt")) and not os.path.exists(os.path.join(target, name)):
                shutil.copy(os.path.join(args.base, name), target)
    print(f"best val {best:.1f}%, merged model in {target}")


if __name__ == "__main__":
    main()
