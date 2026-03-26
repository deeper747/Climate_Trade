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
  iron_steel_72: "Iron & Steel - Primary (HS 72)",
  iron_steel_73: "Iron & Steel - Articles (HS 73)",
  aluminum: "Aluminum",
  aluminum_76: "Aluminum (HS 76)",
  aluminium: "Aluminum",
  cement: "Cement",
  cement_2523: "Cement (HS 2523)",
};

const DASHBOARDS = {
  eu: {
    dataUrl: "./data/eu_trade.json",
    selectId: "eu-sector",
    chartId: "eu-chart",
    tableId: "eu-table",
    headerId: "eu-chart-header",
    titleSuffix: "EU Top-5 Export & Import Partners, 2019-2023",
  },
  us: {
    dataUrl: "./data/us_trade.json",
    selectId: "us-sector",
    chartId: "us-chart",
    tableId: "us-table",
    headerId: "us-chart-header",
    titleSuffix: "U.S. Top-5 Export & Import Partners, 2019-2023",
  },
};

const state = {
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

function uniq(values) {
  return [...new Set(values)];
}

function getChartWidth(chartEl) {
  const measured = chartEl?.clientWidth || chartEl?.parentElement?.clientWidth || 0;
  return Math.max(Math.floor(measured) - 12, 320);
}

function aggregateRows(rows) {
  const bucket = new Map();

  rows.forEach((row) => {
    const key = [row.period, row.flow, row.partnerDesc].join("||");
    bucket.set(key, (bucket.get(key) || 0) + row.trade_value_usd);
  });

  return [...bucket.entries()].map(([key, tradeValue]) => {
    const [period, flow, partnerDesc] = key.split("||");
    return {
      period: Number(period),
      flow,
      partnerDesc,
      trade_value_usd: tradeValue,
    };
  });
}

function buildTradeChartData(rows) {
  const grouped = aggregateRows(rows);

  const top5Any = new Set();
  uniq(grouped.map((row) => `${row.period}||${row.flow}`)).forEach((key) => {
    const [periodKey, flowKey] = key.split("||");
    grouped
      .filter((row) => String(row.period) === periodKey && row.flow === flowKey)
      .sort((a, b) => b.trade_value_usd - a.trade_value_usd)
      .slice(0, 5)
      .forEach((row) => top5Any.add(`${row.flow}||${row.partnerDesc}`));
  });

  const collapsedMap = new Map();
  grouped.forEach((row) => {
    const partnerGroup = top5Any.has(`${row.flow}||${row.partnerDesc}`) ? row.partnerDesc : "Other";
    const key = [row.period, row.flow, partnerGroup].join("||");
    collapsedMap.set(key, (collapsedMap.get(key) || 0) + row.trade_value_usd);
  });

  const plotRows = [...collapsedMap.entries()].map(([key, tradeValue]) => {
    const [period, flow, partnerGroup] = key.split("||");
    return {
      period: Number(period),
      period_str: String(period),
      flow,
      partner_group: partnerGroup,
      trade_value_usd: tradeValue,
    };
  });

  const totalsByYearFlow = new Map();
  plotRows.forEach((row) => {
    const key = `${row.period}||${row.flow}`;
    totalsByYearFlow.set(key, (totalsByYearFlow.get(key) || 0) + row.trade_value_usd);
  });

  plotRows.forEach((row) => {
    const total = totalsByYearFlow.get(`${row.period}||${row.flow}`) || 0;
    row.share_pct = total ? Number(((row.trade_value_usd / total) * 100).toFixed(1)) : 0;
  });

  const maxUsd = Math.max(...plotRows.map((row) => row.trade_value_usd), 0);
  const useBillions = maxUsd >= 2e9;
  const xTitle = useBillions ? "Trade value (billion USD)" : "Trade value (million USD)";
  const xFormat = useBillions && maxUsd >= 10e9 ? ",.0f" : ",.1f";

  plotRows.forEach((row) => {
    row.trade_display = useBillions ? row.trade_value_usd / 1e9 : row.trade_value_usd / 1e6;
    row.partner_color_key = PARTNER_COLORS[row.partner_group] ? row.partner_group : "Other";
  });

  const totalsByFlowPartner = new Map();
  plotRows.forEach((row) => {
    const key = `${row.flow}||${row.partner_group}`;
    totalsByFlowPartner.set(key, (totalsByFlowPartner.get(key) || 0) + row.trade_value_usd);
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
        .forEach((row) => {
          row.stack_order = index + 1;
        });
    });
  });

  const yearDomain = uniq(plotRows.map((row) => row.period_str)).sort();
  return { plotRows, yearDomain, xTitle, xFormat };
}

function buildFlowSpec(flowRows, flowName, yearDomain, xTitle, xFormat, chartWidth) {
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

  const colorRange = colorDomain.map((key) => PARTNER_COLORS[key] || PARTNER_COLORS.Other);
  const hoverName = `hover_${flowName.toLowerCase()}`;
  const maskName = `mask_${flowName.toLowerCase()}`;

  const bars = {
    data: { values: flowRows },
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
    mark: { type: "bar", cornerRadiusEnd: 1.5 },
    width: chartWidth,
    height: 210,
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
        field: "trade_display",
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
        field: "partner_color_key",
        type: "nominal",
        scale: { domain: colorDomain, range: colorRange },
        legend: null,
      },
      order: { field: "stack_order", type: "quantitative" },
      opacity: {
        condition: { param: maskName, value: 1 },
        value: 0.18,
      },
      tooltip: [
        { field: "period_str", type: "ordinal", title: "Year" },
        { field: "partner_group", type: "nominal", title: "Partner" },
        { field: "trade_value_usd", type: "quantitative", title: "Value (USD)", format: ",.0f" },
        { field: "share_pct", type: "quantitative", title: "Share (%)", format: ".1f" },
      ],
    },
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
              tickCount: 4,
              labelPadding: 4,
            },
          },
          color: {
            field: "partner_color_key",
            type: "nominal",
            scale: { domain: colorDomain, range: colorRange },
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
            field: "partner_color_key",
            type: "nominal",
            scale: { domain: colorDomain, range: colorRange },
            legend: null,
          },
        },
      },
    ],
    title: {
      text: "Hover a bar segment -> partner share over time",
      anchor: "start",
      color: "#78a0a3",
      fontSize: 10,
      fontStyle: "italic",
      dy: -4,
    },
  };

  return {
    vconcat: [bars, { vconcat: [shareTitle, shareLine], spacing: 2 }],
    spacing: 16,
  };
}

function buildSpec(rows, chartWidth) {
  const { plotRows, yearDomain, xTitle, xFormat } = buildTradeChartData(rows);
  const exportRows = plotRows.filter((row) => row.flow === "Export");
  const importRows = plotRows.filter((row) => row.flow === "Import");

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
    vconcat: [
      buildFlowSpec(exportRows, "Export", yearDomain, xTitle, xFormat, chartWidth),
      buildFlowSpec(importRows, "Import", yearDomain, xTitle, xFormat, chartWidth),
    ],
    spacing: 36,
  };
}

function renderTable(tableEl, rows) {
  const orderedRows = [...rows].sort((a, b) => {
    if (a.period !== b.period) return a.period - b.period;
    return b.trade_value_usd - a.trade_value_usd;
  });

  const head = `
    <thead>
      <tr>
        <th>Year</th>
        <th>Flow</th>
        <th>Partner</th>
        <th>Trade Value (USD)</th>
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
          <td>${formatTradeValue(row.trade_value_usd)}</td>
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

  headerEl.textContent = `${fmtSector(state[key].selectedSector)} - ${config.titleSuffix}`;
  renderTable(tableEl, rows);
  chartEl.innerHTML = '<div class="chart-loading">Rendering chart...</div>';

  try {
    await vegaEmbed(`#${config.chartId}`, buildSpec(rows, chartWidth), {
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
