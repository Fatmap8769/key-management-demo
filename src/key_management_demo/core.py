from __future__ import annotations

import bisect
from typing import Callable, Dict, List, Optional, Tuple


class TimeOrderedKVStore:
    """A key-value store indexed by insertion timestamp.

    Supports efficient range queries over insertion times and retrieval of
    the most recent N entries.

    Design notes:
      - Two parallel structures are maintained: a dict for key->value and a
        list of (timestamp, key) tuples kept sorted by timestamp.  The list
        is append-only because timestamps are required to be monotonic;
        this keeps inserts O(1) and range queries O(log n + result).
      - A monotonicity check is enforced: each put's timestamp must be >=
        the last stored timestamp.  This invariant guarantees the sorted list
        stays sorted without per-insert sorting.
      - The clock is injectable so tests can be fully deterministic.
      - Values are returned as ``(timestamp, value)`` tuples so callers can
        distinguish entries with the same key inserted at different times.
      - When multiple entries share a timestamp, ties are broken by
        insertion order (stable append), and get_latest returns the most
        recently *inserted* among them.
    """

    def __init__(self, clock: Optional[Callable[[], float]] = None) -> None:
        """Initialise the store.

        Args:
            clock: A zero-argument callable returning a float timestamp.
                If omitted, ``time.monotonic`` is used.  The clock must be
                monotonic non-decreasing for correct operation; the store
                verifies this invariant per insert.
        """
        if clock is None:
            import time

            clock = time.monotonic
        self._clock = clock
        # key -> list of (timestamp, value) in insertion order
        self._data: Dict[str, List[Tuple[float, object]]] = {}
        # flat sorted-by-timestamp list of (timestamp, key, value)
        self._timeline: List[Tuple[float, str, object]] = []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def put(self, key: str, value: object) -> float:
        """Store ``value`` under ``key`` at the current clock time.

        Returns the timestamp assigned to the entry.

        Raises:
            ValueError: If the clock went backwards relative to the last
                stored timestamp.  This protects the sorted-list invariant.
        """
        return self.put_at(key, value, self._clock())

    def put_at(self, key: str, value: object, timestamp: float) -> float:
        """Store ``value`` under ``key`` at an explicit ``timestamp``.

        The timestamp must be >= the last stored timestamp (monotonic).
        Returns the timestamp for convenience.
        """
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if self._timeline and timestamp < self._timeline[-1][0]:
            raise ValueError(
                "timestamp must be >= the last stored timestamp "
                f"({self._timeline[-1][0]}); got {timestamp}"
            )
        self._data.setdefault(key, []).append((timestamp, value))
        self._timeline.append((timestamp, key, value))
        return timestamp

    # ------------------------------------------------------------------
    # Single-key lookups
    # ------------------------------------------------------------------
    def get_latest(self, key: str) -> Optional[Tuple[float, object]]:
        """Return the most recent ``(timestamp, value)`` for ``key``.

        Returns ``None`` if the key has never been stored.
        """
        entries = self._data.get(key)
        if not entries:
            return None
        return entries[-1]

    def get_history(self, key: str) -> List[Tuple[float, object]]:
        """Return all ``(timestamp, value)`` entries for ``key`` in insertion order."""
        return list(self._data.get(key, []))

    # ------------------------------------------------------------------
    # Time-ordered queries
    # ------------------------------------------------------------------
    def get_recent(self, n: int) -> List[Tuple[float, str, object]]:
        """Return the ``n`` most recently inserted entries.

        Results are ordered oldest-first.  If ``n`` exceeds the total
        count, all entries are returned.  ``n <= 0`` yields an empty list.
        """
        if n <= 0:
            return []
        return list(self._timeline[-n:])

    def get_range(self, start: float, end: float) -> List[Tuple[float, str, object]]:
        """Return all entries with ``start <= timestamp <= end``.

        Results are ordered by timestamp, then by insertion order for
        ties.  An empty list is returned when the range matches nothing.
        """
        if start > end:
            return []
        # bisect_left gives the first index whose timestamp >= start
        lo = bisect.bisect_left(self._timeline, (start, "\x00", None))
        # We cannot use bisect_right directly because we want <= end, and
        # bisect_right on the sentinel (end, \uffff, None) would find the
        # insertion point after all entries with timestamp == end.  We use
        # the fact that keys are arbitrary strings and pick sentinels that
        # sort just outside any real key.
        hi = bisect.bisect_right(self._timeline, (end, "\uffff", None))
        return list(self._timeline[lo:hi])
