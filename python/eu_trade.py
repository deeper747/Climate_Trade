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

all_dfs = []
for batch in BATCHES:
    url = f"{BASE}/A.EU27_2020.US.{batch}.1./"
    r = requests.get(url, params={"format": "SDMX-CSV", "startPeriod": "2021", "endPeriod": "2024"}, timeout=60)
    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text[:300]}")
        continue
    df = pd.read_csv(StringIO(r.text))
    all_dfs.append(df)

df_all = pd.concat(all_dfs, ignore_index=True)

print("Available indicators:", df_all["indicators"].unique())

# Keep only the two measures we need
df_val = df_all[df_all["indicators"] == "VALUE_IN_1000EUR"].copy()
df_qty = df_all[df_all["indicators"] == "QUANTITY_IN_100KG"].copy()

print(f"Value rows: {len(df_val)}, Quantity rows: {len(df_qty)}")

# Convert units: 1000 EUR → EUR; 100kg → tonnes (/10)
df_val["eur"] = df_val["OBS_VALUE"] * 1000
df_qty["tonnes"] = df_qty["OBS_VALUE"] / 10

# Average across 2021–2024 per product
val_avg = df_val.groupby("product")["eur"].mean().reset_index()
qty_avg = df_qty.groupby("product")["tonnes"].mean().reset_index()

result = val_avg.merge(qty_avg, on="product", how="outer")
result = result.rename(columns={"product": "cn4", "eur": "avg_eur_per_year", "tonnes": "avg_tonnes_per_year"})
print(result.to_string())
result.to_csv("data/raw/comext_us_cbam_trade.csv", index=False)
print("Saved to data/raw/comext_us_cbam_trade.csv")
