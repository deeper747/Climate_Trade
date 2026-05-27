from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "docs" / "data"
OUTDIR.mkdir(parents=True, exist_ok=True)


def _agg(df: pd.DataFrame, extra_cols: list[str]) -> pd.DataFrame:
    """Group by period/flow/sector/partner, summing value + any extra columns."""
    agg_spec = {"trade_value_usd": ("trade_value_usd", "sum")}
    for col in extra_cols:
        agg_spec[col] = (col, "sum")
    return df.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False).agg(**agg_spec)


def load_eu_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "processed" / "eu_trade_hard_to_abate_partner.csv")
    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df["trade_value_usd"] = pd.to_numeric(df["trade_value_usd"], errors="coerce")
    df = df.dropna(subset=["period", "trade_value_usd", "sector", "partnerDesc", "flow"])
    df = df[df["partnerDesc"].str.lower() != "world"]
    df["sector"] = df["sector"].replace(
        {"iron_steel_72": "iron_steel", "iron_steel_73": "iron_steel"}
    )
    if "quantity_mt" in df.columns:
        df["quantity_mt"] = pd.to_numeric(df["quantity_mt"], errors="coerce")
        return _agg(df, ["quantity_mt"])
    return _agg(df, [])


def load_us_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "raw" / "us_trade_hard_to_abate_partner_raw.csv")
    # Support both old UN Comtrade schema and new Census schema
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

    # Merge iron_steel_72 + iron_steel_73 → iron_steel for US tab if split sectors present
    if "iron_steel_72" in df["sector"].values or "iron_steel_73" in df["sector"].values:
        df["sector"] = df["sector"].replace(
            {"iron_steel_72": "iron_steel", "iron_steel_73": "iron_steel"}
        )

    df = df.rename(columns={value_col: "trade_value_usd"})

    # Convert weight kg → metric tons if available
    if "quantity_kg" in df.columns:
        df["quantity_mt"] = pd.to_numeric(df["quantity_kg"], errors="coerce") / 1000.0
        extra = ["quantity_mt"]
    else:
        extra = []

    return _agg(df[["period", "flow", "sector", "partnerDesc", "trade_value_usd"] + extra], extra)


def export_json(df: pd.DataFrame, filename: str) -> None:
    df = df.assign(period=lambda data: data["period"].astype(int))
    if "quantity_mt" in df.columns:
        df["quantity_mt"] = df["quantity_mt"].round(1)
    # Replace NaN/NA with None so json.dump produces valid JSON null
    records = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in df.where(pd.notna(df), other=None).to_dict("records")
    ]
    with (OUTDIR / filename).open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    export_json(load_eu_data(), "eu_trade.json")
    export_json(load_us_data(), "us_trade.json")
    print(f"Wrote data files to {OUTDIR}")


if __name__ == "__main__":
    main()
