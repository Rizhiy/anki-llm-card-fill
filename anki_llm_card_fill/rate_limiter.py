import contextlib
import time
from collections import deque
from threading import Lock
from typing import Any


class TrackedQueue:
    """Queue that maintains a running total of numeric values."""

    def __init__(self):
        """Initialize tracked queue."""
        self._queue = deque()
        self._values = {}  # Map items to their values
        self._total = 0

    def append(self, item: Any, value: int) -> None:
        """Add item to queue and update total.

        :param item: Item to add to queue
        :param value: Numeric value to add to total
        """
        self._queue.append(item)
        self._values[item] = value
        self._total += value

    def popleft(self) -> tuple[Any, int]:
        """Remove and return first item, updating total.

        :return: Tuple of (item, value)
        :raises IndexError: If queue is empty
        """
        if not self._queue:
            raise IndexError("Queue is empty")
        item = self._queue.popleft()
        value = self._values.pop(item)
        self._total -= value
        return item, value

    def remove_item(self, item: Any) -> None:
        """Remove specific item and update total.

        :param item: Item to remove
        :return: True if item was found and removed
        """
        with contextlib.suppress(ValueError):
            self._queue.remove(item)
            value = self._values.pop(item)
            self._total -= value

    def peek_front(self) -> Any:
        """Return first item without removing it.

        :return: First item in queue
        :raises IndexError: If queue is empty
        """
        if not self._queue:
            raise IndexError("Queue is empty")
        return self._queue[0]

    def __len__(self) -> int:
        """Return queue length."""
        return len(self._queue)

    def __bool__(self) -> bool:
        return bool(len(self._queue))

    @property
    def total(self) -> int:
        """Get current total."""
        return self._total

    def clear(self) -> None:
        """Clear queue and reset total."""
        self._queue.clear()
        self._values.clear()
        self._total = 0

    def items(self):
        """Iterate over (item, value) pairs."""
        for item in self._queue:
            yield item, self._values[item]


class RateLimiter:
    """Simple rate limiter using a queue approach to track requests and token usage."""

    def __init__(self, limit: int = 60, time_window: float = 60.0):
        """Initialize rate limiter.

        :param limit: Maximum limit (requests or tokens) allowed in the time window
        :param time_window: Time window in seconds
        """
        self._limit = limit
        self._time_window = time_window
        self._requests = TrackedQueue()  # Store timestamps with amounts for completed requests
        self._lock = Lock()

    def acquire(self, amount: int = 1) -> None:
        """Acquire capacity from the rate limiter, blocking if necessary.

        :param amount: Amount to acquire (tokens or request count)
        """
        while True:
            with self._lock:
                current_time = time.time()

                # Remove old requests outside the time window and update usage
                self._cleanup_expired_requests(current_time)

                if self._requests.total + amount <= self._limit:
                    # Can proceed immediately with no queue
                    self._requests.append(current_time, amount)
                    return

                time_to_wait = self._calculate_wait_time(amount, current_time)

            time.sleep(max(0.1, time_to_wait))

    def _cleanup_expired_requests(self, current_time: float) -> None:
        """Remove expired requests and update current usage.

        :param current_time: Current timestamp
        """
        while self._requests and (self._requests.peek_front() < current_time - self._time_window):
            self._requests.popleft()

    def _calculate_wait_time(self, amount: int, current_time: float) -> float:
        """Calculate how long to wait before the requested amount can be acquired.

        :param amount: Amount needed
        :return: Number of seconds to wait
        """
        # Total capacity needed includes current usage + waiting requests - limit
        if amount + self._requests.total < self._limit:
            return 0.0

        return self._requests.peek_front() + self._time_window - current_time

    def update_limit(self, new_limit: int) -> None:
        """Update the rate limit.

        :param new_limit: New maximum limit for the time window
        """
        with self._lock:
            self._limit = new_limit
