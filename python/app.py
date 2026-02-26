import streamlit as st
import pandas as pd
import altair as alt

# ─── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CBAM Trade Impact Monitor",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Neuton:wght@400;700;800&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Hanken Grotesk', sans-serif; }

.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }

/* ── Page header */
.page-title {
    font-family: 'Neuton', serif;
    font-size: 2.6rem;
    font-weight: 800;
    color: #194852;
    margin: 0 0 0.5rem 0;
    line-height: 1.15;
    letter-spacing: -0.01em;
}
.page-subtitle {
    font-size: 0.9rem;
    color: #78a0a3;
    margin: 0 0 1rem 0;
    line-height: 1.65;
    max-width: 860px;
}
.related-links {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin: 0 0 1.4rem 0;
}
.related-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #78a0a3;
    white-space: nowrap;
}
.related-links a {
    font-size: 0.82rem;
    color: #348397;
    text-decoration: none;
    border-bottom: 1px solid #7dceda;
    padding-bottom: 1px;
}
.related-links a:hover {
    color: #194852;
    border-color: #194852;
}
.divider { border: none; border-top: 1px solid #d0dbdd; margin: 0 0 1.5rem 0; }

/* ── Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1.5px solid #d0dbdd;
    margin-bottom: 1.75rem;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.875rem;
    font-weight: 500;
    color: #78a0a3;
    padding: 0.55rem 1.35rem;
    border-bottom: 2px solid transparent;
    margin-bottom: -1.5px;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #194852 !important;
    border-bottom-color: #348397 !important;
}

/* ── Filter labels */
.filter-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #78a0a3;
    margin-bottom: 0.3rem;
}
.filter-spacer { margin-top: 1.1rem; }

/* ── Callout */
.callout {
    background: #edf1f2;
    border-left: 3px solid #348397;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1.1rem;
    font-size: 0.83rem;
    color: #0c2a30;
    margin-bottom: 1.4rem;
    line-height: 1.6;
}

/* ── Chart section label */
.chart-header {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #348397;
    margin-bottom: 0.5rem;
}

/* ── Source note */
.source-note {
    font-size: 0.72rem;
    color: #78a0a3;
    margin-top: 0.6rem;
    padding-top: 0.6rem;
    border-top: 1px solid #d0dbdd;
}

/* ── Slider */
div[data-baseweb="slider"] div[role="slider"] + div {
    background-color: #348397 !important;
}
div[data-baseweb="slider"] div[role="slider"] + div + div {
    background-color: rgba(52,131,151,0.18) !important;
}
div[data-baseweb="slider"] div[role="slider"] {
    background-color: #194852 !important;
    border-color: #194852 !important;
    box-shadow: none !important;
}

/* ── Selectbox */
div[data-baseweb="select"] > div {
    border-radius: 7px !important;
    border-color: #d0dbdd !important;
}
div[data-baseweb="select"] > div:focus-within {
    border-color: #348397 !important;
    box-shadow: 0 0 0 1.5px rgba(52,131,151,0.3) !important;
}

/* ── Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# ─── Page header ──────────────────────────────────────────────────────────────
st.markdown(
    """
<p class="page-title">EU Carbon Border Adjustment Mechanism — Trade Impact Monitor</p>
<p class="page-subtitle">
  Tracking bilateral trade in hard-to-abate sectors (iron &amp; steel, aluminum, cement)
  to identify which countries face the greatest exposure to the EU's carbon tariff.
  Data: UN Comtrade, 2019–2023.
</p>
<div class="related-links">
  <span class="related-label">Related reading</span>
  <a href="https://www.niskanencenter.org/reforming-carbon-accounting-for-a-new-era-of-competition/" target="_blank" rel="noopener">Reforming carbon accounting for a new era of competition</a>
  <a href="https://www.niskanencenter.org/where-u-s-carbon-policy-is-being-decided-in-2026/" target="_blank" rel="noopener">Where U.S. carbon policy is being decided in 2026</a>
  <a href="https://www.niskanencenter.org/policy/climate/" target="_blank" rel="noopener">Niskanen climate &amp; energy policy</a>
</div>
<hr class="divider">
""",
    unsafe_allow_html=True,
)

# ─── Color palette (Niskanen Center rebrand) ─────────────────────────────────
# Primary teal:  #0c2a30  #194852  #348397  #7dceda  #78a0a3  #d0dbdd
# Yellow:        #52482a  #bca45e  #f4da91
# Orange:        #411b08  #8d381c  #da5831  #f17d3a
# Green:         #2c3811  #709628  #b5d955  #D7f881
# Purple:        #503961  #8655b2  #e0c6fc
PARTNER_COLORS = {
    # ── EU CBAM top partners (orange/red = high exposure)
    "China":                "#da5831",  # orange-red  — biggest CBAM concern
    "Russia":               "#8d381c",  # dark rust
    "Türkiye":              "#bca45e",  # gold
    "Turkey":               "#bca45e",
    "India":                "#8655b2",  # medium purple
    "United Kingdom":       "#348397",  # medium teal
    "Rep. of Korea":        "#194852",  # brand dark teal
    "Korea, Rep.":          "#194852",
    "Ukraine":              "#709628",  # olive green
    "Viet Nam":             "#2c3811",  # dark forest green
    "Vietnam":              "#2c3811",
    "Japan":                "#f17d3a",  # bright orange
    "Indonesia":            "#503961",  # dark purple
    "Egypt":                "#52482a",  # dark olive-khaki
    "United Arab Emirates": "#78a0a3",  # muted teal-gray
    # ── U.S. top partners
    "Canada":               "#0c2a30",  # very dark navy-teal
    "Mexico":               "#7dceda",  # light teal
    "Germany":              "#b5d955",  # lime green
    "Brazil":               "#411b08",  # very dark brown
    "Malaysia":             "#f4da91",  # light gold
    "Taiwan":               "#503961",  # dark purple
    "Greece":               "#bca45e",  # gold
    "Bahamas":              "#52482a",  # dark olive-khaki
    "Panama":               "#709628",  # olive green
    "Br. Virgin Islands":   "#8d381c",  # dark rust
    "Other Asia, nes":      "#78a0a3",  # muted teal-gray
    # ── Catch-all
    "Other":                "#d0dbdd",  # brand neutral gray
}

COLOR_DOMAIN = list(PARTNER_COLORS.keys())
COLOR_RANGE = list(PARTNER_COLORS.values())

# ─── Sector labels ────────────────────────────────────────────────────────────
SECTOR_LABELS = {
    "iron_steel":    "Iron & Steel",
    "iron_steel_72": "Iron & Steel — Primary (HS 72)",
    "iron_steel_73": "Iron & Steel — Articles (HS 73)",
    "aluminum":      "Aluminum",
    "aluminum_76":   "Aluminum (HS 76)",
    "aluminium":     "Aluminum",
    "cement":        "Cement",
    "cement_2523":   "Cement (HS 2523)",
}


def fmt_sector(s: str) -> str:
    return SECTOR_LABELS.get(s, s.replace("_", " ").title())


# ─── Data loaders ─────────────────────────────────────────────────────────────
@st.cache_data
def load_eu_data() -> pd.DataFrame:
    df = pd.read_csv("data/processed/eu_trade_hard_to_abate_partner.csv")
    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df["trade_value_usd"] = pd.to_numeric(df["trade_value_usd"], errors="coerce")
    df = df.dropna(subset=["period", "trade_value_usd", "sector", "partnerDesc", "flow"])
    df = df[df["partnerDesc"].str.lower() != "world"]
    # Merge HS 72 and HS 73 into a single iron_steel category
    df["sector"] = df["sector"].replace(
        {"iron_steel_72": "iron_steel", "iron_steel_73": "iron_steel"}
    )
    return (
        df.groupby(["period", "flow", "sector", "partnerDesc"], as_index=False)[
            "trade_value_usd"
        ].sum()
    )


@st.cache_data
def load_us_data() -> pd.DataFrame:
    df = pd.read_csv("data/raw/us_trade_hard_to_abate_partner_raw.csv")
    if "flow" not in df.columns:
        if "flowCode" in df.columns:
            df["flow"] = df["flowCode"].map({"X": "Export", "M": "Import"})
        else:
            df["flow"] = "Export"
    val = next((c for c in ["primaryValue", "tradeValue"] if c in df.columns), None)
    if val is None:
        st.error("No value column found in U.S. data.")
        st.stop()
    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df[val] = pd.to_numeric(df[val], errors="coerce")
    df = df.dropna(subset=["period", val, "sector", "partnerDesc", "flow"])
    df = df[df["partnerDesc"].str.lower() != "world"]
    return df.rename(columns={val: "trade_value_usd"})


# ─── Chart builder ────────────────────────────────────────────────────────────
def build_trade_chart(df: pd.DataFrame, top_n: int) -> alt.TopLevelMixin:
    # Aggregate to (year, flow, partner)
    g = df.groupby(["period", "flow", "partnerDesc"], as_index=False).agg(
        trade_value_usd=("trade_value_usd", "sum")
    )

    # Rank within (year, flow) and group low-ranked partners as "Other"
    g["rank"] = g.groupby(["period", "flow"])["trade_value_usd"].rank(
        method="first", ascending=False
    )
    g["partner_group"] = g.apply(
        lambda r: r["partnerDesc"] if r["rank"] <= top_n else "Other", axis=1
    )
    plot_df = g.groupby(["period", "flow", "partner_group"], as_index=False).agg(
        trade_value_usd=("trade_value_usd", "sum")
    )

    # Fill every (year × flow × partner) combination so stacks are complete
    all_years = sorted(plot_df["period"].unique())
    all_flows = sorted(plot_df["flow"].unique())
    all_groups = sorted(plot_df["partner_group"].unique())
    if "Other" in all_groups:
        all_groups = [p for p in all_groups if p != "Other"] + ["Other"]

    idx = pd.MultiIndex.from_product(
        [all_years, all_flows, all_groups],
        names=["period", "flow", "partner_group"],
    )
    plot_df = (
        plot_df.set_index(["period", "flow", "partner_group"])
        .reindex(idx, fill_value=0)
        .reset_index()
    )

    # Derived columns
    plot_df["year_flow_total"] = plot_df.groupby(["period", "flow"])[
        "trade_value_usd"
    ].transform("sum")
    plot_df["share_pct"] = (
        (plot_df["trade_value_usd"] / plot_df["year_flow_total"] * 100)
        .fillna(0)
        .round(1)
    )
    plot_df["value_bil"] = plot_df["trade_value_usd"] / 1e9
    plot_df["period_str"] = plot_df["period"].astype(str)

    # Map to a known color key; unknowns collapse to gray "Other"
    plot_df["partner_color_key"] = plot_df["partner_group"].where(
        plot_df["partner_group"].isin(PARTNER_COLORS), "Other"
    )

    # Stack order: rank by total across ALL years/flows so each partner
    # stays in the same position every bar — largest at bottom, Other on top
    partner_totals = plot_df.groupby("partner_group")["trade_value_usd"].sum()
    rank_map = partner_totals.rank(method="first", ascending=False).to_dict()
    rank_map["Other"] = 1e9
    plot_df["stack_order"] = plot_df["partner_group"].map(rank_map).fillna(500)

    # Ordered Y-axis categories: "2019 Export", "2019 Import", "2020 Export", …
    y_order = []
    for yr in sorted(plot_df["period"].dropna().unique()):
        y_order += [f"{yr} Export", f"{yr} Import"]
    plot_df["year_flow"] = pd.Categorical(
        plot_df["period"].astype(str) + " " + plot_df["flow"],
        categories=y_order,
        ordered=True,
    )

    YEAR_DOMAIN = sorted(plot_df["period_str"].unique().tolist())

    # ── Selections
    hover_mask = alt.selection_point(
        fields=["partner_group", "flow"],
        on="mouseover",
        empty="all",
        clear="mouseout",
    )
    hover_active = alt.selection_point(
        fields=["partner_group", "flow"],
        on="mouseover",
        empty="none",
        clear="mouseout",
    )

    color_scale = alt.Scale(domain=COLOR_DOMAIN, range=COLOR_RANGE)

    # ── Stacked bar chart
    bars = (
        alt.Chart(plot_df)
        .mark_bar()
        .encode(
            y=alt.Y(
                "year_flow:O",
                sort=y_order,
                title=None,
                axis=alt.Axis(
                    labelFontSize=11,
                    labelColor="#78a0a3",
                    ticks=False,
                    domain=False,
                    grid=False,
                    labelPadding=8,
                ),
            ),
            x=alt.X(
                "value_bil:Q",
                title="Trade value (billion USD)",
                stack="zero",
                axis=alt.Axis(
                    format=",.0f",
                    labelFontSize=10,
                    titleFontSize=11,
                    titleColor="#78a0a3",
                    titlePadding=10,
                    grid=True,
                    gridColor="#edf1f2",
                    gridDash=[3, 3],
                    domain=False,
                    ticks=False,
                    labelPadding=4,
                ),
            ),
            color=alt.Color(
                "partner_color_key:N",
                title="Partner",
                scale=color_scale,
                legend=alt.Legend(
                    orient="right",
                    titleFontSize=11,
                    titleColor="#194852",
                    labelFontSize=11,
                    labelColor="#194852",
                    symbolType="square",
                    symbolSize=130,
                    rowPadding=5,
                ),
            ),
            order=alt.Order("stack_order:Q", sort="ascending"),
            opacity=alt.condition(hover_mask, alt.value(1.0), alt.value(0.1)),
            tooltip=[
                alt.Tooltip("period:O", title="Year"),
                alt.Tooltip("flow:N", title="Flow"),
                alt.Tooltip("partner_group:N", title="Partner"),
                alt.Tooltip("value_bil:Q", title="Value ($B)", format=",.2f"),
                alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
            ],
        )
        .add_params(hover_mask, hover_active)
        .properties(height=480)
    )

    # ── Share trend line (appears only on hover)
    share_line = (
        alt.Chart(plot_df)
        .transform_filter(hover_active)
        .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=60, strokeWidth=2))
        .encode(
            x=alt.X(
                "period_str:O",
                sort=YEAR_DOMAIN,
                title="Year",
                axis=alt.Axis(
                    labelFontSize=10,
                    titleFontSize=11,
                    titleColor="#78a0a3",
                    titlePadding=8,
                    ticks=False,
                    domain=False,
                    grid=False,
                    labelPadding=4,
                ),
            ),
            y=alt.Y(
                "share_pct:Q",
                title="Share (%)",
                scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(
                    format=".0f",
                    labelFontSize=10,
                    titleFontSize=11,
                    titleColor="#78a0a3",
                    titlePadding=8,
                    grid=True,
                    gridColor="#edf1f2",
                    gridDash=[3, 3],
                    domain=False,
                    ticks=False,
                    tickCount=4,
                    labelPadding=4,
                ),
            ),
            color=alt.Color("partner_color_key:N", scale=color_scale, legend=None),
            opacity=alt.condition(hover_active, alt.value(1.0), alt.value(0.0)),
            tooltip=[
                alt.Tooltip("period:O", title="Year"),
                alt.Tooltip("flow:N", title="Flow"),
                alt.Tooltip("partner_group:N", title="Partner"),
                alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
            ],
        )
        # No add_params here — params live only on bars to avoid conflicting
        # Vega-Lite param scopes that break transform_filter
    )

    share_labels = (
        alt.Chart(plot_df)
        .transform_filter(hover_active)
        .mark_text(dy=-13, fontSize=11, fontWeight=600)
        .encode(
            x=alt.X("period_str:O", sort=YEAR_DOMAIN),
            y="share_pct:Q",
            text=alt.Text("share_pct:Q", format=".1f"),
            color=alt.Color("partner_color_key:N", scale=color_scale, legend=None),
            opacity=alt.condition(hover_active, alt.value(1.0), alt.value(0.0)),
        )
    )

    share_chart = (share_line + share_labels).properties(
        height=155,
        title=alt.TitleParams(
            text="Hover a bar segment to trace a partner's share over time \u2192",
            fontSize=11,
            color="#78a0a3",
            anchor="start",
            fontStyle="italic",
            dy=-2,
        ),
    )

    return (
        alt.vconcat(bars, share_chart, spacing=30)
        .configure_view(strokeWidth=0)
        .configure(font="Hanken Grotesk")
        .configure_axis(labelFont="Hanken Grotesk", titleFont="Hanken Grotesk")
        .configure_legend(labelFont="Hanken Grotesk", titleFont="Hanken Grotesk")
        .configure_title(font="Hanken Grotesk")
    )


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_eu, tab_us = st.tabs(["EU Trade — CBAM Exposure", "U.S. Trade"])

# ══════════════════════════════════════════════════════════════════════════════
# EU TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_eu:
    eu_raw = load_eu_data()
    eu_sectors = sorted(eu_raw["sector"].unique())

    st.markdown(
        """
<div class="callout">
  The EU's <strong>Carbon Border Adjustment Mechanism (CBAM)</strong>, fully operative
  from 2026, levies a carbon price on imports of iron &amp; steel, aluminum, and
  cement—based on the embedded carbon intensity of production. Countries with large
  export shares to the EU in these sectors face the highest compliance burden.
  <strong>Hover over any bar segment</strong> to trace that trading partner's share
  over time.
</div>""",
        unsafe_allow_html=True,
    )

    f_col, chart_col = st.columns([1, 5], gap="large")

    with f_col:
        st.markdown('<p class="filter-label">Sector</p>', unsafe_allow_html=True)
        eu_sector = st.selectbox(
            "Sector",
            eu_sectors,
            format_func=fmt_sector,
            label_visibility="collapsed",
            key="eu_sector",
        )
        st.markdown(
            '<p class="filter-label filter-spacer">Top partners shown</p>',
            unsafe_allow_html=True,
        )
        eu_top_n = st.slider(
            "Top N",
            1,
            8,
            5,
            label_visibility="collapsed",
            key="eu_topn",
            help="Show this many partners individually; all others are grouped as 'Other'.",
        )

    eu_df = eu_raw[eu_raw["sector"] == eu_sector].copy()

    with chart_col:
        st.markdown(
            f'<p class="chart-header">{fmt_sector(eu_sector)}'
            " — EU Import &amp; Export Partners, 2019–2023</p>",
            unsafe_allow_html=True,
        )
        st.altair_chart(build_trade_chart(eu_df, eu_top_n), use_container_width=True)
        st.markdown(
            '<p class="source-note">Source: UN Comtrade (comtradeapi.un.org). '
            "Prepared by Jia-Shen Tsai, Niskanen Center. Values in current USD.</p>",
            unsafe_allow_html=True,
        )

    with st.expander("Show underlying data"):
        st.dataframe(
            eu_df.sort_values(["period", "trade_value_usd"], ascending=[True, False]),
            use_container_width=True,
            hide_index=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# U.S. TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_us:
    us_raw = load_us_data()
    us_sectors = sorted(us_raw["sector"].unique())

    st.markdown(
        """
<div class="callout">
  U.S. bilateral trade in the same hard-to-abate sectors targeted by CBAM. While the
  U.S. operates outside of CBAM, this view provides a comparison of trade
  patterns—and may inform U.S. trade and climate policy discussions.
  <strong>Hover over any bar segment</strong> to trace a partner's share over time.
</div>""",
        unsafe_allow_html=True,
    )

    f_col, chart_col = st.columns([1, 5], gap="large")

    with f_col:
        st.markdown('<p class="filter-label">Sector</p>', unsafe_allow_html=True)
        us_sector = st.selectbox(
            "Sector",
            us_sectors,
            format_func=fmt_sector,
            label_visibility="collapsed",
            key="us_sector",
        )
        st.markdown(
            '<p class="filter-label filter-spacer">Top partners shown</p>',
            unsafe_allow_html=True,
        )
        us_top_n = st.slider(
            "Top N",
            1,
            5,
            3,
            label_visibility="collapsed",
            key="us_topn",
            help="Show this many partners individually; all others are grouped as 'Other'.",
        )

    us_df = us_raw[us_raw["sector"] == us_sector].copy()

    with chart_col:
        st.markdown(
            f'<p class="chart-header">{fmt_sector(us_sector)}'
            " — U.S. Import &amp; Export Partners, 2019–2023</p>",
            unsafe_allow_html=True,
        )
        st.altair_chart(build_trade_chart(us_df, us_top_n), use_container_width=True)
        st.markdown(
            '<p class="source-note">Source: UN Comtrade (comtradeapi.un.org). '
            "Prepared by Jia-Shen Tsai, Niskanen Center. Values in current USD.</p>",
            unsafe_allow_html=True,
        )

    with st.expander("Show underlying data"):
        st.dataframe(
            us_df.sort_values(["period", "trade_value_usd"], ascending=[True, False]),
            use_container_width=True,
            hide_index=True,
        )
