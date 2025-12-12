import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="U.S. Hard-to-Abate Exports", layout="wide")

st.title("U.S. Hard-to-Abate Exports — Partner Shares Over Time")

# ---- Load data ----
df = pd.read_csv("data/raw/us_trade_hard_to_abate_partner_raw.csv")

# ---- Normalize flow column from Comtrade ----
if "flow" not in df.columns:
    if "flowCode" in df.columns:
        df["flow"] = df["flowCode"].map({
            "X": "Export",
            "M": "Import"
        })
    else:
        df["flow"] = "Export"  # fallback for exports-only files


# Standardize column names (Comtrade sometimes uses primaryValue vs tradeValue)
value_col = None
for c in ["primaryValue", "tradeValue"]:
    if c in df.columns:
        value_col = c
        break
if value_col is None:
    st.error("Could not find a value column (expected 'primaryValue' or 'tradeValue').")
    st.stop()

# Clean
df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
df = df.dropna(subset=["period", value_col, "sector", "partnerDesc"])

# Drop any World aggregate rows if present
df = df[df["partnerDesc"].str.lower() != "world"].copy()

# ---- Settings ----
TOP_N = st.slider("Top partners to show per year (others grouped as 'Other')", 3, 25, 12)

sectors = sorted(df["sector"].unique())
sector = st.selectbox("Sector", sectors, index=0)

d = df[df["sector"] == sector].copy()

# ------------------------------
# Fixed partner color palette
# ------------------------------
PARTNER_COLORS = {
    "Canada": "#19515E",          # Primary green
    "Mexico": "#193A5B",          # Navy
    "China": "#8C2E1C",           # Red
    "Rep. of Korea": "#4C6F8C",   # Muted blue
    "India": "#7B9B97",           # Pale green
    "Malaysia": "#E6C27A",        # Sand
    "Other": "#A5A5A5",           # Gray
}

COLOR_DOMAIN = list(PARTNER_COLORS.keys())
COLOR_RANGE = list(PARTNER_COLORS.values())

# Aggregate to partner-year
g = (
    d.groupby(["period", "flow", "partnerDesc"], as_index=False)
     .agg(export_value_usd=(value_col, "sum"))
)

# Compute year totals and share
g["year_flow_total"] = g.groupby(["period", "flow"])["export_value_usd"].transform("sum")
g["share"] = g["export_value_usd"] / g["year_flow_total"]

# Rank partners within each year and group "Other"
g["rank_in_year"] = g.groupby(["period", "flow"])["export_value_usd"].rank(method="first", ascending=False)

g["partner_group"] = g.apply(
    lambda r: r["partnerDesc"] if r["rank_in_year"] <= TOP_N else "Other",
    axis=1
)

# Aggregate to partner_group-year
plot_df = (
    g.groupby(["period", "flow", "partner_group"], as_index=False)
     .agg(export_value_usd=("export_value_usd", "sum"))
)

# ---------------------------------------------------
# Fill missing (period, partner_group) with zeros
# ---------------------------------------------------
all_years = sorted(plot_df["period"].unique())
all_flows = sorted(plot_df["flow"].unique())
all_groups = list(PARTNER_COLORS.keys())

full_index = pd.MultiIndex.from_product(
    [all_years, all_flows, all_groups],
    names=["period", "flow", "partner_group"]
)

plot_df = (
    plot_df.set_index(["period", "flow", "partner_group"])
           .reindex(full_index, fill_value=0)
           .reset_index()
)

plot_df["year_flow_total"] = plot_df.groupby(["period","flow"])["export_value_usd"].transform("sum")
plot_df["share"] = (plot_df["export_value_usd"] / plot_df["year_flow_total"]).fillna(0)
plot_df["share_pct"] = (plot_df["share"] * 100).round(1)

# ---------------------------------------------------
# Stacking order: largest bottom, "Other" always top
# ---------------------------------------------------
plot_df["stack_order"] = (
    plot_df.groupby(["period","flow"])["export_value_usd"]
           .rank(method="first", ascending=False)
)
plot_df.loc[plot_df["partner_group"] == "Other", "stack_order"] = 1e9

# ---------------------------------------------------
# Hover formatting
# ---------------------------------------------------
plot_df["export_value_usd_fmt"] = plot_df["export_value_usd"].map(
    lambda x: f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.1f}M"
)


# ---- Chart ----
chart = (
    alt.Chart(plot_df)
    .mark_bar()
    .encode(
        x=alt.X("period:O", title="Year"),
        xOffset=alt.XOffset("flow:N", title=None),  # <-- makes two columns per year
        y=alt.Y("export_value_usd:Q", title="Trade value (USD)", stack="zero"),
        color=alt.Color(
            "partner_group:N",
            title="Partner",
            scale=alt.Scale(domain=COLOR_DOMAIN, range=COLOR_RANGE)
        ),
        order=alt.Order("stack_order:Q", sort="ascending"),
        tooltip=[
            alt.Tooltip("period:O", title="Year"),
            alt.Tooltip("flow:N", title="Flow"),
            alt.Tooltip("partner_group:N", title="Partner"),
            alt.Tooltip("export_value_usd:Q", title="Value (USD)", format=",.0f"),
            alt.Tooltip("share_pct:Q", title="Share (%)"),
        ],
    )
    .properties(height=520)
)

st.altair_chart(chart, use_container_width=True)

# Optional: show the underlying data table
with st.expander("Show chart data"):
    st.dataframe(plot_df.sort_values(["period", "export_value_usd"], ascending=[True, False]))
