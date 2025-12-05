# ticket/fonepay_utils.py
import hmac
import hashlib
from typing import Optional
import uuid

def generate_hmac_sha512(secret_key: str, message: str) -> str:
    """
    HMAC-SHA512 hex uppercase (Fonepay expects hex string - sample code uses uppercase hex).
    Message MUST be raw string with commas separating fields and NOT URL-encoded.
    """
    if isinstance(secret_key, str):
        key = secret_key.encode("utf-8")
    else:
        key = secret_key
    msg = message.encode("utf-8")
    mac = hmac.new(key, msg, hashlib.sha512).hexdigest().upper()
    return mac

def make_prn() -> str:
    """Return a unique PRN (product reference number). Uses uuid4."""
    return uuid.uuid4().hex  # 32 char hex; fits docs requiring 1-50
