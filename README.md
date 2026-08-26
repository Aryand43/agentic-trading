# Agentic Trading

Multi-horizon trading **research desk**: signal generation, risk metrics, portfolio
construction, historical backtesting, segmented reports, and a strategy discovery agent loop.

Header should read **Research desk · v0.7**. If you still see “Pipeline desk” or a bare
`yfinance … (5d/1m)` banner, you are on a **stale** frontend/API process — hard-restart below.

## Structure

- `src/signals/` — per-horizon trading signals (1d–3m)
- `src/risk/` — volatility and portfolio risk (long/short aware)
- `src/portfolio/` — blends signals + risk into position weights
- `src/backtest/` — daily engine, metrics, segment reports, TA baselines, portfolio sim
- `src/agents/` — one-horizon strategy discovery loop
- `examples/` — CLI demos
- `api/` + `frontend/` — research control panel

## Setup

```bash
pip install -r requirements.txt
```

## Hard restart (recommended)

Kills stray API/UI processes, then starts a clean stack on **:8000** and **:5173**:

```bash
# free ports
lsof -ti :8000,:5173,:5174 2>/dev/null | xargs kill -9 2>/dev/null || true

# terminal 1 — API (from repo root, venv on)
pip install -r api/requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2 — UI
cd frontend && npm install && npm run dev -- --host 127.0.0.1 --port 5173 --force
```

Open **http://127.0.0.1:5173**

Confirm: title **Research desk**, tabs **Backtest | Live | Agent**, green **Backtest window**
with **Start date / End date**, and eyebrow **Agentic Trading · v0.7**.

## Research control panel

### Modes

| Mode | What it does |
|------|----------------|
| **Backtest** (default) | Date window, capital, equity curve, baselines, regime·vol·industry segments |
| **Live** | Point-in-time snapshot from recent **daily** bars (cache-friendly) |
| **Agent** | Hypothesis → backtest → insights loop for one horizon (1–5 iters) |

### API

- `POST /api/run` — live pipeline (daily history first)
- `POST /api/backtest` — `start_date` + `end_date` *or* `period`, capital, flags; returns equity plus `trades`, `risk_comparison`, `run_id`
- `POST /api/agent` — horizon discovery loop (baselines + `n_iterations` discoveries)
- `GET /api/backtest/{run_id}/trades` — full trade audit
- `GET /api/backtest/{run_id}/audit` — trades + signals + trading rules
- `GET /api/backtest/{run_id}/risk` — predicted vs realized risk table

Paper methods: [`docs/METHODS.md`](docs/METHODS.md).  

## CLI

```bash
python -m examples.run_backtest --horizon 10d --portfolio --agent --agent-iters 2 --no-industry
python -m examples.run_agent --horizon 10d --iters 3
python -m examples.run_portfolio_demo
```

Reports → `reports/<run_id>/` (trades.csv/json, config.json, risk.json). Agent runs → `runs/`. Price cache → `data/cache/`.

Optional LLM text: `OPENAI_API_KEY`.

## Paper note

Draft a paper only after backtest + agent runs produce metrics you can report.
See [`docs/METHODS.md`](docs/METHODS.md) for timing, TP/SL, costs, and risk-baseline
assumptions. Do not present backtests as live trading.
