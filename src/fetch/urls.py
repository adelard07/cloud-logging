import io
import math
import numpy as np
from urllib.parse import unquote
import os
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from src.api_key.authenticate import GenerateAPIKey
from src.fetch.fetch_logs import FetchLogs
from src.db.clickhouse.services import ClickHouseServices
from src.db.redis.services import RedisServices

from src.api_key.authenticate import GenerateAPIKey
from src.fetch.fetch_logs import FetchLogs

load_dotenv()


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/get")
def get_all_logs(
    apikey: str | None = Query(None),
    apiKey: str | None = Query(None),
):
    raw_key = apiKey or apikey
    key = unquote(raw_key).replace(" ", "+") if raw_key else None

    check_api_key = GenerateAPIKey().validate_api_key(api_key=key)[0]
    if not check_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    try:
        df = FetchLogs().merge_format_logs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=404, detail="No logs found.")

    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    records = df.to_dict(orient="records")

    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if math.isnan(obj) else float(obj)
        if isinstance(obj, np.ndarray):
            return sanitize(obj.tolist())
        return obj

    payload = sanitize({"count": len(records), "logs": records})
    return JSONResponse(content=payload, status_code=200)



# @router.get("/export")
# def export_logs_xlsx(
#     apikey: str | None = Query(None),
#     apiKey: str | None = Query(None),
# ) -> StreamingResponse:

#     key = apiKey or apikey
#     check_api_key = GenerateAPIKey().validate_api_key(api_key=key)[0]
#     if not check_api_key:
#         raise HTTPException(status_code=401, detail="Invalid API key.")

#     try:
#         df = FetchLogs().merge_format_logs()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")

#     if df.empty:
#         raise HTTPException(status_code=404, detail="No logs found.")
        
#     if df["timestamp"].dt.tz is not None:
#         df["timestamp"] = df["timestamp"].dt.tz_localize(None)
#     else:
#         df["timestamp"] = df["timestamp"].dt.tz_convert(None)

#     buffer = io.BytesIO()
#     with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
#         df.to_excel(writer, index=False, sheet_name="Logs")
#     buffer.seek(0)

#     filename = f"raw_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

#     return StreamingResponse(
#         buffer,
#         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         headers={"Content-Disposition": f"attachment; filename={filename}"},
#     )
    
    
