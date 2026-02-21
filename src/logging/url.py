from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from src.logging.ingestion import LogIngestionService

router = APIRouter(prefix="/logging", tags=["cloud", "logging", "ingestion"])

@router.post("/ingest")
async def log(request: Request):
    try:
        data = await request.json()

        ingestion_service = LogIngestionService(internal_batch_size=1, redis_flush_count=10)
        log_object = ingestion_service.ingest_log(data)
        
        return JSONResponse(content={"message": "Log received successfully", "log_object": log_object}, status_code=200)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

