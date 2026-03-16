import requests
import pandas as pd
from io import StringIO
import openpyxl

BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
YEARS = [2022, 2023, 2024]
BATCH_SIZE = 10

# ── Extract CN8 codes from the Excel default-value table ─────────────────────
wb = openpyxl.load_workbook("docs/EU_CBAM_default_value_US.xlsx")
ws = wb.active
cn8_codes = []
for row in ws.iter_rows(values_only=True):
    val = row[0]
    if val and isinstance(val, str) and any(c.isdigit() for c in val):
        clean = val.replace("\xa0", "").replace(" ", "")
        if len(clean) == 8 and clean.isdigit():
            cn8_codes.append(clean)

cn8_codes = sorted(set(cn8_codes))
print(f"Unique CN8 codes to query: {len(cn8_codes)}")

# ── Batch into groups and query API ──────────────────────────────────────────
batches = [
    "+".join(cn8_codes[i : i + BATCH_SIZE])
    for i in range(0, len(cn8_codes), BATCH_SIZE)
]

all_dfs = []
for i, batch in enumerate(batches):
    url = f"{BASE}/A.EU27_2020.US.{batch}../"
    r = requests.get(
        url,
        params={"format": "SDMX-CSV", "startPeriod": "2022", "endPeriod": "2024"},
        timeout=60,
    )
    if r.status_code != 200:
        print(f"  Batch {i+1}/{len(batches)} error {r.status_code}: {r.text[:200]}")
        continue
    df = pd.read_csv(StringIO(r.text))
    all_dfs.append(df)
    print(f"  Batch {i+1}/{len(batches)}: {len(df)} rows")

df_all = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
print(f"\nTotal rows fetched: {len(df_all)}")
if len(df_all):
    print("Indicators found:", df_all["indicators"].unique())
    print("Flows found:", df_all["flow"].unique())

# ── Filter to flow=1 (EU imports from US) ────────────────────────────────────
df = df_all[df_all["flow"] == 1].copy()
df["cn8"] = df["product"].astype(str).str.zfill(8)
df["year"] = df["TIME_PERIOD"].astype(int)

df_qty = df[df["indicators"] == "QUANTITY_IN_100KG"].copy()
df_val = df[df["indicators"] == "VALUE_IN_EUROS"].copy()

# Unit conversions: 100kg → tonnes; VALUE_IN_EUROS already in EUR
df_qty["tonnes"] = df_qty["OBS_VALUE"] / 10
df_val["eur"] = df_val["OBS_VALUE"]

# ── Pivot to wide format ──────────────────────────────────────────────────────
qty_wide = df_qty.pivot_table(index="cn8", columns="year", values="tonnes", aggfunc="sum")
val_wide = df_val.pivot_table(index="cn8", columns="year", values="eur", aggfunc="sum")

qty_wide.columns = [f"tonnes_{y}" for y in qty_wide.columns]
val_wide.columns = [f"eur_{y}" for y in val_wide.columns]

result = qty_wide.join(val_wide, how="outer").reset_index()

# ── Ensure all year columns exist, fill missing CN8s with 0 ──────────────────
for y in YEARS:
    for col in [f"tonnes_{y}", f"eur_{y}"]:
        if col not in result.columns:
            result[col] = 0.0

# Add any CN8 codes that returned no data at all
missing = set(cn8_codes) - set(result["cn8"])
if missing:
    print(f"\nNo API data for {len(missing)} codes (filled with 0): {sorted(missing)}")
    filler = pd.DataFrame({"cn8": sorted(missing)})
    for y in YEARS:
        filler[f"tonnes_{y}"] = 0.0
        filler[f"eur_{y}"] = 0.0
    result = pd.concat([result, filler], ignore_index=True)

result = result.fillna(0)

# ── Averages and final column order ──────────────────────────────────────────
result["avg_tonnes_per_year"] = result[[f"tonnes_{y}" for y in YEARS]].mean(axis=1)
result["avg_eur_per_year"] = result[[f"eur_{y}" for y in YEARS]].mean(axis=1)

cols = ["cn8", "tonnes_2022", "eur_2022", "tonnes_2023", "eur_2023",
        "tonnes_2024", "eur_2024", "avg_tonnes_per_year", "avg_eur_per_year"]
result = result[cols].sort_values("cn8").reset_index(drop=True)

print(f"\nResult: {len(result)} rows")
print(result.to_string())

result.to_csv("data/raw/comext_us_cbam_trade.csv", index=False)
print("\nSaved to data/raw/comext_us_cbam_trade.csv")
