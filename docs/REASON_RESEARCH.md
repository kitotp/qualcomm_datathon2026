# Reason track: what we measured on 14–15 November 2026

This is the state of the work on `predict.py` accuracy. Read the summary; the rest is the evidence.

## Summary

- **Best result so far: 155/562 = 27.58% on the full validation set, with no language model.** These are 562 language rows representing 281 distinct problems in English and Catalan. Always answering D gives 130/562 = 23.13%.
- The 27.6% comes from an "option prior": when the five options are numbers, the smallest and the largest are rarely the answer. It answers in 0 seconds.
- **No text model tested within the estimated board budget clearly beats the prior**, with one letter or with written working. Of the five models from 0.8B to 2B, LFM2 1.2B with working is closest (27.0% against 25.0% on the same 100 problems; no clear advantage).
- Models that do reason well enough (Phi-4-mini, Qwen3.5 4B: 33% to 42% with free working) would need 3 to 5 minutes per problem on the board.
- In the original text-only input, 223/562 rows have no OCR options. Later image experiments supplied the full question, diagram and choices for **all 562 rows**, but still did not beat the prior. A separate OCR version increased option coverage to 434/562 and reduced the measured prior accuracy; coverage alone did not establish a gain.
- **Gemma fine-tuning completed with a negative result:** 105/562 before, 108/562 after. Follow-up letter and solution training did not show useful transfer on internal dev; the latter run was stopped. Memorizing train examples worked, but did not establish reasoning.
- **Structured tools did not transfer to M3Kang:** 32 verified correct answers on 60 synthetic problems, but zero verified answers on the real 562-row validation. Its unchanged 27.58% system score came from the old fallback, not from new verified solutions.
- **Image-based Qwen3-VL 2B fine-tuning:** 114/562 = 20.28% before, 128/562 = 22.78% after, all images processed without answer fallback. Training stopped after dev ceased improving. Subsequent reasoning on the same 50 dev problems scored 13/50 with greedy decoding and 10/50 with checkpoint sampling, versus 7/50 for an immediate letter and 17/50 for always D.
- No follow-up model was promoted. The new training and image reasoning measurements used Apple Silicon; their UNO Q latency was not verified. The [NVIDIA PC guide](FINETUNE_PC.md) remains a plan, not evidence that its proposed 20,000-example run happened.

**Decision for the team:** the option prior remains the strongest measured full-validation candidate. The experiments below did not establish a better replacement or reliable feedback to students. This report does not change `config.env` or deploy a model.

## Results on the full validation set

All rows below cover the same original 562 validation rows, English and Catalan. Original baseline/RAG runs used `eval.py --limit 0`; the new MLX runs used the linked experiment harnesses. Gemma's exported GGUF was also checked with official `eval.py` and reproduced the same predictions. The two translations of each problem are correlated, so these are not 562 independent tasks. Small differences alone do not establish a reliable improvement.

| Run | Accuracy | Seconds per problem on the board |
|---|---|---|
| Always D | 23.1% | 0 |
| Baseline: Qwen3.5 0.8B, one letter | 23.1% | about 13 |
| Baseline + 1 retrieved example (RAG) | 23.0% | longer prompt |
| Qwen3.5 2B, one letter | 24.7% | about 48, some problems too slow |
| **Option prior, no model** | **27.6%** | 0 |
| Gemma 3 1B, before answer-letter fine-tune | 105/562 = 18.68% | not measured in this follow-up |
| Gemma 3 1B, after answer-letter fine-tune; MLX and exported GGUF agree | 108/562 = 19.22% | not measured in this follow-up |
| Qwen3-VL 2B, full images, before LoRA | 114/562 = 20.28% | not measured |
| Qwen3-VL 2B, full images, selected LoRA | 128/562 = 22.78% | not measured |

The later Gemma v2 dev tests, synthetic structured-tool tests and 50-problem vision reasoning tests are **not** additional full-validation rows. Their separate denominators are reported below. The structured prototype's 155/562 with fallback is not an independent model improvement.

Letter calibration with log probabilities is on the branch `experiment/letter-debias`. Its preliminary number was about 25% to 26%. Adding the 0.8B model's probabilities to the option prior did not help (26.9% against 27.6%).

## The option prior

Kangaroo options carry information. On the 1,305 train problems with five numeric options:

| Position of the option by size | Share of times it is the answer |
|---|---|
| Smallest | 8.7% |
| Second | 22.5% |
| Middle | 30.7% |
| Fourth | 26.5% |
| Largest | 11.6% |

Validation shows the same pattern (9.6%, 25.5%, 28.5%, 25.5%, 10.9%). An option whose number already appears in the problem text is the answer less often (16.9% against 20.3%).

`copilot/option_prior.py` scores each letter with these features plus a letter frequency, fitted on train by `tools/fit_option_prior.py`. Train accuracy is 28.2% and validation is 27.6%, so it is not fitted to validation.

Limits: it only knows something when the options are numbers (239 of 562 validation problems). With other options it uses the letter frequency, and with no options it answers D.

## Model benchmark

`tools/bench_models.py` answers the 339 validation problems that have options, in three modes:

- **letter**: one letter with no working, the baseline prompt.
- **think**: working that fills the board's time for that model and that problem, then `Answer: X`.
- **free**: up to 300 tokens of working with no time limit. It shows what the model could do if the board were faster.

| Model | File | One letter | Think, within 60 s | Free working | Board time for free working |
|---|---|---|---|---|---|
| Qwen3.5 0.8B (Q8) | 0.8 GB | 22.7% | 25.0% (100) | 23.8% (80) | 62 s |
| Gemma 3 1B (Q8) | 1.0 GB | 21.2% | 24.0% (100) | 25.0% (80) | 72 s |
| LFM2 1.2B (Q8) | 1.2 GB | 23.0% | **27.0% (100)** | 30.0% (80) | 78 s |
| Qwen2.5-Math 1.5B (Q8) | 1.5 GB | 20.4% | 19.0% (100) | 22.5% (80) | 122 s |
| Qwen3.5 2B (Q4) | 1.3 GB | 24.2%, 14% too slow | no time to write | 23.9% (67) | 141 s |
| Phi-4-mini 3.8B (Q4) | 2.3 GB | 26.3%, 99% too slow | not run | 32.5% (80) | 195 s |
| Qwen3.5 4B (Q4) | 2.8 GB | 26.8%, all too slow | not run | 41.9% (62, stopped early) | 311 s |

The number in brackets is how many problems the mode ran on. The option prior scores 28.6% on the same 339 problems and 25% to 26% on the smaller samples. With 80 to 150 problems one standard error is 4 to 5 points.

A first run lost part of the think and free answers: the call for the final letter allowed 6 tokens, which cut `Answer: X` for some models (up to half of the answers of LFM2 and Qwen2.5-Math). The table has the numbers after the fix. Gemma 3 1B, Qwen3.5 2B, and Phi-4-mini were not affected; Qwen3.5 0.8B lost about 5%.

After the fix, **LFM2 1.2B is the best small model with working in this original benchmark: 27.0% within the estimated board time, against 25.0% for the prior on the same 100 problems.** That is inside the noise. LFM2 remained an untested fine-tuning candidate; it was not one of the later trained models below.

**How the board time is estimated.** The laptop is much faster than the board, so time is not measured. The README gives the 0.8B model's speed on the board (reads 11.3 tokens per second, writes 5.9). The laptop measures every model on 4 CPU threads, and each model's ratio to the 0.8B model is applied to the board's numbers. For example the 2B model reads about 2.9 tokens per second on the board by this estimate, so a 200-token problem takes about 70 seconds to read. Bigger models are probably even slower on the board than this. Measure a model on the board before choosing it.

## Why written working does not help the small model

We read the 0.8B model's solutions. Four causes:

1. **The problems need an idea, not a calculation.** The model starts correctly and then guesses.
2. **It misreads the problem** and solves a different one.
3. **It runs out of tokens.** With 160 tokens of working, 59% of the solutions were cut before the end. The board writes 6 tokens per second, so there is no room for more.
4. **Some problem texts are damaged by OCR**, and many problems need a picture that the model does not see.

The wrong options of a Kangaroo problem are typical mistakes. When the 0.8B model computed a number, it matched one of the options 56% of the time, but it was the right option only 18% of the time. Working makes the small model more confident, not more correct.

For the Teach track, saved wrong solutions can be candidates for a reviewed "find the mistake" exercise. They are not checked reference solutions or evidence that the model can correctly diagnose a student's mistake.

## What did not help

So that nobody repeats it:

- A bigger model answering one letter (2B: 24.7%).
- Retrieved examples in the prompt, with 1 example (23.0%) or 3 (23.6% on half of validation). Only 10 of the 281 validation problems have a near copy in train, so better embeddings would not change this.
- "Solve, write a number, match it to the options" with the 0.8B model.
- Voting between the English and Catalan version of a problem with the 0.8B log probabilities (23.5%).
- More features in the option prior (sum, difference, or product of numbers in the text; option length): 28.3%, inside the noise.
- Translation to English was not tested as an intervention in the original benchmark. Similar aggregate language scores there did not establish that translation cannot help.

## Follow-up experiments, 14–15 November

The following tests extend the original research above. Full validation, internal dev, training-set diagnostics and synthetic tasks are kept separate. Unless stated otherwise, the follow-ups ran on the Apple M3 laptop, not the UNO Q.

### 1. Gemma 3 1B answer-letter fine-tune

Used the existing 2,932 M3Kang training rows and 562 validation rows, with no AQuA and no teacher solutions. The internal split kept translations together: 2,786 train and 146 dev rows. The model received the same text/OCR prompt as `predict.py` and learned the reference letter.

QLoRA on a 4-bit base used rank 8 across all 26 layers. An initial stock-trainer pilot was stopped at step 30 and discarded. The subsequent run stopped at step 430 of 697 because dev loss worsened; the selected checkpoint was step 200, chosen on dev before validation. The stock trainer's dev batching scored 144 of the 146 rows. Completion loss fell substantially, but the selected model answered D whenever OCR options were present and A whenever they were absent.

| Evaluation scope | Before | After |
|---|---:|---:|
| All original validation rows | 105/562 = 18.68% | 108/562 = 19.22% |
| Validation rows with OCR options | 67/339 = 19.76% | 72/339 = 21.24% |

The +3-answer difference did not establish useful improvement. Export to Q8_0 GGUF preserved all 562 MLX predictions; official evaluation completed with 562 `ok` statuses. The export started from an already 4-bit base, so Q8 export did not recover the original unquantized precision. The model was not promoted.

Details, grouped bootstrap, artifacts and reproduction: [GEMMA_M3KANG_FINETUNE.md](GEMMA_M3KANG_FINETUNE.md).

### 2. Gemma v2: memorization, letter loss and solution supervision

The follow-up used accuracy for checkpoint selection and a lower effective LoRA scale of 2. Letter-only loss was calculated among A–E rather than dominated by formatting tokens.

| Test and scope | Before | After / selected checkpoint |
|---|---:|---:|
| Train memorization diagnostic, 100 training tasks | 17/100 | 96/100 |
| Letter-only internal dev, 64 tasks | 20/64 = 31.25% | Best 20/64 = 31.25%; all D. Last checkpoint: 9/64 |
| Short solution then separate letter request, another internal dev of 63 tasks | 11/63 = 17.46% | 8/63 = 12.70%, step 333 |
| Small dev subset with checked calculations, 13 tasks | 3/13 | 2/13 |

Memorization proved that parameter updates could learn specific examples; it did not prove transfer to unseen problems. The 64-task dev later revealed one exact training duplicate under a different ID, so that diagnostic was not fully independent. The subsequent 63-task solution dev excluded that duplicate.

Solution training used 1,329 examples: 925 short AQuA solutions and 404 prompt variants of 101 M3Kang tasks with answer-option permutations. Assistant-written M3Kang calculations were checked by arithmetic/enumeration, but were not an expert-verified solution corpus; AQuA solutions were not independently rechecked. Later visual auditing found one ambiguous M3Kang example with damaged exponent notation.

After solution training, 59/63 dev outputs contained an `Answer:` marker, but only 7/63 extracted final answers were correct. The primary before/after metric in the table used the same separate letter request in both runs. Learning the output format did not establish mathematical accuracy.

The user stopped the run: last logged step 510/666, last measured saved checkpoint step 333. No complete v2 full-validation score or v2 GGUF export exists. A stricter 100-task M3Kang-only solution dataset was prepared but **not trained**. The planned 20,000-example AQuA PC run is not one of these completed experiments.

**Data/OCR audit:** inspected source images showed some train-label inconsistencies and damaged mathematical notation. Their overall prevalence was not measured. A separate OCR version supplied options for 434/562 rows instead of 339/562. The old prior weights then scored 133/562; fitting new weights on that OCR's train data scored 123/562, both below the original 155/562. These OCR data/weights were not promoted.

Details and stopped-run artifacts: [GEMMA_V2_CONCLUSIONS.md](GEMMA_V2_CONCLUSIONS.md).

### 3. Gemma plus structured, independently checked calculations

The prototype asked Gemma to propose a restricted expression or named operation. Python executed allowed operations; a separate narrow template checker decided whether the plan matched the condition. Successful arithmetic alone was not accepted as proof of a correct interpretation. No new training was done. An initial free-expression development pilot got 1/5 right and confused steps or quantities; the format was then narrowed to named operations before the main tests.

| Synthetic diagnostic only, 60 generated tasks | Result |
|---|---:|
| Existing option prior | 30/60 = 50% |
| Direct base Gemma | 13/60 = 21.7% |
| Proposed plan produced a value matching one option | 35 candidates, 33 correct |
| Independently verified Gemma plans | 32 accepted out of 60; all 32 correct |
| Verified Gemma plans plus old fallback | 45/60 = 75% |
| Deterministic templates plus old fallback | 57/60 = 95% |

The 32 correct accepted answers are **coverage and precision on accepted synthetic examples**, not 100% accuracy on all 60 or a score on M3Kang. These generated tasks were designed around the supported arithmetic templates.

On the **real 562-row M3Kang validation**, the input gate attempted 178 text-only rows with five OCR options and skipped 384 other rows. Among attempts, 100 plans were rejected, 77 computed candidates remained semantically unverified, and the model declined once. Eight unverified values matched an option; only two matched the gold answer. **Zero plans passed independent verification: verified coverage 0/562.** Direct Gemma scored 46/178 on that restricted subset, not on all validation.

The combined system scored 155/562 = 27.58% because the old fallback answered every unverified/skipped case. Without fallback, the prototype did not answer every example, so its full forced-choice accuracy was **not measured**. The combined score must not be attributed to a new mathematical solver.

Seventeen tests covered arithmetic, fractions, rejected programs, invented numbers, wrong semantics, units and student-step checks. This established behavior within the narrow checker, not general reasoning or reliable student feedback.

Details, raw paths and explicit no-fallback correction: [STRUCTURED_REASONING_RESULTS.md](STRUCTURED_REASONING_RESULTS.md).

### 4. Qwen3-VL 2B: full-image fine-tune

To remove the missing-diagram/option input problem, exported all source images corresponding to the original train and validation JSONL. Each input contained the complete question, all choices and any diagram; no row was excluded because OCR options were empty or a figure was required. M3Kang supplies labels, not reference solution traces or student-error explanations.

Four audited inconsistent/damaged training IDs, eight language rows, were quarantined. The remaining internal split had 2,632 train images and 292 dev images. All 562 original validation rows and labels were preserved in order. Translations and exact duplicate input groups stayed together, with no train/dev/validation group overlap.

The 4-bit Qwen3-VL-2B-Instruct base received images at a 384-visual-token budget, with aspect-preserving resizing and no cropping. LoRA trained q/k/v/o projections in the last eight language layers: rank 8, alpha 16, effective scale 2, 917,504 trainable parameters. The vision encoder and first 20 language layers were frozen and their outputs cached. Label-only cross-entropy used A–E; labels and audit text were excluded from image prompts.

A small input-format pilot on the same 16 internal-dev rows scored 2/16 for image-only and 2/16 for image plus existing OCR text/options. This was not a full validation run and is too small to establish that OCR assistance generally cannot help; the subsequent training used image-only input. The pilot is saved in `results/multimodal/input-audit.json`.

| Internal dev checkpoint | Correct | Always D on the same dev |
|---|---:|---:|
| Base | 38/292 = 13.01% | 84/292 = 28.77% |
| Epoch 1, step 329, selected | 85/292 = 29.11% | 84/292 = 28.77% |
| Epoch 2, step 658 | 84/292 = 28.77% | 84/292 = 28.77% |

Two complete epochs finished. A partial third epoch was stopped and discarded after the dev decline; the last logged training step was 670. The epoch-1 checkpoint was selected solely on dev and reloaded for a direct, uncached image pass over **all 562 validation rows**:

- Before: **114/562 = 20.28%**; after: **128/562 = 22.78%**; processing failures: **0**; answer fallback: **none**.
- Net gain: 14 answers, +2.49 percentage points. Of paired predictions, 117 became right and 103 became wrong.
- Still below always D (130/562 = 23.13%) and the original prior (155/562 = 27.58%).
- English: 58/281 → 62/281. Catalan: 56/281 → 66/281. Text-only: 54/246 → 51/246. With figures: 60/316 → 77/316.
- After-training letter counts: A 0, B 5, C 162, D 350, E 45. Strong letter bias remained.

Training mechanics were checked: four diagnostic updates on four train examples reduced loss from 3.70 to 0.60; checked frozen-prefix/full-forward and save/reload A–E logits had maximum difference 0.0. Those are implementation checks, not evidence of generalization. The full after-training validation took 612.76 seconds on Apple M3, not UNO Q. The MLX adapter was retained for research; it was not exported to GGUF or deployed after this negative result.

Details, dataset audit, per-level metrics and reproduction: [VISION_FINETUNE_RESULTS.md](VISION_FINETUNE_RESULTS.md).

### 5. Qwen3-VL 2B: generate a solution before the final letter

Tested the **unadapted base**, not the letter-trained LoRA, on a fixed internal-dev subset of 50 unique IDs: 25 English and 25 Catalan, 26 text-only and 24 with figures, spanning all eight levels. Seed `20261115` fixed the sample without selecting by labels or OCR success. No fine-tuning was done.

All modes received the same complete images at the same 384-visual-token budget. Reasoning had up to **768 generated tokens**, followed by the same model's separate argmax A–E request on every example. This final request was not an external answer fallback. A 384-generation-token pilot was stopped after output truncation and kept separate from these complete runs.

| Same 50 internal-dev problems | Correct | Reached 768-token solution limit |
|---|---:|---:|
| Immediate letter | 7/50 = 14% | n/a |
| Solution then letter, temperature 0 | 13/50 = 26% | 41/50 |
| Solution then letter, checkpoint sampling | 10/50 = 20% | 40/50 |
| Always D | 17/50 = 34% | n/a |

Checkpoint sampling used temperature 0.7, top_p 0.8, top_k 20 and a fixed per-row seed. Both runs processed all 50 examples with zero errors. Primary direct answers matched the earlier base-model dev predictions, and the sample/labels matched between runs. Counting only a generated explicit `Final answer: X`, with absent markers counted wrong, gave 8/50 and 7/50 respectively; reporting only the successful completed subset would overstate accuracy.

Manual review of ten wrong answers and their images found wrong visual counts, omitted algebraic factors, incorrect constraints, repeated restatements and failure to map a correctly computed value to its letter. One repetitive sampling answer was reproduced exactly after a fresh model load without prior direct requests, ruling out carried-over request state for that case. Reaching the token cap alone is not proof of repetition or of a wrong solution.

Mean solution-plus-letter time on Apple M3 was 11.84 seconds at temperature 0 and 13.28 seconds with sampling. This was not a controlled board-speed benchmark. Neither mode beat always D on the same sample. No new training or subsequent full-validation run was started. **These percentages are not accuracy on the original 562-row validation and cannot be compared directly with its 27.58% prior score.**

Details, ten-case audit, per-level counts, decoding parameters and reproduction: [VISION_REASONING_RESULTS.md](VISION_REASONING_RESULTS.md).

## Current status and untested next steps

1. **No follow-up established a useful replacement for the original option prior.** More training of the same configurations is stopped. The checkpoints and raw measurements are retained; none of the new models was promoted to the working pipeline.
2. **Correct student feedback remains unverified.** Neither answer-letter accuracy, lower training loss, accepted synthetic examples nor a long generated explanation proves that a model can diagnose a student's mistake. Verified solution traces and student-step/error examples would be a different training target and require their own held-out evaluation. This is a possible future direction, not a measured successful result.
3. **Recheck quality after any input/data change, then measure on the actual board before deployment.** More OCR coverage did not automatically improve the prior, and the new vision measurements do not certify memory or the 60-second UNO Q limit. The older [FINETUNE_PC.md](FINETUNE_PC.md) recipe is retained as a proposed route, not an active or completed 20,000-example training job.

## How to reproduce

```bash
# the option prior: fit on train, report on val, then the official evaluation
python3 tools/fit_option_prior.py --save
ANSWER_MODE=prior python3 eval.py --limit 0 --name option-prior

# the model benchmark (downloads each model, answers on the laptop GPU, 6 problems at a time)
python3 tools/bench_models.py --models qwen35-0.8b,gemma3-1b --gpu --jobs 6 --sample 100
python3 tools/bench_models.py --report

# fine-tuning data, in the prompt format of predict.py (written under data/, never commit it)
python3 tools/make_finetune_data.py --aqua 0

# full-image candidate: full original validation, no answer fallback
.venv-vlm/bin/python tools/eval_multimodal.py \
  --adapter models/m3kang-vision-lora/best --out results/multimodal/reproduced-after-val

# paired reasoning diagnostic: same 50 internal-dev problems, not full validation
.venv-vlm/bin/python tools/bench_multimodal_reasoning.py \
  --n 50 --seed 20261115 --max-tokens 768 --temperature 0 \
  --out results/vision-reasoning/reproduced-greedy
.venv-vlm/bin/python tools/bench_multimodal_reasoning.py \
  --n 50 --seed 20261115 --max-tokens 768 --temperature 0.7 \
  --out results/vision-reasoning/reproduced-sampling
```

The original `tools/finetune_lora.py` needs a Python environment with `torch`, `transformers` and `peft`. The newer Apple Silicon training/image tools use separate MLX environments; the vision environment is pinned in `requirements-vlm.lock.txt`. See each linked report for its exact data, model and command requirements. Datasets, images, model weights and raw generated solutions are not committed.
