from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.logging.url import router as logging_router
from src.fetch.urls import router as fetch_logs_router

app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

@app.get("/health_check")
async def health_check():
    return {"server": "ok"}


@app.get("/debug-routes")
async def debug_routes():
    return [{"path": r.path, "name": r.name} for r in app.routes]

app.include_router(logging_router)
app.include_router(fetch_logs_router)

# If your routes are mounted without a prefix issue, use this:
handler = Mangum(app, lifespan="off", api_gateway_base_path=None)