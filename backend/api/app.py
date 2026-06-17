"""
app.py  –  NYC Taxi Urban Mobility Explorer
Flask REST API serving trip data from SQLite database.

Endpoints:
  GET /api/summary          – dashboard summary stats
  GET /api/trips            – paginated trip list with filters
  GET /api/trips/<id>       – single trip detail
  GET /api/by-hour          – trips grouped by hour
  GET /api/by-borough       – trips grouped by borough
  GET /api/by-day           – trips grouped by day of week
  GET /api/by-payment       – trips grouped by payment type
  GET /api/top-zones        – top 10 pickup zones
  GET /api/daily-trend      – daily trip counts and revenue
  GET /api/dsa-benchmark    – run DSA benchmark and return results
  GET /api/data-quality     – data cleaning summary

Author: Group 10 · Gabriel Mugisha · Olivier Dusabamahoro · James Kanneh
"""

import sqlite3
import json
import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

# Path setup
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "etl"))

DB         = os.path.join(BASE, "database", "nyc_taxi.db")
STATS_JSON = os.path.join(BASE, "backend", "data", "processed", "stats.json")

app = Flask(__name__)
CORS(app)   # allow frontend to call API


# ── DB helper ──────────────────────────────────────────────────────────────────
def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Load precomputed stats ─────────────────────────────────────────────────────
def load_stats():
    with open(STATS_JSON) as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/summary")
def summary():
    stats = load_stats()
    return jsonify(stats["summary"])


@app.route("/api/data-quality")
def data_quality():
    stats = load_stats()
    return jsonify(stats["data_quality"])


@app.route("/api/trips")
def trips():
    """
    Paginated trip list.
    Query params:
      page=1, limit=20
      borough=Manhattan
      payment_type=1
      min_fare=0, max_fare=200
      hour=8
    """
    page         = int(request.args.get("page",  1))
    limit        = int(request.args.get("limit", 20))
    offset       = (page - 1) * limit

    borough      = request.args.get("borough")
    payment_type = request.args.get("payment_type")
    min_fare     = request.args.get("min_fare")
    max_fare     = request.args.get("max_fare")
    hour         = request.args.get("hour")

    where  = []
    params = []

    if borough:
        where.append("pu_borough = ?")
        params.append(borough)
    if payment_type:
        where.append("payment_type = ?")
        params.append(int(payment_type))
    if min_fare:
        where.append("fare_amount >= ?")
        params.append(float(min_fare))
    if max_fare:
        where.append("fare_amount <= ?")
        params.append(float(max_fare))
    if hour:
        where.append("hour = ?")
        params.append(int(hour))

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = query_one(
        f"SELECT COUNT(*) as cnt FROM trips {where_clause}", params
    )["cnt"]

    rows = query(
        f"""SELECT trip_id, pickup_datetime, dropoff_datetime,
                   passenger_count, trip_distance, pu_borough, do_borough,
                   pu_zone, do_zone, fare_amount, tip_amount, total_amount,
                   payment_type, trip_duration_min, speed_mph,
                   fare_per_mile, is_airport, hour, day_name
            FROM trips {where_clause}
            ORDER BY trip_id
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    )

    return jsonify({
        "page":       page,
        "limit":      limit,
        "total":      total,
        "pages":      (total + limit - 1) // limit,
        "trips":      rows
    })


@app.route("/api/trips/<int:trip_id>")
def trip_detail(trip_id):
    row = query_one("SELECT * FROM trips WHERE trip_id = ?", (trip_id,))
    if not row:
        return jsonify({"error": f"Trip {trip_id} not found"}), 404
    return jsonify(row)


@app.route("/api/by-hour")
def by_hour():
    stats = load_stats()
    return jsonify(stats["by_hour"])


@app.route("/api/by-borough")
def by_borough():
    stats = load_stats()
    return jsonify(stats["by_borough"])


@app.route("/api/by-day")
def by_day():
    stats = load_stats()
    return jsonify(stats["by_day"])


@app.route("/api/by-payment")
def by_payment():
    stats = load_stats()
    return jsonify(stats["by_payment"])


@app.route("/api/top-zones")
def top_zones():
    stats = load_stats()
    return jsonify(stats["top_pickup_zones"])


@app.route("/api/daily-trend")
def daily_trend():
    stats = load_stats()
    return jsonify(stats["daily_trend"])


@app.route("/api/airport")
def airport():
    stats = load_stats()
    return jsonify(stats["airport_vs_nonairport"])


@app.route("/api/speed-distribution")
def speed_dist():
    stats = load_stats()
    return jsonify(stats["speed_distribution"])


@app.route("/api/dsa-benchmark")
def dsa_benchmark():
    """Run DSA benchmark and return results as JSON."""
    try:
        from algorithms import run_benchmark
        result = run_benchmark()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/boroughs")
def boroughs():
    rows = query("SELECT DISTINCT pu_borough FROM trips WHERE pu_borough IS NOT NULL ORDER BY pu_borough")
    return jsonify([r["pu_borough"] for r in rows])


@app.route("/api/zones")
def zones():
    borough = request.args.get("borough")
    if borough:
        rows = query(
            "SELECT DISTINCT pu_zone FROM trips WHERE pu_borough = ? ORDER BY pu_zone",
            (borough,)
        )
    else:
        rows = query("SELECT DISTINCT pu_zone FROM trips ORDER BY pu_zone LIMIT 50")
    return jsonify([r["pu_zone"] for r in rows])


@app.route("/")
def index():
    return jsonify({
        "name":    "NYC Taxi Urban Mobility API",
        "group":   "Group 10 – ALU Software Engineering",
        "version": "1.0",
        "endpoints": [
            "/api/summary",
            "/api/trips",
            "/api/trips/<id>",
            "/api/by-hour",
            "/api/by-borough",
            "/api/by-day",
            "/api/by-payment",
            "/api/top-zones",
            "/api/daily-trend",
            "/api/airport",
            "/api/speed-distribution",
            "/api/dsa-benchmark",
            "/api/boroughs",
            "/api/data-quality",
        ]
    })


if __name__ == "__main__":
    print("NYC Taxi API  –  http://localhost:5000")
    print("Group 10: Gabriel Mugisha · Olivier Dusabamahoro · James Kanneh")
    app.run(debug=True, port=5000)
