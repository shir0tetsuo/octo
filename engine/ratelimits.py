import time
from collections import defaultdict, deque


# For authorization keys
key_buckets = defaultdict(deque)
def within_key_rate_limit(api_key, RATE = 50, WINDOW = 60):
    now = time.time()
    q = key_buckets[api_key]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True

# General IP rate limiting
ip_buckets = defaultdict(deque)
def within_ip_rate_limit(client_ip, RATE = 25, WINDOW = 30):
    now = time.time()
    q = ip_buckets[client_ip]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True

# Edit rate limiting
edit_buckets = defaultdict(deque)
def within_edit_rate_limit(client_ip, RATE = 5, WINDOW = 25):
    now = time.time()
    q = edit_buckets[client_ip]

    while q and q[0] <= now - WINDOW:
        q.popleft()

    if len(q) >= RATE:
        return False
    
    q.append(now)
    return True