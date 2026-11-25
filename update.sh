#!/usr/bin/env bash
# update.sh — refresh the dashboard data and redeploy to GitHub Pages
# Usage: ./update.sh
# Needs CENSUS_API_KEY in .env (hydrogen series comes from the U.S. Census API).
set -euo pipefail
cd "$(dirname "$0")"

DATA=docs/data/us_eu_cbam_cn_trade.json
BRANCH=$(git rev-parse --abbrev-ref HEAD)

python3 python/build_cn_trade.py

# Commit only if the data actually changed; any other commit failure stops the script.
git add "$DATA"
if git diff --cached --quiet -- "$DATA"; then
  echo "(data unchanged, nothing new to commit)"
else
  git commit -m "data: update trade data $(date +%Y-%m-%d)" -- "$DATA"
fi

# Push whenever the local branch is ahead of the remote, including commits left
# over from an earlier run that never got pushed.
git fetch -q origin "$BRANCH"
AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD")
if [ "$AHEAD" -gt 0 ]; then
  echo "Pushing $AHEAD commit(s) to origin/$BRANCH..."
  git push origin "$BRANCH"
else
  echo "(origin/$BRANCH already up to date)"
fi

# Confirm the remote now matches local.
git fetch -q origin "$BRANCH"
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$BRANCH")" ]; then
  echo "ERROR: origin/$BRANCH does not match local HEAD after push." >&2
  exit 1
fi

LAST=$(python3 -c "import json; print(json.load(open('$DATA'))['periods'][-1])")
echo "Done. origin/$BRANCH is at $(git rev-parse --short HEAD); latest month in data: $LAST."
echo "GitHub Pages usually redeploys within a few minutes."
