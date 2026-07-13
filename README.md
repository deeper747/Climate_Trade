# US–EU CBAM Trade Monitor

Monthly trade flows in CBAM-regulated sectors (iron & steel, aluminum, cement, fertilizers, ammonia, hydrogen) between the US and EU, with the EU's own import data from Eurostat as a cross-check, plus a forward-looking projection of the CBAM charge US exporters would face as free-allocation phases out. Built for the Niskanen Center.

**Live dashboard:** [deeper747.github.io/Climate_Trade](https://deeper747.github.io/Climate_Trade/)

---

## How the project works

```
US Census Bureau API ──┐
                       ├──► python/build_data.py ──► docs/data/trade_data.json
Eurostat Comext     ───┘                                       │
                                                               ▼
                                                     docs/index.html (GitHub Pages)
                                                               │
                                                               ▼
                                            User's browser fetches trade_data.json on load,
                                            then computes CBAM cost projections client-side
```

The whole thing is a **static site on GitHub Pages** — no backend. A Python script pulls two trade APIs and writes a single JSON file; the dashboard is one self-contained HTML page that fetches that JSON and renders everything (including the CBAM cost model) in the browser.

**Two data sources** are pulled on each update:

| Source | What it provides | Script |
|--------|-----------------|--------|
| US Census Bureau International Trade API | Monthly US exports/imports by HS6 code and partner country (2019–present) | `python/build_data.py` |
| Eurostat Comext DS-045409 | Monthly EU27 imports from the US by CN code (2022–present) | `python/build_data.py` |

`build_data.py` aggregates both into a single `docs/data/trade_data.json`. The dashboard fetches that file on every page load. The CBAM cost projection (2026–2034) is calculated in the browser from the trade values, EU ETS product benchmarks, and a declining free-allocation factor — the reference values for that model live in `reference/cbamBenchmarks.js` and are inlined into `docs/index.html`.

---

## Updating the data (one command)

```bash
./update.sh
```

This runs four steps in sequence:

1. `fetch_eu_trade_raw.py` — pulls annual EU bilateral trade from Eurostat Comext → `data/raw/eu_trade_hard_to_abate_partner_raw.csv`
2. `fetch_us_trade_raw.py` — pulls annual US bilateral trade from Census Bureau → `data/raw/us_trade_hard_to_abate_partner_raw.csv`
3. `build_data.py` — calls both APIs for the full monthly time-series, writes `docs/data/trade_data.json`
4. `git commit` + `git push` — deploys the updated JSON to GitHub Pages

A cloud routine (via Claude Code) opens a GitHub issue on the 15th of each month as a reminder to run this.

**Requires:** `CENSUS_API_KEY` in a `.env` file at the project root, and a Python venv at `.venv/`. The Eurostat API needs no key.

```
CENSUS_API_KEY=your_key_here
```

---

## Repository structure

```
python/
  build_data.py                 # MAIN pipeline: Census + Comext APIs → docs/data/trade_data.json
  fetch_eu_trade_raw.py         # Annual EU bilateral trade from Eurostat Comext → data/raw/
  fetch_us_trade_raw.py         # Annual US bilateral trade from Census Bureau → data/raw/
  comtrade_query_restored.py    # Standalone UN Comtrade fetcher (legacy source, not in the main
                                #   pipeline; needs COMTRADE_API_KEY). Kept for historical pulls.

data/
  raw/
    eu_trade_hard_to_abate_partner_raw.csv        # EU bilateral trade by partner/sector/year (EUR)
    us_trade_hard_to_abate_partner_raw.csv        # US bilateral trade by partner/sector/year (USD)
    us_eu27_trade_raw.csv                         # US→EU27 trade by HS6 code
    comext_us_cbam_trade.csv                      # CN-level Comext snapshot (monthly)
    comext_us_cbam_trade_by_year.csv              # CN-level Comext snapshot (annual)
    us_exports_hard_to_abate_comtrade_v1_raw.csv  # Legacy UN Comtrade pull (from comtrade_query)
  processed/
    eu_trade_hard_to_abate_partner.csv            # Cleaned EU trade data
    us_exports_hard_to_abate_top3_partners.csv    # US exports, top-3 partners per sector
    wb_exports_2023_datawrapper.csv               # 2023 world-bank-style export table for Datawrapper

docs/                                             # ← GitHub Pages root
  index.html                    # The dashboard: self-contained, fetches trade_data.json on load
  data/
    trade_data.json             # LIVE data file the browser loads (produced by build_data.py)
    eu_trade.json               # legacy — from an earlier pipeline, no longer generated or used
    us_trade.json               # legacy
    us_eu_trade.json            # legacy
  Niskanen Center_RGB_Logo White.svg              # Dashboard logo

reference/
  cbamBenchmarks.js             # EU ETS product benchmarks + CBAM free-allocation factors
                                #   (source of truth for the dashboard's cost projection)

cbam-trade-dashboard.html       # Standalone single-file snapshot of the dashboard (self-contained)
figs/                           # Exported figures (currently empty)
update.sh                       # One-command update + deploy
requirements.txt                # Python deps (note: streamlit listed is legacy; app was removed)
```

> **Note on the legacy JSONs:** only `docs/data/trade_data.json` is produced by the current pipeline and read by the dashboard. `eu_trade.json`, `us_trade.json`, and `us_eu_trade.json` are leftovers from an earlier multi-file pipeline and are safe to ignore.

---

## CBAM sectors covered

| Dashboard key | HS codes | Notes |
|--------------|----------|-------|
| Iron & steel (primary) | HS 72 + HS 2601.12 | CBAM: full chapter |
| Steel articles | HS 73 | CBAM: partial, treated as upper bound |
| Aluminum | HS 76 | CBAM: most of chapter |
| Cement | HS 2523 + 2507 | CBAM: full |
| Fertilizers | HS 31 | CBAM: nitrogenous only |
| Ammonia | HS 2814 | CBAM: full |
| Hydrogen | HS 2804.10 | CBAM: full |

---

## Data sources

- **US Census Bureau** — [International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html): domestic exports (FAS value), general imports, and shipping weights by HS6 code and partner country
- **Eurostat Comext** ([DS-045409](https://ec.europa.eu/eurostat/web/international-trade-in-goods/database)): EU27 imports from the US by CN code, monthly, in EUR and tonnes
- **UN Comtrade** ([comtradeplus.un.org](https://comtradeplus.un.org/)): used by the legacy `comtrade_query_restored.py` script only, not the live pipeline

All values are nominal. Comext values are CIF in euros and are not directly comparable to Census Bureau FAS dollar figures.

---

## License

[CC BY-NC 4.0](LICENSE) — © 2026 Niskanen Center. Free to share and adapt with attribution; not for commercial use.
