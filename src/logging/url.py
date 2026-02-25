from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.logging.ingestion import LogIngestionService
from src.models.logs import Logs, Source
from src.api_key.dependency import require_api_key

router = APIRouter(prefix="/logging", tags=["cloud", "logging", "ingestion"])


@router.post("/ingest")
async def log(log_model: Logs, tenant: dict = Depends(require_api_key)):
    try:
        if log_model.source is None:
            log_model.source = Source(diagnostics={}, source={})

        if log_model.source.source is None:
            log_model.source.source = {}

        if not isinstance(log_model.source.source, dict):
            log_model.source.source = {"_source": log_model.source.source}

        log_model.source.source["tenant"] = {
            "app_id": tenant.get("app_id"),
            "server_id": tenant.get("server_id"),
        }

        ingestion_service = LogIngestionService(
            internal_batch_size=1,
            redis_flush_count=10,
        )

        log_object = ingestion_service.ingest_log(log_model)

        return {
            "message": "Log received successfully",
            "tenant": tenant,
            "log_object": log_object.model_dump(exclude_none=True),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))