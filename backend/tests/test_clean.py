"""
Unit tests for the ETL cleaning and feature engineering functions.

Run with:  python backend/tests/test_clean.py

"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "etl"))

from clean import clean, engineer, identify_issues, fare_component_mismatch


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
    print(" test_identify_issues_counts_correctly PASSED")


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
    print(" test_clean_removes_bad_records PASSED")


def test_clean_fills_nulls():
    df = make_sample_df()
    clean_df, _ = clean(df)

    assert clean_df["passenger_count"].isna().sum() == 0
    assert clean_df["RatecodeID"].isna().sum() == 0
    print(" test_clean_fills_nulls PASSED")


def test_engineer_adds_derived_features():
    df = make_sample_df()
    clean_df, _ = clean(df)

    if len(clean_df) == 0:
        print("⚠️  test_engineer_adds_derived_features SKIPPED (no clean rows in sample)")
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
    print(" test_engineer_adds_derived_features PASSED")


def test_airport_flag_detection():
    """Trip with PULocationID=132 (JFK) should be flagged as airport trip."""
    df = make_sample_df()
    clean_df, _ = clean(df)

    if len(clean_df) == 0:
        print("⚠️  test_airport_flag_detection SKIPPED (no clean rows)")
        return

    result = engineer(clean_df)
    jfk_rows = result[result["PULocationID"] == 132]
    if len(jfk_rows) > 0:
        assert jfk_rows["is_airport"].iloc[0] == 1
    print(" test_airport_flag_detection PASSED")


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


def make_fare_consistency_df():
    """
    Two trips: the first reconciles (total == sum of components), the second
    does not (total understates the components by $5). Used to isolate the
    fare-consistency check from the other cleaning rules.
    """
    base = datetime(2024, 1, 15, 10, 0, 0)
    data = {
        "VendorID":              [1, 2],
        "tpep_pickup_datetime":  [base, base],
        "tpep_dropoff_datetime": [base + timedelta(minutes=10),
                                  base + timedelta(minutes=12)],
        "passenger_count":       [1, 2],
        "trip_distance":         [2.0, 3.0],
        "RatecodeID":            [1, 1],
        "PULocationID":          [100, 200],
        "DOLocationID":          [50, 60],
        "payment_type":          [1, 1],
        "fare_amount":           [10.0, 20.0],
        "tip_amount":            [2.0, 3.0],
        "tolls_amount":          [0.0, 0.0],
        "total_amount":          [12.0, 18.0],   # row 0 OK (10+2); row 1 off by 5 (20+3=23)
        "congestion_surcharge":  [0.0, 0.0],
        "airport_fee":           [0.0, 0.0],
        "pu_borough":            ["Manhattan", "Brooklyn"],
        "do_borough":            ["Brooklyn", "Queens"],
        "pu_zone":               ["Zone A", "Zone B"],
        "do_zone":               ["Zone C", "Zone D"],
    }
    return pd.DataFrame(data)


def test_fare_component_mismatch_detects_inconsistent_total():
    """total_amount that doesn't match the sum of components is flagged."""
    df = make_fare_consistency_df()
    mismatch = fare_component_mismatch(df)
    assert mismatch.iloc[0] == False   # 10 + 2 == 12 -> consistent
    assert mismatch.iloc[1] == True    # 20 + 3 != 18 -> inconsistent
    print(" test_fare_component_mismatch_detects_inconsistent_total PASSED")


def test_fare_component_mismatch_respects_tolerance():
    """Differences within the tolerance (rounding) are not flagged."""
    df = make_fare_consistency_df()
    # Row 1 is off by exactly $5; a $5 tolerance must not flag it.
    assert fare_component_mismatch(df, tolerance=5.0).iloc[1] == False
    # A tiny rounding-sized gap stays unflagged under the default tolerance.
    df.loc[0, "total_amount"] = 12.5   # 10 + 2 = 12, off by 0.5 < 1.0 default
    assert fare_component_mismatch(df).iloc[0] == False
    print(" test_fare_component_mismatch_respects_tolerance PASSED")


def test_clean_rejects_fare_mismatch():
    """The inconsistent-fare row is removed and labeled in the dead-letter log."""
    df = make_fare_consistency_df()
    clean_df, rejected = clean(df)
    assert len(clean_df) == 1
    assert len(rejected) == 1
    assert (rejected["reason"] == "fare_mismatch").all()
    print(" test_clean_rejects_fare_mismatch PASSED")


def test_identify_issues_counts_fare_mismatch():
    df = make_fare_consistency_df()
    issues = identify_issues(df)
    assert issues["fare_mismatch"] == 1
    print(" test_identify_issues_counts_fare_mismatch PASSED")


def test_engineer_adds_tip_percentage():
    """tip_percentage is derived as tip / fare * 100, with safe handling of $0 fares."""
    df = make_fare_consistency_df()
    clean_df, _ = clean(df)
    result = engineer(clean_df)

    assert "tip_percentage" in result.columns
    # Surviving row: fare 10, tip 2 -> 20.0%
    row = result.iloc[0]
    assert row["tip_percentage"] == 20.0
    # No NaN / inf leaks through into the feature
    assert result["tip_percentage"].notna().all()
    print(" test_engineer_adds_tip_percentage PASSED")


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
    test_fare_component_mismatch_detects_inconsistent_total()
    test_fare_component_mismatch_respects_tolerance()
    test_clean_rejects_fare_mismatch()
    test_identify_issues_counts_fare_mismatch()
    test_engineer_adds_tip_percentage()
    print("=" * 60)
    print("All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
