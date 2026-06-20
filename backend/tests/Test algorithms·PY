"""
Unit tests for the custom QuickSort, MinHeap, and HashMap implementations.

Run with:  python backend/tests/test_algorithms.py


"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "etl"))

from algorithms import quicksort, MinHeap, top_k_zones, HashMap


def test_quicksort_sorts_descending():
    data = [{"fare_amount": v} for v in [5, 2, 9, 1, 7, 3]]
    quicksort(data, "fare_amount")
    result = [d["fare_amount"] for d in data]
    assert result == [9, 7, 5, 3, 2, 1]
    print(" test_quicksort_sorts_descending PASSED")


def test_quicksort_handles_empty_list():
    data = []
    quicksort(data, "fare_amount")
    assert data == []
    print(" test_quicksort_handles_empty_list PASSED")


def test_quicksort_handles_single_element():
    data = [{"fare_amount": 5}]
    quicksort(data, "fare_amount")
    assert data == [{"fare_amount": 5}]
    print(" test_quicksort_handles_single_element PASSED")


def test_quicksort_handles_duplicates():
    data = [{"fare_amount": v} for v in [5, 5, 5, 1, 1]]
    quicksort(data, "fare_amount")
    result = [d["fare_amount"] for d in data]
    assert result == [5, 5, 5, 1, 1]
    print(" test_quicksort_handles_duplicates PASSED")


def test_quicksort_matches_builtin_sort():
    random.seed(1)
    values = [random.randint(0, 1000) for _ in range(200)]
    data = [{"fare_amount": v} for v in values]

    quicksort(data, "fare_amount")
    manual_result = [d["fare_amount"] for d in data]

    builtin_result = sorted(values, reverse=True)
    assert manual_result == builtin_result
    print(" test_quicksort_matches_builtin_sort PASSED (200 random values)")


def test_minheap_push_pop_order():
    heap = MinHeap()
    for v in [5, 1, 8, 3, 9, 2]:
        heap.push((v, f"item-{v}"))

    result = []
    while heap.size() > 0:
        result.append(heap.pop()[0])

    # Pop should always return ascending order (min first)
    assert result == sorted([5, 1, 8, 3, 9, 2])
    print(" test_minheap_push_pop_order PASSED")


def test_top_k_zones_returns_correct_count():
    zone_counts = {f"zone_{i}": i for i in range(50)}
    result = top_k_zones(zone_counts, k=10)
    assert len(result) == 10
    print(" test_top_k_zones_returns_correct_count PASSED")


def test_top_k_zones_returns_highest_values():
    zone_counts = {"A": 100, "B": 50, "C": 200, "D": 10, "E": 150}
    result = top_k_zones(zone_counts, k=3)
    top_zones = set(z for z, c in result)
    assert top_zones == {"C", "E", "A"}   # top 3 by count: C=200, E=150, A=100
    print(" test_top_k_zones_returns_highest_values PASSED")


def test_top_k_zones_matches_builtin_sort():
    random.seed(2)
    zone_counts = {f"zone_{i}": random.randint(0, 1000) for i in range(100)}

    manual_top10  = sorted([z for z, c in top_k_zones(zone_counts, k=10)],
                            key=lambda z: zone_counts[z], reverse=True)
    builtin_top10 = sorted(zone_counts, key=zone_counts.get, reverse=True)[:10]

    assert set(manual_top10) == set(builtin_top10)
    print(" test_top_k_zones_matches_builtin_sort PASSED (100 random zones)")


def test_hashmap_increment_and_get():
    hmap = HashMap()
    hmap.increment("Manhattan")
    hmap.increment("Manhattan")
    hmap.increment("Brooklyn")

    assert hmap.get("Manhattan") == 2
    assert hmap.get("Brooklyn")  == 1
    assert hmap.get("Queens")    == 0   # never inserted
    print(" test_hashmap_increment_and_get PASSED")


def test_hashmap_matches_dict_behavior():
    random.seed(3)
    boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
    sample   = [random.choice(boroughs) for _ in range(500)]

    hmap = HashMap()
    for b in sample:
        hmap.increment(b)

    builtin = {}
    for b in sample:
        builtin[b] = builtin.get(b, 0) + 1

    hmap_dict = dict(hmap.items())
    assert hmap_dict == builtin
    print(" test_hashmap_matches_dict_behavior PASSED (500 random inserts)")


def run_all_tests():
    print("=" * 60)
    print("Running DSA Algorithm Unit Tests — Group 10")
    print("=" * 60)
    test_quicksort_sorts_descending()
    test_quicksort_handles_empty_list()
    test_quicksort_handles_single_element()
    test_quicksort_handles_duplicates()
    test_quicksort_matches_builtin_sort()
    test_minheap_push_pop_order()
    test_top_k_zones_returns_correct_count()
    test_top_k_zones_returns_highest_values()
    test_top_k_zones_matches_builtin_sort()
    test_hashmap_increment_and_get()
    test_hashmap_matches_dict_behavior()
    print("=" * 60)
    print("All 11 tests completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
