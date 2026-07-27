"""FastAPI entrypoint. Run from repo root:

    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import RunRequest, RunResponse
from api.service import run_pipeline

app = FastAPI(title="Agentic Trading API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run", response_model=RunResponse)
def run(request: RunRequest | None = None) -> RunResponse:
    try:
        return run_pipeline(request or RunRequest())
    except Exception as exc:  # surface yfinance / data errors cleanly
        raise HTTPException(status_code=500, detail=str(exc)) from exc
