"""
Fetch US bilateral trade data from Census Bureau International Trade API.

API docs: https://www.census.gov/data/developers/data-sets/international-trade.html
Exports:  https://api.census.gov/data/timeseries/intltrade/exports/hs
Imports:  https://api.census.gov/data/timeseries/intltrade/imports/hs

Strategy: query COMM_LVL=HS6 once per year per flow (~380k rows per call).
Filter client-side to CBAM-relevant HS6 codes derived from EU IR 2025/2620 Annex I:
  - 6-digit entries → exact HS6 match (mirrors specific CN sub-codes from the EU script)
  - 4-digit entries → prefix match (all HS6 sub-codes under that heading are in-scope,
    matching EU entries that cover an entire HS heading without sub-code restriction)

Weight: AIR_WGT_YR + VES_WGT_YR (kg). Census does not publish ALL_WGT_YR at HS6.

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
END_YEAR   = 2025

# ---------------------------------------------------------------------------
# Sector headings — derived from CBAM CN codes in fetch_eu_trade_raw.py.
#
# 6-digit codes: exact HS6 match (first 6 digits of the EU CN-8 code).
# 4-digit codes: prefix match — any HS6 sub-code under that heading qualifies,
#   mirroring EU entries where the entire HS heading is CBAM-regulated.
# ---------------------------------------------------------------------------
SECTOR_HEADINGS: dict[str, set[str]] = {
    "iron_steel_72": {
        # Precursor
        "260112",                               # agglomerated iron ores (26011200)
        # HS 72 — 4-digit prefix entries (all sub-codes covered by CBAM)
        "7201", "7203", "7205",                 # pig iron, DRI, granules/powders
        "7208", "7209", "7210",                 # HR/CR flat-rolled ≥600mm, coated
        "7212", "7213", "7215", "7216", "7221", # bars, rods, angles, SS bars
        # HS 72 — 6-digit exact entries
        "720211", "720241", "720260",           # ferro-manganese, ferro-chromium, ferro-nickel
        "720610",                               # non-alloy steel ingots
        "721113",                               # wide flats 150–600mm
        "721420",                               # rebars
        "721710", "721720",                     # wire uncoated / zinc-coated
        "721810", "721911", "721931",           # stainless ingots / HR / CR flat-rolled
        "722300",                               # stainless wire
        "722410", "722511", "722530", "722550", # alloy steel ingots, Si-electrical, HR, CR
    },
    "iron_steel_73": {
        # 4-digit prefix entries
        "7301", "7302",                         # sheet piling, railway track
        "7305", "7308", "7309", "7310",         # large-diameter pipes, structures, tanks
        # 6-digit exact entries
        "730300",                               # cast iron tubes/pipes
        "730419", "730439",                     # seamless line pipe / circular tubes non-SS
        "730619", "730630",                     # welded line pipe / tubes 168–406mm non-SS
        "730721", "730791",                     # SS flanges, non-SS flanges
        "731100",                               # containers for compressed gas
        "731815", "731816",                     # screws/bolts, nuts
        "731822", "731823",                     # washers, rivets
        "732690",                               # articles of iron/steel NES
    },
    "aluminum_76": {
        # 4-digit prefix entries
        "7601", "7603",                         # unwrought aluminum, powders/flakes
        "7605", "7606", "7607", "7608",         # wire, plates, foil, tubes/pipes
        "7612", "7614",                         # casks/drums, stranded wire/cables
        # 6-digit exact entries
        "760410", "760421", "760429",           # extruded profiles
        "760900",                               # tube/pipe fittings
        "761010", "761100",                     # structures/tanks (large)
        "761300",                               # containers for compressed gas
        "761610", "761691", "761699",           # nails, cloth/netting, other articles
    },
    "cement_2523": {
        # 6-digit exact entries only (no full-heading entries needed)
        "250700",                               # kaolinic clays precursor (25070080)
        "252310", "252321", "252329",           # clinker, white/grey Portland cement
        "252330", "252390",                     # aluminous cement, other hydraulic cements
    },
    "hydrogen_2804": {
        "280410",                               # hydrogen only — excludes noble gases
    },
    "fertilizers": {
        # HS 28 precursors
        "280800",                               # nitric acid
        "281410", "281420",                     # ammonia anhydrous / aqueous
        "283421",                               # potassium nitrate
        # HS 31 nitrogenous fertilizers (3102)
        "310210",                               # urea (all sub-types)
        "310221", "310229",                     # ammonium sulphate / double salts
        "310230",                               # ammonium nitrate
        "310240",                               # AN + CaCO₃
        "310250", "310260",                     # sodium nitrate, Ca nitrate/AN mix
        "310280", "310290",                     # UAN solution, other N fertilizers
        # HS 31 NPK/NP/NK (3105)
        "310510", "310520",                     # NPK packaged, NPK bulk
        "310530", "310540",                     # DAP, MAP
        "310551", "310559",                     # NP nitrates, NP other
        "310590",                               # NK fertilizers
    },
}

# HS6 codes that must match exactly
HS6_EXACT: set[str] = {c for codes in SECTOR_HEADINGS.values() for c in codes if len(c) == 6}
# 4-digit prefixes where any HS6 sub-code qualifies
HS4_PREFIXES: set[str] = {c for codes in SECTOR_HEADINGS.values() for c in codes if len(c) == 4}

def _is_cbam(hs6: str) -> bool:
    return hs6 in HS6_EXACT or hs6[:4] in HS4_PREFIXES

# heading → sector (supports both 4-digit and 6-digit keys)
HEADING_TO_SECTOR: dict[str, str] = {
    code: sector for sector, codes in SECTOR_HEADINGS.items() for code in codes
}

def _sector(hs6: str) -> str | None:
    return HEADING_TO_SECTOR.get(hs6) or HEADING_TO_SECTOR.get(hs6[:4])

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

AGGREGATE_MARKERS = {
    "OECD", "APEC", "USMCA", "NAFTA", "NATO",
    "EUROPEAN UNION", "G20", "G7", "OPEC", "ASEAN", "ADB",
    "TOTAL", "WORLD", "REST OF WORLD",
    "LATIN AMERICAN", "PACIFIC RIM", "EURO AREA",
    "CAFTA", "LAFTA", "AND OCEANIA",
}
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
    """One API call → all HS-6 codes × all countries for one year + flow."""
    cfg = FLOW_CONFIG[flow_name]
    cmd = cfg["cmd_col"]
    val = cfg["val_col"]

    params = {
        "get":      f"{cmd},CTY_CODE,CTY_NAME,{val},AIR_WGT_YR,VES_WGT_YR",
        "YEAR":     str(year),
        "MONTH":    "12",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }

    for attempt in range(5):
        try:
            resp = requests.get(cfg["url"], params=params, timeout=180)
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
    """Filter to CBAM HS6 codes, drop aggregates, map names, return tidy frame."""
    cfg = FLOW_CONFIG[flow_name]
    cmd = cfg["cmd_col"]
    val = cfg["val_col"]

    df[val] = pd.to_numeric(df[val], errors="coerce")
    df["AIR_WGT_YR"] = pd.to_numeric(df.get("AIR_WGT_YR", 0), errors="coerce").fillna(0)
    df["VES_WGT_YR"] = pd.to_numeric(df.get("VES_WGT_YR", 0), errors="coerce").fillna(0)
    df["quantity_kg"] = df["AIR_WGT_YR"] + df["VES_WGT_YR"]

    # Filter to CBAM-relevant HS6 codes (exact or 4-digit prefix match)
    df = df[df[cmd].apply(_is_cbam)].copy()

    # Drop geographic aggregates and zero-value rows
    df = df[~df["CTY_NAME"].apply(_is_aggregate)].copy()
    df = df[df[val].notna() & (df[val] > 0)].copy()

    # Map country names
    df["partnerDesc"] = (
        df["CTY_NAME"].str.upper()
                      .map(PARTNER_NAMES)
                      .fillna(df["CTY_NAME"].str.title())
    )

    # Assign sector (exact HS6 match first, then 4-digit prefix fallback)
    df["sector"] = df[cmd].apply(_sector)
    df = df[df["sector"].notna()].copy()

    df["period"] = year
    df["flow"]   = flow_name
    df = df.rename(columns={val: "primaryValue"})

    return (
        df.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)
          .agg(primaryValue=("primaryValue", "sum"), quantity_kg=("quantity_kg", "sum"))
    )


def process_eu(df: pd.DataFrame, flow_name: str, year: int) -> pd.DataFrame:
    """Extract EU27 aggregate rows, preserving HS6 code for commodity-level breakdown."""
    cfg = FLOW_CONFIG[flow_name]
    cmd = cfg["cmd_col"]
    val = cfg["val_col"]

    df = df.copy()
    df[val] = pd.to_numeric(df[val], errors="coerce")
    df["AIR_WGT_YR"] = pd.to_numeric(df.get("AIR_WGT_YR", 0), errors="coerce").fillna(0)
    df["VES_WGT_YR"] = pd.to_numeric(df.get("VES_WGT_YR", 0), errors="coerce").fillna(0)
    df["quantity_kg"] = df["AIR_WGT_YR"] + df["VES_WGT_YR"]

    # Filter to CBAM-relevant HS6 codes
    df = df[df[cmd].apply(_is_cbam)].copy()

    # Keep only the EU27 aggregate partner
    eu_mask = df["CTY_NAME"].str.upper().str.contains("EUROPEAN UNION", na=False)
    df = df[eu_mask].copy()

    if df.empty:
        return pd.DataFrame()

    df = df[df[val].notna() & (df[val] > 0)].copy()

    df["sector"] = df[cmd].apply(_sector)
    df = df[df["sector"].notna()].copy()

    df["period"] = year
    df["flow"]   = flow_name
    df["hs6"]    = df[cmd]
    df = df.rename(columns={val: "primaryValue"})

    return (
        df.groupby(["period", "flow", "sector", "hs6"], as_index=False)
          .agg(primaryValue=("primaryValue", "sum"), quantity_kg=("quantity_kg", "sum"))
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    frames: list[pd.DataFrame] = []
    eu_frames: list[pd.DataFrame] = []

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

            df_eu = process_eu(df_raw, flow_name, year)
            if not df_eu.empty:
                eu_frames.append(df_eu)
                print(f"  (EU27: {len(df_eu):,} HS6 rows)")

            time.sleep(0.5)

    if not frames:
        print("\nNo data fetched — check CENSUS_API_KEY and network.")
        return

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["period", "partnerDesc", "primaryValue", "sector"])

    out_path = OUTDIR / "us_trade_hard_to_abate_partner_raw.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(out):,} rows)")
    print("Note: primaryValue in USD; quantity_kg = AIR_WGT_YR + VES_WGT_YR (kg).")

    if eu_frames:
        eu_out = pd.concat(eu_frames, ignore_index=True)
        eu_out = eu_out.dropna(subset=["period", "hs6", "primaryValue", "sector"])
        eu_out_path = OUTDIR / "us_eu27_trade_raw.csv"
        eu_out.to_csv(eu_out_path, index=False)
        print(f"Saved EU27: {eu_out_path}  ({len(eu_out):,} rows)")
    else:
        print("Warning: No EU27 rows found — Census may not report EU as an aggregate partner.")


if __name__ == "__main__":
    main()
