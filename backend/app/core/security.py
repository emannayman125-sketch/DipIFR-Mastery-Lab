import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        # "jti" (JWT ID) is a random nonce that guarantees two tokens for the
        # same user are never byte-identical, even if minted within the same
        # second (e.g. a fast register-then-refresh) — without it, identical
        # claims + identical second-granularity expiry can produce identical
        # JWTs, which is confusing for anything that compares/logs tokens
        # even though each remains independently valid.
        {"sub": subject, "type": "access", "jti": secrets.token_hex(8), "exp": expires},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise ValueError("Wrong token type")
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Invalid token subject")
    return str(subject)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)


def generate_one_time_token() -> str:
    """Generate an opaque high-entropy token for email/password flows."""
    return secrets.token_urlsafe(48)


def hash_one_time_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
