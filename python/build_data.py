"""
Build docs/data/trade_data.json from Census Bureau + Eurostat Comext APIs.

Annual EU27 US exports (ae, aew) come from the existing CSV produced by
fetch_us_trade_raw.py.  World totals (awx, awm) and monthly series (me, mew,
mw) come from the Census Bureau API.  EU imports from US come from Comext.

Existing trade_data.json is loaded as a baseline; fields are only overwritten
when new data is non-empty, so an API failure never wipes good old data.
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

ROOT    = Path(__file__).resolve().parents[1]
OUT     = ROOT / "docs" / "data" / "trade_data.json"
EU27_CSV = ROOT / "data" / "raw" / "us_eu27_trade_raw.csv"

load_dotenv(ROOT / ".env")
CENSUS_KEY = os.getenv("CENSUS_API_KEY", "")
if not CENSUS_KEY:
    raise RuntimeError("CENSUS_API_KEY not found — add it to the project .env file")

EXPORT_URL  = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
IMPORT_URL  = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
COMEXT_BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"

START_YEAR   = 2019
CURRENT_YEAR = date.today().year
MONTHLY_FROM = (2024, 1)

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

def hs6_to_key(hs6: str) -> Optional[str]:
    if hs6 == "260112" or hs6.startswith("72"): return "72"
    if hs6.startswith("73"):                     return "73"
    if hs6.startswith("76"):                     return "76"
    if hs6.startswith("2523") or hs6.startswith("2507"): return "2523"
    if hs6 == "280410":                          return "280410"
    if hs6.startswith("2814"):                   return "2814"
    if hs6.startswith("31"):                     return "31"
    return None

# ---------------------------------------------------------------------------
# Aggregate-country detection (mirrors fetch_us_trade_raw.py)
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

def _to_float(v) -> float:
    if v is None: return 0.0
    try: return float(v)
    except (ValueError, TypeError): return 0.0

# ---------------------------------------------------------------------------
# Generic Census HTTP helper
# ---------------------------------------------------------------------------
def _census_fetch(url: str, params: dict, label: str) -> list:
    for attempt in range(4):
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
                    print(f"\n    Census maintenance — waiting 30 s")
                    time.sleep(30)
                    continue
                print(f"\n    bad JSON ({label}): {r.text[:200]}")
                return []
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"\n    rate-limited — waiting {wait} s")
            time.sleep(wait)
            continue
        print(f"\n    HTTP {r.status_code} ({label}): {r.text[:200]}")
        return []
    return []

# ---------------------------------------------------------------------------
# Annual EU27 exports — read from CSV produced by fetch_us_trade_raw.py
# (more reliable than a fresh Census API call; covers 2019–latest full year)
# ---------------------------------------------------------------------------
def load_annual_from_csv() -> tuple[dict, dict]:
    """Return (ae, aew) dicts: ae[key][year]=USD, aew[key][year]=tonnes."""
    ae_raw:  dict[str, dict] = {k: {} for k in RAW_KEYS}
    aew_raw: dict[str, dict] = {k: {} for k in RAW_KEYS}

    if not EU27_CSV.exists():
        print(f"  WARNING: {EU27_CSV} not found — annual EU27 data will be empty")
        return ae_raw, aew_raw

    df = pd.read_csv(EU27_CSV, dtype=str)
    df["primaryValue"] = pd.to_numeric(df["primaryValue"], errors="coerce").fillna(0)
    df["quantity_kg"]  = pd.to_numeric(df["quantity_kg"],  errors="coerce").fillna(0)

    exports = df[df["flow"].str.strip().str.lower() == "export"]
    for _, row in exports.iterrows():
        hs6 = str(row.get("hs6", "")).strip()
        key = hs6_to_key(hs6)
        if key is None:
            continue
        year = str(row.get("period", "")).strip()[:4]
        if not year.isdigit():
            continue
        ae_raw[key][year]  = ae_raw[key].get(year,  0.0) + float(row["primaryValue"])
        aew_raw[key][year] = aew_raw[key].get(year, 0.0) + float(row["quantity_kg"])

    # Round at the end (not per-row) to avoid accumulated rounding error
    ae:  dict[str, dict] = {k: {y: round(v)          for y, v in ae_raw[k].items()}  for k in RAW_KEYS}
    aew: dict[str, dict] = {k: {y: round(v/1000, 1)  for y, v in aew_raw[k].items()} for k in RAW_KEYS}

    sectors_ok = sum(1 for k in RAW_KEYS if ae[k])
    years_found = sorted({y for k in RAW_KEYS for y in ae[k]})
    print(f"  CSV → {sectors_ok}/{len(RAW_KEYS)} sectors with data, years: {years_found}")
    return ae, aew

# ---------------------------------------------------------------------------
# Census annual: world export total per sector (awx)
# ---------------------------------------------------------------------------
def fetch_annual_exports_world(year: int) -> dict:
    print(f"  export world {year} … ", end="", flush=True)
    data = _census_fetch(EXPORT_URL, {
        "get":      "E_COMMODITY,CTY_CODE,CTY_NAME,ALL_VAL_YR",
        "YEAR":     str(year),
        "MONTH":    "12",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"export world {year}")
    if len(data) < 2:
        print("no data")
        return {}

    headers = data[0]
    awx: dict[str, float] = {}
    for row_list in data[1:]:
        row  = dict(zip(headers, row_list))
        hs6  = row.get("E_COMMODITY", "")
        if not _is_cbam(hs6):
            continue
        key = hs6_to_key(hs6)
        if key is None:
            continue
        name = (row.get("CTY_NAME") or "").upper()
        if not _is_aggregate(name):
            awx[key] = awx.get(key, 0.0) + _to_float(row.get("ALL_VAL_YR"))

    print(f"{len(data)-1:,} rows")
    return awx

# ---------------------------------------------------------------------------
# Census annual: world import total per sector (awm)
# ---------------------------------------------------------------------------
def fetch_annual_imports(year: int) -> dict:
    print(f"  import world {year} … ", end="", flush=True)
    data = _census_fetch(IMPORT_URL, {
        "get":      "I_COMMODITY,CTY_CODE,CTY_NAME,GEN_VAL_YR",
        "YEAR":     str(year),
        "MONTH":    "12",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"import world {year}")
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
        name = (row.get("CTY_NAME") or "").upper()
        if not _is_aggregate(name):
            awm[key] = awm.get(key, 0.0) + _to_float(row.get("GEN_VAL_YR"))

    print(f"{len(data)-1:,} rows")
    return awm

# ---------------------------------------------------------------------------
# Census exports YTD (cumulative through a given month)
# Returns (eu_ytd_val, eu_ytd_kg, world_ytd_kg) — all year-to-date cumulative.
#
# Uses ALL_VAL_YR (cumulative Jan–month) instead of ALL_VAL_MO (point-in-time)
# because the Census exports/hs endpoint only includes the "EUROPEAN UNION"
# aggregate row in cumulative queries; it is absent in monthly-only responses.
# The caller diffs consecutive months to derive point-in-time monthly values.
# ---------------------------------------------------------------------------
def fetch_exports_ytd(year: int, month: int) -> tuple[dict, dict, dict]:
    label = f"{year}{month:02d}"
    print(f"  export YTD {label} … ", end="", flush=True)
    data = _census_fetch(EXPORT_URL, {
        "get":      "E_COMMODITY,CTY_CODE,CTY_NAME,ALL_VAL_YR,AIR_WGT_YR,VES_WGT_YR",
        "YEAR":     str(year),
        "MONTH":    f"{month:02d}",
        "COMM_LVL": "HS6",
        "key":      CENSUS_KEY,
    }, f"export YTD {label}")
    if len(data) < 2:
        print("no data")
        return {}, {}, {}

    headers = data[0]
    eu_ytd_val:   dict[str, float] = {}
    eu_ytd_kg:    dict[str, float] = {}
    world_ytd_kg: dict[str, float] = {}

    for row_list in data[1:]:
        row  = dict(zip(headers, row_list))
        hs6  = row.get("E_COMMODITY", "")
        if not _is_cbam(hs6):
            continue
        key = hs6_to_key(hs6)
        if key is None:
            continue
        val = _to_float(row.get("ALL_VAL_YR"))
        wgt = _to_float(row.get("AIR_WGT_YR")) + _to_float(row.get("VES_WGT_YR"))
        name = (row.get("CTY_NAME") or "").upper()
        if _is_eu27(name):
            eu_ytd_val[key] = eu_ytd_val.get(key, 0.0) + val
            eu_ytd_kg[key]  = eu_ytd_kg.get(key,  0.0) + wgt
        elif not _is_aggregate(name):
            world_ytd_kg[key] = world_ytd_kg.get(key, 0.0) + wgt

    eu_n = sum(1 for v in eu_ytd_val.values() if v > 0)
    print(f"{len(data)-1:,} rows → {eu_n} EU sectors")
    return eu_ytd_val, eu_ytd_kg, world_ytd_kg

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
        url    = f"{COMEXT_BASE}/M.EU27_2020.US.{'+'.join(batch)}.1./"
        params = {"format": "SDMX-CSV", "startPeriod": "2022-01", "lang": "EN"}
        df     = pd.DataFrame()

        for attempt in range(4):
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
        if not {"time_period", "obs_value", "indicators"}.issubset(df.columns):
            time.sleep(0.3)
            continue

        df["period"]    = df["time_period"].astype(str).str.replace("-", "", regex=False)
        df["obs_value"] = pd.to_numeric(df["obs_value"], errors="coerce").fillna(0)

        for _, row in df[df["indicators"].str.upper() == "VALUE_IN_EUROS"].iterrows():
            p = str(row["period"])
            if len(p) == 6:
                result.setdefault(p, [0.0, 0.0])
                result[p][0] += float(row["obs_value"])

        for _, row in df[df["indicators"].str.upper() == "QUANTITY_IN_100KG"].iterrows():
            p = str(row["period"])
            if len(p) == 6:
                result.setdefault(p, [0.0, 0.0])
                result[p][1] += float(row["obs_value"]) / 10.0  # 100 kg → tonnes

        time.sleep(0.4)

    rounded = {p: [round(v, 2), round(t, 1)] for p, (v, t) in sorted(result.items())}
    print(f"{len(rounded)} months")
    return rounded

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
RAW_KEYS = ["72", "73", "76", "2523", "280410", "31", "2814"]

def build() -> None:
    # Load existing file as baseline so API failures never wipe good old data
    ex_raw: dict = {}
    ex_eu:  dict = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text())
            ex_raw = existing.get("RAW", {})
            ex_eu  = existing.get("RAWEU", {})
            print(f"Loaded baseline from {OUT}  ({OUT.stat().st_size//1024} KB)")
        except Exception as e:
            print(f"Warning: could not parse existing {OUT} ({e}) — starting fresh")

    RAW: dict = {k: {
        "ae":  dict(ex_raw.get(k, {}).get("ae",  {})),
        "awx": dict(ex_raw.get(k, {}).get("awx", {})),
        "awm": dict(ex_raw.get(k, {}).get("awm", {})),
        "aew": dict(ex_raw.get(k, {}).get("aew", {})),
        "me":  dict(ex_raw.get(k, {}).get("me",  {})),
        "mw":  dict(ex_raw.get(k, {}).get("mw",  {})),
        "mew": dict(ex_raw.get(k, {}).get("mew", {})),
    } for k in RAW_KEYS}

    RAWEU: dict = {k: dict(ex_eu.get(k, {})) for k in COMEXT_SECTORS}

    # ---- Annual EU27 exports from CSV (ae, aew) ----
    print("\n=== Annual EU27 exports (from us_eu27_trade_raw.csv) ===")
    ae, aew = load_annual_from_csv()
    for k in RAW_KEYS:
        RAW[k]["ae"].update(ae[k])
        RAW[k]["aew"].update(aew[k])

    # ---- Annual world exports from Census (awx) ----
    print("\n=== Census annual exports (world total for awx) ===")
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        awx = fetch_annual_exports_world(year)
        y = str(year)
        for k in RAW_KEYS:
            if awx.get(k):
                RAW[k]["awx"][y] = round(awx[k])
        time.sleep(0.5)

    # ---- Annual world imports from Census (awm) ----
    print("\n=== Census annual imports (world total for awm) ===")
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        awm = fetch_annual_imports(year)
        y = str(year)
        for k in RAW_KEYS:
            if awm.get(k):
                RAW[k]["awm"][y] = round(awm[k])
        time.sleep(0.5)

    # ---- Monthly exports from Census (me, mew, mw) ----
    # Each call fetches the cumulative YTD total through that month from the
    # annual endpoint (which includes the EU27 aggregate row).  Point-in-time
    # monthly values are the diff between consecutive months.
    print("\n=== Census monthly exports (me, mew, mw via YTD diff) ===")
    today = date.today()
    y, m  = MONTHLY_FROM
    prev_eu_val:   dict[str, float] = {}
    prev_eu_kg:    dict[str, float] = {}
    prev_world_kg: dict[str, float] = {}
    cur_year = y

    while (y, m) <= (today.year, today.month):
        if y != cur_year:           # New calendar year — YTD accumulators reset
            prev_eu_val   = {}
            prev_eu_kg    = {}
            prev_world_kg = {}
            cur_year      = y

        curr_eu_val, curr_eu_kg, curr_world_kg = fetch_exports_ytd(y, m)
        label = f"{y}{m:02d}"

        for k in RAW_KEYS:
            me_val  = curr_eu_val.get(k, 0)   - prev_eu_val.get(k, 0)
            mew_val = (curr_eu_kg.get(k, 0)   - prev_eu_kg.get(k, 0))   / 1000  # kg→t
            mw_val  = curr_world_kg.get(k, 0)  - prev_world_kg.get(k, 0)         # kg

            if me_val  > 0: RAW[k]["me"][label]  = round(me_val)
            if mew_val > 0: RAW[k]["mew"][label] = round(mew_val, 1)
            if mw_val  > 0: RAW[k]["mw"][label]  = round(mw_val)

        prev_eu_val   = curr_eu_val
        prev_eu_kg    = curr_eu_kg
        prev_world_kg = curr_world_kg

        m += 1
        if m > 12:
            m, y = 1, y + 1
        time.sleep(0.5)

    # ---- Comext monthly EU27 imports from US (RAWEU) ----
    print("\n=== Comext monthly EU imports from US ===")
    for sector, codes in COMEXT_SECTORS.items():
        fresh = fetch_comext_monthly(sector, codes)
        if fresh:
            RAWEU[sector] = fresh
        time.sleep(1.0)

    # ---- Write ----
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        json.dump({"RAW": RAW, "RAWEU": RAWEU}, fh, separators=(",", ":"))

    size_kb = OUT.stat().st_size / 1024
    print(f"\nWrote {OUT}  ({size_kb:.0f} KB)")

    # Quick sanity check
    ae_ok  = sum(1 for k in RAW_KEYS if RAW[k]["ae"])
    me_ok  = sum(1 for k in RAW_KEYS if RAW[k]["me"])
    eu_ok  = sum(1 for k in RAWEU if RAWEU[k])
    print(f"  ae populated: {ae_ok}/{len(RAW_KEYS)} sectors")
    print(f"  me populated: {me_ok}/{len(RAW_KEYS)} sectors")
    print(f"  RAWEU populated: {eu_ok}/{len(COMEXT_SECTORS)} sectors")


if __name__ == "__main__":
    build()
