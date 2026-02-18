import logging
import json
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("cloud_logging.log"),
        ]
)

logging.info("Logging setup complete. Logs will be written to cloud_logging.log")


def _to_sql_literal(v):
    if v is None:
        return "NULL"

    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)

    if isinstance(v, datetime):
        v = v.isoformat(sep=" ", timespec="seconds")

    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"
