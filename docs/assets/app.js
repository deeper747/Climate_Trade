const PARTNER_COLORS = {
  China: "#da5831",
  Russia: "#503961",
  "Russian Federation": "#503961",
  "Türkiye": "#bca45e",
  Turkey: "#bca45e",
  India: "#b5d955",
  "United Kingdom": "#f17d3a",
  "Rep. of Korea": "#194852",
  "Korea, Rep.": "#194852",
  Ukraine: "#709628",
  "Viet Nam": "#2c3811",
  Vietnam: "#2c3811",
  Japan: "#348397",
  Indonesia: "#8d381c",
  Egypt: "#52482a",
  "United Arab Emirates": "#78a0a3",
  USA: "#D7f881",
  Switzerland: "#e0c6fc",
  Norway: "#f4da91",
  Canada: "#0c2a30",
  Mexico: "#7dceda",
  Germany: "#b5d955",
  Brazil: "#411b08",
  Malaysia: "#f4da91",
  Taiwan: "#503961",
  Greece: "#bca45e",
  Bahamas: "#52482a",
  Panama: "#709628",
  "Br. Virgin Islands": "#8d381c",
  "Other Asia, nes": "#78a0a3",
  Other: "#d0dbdd",
};

const SECTOR_LABELS = {
  iron_steel: "Iron & Steel",
  iron_steel_72: "Iron & Steel — Primary (CBAM CN codes)",
  iron_steel_73: "Iron & Steel — Articles (CBAM CN codes)",
  aluminum: "Aluminum",
  aluminum_76: "Aluminum (CBAM CN codes)",
  aluminium: "Aluminum",
  cement: "Cement",
  cement_2523: "Cement & Precursors (CBAM CN codes)",
  hydrogen_2804: "Hydrogen",
  fertilizers: "Fertilizers",
};

const DASHBOARDS = {
  eu: {
    dataUrl: "./data/eu_trade.json",
    selectId: "eu-sector",
    chartId: "eu-chart",
    tableId: "eu-table",
    headerId: "eu-chart-header",
    titlePrefix: "EU Top-5 Export & Import Partners",
    flowOrder: ["Import", "Export"],
  },
  us: {
    dataUrl: "./data/us_trade.json",
    selectId: "us-sector",
    chartId: "us-chart",
    tableId: "us-table",
    headerId: "us-chart-header",
    titlePrefix: "U.S. Top-5 Export & Import Partners",
    flowOrder: ["Export", "Import"],
  },
};

const state = {
  metricMode: "value",  // "value" | "quantity"
  eu: { rows: [], selectedSector: null },
  us: { rows: [], selectedSector: null },
};

function fmtSector(value) {
  return SECTOR_LABELS[value] || value.replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function formatTradeValue(value) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatQuantity(valueMt) {
  if (valueMt == null || isNaN(valueMt)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
  }).format(valueMt / 1000);
}

function uniq(values) {
  return [...new Set(values)];
}

function getChartWidth(chartEl) {
  const measured = chartEl?.clientWidth || chartEl?.parentElement?.clientWidth || 0;
  return Math.max(Math.floor(measured) - 12, 320);
}

// Aggregate rows by (period, flow, partner), summing the chosen metric field.
// Returns objects with a normalised `metric_value` key.
function aggregateRows(rows, metricField) {
  const bucket = new Map();
  rows.forEach((row) => {
    const key = [row.period, row.flow, row.partnerDesc].join("||");
    bucket.set(key, (bucket.get(key) || 0) + (row[metricField] || 0));
  });
  return [...bucket.entries()].map(([key, metricValue]) => {
    const [period, flow, partnerDesc] = key.split("||");
    return { period: Number(period), flow, partnerDesc, metric_value: metricValue };
  });
}

function buildTradeChartData(rows, metricMode) {
  const metricField = metricMode === "quantity" ? "quantity_mt" : "trade_value_usd";
  const grouped = aggregateRows(rows, metricField);

  // Top-5 partners per flow (by total metric across all years)
  const topPartnersByFlow = new Set();
  ["Export", "Import"].forEach((flow) => {
    const totals = new Map();
    grouped
      .filter((row) => row.flow === flow)
      .forEach((row) => {
        totals.set(row.partnerDesc, (totals.get(row.partnerDesc) || 0) + row.metric_value);
      });
    [...totals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([partnerDesc]) => {
        topPartnersByFlow.add(`${flow}||${partnerDesc}`);
      });
  });

  // Collapse non-top-5 into "Other"
  const collapsedMap = new Map();
  grouped.forEach((row) => {
    const partnerGroup = topPartnersByFlow.has(`${row.flow}||${row.partnerDesc}`)
      ? row.partnerDesc
      : "Other";
    const key = [row.period, row.flow, partnerGroup].join("||");
    collapsedMap.set(key, (collapsedMap.get(key) || 0) + row.metric_value);
  });

  const plotRows = [...collapsedMap.entries()].map(([key, metricValue]) => {
    const [period, flow, partnerGroup] = key.split("||");
    return {
      period: Number(period),
      period_str: String(period),
      flow,
      partner_group: partnerGroup,
      metric_value: metricValue,
    };
  });

  // Share of total per year × flow
  const totalsByYearFlow = new Map();
  plotRows.forEach((row) => {
    const key = `${row.period}||${row.flow}`;
    totalsByYearFlow.set(key, (totalsByYearFlow.get(key) || 0) + row.metric_value);
  });
  plotRows.forEach((row) => {
    const total = totalsByYearFlow.get(`${row.period}||${row.flow}`) || 0;
    row.share_pct = total ? Number(((row.metric_value / total) * 100).toFixed(1)) : 0;
  });

  // Scale metric_value → metric_display for the x-axis
  let xTitle, xFormat;
  if (metricMode === "quantity") {
    const maxMt = Math.max(...plotRows.map((r) => r.metric_value), 0);
    plotRows.forEach((r) => { r.metric_display = r.metric_value / 1000; });
    xTitle = "Volume (thousand t)";
    xFormat = maxMt / 1000 >= 1000 ? ",.0f" : ",.1f";
  } else {
    const maxUsd = Math.max(...plotRows.map((r) => r.metric_value), 0);
    const useBillions = maxUsd >= 2e9;
    plotRows.forEach((r) => {
      r.metric_display = useBillions ? r.metric_value / 1e9 : r.metric_value / 1e6;
    });
    xTitle = useBillions ? "Trade value (billion USD)" : "Trade value (million USD)";
    xFormat = useBillions && maxUsd >= 10e9 ? ",.0f" : ",.1f";
  }

  // Assign colors
  plotRows.forEach((row) => {
    row.partner_color_key = PARTNER_COLORS[row.partner_group] ? row.partner_group : "Other";
    row.partner_color = PARTNER_COLORS[row.partner_color_key] || PARTNER_COLORS.Other;
  });

  // Stack order (largest partner first, Other last)
  const totalsByFlowPartner = new Map();
  plotRows.forEach((row) => {
    const key = `${row.flow}||${row.partner_group}`;
    totalsByFlowPartner.set(key, (totalsByFlowPartner.get(key) || 0) + row.metric_value);
  });
  ["Export", "Import"].forEach((flow) => {
    const ordered = [...totalsByFlowPartner.entries()]
      .filter(([key]) => key.startsWith(`${flow}||`))
      .map(([key, total]) => ({ partner_group: key.split("||")[1], total }))
      .sort((a, b) => {
        if (a.partner_group === "Other") return 1;
        if (b.partner_group === "Other") return -1;
        return b.total - a.total;
      });
    ordered.forEach((entry, index) => {
      plotRows
        .filter((row) => row.flow === flow && row.partner_group === entry.partner_group)
        .forEach((row) => { row.stack_order = index + 1; });
    });
  });

  const yearDomain = uniq(plotRows.map((row) => row.period_str)).sort();
  return { plotRows, yearDomain, xTitle, xFormat, metricMode };
}

function buildFlowSpec(flowRows, flowName, yearDomain, xTitle, xFormat, chartWidth, metricMode) {
  if (!flowRows.length) {
    return {
      data: { values: [{ note: `No ${flowName} data` }] },
      mark: { type: "text", color: "#78a0a3", fontSize: 12 },
      encoding: { text: { field: "note" } },
      width: chartWidth,
      height: 180,
    };
  }

  const colorDomain = flowRows
    .filter((row) => row.partner_color_key !== "Other")
    .sort((a, b) => a.stack_order - b.stack_order)
    .map((row) => row.partner_color_key)
    .filter((value, index, list) => list.indexOf(value) === index);
  if (flowRows.some((row) => row.partner_color_key === "Other")) {
    colorDomain.push("Other");
  }

  const hoverName = `hover_${flowName.toLowerCase()}`;
  const maskName = `mask_${flowName.toLowerCase()}`;
  const lastYear = yearDomain[yearDomain.length - 1];

  const tooltipLabel = metricMode === "quantity" ? "Volume (t)" : "Value (USD)";
  const tooltipFormat = ",.0f";

  const barLayer = {
    params: [
      {
        name: hoverName,
        select: { type: "point", fields: ["partner_group"], on: "mouseover", clear: "mouseout" },
      },
      {
        name: maskName,
        select: { type: "point", fields: ["partner_group"], on: "mouseover", clear: "mouseout", empty: true },
      },
    ],
    mark: { type: "bar" },
    encoding: {
      y: {
        field: "period_str",
        type: "ordinal",
        sort: yearDomain,
        title: null,
        axis: {
          labelFontSize: 11,
          labelColor: "#78a0a3",
          ticks: false,
          domain: false,
          grid: false,
          labelPadding: 4,
        },
      },
      x: {
        field: "metric_display",
        type: "quantitative",
        stack: "zero",
        title: xTitle,
        axis: {
          format: xFormat,
          labelFontSize: 10,
          titleFontSize: 11,
          titleColor: "#78a0a3",
          titlePadding: 8,
          grid: true,
          gridColor: "#edf1f2",
          gridDash: [3, 3],
          domain: false,
          ticks: false,
          labelPadding: 4,
        },
      },
      color: {
        field: "partner_color",
        type: "nominal",
        scale: null,
        legend: null,
      },
      order: { field: "stack_order", type: "quantitative" },
      opacity: {
        condition: { param: maskName, value: 1 },
        value: 0.35,
      },
      tooltip: [
        { field: "period_str", type: "ordinal", title: "Year" },
        { field: "partner_group", type: "nominal", title: "Partner" },
        { field: "metric_value", type: "quantitative", title: tooltipLabel, format: tooltipFormat },
        { field: "share_pct", type: "quantitative", title: "Share (%)", format: ".1f" },
      ],
    },
  };

  const totalLabelLayer = {
    transform: [
      {
        aggregate: [{ op: "sum", field: "metric_display", as: "total_display" }],
        groupby: ["period_str"],
      },
    ],
    mark: { type: "text", align: "left", dx: 5, baseline: "middle", fontSize: 9.5 },
    encoding: {
      y: { field: "period_str", type: "ordinal", sort: yearDomain },
      x: { field: "total_display", type: "quantitative" },
      text: { field: "total_display", type: "quantitative", format: xFormat },
      color: { value: "#78a0a3" },
    },
  };

  const bars = {
    data: { values: flowRows },
    width: chartWidth,
    height: 210,
    layer: [barLayer, totalLabelLayer],
    title: {
      text: flowName,
      anchor: "start",
      color: "#194852",
      fontSize: 14,
      fontWeight: 600,
      dy: -6,
    },
  };

  const shareTitle = {
    data: { values: flowRows },
    transform: [
      { filter: { param: hoverName, empty: false } },
      { aggregate: [{ op: "max", field: "partner_group", as: "partner_group" }], groupby: [] },
    ],
    mark: { type: "text", align: "left", baseline: "bottom", fontSize: 12, fontWeight: 600, color: "#194852" },
    encoding: {
      text: { field: "partner_group", type: "nominal" },
    },
    width: chartWidth,
    height: 18,
  };

  const shareLine = {
    data: { values: flowRows },
    transform: [{ filter: { param: hoverName, empty: false } }],
    width: chartWidth,
    height: 130,
    layer: [
      {
        mark: { type: "line", strokeWidth: 2.5, point: { filled: true, size: 55 } },
        encoding: {
          x: {
            field: "period_str",
            type: "ordinal",
            sort: yearDomain,
            title: "Year",
            axis: {
              labelFontSize: 10,
              titleFontSize: 11,
              titleColor: "#78a0a3",
              titlePadding: 8,
              ticks: false,
              domain: false,
              grid: false,
              labelPadding: 4,
            },
          },
          y: {
            field: "share_pct",
            type: "quantitative",
            title: "Share of total (%)",
            scale: { domain: [0, 100] },
            axis: {
              format: ".0f",
              labelFontSize: 10,
              titleFontSize: 11,
              titleColor: "#78a0a3",
              titlePadding: 8,
              grid: true,
              gridColor: "#edf1f2",
              gridDash: [3, 3],
              domain: false,
              ticks: false,
              tickCount: 3,
              labelPadding: 4,
            },
          },
          color: {
            field: "partner_color",
            type: "nominal",
            scale: null,
            legend: null,
          },
          tooltip: [
            { field: "period_str", type: "ordinal", title: "Year" },
            { field: "partner_group", type: "nominal", title: "Partner" },
            { field: "share_pct", type: "quantitative", title: "Share (%)", format: ".1f" },
          ],
        },
      },
      {
        mark: { type: "text", dy: -12, fontSize: 10, fontWeight: 600 },
        encoding: {
          x: { field: "period_str", type: "ordinal", sort: yearDomain },
          y: { field: "share_pct", type: "quantitative" },
          text: { field: "share_pct", type: "quantitative", format: ".1f" },
          color: {
            field: "partner_color",
            type: "nominal",
            scale: null,
            legend: null,
          },
        },
      },
      {
        transform: [{ filter: `datum.period_str === '${lastYear}'` }],
        mark: { type: "text", align: "left", dx: 7, baseline: "middle", fontSize: 10, fontWeight: 600 },
        encoding: {
          x: { field: "period_str", type: "ordinal", sort: yearDomain },
          y: { field: "share_pct", type: "quantitative" },
          text: { field: "partner_group", type: "nominal" },
          color: {
            field: "partner_color",
            type: "nominal",
            scale: null,
            legend: null,
          },
        },
      },
    ],
  };

  return {
    vconcat: [bars, { vconcat: [shareTitle, shareLine], spacing: 2 }],
    spacing: 16,
  };
}

function buildSpec(rows, chartWidth, flowOrder, metricMode) {
  if (metricMode === "quantity" && !rows.some((r) => r.quantity_mt != null && r.quantity_mt > 0)) {
    return {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      background: null,
      config: { font: "Hanken Grotesk" },
      data: { values: [{ note: "Volume data not available for this dataset" }] },
      mark: { type: "text", color: "#78a0a3", fontSize: 13 },
      encoding: { text: { field: "note" } },
      width: chartWidth,
      height: 120,
    };
  }

  const { plotRows, yearDomain, xTitle, xFormat } = buildTradeChartData(rows, metricMode);
  const rowsByFlow = {
    Export: plotRows.filter((row) => row.flow === "Export"),
    Import: plotRows.filter((row) => row.flow === "Import"),
  };

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: null,
    autosize: {
      type: "fit-x",
      contains: "padding",
      resize: true,
    },
    config: {
      font: "Hanken Grotesk",
      view: {
        continuousWidth: chartWidth,
        stroke: null,
      },
      axis: {
        labelFont: "Hanken Grotesk",
        titleFont: "Hanken Grotesk",
      },
      title: {
        font: "Hanken Grotesk",
      },
    },
    vconcat: flowOrder.map((flow) =>
      buildFlowSpec(rowsByFlow[flow], flow, yearDomain, xTitle, xFormat, chartWidth, metricMode)
    ),
    spacing: 36,
  };
}

function renderTable(tableEl, rows, metricMode) {
  const useQuantity = metricMode === "quantity";
  const sortField = useQuantity ? "quantity_mt" : "trade_value_usd";
  const colHeader = useQuantity ? "Volume (thousand t)" : "Trade Value (USD)";

  const orderedRows = [...rows].sort((a, b) => {
    if (a.period !== b.period) return a.period - b.period;
    return (b[sortField] || 0) - (a[sortField] || 0);
  });

  const head = `
    <thead>
      <tr>
        <th>Year</th>
        <th>Flow</th>
        <th>Partner</th>
        <th>${colHeader}</th>
      </tr>
    </thead>
  `;

  const body = orderedRows
    .map(
      (row) => `
        <tr>
          <td>${row.period}</td>
          <td>${row.flow}</td>
          <td>${row.partnerDesc}</td>
          <td>${useQuantity ? formatQuantity(row.quantity_mt) : formatTradeValue(row.trade_value_usd)}</td>
        </tr>
      `
    )
    .join("");

  tableEl.innerHTML = `${head}<tbody>${body}</tbody>`;
}

async function renderDashboard(key) {
  const config = DASHBOARDS[key];
  const chartEl = document.getElementById(config.chartId);
  const tableEl = document.getElementById(config.tableId);
  const headerEl = document.getElementById(config.headerId);
  const rows = state[key].rows.filter((row) => row.sector === state[key].selectedSector);
  const chartWidth = getChartWidth(chartEl);
  const metricMode = state.metricMode;

  const years = uniq(rows.map((r) => r.period)).sort();
  const yearRange = years.length >= 2 ? `${years[0]}–${years[years.length - 1]}` : (years[0] ?? "");
  headerEl.textContent = `${fmtSector(state[key].selectedSector)} — ${config.titlePrefix}, ${yearRange}`;
  renderTable(tableEl, rows, metricMode);
  chartEl.innerHTML = '<div class="chart-loading">Rendering chart...</div>';

  try {
    await vegaEmbed(`#${config.chartId}`, buildSpec(rows, chartWidth, config.flowOrder, metricMode), {
      actions: false,
      renderer: "svg",
    });
  } catch (error) {
    chartEl.innerHTML = `<div class="chart-error">Chart failed to render: ${error.message}</div>`;
  }
}

function hydrateSelect(key) {
  const config = DASHBOARDS[key];
  const selectEl = document.getElementById(config.selectId);
  const sectors = uniq(state[key].rows.map((row) => row.sector)).sort();
  state[key].selectedSector = sectors[0];

  selectEl.innerHTML = sectors
    .map((sector) => `<option value="${sector}">${fmtSector(sector)}</option>`)
    .join("");

  selectEl.value = state[key].selectedSector;
  selectEl.addEventListener("change", async (event) => {
    state[key].selectedSector = event.target.value;
    await renderDashboard(key);
  });
}

function initTabs() {
  const buttons = document.querySelectorAll(".tab-button");
  const panels = document.querySelectorAll(".panel");

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      buttons.forEach((item) => item.classList.toggle("is-active", item === button));
      panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === tab));
      renderDashboard(tab);
    });
  });
}

function initMetricToggle() {
  document.querySelectorAll(".metric-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (btn.dataset.metric === state.metricMode) return;
      state.metricMode = btn.dataset.metric;
      document.querySelectorAll(".metric-btn").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.metric === state.metricMode);
      });
      const activePanel = document.querySelector(".panel.is-active");
      if (activePanel) {
        await renderDashboard(activePanel.dataset.panel);
      }
    });
  });
}

async function loadData() {
  await Promise.all(
    Object.entries(DASHBOARDS).map(async ([key, config]) => {
      const response = await fetch(config.dataUrl);
      if (!response.ok) {
        throw new Error(`Failed to load ${config.dataUrl}`);
      }
      state[key].rows = await response.json();
      hydrateSelect(key);
      await renderDashboard(key);
    })
  );
}

async function bootstrap() {
  initTabs();
  initMetricToggle();
  try {
    await loadData();
  } catch (error) {
    Object.values(DASHBOARDS).forEach((config) => {
      const chartEl = document.getElementById(config.chartId);
      chartEl.innerHTML = `<div class="chart-error">Unable to load dashboard data: ${error.message}</div>`;
    });
  }
}

let resizeTimer = null;
window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    const activePanel = document.querySelector(".panel.is-active");
    if (activePanel) {
      renderDashboard(activePanel.dataset.panel);
    }
  }, 120);
});

window.addEventListener("DOMContentLoaded", bootstrap);
