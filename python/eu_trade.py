import requests
import pandas as pd
from io import StringIO

BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"

BATCHES = [
    "7208+7209+7210+7211+7212+7213+7214+7215+7216+7217",
    "7218+7219+7220+7221+7222+7223+7224+7225+7226+7227",
    "7228+7229+7301+7302+7303+7304+7305+7306+7307+7308",
    "7309+7310+7311+7318+7326+7601+7603+7604+7605+7606",
    "7607+7608+7609+7610+7611+7612+7613+7614+7616+2814",
    "2808+2834+3102+3105+2601+2804+7201+7202+7203+7205",
]

YEARS = [2022, 2023, 2024]

all_dfs = []
for batch in BATCHES:
    url = f"{BASE}/A.EU27_2020.US.{batch}../"
    r = requests.get(
        url,
        params={"format": "SDMX-CSV", "startPeriod": "2022", "endPeriod": "2024"},
        timeout=60,
    )
    if r.status_code != 200:
        print(f"  Error {r.status_code} for batch {batch[:20]}...: {r.text[:200]}")
        continue
    df = pd.read_csv(StringIO(r.text))
    all_dfs.append(df)

df_all = pd.concat(all_dfs, ignore_index=True)
print(f"Total rows: {len(df_all)}, indicators: {df_all['indicators'].unique()}, flows: {df_all['flow'].unique()}")

# Flow 1 = imports to EU from US
df = df_all[df_all["flow"] == 1].copy()
df["cn4"] = df["product"].astype(str).str.zfill(4)
df["year"] = df["TIME_PERIOD"].astype(int)

df_qty = df[df["indicators"] == "QUANTITY_IN_100KG"].copy()
df_val = df[df["indicators"] == "VALUE_IN_EUROS"].copy()

# Convert units
df_qty["tonnes"] = df_qty["OBS_VALUE"] / 10      # 100kg → tonnes
df_val["eur"] = df_val["OBS_VALUE"]               # already in EUR

# Pivot to wide format
qty_wide = df_qty.pivot_table(index="cn4", columns="year", values="tonnes", aggfunc="sum")
val_wide = df_val.pivot_table(index="cn4", columns="year", values="eur", aggfunc="sum")

qty_wide.columns = [f"tonnes_{y}" for y in qty_wide.columns]
val_wide.columns = [f"eur_{y}" for y in val_wide.columns]

result = qty_wide.join(val_wide, how="outer").reset_index()

# Ensure all year columns exist even if missing from API
for y in YEARS:
    for col in [f"tonnes_{y}", f"eur_{y}"]:
        if col not in result.columns:
            result[col] = float("nan")

# Averages
result["avg_tonnes_per_year"] = result[[f"tonnes_{y}" for y in YEARS]].mean(axis=1)
result["avg_eur_per_year"] = result[[f"eur_{y}" for y in YEARS]].mean(axis=1)

# Final column order
cols = ["cn4", "tonnes_2022", "eur_2022", "tonnes_2023", "eur_2023", "tonnes_2024", "eur_2024",
        "avg_tonnes_per_year", "avg_eur_per_year"]
result = result[cols].sort_values("cn4").reset_index(drop=True)

print(result.to_string())
result.to_csv("data/raw/comext_us_cbam_trade.csv", index=False)
print(f"\nSaved {len(result)} rows to data/raw/comext_us_cbam_trade.csv")
