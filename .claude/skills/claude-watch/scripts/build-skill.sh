#!/bin/bash
# Package the claude-watch skill into an uploadable archive.
#
# Produces dist/claude-watch.zip — the folder you upload at
#   claude.ai -> Settings -> Capabilities -> Skills -> "+"
# (it also loads via `claude --plugin-dir dist/claude-watch.zip`).
#
# The archive contains a single top-level `claude-watch/` folder with SKILL.md
# at its root, which is what the Skills uploader expects.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../claude-watch
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
DIST="$REPO_ROOT/dist"
STAGE="$DIST/claude-watch"

rm -rf "$STAGE" "$DIST/claude-watch.zip"
mkdir -p "$STAGE"

# Copy the skill, excluding build/cache/vcs cruft.
( cd "$SKILL_DIR" && \
  find . \
    -path ./__pycache__ -prune -o \
    -name '*.pyc' -prune -o \
    -name '.gitignore' -prune -o \
    -type f -print ) | while read -r f; do
  dest="$STAGE/${f#./}"
  mkdir -p "$(dirname "$dest")"
  cp "$SKILL_DIR/$f" "$dest"
done

( cd "$DIST" && zip -q -r claude-watch.zip claude-watch )
rm -rf "$STAGE"

echo "Built: $DIST/claude-watch.zip"
unzip -l "$DIST/claude-watch.zip" | sed 's/^/  /'
