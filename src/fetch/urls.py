import io
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from src.db.clickhouse.services import ClickHouseServices
from src.api_key.authenticate import GenerateAPIKey
from src.fetch.fetch_logs import FetchLogs

load_dotenv()

router = APIRouter(prefix="/logs", tags=["logs"])

API_KEY_QUERY_NAME = (os.getenv("API_KEY_HEADER_NAME") or "apikey").strip()


@router.get("/export")
def export_logs_csv(
    apikey: str | None = Query(None),
    apiKey: str | None = Query(None),
    log_id: Optional[str] = Query(None, description="Optional single log_id filter"),
) -> StreamingResponse:

    # --- Auth ---
    key = apiKey or apikey
    check_api_key = GenerateAPIKey().validate_api_key(api_key=key)[0]
    if check_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    # --- Fetch & format logs ---
    try:
        df = FetchLogs().merge_format_logs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=404, detail="No logs found.")

    # --- Optional log_id filter ---
    if log_id:
        df = df[df["log_id"].astype(str) == log_id.strip()]
        if df.empty:
            raise HTTPException(
                status_code=404, detail=f"No log found with log_id '{log_id}'."
            )

    # --- Stream CSV response ---
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"logs_export_{ts}.csv"
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )