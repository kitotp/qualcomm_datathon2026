# Fine-tune the small model on a PC with an NVIDIA GPU

These are the steps for a new session on the training PC (RTX 2070 Super, 8 GB of video memory, 32 GB of RAM). Read [REASON_RESEARCH.md](REASON_RESEARCH.md) first: it says what was measured and why we fine-tune.

## Goal

Train a small model to write a short solution and end with `Answer: X`, then hand back one GGUF file. The laptop session scores that file on the M3Kang validation set with the board's time limit.

- **Time budget: about 90 minutes in total.** Prefer a finished smaller run over an unfinished bigger one.
- **No M3Kang data is needed on this PC.** The training set is 20,000 problems from AQuA-RAT (Apache 2.0), which the data script downloads itself.
- Never commit `data/` or `models/`. Work on the branch `experiment/reason-research`. Commit fixes to the scripts locally, and ask the user before pushing.

## Steps

### 1. Check the machine

```bash
nvidia-smi          # the GPU and its free memory
python --version    # 3.10 to 3.12
```

### 2. Get the code and the libraries

```bash
git clone https://github.com/kitotp/qualcomm_datathon2026.git
cd qualcomm_datathon2026
git checkout experiment/reason-research
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install transformers peft accelerate sentencepiece protobuf gguf huggingface_hub
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

The last line must print `True`. If it prints `False`, the wrong torch build was installed: fix that before anything else.

### 3. Build the training files

```bash
python tools/make_finetune_data.py --aqua 20000
```

It writes `data/finetune/solutions.jsonl` (19,000 examples, about 2.7 million tokens) and `solutions-dev.jsonl` (1,000). Each example is the copilot's "think" prompt (`tools/solve_match.py`, `think_messages`) and a reply with a short solution that ends with `Answer: X`. It also prints a line about `letters`; ignore that set here.

### 4. Choose the base model with a two-minute speed test

Two candidates. Both fit the board's time limit by our estimate.

| Model | Why | Risk |
|---|---|---|
| `unsloth/gemma-3-1b-it` | Standard architecture, trains fast anywhere. Best small model in our "think" test (24%). | fp16 can give a `nan` loss; the script stops and says so. Its license is the Gemma terms, which the team must check before publishing. |
| `Qwen/Qwen3.5-0.8B` | The model that is on the board now, Apache 2.0. | New architecture with linear attention. Without the `flash-linear-attention` and `causal_conv1d` packages, transformers falls back to a slow implementation. On Windows those packages may not install. |

Run the test for each, and read the `tokens/s` in the log:

```bash
python tools/finetune_lora.py --base unsloth/gemma-3-1b-it --limit 400 --epochs 1 --generate 0 --out models/speed-test
```

Take Gemma unless Qwen trains at a similar speed. If the loss is `nan`, add `--precision bf16`, and if that is slow, `--precision fp32 --batch 8`.

### 5. Score the untrained model, for comparison

```bash
python tools/finetune_lora.py --base <model> --eval-only
```

It prints `dev generated: right N%`: the share of 200 held-out AQuA problems where the generated solution ends with the right letter.

### 6. Train

```bash
python tools/finetune_lora.py --base <model> --epochs 1 --out models/solutions-v1
```

Every 25 steps it prints the loss, the speed, and the minutes left. If more than 60 minutes are left after the first 100 steps, stop and run again with `--limit 10000`. At the end it prints the dev loss and the generated score, and writes the merged model to `models/solutions-v1/merged`.

### 7. Convert to GGUF

Use the same llama.cpp commit as the board (`LLAMA_CPP_REF` in `config.env`), so the file loads there:

```bash
git clone https://github.com/ggml-org/llama.cpp ../llama.cpp
git -C ../llama.cpp checkout 2cbe0ec429b849a88664e0f62388fc92a5abd699
python ../llama.cpp/convert_hf_to_gguf.py models/solutions-v1/merged --outtype q8_0 --outfile models/solutions-v1-q8_0.gguf
```

Do not run `pip install -r` on llama.cpp's requirements files: they can replace the GPU build of torch.

### 8. Hand back

Tell the user:

- the full path of `models/solutions-v1-q8_0.gguf`, to copy to the laptop's `~/models/`
- the base model, the training speed and time, the dev loss
- `dev generated: right` before and after training
- anything you had to change

The laptop session then runs:

```bash
python3 tools/bench_models.py --models solutions-v1=~/models/solutions-v1-q8_0.gguf --modes letter,think --gpu --jobs 6 --sample 150
```

## If something breaks

- `tools/finetune_lora.py` was only tested end to end on a tiny model on a CPU, not on CUDA. Fix what breaks and keep the fixes small.
- Out of GPU memory: lower `--batch` to 8, then `--max-length` to 384.
- The converter does not know the model: try the newest llama.cpp for the conversion only, and say so in the hand-back.
