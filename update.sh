#!/usr/bin/env bash
# update.sh — refresh the dashboard data from Eurostat Comext and redeploy to GitHub Pages
# Usage: ./update.sh   (Python 3 standard library only; no API key needed)
set -euo pipefail
cd "$(dirname "$0")"
python3 python/build_cn_trade.py
git add docs/data/us_eu_cbam_cn_trade.json
git commit -m "data: update trade data $(date +%Y-%m-%d)" || echo "(nothing to commit)"
git push
