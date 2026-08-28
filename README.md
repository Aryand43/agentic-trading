# Agentic Trading

Research desk: multi-horizon signals, backtests, risk comparison, and a discovery agent.

Methods: [`docs/METHODS.md`](docs/METHODS.md). Backtests are not live trading.

## Desk

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend && npm install && npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173 — **Backtest**, **Live**, **Agent**. Window is 1y / 3y / 5y.

## API

- `POST /api/run` — live snapshot
- `POST /api/backtest` — equity, trades, risk comparison
- `POST /api/agent` — horizon discovery loop
- `GET /api/backtest/{run_id}/trades` · `/audit` · `/risk`

## CLI

```bash
python -m examples.run_backtest --horizon 10d --portfolio --agent --agent-iters 2 --no-industry
python -m examples.run_agent --horizon 10d --iters 3
python -m examples.run_paper_experiment
python -m examples.run_paper_experiment --plan
```

Reports → `reports/<run_id>/`. Paper tables → `reports/paper/`. Agent runs → `runs/`. Cache → `data/cache/`. Optional LLM: `OPENAI_API_KEY`.
