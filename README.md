# US–EU CBAM Trade Monitor

Monthly and annual U.S. exports to the EU in the five sectors covered by the EU Carbon Border Adjustment Mechanism (CBAM): iron and steel, aluminium, fertilisers, cement and hydrogen. Figures are EU imports from the United States as recorded by EU customs (Eurostat Comext), broken down by sector and by Combined Nomenclature (CN) code. The CN code list matches the [U.S. CBAM Exposure Calculator](https://the-niskanen-center.github.io/US-CBAM-calculator/). Built for the Niskanen Center.

**Live dashboard:** [deeper747.github.io/Climate_Trade](https://deeper747.github.io/Climate_Trade/)

---

## How the project works

```
Eurostat Comext DS-045409 ──► python/build_cn_trade.py ──► docs/data/us_eu_cbam_cn_trade.json
                                                                       │
                                                                       ▼
                                                     docs/index.html (GitHub Pages)
                                                                       │
                                                                       ▼
                                        Browser fetches the JSON on load and draws every chart
```

The dashboard is a **static site on GitHub Pages** with no backend. `build_cn_trade.py` pulls monthly EU imports from the U.S. (January 2021 onward, value in EUR and net mass in tonnes) for 102 CN codes, attaches each code's Comext description, and writes one JSON file. `docs/index.html` is a single page that loads that file and renders:

- an all-sector total and one panel per sector, each with annual and monthly bar charts;
- a collapsible CN code table under each sector (2025 value, current-year value, share of the sector's 2025 total, 2021–2025 trend), where each code opens into its own annual and monthly charts;
- toggles for value (€) or volume (tonnes), and for calendar-year or same-months (year-to-date) annual bars.

---

## Updating the data (one command)

```bash
./update.sh
```

This runs the following steps in sequence:

1. `fetch_eu_trade_raw.py`: annual EU bilateral trade from Eurostat Comext → `data/raw/eu_trade_hard_to_abate_partner_raw.csv`
2. `fetch_us_trade_raw.py`: annual US bilateral trade from Census Bureau → `data/raw/us_trade_hard_to_abate_partner_raw.csv`
3. `build_data.py`: Census + Comext monthly series → `docs/data/trade_data.json` (used by the previous dashboard version; kept for reference)
4. `build_cn_trade.py` (step 3b in the script): Comext CN-level monthly series → `docs/data/us_eu_cbam_cn_trade.json`, **the file the live dashboard reads**
5. `git commit` + `git push`: deploys the updated JSON files to GitHub Pages

To refresh only the dashboard data, run `python3 python/build_cn_trade.py` and commit `docs/data/us_eu_cbam_cn_trade.json`. It uses the Python standard library only, and the Eurostat API needs no key. Eurostat publishes extra-EU monthly data about six to seven weeks after the reference month.

A cloud routine (via Claude Code) opens a GitHub issue on the 15th of each month as a reminder to run the update.

**Requires (for the full `update.sh`):** `CENSUS_API_KEY` in a `.env` file at the project root, and a Python venv at `.venv/`.

```
CENSUS_API_KEY=your_key_here
```

---

## Repository structure

```
python/
  build_cn_trade.py             # DASHBOARD pipeline: Comext CN-level data → docs/data/us_eu_cbam_cn_trade.json
  build_data.py                 # Census + Comext APIs → docs/data/trade_data.json (previous dashboard)
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
  index.html                    # The dashboard: single page, fetches us_eu_cbam_cn_trade.json on load
  data/
    us_eu_cbam_cn_trade.json    # LIVE data file the browser loads (produced by build_cn_trade.py)
    trade_data.json             # Census + Comext series for the previous dashboard (build_data.py)
    eu_trade.json               # legacy — from an earlier pipeline, no longer generated or used
    us_trade.json               # legacy
    us_eu_trade.json            # legacy
  Niskanen Center_RGB_Logo Teal.png               # Dashboard logo (shown in white via CSS on the header)

reference/
  cbamBenchmarks.js             # EU ETS product benchmarks + CBAM free-allocation factors
                                #   (source of truth for the dashboard's cost projection)
  cbam_ex_ante_reports/         # Official ex-ante CBAM impact analyses (EC IA SWD(2021) 643,
                                #   JRC GHG-intensity reports, EPRS, INTA, UNCTAD)

summer/                                           # Jan–Apr 2026 CBAM import comparison (side analysis)
  cbam_methodology_deck.pptx    # 12-slide walkthrough of the methodology and early evidence:
                                #   data pipeline, matched Jan–Apr windows, extra-EU benchmark,
                                #   DiD illustrations (partner-vs-benchmark + goods-level design)
  jan_apr_cbam_comparison.py    # Fetches EU monthly imports of CBAM goods (Eurostat Comext +
                                #   UN Comtrade) for CN/EG/IN/MA/TR/US and the extra-EU total;
                                #   compares Jan–Apr 2026 vs 2022–2025
  jan_apr_cbam_comparison.xlsx  # Output workbook: per-partner and per-sector comparisons,
                                #   tonnes sheet, and the "pp vs extra-EU" benchmark column
  raw_eurostat_jan_apr.csv      # Cached raw pulls (delete to force a fresh fetch)
  raw_comtrade_jan_apr.csv

cbam-trade-dashboard.html       # Standalone single-file snapshot of the dashboard (self-contained)
figs/                           # Exported figures (currently empty)
update.sh                       # One-command update + deploy
requirements.txt                # Python deps (note: streamlit listed is legacy; app was removed)
```

> **Note on the JSON files:** the live dashboard reads only `docs/data/us_eu_cbam_cn_trade.json`. `trade_data.json` still regenerates through `update.sh` but feeds nothing on the current page; the previous dashboard that used it (Census cross-check and 2026–2034 CBAM cost projection) remains in git history at commit `e65e675`. `eu_trade.json`, `us_trade.json` and `us_eu_trade.json` are leftovers from an earlier pipeline and are safe to ignore.

---

## CBAM sectors covered

The dashboard uses the same 102 CN codes as the U.S. CBAM Exposure Calculator. Four-digit and six-digit codes aggregate all their subheadings.

| Sector | CN codes | Examples |
|--------|----------|----------|
| Iron and steel | 47 | Iron ore pellets (2601 12 00), direct-reduced iron (7203), flat-rolled products (7208–7210, 7212), screws, bolts and nuts (7318), articles n.e.s. (7326 90 98) |
| Aluminium | 21 | Unwrought aluminium (7601), plates and sheets (7606), foil (7607), doors and windows (7610 10 00) |
| Fertilisers | 27 | Anhydrous ammonia (2814 10 00), nitric acid (2808), urea (3102 10), UAN solutions (3102 80 00), ammonium phosphates (3105 30 00, 3105 40 00) |
| Cement | 6 | Kaolinic clays (2507 00 80), clinker (2523 10 00), Portland cement (2523 21 00, 2523 29 00) |
| Hydrogen | 1 | Hydrogen (2804 10 00) |

Known data caveats, also noted on the page:

- CN 7306 19 00 and 7202 11 did not exist in the 2021 nomenclature, so 2021 iron and steel totals omit them (both under €0.5M a year in U.S. exports to the EU).
- August 2025 reports 57,134 t of U.S. hydrogen at €3.5M (about €61/t), almost certainly a reporting error; the volume view for hydrogen should be read with caution.
- The current year and, until Eurostat's annual revision, the previous year are provisional.

---

## Data sources

- **Eurostat Comext** ([DS-045409](https://ec.europa.eu/eurostat/web/international-trade-in-goods/database)): EU27 imports from the US by CN code, monthly, in EUR and 100 kg units (converted to tonnes). This is the only source for the live dashboard.
- **US Census Bureau** ([International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html)): domestic exports (FAS value), general imports, and shipping weights by HS6 code and partner country. Used by `build_data.py` and the annual fetch scripts, not by the current page.
- **UN Comtrade** ([comtradeplus.un.org](https://comtradeplus.un.org/)): used by the legacy `comtrade_query_restored.py` script and the `summer/` side analysis only.

All values are nominal. Comext import values are CIF (cost, insurance and freight, valued at the EU border) in euros and are not directly comparable to Census Bureau FAS dollar figures.

---

## License

[CC BY-NC 4.0](LICENSE) — © 2026 Niskanen Center. Free to share and adapt with attribution; not for commercial use.
