#!/usr/bin/env bash
# Phase 0 setup: git baseline commit + data backup.
# Assumes bash (WSL / Linux / macOS / Git Bash). Run from the project root.
set -euo pipefail

cd "$(dirname "$0")"

echo "== Backing up data/ =="
if [ -d data ]; then
    backup_dir="_backup/data_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r data/. "$backup_dir/"
    echo "  Backed up data/ -> $backup_dir"
else
    echo "  No data/ directory found -- skipping."
fi

echo
echo "== Git baseline =="
if [ -d .git ]; then
    echo "  .git already exists -- skipping 'git init'."
else
    git init
fi

if ! grep -qxF ".env" .gitignore 2>/dev/null; then
    echo "ERROR: .env is not in .gitignore. Refusing to commit until it is."
    echo "       (This is exactly the mistake that leaked keys before -- see I-17.)"
    exit 1
fi

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "ERROR: .env is already tracked by git. Remove it first:"
    echo "       git rm --cached .env"
    exit 1
fi

git add -A

# Defense in depth: even with .gitignore excluding .env*, double-check nothing
# that LOOKS like a secrets file got staged anyway (e.g. a future backup-file
# naming pattern .gitignore doesn't know about yet). This is exactly the
# failure mode that committed .env.backup / .env.backup-messy /
# .env.broken-backup into git on an earlier run of this script (I-17) --
# .gitignore only excluded ".env" exactly, not ".env.*" variants.
staged_secrets=$(git diff --cached --name-only | grep -E '(^|/)\.env(\.|$)' | grep -v '\.env\.example$' || true)
if [ -n "$staged_secrets" ]; then
    echo "ERROR: file(s) that look like secrets are staged for commit:"
    echo "$staged_secrets" | sed 's/^/       /'
    echo "       Unstage everything, fix .gitignore to cover them, then re-run:"
    echo "         git reset"
    exit 1
fi

if git diff --cached --quiet; then
    echo "  Nothing to commit (working tree already matches HEAD)."
else
    git commit -m "Baseline before refactor (Phase 0)"
fi

if git rev-parse baseline-v0 >/dev/null 2>&1; then
    echo "  Tag 'baseline-v0' already exists -- leaving it alone."
else
    git tag baseline-v0
    echo "  Tagged current commit as baseline-v0."
fi

echo
echo "== Disk usage of things Step 1.9 will clean up =="
du -sh downloades vector_db data/frames 2>/dev/null || true

echo
echo "Done. Next: python check_env.py, then run SMOKE_TEST.md against baseline-v0."
