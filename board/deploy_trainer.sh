#!/usr/bin/env bash
# Copy the trainer to the board and start its web page there. Run it on the laptop:
#
#   board/deploy_trainer.sh 192.168.1.131
#
# It copies the code (no Git history), data/train.jsonl and data/map.db to
# ~/work/trainer on the board, then starts tools/dev_server.py on port 7000.
# The language model must already run on the board as the math-llm service
# (port 8081, README step 7). Stop the page with Ctrl+C.
set -euo pipefail

BOARD="arduino@${1:?usage: board/deploy_trainer.sh <board-ip>}"
cd "$(dirname "$0")/.."

for file in data/train.jsonl data/map.db; do
    [ -e "$file" ] || { echo "Missing $file. Build the map first: python3 tools/build_map.py --no-embed"; exit 1; }
done

echo "Copying the trainer to $BOARD:~/work/trainer"
ssh "$BOARD" "mkdir -p ~/work/trainer/data"
# -h follows the symlinks that a worktree uses for its data files
tar -chf - app copilot tools config.env data/train.jsonl data/map.db \
    --exclude '__pycache__' | ssh "$BOARD" "tar -xf - -C ~/work/trainer"

echo "Checking the language model on the board"
ssh "$BOARD" "curl -s --max-time 5 http://127.0.0.1:8081/health || echo 'NOT RUNNING: sudo systemctl start math-llm'"

echo
echo "Starting the page. Open http://${1}:7000 on a phone or laptop in the same network."
ssh -t "$BOARD" "cd ~/work/trainer && python3 tools/dev_server.py --host 0.0.0.0 --port 7000"
