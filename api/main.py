"""FastAPI entrypoint. Run from repo root:

    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    AgentRequest,
    AgentResponse,
    AuditResponse,
    BacktestRequest,
    BacktestResponse,
    RiskAuditResponse,
    RunRequest,
    RunResponse,
    TradesResponse,
)
from api.service import (
    get_backtest_audit,
    get_backtest_risk,
    get_backtest_trades,
    run_agent,
    run_backtest,
    run_pipeline,
)

app = FastAPI(title="Agentic Trading API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/backtest", response_model=BacktestResponse)
def backtest(request: BacktestRequest | None = None) -> BacktestResponse:
    try:
        return run_backtest(request or BacktestRequest())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/agent", response_model=AgentResponse)
def agent(request: AgentRequest | None = None) -> AgentResponse:
    try:
        return run_agent(request or AgentRequest())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/backtest/{run_id}/trades", response_model=TradesResponse)
def backtest_trades(run_id: str) -> TradesResponse:
    try:
        return get_backtest_trades(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/backtest/{run_id}/audit", response_model=AuditResponse)
def backtest_audit(run_id: str) -> AuditResponse:
    try:
        return get_backtest_audit(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/backtest/{run_id}/risk", response_model=RiskAuditResponse)
def backtest_risk(run_id: str) -> RiskAuditResponse:
    try:
        return get_backtest_risk(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
