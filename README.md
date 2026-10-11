# key-management-demo

A key-value store that indexes entries by timestamp, supporting efficient range queries over insertion times and retrieval of the most recent N entries.

## Usage

```python
from key_management_demo import TimeOrderedKVStore

store = TimeOrderedKVStore()
store.put("sensor-1", 42.0)
store.put("sensor-2", 18.0)

# Most recent entry for a key -> (timestamp, value)
print(store.get_latest("sensor-1"))   # (t, 42.0)

# 10 most recent entries across all keys -> [(timestamp, key, value), ...]
print(store.get_recent(10))

# Everything in a time window [start, end], inclusive
print(store.get_range(0.0, 100.0))

# All versions of a key in insertion order -> [(timestamp, value), ...]
print(store.get_history("sensor-1"))
```

For deterministic control, pass a clock function:

```python
class FakeClock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now
    def advance(self, by=1.0):
        self.now += by

clk = FakeClock()
store = TimeOrderedKVStore(clock=clk)
store.put("k", "v1")
clk.advance()
store.put("k", "v2")
```

## Why

The store maintains a dict for key→value lookups alongside a flat list of
`(timestamp, key, value)` kept sorted by timestamp.  Inserts are O(1) because
timestamps must be monotonic non-decreasing — the store enforces this and
raises `ValueError` if a clock goes backwards.  Range scans use binary search,
giving O(log n + result) query time.

## Edge case to know about

Timestamps must be monotonic.  If the injected clock ever decreases, `put`
raises `ValueError`.  The default clock is `time.monotonic`, which does not go
backwards but can return the same value across rapid calls.  Equal timestamps
are allowed; ties are ordered by insertion sequence.
