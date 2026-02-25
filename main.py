from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.logging.url import router as logging_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health_check")
async def health_check():
    return {"server": "ok"}

app.include_router(logging_router)

handler = Mangum(app, lifespan="off")