from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.logging.ingestion import LogIngestionService
from src.models.logs import Logs, SourceInfo
from src.api_key.dependency import require_api_key

router = APIRouter(prefix="/logging", tags=["cloud", "logging", "ingestion"])


@router.post("/ingest")
async def log(log_model: Logs, tenant: dict = Depends(require_api_key)):
    try:
        if log_model.source_info is None:
            log_model.source_info = SourceInfo(diagnostics={}, source={})

        if log_model.source_info.source is None:
            log_model.source_info.source = {}
        if not isinstance(log_model.source_info.source, dict):
            log_model.source_info.source = {"_source": log_model.source_info.source}

        if log_model.source_info.diagnostics is None:
            log_model.source_info.diagnostics = {}

        log_model.source_info.source["tenant"] = {
            "app_id": tenant.get("app_id"),
            "server_id": tenant.get("server_id"),
        }

        if log_model.server_info is not None:
            log_model.source_info.source["server"] = {
                "hostname": log_model.server_info.hostname,
                "portnumber": log_model.server_info.portnumber,
            }

        if log_model.request_info is not None:
            log_model.source_info.diagnostics["request"] = {
                "request_id": str(log_model.request_info.request_id),
                "request_type": log_model.request_info.request_type,
                "session_id": log_model.request_info.session_id,
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