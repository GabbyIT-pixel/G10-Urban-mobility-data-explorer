// api.js - handles all fetch calls to the Flask backend
const API = "http://127.0.0.1:5000/api";
async function apiFetch(endpoint) {
  try {
    const res = await fetch(`${API}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error [${endpoint}]:`, e);
    return null;
  }
}
async function fetchSummary() {
  return apiFetch("/summary");
}
async function fetchByHour() {
  return apiFetch("/by-hour");
}
async function fetchByBorough() {
  return apiFetch("/by-borough");
}
async function fetchByDay() {
  return apiFetch("/by-day");
}
async function fetchByPayment() {
  return apiFetch("/by-payment");
}
async function fetchTopZones() {
  return apiFetch("/top-zones");
}
async function fetchDailyTrend() {
  return apiFetch("/daily-trend");
}
async function fetchAirport() {
  return apiFetch("/airport");
}
async function fetchSpeedDist() {
  return apiFetch("/speed-distribution");
}
async function fetchDataQuality() {
  return apiFetch("/data-quality");
}
async function fetchDSABenchmark() {
  return apiFetch("/dsa-benchmark");
}
async function fetchBoroughs() {
  return apiFetch("/boroughs");
}
async function fetchTrips(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) qs.append(k, v);
  });
  return apiFetch(`/trips?${qs.toString()}`);
}