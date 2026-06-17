/**
 * Chart.js wrappers for all dashboard visualizations.
 */
const COLORS = {
  yellow: "#f6c90e",
  blue: "#3182ce",
  green: "#38a169",
  red: "#e53e3e",
  orange: "#dd6b20",
  purple: "#805ad5",
  teal: "#319795",
  pink: "#d53f8c",
  dark: "#1a1a2e",
};

const PALETTE = [
  "#f6c90e",
  "#3182ce",
  "#38a169",
  "#e53e3e",
  "#dd6b20",
  "#805ad5",
  "#319795",
  "#d53f8c",
  "#2b6cb0",
  "#276749",
];

const charts = {};

function destroyChart(id) {
  if (charts[id]) {
    charts[id].destroy();
    delete charts[id];
  }
}

// ── Daily Trend Line Chart ──────────────────────────────────────────────────
function renderDailyTrend(data) {
  destroyChart("daily");
  const labels = data.map((d) => d.pickup_date);
  const trips = data.map((d) => d.trips);
  const revenue = data.map((d) => d.revenue);
  charts["daily"] = new Chart(document.getElementById("chart-daily"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Trips",
          data: trips,
          borderColor: COLORS.yellow,
          backgroundColor: "rgba(246,201,14,0.1)",
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          yAxisID: "y",
        },
        {
          label: "Revenue ($)",
          data: revenue,
          borderColor: COLORS.blue,
          backgroundColor: "rgba(49,130,206,0.05)",
          fill: false,
          tension: 0.4,
          pointRadius: 3,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top" } },
      scales: {
        y: {
          type: "linear",
          position: "left",
          title: { display: true, text: "Trips" },
        },
        y1: {
          type: "linear",
          position: "right",
          title: { display: true, text: "Revenue ($)" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

// ── Payment Doughnut ───────────────────────────────────────────────────────
function renderPayment(data) {
  destroyChart("payment");
  const labels = data.map((d) => d.label || `Type ${d.payment_type}`);
  const values = data.map((d) => d.trips);
  charts["payment"] = new Chart(document.getElementById("chart-payment"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: PALETTE, borderWidth: 2 }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "right" },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ` ${ctx.label}: ${ctx.parsed.toLocaleString()} trips`,
          },
        },
      },
    },
  });
}

// ── Hourly Bar Chart ───────────────────────────────────────────────────────
function renderByHour(data) {
  destroyChart("hour");
  const sorted = [...data].sort((a, b) => a.hour - b.hour);
  const labels = sorted.map((d) => `${d.hour}:00`);
  const trips = sorted.map((d) => d.trips);
  const fares = sorted.map((d) => d.avg_fare);
  charts["hour"] = new Chart(document.getElementById("chart-hour"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Trips",
          data: trips,
          backgroundColor: COLORS.yellow,
          yAxisID: "y",
        },
        {
          label: "Avg Fare ($)",
          data: fares,
          type: "line",
          borderColor: COLORS.blue,
          backgroundColor: "transparent",
          tension: 0.4,
          yAxisID: "y1",
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "top" } },
      scales: {
        y: { title: { display: true, text: "Trips" } },
        y1: {
          position: "right",
          title: { display: true, text: "Avg Fare ($)" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

// ── Day of Week Bar ────────────────────────────────────────────────────────
function renderByDay(data) {
  destroyChart("day");
  const order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
  ];
  const sorted = order.map(
    (day) =>
      data.find((d) => d.day_name === day) || {
        day_name: day,
        trips: 0,
        avg_fare: 0,
      },
  );
  charts["day"] = new Chart(document.getElementById("chart-day"), {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.day_name.slice(0, 3)),
      datasets: [
        {
          label: "Trips",
          data: sorted.map((d) => d.trips),
          backgroundColor: PALETTE,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { title: { display: true, text: "Trips" } } },
    },
  });
}

// ── Speed Distribution ─────────────────────────────────────────────────────
function renderSpeedDist(data) {
  destroyChart("speed");
  const labels = Object.keys(data).map((k) => `${k} mph`);
  const values = Object.values(data);
  charts["speed"] = new Chart(document.getElementById("chart-speed"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Trips",
          data: values,
          backgroundColor: [
            COLORS.green,
            COLORS.yellow,
            COLORS.orange,
            COLORS.red,
            COLORS.purple,
          ],
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Average Speed (mph)" },
      },
      scales: { y: { title: { display: true, text: "Trips" } } },
    },
  });
}

// ── Borough Bar Charts ─────────────────────────────────────────────────────
function renderByBorough(data) {
  destroyChart("borough");
  destroyChart("borough-rev");
  const sorted = [...data].sort((a, b) => b.trips - a.trips);
  charts["borough"] = new Chart(document.getElementById("chart-borough"), {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.borough),
      datasets: [
        {
          label: "Trips",
          data: sorted.map((d) => d.trips),
          backgroundColor: PALETTE,
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { x: { title: { display: true, text: "Trips" } } },
    },
  });
  charts["borough-rev"] = new Chart(
    document.getElementById("chart-borough-rev"),
    {
      type: "bar",
      data: {
        labels: sorted.map((d) => d.borough),
        datasets: [
          {
            label: "Revenue ($)",
            data: sorted.map((d) => d.revenue),
            backgroundColor: COLORS.blue,
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { title: { display: true, text: "Revenue ($)" } } },
      },
    },
  );
}

// ── Top Zones Horizontal Bar ───────────────────────────────────────────────
function renderTopZones(data, canvasId = "chart-zones") {
  destroyChart(canvasId);
  const sorted = [...data].sort((a, b) => b.trips - a.trips);
  charts[canvasId] = new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.zone || d.pu_zone),
      datasets: [
        {
          label: "Trips",
          data: sorted.map((d) => d.trips),
          backgroundColor: COLORS.yellow,
          borderColor: COLORS.dark,
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Number of Trips" } },
        y: { ticks: { font: { size: 11 } } },
      },
    },
  });
}

// ── Rejection Pie ──────────────────────────────────────────────────────────
function renderRejection(data) {
  destroyChart("rejection");
  const labels = Object.keys(data).map((k) => k.replace(/_/g, " "));
  const values = Object.values(data);
  charts["rejection"] = new Chart(document.getElementById("chart-rejection"), {
    type: "pie",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: [
            COLORS.red,
            COLORS.orange,
            COLORS.yellow,
            COLORS.purple,
            COLORS.blue,
          ],
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
    },
  });
}

// ── DSA Zones ─────────────────────────────────────────────────────────────
function renderDSAZones(data) {
  if (!data || !data.top_zones) return;
  renderTopZones(
    data.top_zones.map((z) => ({ zone: z.zone, trips: z.trips })),
    "chart-dsa-zones",
  );
}
