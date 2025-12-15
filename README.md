# Climate_Trade

This repository contains code and data for analyzing **trade in hard-to-abate sectors** and its implications for climate and industrial policy.

It includes tools to:
- Download and process international trade data from **UN Comtrade (API)**
- Analyze exports and imports in **hard-to-abate sectors** (steel, aluminum, cement)
- Combine trade data with **World Bank indicators**
- Produce **interactive visualizations** and dashboards using **Streamlit**
- Create reproducible analysis workflows using **Python** and **R**

## Key components

- `python/`
  Streamlit app and data-processing scripts for interactive dashboards
- `data/raw/`
  Raw trade data pulled from UN Comtrade and other sources
- `data/processed/`
  Cleaned and aggregated datasets used for visualization
- `R/`
  Supporting R scripts and exploratory analysis (World Bank, mapping)

## Live dashboard

The main output of this repository is an interactive Streamlit dashboard showing:
- U.S. exports and imports in hard-to-abate sectors
- Partner shares over time
- Export vs. import comparisons by year and sector

## Data sources

- **UN Comtrade** — bilateral trade flows by product and partner
- **World Bank** — macroeconomic and trade indicators

## Notes

- API keys are managed via environment variables and are **not** committed to the repository.
- This project is under active development and intended for policy analysis and research use.