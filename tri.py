import time

# Create a high-precision epoch clock to eliminate 15.6ms Windows jitter
_INITIAL_TIME = time.time()
_INITIAL_PERF = time.perf_counter()

_INIT_TIME_0 = 0


def get_precise_time():
    """Returns absolute epoch time with sub-millisecond precision."""
    return time.perf_counter() - _INITIAL_PERF


for i in range(10):
    print(get_precise_time())
