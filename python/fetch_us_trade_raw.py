import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # loads .env from the project root

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
API_KEY = os.getenv("COMTRADE_API_KEY")


if not API_KEY:
    raise RuntimeError("COMTRADE_API_KEY is not set in this terminal session.")

HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY}

FLOWS = {
    "X": "Export",
    "M": "Import",
}

REPORTER_USA = "842"   # USA
PARTNER_ALL = "0"      # all partners
FLOW_EXPORT = "X"      # exports

YEARS = [2019, 2020, 2021, 2022, 2023]

SECTORS = {
    "iron_steel": ["72", "73"],  # HS 72-73
    "aluminum": ["76"],          # HS 76
    "cement": ["2523"],          # HS 2523
}


def fetch(year: int, hs_code: str, flow_code: str, max_retries: int = 5) -> pd.DataFrame:
    params = {
        "reporterCode": REPORTER_USA,
        "period": str(year),
        "cmdCode": hs_code,
        "flowCode": flow_code,      # "X" or "M"
        "includeDesc": "true",
    }

    for attempt in range(1, max_retries + 1):
        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=60)

        if r.status_code == 200:
            payload = r.json()
            rows = payload.get("data", [])
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows)

        if r.status_code == 429:
            wait = max(1, attempt)   # exponential-ish backoff
            print(f"Rate limited (429). Waiting {wait}s before retry...")
            time.sleep(wait)
            continue

        # Any other error
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

    raise RuntimeError(f"Failed after {max_retries} retries for {year}, HS {hs_code}")


def main():
    all_frames = []
    for flow_code, flow_name in FLOWS.items():
        for sector, codes in SECTORS.items():
            for year in YEARS:
                for code in codes:
                    print(f"Requesting {year} sector={sector} HS={code}")
                    df = fetch(year, code, flow_code)
                    if not df.empty:
                        df["sector"] = sector
                        all_frames.append(df)

                    time.sleep(1.2)  # ← IMPORTANT: polite pacing

    out = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()

    os.makedirs("data/raw", exist_ok=True)
    out.to_csv("data/raw/us_trade_hard_to_abate_partner_raw.csv", index=False)
    print("Saved: data/raw/us_trade_hard_to_abate_partner_raw.csv")
    print(out.head())

if __name__ == "__main__":
    main()
