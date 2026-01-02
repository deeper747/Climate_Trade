import os
import time
import random
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COMTRADE_API_KEY")
if not API_KEY:
    raise RuntimeError("COMTRADE_API_KEY not found in environment/.env")

BASE = "https://comtradeapi.un.org/data/v1/get"
HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY}

ROOT = Path(__file__).resolve().parents[1]   # Climate_Trade/
DATA = ROOT / "data"
OUTDIR = DATA / "raw"
OUTDIR.mkdir(parents=True, exist_ok=True)

REPORTER_CODE = "97"  # EU aggregate (often EU-28)  
FREQ = "A"
CL = "HS"

SECTORS = {
    "iron_steel_72": "72",
    "iron_steel_73": "73",
    "aluminum_76": "76",
    "cement_2523": "2523",
}

YEARS = list(range(2019, 2024))
FLOWS = {"Export": "X", "Import": "M"}

def call_comtrade(cmd_code: str, year: int, flow_code: str, reporter_code: str = "97") -> pd.DataFrame:
    """
    All partners breakdown: DO NOT send partnerCode at all. (partnerCode=None)
    """
    params = {
        "reporterCode": reporter_code,
        "period": str(year),
        "cmdCode": cmd_code,
        "flowCode": flow_code,
        "includeDesc": "true",
        "maxRecords": "250000",
        "breakdownMode": "classic",
    }

    url = f"{BASE}/C/A/HS"

    for attempt in range(10):
        r = requests.get(url, params=params, headers=HEADERS, timeout=90)

        if r.status_code == 200:
            js = r.json()
            return pd.DataFrame(js.get("data", []))

        if r.status_code == 429:
            wait = 1.0 + attempt * 1.5 + random.random()
            time.sleep(wait)
            continue

        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")

    raise RuntimeError("Too many retries (rate limiting). Try again later.")

def main():
    frames = []
    for year in YEARS:
        for flow_name, flow_code in FLOWS.items():
            for sector_name, cmd_code in SECTORS.items():
                print(f"Fetching EU {year} {flow_name} HS={cmd_code} ...")
                df = call_comtrade(cmd_code=cmd_code, year=year, flow_code=flow_code, reporter_code="97")
                if df.empty:
                    continue

                # Keep only what you need (adjust if your payload differs)
                keep = [
                    "period", "flowCode", "flowDesc",
                    "reporterCode", "reporterDesc",
                    "partnerCode", "partnerDesc",
                    "cmdCode", "cmdDesc",
                    "tradeValue", "primaryValue",
                    "qty", "qtyUnitCode", "qtyUnitAbbr",
                ]
                for c in keep:
                    if c not in df.columns:
                        df[c] = pd.NA

                df["year"] = year
                df["flow"] = flow_name
                df["sector"] = sector_name
                frames.append(df[keep + ["year", "flow", "sector"]])

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # pick value column
    value_col = "tradeValue" if "tradeValue" in out.columns else "primaryValue"
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")

    # drop world aggregate if it appears
    out = out[out["partnerDesc"].astype(str).str.lower() != "world"].copy()

    out_path = OUTDIR / "eu_trade_hard_to_abate_partner_raw.csv"
    out.to_csv(out_path, index=False)
    print(f"Saved: {out_path} ({len(out):,} rows)")

if __name__ == "__main__":
    main()
