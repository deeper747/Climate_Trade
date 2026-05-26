"""
Fetch US bilateral trade data from Census Bureau International Trade API.

API docs: https://www.census.gov/data/developers/data-sets/international-trade.html
Exports:  https://api.census.gov/data/timeseries/intltrade/exports/hs
Imports:  https://api.census.gov/data/timeseries/intltrade/imports/hs

Commodity codes follow the same sector groupings as the EU CBAM fetcher,
using 2-digit HS chapter codes (which the Census API aggregates automatically).
Precursor headings (HS 2601 iron ore, HS 2507 kaolinic clay) are included
to match the EU CBAM sector definitions.

Values are in USD.  Annual total = MONTH=12 with the *_YR cumulative variable.

Output: data/raw/us_trade_hard_to_abate_partner_raw.csv
        Columns: period, flow, sector, partnerDesc, primaryValue (USD)
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

load_dotenv(ROOT / ".env")   # explicit path so the script works from any cwd

CENSUS_KEY = os.getenv("CENSUS_API_KEY", "")
if not CENSUS_KEY:
    raise RuntimeError("CENSUS_API_KEY not found — add it to the project .env file")

EXPORT_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
IMPORT_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"

START_YEAR = 2019
END_YEAR   = 2024   # update when Census publishes later years

# HS commodity codes per sector — 2-digit chapter where possible.
# Census aggregates all 10-digit Schedule B/HTS codes under the specified prefix.
# Precursor chapters (2601, 2507) included to match EU CBAM sector scope.
SECTORS: dict[str, list[str]] = {
    "iron_steel_72": ["72", "2601"],   # HS 72 + iron ore precursor (HS 2601)
    "iron_steel_73": ["73"],           # HS 73 articles of iron & steel
    "aluminum_76":   ["76"],           # HS 76 aluminum
    "cement_2523":   ["2523", "2507"], # HS 2523 cement + kaolinic clay precursor (HS 2507)
}

FLOW_CONFIG = {
    "Export": {
        "url":       EXPORT_URL,
        "cmd_param": "E_COMMODITY",
        "val_var":   "ALL_VAL_YR",
        "get_vars":  "E_COMMODITY,CTY_CODE,CTY_NAME,ALL_VAL_YR",
    },
    "Import": {
        "url":       IMPORT_URL,
        "cmd_param": "I_COMMODITY",
        "val_var":   "GEN_VAL_YR",
        "get_vars":  "I_COMMODITY,CTY_CODE,CTY_NAME,GEN_VAL_YR",
    },
}

# Census country name (uppercase) → display name matching app.js PARTNER_COLORS
PARTNER_NAMES: dict[str, str] = {
    "CHINA":                          "China",
    "CHINA, MAINLAND":                "China",
    "RUSSIA":                         "Russian Federation",
    "TURKEY":                         "Türkiye",
    "INDIA":                          "India",
    "UNITED KINGDOM":                 "United Kingdom",
    "KOREA, SOUTH":                   "Rep. of Korea",
    "UKRAINE":                        "Ukraine",
    "VIETNAM":                        "Viet Nam",
    "VIET NAM":                       "Viet Nam",
    "JAPAN":                          "Japan",
    "INDONESIA":                      "Indonesia",
    "EGYPT":                          "Egypt",
    "UNITED ARAB EMIRATES":           "United Arab Emirates",
    "SWITZERLAND":                    "Switzerland",
    "NORWAY":                         "Norway",
    "CANADA":                         "Canada",
    "MEXICO":                         "Mexico",
    "GERMANY":                        "Germany",
    "BRAZIL":                         "Brazil",
    "MALAYSIA":                       "Malaysia",
    "TAIWAN":                         "Taiwan",
    "GREECE":                         "Greece",
    "SAUDI ARABIA":                   "Saudi Arabia",
    "SOUTH AFRICA":                   "South Africa",
    "AUSTRALIA":                      "Australia",
    "IRAN":                           "Iran",
    "PAKISTAN":                       "Pakistan",
    "THAILAND":                       "Thailand",
    "PHILIPPINES":                    "Philippines",
    "BANGLADESH":                     "Bangladesh",
    "MOROCCO":                        "Morocco",
    "ALGERIA":                        "Algeria",
    "NIGERIA":                        "Nigeria",
    "ARGENTINA":                      "Argentina",
    "AUSTRIA":                        "Austria",
    "BAHRAIN":                        "Bahrain",
    "CHILE":                          "Chile",
    "COLOMBIA":                       "Colombia",
    "CZECH REPUBLIC":                 "Czech Republic",
    "FINLAND":                        "Finland",
    "FRANCE":                         "France",
    "ISRAEL":                         "Israel",
    "ITALY":                          "Italy",
    "NETHERLANDS":                    "Netherlands",
    "NEW ZEALAND":                    "New Zealand",
    "PERU":                           "Peru",
    "POLAND":                         "Poland",
    "PORTUGAL":                       "Portugal",
    "SINGAPORE":                      "Singapore",
    "SPAIN":                          "Spain",
    "SWEDEN":                         "Sweden",
    "VENEZUELA":                      "Venezuela",
}

# Rows to drop — country totals and domestic entries
TOTAL_MARKERS = {"TOTAL FOR ALL COUNTRIES", "TOTAL - FOREIGN", "UNKNOWN"}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_one(url: str, cmd_param: str, val_var: str, get_vars: str,
              commodity: str, year: int) -> pd.DataFrame:
    params: dict = {
        "get":    get_vars,
        "YEAR":   str(year),
        "MONTH":  "12",        # MONTH=12 → full-year cumulative value in *_YR columns
        cmd_param: commodity,
    }
    if CENSUS_KEY:
        params["key"] = CENSUS_KEY

    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException as exc:
            print(f"\n    Network error (attempt {attempt + 1}): {exc}")
            time.sleep(2 ** attempt)
            continue

        if resp.ok:
            try:
                data = resp.json()
            except Exception:
                if "maintenance" in resp.text.lower():
                    print(f"\n    Census API maintenance — waiting 30s …")
                    time.sleep(30)
                    continue
                print(f"\n    Bad JSON: {resp.text[:120]}")
                return pd.DataFrame()

            if len(data) < 2:
                return pd.DataFrame()

            headers = data[0]
            rows = [dict(zip(headers, row)) for row in data[1:]]
            df = pd.DataFrame(rows)
            df[val_var] = pd.to_numeric(df[val_var], errors="coerce")
            return df

        if resp.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"\n    Rate limited — waiting {wait}s …")
            time.sleep(wait)
            continue

        if resp.status_code in (400, 404):
            return pd.DataFrame()

        print(f"\n    HTTP {resp.status_code}: {resp.text[:120]}")
        return pd.DataFrame()

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    frames: list[pd.DataFrame] = []

    for sector_name, commodities in SECTORS.items():
        for flow_name, cfg in FLOW_CONFIG.items():
            print(f"\n{sector_name}  {flow_name}")
            sector_frames: list[pd.DataFrame] = []

            for commodity in commodities:
                for year in range(START_YEAR, END_YEAR + 1):
                    print(f"  HS {commodity}  {year} … ", end="", flush=True)
                    df = fetch_one(
                        cfg["url"], cfg["cmd_param"], cfg["val_var"],
                        cfg["get_vars"], commodity, year,
                    )

                    if df.empty:
                        print("(no data)")
                        time.sleep(0.3)
                        continue

                    val_var = cfg["val_var"]
                    cty_col = "CTY_NAME"

                    # Drop total/unknown rows
                    df = df[~df[cty_col].str.upper().isin(TOTAL_MARKERS)].copy()
                    df = df[df[val_var].notna() & (df[val_var] > 0)].copy()

                    # Map country names → display names (unmapped keep their Census name)
                    df["partnerDesc"] = (
                        df[cty_col].str.upper()
                                   .map(PARTNER_NAMES)
                                   .fillna(df[cty_col].str.title())
                    )
                    df["period"]       = year
                    df["flow"]         = flow_name
                    df["sector"]       = sector_name
                    df["primaryValue"] = df[val_var]

                    sector_frames.append(
                        df[["period", "flow", "sector", "partnerDesc", "primaryValue"]]
                    )
                    print(f"{len(df):,} rows")
                    time.sleep(0.4)

            if sector_frames:
                combined = pd.concat(sector_frames, ignore_index=True)
                # Sum across commodity codes for same partner × year
                agg = (
                    combined.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)
                            ["primaryValue"].sum()
                )
                frames.append(agg)
                print(f"  → {len(agg):,} aggregated rows")

    if not frames:
        print("\nNo data fetched — check Census API key and network.")
        return

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["period", "partnerDesc", "primaryValue"])

    out_path = OUTDIR / "us_trade_hard_to_abate_partner_raw.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(out):,} rows)")
    print("Note: 'primaryValue' is in USD (Census Bureau, Schedule B / HTS).")


if __name__ == "__main__":
    main()
