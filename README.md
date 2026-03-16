# Climate_Trade — EU CBAM Trade Impact Monitor

This repository tracks bilateral trade in hard-to-abate sectors to identify which countries face the greatest exposure to the EU's **Carbon Border Adjustment Mechanism (CBAM)**.

## Live dashboard

[ushard2abatesectortrade.streamlit.app](https://ushard2abatesectortrade.streamlit.app/)

The dashboard has two tabs:

- **EU Trade — CBAM Exposure** — EU import and export partners for iron & steel, aluminum, and cement (2019–2023), with partner share trends on hover
- **U.S. Trade** — same sectors for the U.S., as a comparison

## Repository structure

```
python/
  app.py                   # Streamlit dashboard (EU + U.S. tabs)
  eu_trade.py              # Downloads EU→US trade data from Eurostat COMEXT API
  comtrade_query.py        # Downloads U.S. trade data from UN Comtrade API
  download_eu_trade.py     # Downloads EU trade data from UN Comtrade API
  clean_eu_trade.py        # Cleans raw EU trade data
  process_exports.py       # Processes U.S. export data

data/
  raw/
    comext_us_cbam_trade.csv   # EU→US bilateral trade, 2022–2024, per CN4 code
                               # Columns: cn4, tonnes_2022, eur_2022, ..._2023, ..._2024,
                               #          avg_tonnes_per_year, avg_eur_per_year
  processed/                   # Cleaned datasets used by the dashboard

docs/
  EU_CBAM_default_value_US.xlsx  # Official EU CBAM default embedded-emission values
                                 # per CN code for US exporters, with mark-up rates
                                 # (10%/20%/30%) for 2026, 2027, and 2028+
```

## How the COMEXT data is used

`comext_us_cbam_trade.csv` feeds a CBAM cost dashboard that estimates the financial exposure of US exporters shipping to the EU:

1. **Historical liability (2022–2024, hard-coded)** — average annual export tonnage per CN4 code × the official EU CBAM default embedded-emission value (tCO₂e/tonne) from `EU_CBAM_default_value_US.xlsx` × the EU carbon price. Computed for both the base default value and the mark-up values (10%/20%/30% for 2026/2027/2028+).

2. **Live 2026 counter** — a running total that accumulates in real time based on the day the user views the site. Using the 2022–2024 average tonnage as a proxy for 2026 volume, the counter shows how much US exporters are forgoing (or paying) right now due to the absence of a domestic US carbon price — growing every second the page is open.

## Data sources

- **Eurostat COMEXT** (`DS-045409`) — EU→US bilateral trade by CN4 product code; reporter EU27_2020, flow 1 (imports), 2022–2024
- **UN Comtrade** — bilateral trade flows by HS product code and partner country
- Sectors covered: Iron & Steel (HS 72, 73), Aluminum (HS 76), Cement (HS 2523), plus upstream inputs (HS 26, 28, 31)
- Years: 2019–2024

## Running locally

```bash
pip install -r requirements.txt
streamlit run python/app.py
```

Requires a `COMTRADE_API_KEY` in a `.env` file to re-download UN Comtrade data. The Eurostat COMEXT API (`eu_trade.py`) requires no key.
