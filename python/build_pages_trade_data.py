from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "docs" / "data"
OUTDIR.mkdir(parents=True, exist_ok=True)


def load_eu_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "processed" / "eu_trade_hard_to_abate_partner.csv")
    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df["trade_value_usd"] = pd.to_numeric(df["trade_value_usd"], errors="coerce")
    df = df.dropna(subset=["period", "trade_value_usd", "sector", "partnerDesc", "flow"])
    df = df[df["partnerDesc"].str.lower() != "world"]
    df["sector"] = df["sector"].replace(
        {"iron_steel_72": "iron_steel", "iron_steel_73": "iron_steel"}
    )
    return (
        df.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)[
            "trade_value_usd"
        ].sum()
    )


def load_us_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "raw" / "us_trade_hard_to_abate_partner_raw.csv")
    if "flow" not in df.columns:
        if "flowCode" in df.columns:
            df["flow"] = df["flowCode"].map({"X": "Export", "M": "Import"})
        else:
            df["flow"] = "Export"
    value_col = next((col for col in ["primaryValue", "tradeValue"] if col in df.columns), None)
    if value_col is None:
        raise ValueError("No value column found in U.S. trade data.")

    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=["period", value_col, "sector", "partnerDesc", "flow"])
    df = df[df["partnerDesc"].str.lower() != "world"]
    df = df.rename(columns={value_col: "trade_value_usd"})
    return df[["period", "flow", "sector", "partnerDesc", "trade_value_usd"]]


def export_json(df: pd.DataFrame, filename: str) -> None:
    records = df.assign(period=lambda data: data["period"].astype(int)).to_dict("records")
    with (OUTDIR / filename).open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    export_json(load_eu_data(), "eu_trade.json")
    export_json(load_us_data(), "us_trade.json")
    print(f"Wrote data files to {OUTDIR}")


if __name__ == "__main__":
    main()
