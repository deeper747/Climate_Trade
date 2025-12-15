import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="U.S. Hard-to-Abate Exports and Imports", layout="wide")
st.markdown(
    """
    <style>
    :root { --niskanen-green: #19515e; }

    /* ---- Slider (BaseWeb) ---- */
    /* active (filled) track */
    div[data-baseweb="slider"] div[role="slider"] + div {
        background-color: var(--niskanen-green) !important;
    }

    /* inactive track */
    div[data-baseweb="slider"] div[role="slider"] + div + div {
        background-color: rgba(25, 81, 94, 0.25) !important;
    }

    /* thumb */
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: var(--niskanen-green) !important;
        border-color: var(--niskanen-green) !important;
        box-shadow: none !important;
    }

    /* value label above the thumb */
    div[data-baseweb="slider"] div[data-testid="stTickBar"] ~ div {
        color: var(--niskanen-green) !important;
    }

    /* ---- Selectbox border (BaseWeb) ---- */
    div[data-baseweb="select"] > div {
        border-color: var(--niskanen-green) !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--niskanen-green) !important;
        box-shadow: 0 0 0 1px var(--niskanen-green) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.title("U.S. Hard-to-Abate Exports and Imports — Partner Shares Over Time")

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
left, right = st.columns([1, 4], gap="large")

with left:
    st.subheader("Filters")
    TOP_N = st.slider("Top partners to show per year (others grouped as 'Other')", 1, 5, 3)
    sectors = sorted(df["sector"].unique())
    sector = st.selectbox("Sector", sectors, index=0)

d = df[df["sector"] == sector].copy()


# ------------------------------
# Fixed partner color palette
# ------------------------------
PARTNER_COLORS = {
    "Canada": "#19515E",     
    "Mexico": "#193A5B",    
    "China": "#8C2E1C",         
    "Rep. of Korea": "#4C6F8C",  
    "India": "#7B9B97",          
    "Malaysia": "#E6C27A",    
    "Germany": "#D97C4C",       
    "United Arab Emirates": "#A17BB0",
    "Türkiye": "#B89C2C", 
    "Greece": "#649CF6",
    "Viet Nam": "#4C6F8C",        
    "Bahamas": "#2C5C2F",         
    "Panama": "#681E70",        
    "Br. Virgin Islands": "#938261",       
    "Other Asia, nes": "#6F8597",        
    "Brazil": "#3D613D",         
    "Other": "#A5A5A5",           
}

COLOR_DOMAIN = list(PARTNER_COLORS.keys())
COLOR_RANGE = list(PARTNER_COLORS.values())

# Aggregate to partner-year
g = (
    d.groupby(["period", "flow", "partnerDesc"], as_index=False)
     .agg(export_value_usd=(value_col, "sum"))
)

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
all_groups = sorted(plot_df["partner_group"].unique())
if "Other" in all_groups:
    all_groups = [g for g in all_groups if g != "Other"] + ["Other"]


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
plot_df["share_pct_label"] = plot_df["share_pct"].map(lambda x: f"{x:.1f}%")
plot_df["period_str"] = plot_df["period"].astype(str)
YEAR_DOMAIN = sorted(plot_df["period_str"].unique().tolist())

# ------------------------------
# Color key for stable palette
# ------------------------------
known = set(PARTNER_COLORS.keys())

plot_df["partner_color_key"] = plot_df["partner_group"].where(
    plot_df["partner_group"].isin(known),
    "Other"   # collapse unknown partners into gray
)

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

# --- Axis label helper: one bar per (year, flow) ---
plot_df["year_flow"] = plot_df["period"].astype(str) + " " + plot_df["flow"]

# Optional: force Export then Import ordering within each year
ordered = []
for y in sorted(plot_df["period"].dropna().unique()):
    ordered += [f"{y} Export", f"{y} Import"]
plot_df["year_flow"] = pd.Categorical(plot_df["year_flow"], categories=ordered, ordered=True)


# ---- Chart ----
plot_df["value_bil"] = plot_df["export_value_usd"] / 1e9

hover_mask = alt.selection_point(
    fields=["partner_group", "flow"],
    on="mouseover",
    empty="all",
    clear="mouseout"
)

hover_active = alt.selection_point(
    fields=["partner_group", "flow"],
    on="mouseover",
    empty="none",
    clear="mouseout"
)

base = alt.Chart(plot_df).encode(
    y=alt.Y(
        "year_flow:O",
        title="Year / Flow",
        sort=ordered,   # keep your custom order
    ),
)


bars = (
    base.mark_bar()
    .encode(
        x=alt.X(
            "value_bil:Q",
            title="Trade value ($ billion USD)",
            stack="zero",
            axis=alt.Axis(format=",.1f"),
        ),
        color=alt.Color(
            "partner_color_key:N",
            title="Partner",
            scale=alt.Scale(
                domain=list(PARTNER_COLORS.keys()),
                range=list(PARTNER_COLORS.values()),
            ),
        ),
        order=alt.Order("stack_order:Q", sort="ascending"),
        opacity=alt.condition(hover_mask, alt.value(1.0), alt.value(0.15)),
        tooltip=[
            alt.Tooltip("period:O", title="Year"),
            alt.Tooltip("flow:N", title="Flow"),
            alt.Tooltip("partner_group:N", title="Partner"),
            alt.Tooltip("value_bil:Q", title="Value ($B)", format=",.2f"),
            alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
        ],
    )
    .add_params(hover_mask, hover_active)
    .properties(height=620)
)


share_line = (
    alt.Chart(plot_df)
    .transform_filter(hover_active)     # only show selected partner+flow on hover
    .mark_line(point=True)
    .encode(
        x=alt.X(
            "period_str:O",
            title="Year",
            sort=YEAR_DOMAIN,
            scale=alt.Scale(domain=YEAR_DOMAIN),
        ),
        y=alt.Y(
            "share_pct:Q",
            title="Share of year total (%)",
            scale=alt.Scale(domain=[0, 100]),
            axis=alt.Axis(format=".1f"),
        ),
        opacity=alt.condition(hover_active, alt.value(1.0), alt.value(0.0)),
        tooltip=[
            alt.Tooltip("period:O", title="Year"),
            alt.Tooltip("flow:N", title="Flow"),
            alt.Tooltip("partner_group:N", title="Partner"),
            alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
        ],
    )
    .add_params(hover_mask, hover_active)
    .properties(height=160)
)

plot_df["share_pct_label"] = plot_df["share_pct"].map(lambda x: f"{x:.1f}%")

share_labels = (
    alt.Chart(plot_df)
    .transform_filter(hover_active)
    .mark_text(dy=-15, fontSize=15)
    .encode(
        x=alt.X("period_str:O", sort=YEAR_DOMAIN, scale=alt.Scale(domain=YEAR_DOMAIN)),
        y="share_pct:Q",
        text="share_pct_label:N",
        opacity=alt.condition(hover_active, alt.value(1.0), alt.value(0.0)),
    )
)

share_chart = share_line + share_labels

chart = alt.vconcat(bars, share_chart)
with right:
    st.altair_chart(chart, use_container_width=True)



with st.expander("Show chart data"):
    st.dataframe(plot_df.sort_values(["period", "export_value_usd"], ascending=[True, False]))
