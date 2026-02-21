from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from src.logging.ingestion import LogIngestionService

router = APIRouter(prefix="/logging", tags=["cloud", "logging"])

@router.post("/log")
async def log(request: Request):
    try:
        data = await request.json()

        ingestion = LogIngestionService()
        log_object = ingestion.ingest_log(data)
        
        return JSONResponse(content={"message": "Log received successfully"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))