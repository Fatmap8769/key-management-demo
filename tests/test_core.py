import unittest

from key_management_demo import TimeOrderedKVStore


class FakeClock:
    """A deterministic, manually-advanced clock for tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, by: float = 1.0) -> None:
        self.now += by


class TestPutAndGetLatest(unittest.TestCase):
    def test_put_then_get_latest(self):
        clock = FakeClock(10.0)
        store = TimeOrderedKVStore(clock=clock)
        ts = store.put("a", 1)
        self.assertEqual(ts, 10.0)
        self.assertEqual(store.get_latest("a"), (10.0, 1))

    def test_overwrite_returns_latest(self):
        clock = FakeClock(0.0)
        store = TimeOrderedKVStore(clock=clock)
        store.put("k", "v1")
        clock.advance()
        store.put("k", "v2")
        self.assertEqual(store.get_latest("k"), (1.0, "v2"))

    def test_get_latest_missing_key(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        self.assertIsNone(store.get_latest("nope"))

    def test_get_history_preserves_insertion_order(self):
        clock = FakeClock()
        store = TimeOrderedKVStore(clock=clock)
        store.put("k", "a")
        clock.advance()
        store.put("k", "b")
        clock.advance()
        store.put("k", "c")
        self.assertEqual(
            store.get_history("k"),
            [(0.0, "a"), (1.0, "b"), (2.0, "c")],
        )


class TestPutAt(unittest.TestCase):
    def test_explicit_timestamp(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put_at("x", 1, 5.0)
        self.assertEqual(store.get_latest("x"), (5.0, 1))

    def test_non_monotonic_timestamp_rejected(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put_at("x", 1, 5.0)
        with self.assertRaises(ValueError):
            store.put_at("y", 2, 4.0)

    def test_equal_timestamp_allowed(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put_at("x", 1, 5.0)
        store.put_at("y", 2, 5.0)  # should not raise
        self.assertEqual(store.get_latest("y"), (5.0, 2))

    def test_non_string_key_rejected(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        with self.assertRaises(TypeError):
            store.put_at(123, "x", 1.0)  # type: ignore[arg-type]


class TestGetRecent(unittest.TestCase):
    def test_returns_n_most_recent(self):
        clock = FakeClock()
        store = TimeOrderedKVStore(clock=clock)
        store.put("a", 1)
        clock.advance()
        store.put("b", 2)
        clock.advance()
        store.put("c", 3)
        recent = store.get_recent(2)
        self.assertEqual(
            recent,
            [(1.0, "b", 2), (2.0, "c", 3)],
        )

    def test_n_exceeds_total(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put("a", 1)
        self.assertEqual(store.get_recent(10), [(0.0, "a", 1)])

    def test_n_zero_or_negative(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put("a", 1)
        self.assertEqual(store.get_recent(0), [])
        self.assertEqual(store.get_recent(-1), [])

    def test_empty_store(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        self.assertEqual(store.get_recent(5), [])
        self.assertEqual(store.get_range(0.0, 10.0), [])


class TestGetRange(unittest.TestCase):
    def test_inclusive_bounds(self):
        clock = FakeClock()
        store = TimeOrderedKVStore(clock=clock)
        store.put("a", 1)  # 0
        clock.advance()
        store.put("b", 2)  # 1
        clock.advance()
        store.put("c", 3)  # 2
        result = store.get_range(1.0, 2.0)
        self.assertEqual(
            result,
            [(1.0, "b", 2), (2.0, "c", 3)],
        )

    def test_single_point_range(self):
        clock = FakeClock()
        store = TimeOrderedKVStore(clock=clock)
        store.put("a", 1)
        self.assertEqual(store.get_range(0.0, 0.0), [(0.0, "a", 1)])

    def test_no_match(self):
        clock = FakeClock()
        store = TimeOrderedKVStore(clock=clock)
        store.put("a", 1)
        self.assertEqual(store.get_range(5.0, 10.0), [])

    def test_inverted_range(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        self.assertEqual(store.get_range(5.0, 1.0), [])

    def test_ties_break_by_insertion_order(self):
        store = TimeOrderedKVStore(clock=FakeClock())
        store.put_at("a", 1, 5.0)
        store.put_at("b", 2, 5.0)
        store.put_at("c", 3, 5.0)
        result = store.get_range(5.0, 5.0)
        self.assertEqual(
            result,
            [(5.0, "a", 1), (5.0, "b", 2), (5.0, "c", 3)],
        )
        # get_latest should return the most recently inserted at that ts
        self.assertEqual(store.get_latest("c"), (5.0, 3))


class TestDefaultClockIsMonotonic:
    def test_default_clock_used(self):
        store = TimeOrderedKVStore()
        ts = store.put("a", 1)
        self.assertIsInstance(ts, float)
        self.assertGreaterEqual(ts, 0.0)
        self.assertEqual(store.get_latest("a")[0], ts)


if __name__ == "__main__":
    unittest.main()
