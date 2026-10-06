from segment_builder.rate_limiter import SlidingWindowRateLimiter


class FakeClock:
    """Deterministic clock: sleep_fn advances the same clock time_fn reads,
    so the limiter's pacing decisions are exactly reproducible without a
    real wall-clock wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _no_window_of_the_budget_is_exceeded(timestamps: list[float], max_requests: int, window_seconds: float) -> bool:
    """Reference oracle, independent of SlidingWindowRateLimiter's own
    internals: for every timestamp, count how many timestamps (including
    itself) fall within window_seconds before or at it, and require that
    count never exceeds max_requests."""
    for i, t in enumerate(timestamps):
        count = sum(1 for other in timestamps if t - window_seconds < other <= t)
        if count > max_requests:
            return False
    return True


def test_first_max_requests_proceed_without_waiting():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(100, 10.0, time_fn=clock.time, sleep_fn=clock.sleep)
    waited = [limiter.acquire() for _ in range(100)]
    assert waited == [0.0] * 100
    assert clock.sleeps == []


def test_101st_request_in_same_instant_waits_for_the_window_to_clear():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(100, 10.0, time_fn=clock.time, sleep_fn=clock.sleep)
    for _ in range(100):
        limiter.acquire()
    waited = limiter.acquire()
    assert waited > 0.0
    assert clock.now >= 10.0


def test_250_requests_never_exceed_the_budget_in_any_10s_window():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(100, 10.0, time_fn=clock.time, sleep_fn=clock.sleep)
    timestamps = []
    for _ in range(250):
        limiter.acquire()
        timestamps.append(clock.now)
    assert _no_window_of_the_budget_is_exceeded(timestamps, 100, 10.0)


def test_spreading_requests_out_avoids_waiting_at_all():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(100, 10.0, time_fn=clock.time, sleep_fn=clock.sleep)
    for _ in range(300):
        limiter.acquire()
        clock.now += 0.2  # ~1 request every 0.2s is well under 100 per 10s
    assert clock.sleeps == []
