"""
Fetch EU bilateral trade data from Eurostat COMEXT DS-045409 (annual).

API: https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409
URL path: /A.{DECLARANT}..{PRODUCT}.{FLOW}./
  Empty PARTNER slot = all extra-EU partners.
  Empty INDICATORS slot = all indicators (filtered to VALUE_IN_EUROS below).

CN codes sourced from EU Implementing Regulation 2025/2620 Annex I
(reference/cbamBenchmarks.js). Codes are queried at their regulation
digit level; the API aggregates all CN8 sub-codes automatically.

Output: data/raw/eu_trade_hard_to_abate_partner_raw.csv
        Columns: period, flow, sector, partnerDesc, primaryValue (EUR)
        Schema-compatible with build_eu_trade_processed.py.
"""

from __future__ import annotations

import time
import requests
import pandas as pd
from io import StringIO
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "raw"
OUTDIR.mkdir(parents=True, exist_ok=True)

BASE_URL   = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
DECLARANT  = "EU27_2020"
START_YEAR = "2019"
END_YEAR   = "2025"
BATCH_SIZE = 10   # max CN codes per API call (mirrors reference/process_trade_data.py)

# ---------------------------------------------------------------------------
# CN codes per sector — from EU IR 2025/2620 Annex I (cbamBenchmarks.js)
# ---------------------------------------------------------------------------
SECTORS: dict[str, list[str]] = {
    "iron_steel_72": [
        # HS 26 precursor included under CBAM iron & steel
        "26011200",
        # HS 72 — primary iron & steel products
        "7201", "720211", "720241", "72026000",
        "7203",
        "7205", "72061000",
        "7208", "7209", "7210", "72111300", "7212", "7213", "72142000",
        "7215", "7216",
        "721710", "721720",
        "72181000", "72191100", "72193100",
        "7221", "722300",
        "722410", "72251100", "722530", "722550",
    ],
    "iron_steel_73": [
        # HS 73 — articles of iron & steel (incl. cast iron HS 7303)
        "730300",
        "7301", "7302",
        "730419", "730439",
        "7305", "73061900", "73063080",
        "73072100", "73079100",
        "7308", "7309", "7310", "731100",
        "731815", "731816", "73182200", "73182300",
        "73269098",
    ],
    "aluminum_76": [
        "7601", "7603",
        "76041010", "76041090", "76042100", "76042910", "76042990",
        "7605", "7606", "7607", "7608",
        "76090000", "76101000", "76110000",
        "7612", "76130000", "7614",
        "76161000", "76169100", "76169910", "76169990",
    ],
    "cement_2523": [
        # HS 25 — clinker, cement, and kaolinic clay precursor (HS 2507)
        "25070080",
        "25231000", "25232100", "25232900", "25233000", "25239000",
    ],
}

FLOW_CODES: dict[str, str] = {
    "Export": "2",
    "Import": "1",
}

# ---------------------------------------------------------------------------
# Eurostat ISO-2 partner codes → display names (aligned with app.js PARTNER_COLORS)
# ---------------------------------------------------------------------------
PARTNER_NAMES: dict[str, str] = {
    "CN": "China",
    "RU": "Russian Federation",
    "TR": "Türkiye",
    "IN": "India",
    "GB": "United Kingdom",
    "KR": "Rep. of Korea",
    "UA": "Ukraine",
    "VN": "Viet Nam",
    "JP": "Japan",
    "ID": "Indonesia",
    "EG": "Egypt",
    "AE": "United Arab Emirates",
    "US": "USA",
    "CH": "Switzerland",
    "NO": "Norway",
    "CA": "Canada",
    "MX": "Mexico",
    "BR": "Brazil",
    "MY": "Malaysia",
    "TW": "Taiwan",
    "SA": "Saudi Arabia",
    "ZA": "South Africa",
    "AU": "Australia",
    "IR": "Iran",
    "PK": "Pakistan",
    "TH": "Thailand",
    "PH": "Philippines",
    "BD": "Bangladesh",
    "MA": "Morocco",
    "DZ": "Algeria",
    "NG": "Nigeria",
    "AR": "Argentina",
    "MK": "North Macedonia",
    "RS": "Serbia",
    "XS": "Serbia",          # Eurostat legacy code for Serbia
    "BA": "Bosnia and Herzegovina",
    "AL": "Albania",
    "ME": "Montenegro",
    "MD": "Moldova",
    "GE": "Georgia",
    "AM": "Armenia",
    "AZ": "Azerbaijan",
    "KZ": "Kazakhstan",
    "UZ": "Uzbekistan",
    "BY": "Belarus",
    "LY": "Libya",
    "TN": "Tunisia",
    "IL": "Israel",
    "SG": "Singapore",
    "IS": "Iceland",
    "QA": "Qatar",
    "MZ": "Mozambique",
    "BH": "Bahrain",
    "CL": "Chile",
    "CO": "Colombia",
    "VE": "Venezuela",
    "EG": "Egypt",
    "KW": "Kuwait",
    "OM": "Oman",
    "QP": "Palestine",       # Eurostat code for Palestinian Territory
    "QM": "Montenegro",      # Eurostat legacy code
    "XK": "Kosovo",
}

# Partner codes to drop: EU-level aggregates + all EU-27 member states.
# CBAM covers extra-EU trade only; intra-EU is not relevant.
# Eurostat uses "EL" for Greece (not "GR").
AGGREGATE_CODES: set[str] = {
    "EU27_2020", "EU28", "EU27", "EU25", "EU15",
    "INT_EU27_2020", "EXT_EU27_2020",
    "WORLD", "WRL", "TOTAL", "EEA", "EFTA", "INTRA_EU", "EXTRA_EU",
    # EU-27 member states (Eurostat uses "EL" for Greece, but "GR" appears in some data vintages)
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "GR", "ES",
    "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_batch(cn_codes: list[str], flow_code: str) -> pd.DataFrame:
    """Fetch a batch of CN codes (joined with +) for all partners and all years."""
    codes_str = "+".join(cn_codes)
    url = f"{BASE_URL}/A.{DECLARANT}..{codes_str}.{flow_code}./"
    params = {
        "format":      "SDMX-CSV",
        "startPeriod": START_YEAR,
        "endPeriod":   END_YEAR,
        "lang":        "EN",
    }

    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=120)
        except requests.RequestException as exc:
            print(f"\n    Network error (attempt {attempt + 1}): {exc}")
            time.sleep(2 ** attempt)
            continue

        if resp.ok:
            return pd.read_csv(StringIO(resp.text))

        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"\n    Rate limited — waiting {wait}s …", end="", flush=True)
            time.sleep(wait)
            continue

        if resp.status_code in (400, 404):
            return pd.DataFrame()

        print(f"\n    HTTP {resp.status_code}: {resp.text[:120]}")
        return pd.DataFrame()

    return pd.DataFrame()


def clean_df(df: pd.DataFrame, flow_name: str, sector_name: str) -> pd.DataFrame | None:
    """Normalise columns, filter to EUR values, map partner codes → names."""
    df.columns = [c.lower() for c in df.columns]

    if "indicators" in df.columns:
        df = df[df["indicators"].str.upper() == "VALUE_IN_EUROS"].copy()

    missing = [c for c in ("partner", "time_period", "obs_value") if c not in df.columns]
    if missing:
        print(f"\n    Missing columns {missing}; skipping")
        return None

    df = df[df["partner"].notna()].copy()
    df = df[~df["partner"].astype(str).isin(AGGREGATE_CODES)].copy()

    df["partnerDesc"] = df["partner"].astype(str).map(PARTNER_NAMES).fillna(df["partner"].astype(str))
    df["period"]      = pd.to_numeric(df["time_period"].astype(str).str[:4], errors="coerce").astype("Int64")
    df["primaryValue"] = pd.to_numeric(df["obs_value"], errors="coerce")
    df["flow"]         = flow_name
    df["sector"]       = sector_name

    return df[["period", "flow", "sector", "partnerDesc", "primaryValue"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    frames: list[pd.DataFrame] = []

    for sector_name, cn_codes in SECTORS.items():
        batches = [cn_codes[i : i + BATCH_SIZE] for i in range(0, len(cn_codes), BATCH_SIZE)]

        for flow_name, flow_code in FLOW_CODES.items():
            print(f"\n{sector_name}  {flow_name}  ({len(cn_codes)} codes, {len(batches)} batches)")
            sector_frames: list[pd.DataFrame] = []

            for b_idx, batch in enumerate(batches):
                print(f"  batch {b_idx + 1}/{len(batches)}: {'+'.join(batch)[:60]} … ", end="", flush=True)
                df_raw = fetch_batch(batch, flow_code)

                if df_raw.empty:
                    print("(no data)")
                    continue

                print(f"{len(df_raw):,} rows", end=" → ", flush=True)
                df = clean_df(df_raw, flow_name, sector_name)
                if df is None:
                    continue

                sector_frames.append(df)
                print(f"{len(df):,} EUR rows")
                time.sleep(0.5)

            if sector_frames:
                # Aggregate all batches: sum CN-code rows for same partner × year
                combined = pd.concat(sector_frames, ignore_index=True)
                agg = (
                    combined.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)
                            ["primaryValue"].sum()
                )
                frames.append(agg)
                print(f"  → {len(agg):,} aggregated rows")

    if not frames:
        print("\nNo data fetched — check network or API.")
        return

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["period", "partnerDesc", "primaryValue"])

    out_path = OUTDIR / "eu_trade_hard_to_abate_partner_raw.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(out):,} rows)")
    print("Note: 'primaryValue' is in EUR (Eurostat COMEXT DS-045409).")


if __name__ == "__main__":
    main()
