from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared across the app so auth endpoints (and any future sensitive endpoint)
# can opt in with @limiter.limit(...). In-memory storage is fine for a single
# instance; swap to a Redis storage_uri before scaling to multiple workers.
limiter = Limiter(key_func=get_remote_address)
