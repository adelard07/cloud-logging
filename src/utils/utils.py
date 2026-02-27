from zoneinfo import ZoneInfo
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

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


import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class Crypting:
    def __init__(self):
        key_raw = os.getenv("ENCRYPTION_KEY")
        if not key_raw:
            raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
        try:
            decoded = base64.urlsafe_b64decode(key_raw + "=" * (-len(key_raw) % 4))
            if len(decoded) not in (16, 24, 32):
                raise ValueError(f"Decoded ENCRYPTION_KEY must be 16, 24, or 32 bytes, got {len(decoded)}")
            self.key = decoded
        except Exception:
            raw_bytes = key_raw.encode("utf-8")
            if len(raw_bytes) < 16:
                raise RuntimeError(f"ENCRYPTION_KEY too short: {len(raw_bytes)} bytes, minimum 16")
            self.key = raw_bytes[:32].ljust(32, b"\0")

    def encrypt(self, plaintext: str) -> str:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
        return base64.urlsafe_b64encode(iv + ciphertext).decode("utf-8").rstrip("=")

    def decrypt(self, token: str) -> str:
        if not token or not isinstance(token, str):
            raise ValueError("Token must be a non-empty string")
        padded = token + "=" * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded)
        except Exception as e:
            raise ValueError(f"Failed to base64-decode token: {e}")
        if len(raw) < 17:  # 16 bytes IV + at least 1 byte ciphertext
            raise ValueError(f"Token too short after decoding: {len(raw)} bytes")
        iv, ciphertext = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")