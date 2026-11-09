"""Shared slowapi limiter (lives here so routes can decorate endpoints without importing main)."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.app.config import ENABLE_RATE_LIMITING, RATE_LIMIT_PER_MINUTE

limiter = Limiter(key_func=get_remote_address, enabled=ENABLE_RATE_LIMITING)
CHAT_RATE_LIMIT = f"{RATE_LIMIT_PER_MINUTE}/minute"
