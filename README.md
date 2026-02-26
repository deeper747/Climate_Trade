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
  comtrade_query.py        # Downloads U.S. trade data from UN Comtrade API
  download_eu_trade.py     # Downloads EU trade data from UN Comtrade API
  clean_eu_trade.py        # Cleans raw EU trade data
  process_exports.py       # Processes U.S. export data

data/
  raw/                     # Raw data pulled from UN Comtrade
  processed/               # Cleaned datasets used by the dashboard
```

## Data sources

- **UN Comtrade** — bilateral trade flows by HS product code and partner country
- Sectors covered: Iron & Steel (HS 72, 73), Aluminum (HS 76), Cement (HS 2523)
- Years: 2019–2023

## Running locally

```bash
pip install -r requirements.txt
streamlit run python/app.py
```

Requires a `COMTRADE_API_KEY` in a `.env` file to re-download data.
