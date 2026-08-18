from project_sentinel.probe.rate_limit import ToolRateLimiter


def test_token_bucket_waits_after_burst_is_consumed():
    now = [0.0]
    sleeps = []

    def clock():
        return now[0]

    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    limiter = ToolRateLimiter(30, 2, clock=clock, sleeper=sleep)
    limiter.wait()
    limiter.wait()
    limiter.wait()
    assert sleeps == [2.0]
