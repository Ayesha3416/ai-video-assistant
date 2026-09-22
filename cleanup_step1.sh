#!/usr/bin/env bash
# Step 1: cleanup only. No git init, no commit — just gets the working tree
# clean and safe. Run from the project root (~/projects/ai-video-assistant).
set -euo pipefail
cd "$(dirname "$0")"

echo "== Step 1 cleanup =="

# 1. Remove leaked-secret backup files (rotate the keys first if you haven't!)
for f in .env.broken-backup .env.backup-messy .env.backup; do
    if [ -f "$f" ]; then
        rm -f "$f"
        echo "  removed $f"
    fi
done

# 2. Remove the stale pre-refactor backup folder
if [ -d .backup-step1 ]; then
    rm -rf .backup-step1
    echo "  removed .backup-step1/"
fi

# 3. Remove __pycache__ everywhere
found_pycache=$(find . -type d -name "__pycache__" -not -path "./.git/*")
if [ -n "$found_pycache" ]; then
    find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
    echo "  removed __pycache__ directories"
fi

# 4. Remove Windows Zone.Identifier junk (from downloading via WSL/Windows)
found_zone=$(find . -name "*Zone.Identifier*" -not -path "./.git/*" || true)
if [ -n "$found_zone" ]; then
    find . -name "*Zone.Identifier*" -not -path "./.git/*" -delete
    echo "  removed *Zone.Identifier files"
fi

# 5. Clear the runtime log (keep the folder + a .gitkeep so logging still works)
if [ -f logs/app.log ]; then
    : > logs/app.log
    echo "  cleared logs/app.log"
fi

# 6. Remove any existing .git — nothing has been pushed anywhere, and old
#    commits may still contain the leaked .env.backup* files even after the
#    working-tree copies are deleted above (deleting a file doesn't remove it
#    from git history). Since there's no remote and no collaborators, the
#    simplest safe fix is to drop history and start clean rather than rewrite it.
if [ -d .git ]; then
    rm -rf .git
    echo "  removed .git (was never pushed anywhere — confirmed with user)"
fi

echo
echo "== Done. Nothing was committed to git in this step. =="
echo "Next: rotate your Groq / Sarvam / Mistral keys if you haven't yet,"
echo "then run: python check_env.py"
