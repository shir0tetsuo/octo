import time
from collections import defaultdict, deque

key_buckets = defaultdict(deque)
ip_buckets = defaultdict(deque)

def within_key_rate_limit(api_key):
    RATE = 50
    WINDOW = 60
    now = time.time()
    q = key_buckets[api_key]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True

def within_ip_rate_limit(client_ip):
    RATE = 25
    WINDOW = 30
    now = time.time()
    q = ip_buckets[client_ip]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True