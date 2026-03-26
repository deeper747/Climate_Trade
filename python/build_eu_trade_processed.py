import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # Climate_Trade/
DATA = ROOT / "data"

RAW = DATA / "raw" / "eu_trade_hard_to_abate_partner_raw.csv"
OUT = DATA / "processed" / "eu_trade_hard_to_abate_partner.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(RAW)

required = ["period", "flow", "sector", "partnerDesc", "primaryValue"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise RuntimeError(f"Missing required columns: {missing}")

df = df[required].copy()

df["period"] = pd.to_numeric(df["period"], errors="coerce")
df["primaryValue"] = pd.to_numeric(df["primaryValue"], errors="coerce")
if "partnerDesc" not in df.columns:
    raise RuntimeError("partnerDesc column missing from raw Comtrade data.")

if "partnerCode" in df.columns:
    df["partnerDesc"] = df["partnerDesc"].fillna(df["partnerCode"].astype(str))

df = df.dropna(subset=["period", "partnerDesc", "primaryValue"])

df = df[df["partnerDesc"].str.lower() != "world"].copy()

df = df.rename(columns={"primaryValue": "trade_value_usd"})
df.to_csv(OUT, index=False)
print("Saved:", OUT)
