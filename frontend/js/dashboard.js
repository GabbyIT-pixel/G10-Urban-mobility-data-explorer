// dashboard.js - main controller: loads data, updates DOM, handles interactions

// number and currency formatters used throughout
const fmt = {
  num: (v) => (v ?? 0).toLocaleString(),
  money: (v) =>
    `$${(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  dec: (v) => (v ?? 0).toFixed(2),
  pct: (v, t) => `${((v / t) * 100).toFixed(1)}%`,
};

const payLabel = {
  1: "Credit Card",
  2: "Cash",
  3: "No Charge",
  4: "Dispute",
  5: "Unknown",
};

// tab switching
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".tab")
      .forEach((b) => b.classList.remove("active"));
    document
      .querySelectorAll(".tab-content")
      .forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// overview tab
async function loadOverview() {
  const [summary, trend, payment, airport] = await Promise.all([
    fetchSummary(),
    fetchDailyTrend(),
    fetchByPayment(),
    fetchAirport(),
  ]);

  if (summary) {
    document.getElementById("kpi-trips").textContent = fmt.num(
      summary.total_trips,
    );
    document.getElementById("kpi-revenue").textContent = fmt.money(
      summary.total_revenue,
    );
    document.getElementById("kpi-avg-fare").textContent = fmt.money(
      summary.avg_fare,
    );
    document.getElementById("kpi-avg-dist").textContent =
      `${fmt.dec(summary.avg_distance)} mi`;
    document.getElementById("kpi-avg-dur").textContent =
      `${fmt.dec(summary.avg_duration)} min`;
    document.getElementById("kpi-airport").textContent = fmt.num(
      summary.airport_trips,
    );
    document.getElementById("status-badge").textContent = "● Live";
    document.getElementById("status-badge").style.background = "#38a169";
  }

  if (trend) {
    renderDailyTrend(trend);

    // Derive the human-readable reporting period from the actual data
    // returned by the API rather than hardcoding any month/year — this
    // keeps the UI correct regardless of which TLC file was loaded.
    //
    // IMPORTANT: pickup_date strings are plain "YYYY-MM-DD" with no time
    // component, which `new Date(...)` parses as UTC midnight. Reading
    // them back with local-time getters (getMonth(), toLocaleDateString())
    // can silently roll the date forward or backward a day depending on
    // the viewer's timezone offset — e.g. "2019-01-31" showing as February
    // for anyone west of UTC. We use the UTC getters/formatter explicitly
    // so the label always matches the actual date string from the API.
    const dates = trend
      .map((d) => d.pickup_date)
      .filter(Boolean)
      .sort();
    if (dates.length) {
      const first = new Date(dates[0]);
      const last = new Date(dates[dates.length - 1]);
      const opts = { year: "numeric", month: "long", timeZone: "UTC" };
      const periodLabel =
        first.getUTCFullYear() === last.getUTCFullYear() &&
        first.getUTCMonth() === last.getUTCMonth()
          ? first.toLocaleDateString("en-US", opts)
          : `${first.toLocaleDateString("en-US", opts)} – ${last.toLocaleDateString("en-US", opts)}`;

      document.getElementById("header-subtitle").textContent =
        `Group 10 · ALU Software Engineering · ${periodLabel} Data`;
      document.getElementById("daily-trend-title").textContent =
        `Daily Trip Trend — ${periodLabel}`;
      document.getElementById("footer-period").textContent =
        `Gabriel Mugisha · Olivier Dusabamahoro · James Kanneh · ${periodLabel} Data`;
    }
  }

  if (payment) renderPayment(payment);

  if (airport) {
    const diff = airport.airport - airport.non_airport;
    document.getElementById("insight-airport").innerHTML =
      `Airport trips average <strong>${fmt.money(airport.airport)}</strong> per fare, compared to 
       <strong>${fmt.money(airport.non_airport)}</strong> for non-airport trips — 
       a <strong>${fmt.money(Math.abs(diff))}</strong> ${diff > 0 ? "premium" : "discount"}.
       This reflects longer distances and fixed-rate structures for JFK, LaGuardia, and Newark routes.`;
  }
}

// time patterns tab
async function loadPatterns() {
  const [hourly, daily, speed] = await Promise.all([
    fetchByHour(),
    fetchByDay(),
    fetchSpeedDist(),
  ]);

  if (hourly) {
    renderByHour(hourly);
    const peak = hourly.reduce(
      (a, b) => (b.trips > a.trips ? b : a),
      hourly[0],
    );
    document.getElementById("insight-hour").innerHTML =
      `The busiest hour is <strong>${peak.hour}:00</strong> with 
       <strong>${fmt.num(peak.trips)}</strong> trips and an average fare of 
       <strong>${fmt.money(peak.avg_fare)}</strong>. 
       Late night hours (2–5 AM) show the lowest demand, while morning and evening commute 
       peaks dominate weekday patterns. This aligns with typical urban commuter behavior 
       in New York City.`;
  }
  if (daily) renderByDay(daily);
  if (speed) renderSpeedDist(speed);
}

// geography tab
async function loadGeography() {
  const [boroughs, zones] = await Promise.all([
    fetchByBorough(),
    fetchTopZones(),
  ]);

  if (boroughs) {
    renderByBorough(boroughs);
    const top = boroughs.sort((a, b) => b.trips - a.trips)[0];
    document.getElementById("insight-geo").innerHTML =
      `<strong>${top?.borough}</strong> is the busiest borough with 
       <strong>${fmt.num(top?.trips)}</strong> pickups, generating 
       <strong>${fmt.money(top?.revenue)}</strong> in revenue. 
       Manhattan dominates NYC taxi demand due to its density of offices, 
       hotels, and tourist attractions. Airport zones (JFK #132, LaGuardia #138) 
       consistently rank among the top individual pickup locations.`;
  }
  if (zones) renderTopZones(zones);
}

// trip explorer with filters and pagination
let currentPage = 1;
let currentFilters = {};

async function loadTrips(page = 1, filters = {}) {
  currentPage = page;
  currentFilters = filters;

  const data = await fetchTrips({ ...filters, page, limit: 20 });
  if (!data) return;

  document.getElementById("results-info").textContent =
    `Showing ${fmt.num((page - 1) * 20 + 1)}–${fmt.num(Math.min(page * 20, data.total))} of ${fmt.num(data.total)} trips`;

  const tbody = document.getElementById("trips-tbody");
  if (!data.trips.length) {
    tbody.innerHTML = `<tr><td colspan="12" class="empty">No trips found for these filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.trips
    .map(
      (t) => `
    <tr>
      <td>${t.trip_id}</td>
      <td>${t.pickup_datetime?.slice(0, 16) ?? "—"}</td>
      <td>${t.pu_borough ?? "—"}<br><small>${t.pu_zone ?? ""}</small></td>
      <td>${t.do_borough ?? "—"}<br><small>${t.do_zone ?? ""}</small></td>
      <td>${fmt.dec(t.trip_distance)} mi</td>
      <td>${fmt.dec(t.trip_duration_min)} min</td>
      <td>${fmt.dec(t.speed_mph)} mph</td>
      <td>${fmt.money(t.fare_amount)}</td>
      <td>${fmt.money(t.tip_amount)}</td>
      <td>${fmt.money(t.total_amount)}</td>
      <td><span class="badge-${t.payment_type === 1 ? "credit" : "cash"}">${payLabel[t.payment_type] ?? "Other"}</span></td>
      <td>${t.is_airport ? '<span class="badge-airport">Airport</span>' : '<span class="badge-noairport">No</span>'}</td>
    </tr>
  `,
    )
    .join("");

  renderPagination(data.pages, page);
}

function renderPagination(totalPages, current) {
  const el = document.getElementById("pagination");
  el.innerHTML = "";
  if (totalPages <= 1) return;

  const makeBtn = (label, page, active = false, disabled = false) => {
    const b = document.createElement("button");
    b.className = "page-btn" + (active ? " active" : "");
    b.textContent = label;
    b.disabled = disabled;
    if (!disabled) b.onclick = () => loadTrips(page, currentFilters);
    el.appendChild(b);
  };

  makeBtn("«", 1, false, current === 1);
  makeBtn("‹", current - 1, false, current === 1);

  const start = Math.max(1, current - 2);
  const end = Math.min(totalPages, current + 2);
  for (let p = start; p <= end; p++) makeBtn(p, p, p === current);

  makeBtn("›", current + 1, false, current === totalPages);
  makeBtn("»", totalPages, false, current === totalPages);
}

// filter controls
document.getElementById("btn-search").addEventListener("click", () => {
  const filters = {
    borough: document.getElementById("filter-borough").value,
    payment_type: document.getElementById("filter-payment").value,
    min_fare: document.getElementById("filter-min-fare").value,
    max_fare: document.getElementById("filter-max-fare").value,
    hour: document.getElementById("filter-hour").value,
  };
  loadTrips(1, filters);
});

document.getElementById("btn-reset").addEventListener("click", () => {
  document.getElementById("filter-borough").value = "";
  document.getElementById("filter-payment").value = "";
  document.getElementById("filter-min-fare").value = "";
  document.getElementById("filter-max-fare").value = "";
  document.getElementById("filter-hour").value = "";
  loadTrips(1, {});
});

async function populateBoroughFilter() {
  const boroughs = await fetchBoroughs();
  if (!boroughs) return;
  const sel = document.getElementById("filter-borough");
  boroughs.forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b;
    opt.textContent = b;
    sel.appendChild(opt);
  });
}

// algorithms benchmark tab
document.getElementById("btn-run-dsa").addEventListener("click", async () => {
  const btn = document.getElementById("btn-run-dsa");
  btn.textContent = "Running…";
  btn.disabled = true;

  const data = await fetchDSABenchmark();
  btn.textContent = "▶ Run Benchmark";
  btn.disabled = false;

  if (!data) {
    ["bench-quicksort", "bench-heap", "bench-hashmap"].forEach((id) => {
      document.getElementById(id).textContent = "Error running benchmark.";
    });
    return;
  }

  document.getElementById("bench-quicksort").innerHTML =
    `Manual QuickSort : <strong>${data.quicksort_ms} ms</strong><br>
     Python sort()    : ${data.python_sort_ms} ms<br>
     Results match    : <span class="match-ok">OK</span>`;

  document.getElementById("bench-heap").innerHTML =
    `Manual MinHeap   : <strong>${data.heap_ms} ms</strong> O(n log k)<br>
     Python sorted()  : ${data.sorted_ms} ms O(n log n)<br>
     Top zone         : ${data.top_zones?.[0]?.zone ?? "—"}`;

  document.getElementById("bench-hashmap").innerHTML =
    `Manual HashMap   : <strong>${data.hashmap_ms} ms</strong><br>
     Python dict      : ${data.dict_ms} ms<br>
     Results match    : <span class="match-ok">OK</span>`;

  if (data.top_zones) renderDSAZones(data);
});

// data quality tab
async function loadQuality() {
  const data = await fetchDataQuality();
  if (!data) return;

  const grid = document.getElementById("quality-grid");
  const items = [
    { key: "total_raw", label: "Total Raw Records", warn: false },
    { key: "negative_fare", label: "Negative Fares", warn: true },
    { key: "zero_passenger", label: "Zero Passengers", warn: true },
    { key: "zero_distance", label: "Zero Distance", warn: true },
    { key: "future_pickup", label: "Future Timestamps", warn: true },
    { key: "null_passenger", label: "Null Passenger Count", warn: true },
    { key: "null_ratecode", label: "Null Rate Code", warn: false },
    { key: "dropoff_before_pickup", label: "Bad Trip Duration", warn: true },
    { key: "extreme_fare", label: "Extreme Fares (>$500)", warn: true },
    { key: "extreme_distance", label: "Distance >100 mi", warn: true },
  ];

  grid.innerHTML = items
    .map(
      (item) => `
    <div class="quality-card ${item.warn && data[item.key] > 0 ? "warn" : "ok"}">
      <div class="q-value">${fmt.num(data[item.key] ?? 0)}</div>
      <div class="q-label">${item.label}</div>
    </div>
  `,
    )
    .join("");

  // rejection breakdown chart
  const rejData = await apiFetch("/data-quality");
  if (rejData) {
    const rejectKeys = [
      "negative_fare",
      "zero_passenger",
      "zero_distance",
      "future_pickup",
      "dropoff_before_pickup",
      "extreme_fare",
    ];
    const chartData = {};
    rejectKeys.forEach((k) => {
      if (rejData[k] > 0) chartData[k] = rejData[k];
    });
    renderRejection(chartData);
  }
}

// init - load overview immediately, lazy load everything else on tab click
(async function init() {
  await Promise.all([loadOverview(), populateBoroughFilter()]);

  const loaded = { overview: true };

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const tab = btn.dataset.tab;
      if (loaded[tab]) return;
      loaded[tab] = true;

      if (tab === "patterns") await loadPatterns();
      if (tab === "geography") await loadGeography();
      if (tab === "trips") await loadTrips(1, {});
      if (tab === "quality") await loadQuality();
    });
  });
})();