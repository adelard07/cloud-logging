from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.logging.ingestion import LogIngestionService
from src.models.logs import Logs
from src.api_key.dependency import require_api_key

router = APIRouter(prefix="/logging", tags=["cloud", "logging", "ingestion"])

@router.post("/ingest")
async def log(log_model: Logs, tenant: dict = Depends(require_api_key)):
    try:
        # Stamp tenant into log source (keeps Logs schema unchanged)
        src = log_model.source or {}
        if not isinstance(src, dict):
            src = {"_source": src}

        src["tenant"] = {
            "app_id": tenant["app_id"],
            "server_id": tenant["server_id"],
        }
        log_model.source = src

        ingestion_service = LogIngestionService(
            internal_batch_size=1,
            redis_flush_count=10
        )

        log_object = ingestion_service.ingest_log(log_model)

        return {
            "message": "Log received successfully",
            "tenant": tenant,
            "log_object": log_object.model_dump()
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))