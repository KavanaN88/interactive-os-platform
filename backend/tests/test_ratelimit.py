from app.core.ratelimit import SlidingWindowLimiter

class Clock:
    t = 0.0
    def __call__(self): return self.t

def test_blocks_after_limit_and_recovers_after_window():
    c = Clock(); lim = SlidingWindowLimiter(3, 10, clock=c)
    assert [lim.allow("a") for _ in range(4)] == [True, True, True, False]
    c.t = 10.5
    assert lim.allow("a") is True

def test_clients_are_independent():
    c = Clock(); lim = SlidingWindowLimiter(1, 10, clock=c)
    assert lim.allow("a") and not lim.allow("a") and lim.allow("b")

def test_sliding_not_fixed_window():
    c = Clock(); lim = SlidingWindowLimiter(2, 10, clock=c)
    c.t = 0; assert lim.allow("a")
    c.t = 9; assert lim.allow("a")
    c.t = 10.5; assert lim.allow("a")          # the t=0 hit expired, the t=9 hit still counts
    assert not lim.allow("a")

def test_memory_is_bounded():
    c = Clock(); lim = SlidingWindowLimiter(1, 1, max_keys=100, clock=c)
    for i in range(500):
        c.t += 2
        lim.allow(f"k{i}")
    assert len(lim._hits) <= 101
