#!/usr/bin/env python3
"""Fine-tune a small model with LoRA, and score it without llama.cpp.

Needs its own Python environment (torch, transformers, peft); the rest of the
repository uses only the standard library. Meant for an NVIDIA GPU. See
docs/FINETUNE_PC.md for the steps on a new machine.

    # train on problems with written solutions (data/finetune/solutions.jsonl)
    python tools/finetune_lora.py --base unsloth/gemma-3-1b-it \
        --data data/finetune/solutions.jsonl --dev data/finetune/solutions-dev.jsonl \
        --out models/solutions-gemma1b --epochs 1

    # the base model before any training, for comparison
    python tools/finetune_lora.py --base unsloth/gemma-3-1b-it --eval-only

The prompt is rendered with the model's chat template with thinking off,
which is what llama-server sends with --jinja --reasoning off. Only the
assistant's reply counts in the loss.

Two scores, both optional because they need files that may not be on the
training machine:
  --val        M3Kang validation: the share of problems where the right
               letter is the most likely first token (the predict.py prompt)
  --dev        held-out examples of the training set: the loss, and with
               --generate N the share of N examples whose generated reply
               ends with the right "Answer: X"

--out/merged holds the full model with the LoRA merged in, ready for
llama.cpp's convert_hf_to_gguf.py.
"""
import argparse
import json
import math
import os
import random
import re
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
ANSWER = re.compile(r"Answer:\s*([A-E])")


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_model(base, device, dtype):
    import transformers
    for name in ("AutoModelForCausalLM", "AutoModelForImageTextToText"):
        try:
            return getattr(transformers, name).from_pretrained(base, dtype=dtype).to(device)
        except (ValueError, AttributeError, KeyError) as error:
            last = error
    raise last


def render(tokenizer, messages):
    """The prompt up to the start of the assistant's reply, as llama-server builds it."""
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)


def reply_text(tokenizer, messages, prompt):
    """The assistant's reply with the model's own end-of-turn marker."""
    full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    if full.startswith(prompt):
        return full[len(prompt):]
    # Templates with a thinking block render a past reply differently: add the marker by hand
    return messages[-1]["content"] + (tokenizer.eos_token or "")


def encode(tokenizer, example, max_length):
    """Token ids, and labels that are -100 everywhere except on the assistant's reply."""
    text = render(tokenizer, example["messages"][:-1])
    prompt = tokenizer(text, add_special_tokens=False)["input_ids"]
    reply = tokenizer(reply_text(tokenizer, example["messages"], text), add_special_tokens=False)["input_ids"]
    reply = reply[:max_length // 2]
    prompt = prompt[-(max_length - len(reply)):]
    return prompt + reply, [-100] * len(prompt) + reply


def batches(items, size, pad, device, shuffle, left=False):
    """Batches of similar length. Padded on the right, or on the left for generation."""
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
            where = slice(width - n, width) if left else slice(0, n)
            ids[row, where] = torch.tensor(items[i][0])
            mask[row, where] = 1
            if items[i][1]:  # scoring passes no labels
                labels[row, where] = torch.tensor(items[i][1])
        yield ids.to(device), mask.to(device), labels.to(device), group


@torch.no_grad()
def score_letters(model, tokenizer, problems, device, batch_size=16):
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
    return 100 * sum(hits) / len(hits), 100 * sum(with_options) / max(len(with_options), 1), counts


@torch.no_grad()
def score_generated(model, tokenizer, examples, device, max_new_tokens, batch_size=16):
    """Share of examples whose generated reply ends with the reference's "Answer: X"."""
    model.eval()
    items = [(tokenizer(render(tokenizer, ex["messages"][:-1]), add_special_tokens=False)["input_ids"], [])
             for ex in examples]
    truth = [(ANSWER.findall(ex["messages"][-1]["content"]) or [None])[-1] for ex in examples]
    hits = answered = tokens = 0
    for ids, mask, _labels, group in batches(items, batch_size, tokenizer.pad_token_id, device, False, left=True):
        out = model.generate(input_ids=ids, attention_mask=mask, max_new_tokens=max_new_tokens,
                             do_sample=False, pad_token_id=tokenizer.pad_token_id)
        for i, row in zip(group, out[:, ids.shape[1]:]):
            text = tokenizer.decode(row, skip_special_tokens=True)
            found = ANSWER.findall(text)
            answered += bool(found)
            hits += bool(found) and found[-1] == truth[i]
            tokens += int((row != tokenizer.pad_token_id).sum())
    n = len(examples)
    return 100 * hits / n, 100 * answered / n, tokens / n


@torch.no_grad()
def dev_loss(model, items, pad, device, batch_size, autocast):
    model.eval()
    total, n = 0.0, 0
    for ids, mask, labels, group in batches(items, batch_size, pad, device, False):
        with autocast():
            total += model(input_ids=ids, attention_mask=mask, labels=labels).loss.item() * len(group)
        n += len(group)
    return total / max(n, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True, help="Hugging Face id or folder of the original model")
    p.add_argument("--data", default="data/finetune/solutions.jsonl")
    p.add_argument("--dev", default="data/finetune/solutions-dev.jsonl")
    p.add_argument("--val", default="data/val.jsonl", help="skipped when the file does not exist")
    p.add_argument("--out", default="models/lora")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--rate", type=float, default=2e-4)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--rank", type=int, default=16)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--precision", default="", choices=["", "fp32", "fp16", "bf16"],
                   help="default: fp16 on an NVIDIA GPU, fp32 elsewhere. Use fp32 or bf16 if the loss is nan")
    p.add_argument("--generate", type=int, default=200, help="dev examples to generate for; 0 for none")
    p.add_argument("--max-new-tokens", type=int, default=200)
    p.add_argument("--limit", type=int, default=0, help="train on the first N examples only")
    p.add_argument("--device", default="", help="cuda, mps, or cpu; default: the best one found")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available()
                             else "mps" if torch.backends.mps.is_available() else "cpu")
    precision = args.precision or ("fp16" if device == "cuda" else "fp32")
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = load_model(args.base, device, torch.bfloat16 if precision == "bf16" else torch.float32)
    print(f"device {device}, {precision}, {sum(p.numel() for p in model.parameters()) / 1e6:.0f}M parameters",
          flush=True)

    def autocast():
        return torch.autocast(device, dtype=torch.float16, enabled=(precision == "fp16"))

    val = load_jsonl(args.val) if os.path.exists(args.val) else []
    dev_examples = load_jsonl(args.dev) if args.dev and os.path.exists(args.dev) else []

    def report(name):
        line = name
        if val:
            with autocast():
                acc, acc_options, counts = score_letters(model, tokenizer, val, device)
            line += f" | val letters {acc:.1f}% (with options {acc_options:.1f}%) {counts}"
        if dev_examples and args.generate:
            with autocast():
                acc, answered, tokens = score_generated(model, tokenizer, dev_examples[:args.generate], device,
                                                        args.max_new_tokens)
            line += f" | dev generated: right {acc:.1f}%, gave an answer {answered:.1f}%, {tokens:.0f} tokens"
        print(line, flush=True)

    if args.eval_only:
        report("base")
        return

    # LoRA on every linear layer of the language model, not on the vision part or the output layer
    vocab = model.get_output_embeddings().out_features
    targets = [name for name, module in model.named_modules()
               if isinstance(module, torch.nn.Linear) and "vis" not in name.lower()
               and module.out_features != vocab]
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05,
                                             target_modules=targets))
    model.print_trainable_parameters()

    train = [encode(tokenizer, ex, args.max_length) for ex in load_jsonl(args.data)]
    if args.limit:
        train = train[:args.limit]
    dev = [encode(tokenizer, ex, args.max_length) for ex in dev_examples]
    steps = args.epochs * math.ceil(len(train) / args.batch)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.rate)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.rate, total_steps=steps, pct_start=0.05)
    scaler = torch.amp.GradScaler(device, enabled=(precision == "fp16"))
    print(f"{len(train)} examples, {sum(len(x[0]) for x in train):,} tokens per epoch, {steps} steps", flush=True)

    os.makedirs(args.out, exist_ok=True)
    step, seen, start = 0, 0, time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for ids, mask, labels, _group in batches(train, args.batch, tokenizer.pad_token_id, device, True):
            with autocast():
                loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
            if not torch.isfinite(loss):
                sys.exit("the loss is nan: run again with --precision fp32 (or bf16)")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            schedule.step()
            optimizer.zero_grad()
            running += loss.item()
            seen += int(mask.sum())
            step += 1
            if step % 25 == 0:
                elapsed = time.time() - start
                print(f"  step {step}/{steps}  loss {running / 25:.3f}  {seen / elapsed:,.0f} tokens/s  "
                      f"{elapsed / 60:.0f} min, about {elapsed / step * (steps - step) / 60:.0f} min left",
                      flush=True)
                running = 0.0
        model.save_pretrained(os.path.join(args.out, "adapter"))
        loss = dev_loss(model, dev, tokenizer.pad_token_id, device, args.batch, autocast) if dev else float("nan")
        report(f"epoch {epoch}: dev loss {loss:.3f}")

    merged = model.merge_and_unload()
    target = os.path.join(args.out, "merged")
    merged.save_pretrained(target)
    tokenizer.save_pretrained(target)
    if os.path.isdir(args.base):  # files that the GGUF converter expects next to the weights
        for name in os.listdir(args.base):
            if name.endswith((".json", ".jinja", ".txt")) and not os.path.exists(os.path.join(target, name)):
                shutil.copy(os.path.join(args.base, name), target)
    print(f"merged model in {target}\n"
          f"next: python <llama.cpp>/convert_hf_to_gguf.py {target} --outtype q8_0 --outfile {args.out}.gguf")


if __name__ == "__main__":
    main()
