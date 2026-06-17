"""
Unit tests for the ETL cleaning and feature engineering functions.

Run with: python backend/tests/test_clean.py

"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "etl"))

from clean import clean, engineer, identify_issues


def make_sample_df():
    """Create a small synthetic dataframe for testing."""
    base = datetime(2024, 1, 15, 10, 0, 0)
    data = {
        "VendorID":              [1, 1, 2, 1, 2, 1, 1],
        "tpep_pickup_datetime":  [
            base, base, base, base,
            datetime(2025, 6, 1),          # future date -> should be rejected
            base, base
        ],
        "tpep_dropoff_datetime": [
            base + timedelta(minutes=10),
            base + timedelta(minutes=15),
            base + timedelta(minutes=5),
            base - timedelta(minutes=5),   # dropoff before pickup -> rejected
            base + timedelta(minutes=10),
            base + timedelta(minutes=20),
            base + timedelta(minutes=8),
        ],
        "passenger_count": [1, 0, 2, 1, 1, None, 3],   # 0 passengers -> rejected
        "trip_distance":   [2.5, 3.0, 0, 1.5, 4.0, 2.0, 5.0],  # 0 distance -> rejected
        "RatecodeID":      [1, 1, 1, 1, 1, None, 2],
        "PULocationID":    [132, 45, 100, 138, 50, 1, 200],
        "DOLocationID":    [50, 60, 70, 80, 90, 100, 110],
        "payment_type":    [1, 2, 1, 1, 1, 2, 1],
        "fare_amount":     [10.0, 12.0, 8.0, -5.0, 600.0, 15.0, 20.0],  # negative & extreme
        "tip_amount":      [2.0, 0, 1.5, 0, 0, 3.0, 4.0],
        "tolls_amount":    [0, 0, 0, 0, 0, 0, 0],
        "total_amount":    [12.0, 12.0, 9.5, -5.0, 600.0, 18.0, 24.0],
        "congestion_surcharge": [0, 0, 0, 0, 0, None, 2.5],
        "airport_fee":     [0, 0, 0, 1.25, 0, None, 0],
        "pu_borough":      ["Manhattan","Brooklyn","Queens","Queens","Bronx","EWR","Staten Island"],
        "do_borough":      ["Brooklyn","Queens","Manhattan","Manhattan","Bronx","Manhattan","Queens"],
        "pu_zone":         ["Zone A","Zone B","Zone C","Zone D","Zone E","Zone F","Zone G"],
        "do_zone":         ["Zone H","Zone I","Zone J","Zone K","Zone L","Zone M","Zone N"],
    }
    return pd.DataFrame(data)


def test_identify_issues_counts_correctly():
    df = make_sample_df()
    issues = identify_issues(df)

    assert issues["total_raw"] == 7
    assert issues["zero_passenger"] == 1
    assert issues["zero_distance"] == 1
    assert issues["negative_fare"] == 1
    assert issues["extreme_fare"] == 1
    assert issues["future_pickup"] == 1
    assert issues["dropoff_before_pickup"] >= 1
    print("test_identify_issues_counts_correctly PASSED")


def test_clean_removes_bad_records():
    df = make_sample_df()
    clean_df, rejected = clean(df)

    # 7 total, several rows have multiple problems so rejected count >= 4
    assert len(rejected) >= 4
    assert len(clean_df) <= 3

    # No negative fares in clean data
    assert (clean_df["fare_amount"] >= 0).all()
    # No zero distances
    assert (clean_df["trip_distance"] > 0).all()
    # No zero passengers
    assert (clean_df["passenger_count"] != 0).all()
    print("test_clean_removes_bad_records PASSED")


def test_clean_fills_nulls():
    df = make_sample_df()
    clean_df, _ = clean(df)

    assert clean_df["passenger_count"].isna().sum() == 0
    assert clean_df["RatecodeID"].isna().sum() == 0
    print("test_clean_fills_nulls PASSED")


def test_engineer_adds_derived_features():
    df = make_sample_df()
    clean_df, _ = clean(df)

    if len(clean_df) == 0:
        print(" test_engineer_adds_derived_features SKIPPED (no clean rows in sample)")
        return

    result = engineer(clean_df)

    assert "trip_duration_min" in result.columns
    assert "speed_mph" in result.columns
    assert "fare_per_mile" in result.columns
    assert "is_airport" in result.columns
    assert "hour" in result.columns
    assert "day_name" in result.columns

    # Duration should be positive for all remaining rows
    assert (result["trip_duration_min"] > 0).all()
    print("test_engineer_adds_derived_features PASSED")


def test_airport_flag_detection():
    """Trip with PULocationID=132 (JFK) should be flagged as airport trip."""
    df = make_sample_df()
    clean_df, _ = clean(df)

    if len(clean_df) == 0:
        print(" test_airport_flag_detection SKIPPED (no clean rows)")
        return

    result = engineer(clean_df)
    jfk_rows = result[result["PULocationID"] == 132]
    if len(jfk_rows) > 0:
        assert jfk_rows["is_airport"].iloc[0] == 1
    print("test_airport_flag_detection PASSED")


def test_speed_filter_removes_impossible_speeds():
    """A trip covering 50 miles in 1 minute (3000 mph) should be filtered out."""
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        "VendorID": [1],
        "tpep_pickup_datetime": [base],
        "tpep_dropoff_datetime": [base + timedelta(minutes=1)],
        "passenger_count": [1],
        "trip_distance": [50.0],   # 50 miles in 1 minute = impossible
        "RatecodeID": [1],
        "PULocationID": [1],
        "DOLocationID": [2],
        "payment_type": [1],
        "fare_amount": [20.0],
        "tip_amount": [0],
        "tolls_amount": [0],
        "total_amount": [20.0],
        "congestion_surcharge": [0],
        "airport_fee": [0],
        "pu_borough": ["Manhattan"],
        "do_borough": ["Brooklyn"],
        "pu_zone": ["Zone A"],
        "do_zone": ["Zone B"],
    })

    result = engineer(df)
    assert len(result) == 0   # should be filtered by speed > 100mph check
    print(" test_speed_filter_removes_impossible_speeds PASSED")


def run_all_tests():
    print("=" * 60)
    print("Running ETL Unit Tests — Group 10")
    print("=" * 60)
    test_identify_issues_counts_correctly()
    test_clean_removes_bad_records()
    test_clean_fills_nulls()
    test_engineer_adds_derived_features()
    test_airport_flag_detection()
    test_speed_filter_removes_impossible_speeds()
    print("=" * 60)
    print("All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
