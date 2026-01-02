import pandas as pd
import altair as alt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # Climate_Trade/

INP = ROOT / "data" / "processed" / "eu_trade_hard_to_abate_partner.csv"
OUTDIR = ROOT / "docs"
OUTDIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INP)
df["period"] = df["period"].astype(int).astype(str)  # treat as ordinal labels

# Example: aggregate HS72+73 into one "iron_steel" (optional)
df["sector"] = df["sector"].replace({"iron_steel_72":"iron_steel", "iron_steel_73":"iron_steel"})
df = df.groupby(["period","flow","sector","partnerDesc"], as_index=False)["trade_value_usd"].sum()

# Compute share within (period, flow, sector)
df["year_flow_sector_total"] = df.groupby(["period","flow","sector"])["trade_value_usd"].transform("sum")
df["total_usd"] = df.groupby(["period","flow","sector"])["trade_value_usd"].transform("sum")
df["share_pct"] = (df["trade_value_usd"] / df["total_usd"] * 100).fillna(0)
df = df.drop(columns=["total_usd"])

# Simple top-N grouping per year/flow/sector (optional)
TOP_N = 8
df["rank"] = df.groupby(["period","flow","sector"])["trade_value_usd"].rank(method="first", ascending=False)
df["partner_group"] = df.apply(lambda r: r["partnerDesc"] if r["rank"] <= TOP_N else "Other", axis=1)
df = df.groupby(["period","flow","sector","partner_group"], as_index=False).agg(
    trade_value_usd=("trade_value_usd","sum"),
    share_pct=("share_pct","sum"),
)
df["trade_value_busd"] = df["trade_value_usd"] / 1e9


SORT_YEAR = "2023"

# Rank partners WITHIN EACH SECTOR by Import value in SORT_YEAR
rank_df = (
    df[(df["period"] == SORT_YEAR) & (df["flow"] == "Import")]
    .groupby(["sector", "partner_group"], as_index=False)["trade_value_usd"]
    .sum()
)

# rank 1 = biggest
rank_df["stack_rank"] = rank_df.groupby("sector")["trade_value_usd"].rank(
    method="first", ascending=False
)

# force "Other" to the end
rank_df.loc[rank_df["partner_group"] == "Other", "stack_rank"] = 9999

# merge back to main df
df = df.merge(rank_df[["sector", "partner_group", "stack_rank"]],
              on=["sector", "partner_group"], how="left")

# anything not in 2023 import ranking goes after ranked ones (but before Other)
df["stack_rank"] = df["stack_rank"].fillna(9000)

sector_param = alt.param(
    name="Sector",
    bind=alt.binding_select(options=sorted(df["sector"].unique())),
    value=sorted(df["sector"].unique())[0],
)

# --- Two selections: one for opacity, one for "active hover" ---
mask = alt.selection_point(
    fields=["partner_group","flow"],
    on="mouseover",
    empty="all",
    clear="mouseout"
)

hover = alt.selection_point(
    fields=["partner_group","flow"],
    on="mouseover",
    empty="none",
    clear="mouseout"
)

base = alt.Chart(df).transform_filter(
    alt.datum.sector == sector_param
)

bars = base.mark_bar().encode(
    y=alt.Y("period:O", title="Year"),
    x=alt.X(
        "trade_value_busd:Q",
        title="Trade value (billion USD)",
        axis=alt.Axis(format=",.0f")
    ),
    color=alt.Color(
    "partner_group:N",
    title="Partner",
    sort=alt.SortField("stack_rank", order="ascending"),),
    order=alt.Order("stack_rank:Q", sort="ascending"),
    row=alt.Row("flow:N", title=None),
    opacity=alt.condition(mask, alt.value(1.0), alt.value(0.15)),
    tooltip=[
        alt.Tooltip("period:O", title="Year"),
        alt.Tooltip("flow:N", title="Flow"),
        alt.Tooltip("partner_group:N", title="Partner"),
        alt.Tooltip("trade_value_busd:Q", title="Value ($M)", format=",.1f"),
        alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
    ],
).add_params(mask, hover, sector_param).properties(width=900)

# Title should show ONLY the hovered partner, and only one copy
share_title = (
    base.transform_filter(hover)
    .transform_aggregate(partner_group="max(partner_group)", groupby=[])
    .mark_text(align="center", baseline="bottom", fontSize=16, dy=-5)
    .encode(text="partner_group:N")
    .properties(width=900, height=25)
)

# Share line: ONLY the hovered series
share = (
    base.transform_filter(hover)
    .mark_line(point=True)
    .encode(
        x=alt.X("period:O", title="Year"),
        y=alt.Y("share_pct:Q", title="Share (%)", scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip("period:O", title="Year"),
            alt.Tooltip("flow:N", title="Flow"),
            alt.Tooltip("partner_group:N", title="Partner"),
            alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
        ],
    )
    .properties(width=900, height=180)
)

share_block = alt.vconcat(share_title, share, spacing=0)

footer_text = (
    "Source: UN Comtrade (via comtradeapi.un.org). "
    "Prepared by Jia-Shen Tsai, Niskanen Center. "
    "Values in current USD."
)

footer = (
    alt.Chart(pd.DataFrame({"text":[footer_text]}))
    .mark_text(align="left", baseline="top", fontSize=12)
    .encode(text="text:N")
    .properties(width=900, height=30)
)

chart = (
    alt.vconcat(bars, share_block, footer, spacing=15)
    .resolve_scale(color="shared")
    .properties(title={
        "text": "EU Hard-to-Abate Trade (Iron & Steel, Aluminum, Cement) — Partner Shares Over Time",
        "fontSize": 22,          # ← increase this (try 24–28 if you want bolder)
        "fontWeight": "bold",
        "anchor": "start",       # left-align (matches report style)
        "offset": 10
    })
)

out_html = OUTDIR / "index.html"
chart.save(out_html)
print("Wrote:", out_html)
