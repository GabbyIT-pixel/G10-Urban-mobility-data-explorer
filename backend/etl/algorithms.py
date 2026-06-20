"""
Custom algorithm and data structure implementations.
"""

import time
import sqlite3
import os
import copy

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "database", "nyc_taxi.db")


# ══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 1 — QuickSort
# Sorts list of dicts by a numeric key in descending order.
#
# Pseudo-code:
#   quicksort(arr, key, lo, hi):
#     if lo < hi:
#       p = partition(arr, key, lo, hi)
#       quicksort(arr, key, lo, p-1)
#       quicksort(arr, key, p+1, hi)
#
# Time:  O(n log n) average  |  O(n²) worst case
# Space: O(log n) call stack
# ══════════════════════════════════════════════════════════════════════════════

def _partition(arr, key, lo, hi):
    pivot = arr[hi][key]
    i     = lo - 1
    for j in range(lo, hi):
        if arr[j][key] >= pivot:       # descending: keep larger values left
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i+1], arr[hi] = arr[hi], arr[i+1]
    return i + 1


def quicksort(arr, key, lo=None, hi=None):
    """Sort list of dicts by key descending using manual QuickSort."""
    if lo is None: lo = 0
    if hi is None: hi = len(arr) - 1
    if lo < hi:
        p = _partition(arr, key, lo, hi)
        quicksort(arr, key, lo, p - 1)
        quicksort(arr, key, p + 1, hi)
    return arr


# ══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 2 — Min-Heap for Top-K
# Finds top-K busiest zones using a min-heap of size K.
# More efficient than sorting all zones when K << N.
#
# Pseudo-code:
#   for each (zone, count):
#     if heap.size < K:
#       heap.push(count, zone)
#     elif count > heap.min():
#       heap.pop()
#       heap.push(count, zone)
#
# Time:  O(n log k)   |  Space: O(k)
# ══════════════════════════════════════════════════════════════════════════════

class MinHeap:
    """Manual min-heap storing (count, zone) tuples."""

    def __init__(self):
        self._h = []

    def size(self):           return len(self._h)
    def peek(self):           return self._h[0] if self._h else None
    def _parent(self, i):     return (i - 1) // 2
    def _left(self, i):       return 2 * i + 1
    def _right(self, i):      return 2 * i + 2

    def push(self, item):
        self._h.append(item)
        self._up(len(self._h) - 1)

    def pop(self):
        if not self._h: return None
        self._h[0], self._h[-1] = self._h[-1], self._h[0]
        val = self._h.pop()
        if self._h: self._down(0)
        return val

    def _up(self, i):
        while i > 0:
            p = self._parent(i)
            if self._h[p][0] > self._h[i][0]:
                self._h[p], self._h[i] = self._h[i], self._h[p]
                i = p
            else:
                break

    def _down(self, i):
        n = len(self._h)
        while True:
            s = i
            l, r = self._left(i), self._right(i)
            if l < n and self._h[l][0] < self._h[s][0]: s = l
            if r < n and self._h[r][0] < self._h[s][0]: s = r
            if s != i:
                self._h[i], self._h[s] = self._h[s], self._h[i]
                i = s
            else:
                break

    def to_sorted_list(self):
        """Extract all items in descending order."""
        result = []
        tmp    = MinHeap()
        tmp._h = list(self._h)
        while tmp.size():
            result.append(tmp.pop())
        # reverse without built-in
        n = len(result)
        for i in range(n // 2):
            result[i], result[n-1-i] = result[n-1-i], result[i]
        return result


def top_k_zones(zone_counts, k=10):
    """Return top-K (zone, count) pairs using MinHeap."""
    heap = MinHeap()
    for zone, count in zone_counts.items():
        if heap.size() < k:
            heap.push((count, zone))
        elif count > heap.peek()[0]:
            heap.pop()
            heap.push((count, zone))
    return [(z, c) for c, z in heap.to_sorted_list()]


# ══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 3 — Manual HashMap (separate chaining)
# Count trips per borough without using Counter or dict.get shortcuts.
#
# Time:  O(n) average  |  Space: O(k) unique keys
# ══════════════════════════════════════════════════════════════════════════════

class HashMap:
    """Manual hash map with separate chaining for collision resolution."""

    def __init__(self, size=64):
        self._size    = size
        self._buckets = [[] for _ in range(size)]

    def _hash(self, key):
        h = 0
        for ch in str(key):
            h = (h * 31 + ord(ch)) % self._size
        return h

    def increment(self, key, amount=1):
        idx = self._hash(key)
        for i, (k, v) in enumerate(self._buckets[idx]):
            if k == key:
                self._buckets[idx][i] = (k, v + amount)
                return
        self._buckets[idx].append((key, amount))

    def get(self, key):
        for k, v in self._buckets[self._hash(key)]:
            if k == key: return v
        return 0

    def items(self):
        out = []
        for bucket in self._buckets:
            out.extend(bucket)
        return out


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark():
    print("=" * 60)
    print("NYC Taxi DSA Benchmark  –  Group 10")
    print("=" * 60)

    conn = sqlite3.connect(DB)
    cur  = conn.cursor()

    trips = [{"fare_amount": r[0], "trip_distance": r[1], "pu_borough": r[2]}
             for r in cur.execute(
                 "SELECT fare_amount, trip_distance, pu_borough FROM trips LIMIT 2000"
             ).fetchall()]

    zone_rows = cur.execute(
        "SELECT pu_zone, COUNT(*) FROM trips GROUP BY pu_zone"
    ).fetchall()
    zone_counts = {r[0]: r[1] for r in zone_rows if r[0]}
    conn.close()

    print(f"\nDataset: {len(trips)} trips  |  {len(zone_counts)} zones\n")

    # ── QuickSort ──────────────────────────────────────────────────────────────
    t1 = copy.deepcopy(trips)
    t2 = copy.deepcopy(trips)

    s = time.perf_counter()
    quicksort(t1, "fare_amount")
    qs_ms = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    t2.sort(key=lambda x: x["fare_amount"], reverse=True)
    py_ms = (time.perf_counter() - s) * 1000

    print("--- QuickSort vs Python sort() ---")
    print(f"  Manual QuickSort : {qs_ms:.3f} ms")
    print(f"  Python sort()    : {py_ms:.3f} ms")
    print(f"  Top fare match   : {t1[0]['fare_amount'] == t2[0]['fare_amount']}")

    # ── Top-K Heap ─────────────────────────────────────────────────────────────
    s = time.perf_counter()
    top10_heap = top_k_zones(zone_counts, k=10)
    heap_ms = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    top10_sort = sorted(zone_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    sort_ms = (time.perf_counter() - s) * 1000

    print("\n--- Top-10 Zones: Min-Heap vs sorted() ---")
    print(f"  Manual MinHeap   : {heap_ms:.3f} ms  O(n log k)")
    print(f"  Python sorted()  : {sort_ms:.3f} ms  O(n log n)")
    print(f"  Top zone (heap)  : {top10_heap[0][0]} — {top10_heap[0][1]} trips")

    # ── HashMap ────────────────────────────────────────────────────────────────
    s = time.perf_counter()
    hmap = HashMap()
    for t in trips:
        hmap.increment(t["pu_borough"] or "Unknown")
    hmap_ms = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    d = {}
    for t in trips:
        k = t["pu_borough"] or "Unknown"
        d[k] = d.get(k, 0) + 1
    dict_ms = (time.perf_counter() - s) * 1000

    print("\n--- Borough Count: HashMap vs dict ---")
    print(f"  Manual HashMap   : {hmap_ms:.3f} ms")
    print(f"  Python dict      : {dict_ms:.3f} ms")
    print(f"  Results match    : {sorted(hmap.items()) == sorted(d.items())}")

    print("\n--- Top 10 Pickup Zones ---")
    for i, (zone, count) in enumerate(top10_heap, 1):
        print(f"  {i:2}. {zone:<40} {count:,} trips")

    print("""
--- Complexity Summary ---
  QuickSort     : O(n log n) avg · O(n²) worst · O(log n) space
  MinHeap Top-K : O(n log k) time · O(k) space  — faster when k << n
  HashMap       : O(n) time  · O(k) space
""")
    return {
        "quicksort_ms":   round(qs_ms, 3),
        "python_sort_ms": round(py_ms, 3),
        "heap_ms":        round(heap_ms, 3),
        "sorted_ms":      round(sort_ms, 3),
        "hashmap_ms":     round(hmap_ms, 3),
        "dict_ms":        round(dict_ms, 3),
        "top_zones":      [{"zone": z, "trips": c} for z, c in top10_heap],
    }


if __name__ == "__main__":
    run_benchmark()
