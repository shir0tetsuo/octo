import time
from collections import defaultdict, deque

RATE = 50
WINDOW = 60

buckets = defaultdict(deque)

def within_rate_limit(api_key):
    now = time.time()
    q = buckets[api_key]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True