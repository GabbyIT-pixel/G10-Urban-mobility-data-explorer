# NYC Taxi Urban Mobility Data Explorer

> **Group 10** · ALU Software Engineering · Summative Assessment

A full-stack data platform that cleans, analyzes, and visualizes NYC Yellow Taxi trip data using a custom ETL pipeline, a Flask REST API, manually implemented algorithms, and an interactive dashboard.

---

## Table of Contents
- [Overview](#overview)
- [Team](#team)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Project](#running-the-project)
- [Database Schema](#database-schema)
- [Custom Algorithms](#custom-algorithms)
- [API Reference](#api-reference)
- [Data Cleaning Summary](#data-cleaning-summary)
- [Video Walkthrough](#video-walkthrough)

---

## Overview

This project ingests NYC Taxi & Limousine Commission (TLC) trip data — a parquet fact table of individual trips, joined against a CSV dimension table of taxi zones — cleans it, engineers new features, stores it in a normalized SQLite database, and serves it through a Flask API to an interactive HTML/CSS/JS dashboard.

| Capability | Detail |
|---|---|
| Data source | `yellow_tripdata_2024-01.parquet` + `taxi_zone_lookup.csv` |
| Records processed | 50,000 raw → 49,121 clean trips |
| Data cleaning | Removes negative fares, zero distances, zero passengers, future dates, impossible speeds, inconsistent fare totals |
| Feature engineering | 4 derived features: trip duration, average speed, fare-per-mile, tip percentage |
| Database | SQLite with indexed `trips` and `taxi_zones` tables |
| Backend | Flask REST API with 13 endpoints |
| Frontend | 6-tab interactive dashboard with Chart.js visualizations |
| Custom DSA | Manual QuickSort, Min-Heap Top-K, and HashMap — no built-in sort/heapq/Counter |

---

## Team

| Name | Role |
|---|---|
| Gabriel Mugisha | Team Lead · Project Structure |
| Olivier Dusabamahoro | Backend · ETL Pipeline · Database |
| James Kanneh | Frontend · Dashboard · Visualization |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Data Sources                          │
│  yellow_tripdata_2024-01.parquet (fact table)             │
│  taxi_zone_lookup.csv (dimension table)                   │
│  taxi_zones.shp (spatial metadata)                        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│                  ETL Pipeline (Python)                    │
│  backend/etl/clean.py                                     │
│    1. Load & merge parquet + CSV                          │
│    2. Identify data quality issues                        │
│    3. Clean (remove outliers, fill nulls)                 │
│    4. Engineer features (duration, speed, fare/mile)      │
│    5. Save to SQLite + dead-letter log                    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│              SQLite Database (nyc_taxi.db)                │
│  trips table (indexed)  +  taxi_zones table                │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / JSON
                        ▼
┌──────────────────────────────────────────────────────────┐
│              Flask REST API (backend/api/app.py)          │
│  /api/summary  /api/trips  /api/by-hour  /api/by-borough   │
│  /api/dsa-benchmark  ...13 endpoints total                │
└───────────────────────┬─────────────────────────────────┘
                        │ fetch()
                        ▼
┌──────────────────────────────────────────────────────────┐
│         Frontend Dashboard (HTML/CSS/JS + Chart.js)        │
│  6 tabs: Overview · Patterns · Geography ·                 │
│          Trip Explorer · DSA Benchmark · Data Quality      │
└──────────────────────────────────────────────────────────┘
```

**Why this stack?**
- **SQLite** chosen over PostgreSQL/MySQL for zero-config local development and easy grading — no server setup required for the instructor.
- **Flask** chosen over FastAPI for simplicity and because the assignment explicitly allows it; no async features were needed for this read-heavy workload.
- **Vanilla JS + Chart.js** chosen over a frontend framework (React/Vue) to keep the dashboard dependency-free and instantly runnable with no build step.

---

## Project Structure

```
G10-Urban-mobility-data-explorer/
│
├── README.md
├── .gitignore
│
├── backend/
│   ├── etl/
│   │   ├── clean.py          – data cleaning & feature engineering
│   │   └── algorithms.py     – custom QuickSort, MinHeap, HashMap
│   ├── api/
│   │   └── app.py            – Flask REST API
│   └── tests/
│       ├── test_clean.py     – ETL unit tests
│       └── test_algorithms.py – DSA unit tests
│
├── data/
│   ├── raw/
│   │   ├── yellow_tripdata_2024-01.parquet
│   │   ├── taxi_zone_lookup.csv
│   │   └── taxi_zones.shp (+ .dbf, .shx, .prj)
│   ├── processed/
│   │   └── stats.json        – precomputed dashboard stats
│   └── logs/
│       ├── dead_letter.csv   – rejected records
│       └── rejection_summary.json
│
├── database/
│   └── nyc_taxi.db           – SQLite database (generated)
│
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js            – fetch wrappers
│       ├── charts.js         – Chart.js render functions
│       └── dashboard.js       – main controller
│
├── docs/
│   ├── architecture.png      – system diagram
│   ├── erd.png               – database entity-relationship diagram
│   └── technical_report.pdf  – problem framing, architecture, algorithms, insights, reflection
│
└── screenshots/              – test evidence
```

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/luckydus5/G10-Urban-mobility-data-explorer.git
cd G10-Urban-mobility-data-explorer
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install pandas pyarrow flask flask-cors
```

### 4. Place the data files
Download from the [NYC TLC website](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page):
- `yellow_tripdata_2024-01.parquet` → place in `backend/data/raw/`
- `taxi_zone_lookup.csv` → place in `backend/data/raw/` (already included)
- `taxi_zones.shp` (+ related files) → place in `backend/data/raw/` (already included)

> **Note on data location:** the ETL script resolves paths relative to itself
> (`backend/etl/clean.py` → looks for `backend/data/raw/`), **not** a top-level
> `data/` folder. If you see `FileNotFoundError`, double check the files are
> nested under `backend/data/raw/`, not `data/raw/` at the project root.

---

## Running the Project

### Step 1 — Run the ETL pipeline
```bash
cd backend/etl
python clean.py
```
This cleans the raw data, engineers features, and populates `database/nyc_taxi.db`.

**Expected output:**
```
[1/6] Loading raw data...
      Raw records : 50,000
[2/6] Cleaning data...
      Clean    : 49,502
      Rejected : 498  (1.0%)
[3/6] Engineering features...
      Records after speed filter : 49,121
[4/6] Saving to database...
      Inserted 49,121 trips
[5/6] Computing dashboard stats...
[6/6] Dead-letter: 498 records → data/logs/dead_letter.csv
```

### Step 2 — Run the DSA benchmark (optional, standalone)
```bash
python algorithms.py
```

### Step 3 — Start the backend API
```bash
cd backend/api
python app.py
```
API runs on `http://127.0.0.1:5000`

> **Troubleshooting — `sqlite3.OperationalError: no such table: trips`:**
> This means `clean.py` (Step 1) was never run successfully, or `database/nyc_taxi.db`
> exists but is 0 bytes / empty. Re-run `python clean.py` from `backend/etl/` and
> confirm you see `Inserted 49,121 trips` in the output **before** starting the API
> or running `algorithms.py`.

### Step 4 — Launch the frontend
Open `frontend/index.html` with a local server (e.g. VS Code Live Server extension) at `http://127.0.0.1:5500/frontend/index.html`

> **Note:** Opening `index.html` directly via `file://` will not work because the browser blocks `fetch()` calls to the API under CORS for local files. Use Live Server or run `python -m http.server` from the `frontend/` folder.

### Step 5 — Run the test suite
```bash
cd backend/tests
python test_clean.py
python test_algorithms.py
```

---

## Database Schema

```sql
CREATE TABLE taxi_zones (
    location_id  INTEGER PRIMARY KEY,
    borough      TEXT NOT NULL,
    zone         TEXT NOT NULL,
    service_zone TEXT
);

CREATE TABLE trips (
    trip_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id             INTEGER,
    pickup_datetime       TEXT NOT NULL,
    dropoff_datetime      TEXT NOT NULL,
    passenger_count       INTEGER,
    trip_distance         REAL NOT NULL,
    pu_location_id        INTEGER,
    do_location_id        INTEGER,
    rate_code_id          INTEGER,
    payment_type          INTEGER,
    fare_amount           REAL NOT NULL,
    tip_amount            REAL DEFAULT 0,
    tolls_amount          REAL DEFAULT 0,
    total_amount          REAL NOT NULL,
    congestion_surcharge  REAL DEFAULT 0,
    airport_fee           REAL DEFAULT 0,
    trip_duration_min     REAL,   -- derived feature 1
    speed_mph             REAL,   -- derived feature 2
    fare_per_mile         REAL,   -- derived feature 3
    tip_percentage        REAL,   -- derived feature 4
    hour                  INTEGER,
    day_name              TEXT,
    pickup_date           TEXT,
    is_airport            INTEGER DEFAULT 0,
    pu_borough            TEXT,
    do_borough            TEXT,
    pu_zone               TEXT,
    do_zone               TEXT
);

CREATE INDEX idx_date    ON trips(pickup_date);
CREATE INDEX idx_borough ON trips(pu_borough);
CREATE INDEX idx_hour    ON trips(hour);
CREATE INDEX idx_payment ON trips(payment_type);
CREATE INDEX idx_airport ON trips(is_airport);
```

---

## Custom Algorithms

Three algorithms were implemented manually with no built-in `sort()`, `heapq`, or `Counter`:

### 1. QuickSort — `backend/etl/algorithms.py`
Sorts trips by fare amount using manual partition-based recursion.
**Complexity:** O(n log n) average, O(n²) worst case, O(log n) space.

### 2. Min-Heap Top-K — `backend/etl/algorithms.py`
Finds the top-10 busiest pickup zones using a manually built min-heap of size K, avoiding a full O(n log n) sort.
**Complexity:** O(n log k) time, O(k) space.

### 3. Manual HashMap — `backend/etl/algorithms.py`
Counts trips per borough using a hash table with separate chaining and a custom polynomial rolling hash function.
**Complexity:** O(n) average, O(k) space.

Run the live benchmark:
```bash
python backend/etl/algorithms.py
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/summary` | Dashboard KPI summary |
| GET | `/api/trips` | Paginated trips with filters (`borough`, `payment_type`, `min_fare`, `max_fare`, `hour`) |
| GET | `/api/trips/<id>` | Single trip detail |
| GET | `/api/by-hour` | Trips grouped by hour of day |
| GET | `/api/by-borough` | Trips grouped by borough |
| GET | `/api/by-day` | Trips grouped by day of week |
| GET | `/api/by-payment` | Trips grouped by payment type |
| GET | `/api/top-zones` | Top 10 busiest pickup zones |
| GET | `/api/daily-trend` | Daily trip counts and revenue |
| GET | `/api/airport` | Airport vs non-airport fare comparison |
| GET | `/api/speed-distribution` | Speed bucket distribution |
| GET | `/api/dsa-benchmark` | Live DSA algorithm benchmark results |
| GET | `/api/data-quality` | Data cleaning issue counts |

---

## Data Cleaning Summary

| Issue | Count | Action |
|---|---|---|
| Negative fares | 199 | Excluded (meter/refund errors) |
| Zero passengers | 149 | Excluded (data entry error) |
| Zero distance | 100 | Excluded (cancelled/GPS failure) |
| Future timestamps | 50 | Excluded (temporal anomaly) |
| Impossible speed (>100mph) | ~381 | Excluded post feature-engineering |
| Inconsistent fare total | varies | Excluded when `total_amount` ≠ sum of components (±$1 tolerance) |
| Null passenger count | 300 | Filled with mode (1) |
| Null rate code | 200 | Filled with mode (1) |

**Total:** 50,000 raw → 49,121 clean records (98.2% retention rate)

Full dead-letter log: `backend/data/logs/dead_letter.csv`

---

## Video Walkthrough

*(Link to be added before submission)*

---

## AI Usage Disclosure

In accordance with the assignment's academic integrity policy, AI tools were used only to assist in writing this README file. All code, database design, algorithm implementation, and insights were produced independently by the team.

Chat reference: [(https://chatgpt.com/share/6a387ff0-6b70-83ea-8f0c-a4ad14348fef)]


---
