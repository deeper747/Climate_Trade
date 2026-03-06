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
    font-family: 'Neuton', serif !important;
    font-size: 1.2 rem !important;
    font-weight: 400 !important;
    color: #194852 !important;
    margin: 0 0 0.5rem 0 !important;
    line-height: 1.1 !important;
    letter-spacing: -0.02em !important;
    display: block;
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
<p class="page-title">EU CBAM &amp; U.S. Hard-to-Abate Trade Monitor</p>
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
    "Russian Federation":   "#8d381c",  # same — UN Comtrade EU name variant
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
    "USA":                  "#D7f881",  # bright lime — top EU export destination
    "Switzerland":          "#e0c6fc",  # light lavender
    "Norway":               "#f4da91",  # light gold
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
def build_trade_charts(df: pd.DataFrame) -> alt.TopLevelMixin:
    """Two stacked-bar + hover share-trend blocks: Export on top, Import below.

    Named partners = union of top-5 per flow across ALL years (2019–2023).
    This captures trade champions that may have dropped out in later years (e.g. Russia).
    All remaining partners collapse into 'Other' (gray). Colors are stable across years.
    """
    # 1. Aggregate to (year, flow, partner)
    g = df.groupby(["period", "flow", "partnerDesc"], as_index=False).agg(
        trade_value_usd=("trade_value_usd", "sum")
    )

    # 2. Union of top-5 per flow across ALL years
    top5_any = (
        g.sort_values(["period", "flow", "trade_value_usd"], ascending=[True, True, False])
        .groupby(["period", "flow"])
        .head(5)[["flow", "partnerDesc"]]
        .drop_duplicates(["flow", "partnerDesc"])
        .assign(is_top5=True)
    )

    # 3. Assign partner_group: named if ever top-5, else "Other"
    g = g.merge(top5_any, on=["flow", "partnerDesc"], how="left")
    g["partner_group"] = g["partnerDesc"].where(g["is_top5"].eq(True), "Other")

    # 4. Re-aggregate with partner_group
    plot_df = g.groupby(["period", "flow", "partner_group"], as_index=False).agg(
        trade_value_usd=("trade_value_usd", "sum")
    )
    plot_df["yf_total"] = plot_df.groupby(["period", "flow"])["trade_value_usd"].transform("sum")
    plot_df["share_pct"] = (
        (plot_df["trade_value_usd"] / plot_df["yf_total"] * 100).fillna(0).round(1)
    )
    # Adaptive display unit: billions for large sectors, millions for cement-scale
    max_usd = plot_df["trade_value_usd"].max()
    if max_usd >= 2e9:
        plot_df["trade_display"] = plot_df["trade_value_usd"] / 1e9
        x_title = "Trade value (billion USD)"
        x_format = ",.0f" if max_usd >= 10e9 else ",.1f"
    else:
        plot_df["trade_display"] = plot_df["trade_value_usd"] / 1e6
        x_title = "Trade value (million USD)"
        x_format = ",.0f"
    plot_df["period_str"] = plot_df["period"].astype(str)
    plot_df["partner_color_key"] = plot_df["partner_group"].where(
        plot_df["partner_group"].isin(PARTNER_COLORS), "Other"
    )

    # 5. Stack order: rank by total across all years per flow, "Other" always last
    totals = (
        plot_df.groupby(["flow", "partner_group"])["trade_value_usd"]
        .sum()
        .reset_index()
    )
    totals["rank"] = totals.groupby("flow")["trade_value_usd"].rank(
        method="first", ascending=False
    )
    totals.loc[totals["partner_group"] == "Other", "rank"] = 1e9
    plot_df = plot_df.merge(
        totals[["flow", "partner_group", "rank"]], on=["flow", "partner_group"], how="left"
    )
    plot_df["stack_order"] = plot_df["rank"].fillna(500)

    YEAR_DOMAIN = sorted(plot_df["period_str"].unique().tolist())

    def make_flow_chart(flow_name: str) -> alt.VConcatChart:
        fd = plot_df[plot_df["flow"] == flow_name].copy()
        if fd.empty:
            return (
                alt.Chart(pd.DataFrame({"note": [f"No {flow_name} data"]}))
                .mark_text(fontSize=12, color="#78a0a3")
                .encode(text="note:N")
                .properties(height=180)
            )

        # Per-chart color scale (only partners present in this flow)
        key_order = (
            fd[fd["partner_color_key"] != "Other"]
            .drop_duplicates("partner_color_key")
            .sort_values("stack_order")["partner_color_key"]
            .tolist()
        )
        has_other = "Other" in fd["partner_color_key"].values
        c_domain = key_order + (["Other"] if has_other else [])
        c_range = [PARTNER_COLORS.get(k, "#d0dbdd") for k in c_domain]
        color_scale = alt.Scale(domain=c_domain, range=c_range)

        # Unique selection names per flow to prevent param collisions in vconcat
        slug = flow_name.lower()
        hover = alt.selection_point(
            name=f"hover_{slug}",
            fields=["partner_group"],
            on="mouseover",
            empty=False,       # Altair 5: False = show nothing when selection is empty
            clear="mouseout",
        )
        hover_mask = alt.selection_point(
            name=f"mask_{slug}",
            fields=["partner_group"],
            on="mouseover",
            empty=True,        # Altair 5: True = treat all as selected when nothing hovered
            clear="mouseout",
        )

        # ── Stacked bar chart
        bars = (
            alt.Chart(fd)
            .mark_bar()
            .encode(
                y=alt.Y(
                    "period_str:O",
                    sort=YEAR_DOMAIN,
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
                    "trade_display:Q",
                    title=x_title,
                    stack="zero",
                    axis=alt.Axis(
                        format=x_format,
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
                opacity=alt.condition(hover_mask, alt.value(1.0), alt.value(0.25)),
                tooltip=[
                    alt.Tooltip("period_str:O", title="Year"),
                    alt.Tooltip("partner_group:N", title="Partner"),
                    alt.Tooltip("trade_display:Q", title=x_title.replace("Trade value (", "Value ("), format=",.2f"),
                    alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
                ],
            )
            .add_params(hover, hover_mask)
            .properties(
                height=220,
                title=alt.TitleParams(
                    text=flow_name,
                    fontSize=13,
                    fontWeight=600,
                    color="#194852",
                    anchor="start",
                ),
            )
        )

        # ── Share trend line (only visible on hover; params live on bars above)
        share_line = (
            alt.Chart(fd)
            .transform_filter(hover)
            .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=55, strokeWidth=2))
            .properties(width="container")
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
                    title="Share of total (%)",
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
                tooltip=[
                    alt.Tooltip("period_str:O", title="Year"),
                    alt.Tooltip("partner_group:N", title="Partner"),
                    alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
                ],
            )
        )

        share_labels = (
            alt.Chart(fd)
            .transform_filter(hover)
            .mark_text(dy=-12, fontSize=10, fontWeight=600)
            .encode(
                x=alt.X("period_str:O", sort=YEAR_DOMAIN),
                y="share_pct:Q",
                text=alt.Text("share_pct:Q", format=".1f"),
                color=alt.Color("partner_color_key:N", scale=color_scale, legend=None),
            )
        )

        share_chart = (share_line + share_labels).properties(
            height=130,
            width="container",
            title=alt.TitleParams(
                text="Hover a bar segment \u2192 partner share over time",
                fontSize=10,
                color="#78a0a3",
                anchor="start",
                fontStyle="italic",
                dy=-4,
            ),
        )

        return alt.vconcat(bars, share_chart, spacing=16)

    export_block = make_flow_chart("Export")
    import_block = make_flow_chart("Import")

    return (
        alt.vconcat(export_block, import_block, spacing=36)
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
  Top partners are the union of top-5 by trade value in each year (2019–2023), capturing
  countries whose share shifted over time. All others are grouped as "Other."
  <strong>Hover a bar segment</strong> to trace that partner's share over time.
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

    eu_df = eu_raw[eu_raw["sector"] == eu_sector].copy()

    with chart_col:
        st.markdown(
            f'<p class="chart-header">{fmt_sector(eu_sector)}'
            " — EU Top-5 Export &amp; Import Partners, 2019–2023</p>",
            unsafe_allow_html=True,
        )
        st.altair_chart(build_trade_charts(eu_df), use_container_width=True)
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
  Top partners are the union of top-5 by trade value in each year (2019–2023), capturing
  countries whose share shifted over time. All others are grouped as "Other."
  <strong>Hover a bar segment</strong> to trace that partner's share over time.
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

    us_df = us_raw[us_raw["sector"] == us_sector].copy()

    with chart_col:
        st.markdown(
            f'<p class="chart-header">{fmt_sector(us_sector)}'
            " — U.S. Top-5 Export &amp; Import Partners, 2019–2023</p>",
            unsafe_allow_html=True,
        )
        st.altair_chart(build_trade_charts(us_df), use_container_width=True)
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
