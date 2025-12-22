def expand_sequence(n: int, length: int = 8):
    start = n * length + 1
    return list(range(start, start + length))