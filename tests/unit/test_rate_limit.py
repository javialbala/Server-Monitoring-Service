from conftest import FakeClock

from minipaas.controlplane.security.rate_limit import LoginRateLimiter


def make(clock):
    return LoginRateLimiter(max_failures=5, window_minutes=15, clock=clock)


def fail(limiter, times, ip="1.1.1.1", user="ana"):
    for _ in range(times):
        limiter.record_failure(ip, user)


def test_not_blocked_below_limit():
    limiter = make(FakeClock())
    fail(limiter, 4)
    assert limiter.is_blocked("1.1.1.1", "ana") is None


def test_blocked_at_limit_with_retry_after():
    clock = FakeClock()
    limiter = make(clock)
    fail(limiter, 5)
    assert limiter.is_blocked("1.1.1.1", "ana") == 15 * 60
    clock.advance(minutes=10)
    assert limiter.is_blocked("1.1.1.1", "ana") == 5 * 60


def test_unblocked_after_window():
    clock = FakeClock()
    limiter = make(clock)
    fail(limiter, 5)
    clock.advance(minutes=15, seconds=1)
    assert limiter.is_blocked("1.1.1.1", "ana") is None


def test_blocks_by_ip_across_usernames():
    limiter = make(FakeClock())
    for i in range(5):
        limiter.record_failure("1.1.1.1", f"user{i}")
    assert limiter.is_blocked("1.1.1.1", "otro") is not None
    assert limiter.is_blocked("2.2.2.2", "otro") is None


def test_blocks_by_username_across_ips_case_insensitive():
    limiter = make(FakeClock())
    for i in range(5):
        limiter.record_failure(f"10.0.0.{i}", "Ana")
    assert limiter.is_blocked("9.9.9.9", "ANA") is not None


def test_reset_username_after_success():
    limiter = make(FakeClock())
    fail(limiter, 5)
    limiter.reset_username("ana")
    assert limiter.is_blocked("2.2.2.2", "ana") is None
