# CLAUDE.md

Rules for Claude in this repository. Several team members work on it in parallel, each with their own Claude session. Follow these rules in every session. Human workflow details are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Language

- Everything written into the repository is in **English**: code, comments, docstrings, commit messages, branch names, PR titles and descriptions, Markdown files, log messages, and UI text.
- This holds even when the person you're talking to writes in another language. Answer them in their language in chat, but write files and git messages in English.
- If you find non-English text in a tracked file, point it out and offer to translate it.
- M3Kang problem text in other languages is data, not repository text. It stays as it is.

## Branches

- Never commit directly to `main`. Every new feature, experiment, or fix goes on its own branch, created from an up-to-date `main`:
  ```bash
  git switch main && git pull --ff-only && git switch -c <type>/<short-name>
  ```
- Branch name prefixes: `feature/`, `experiment/`, `fix/`, `docs/`, `ui/`. Use lowercase words joined by hyphens, for example `feature/hint-ladder` or `experiment/rag-k3`.
- One branch, one topic. If a request is about a different topic than the current branch, ask whether to start a new branch before changing anything.
- Before starting work, run `git status` and `git branch --show-current`. If the working tree has changes you didn't make in this session, stop and ask. They may belong to a teammate or to another branch.

## Before any push: always ask

- **Never run `git push` without asking the user first, and wait for an explicit yes.** Approval for one push doesn't cover the next one.
- Before asking, show:
  1. The current branch and the remote branch it will push to
  2. `git log --oneline origin/main..HEAD`, the commits that will be pushed
  3. `git diff --stat origin/main...HEAD`
  4. The result of `git fetch origin` and whether `main` moved since the branch was created (if it did, offer to rebase or merge `main` first)
- Never push to `main`. Never use `git push --force` or `--force-with-lease`. Never delete remote branches. Never rewrite history that's already pushed.
- Merges into `main` happen only through pull requests that a teammate reviews.

## Don't overwrite teammates' work

- Don't edit files outside the scope of the current task. Shared files cause most conflicts. Change them in small, separate commits and say so in the PR:
  - `config.env` (ports, models, run rules, used by everyone)
  - `predict.py` and `eval.py` (the official contract and the measurement script)
  - `copilot/pipeline.py`, `copilot/config.py`
  - `README.md`
- Prefer adding a new module (for example `copilot/hints.py`) over rewriting a shared one.
- If a merge or rebase conflict appears, don't resolve it by picking one side wholesale. Show the conflicting hunks and ask.
- Don't run `git reset --hard`, `git checkout -- .`, `git clean`, or `git stash drop` without asking.

## Data and secrets

- M3Kang is for research use only. Never commit `data/*.jsonl` (except `data/sample_problems.jsonl`), `data/images/`, `data/index.db`, `*.gguf`, or anything in `results/` except `.gitkeep`.
- Never commit secrets: tokens, Wi-Fi passwords, the board's password, or IP addresses of team laptops.

## The shared board

The team may share one Arduino UNO Q. Treat it like a shared server:

- Ask before restarting or stopping the model services (`llama-llm`, `llama-embed`) or rebooting the board. Other people may be running an evaluation.
- Each person works in their own clone on the board, for example `~/work/<name>/`, never in someone else's folder.
- Name evaluation runs after the branch, for example `python3 eval.py ... --name hint-ladder`, so `results/ablations.csv` shows who ran what.
- Commit before each evaluation, so the commit in `ablations.csv` points at the code that made the number.

## Skills

The project skills are in `.skills/` (linked from `.claude/skills`). Use them:

- `unoq-board` for anything that runs on the board
- `m3kang-copilot` for changes to the copilot, experiments, and error analysis
- `unoq-hardware-ui` for the App Lab app, web page, and LED matrix
- `publish-project` for the README, the public repository, and Arduino Project Hub
