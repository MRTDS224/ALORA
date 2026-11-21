import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from app.core.config import settings

SESSION_COOKIE_NAME = "alora_session"
CONTRIBUTOR_COOKIE_NAME = "alora_contributor"
VALID_ROLES = ("collector", "reviewer", "admin")


def hash_password(password: str) -> str:
    """Hash a password using Python stdlib scrypt with a random 16-byte salt."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored scrypt hash in constant time."""
    try:
        scheme, salt_hex, dk_hex = stored_hash.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def sign_token(payload: Dict[str, Any]) -> str:
    """Sign a JSON payload with HMAC-SHA256 using settings.SECRET_KEY."""
    data = {**payload, "iat": int(time.time())}
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_token(token: Optional[str], max_age_seconds: int = settings.SESSION_MAX_AGE_SECONDS) -> Optional[Dict[str, Any]]:
    """Verify an HMAC-signed token and check its expiration."""
    if not token or "." not in token:
        return None
    try:
        b64, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), b64.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        pad = "=" * ((4 - len(b64) % 4) % 4)
        raw = base64.urlsafe_b64decode(b64 + pad)
        data = json.loads(raw.decode("utf-8"))
        iat = int(data.get("iat", 0))
        if max_age_seconds > 0 and (time.time() - iat) > max_age_seconds:
            return None
        return data
    except Exception:
        return None


# Simple in-memory sliding-window rate limiter for public endpoints
_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, max_requests: int = 60, window_seconds: int = 3600) -> bool:
    """Returns True if allowed, False if rate limit exceeded."""
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_requests:
        return False
    bucket.append(now)
    return True


def is_secure_cookie(request) -> bool:
    """Enable Secure cookie attribute in production or behind HTTPS proxies (Render, Cloudflare)."""
    if settings.is_production:
        return True
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return forwarded_proto == "https" or getattr(request.url, "scheme", "") == "https"


def get_client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
