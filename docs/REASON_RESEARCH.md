# Reason track: what we measured on 14 November

This is the state of the work on `predict.py` accuracy. Read the summary; the rest is the evidence.

## Summary

- **Best result so far: 27.6% on the full validation set (562 problems), with no language model.** The baseline is 23.1%, the same as always answering D.
- The 27.6% comes from an "option prior": when the five options are numbers, the smallest and the largest are rarely the answer. It answers in 0 seconds.
- **Every model that fits the board's 60 seconds scores below the prior**, with one letter or with written working. We tried five models from 0.8B to 2B.
- Models that do reason well enough (Phi-4-mini, Qwen3.5 4B: 33% to 35% with free working) would need 3 to 5 minutes per problem on the board.
- 223 of the 562 validation problems have no options read by OCR. On those, every method answers blind. Reading more options helps whatever else we do.
- **In progress:** fine-tuning the 0.8B model on M3Kang train. No result yet.

**Decision for the team:** make the option prior the default answer of `predict.py` (`ANSWER_MODE=prior` in `config.env`). It is in this branch but turned off.

## Results on the full validation set

All rows are `eval.py --limit 0` on the laptop, 562 problems, English and Catalan. One standard error is about 1.9 points, so differences under 3 points are noise.

| Run | Accuracy | Seconds per problem on the board |
|---|---|---|
| Always D | 23.1% | 0 |
| Baseline: Qwen3.5 0.8B, one letter | 23.1% | about 13 |
| Baseline + 1 retrieved example (RAG) | 23.0% | longer prompt |
| Qwen3.5 2B, one letter | 24.7% | about 48, some problems too slow |
| **Option prior, no model** | **27.6%** | 0 |

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
| Qwen3.5 0.8B (Q8) | 0.8 GB | 22.7% | 20.0% (150) | 21.0% (100) | 62 s |
| Gemma 3 1B (Q8) | 1.0 GB | 21.2% | 24.0% (100) | 25.0% (80) | 72 s |
| LFM2 1.2B (Q8) | 1.2 GB | 23.0% | 17.0% (100) | 22.5% (80) | 78 s |
| Qwen2.5-Math 1.5B (Q8) | 1.5 GB | 20.4% | 14.0% (100) | 12.5% (80) | 122 s |
| Qwen3.5 2B (Q4) | 1.3 GB | 24.2%, 14% too slow | no time to write | 23.9% (67) | 141 s |
| Phi-4-mini 3.8B (Q4) | 2.3 GB | 26.3%, 99% too slow | not run | 32.5% (80) | 195 s |
| Qwen3.5 4B (Q4) | 2.8 GB | 26.8%, all too slow | not run | 35.3% (34, still running) | 311 s |

The number in brackets is how many problems the mode ran on. The option prior scores 28.6% on the same 339 problems and 25% to 26% on the smaller samples. With 80 to 150 problems one standard error is 4 to 5 points.

**How the board time is estimated.** The laptop is much faster than the board, so time is not measured. The README gives the 0.8B model's speed on the board (reads 11.3 tokens per second, writes 5.9). The laptop measures every model on 4 CPU threads, and each model's ratio to the 0.8B model is applied to the board's numbers. For example the 2B model reads about 2.9 tokens per second on the board by this estimate, so a 200-token problem takes about 70 seconds to read. Bigger models are probably even slower on the board than this. Measure a model on the board before choosing it.

## Why written working does not help the small model

We read the 0.8B model's solutions. Four causes:

1. **The problems need an idea, not a calculation.** The model starts correctly and then guesses.
2. **It misreads the problem** and solves a different one.
3. **It runs out of tokens.** With 160 tokens of working, 59% of the solutions were cut before the end. The board writes 6 tokens per second, so there is no room for more.
4. **Some problem texts are damaged by OCR**, and many problems need a picture that the model does not see.

The wrong options of a Kangaroo problem are typical mistakes. When the 0.8B model computed a number, it matched one of the options 56% of the time, but it was the right option only 18% of the time. Working makes the small model more confident, not more correct.

The same finding is useful for the Teach track: the model falls into the same traps as students, and its saved wrong solutions are ready material for a "find the mistake" exercise.

## What did not help

So that nobody repeats it:

- A bigger model answering one letter (2B: 24.7%).
- Retrieved examples in the prompt, with 1 example (23.0%) or 3 (23.6% on half of validation). Only 10 of the 281 validation problems have a near copy in train, so better embeddings would not change this.
- "Solve, write a number, match it to the options" with the 0.8B model.
- Voting between the English and Catalan version of a problem with the 0.8B log probabilities (23.5%).
- More features in the option prior (sum, difference, or product of numbers in the text; option length): 28.3%, inside the noise.
- Translation to English was not tried: English and Catalan score the same with every model.

## What is next

1. **Fine-tune the 0.8B model** (it is the only one sure to fit the time limit). First on M3Kang train only, with the exact `predict.py` prompt, scored on validation. If that beats the prior, add 20,000 problems from AQuA-RAT (Apache 2.0, five options A to E, with written solutions) and solutions written by a bigger model for the train problems it gets right.
2. **Read more options.** The work on `feature/ocr-options` now moves accuracy directly. Rerun `tools/fit_option_prior.py --save` after the data changes.
3. **Confirm timing on the board** for whatever replaces the baseline.

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
```

`tools/finetune_lora.py` needs its own Python environment with `torch`, `transformers`, and `peft`. Everything else uses the standard library.
