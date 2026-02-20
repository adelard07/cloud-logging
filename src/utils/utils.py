from zoneinfo import ZoneInfo
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import logging
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("cloud_logging.log"),
        ]
)


def to_sql_literal(v):
    if v is None:
        return "NULL"

    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)

    if isinstance(v, datetime):
        v = v.isoformat(sep=" ", timespec="seconds")

    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def get_ist_time(self):
    return datetime.now(tz=ZoneInfo('Asia/Kolkata'))


_SECRET_KEY = os.getenv("AES_SECRET_KEY")

if not _SECRET_KEY:
    raise RuntimeError("AES_SECRET_KEY environment variable is not set")

_KEY = _SECRET_KEY.encode("utf-8")

if len(_KEY) != 32:
    raise ValueError("AES_SECRET_KEY must be exactly 32 bytes for AES-256")

def encrypt(data: str) -> str:
    if data is None:
        return None
    aesgcm = AESGCM(_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    encrypted = nonce + ciphertext
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt(data: str) -> str:
    if data is None:
        return None
    raw = base64.b64decode(data.encode("utf-8"))
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(_KEY)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
