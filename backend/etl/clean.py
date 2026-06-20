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
def load_raw():
    print("[1/6] Loading raw data...")
    df    = pd.read_parquet(os.path.join(RAW, "yellow_tripdata_2024-01.parquet"))
    zones = pd.read_csv(os.path.join(RAW, "taxi_zone_lookup.csv"))
    print(f"      Raw records : {len(df):,}")

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
def identify_issues(df):
    return {
        "total_raw"           : int(len(df)),
        "null_passenger"      : int(df["passenger_count"].isna().sum()),
        "zero_passenger"      : int((df["passenger_count"]==0).sum()),
        "negative_fare"       : int((df["fare_amount"]<0).sum()),
        "zero_distance"       : int((df["trip_distance"]<=0).sum()),
        "future_pickup"       : int((df["tpep_pickup_datetime"]>pd.Timestamp("2024-02-01")).sum()),
        "past_pickup"         : int((df["tpep_pickup_datetime"]<pd.Timestamp("2024-01-01")).sum()),
        "dropoff_before_pickup": int((df["tpep_dropoff_datetime"]<=df["tpep_pickup_datetime"]).sum()),
        "extreme_fare"        : int((df["fare_amount"]>500).sum()),
        "extreme_distance"    : int((df["trip_distance"]>100).sum()),
    }


# ── 3. CLEAN ──────────────────────────────────────────────────────────────────
def clean(df):
    print("[2/6] Cleaning data...")
    original = len(df)
    mask     = pd.Series(False, index=df.index)
    reasons  = pd.Series("", index=df.index)

    def flag(condition, reason):
        nonlocal mask, reasons
        new = condition & ~mask
        mask   |= condition
        reasons[new] = reason

    flag(df["tpep_pickup_datetime"] > pd.Timestamp("2024-02-01"), "future_date")
    flag(df["tpep_pickup_datetime"] < pd.Timestamp("2024-01-01"), "past_date")
    flag(df["tpep_dropoff_datetime"] <= df["tpep_pickup_datetime"],  "bad_duration")
    flag(df["fare_amount"] < 0,       "negative_fare")
    flag(df["trip_distance"] <= 0,    "zero_distance")
    flag(df["passenger_count"] == 0,  "zero_passengers")
    flag(df["fare_amount"] > 500,     "extreme_fare")
    flag(df["trip_distance"] > 100,   "extreme_distance")

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
        hour                  INTEGER,
        day_name              TEXT,
        pickup_date           TEXT,
        is_airport            INTEGER DEFAULT 0,
        pu_borough            TEXT,
        do_borough            TEXT,
        pu_zone               TEXT,
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
