"""
Download Eurostat Comext trade data for all CBAM regulation CN codes (US → EU27).

API notes (from working original):
  - Annual endpoint (A.) with batched CN codes works reliably.
  - Flow 1 (imports) is specified in the URL path itself: A.EU27_2020.US.{codes}.1./
  - Value indicator on the annual dataset is VALUE_IN_EUROS (already in EUR, no conversion needed).
  - CN4/CN6/CN8 codes all work as query keys; API returns aggregate for that hierarchy level.

CN code level rule (for codes listed in IR 2025/2621 Annex I):
  - Codes are stored at their regulation digit level (4, 6, or 8 digits).
  - Trailing-zero padding to 8 digits is NOT used — querying "7601" returns all CN8 sub-codes.

Output: data/raw/comext_us_cbam_trade_by_year.csv
"""

import requests
import pandas as pd
from io import StringIO
import time

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
YEARS = [2022, 2023, 2024]
BATCH_SIZE = 10

# ── CBAM regulation CN codes (IR 2025/2621 Annex I) ─────────────────────────
# Stored at the regulation digit level (CN4, CN6, or CN8 as listed).
# When a CN4/CN6 code is used, the API aggregates all sub-codes automatically.
CBAM_CN_CODES = [
    # Cement
    ("25070080", "Cement"),
    ("25231000", "Cement"),
    ("25232100", "Cement"),
    ("25232900", "Cement"),
    ("25233000", "Cement"),
    ("25239000", "Cement"),
    # Fertilisers
    ("28080000", "Fertilisers"),
    ("28141000", "Fertilisers"),
    ("28142000", "Fertilisers"),
    ("28342100", "Fertilisers"),
    ("31021012", "Fertilisers"),
    ("31021015", "Fertilisers"),
    ("31021019", "Fertilisers"),
    ("31021090", "Fertilisers"),
    ("31022100", "Fertilisers"),
    ("31022900", "Fertilisers"),
    ("31023010", "Fertilisers"),
    ("31023090", "Fertilisers"),
    ("31024010", "Fertilisers"),
    ("31024090", "Fertilisers"),
    ("31025000", "Fertilisers"),
    ("31026000", "Fertilisers"),
    ("31028000", "Fertilisers"),
    ("31029000", "Fertilisers"),
    ("31051000", "Fertilisers"),
    ("31052010", "Fertilisers"),
    ("31052090", "Fertilisers"),
    ("31053000", "Fertilisers"),
    ("31054000", "Fertilisers"),
    ("31055100", "Fertilisers"),
    ("31055900", "Fertilisers"),
    ("31059020", "Fertilisers"),
    ("31059080", "Fertilisers"),
    # Aluminium — CN4 codes (API aggregates all sub-chapters)
    ("7601", "Aluminium"),
    ("7603", "Aluminium"),
    ("76041010", "Aluminium"),
    ("76041090", "Aluminium"),
    ("76042100", "Aluminium"),
    ("76042910", "Aluminium"),
    ("76042990", "Aluminium"),
    ("7605", "Aluminium"),
    ("7606", "Aluminium"),
    ("7607", "Aluminium"),
    ("7608", "Aluminium"),
    ("76090000", "Aluminium"),
    ("76101000", "Aluminium"),
    ("76110000", "Aluminium"),
    ("7612", "Aluminium"),
    ("76130000", "Aluminium"),
    ("7614", "Aluminium"),
    ("76161000", "Aluminium"),
    ("76169100", "Aluminium"),
    ("76169910", "Aluminium"),
    ("76169990", "Aluminium"),
    # Hydrogen
    ("28041000", "Hydrogen"),
    # Iron & Steel — mix of CN4, CN6, CN8
    ("26011200", "Iron & Steel"),
    ("7201", "Iron & Steel"),          # CN4
    ("720211", "Iron & Steel"),        # CN6: 7202 11
    ("720241", "Iron & Steel"),        # CN6: 7202 41
    ("72026000", "Iron & Steel"),
    ("7203", "Iron & Steel"),          # CN4
    ("7205", "Iron & Steel"),          # CN4
    ("72061000", "Iron & Steel"),
    ("7208", "Iron & Steel"),          # CN4
    ("7209", "Iron & Steel"),          # CN4
    ("7210", "Iron & Steel"),          # CN4
    ("72111300", "Iron & Steel"),
    ("7212", "Iron & Steel"),          # CN4
    ("7213", "Iron & Steel"),          # CN4
    ("72142000", "Iron & Steel"),
    ("7215", "Iron & Steel"),          # CN4
    ("7216", "Iron & Steel"),          # CN4
    ("721710", "Iron & Steel"),        # CN6: 7217 10
    ("721720", "Iron & Steel"),        # CN6: 7217 20
    ("72181000", "Iron & Steel"),
    ("72191100", "Iron & Steel"),
    ("72193100", "Iron & Steel"),
    ("7221", "Iron & Steel"),          # CN4
    ("722300", "Iron & Steel"),        # CN6: 7223 00
    ("722410", "Iron & Steel"),        # CN6: 7224 10
    ("72251100", "Iron & Steel"),
    ("722530", "Iron & Steel"),        # CN6: 7225 30
    ("722550", "Iron & Steel"),        # CN6: 7225 50
    ("7301", "Iron & Steel"),          # CN4
    ("7302", "Iron & Steel"),          # CN4
    ("7303", "Iron & Steel"),          # CN4 (73030000 is not a valid CN8; use parent)
    ("730419", "Iron & Steel"),        # CN6: 7304 19
    ("730439", "Iron & Steel"),        # CN6: 7304 39
    ("7305", "Iron & Steel"),          # CN4
    ("73061900", "Iron & Steel"),
    ("73063080", "Iron & Steel"),
    ("73072100", "Iron & Steel"),
    ("73079100", "Iron & Steel"),
    ("7308", "Iron & Steel"),          # CN4
    ("7309", "Iron & Steel"),          # CN4
    ("7310", "Iron & Steel"),          # CN4
    ("731100", "Iron & Steel"),        # CN6: 7311 00
    ("731815", "Iron & Steel"),        # CN6: 7318 15
    ("731816", "Iron & Steel"),        # CN6: 7318 16
    ("73182200", "Iron & Steel"),
    ("73182300", "Iron & Steel"),
    ("73269098", "Iron & Steel"),
]


def main():
    # Deduplicate codes, preserving sector mapping
    seen = set()
    cn_entries = []
    for cn, sector in CBAM_CN_CODES:
        if cn not in seen:
            seen.add(cn)
            cn_entries.append((cn, sector))

    sector_map = {cn: sector for cn, sector in cn_entries}
    codes = [cn for cn, _ in cn_entries]
    print(f"Unique regulation codes to query: {len(codes)}")

    # Batch queries against the annual endpoint
    batches = [codes[i : i + BATCH_SIZE] for i in range(0, len(codes), BATCH_SIZE)]
    all_dfs = []

    for i, batch in enumerate(batches):
        batch_str = "+".join(batch)
        # Flow 1 = imports; annual frequency (A.)
        url = f"{BASE_URL}/A.EU27_2020.US.{batch_str}.1./"
        print(f"  Batch {i+1}/{len(batches)}: {batch_str[:50]}", end=" ... ", flush=True)
        for attempt in range(3):
            try:
                r = requests.get(
                    url,
                    params={
                        "format": "SDMX-CSV",
                        "startPeriod": str(min(YEARS)),
                        "endPeriod": str(max(YEARS)),
                    },
                    timeout=60,
                )
                if r.ok:
                    df = pd.read_csv(StringIO(r.text))
                    all_dfs.append(df)
                    print(f"ok ({len(df)} rows)")
                    break
                print(f"HTTP {r.status_code}", end=" ")
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                else:
                    break
            except Exception as e:
                print(f"error: {e}", end=" ")
            time.sleep(1)
        else:
            print("FAILED after 3 attempts")
        time.sleep(0.3)

    if not all_dfs:
        print("No data fetched — check network or API availability.")
        return

    df_all = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal rows fetched: {len(df_all)}")
    print("Indicators found:", df_all["indicators"].unique())

    # Normalise product code to string for mapping
    df_all["product"] = df_all["product"].astype(str)

    # Quantity: 100 kg → tonnes
    df_qty = df_all[df_all["indicators"] == "QUANTITY_IN_100KG"].copy()
    df_qty["tonnes"] = df_qty["OBS_VALUE"] / 10

    # Value: annual dataset uses VALUE_IN_EUROS directly
    df_val = df_all[df_all["indicators"] == "VALUE_IN_EUROS"].copy()
    df_val["eur"] = df_val["OBS_VALUE"]

    # Pivot by (product, year)
    qty_wide = df_qty.pivot_table(index="product", columns="TIME_PERIOD", values="tonnes", aggfunc="sum")
    val_wide = df_val.pivot_table(index="product", columns="TIME_PERIOD", values="eur", aggfunc="sum")

    qty_wide.columns = [f"tonnes_{y}" for y in qty_wide.columns]
    val_wide.columns = [f"eur_{y}" for y in val_wide.columns]

    result = qty_wide.join(val_wide, how="outer").reset_index()
    result = result.rename(columns={"product": "cn_code"})
    result["sector"] = result["cn_code"].map(sector_map)

    # Add any CBAM codes the API returned zero data for (no trade = 0, not missing)
    returned = set(result["cn_code"])
    missing_rows = [
        {"cn_code": cn, "sector": sec}
        for cn, sec in cn_entries
        if cn not in returned
    ]
    if missing_rows:
        print(f"  Codes with no API data (zero trade): {[r['cn_code'] for r in missing_rows]}")
        result = pd.concat([result, pd.DataFrame(missing_rows)], ignore_index=True)

    # Ensure all year columns exist; fill NaN → 0 (no trade row = zero, not unknown)
    for y in YEARS:
        for col in [f"tonnes_{y}", f"eur_{y}"]:
            if col not in result.columns:
                result[col] = 0.0
            else:
                result[col] = result[col].fillna(0.0)

    # Averages across requested years
    result["avg_tonnes"] = result[[f"tonnes_{y}" for y in YEARS]].mean(axis=1)
    result["avg_eur"] = result[[f"eur_{y}" for y in YEARS]].mean(axis=1)

    cols = ["cn_code", "sector"] + [
        c for y in YEARS for c in [f"tonnes_{y}", f"eur_{y}"]
    ] + ["avg_tonnes", "avg_eur"]
    result = result[[c for c in cols if c in result.columns]].sort_values("cn_code").reset_index(drop=True)

    out = "data/raw/comext_us_cbam_trade_by_year.csv"
    result.to_csv(out, index=False)
    print(f"\nDone. Saved {len(result)} rows → {out}")
    print(result[["cn_code", "sector", "avg_tonnes", "avg_eur"]].to_string())


if __name__ == "__main__":
    main()
