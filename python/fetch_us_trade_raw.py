"""
Fetch US bilateral trade data from Census Bureau International Trade API.

API docs: https://www.census.gov/data/developers/data-sets/international-trade.html
Exports:  https://api.census.gov/data/timeseries/intltrade/exports/hs
Imports:  https://api.census.gov/data/timeseries/intltrade/imports/hs

Strategy: query COMM_LVL=HS4 once per year per flow — returns all 4-digit HS
headings × all countries in a single call (~127k rows). Filter client-side to
the CBAM-relevant headings and drop geographic aggregate groups (OECD, APEC …).

4-digit HS headings are internationally harmonized, so the CBAM CN code list
(EU IR 2025/2620 Annex I) maps directly to US Schedule B / HTS at this level.

Add CENSUS_API_KEY to the project .env file before running.
Output: data/raw/us_trade_hard_to_abate_partner_raw.csv
"""

from __future__ import annotations

import os, time
import requests
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "raw"
OUTDIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")
CENSUS_KEY = os.getenv("CENSUS_API_KEY", "")
if not CENSUS_KEY:
    raise RuntimeError("CENSUS_API_KEY not found — add it to the project .env file")

EXPORT_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
IMPORT_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"

START_YEAR = 2019
END_YEAR   = 2025   # Census publishes through the most recent completed year

# ---------------------------------------------------------------------------
# 4-digit HS headings per sector — derived from CBAM CN codes in cbamBenchmarks.js.
# HS-4 headings are internationally harmonized (same in EU CN and US HTS/Schedule B).
# ---------------------------------------------------------------------------
SECTOR_HEADINGS: dict[str, set[str]] = {
    "iron_steel_72": {
        "2601",                           # agglomerated iron ore (CBAM precursor)
        "7201", "7202", "7203",           # pig iron, ferro-alloys, DRI
        "7205", "7206",                   # granules/powders, ingots
        "7208", "7209", "7210", "7211",   # flat-rolled products
        "7212", "7213", "7214", "7215", "7216", "7217",  # bars, rods, angles, wire
        "7218", "7219",                   # stainless ingots/flat-rolled
        "7221", "7223", "7224", "7225",   # SS/alloy bars, wire, ingots, flat-rolled
    },
    "iron_steel_73": {
        "7301", "7302", "7303", "7304", "7305", "7306",  # sheet piling, rail, tubes/pipes
        "7307", "7308", "7309", "7310", "7311",           # fittings, structures, tanks
        "7318", "7326",                                   # screws/bolts/nuts, other articles
    },
    "aluminum_76": {
        "7601", "7603", "7604", "7605", "7606", "7607",
        "7608", "7609", "7610", "7611", "7612", "7613", "7614", "7616",
    },
    "cement_2523": {
        "2507",   # kaolinic clay (CBAM precursor)
        "2523",   # cement and clinker
    },
}

ALL_CBAM_HEADINGS: set[str] = set().union(*SECTOR_HEADINGS.values())

# Build a reverse map: heading → sector (for fast lookup)
HEADING_TO_SECTOR: dict[str, str] = {
    h: sector for sector, headings in SECTOR_HEADINGS.items() for h in headings
}

FLOW_CONFIG = {
    "Export": {
        "url":     EXPORT_URL,
        "cmd_col": "E_COMMODITY",
        "val_col": "ALL_VAL_YR",
    },
    "Import": {
        "url":     IMPORT_URL,
        "cmd_col": "I_COMMODITY",
        "val_col": "GEN_VAL_YR",
    },
}

# ---------------------------------------------------------------------------
# Census country name normalisation
# ---------------------------------------------------------------------------

# Geographic aggregates / blocs — not individual countries
# Substring markers: safe because no single country name contains these strings.
AGGREGATE_MARKERS = {
    "OECD", "APEC", "USMCA", "NAFTA", "NATO",
    "EUROPEAN UNION", "G20", "G7", "OPEC", "ASEAN", "ADB",
    "TOTAL", "WORLD", "REST OF WORLD",
    # Census Bureau regional trade-bloc labels
    "LATIN AMERICAN",   # "Twenty Latin American Republics", "Latin American…"
    "PACIFIC RIM",      # "Pacific Rim Countries"
    "EURO AREA",        # "Euro Area"
    "CAFTA",            # "Cafta-Dr"
    "LAFTA",            # Latin American Free Trade Association
    "AND OCEANIA",      # "Australia And Oceania"
}
# Exact matches for continental names where substring would cause false positives
# (e.g. "AFRICA" substring would match "South Africa").
AGGREGATE_EXACT = {
    "AFRICA", "NORTH AFRICA", "SUB-SAHARAN AFRICA",
    "ASIA", "EAST ASIA", "SOUTH ASIA", "SOUTHEAST ASIA", "CENTRAL ASIA",
    "EUROPE",
    "AMERICAS", "NORTH AMERICA", "SOUTH AMERICA", "CENTRAL AMERICA",
    "LATIN AMERICA", "LATIN AMERICA AND CARIBBEAN",
    "CARIBBEAN", "OCEANIA", "PACIFIC",
    "MIDDLE EAST", "NEAR EAST",
}

def _is_aggregate(name: str) -> bool:
    n = name.upper()
    return n in AGGREGATE_EXACT or any(marker in n for marker in AGGREGATE_MARKERS)

# Census country name (uppercase) → display name aligned with app.js PARTNER_COLORS
PARTNER_NAMES: dict[str, str] = {
    "CHINA":                    "China",
    "CHINA, MAINLAND":          "China",
    "RUSSIA":                   "Russian Federation",
    "TURKEY":                   "Türkiye",
    "INDIA":                    "India",
    "UNITED KINGDOM":           "United Kingdom",
    "KOREA, SOUTH":             "Rep. of Korea",
    "UKRAINE":                  "Ukraine",
    "VIETNAM":                  "Viet Nam",
    "VIET NAM":                 "Viet Nam",
    "JAPAN":                    "Japan",
    "INDONESIA":                "Indonesia",
    "EGYPT":                    "Egypt",
    "UNITED ARAB EMIRATES":     "United Arab Emirates",
    "SWITZERLAND":              "Switzerland",
    "NORWAY":                   "Norway",
    "CANADA":                   "Canada",
    "MEXICO":                   "Mexico",
    "GERMANY":                  "Germany",
    "BRAZIL":                   "Brazil",
    "MALAYSIA":                 "Malaysia",
    "TAIWAN":                   "Taiwan",
    "GREECE":                   "Greece",
    "SAUDI ARABIA":             "Saudi Arabia",
    "SOUTH AFRICA":             "South Africa",
    "AUSTRALIA":                "Australia",
    "IRAN":                     "Iran",
    "PAKISTAN":                 "Pakistan",
    "THAILAND":                 "Thailand",
    "PHILIPPINES":              "Philippines",
    "BANGLADESH":               "Bangladesh",
    "MOROCCO":                  "Morocco",
    "ALGERIA":                  "Algeria",
    "NIGERIA":                  "Nigeria",
    "ARGENTINA":                "Argentina",
    "AUSTRIA":                  "Austria",
    "BAHRAIN":                  "Bahrain",
    "CHILE":                    "Chile",
    "COLOMBIA":                 "Colombia",
    "CZECH REPUBLIC":           "Czech Republic",
    "FINLAND":                  "Finland",
    "FRANCE":                   "France",
    "ISRAEL":                   "Israel",
    "ITALY":                    "Italy",
    "NETHERLANDS":              "Netherlands",
    "NEW ZEALAND":              "New Zealand",
    "PERU":                     "Peru",
    "POLAND":                   "Poland",
    "PORTUGAL":                 "Portugal",
    "SINGAPORE":                "Singapore",
    "SPAIN":                    "Spain",
    "SWEDEN":                   "Sweden",
    "VENEZUELA":                "Venezuela",
}


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_year_flow(flow_name: str, year: int) -> pd.DataFrame:
    """One API call → all HS-4 headings × all countries for one year+flow."""
    cfg  = FLOW_CONFIG[flow_name]
    cmd  = cfg["cmd_col"]
    val  = cfg["val_col"]

    params = {
        "get":      f"{cmd},CTY_CODE,CTY_NAME,{val}",
        "YEAR":     str(year),
        "MONTH":    "12",     # cumulative full-year value
        "COMM_LVL": "HS4",
        "key":      CENSUS_KEY,
    }

    for attempt in range(5):
        try:
            resp = requests.get(cfg["url"], params=params, timeout=120)
        except requests.RequestException as exc:
            print(f"\n    Network error (attempt {attempt + 1}): {exc}")
            time.sleep(2 ** attempt)
            continue

        if resp.ok:
            try:
                data = resp.json()
            except Exception:
                if "maintenance" in resp.text.lower():
                    print(f"\n    Census maintenance — waiting 30s …")
                    time.sleep(30)
                    continue
                print(f"\n    Bad JSON: {resp.text[:120]}")
                return pd.DataFrame()

            if len(data) < 2:
                return pd.DataFrame()

            headers = data[0]
            df = pd.DataFrame(data[1:], columns=headers)
            return df

        if resp.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"\n    Rate limited — waiting {wait}s …")
            time.sleep(wait)
            continue

        print(f"\n    HTTP {resp.status_code}: {resp.text[:120]}")
        return pd.DataFrame()

    return pd.DataFrame()


def process(df: pd.DataFrame, flow_name: str, year: int) -> pd.DataFrame:
    """Filter to CBAM headings, drop aggregates, map names, return tidy frame."""
    cfg = FLOW_CONFIG[flow_name]
    cmd = cfg["cmd_col"]
    val = cfg["val_col"]

    df[val] = pd.to_numeric(df[val], errors="coerce")

    # Keep only CBAM-relevant headings
    df = df[df[cmd].isin(ALL_CBAM_HEADINGS)].copy()

    # Drop geographic aggregates and zero-value rows
    df = df[~df["CTY_NAME"].apply(_is_aggregate)].copy()
    df = df[df[val].notna() & (df[val] > 0)].copy()

    # Map country names
    df["partnerDesc"] = (
        df["CTY_NAME"].str.upper()
                      .map(PARTNER_NAMES)
                      .fillna(df["CTY_NAME"].str.title())
    )

    # Assign sector
    df["sector"] = df[cmd].map(HEADING_TO_SECTOR)
    df["period"] = year
    df["flow"]   = flow_name
    df = df.rename(columns={val: "primaryValue"})

    # Aggregate headings → partner × sector × year
    return (
        df.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)
          ["primaryValue"].sum()
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    frames: list[pd.DataFrame] = []

    for year in range(START_YEAR, END_YEAR + 1):
        for flow_name in ("Export", "Import"):
            print(f"Fetching  {year}  {flow_name} … ", end="", flush=True)
            df_raw = fetch_year_flow(flow_name, year)

            if df_raw.empty:
                print("(no data)")
                time.sleep(1)
                continue

            print(f"{len(df_raw):,} rows → ", end="", flush=True)
            df = process(df_raw, flow_name, year)
            print(f"{len(df):,} aggregated rows")
            frames.append(df)
            time.sleep(0.5)

    if not frames:
        print("\nNo data fetched — check CENSUS_API_KEY and network.")
        return

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["period", "partnerDesc", "primaryValue", "sector"])

    out_path = OUTDIR / "us_trade_hard_to_abate_partner_raw.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(out):,} rows)")
    print("Note: 'primaryValue' is in USD (Census Bureau, Schedule B / HTS).")


if __name__ == "__main__":
    main()
