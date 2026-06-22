"""
Data cleaning, feature engineering, and database loading.

"""

import pandas as pd
import numpy as np
import sqlite3
import json
import os

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW     = os.path.join(BASE, "data", "raw")
PROC    = os.path.join(BASE, "data", "processed")
LOGS    = os.path.join(BASE, "data", "logs")
DB      = os.path.join(BASE, "database", "nyc_taxi.db")

for d in [PROC, LOGS, os.path.dirname(DB)]:
    os.makedirs(d, exist_ok=True)


# ── 1. LOAD ────────────────────────────────────────────────────────────────────
def find_trip_data_file():
    """
    Locate the trip data file in data/raw/ without hardcoding a specific
    filename, year, or month. TLC trip files always start with a known
    prefix (yellow_tripdata, green_tripdata, fhv_tripdata) and end in
    either .csv or .parquet — we search for any file matching that pattern
    so the pipeline works regardless of which month/year/format is supplied.
    """
    import glob

    patterns = ["*tripdata*.csv", "*tripdata*.parquet"]
    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(os.path.join(RAW, pattern)))

    if not candidates:
        raise FileNotFoundError(
            f"No trip data file found in {RAW}. "
            f"Expected a file matching '*tripdata*.csv' or '*tripdata*.parquet' "
            f"(e.g. yellow_tripdata_2019-01.csv)."
        )

    if len(candidates) > 1:
        print(f"      Warning: multiple trip data files found, using the first: {candidates}")

    return sorted(candidates)[0]


def load_raw():
    print("[1/6] Loading raw data...")

    trip_file = find_trip_data_file()
    is_csv    = trip_file.lower().endswith(".csv")

    print(f"      Source: {trip_file} ({'CSV' if is_csv else 'Parquet'})")

    if is_csv:
        df = pd.read_csv(
            trip_file,
            parse_dates=["tpep_pickup_datetime", "tpep_dropoff_datetime"],
            dtype={
                "VendorID": "Int64", "passenger_count": "Int64",
                "RatecodeID": "Int64", "PULocationID": "Int64",
                "DOLocationID": "Int64", "payment_type": "Int64",
            },
        )
    else:
        df = pd.read_parquet(trip_file)

    zones = pd.read_csv(os.path.join(RAW, "taxi_zone_lookup.csv"))
    print(f"      Raw records : {len(df):,}")
    print(f"      Raw columns : {list(df.columns)}")

    # Real TLC files vary by year/month (Airport_fee/airport_fee capitalization
    # changes, and some files omit it entirely depending on when congestion/
    # airport surcharges were introduced). Normalize so the rest of the
    # pipeline always sees the same lowercase keys regardless of source file.
    rename_map = {}
    for col in df.columns:
        if col.lower() == "airport_fee":
            rename_map[col] = "airport_fee"
        elif col.lower() == "congestion_surcharge":
            rename_map[col] = "congestion_surcharge"
    df = df.rename(columns=rename_map)

    # Some files omit airport_fee/congestion_surcharge entirely, or include
    # the column with all-null values (the surcharge didn't exist yet for
    # that reporting period). Default both to 0 so downstream code never
    # KeyErrors or carries NaN into fare calculations.
    for required_col in ["airport_fee", "congestion_surcharge"]:
        if required_col not in df.columns:
            print(f"      Note: '{required_col}' not present in this file — defaulting to 0")
            df[required_col] = 0.0
        else:
            df[required_col] = df[required_col].fillna(0.0)

    df = df.merge(zones.rename(columns={
        "LocationID":"PULocationID","Borough":"pu_borough",
        "Zone":"pu_zone","service_zone":"pu_service_zone"
    }), on="PULocationID", how="left")

    df = df.merge(zones.rename(columns={
        "LocationID":"DOLocationID","Borough":"do_borough",
        "Zone":"do_zone","service_zone":"do_service_zone"
    }), on="DOLocationID", how="left")

    return df, zones


# ── 2. IDENTIFY ISSUES ────────────────────────────────────────────────────────
def get_expected_month_window(df):
    """
    Determine the valid pickup-date window from the data itself rather than
    hardcoding a specific month/year. We find the *mode* of (year, month)
    across all pickups — the single most common reporting month in the
    file — and treat that exact calendar month as the only valid window.
    Any record outside it (even by one day) is rejected as a temporal
    anomaly, so the dashboard never displays a date range wider than the
    file's actual reporting month.
    """
    year_month   = df["tpep_pickup_datetime"].dt.to_period("M")
    dominant     = year_month.mode().iloc[0]
    window_start = dominant.start_time
    window_end   = dominant.end_time.normalize() + pd.Timedelta(days=1)
    return window_start, window_end


def fare_component_mismatch(df, tolerance=1.0):
    """
    Identify trips whose total_amount does not reconcile with the sum of its
    component charges (fare + tip + tolls + congestion surcharge + airport fee)
    beyond a small tolerance.

    Real TLC files contain rows where total_amount was recorded independently
    of the line items and the two disagree (meter glitches, manual overrides,
    refund adjustments). The existing pipeline checks each charge in isolation
    but never verifies they add up, so these inconsistent fares slip through and
    distort revenue totals on the dashboard. The tolerance (default $1.00)
    absorbs ordinary rounding without flagging genuine, well-formed trips.
    """
    components = (
        df["fare_amount"].fillna(0)
        + df["extra"].fillna(0)
        + df["mta_tax"].fillna(0)
        + df["tip_amount"].fillna(0)
        + df["tolls_amount"].fillna(0)
        + df["improvement_surcharge"].fillna(0)
        + df["congestion_surcharge"].fillna(0)
        + df["airport_fee"].fillna(0)
    )
    return (df["total_amount"].fillna(0) - components).abs() > tolerance


def identify_issues(df):
    window_start, window_end = get_expected_month_window(df)
    return {
        "total_raw"           : int(len(df)),
        "null_passenger"      : int(df["passenger_count"].isna().sum()),
        "zero_passenger"      : int((df["passenger_count"]==0).sum()),
        "negative_fare"       : int((df["fare_amount"]<0).sum()),
        "zero_distance"       : int((df["trip_distance"]<=0).sum()),
        "future_pickup"       : int((df["tpep_pickup_datetime"]>=window_end).sum()),
        "past_pickup"         : int((df["tpep_pickup_datetime"]<window_start).sum()),
        "dropoff_before_pickup": int((df["tpep_dropoff_datetime"]<=df["tpep_pickup_datetime"]).sum()),
        "extreme_fare"        : int((df["fare_amount"]>500).sum()),
        "extreme_distance"    : int((df["trip_distance"]>100).sum()),
        "fare_mismatch"       : int(fare_component_mismatch(df).sum()),
    }


# ── 3. CLEAN ──────────────────────────────────────────────────────────────────
def clean(df):
    print("[2/6] Cleaning data...")
    original = len(df)
    mask     = pd.Series(False, index=df.index)
    reasons  = pd.Series("", index=df.index)

    window_start, window_end = get_expected_month_window(df)
    print(f"      Reporting month detected: {window_start.strftime('%Y-%m')} "
          f"(valid window {window_start.date()} to {window_end.date()})")

    def flag(condition, reason):
        nonlocal mask, reasons
        new = condition & ~mask
        mask   |= condition
        reasons[new] = reason

    flag(df["tpep_pickup_datetime"] >= window_end,  "future_date")
    flag(df["tpep_pickup_datetime"] <  window_start, "past_date")
    flag(df["tpep_dropoff_datetime"] <= df["tpep_pickup_datetime"],  "bad_duration")
    flag(df["fare_amount"] < 0,       "negative_fare")
    flag(df["trip_distance"] <= 0,    "zero_distance")
    flag(df["passenger_count"] == 0,  "zero_passengers")
    flag(df["fare_amount"] > 500,     "extreme_fare")
    flag(df["trip_distance"] > 100,   "extreme_distance")
    flag(fare_component_mismatch(df), "fare_mismatch")

    rejected          = df[mask].copy()
    rejected["reason"]= reasons[mask]
    clean_df          = df[~mask].copy()

    # Fill remaining nulls
    clean_df["passenger_count"]      = clean_df["passenger_count"].fillna(1)
    clean_df["RatecodeID"]           = clean_df["RatecodeID"].fillna(1)
    clean_df["congestion_surcharge"] = clean_df["congestion_surcharge"].fillna(0)
    clean_df["airport_fee"]          = clean_df["airport_fee"].fillna(0)
    clean_df["pu_borough"]           = clean_df["pu_borough"].fillna("Unknown")
    clean_df["do_borough"]           = clean_df["do_borough"].fillna("Unknown")
    clean_df["pu_zone"]              = clean_df["pu_zone"].fillna("Unknown")
    clean_df["do_zone"]              = clean_df["do_zone"].fillna("Unknown")

    print(f"      Clean    : {len(clean_df):,}")
    print(f"      Rejected : {len(rejected):,}  ({len(rejected)/original*100:.1f}%)")
    return clean_df, rejected


# ── 4. FEATURE ENGINEERING ────────────────────────────────────────────────────
def engineer(df):
    print("[3/6] Engineering features...")
    AIRPORTS = {1, 132, 138}   # EWR, JFK, LaGuardia

    # Derived feature 1: trip duration in minutes
    df["trip_duration_min"] = (
        (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"])
        .dt.total_seconds() / 60
    ).round(2)

    # Derived feature 2: average speed mph
    df["speed_mph"] = (
        df["trip_distance"] / (df["trip_duration_min"] / 60)
    ).replace([np.inf, -np.inf], 0).round(2)

    # Derived feature 3: fare efficiency ($ per mile)
    df["fare_per_mile"] = (
        df["fare_amount"] / df["trip_distance"]
    ).replace([np.inf, -np.inf], 0).round(2)

    # Derived feature 4: tip as a percentage of the base fare. Computed against
    # fare_amount (not total_amount) so tolls/surcharges don't dilute the
    # signal — this is the number riders actually think of as "the tip %".
    # Cash trips report tip_amount = 0 by TLC convention, which correctly shows
    # as a 0% tip rather than a missing value.
    df["tip_percentage"] = (
        df["tip_amount"] / df["fare_amount"] * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    # Time features
    df["hour"]        = df["tpep_pickup_datetime"].dt.hour
    df["day_name"]    = df["tpep_pickup_datetime"].dt.day_name()
    df["pickup_date"] = df["tpep_pickup_datetime"].dt.date.astype(str)

    # Airport flag
    df["is_airport"]  = (
        df["PULocationID"].isin(AIRPORTS) | df["DOLocationID"].isin(AIRPORTS)
    ).astype(int)

    # Remove implausible speeds
    df = df[df["speed_mph"] <= 100].copy()
    print(f"      Records after speed filter : {len(df):,}")
    return df


# ── 5. SAVE TO DB ─────────────────────────────────────────────────────────────
def save_db(df, zones):
    print("[4/6] Saving to database...")
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()

    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS taxi_zones (
        location_id  INTEGER PRIMARY KEY,
        borough      TEXT NOT NULL,
        zone         TEXT NOT NULL,
        service_zone TEXT
    );

    CREATE TABLE IF NOT EXISTS trips (
        trip_id               INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id             INTEGER,
        pickup_datetime       TEXT    NOT NULL,
        dropoff_datetime      TEXT    NOT NULL,
        passenger_count       INTEGER,
        trip_distance         REAL    NOT NULL,
        pu_location_id        INTEGER,
        do_location_id        INTEGER,
        rate_code_id          INTEGER,
        payment_type          INTEGER,
        fare_amount           REAL    NOT NULL,
        tip_amount            REAL    DEFAULT 0,
        tolls_amount          REAL    DEFAULT 0,
        total_amount          REAL    NOT NULL,
        congestion_surcharge  REAL    DEFAULT 0,
        airport_fee           REAL    DEFAULT 0,
        trip_duration_min     REAL,
        speed_mph             REAL,
        fare_per_mile         REAL,
        tip_percentage        REAL,
        hour                  INTEGER,
        day_name              TEXT,
        pickup_date           TEXT,
        is_airport            INTEGER DEFAULT 0,
        pu_borough            TEXT,
        do_borough            TEXT,
        pu_zone                TEXT,
        do_zone               TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_date    ON trips(pickup_date);
    CREATE INDEX IF NOT EXISTS idx_borough ON trips(pu_borough);
    CREATE INDEX IF NOT EXISTS idx_hour    ON trips(hour);
    CREATE INDEX IF NOT EXISTS idx_payment ON trips(payment_type);
    CREATE INDEX IF NOT EXISTS idx_airport ON trips(is_airport);
    """)

    # Insert zones — fill nulls (e.g. LocationID 264/265 "Unknown"/"N/A" rows
    # in the official TLC lookup table have no borough/zone/service_zone)
    zones_clean = zones.rename(columns={
        "LocationID":"location_id","Borough":"borough",
        "Zone":"zone","service_zone":"service_zone"
    }).copy()
    zones_clean["borough"]      = zones_clean["borough"].fillna("Unknown")
    zones_clean["zone"]         = zones_clean["zone"].fillna("Unknown")
    zones_clean["service_zone"] = zones_clean["service_zone"].fillna("N/A")

    cur.execute("DELETE FROM taxi_zones")
    zones_clean.to_sql("taxi_zones", conn, if_exists="append", index=False)

    # Insert trips
    cols_map = {
        "VendorID":"vendor_id",
        "tpep_pickup_datetime":"pickup_datetime",
        "tpep_dropoff_datetime":"dropoff_datetime",
        "passenger_count":"passenger_count",
        "trip_distance":"trip_distance",
        "PULocationID":"pu_location_id",
        "DOLocationID":"do_location_id",
        "RatecodeID":"rate_code_id",
        "payment_type":"payment_type",
        "fare_amount":"fare_amount",
        "tip_amount":"tip_amount",
        "tolls_amount":"tolls_amount",
        "total_amount":"total_amount",
        "congestion_surcharge":"congestion_surcharge",
        "airport_fee":"airport_fee",
        "trip_duration_min":"trip_duration_min",
        "speed_mph":"speed_mph",
        "fare_per_mile":"fare_per_mile",
        "tip_percentage":"tip_percentage",
        "hour":"hour",
        "day_name":"day_name",
        "pickup_date":"pickup_date",
        "is_airport":"is_airport",
        "pu_borough":"pu_borough",
        "do_borough":"do_borough",
        "pu_zone":"pu_zone",
        "do_zone":"do_zone",
    }
    ins = df[list(cols_map.keys())].rename(columns=cols_map).copy()
    ins["pickup_datetime"]  = ins["pickup_datetime"].astype(str)
    ins["dropoff_datetime"] = ins["dropoff_datetime"].astype(str)

    cur.execute("DELETE FROM trips")
    ins.to_sql("trips", conn, if_exists="append", index=False)
    conn.commit()

    n = cur.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    print(f"      Inserted {n:,} trips")
    conn.close()


# ── 6. SAVE STATS ─────────────────────────────────────────────────────────────
def save_stats(df, issues):
    print("[5/6] Computing dashboard stats...")

    payment_labels = {1:"Credit Card",2:"Cash",3:"No Charge",4:"Dispute",5:"Unknown"}

    stats = {
        "summary": {
            "total_trips"   : int(len(df)),
            "total_revenue" : round(float(df["total_amount"].sum()), 2),
            "avg_fare"      : round(float(df["fare_amount"].mean()), 2),
            "avg_distance"  : round(float(df["trip_distance"].mean()), 2),
            "avg_duration"  : round(float(df["trip_duration_min"].mean()), 2),
            "avg_speed"     : round(float(df["speed_mph"].mean()), 2),
            "airport_trips" : int(df["is_airport"].sum()),
            "avg_tip"       : round(float(df["tip_amount"].mean()), 2),
            "avg_tip_pct"   : round(float(df["tip_percentage"].mean()), 2),
        },
        "data_quality": issues,
        "by_borough": df.groupby("pu_borough").agg(
            trips=("fare_amount","count"),
            revenue=("total_amount","sum"),
            avg_fare=("fare_amount","mean"),
            avg_distance=("trip_distance","mean")
        ).round(2).reset_index().rename(columns={"pu_borough":"borough"}).to_dict("records"),

        "by_hour": df.groupby("hour").agg(
            trips=("fare_amount","count"),
            avg_fare=("fare_amount","mean"),
            avg_duration=("trip_duration_min","mean")
        ).round(2).reset_index().to_dict("records"),

        "by_day": df.groupby("day_name").agg(
            trips=("fare_amount","count"),
            avg_fare=("fare_amount","mean"),
            revenue=("total_amount","sum")
        ).round(2).reset_index().to_dict("records"),

        "by_payment": [
            {
                "payment_type": int(pt),
                "label": payment_labels.get(int(pt), "Other"),
                "trips": int(grp["fare_amount"].count()),
                "avg_tip": round(float(grp["tip_amount"].mean()), 2),
                "avg_fare": round(float(grp["fare_amount"].mean()), 2),
            }
            for pt, grp in df.groupby("payment_type")
        ],

        "top_pickup_zones": df.groupby("pu_zone")["fare_amount"].count()
            .sort_values(ascending=False).head(10)
            .reset_index().rename(columns={"pu_zone":"zone","fare_amount":"trips"})
            .to_dict("records"),

        "daily_trend": df.groupby("pickup_date").agg(
            trips=("fare_amount","count"),
            revenue=("total_amount","sum")
        ).round(2).reset_index().to_dict("records"),

        "airport_vs_nonairport": {
            "airport":     round(float(df[df["is_airport"]==1]["fare_amount"].mean()), 2),
            "non_airport": round(float(df[df["is_airport"]==0]["fare_amount"].mean()), 2),
        },

        "speed_distribution": {
            "0-10":  int(((df["speed_mph"]>=0)  & (df["speed_mph"]<10)).sum()),
            "10-20": int(((df["speed_mph"]>=10) & (df["speed_mph"]<20)).sum()),
            "20-30": int(((df["speed_mph"]>=20) & (df["speed_mph"]<30)).sum()),
            "30-40": int(((df["speed_mph"]>=30) & (df["speed_mph"]<40)).sum()),
            "40+":   int((df["speed_mph"]>=40).sum()),
        }
    }

    with open(os.path.join(PROC, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"      Stats saved → data/processed/stats.json")


def save_dead_letter(rejected):
    rejected.to_csv(os.path.join(LOGS, "dead_letter.csv"), index=False)
    summary = rejected["reason"].value_counts().to_dict()
    with open(os.path.join(LOGS, "rejection_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[6/6] Dead-letter: {len(rejected):,} records → data/logs/dead_letter.csv")
    print(f"      Reasons: {summary}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def run():
    print("=" * 60)
    print("NYC Taxi ETL Pipeline  –  Group 10")
    print("=" * 60)
    df, zones = load_raw()
    issues    = identify_issues(df)
    df, rej   = clean(df)
    df        = engineer(df)
    save_db(df, zones)
    save_stats(df, issues)
    save_dead_letter(rej)
    print("=" * 60)
    print(f"Done. {len(df):,} clean trips loaded into database.")
    print("=" * 60)

if __name__ == "__main__":
    run()
