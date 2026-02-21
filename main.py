from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import fastapi

from src.logging.url import router as logging_router


app = FastAPI()

@app.get("/health_check")
async def health_check():
    return {"server": "ok"}


app.include_router(logging_router)