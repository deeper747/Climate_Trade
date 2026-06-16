"""
Build docs/data/trade_data.json from Census Bureau + Eurostat Comext APIs.

Census Bureau (https://api.census.gov/data/timeseries/intltrade/):
  RAW[hs_key][series][period]
  hs_key  : "72","73","76","2523","280410","31","2814"
  annual  : ae, awx, awm, aew  (period = "2019".."current_year")
  monthly : me, mw, mew        (period = "202401".."latest_month")

Eurostat Comext DS-045409 (monthly EU27 imports from US):
  RAWEU[sector][period] → [eur, tonnes]
  sector  : "steel","alu","cement","fert","h2"
  period  : "202201".."latest_month"

Run:  python python/build_data.py
Env:  CENSUS_API_KEY in project .env
"""
from __future__ import annotations

import json, os, time
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "docs" / "data" / "trade_data.json"

load_dotenv(ROOT / ".env")
CENSUS_KEY = os.getenv("CENSUS_API_KEY", "")
if not CENSUS_KEY:
    raise RuntimeError("CENSUS_API_KEY not found — add it to the project .env file")

EXPORT_URL   = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
IMPORT_URL   = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
COMEXT_BASE  = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"

START_YEAR    = 2019
CURRENT_YEAR  = date.today().year
MONTHLY_FROM  = (2024, 1)   # start of monthly window

# ---------------------------------------------------------------------------
# CBAM sector definitions — kept in sync with fetch_us_trade_raw.py
# ---------------------------------------------------------------------------
SECTOR_HEADINGS: dict[str, set[str]] = {
    "iron_steel_72": {
        "260112",
        "7201", "7203", "7205",
        "7208", "7209", "7210",
        "7212", "7213", "7215", "7216", "7221",
        "720211", "720241", "720260",
        "720610",
        "721113",
        "721420",
        "721710", "721720",
        "721810", "721911", "721931",
        "722300",
        "722410", "722511", "722530", "722550",
    },
    "iron_steel_73": {
        "7301", "7302",
        "7305", "7308", "7309", "7310",
        "730300",
        "730419", "730439",
        "730619", "730630",
        "730721", "730791",
        "731100",
        "731815", "731816",
        "731822", "731823",
        "732690",
    },
    "aluminum_76": {
        "7601", "7603",
        "7605", "7606", "7607", "7608",
        "7612", "7614",
        "760410", "760421", "760429",
        "760900",
        "761010", "761100",
        "761300",
        "761610", "761691", "761699",
    },
    "cement_2523": {
        "250700",
        "252310", "252321", "252329",
        "252330", "252390",
    },
    "hydrogen_2804": {
        "280410",
    },
    "fertilizers": {
        "280800",
        "281410", "281420",
        "283421",
        "310210",
        "310221", "310229",
        "310230",
        "310240",
        "310250", "310260",
        "310280", "310290",
        "310510", "310520",
        "310530", "310540",
        "310551", "310559",
        "310590",
    },
}

HS6_EXACT: set[str]    = {c for codes in SECTOR_HEADINGS.values() for c in codes if len(c) == 6}
HS4_PREFIXES: set[str] = {c for codes in SECTOR_HEADINGS.values() for c in codes if len(c) == 4}

def _is_cbam(hs6: str) -> bool:
    return hs6 in HS6_EXACT or hs6[:4] in HS4_PREFIXES

# ---------------------------------------------------------------------------
# HS6 code → RAW key  (aligns with SECTORS in index.html)
# ---------------------------------------------------------------------------
def hs6_to_key(hs6: str) -> Optional[str]:
    if hs6 == "260112" or hs6.startswith("72"):
        return "72"
    if hs6.startswith("73"):
        return "73"
    if hs6.startswith("76"):
        return "76"
    if hs6.startswith("2523") or hs6.startswith("2507"):
        return "2523"
    if hs6 == "280410":
        return "280410"
    if hs6.startswith("2814"):
        return "2814"
    if hs6.startswith("31"):
        return "31"
    # Other HS28 codes (nitric acid 280800, potassium nitrate 283421): no RAW key
    return None

# ---------------------------------------------------------------------------
# Aggregate detection — mirrors fetch_us_trade_raw.py
# ---------------------------------------------------------------------------
_AGG_MARKERS = {
    "OECD","APEC","USMCA","NAFTA","NATO","EUROPEAN UNION","G20","G7","OPEC","ASEAN",
    "TOTAL","WORLD","REST OF WORLD","LATIN AMERICAN","PACIFIC RIM","EURO AREA",
    "CAFTA","LAFTA","AND OCEANIA",
}
_AGG_EXACT = {
    "AFRICA","NORTH AFRICA","SUB-SAHARAN AFRICA",
    "ASIA","EAST ASIA","SOUTH ASIA","SOUTHEAST ASIA","CENTRAL ASIA",
    "EUROPE","AMERICAS","NORTH AMERICA","SOUTH AMERICA","CENTRAL AMERICA",
    "LATIN AMERICA","LATIN AMERICA AND CARIBBEAN","CARIBBEAN","OCEANIA","PACIFIC",
    "MIDDLE EAST","NEAR EAST",
}

def _is_eu27(name: str) -> bool:
    return "EUROPEAN UNION" in name.upper()

def _is_aggregate(name: str) -> bool:
    n = name.upper()
    return n in _AGG_EXACT or any(m in n for m in _AGG_MARKERS)

# ---------------------------------------------------------------------------
# Generic Census HTTP helper
# ---------------------------------------------------------------------------
def _census_fetch(url: str, params: dict, label: str) -> list:
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as exc:
            print(f"\n    network error ({label}, attempt {attempt+1}): {exc}")
            time.sleep(2 ** attempt)
            continue
        if r.ok:
            try:
                return r.json()
            except Exception:
                if "maintenance" in r.text.lower():
                    print(f"\n    Census maintenance — waiting 30s")
                    time.sleep(30)
                    continue
                print(f"\n    bad JSON ({label}): {r.text[:120]}")
                return []
        if r.status_code == 429:
            time.sleep(20 * (attempt + 1))
            continue
        print(f"\n    HTTP {r.status_code} ({label}): {r.text[:80]}")
        return []
    return []

# ---------------------------------------------------------------------------
# Census annual export: ae (EU27 value), aew (EU27 weight kg), awx (world value)
# ---------------------------------------------------------------------------
def fetch_annual_exports(year: int) -> tuple[dict, dict, dict]:
    print(f"  export annual {year} … ", end="", flush=True)
    data = _census_fetch(EXPORT_URL, {
        "get":      "E_COMMODITY,CTY_NAME,ALL_VAL_YR,AIR_WGT_YR,VES_WGT_YR",
        "YEAR":     str(year),
        "MONTH":    "12",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"export {year}")
    if len(data) < 2:
        print("no data")
        return {}, {}, {}

    headers = data[0]
    ae: dict[str, float] = {}
    aew: dict[str, float] = {}
    awx: dict[str, float] = {}

    for row_list in data[1:]:
        row  = dict(zip(headers, row_list))
        hs6  = row.get("E_COMMODITY", "")
        if not _is_cbam(hs6):
            continue
        key = hs6_to_key(hs6)
        if key is None:
            continue
        val  = float(row.get("ALL_VAL_YR") or 0)
        wgt  = float(row.get("AIR_WGT_YR") or 0) + float(row.get("VES_WGT_YR") or 0)
        name = (row.get("CTY_NAME") or "").upper()
        if _is_eu27(name):
            ae[key]  = ae.get(key, 0.0)  + val
            aew[key] = aew.get(key, 0.0) + wgt
        elif not _is_aggregate(name):
            awx[key] = awx.get(key, 0.0) + val

    print(f"{len(data)-1:,} rows")
    return ae, aew, awx

# ---------------------------------------------------------------------------
# Census annual import: awm (world value)
# ---------------------------------------------------------------------------
def fetch_annual_imports(year: int) -> dict:
    print(f"  import annual {year} … ", end="", flush=True)
    data = _census_fetch(IMPORT_URL, {
        "get":      "I_COMMODITY,CTY_NAME,GEN_VAL_YR",
        "YEAR":     str(year),
        "MONTH":    "12",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"import {year}")
    if len(data) < 2:
        print("no data")
        return {}

    headers = data[0]
    awm: dict[str, float] = {}

    for row_list in data[1:]:
        row = dict(zip(headers, row_list))
        hs6 = row.get("I_COMMODITY", "")
        if not _is_cbam(hs6):
            continue
        key = hs6_to_key(hs6)
        if key is None:
            continue
        if not _is_aggregate((row.get("CTY_NAME") or "").upper()):
            awm[key] = awm.get(key, 0.0) + float(row.get("GEN_VAL_YR") or 0)

    print(f"{len(data)-1:,} rows")
    return awm

# ---------------------------------------------------------------------------
# Census monthly exports: me (EU27 value), mew (EU27 weight kg), mw (world weight kg)
# ---------------------------------------------------------------------------
def fetch_monthly_exports(year: int, month: int) -> tuple[dict, dict, dict]:
    label = f"{year}{month:02d}"
    print(f"  export monthly {label} … ", end="", flush=True)
    data = _census_fetch(EXPORT_URL, {
        "get":      "E_COMMODITY,CTY_NAME,ALL_VAL_MO,AIR_WGT_MO,VES_WGT_MO",
        "YEAR":     str(year),
        "MONTH":    f"{month:02d}",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"monthly {label}")
    if len(data) < 2:
        print("no data")
        return {}, {}, {}

    headers = data[0]
    me:  dict[str, float] = {}
    mew: dict[str, float] = {}
    mw:  dict[str, float] = {}

    for row_list in data[1:]:
        row = dict(zip(headers, row_list))
        hs6 = row.get("E_COMMODITY", "")
        if not _is_cbam(hs6):
            continue
        key = hs6_to_key(hs6)
        if key is None:
            continue
        val  = float(row.get("ALL_VAL_MO") or 0)
        wgt  = float(row.get("AIR_WGT_MO") or 0) + float(row.get("VES_WGT_MO") or 0)
        name = (row.get("CTY_NAME") or "").upper()
        if _is_eu27(name):
            me[key]  = me.get(key,  0.0) + val
            mew[key] = mew.get(key, 0.0) + wgt
        elif not _is_aggregate(name):
            mw[key] = mw.get(key, 0.0) + wgt

    eu_keys = sum(1 for v in me.values() if v > 0)
    print(f"{len(data)-1:,} rows → {eu_keys} EU sectors")
    return me, mew, mw

# ---------------------------------------------------------------------------
# Comext: monthly EU27 imports from US per CBAM sector
# ---------------------------------------------------------------------------
COMEXT_SECTORS: dict[str, list[str]] = {
    "steel": [
        "26011200",
        "7201", "720211", "720241", "72026000",
        "7203", "7205", "72061000",
        "7208", "7209", "7210", "72111300", "7212", "7213", "72142000",
        "7215", "7216", "721710", "721720",
        "72181000", "72191100", "72193100",
        "7221", "722300",
        "722410", "72251100", "722530", "722550",
        "730300", "7301", "7302",
        "730419", "730439",
        "7305", "73061900", "73063080",
        "73072100", "73079100",
        "7308", "7309", "7310", "731100",
        "731815", "731816", "73182200", "73182300",
        "73269098",
    ],
    "alu": [
        "7601", "7603",
        "76041010", "76041090", "76042100", "76042910", "76042990",
        "7605", "7606", "7607", "7608",
        "76090000", "76101000", "76110000",
        "7612", "76130000", "7614",
        "76161000", "76169100", "76169910", "76169990",
    ],
    "cement": [
        "25070080", "25231000", "25232100", "25232900", "25233000", "25239000",
    ],
    "fert": [
        "28080000", "28141000", "28142000", "28342100",
        "31021012", "31021015", "31021019", "31021090",
        "31022100", "31022900", "31023010", "31023090",
        "31024010", "31024090", "31025000", "31026000",
        "31028000", "31029000",
        "31051000", "31052010", "31052090",
        "31053000", "31054000",
        "31055100", "31055900", "31059020", "31059080",
    ],
    "h2": ["28041000"],
}

_COMEXT_BATCH = 10

def fetch_comext_monthly(sector: str, cn_codes: list[str]) -> dict[str, list]:
    """Returns {YYYYMM: [eur, tonnes]} for EU27 imports from US."""
    print(f"  Comext {sector} ({len(cn_codes)} codes) … ", end="", flush=True)
    result: dict[str, list] = {}
    batches = [cn_codes[i:i+_COMEXT_BATCH] for i in range(0, len(cn_codes), _COMEXT_BATCH)]

    for batch in batches:
        url = f"{COMEXT_BASE}/M.EU27_2020.US.{'+'.join(batch)}.1./"
        params = {"format": "SDMX-CSV", "startPeriod": "2022-01", "lang": "EN"}

        df = pd.DataFrame()
        for attempt in range(5):
            try:
                r = requests.get(url, params=params, timeout=120)
            except requests.RequestException as exc:
                print(f"\n    network error (attempt {attempt+1}): {exc}")
                time.sleep(2 ** attempt)
                continue
            if r.ok:
                df = pd.read_csv(StringIO(r.text))
                break
            if r.status_code in (400, 404):
                break
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            print(f"\n    HTTP {r.status_code}: {r.text[:80]}")
            break

        if df.empty:
            time.sleep(0.3)
            continue

        df.columns = [c.lower() for c in df.columns]
        needed = {"time_period", "obs_value", "indicators"}
        if not needed.issubset(df.columns):
            time.sleep(0.3)
            continue

        df["period"]    = df["time_period"].astype(str).str.replace("-", "", regex=False)
        df["obs_value"] = pd.to_numeric(df["obs_value"], errors="coerce").fillna(0)

        val_rows = df[df["indicators"].str.upper() == "VALUE_IN_EUROS"]
        qty_rows = df[df["indicators"].str.upper() == "QUANTITY_IN_100KG"]

        for _, row in val_rows.iterrows():
            p = str(row["period"])
            if len(p) == 6:
                result.setdefault(p, [0.0, 0.0])
                result[p][0] += float(row["obs_value"])

        for _, row in qty_rows.iterrows():
            p = str(row["period"])
            if len(p) == 6:
                result.setdefault(p, [0.0, 0.0])
                result[p][1] += float(row["obs_value"]) / 10.0  # 100 kg → tonnes

        time.sleep(0.4)

    rounded = {p: [round(v, 2), round(t, 1)]
               for p, (v, t) in sorted(result.items())}
    print(f"{len(rounded)} months")
    return rounded

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
RAW_KEYS = ["72", "73", "76", "2523", "280410", "31", "2814"]

def build() -> None:
    RAW: dict = {k: {"ae": {}, "awx": {}, "awm": {}, "aew": {},
                      "me": {}, "mw": {}, "mew": {}} for k in RAW_KEYS}

    # --- Annual ---
    print("\n=== Census annual exports ===")
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        ae, aew_kg, awx = fetch_annual_exports(year)
        y = str(year)
        for k in RAW_KEYS:
            if ae.get(k):  RAW[k]["ae"][y]  = round(ae[k])
            if aew_kg.get(k): RAW[k]["aew"][y] = round(aew_kg[k] / 1000, 1)  # kg → t
            if awx.get(k): RAW[k]["awx"][y] = round(awx[k])
        time.sleep(0.5)

    print("\n=== Census annual imports ===")
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        awm = fetch_annual_imports(year)
        y = str(year)
        for k in RAW_KEYS:
            if awm.get(k): RAW[k]["awm"][y] = round(awm[k])
        time.sleep(0.5)

    # --- Monthly ---
    print("\n=== Census monthly exports ===")
    today = date.today()
    y, m = MONTHLY_FROM
    while (y, m) <= (today.year, today.month):
        me, mew_kg, mw = fetch_monthly_exports(y, m)
        label = f"{y}{m:02d}"
        for k in RAW_KEYS:
            # Only write a month if there's any EU export value
            if me.get(k, 0) > 0:
                RAW[k]["me"][label]  = round(me[k])
            if mew_kg.get(k, 0) > 0:
                RAW[k]["mew"][label] = round(mew_kg[k] / 1000, 1)  # kg → t
            if mw.get(k, 0) > 0:
                RAW[k]["mw"][label]  = round(mw[k])
        m += 1
        if m > 12:
            m, y = 1, y + 1
        time.sleep(0.5)

    # --- Comext ---
    print("\n=== Comext monthly EU imports from US ===")
    RAWEU: dict = {}
    for sector, codes in COMEXT_SECTORS.items():
        RAWEU[sector] = fetch_comext_monthly(sector, codes)
        time.sleep(1.0)

    # --- Write ---
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        json.dump({"RAW": RAW, "RAWEU": RAWEU}, fh, separators=(",", ":"))

    size_kb = OUT.stat().st_size / 1024
    print(f"\nWrote {OUT}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    build()
