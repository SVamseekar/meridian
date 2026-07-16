#!/bin/sh
# Installs repo git hooks from scripts/hooks/ into .git/hooks/
# .git/hooks/ is not tracked by git, so this must be run once after cloning.

set -e
repo_root=$(git rev-parse --show-toplevel)

for hook in "$repo_root"/scripts/hooks/*; do
  name=$(basename "$hook")
  cp "$hook" "$repo_root/.git/hooks/$name"
  chmod +x "$repo_root/.git/hooks/$name"
  echo "Installed $name"
done
