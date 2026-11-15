# Letter scoring: model + option prior

Branch: `experiment/letter-scoring`. Status: measured offline on a laptop, not yet confirmed with `eval.py` on the board.

## The idea

Two ways to pick the letter already existed on `main`, each using half of the evidence:

- `copilot/debias.py` reads the model's log probability for each letter A to E and removes its letter bias. It reads the problem, but the 0.8B model is weak at math.
- `copilot/option_prior.py` scores the options alone: the smallest and the largest numbers are rarely right, the middle one often is. It never reads the question.

`copilot/combine.py` adds them into one score per letter:

```
score(L) = logp(L) + bias(L) + weight * prior(L)
```

- `logp`: the model's log softmax over the five letters, after the prefill "The correct option is" (one forward pass, the same request as `debias.py`).
- `bias`: one number per letter, fitted so that the predicted letters are as frequent as the true ones on train.
- `prior`: `option_prior.scores()`.
- `weight`: how much the prior counts against the model. 0 is the model alone. The prior mostly decides when the model hesitates.

Problems without five options get the prior's answer, with no model call. Turn it on with `ANSWER_MODE=combined` in `config.env`.

## How the numbers are fitted

1. `tools/collect_letter_probs.py` asks the model once per problem and caches the five letter log probabilities in `results/letters-{train,val}.jsonl` (ids and numbers only). This is the slow step: about 1 hour on a laptop for train and val.
2. `tools/fit_combine.py` tries weights from 0 to 4. For each one it fits the letter bias, then keeps the weight with the lowest log loss on train. Train accuracy is almost flat across weights, so it is too noisy to choose by. Val is only reported.
3. `--save` writes `copilot/combine.json`: weight 0.75, plus the bias.

## Results

Data: `prepare_m3kang.py --languages eng,cat --text-only` (the version on `feature/demo-test-set`), shard 0 of `high_quality`. Train has 1,376 rows (1,255 with five options), val 246 (210 with five options). Model: Qwen3.5 0.8B Q8_0, run with `llama-server` on a laptop.

Val, the 210 rows with five options:

| Way to answer | Accuracy | eng | cat |
| --- | --- | --- | --- |
| Always D | 21.9% | 21.9% | 21.9% |
| Option prior only | 25.7% | 25.7% | 25.7% |
| Model, raw argmax | 25.7% | 25.7% | 25.7% |
| Model, letter bias removed | 25.2% | 28.6% | 21.9% |
| **Model + prior, weight 0.75** | **33.8% (71/210)** | **37.1%** | **30.5%** |

Every weight from 0.25 to 4 beat both single methods on val (29% to 34%). The raw model answers D on 142 of 210 rows. In the official run, Catalan problems are answered through their English version (`copilot/bridge.py`), so the English number is closer to what to expect there.

**What to expect on new problems: about 29%, not 34%.** On train, six times bigger than val, the combined score gets 28.7% (model alone, letter bias removed: 25.3%). The 33.8% on val is probably partly luck in a small set. The gain over the option prior alone and over always D holds on both.

### Tried and dropped: asking twice with the options reversed

A second pass shows the options in reverse order (the value under A goes under E), and the two passes are averaged by value, so a taste for one letter pushes two different values and cancels out. It needs a second forward pass. Fitted the same way on the same rows:

| Val, same 210 rows | One pass | Two passes |
| --- | --- | --- |
| Model alone, letter bias removed | 25.2% | 24.8% |
| Model + prior | **33.8%** | 26.7% (weight 1.0) |
| Train accuracy, model + prior | 28.7% | 28.6% |

The reversal did remove the letter habit (the answers spread evenly over A to E), but the model got no better: most of what it "knew" was the habit. On train both versions are equal, so it doubles the time for nothing. We kept one pass.

## Limits

- It is an educated guess, not reasoning. It can't explain an answer to a student. Teaching features need verified explanations, for example a formula checked by Python, or solutions written offline and checked against the label.
- About 1 point per 2 problems: on 210 rows, differences under about 3 points are noise.
- The OCR misreads stacked fractions (1/5 becomes `115`), so the option prior sees wrong numbers on some fraction problems.

## Reproduce

```bash
python3 tools/collect_letter_probs.py --input data/val.jsonl --output results/letters-val.jsonl
python3 tools/collect_letter_probs.py --input data/train.jsonl --output results/letters-train.jsonl
python3 tools/fit_combine.py --save
```

Then on the board, with `ANSWER_MODE=combined`: `python3 eval.py --name letter-scoring`.

## Next

- Confirm on the board with `ANSWER_MODE=combined` and `eval.py --name letter-scoring`, for the official time per problem.
- For explanations a student can use, try a formula written by the model and checked by Python. It would also give the official run real reasoning instead of a better guess.
