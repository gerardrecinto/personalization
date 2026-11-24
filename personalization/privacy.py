import hashlib
import hmac
import os


def user_key(user_id: str, secret: str | None = None) -> str:
    """Keyed hash so raw user ids never reach the store or the logs."""
    key = (secret or os.environ.get("USER_HASH_SECRET", "dev-only-secret")).encode()
    return hmac.new(key, user_id.encode(), hashlib.sha256).hexdigest()[:24]
