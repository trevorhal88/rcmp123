from time import time

attempts = {}

def rate_limit(ip: str, limit: int = 5, window: int = 60):
    now = time()

    if ip not in attempts:
        attempts[ip] = []

    attempts[ip] = [t for t in attempts[ip] if now - t < window]

    if len(attempts[ip]) >= limit:
        return False

    attempts[ip].append(now)
    return True