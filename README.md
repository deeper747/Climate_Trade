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

This runs `python/build_cn_trade.py` (Comext CN-level monthly series → `docs/data/us_eu_cbam_cn_trade.json`), then commits and pushes the JSON, which redeploys GitHub Pages. The script uses the Python standard library only. The Eurostat and ECB APIs need no key, but the hydrogen series comes from the U.S. Census Bureau, so `CENSUS_API_KEY` must be set in the environment or in a `.env` file at the project root. Eurostat publishes extra-EU monthly data about six to seven weeks after the reference month.

A cloud routine (via Claude Code) opens a GitHub issue on the 15th of each month as a reminder to run the update.

---

## Repository structure

```
python/
  build_cn_trade.py             # Comext CN-level data → docs/data/us_eu_cbam_cn_trade.json

docs/                           # ← GitHub Pages root
  index.html                    # The dashboard: single page, fetches the JSON on load
  data/
    us_eu_cbam_cn_trade.json    # Data file the browser loads
  Niskanen Center_RGB_Logo Teal.png   # Dashboard logo (shown in white via CSS on the header)

update.sh                       # One-command update + deploy
```

Earlier pipelines (UN Comtrade and Census Bureau fetchers, the previous dashboard with a Census cross-check and 2026–2034 CBAM cost projection) remain in git history; see commit `e65e675`.

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
- Hydrogen uses U.S. Census export data instead of Comext, because Comext reports 57,134 t at €3.5M (about €61/t) for August 2025, almost certainly a reporting error. Census values are FAS rather than CIF, and its volume is gross shipping weight for air and vessel shipments only.
- The current year and, until Eurostat's annual revision, the previous year are provisional.

---

## Data sources

- **Eurostat Comext** ([DS-045409](https://ec.europa.eu/eurostat/web/international-trade-in-goods/database)): EU27 imports from the US by CN code, monthly, in EUR and 100 kg units (converted to tonnes). Used for every sector except hydrogen.
- **US Census Bureau** ([International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html)): U.S. exports of HS 2804.10 (hydrogen) to the European Union (country code 0003), monthly. Replaces the Comext hydrogen series, which reports an implausible 57,134 t at €3.5M for August 2025. FAS dollar values are converted to euros at ECB monthly average USD/EUR rates ([ECB Data Portal](https://data.ecb.europa.eu/), series EXR.M.USD.EUR.SP00.A); volume is air plus vessel shipping weight.

All values are nominal. Comext import values are CIF (cost, insurance and freight, valued at the EU border) in euros.

---

## License

[CC BY-NC 4.0](LICENSE) — © 2026 Niskanen Center. Free to share and adapt with attribution; not for commercial use.
