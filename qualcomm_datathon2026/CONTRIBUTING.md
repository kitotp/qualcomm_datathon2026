# Contributing

How our team works on this repository without overwriting each other's work. Claude follows the same rules, written for it in [CLAUDE.md](CLAUDE.md).

## The rules in short

1. **English only** in the repository: code, comments, commits, branches, PRs, and docs.
2. **Every feature on its own branch.** Nobody commits or pushes to `main`.
3. **Pull requests only.** A teammate reviews each PR before it's merged into `main`.
4. **Ask before you push** when Claude does it for you. Claude is set up to ask, so read what it shows before you say yes.
5. **Never force-push**, and never rewrite history that's already on GitHub.

## One-time setup

After you clone our team repository:

```bash
# Turn on the hook that blocks direct pushes to main
git config core.hooksPath .githooks

# Link the project skills for Claude Code (skip if .claude/skills already exists)
mkdir -p .claude && ln -s ../.skills .claude/skills
```

Note: the original repository, `mpous/datathon-UPC-maths-qualcomm-arduino-unoq`, belongs to the organizers. We push to our own fork. Check with `git remote -v` that `origin` points at the team fork.

We also recommend turning on branch protection for `main` on GitHub (Settings → Branches): require a pull request and one approval before merging.

## Daily workflow

### 1. Start a branch from an up-to-date main

```bash
git switch main
git pull --ff-only
git switch -c feature/hint-ladder
```

| Prefix | Use it for |
| --- | --- |
| `feature/` | A new teaching or reasoning feature |
| `experiment/` | An accuracy or latency experiment measured with `eval.py` |
| `fix/` | A bug fix |
| `ui/` | The App Lab app, web page, or LED matrix |
| `docs/` | README, write-up, or other documentation |

Use lowercase words joined by hyphens. Keep one topic per branch.

### 2. Commit small and often

```bash
git add <files>
git commit -m "Add a three-step hint ladder to the pipeline"
```

- Write the message in English, in the imperative ("Add", "Fix", "Measure").
- Use `git add <files>`, not `git add .`, so you don't commit data or results by accident.
- Commit before every evaluation run, so `results/ablations.csv` records the right commit.

### 3. Stay in sync with main

Before you push, and whenever a teammate merges something:

```bash
git fetch origin
git rebase origin/main     # only on a branch nobody else has pulled
# or
git merge origin/main
```

If there's a conflict you don't understand, ask the person who wrote the other side. Don't just keep your version.

### 4. Push your branch and open a PR

```bash
git push -u origin feature/hint-ladder
```

Then open a pull request into `main`. In the description, say:

- What changed, and why
- Which shared files you touched (see below)
- Results from `eval.py`, if the change affects accuracy or latency: accuracy, mean and worst latency, and the number of problems

Merge only after a teammate approves. Delete the branch after the merge.

## Shared files: handle with care

Changes to these files affect everyone. Keep them small, in separate commits, and mention them in the PR:

| File | Why it matters |
| --- | --- |
| `config.env` | Ports, models, and run rules for every script |
| `predict.py` | The official input/output contract used for scoring |
| `eval.py` | How we measure; changes make old results incomparable |
| `copilot/pipeline.py`, `copilot/config.py` | The core every feature builds on |
| `README.md` | The public face of the project |

When you can, add a new module (such as `copilot/hints.py`) instead of rewriting a shared one.

## Never commit

- M3Kang data: `data/*.jsonl` (except `data/sample_problems.jsonl`), `data/images/`, `data/index.db`. The dataset is for research use only.
- Models (`*.gguf`) and results (`results/*`)
- Secrets: tokens, Wi-Fi passwords, the board's password

`.gitignore` covers most of these, but check `git status` before each commit.

## Sharing the board

If we share one Arduino UNO Q:

- Each person works in their own clone on the board, in `~/work/<your-name>/`.
- Tell the team in chat before you restart the model services or reboot the board. Someone may be running an evaluation.
- Run one evaluation at a time. Two runs at once slow each other down and make the latency numbers wrong.
- Name runs after your branch: `--name hint-ladder`.
