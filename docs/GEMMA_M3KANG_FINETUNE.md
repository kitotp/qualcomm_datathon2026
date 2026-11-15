# Gemma 3 1B: M3Kang fine-tune, 14 November 2026

Fine-tuning on answer letters did not improve mathematical accuracy. The selected adapter collapsed to D for every problem with OCR options and A for every problem without options. It should not replace the existing option prior or be used as evidence that feedback to students is reliable.

| Model / method | Full validation (562) | With OCR options (339) |
|---|---:|---:|
| Gemma before, MLX 4-bit | 105/562 = 18.68% | 67/339 = 19.76% |
| Gemma after, same MLX base + LoRA | 108/562 = 19.22% | 72/339 = 21.24% |
| Exported Q8_0 GGUF, official `eval.py` | 108/562 = 19.22% | 72/339 = 21.24% |
| Existing option prior, no model | 155/562 = 27.58% | 97/339 = 28.61% |
| Always D | 130/562 = 23.13% | 72/339 = 21.24% |

The change is +0.53 percentage points. A paired bootstrap with 10,000 resamples, seed 42, grouped by problem ID to keep translations together, gives a 95% interval of [-5.34, +6.41] points. There are 281 distinct validation problems, each in English and Catalan. There is no evidence of an improvement.

## Data and training

- Existing OCR data: 2,932 train rows, 562 validation rows. No problem ID is shared between them.
- Internal split: 2,786 training rows and 146 dev rows, grouped by ID. Fixed the data builder to prevent translations crossing this split and to correctly report empty solution datasets.
- AQuA: zero. Teacher solutions: zero. Supervision: the exact `copilot.llm.build_messages` prompt followed by the reference answer letter. No generated explanations or student-error annotations were used.
- Base: `mlx-community/gemma-3-1b-it-4bit`, revision `2d44e83dc9e80843d22fb941d3d699a0b1351aa6`.
- Apple Silicon GPU, MLX 0.32.4, mlx-lm 0.32.2, transformers 5.23.0.
- QLoRA, all 26 layers, rank 8, scale 16, dropout 0.05; 6.523M trainable parameters. Adam, constant learning rate 1e-4, batch 4, seed 42, sequence limit 512. All examples fit without truncation.
- Planned 697 steps, interrupted after step 430 because internal dev loss worsened. Dev loss: 10.808 before training, 0.546 at step 200, 0.565 at step 400. The stock MLX batching uses 144 of the 146 dev rows (it drops the incomplete batch). Selected the saved step-200 adapter using dev alone, before the final validation run. It represents approximately 800 training-example presentations.
- A first stock-trainer run was stopped at step 30 and discarded. The final run restarted from the original base with seed 42.
- `tools/train_mlx_letters.py` computes vocabulary logits only at the three reply positions (letter, end-of-turn, newline). The transformer still reads the full prompt. Loss excludes padding. Its result was checked against a full-logit calculation on a real example (10.5117 vs 10.5156, within float16 tolerance).
- Accuracy uses the highest-scoring first token among A–E, matching the single-letter grammar in `predict.py`, no RAG. Before and after use the same base quantization, prompt, and validation file.

## Artifacts

Paths relative to this worktree:

- `models/gemma-m3kang-best/`: selected adapter and config.
- `models/gemma-m3kang-merged/`: merged, dequantized weights and tokenizer.
- `models/gemma-m3kang-q8_0.gguf`: exported model for llama.cpp.
- `results/gemma-m3kang/before.json`, `after.json`: aggregate scores.
- `results/gemma-m3kang/before.jsonl`, `after.jsonl`: per-example predictions and A–E scores; no problem text.
- `results/gemma-m3kang/train.log`, `train-original.log`: training logs.
- `results/gemma-m3kang/manifest.json`: dependency versions, base revision, data counts and SHA-256 hashes.
- `results/gemma-m3kang/comparison.json`: paired bootstrap result.
- `results/gemma-m3kang/gguf-eval.log`, `predict-smoke.csv`: official pipeline checks.

The GGUF is Q8_0 exported from an initially 4-bit base after merging and dequantization; exporting to Q8 does not recover the original unquantized base's precision. Conversion used the repository's pinned llama.cpp commit `2cbe0ec429b849a88664e0f62388fc92a5abd699`. The GGUF produced exactly the same 562 predictions as MLX. Official `eval.py` completed with 562 `ok` statuses; the five-example `predict.py` smoke test also passed. Laptop latency was 0.1 s on average, 0.2 s maximum; this is not a measurement of UNO Q latency.

## Reproduce the selected checkpoint

Use an Apple Silicon Python environment with `mlx-lm[train]`. The selected base must already be downloaded at the model path above.

```bash
python tools/make_finetune_data.py --aqua 0 --out data/finetune-m3kang
mkdir -p data/finetune-m3kang/mlx
cp data/finetune-m3kang/letters.jsonl data/finetune-m3kang/mlx/train.jsonl
cp data/finetune-m3kang/letters-dev.jsonl data/finetune-m3kang/mlx/valid.jsonl
python tools/eval_mlx_letters.py --model models/gemma-3-1b-it-4bit --out results/gemma-reproduced/before
python tools/train_mlx_letters.py --config docs/GEMMA_M3KANG.yaml
python tools/eval_mlx_letters.py --model models/gemma-3-1b-it-4bit --adapter models/gemma-m3kang-reproduced --out results/gemma-reproduced/after
```

`docs/GEMMA_M3KANG.yaml` runs 200 steps to reproduce the selected checkpoint directly. The original 697-step configuration remains in `results/gemma-m3kang/train.yaml`.

## What this experiment establishes

Answer-only adaptation on this small OCR dataset did not teach this model to solve the problems. A low completion loss largely reflects learning a short output format and does not establish mathematical reasoning. This experiment did not train or evaluate explanations of student mistakes. That requires checked solutions, examples of student errors and correct feedback, and a separate held-out evaluation of explanation correctness. Missing options and unseen diagrams also remain limitations of this text-only input.
