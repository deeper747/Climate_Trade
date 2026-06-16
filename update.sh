#!/usr/bin/env bash
# update.sh — fetch latest trade data and redeploy the dashboard to GitHub Pages
#
# Usage:  ./update.sh
# Needs:  CENSUS_API_KEY in .env, Python venv at .venv/

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV" ]]; then
  echo "ERROR: virtualenv not found at .venv/. Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "=== Step 1: Fetch EU trade data from Eurostat Comext ==="
"$VENV" python/fetch_eu_trade_raw.py

echo ""
echo "=== Step 2: Fetch US trade data from Census Bureau ==="
"$VENV" python/fetch_us_trade_raw.py

echo ""
echo "=== Step 3: Build docs/data/trade_data.json ==="
"$VENV" python/build_data.py

echo ""
echo "=== Step 4: Commit and push ==="
TODAY="$(date +%Y-%m-%d)"
git add docs/data/trade_data.json
git commit -m "data: update trade data ${TODAY}" || echo "(nothing to commit)"
git push

echo ""
echo "Done — dashboard will update at https://deeper747.github.io/Climate_Trade/ within a few minutes."
