from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.logging.url import router as logging_router
from src.fetch.urls import router as fetch_logs_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
                   "https://sales-copilot-hazel.vercel.app",
                   "https://salescopilot.eduvance.ai"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["content-type", 
                   "authorization", 
                   "apikey", 
                   "apiKey"],
)

@app.get("/health_check")
async def health_check():
    return {"server": "ok"}

app.include_router(logging_router)
app.include_router(fetch_logs_router)

handler = Mangum(app, lifespan="off")