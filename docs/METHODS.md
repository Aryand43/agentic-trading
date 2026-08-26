# Research desk methods

This document states the assumptions used by the agentic-trading research desk.
Results are **historical backtests**, not live or real-time trading.

## Data

- **Source:** Yahoo Finance via `yfinance` (`src/risk/engine/data_loader.py`).
- **Frequency:** daily OHLCV for research/backtest (`interval=1d`). Live snapshot also uses daily bars by default.
- **Universe:** configurable; research default is a liquid NASDAQ-heavy list in `src/config.py`.
- **Cache:** Close panels and OHLC panels are stored separately under `data/cache/`. Missing Open/High/Low are **not invented**.

## Signal timing (no look-ahead)

- A signal at session **T** may use OHLCV **through T’s close only**.
- Signals never see T+1 open, high, low, or close.
- Classification: score ≥ `long_threshold` → buy; score ≤ −`short_threshold` → sell (disabled in `long_only`); otherwise neutral.

Horizons: `1d, 3d, 5d, 10d, 15d, 1m, 3m` with trading-day lengths 1, 3, 5, 10, 15, 21, 63.

## Execution

- **Entry:** T+1 **open** when Open exists; otherwise the next available **close** (`price_source` records which).
- **Take-profit / stop-loss:** checked on that bar’s high/low. If the open gaps through the level, the fill is the **open**; otherwise the **threshold**. If high/low are missing, close is used and documented. If both TP and SL trade on the same bar, **stop-loss is assumed** (conservative).
- **Horizon exit:** close at T+h, where h is the horizon’s trading-day count.
- **Rebalance:** new entries only on schedule (`rebalance_every`, default 5). Flattened sleeves exit at close with `exit_reason=rebalance`.
- **End of sample:** open lots close at the last close (`end_of_data`). Unfilled intents are `rejected`.

This is **not** intraday or real-time execution. Daily bars cannot recover trade-through times.

## Costs and sizing

- Cost on each fill: `(cost_bps + slippage_bps) / 10_000 × |notional|`.
- Defaults: 5 bps commission, 0 bps extra slippage, $10,000 capital.
- Portfolio: blend horizon scores (`combine_horizon_signals`), inverse-volatility weights, optional target-vol scale, `max_position` and `gross_exposure` caps.
- Sleeves: each non-neutral `(ticker, horizon)` can be a separate trade so `signal_horizon` is honest. Ticker weight is split across agreeing active horizons.
- Default book is **long/short**; `long_only` clips sell signals to flat.

## Risk methods

The live minute-bar engine (`src/risk/volatility.py`) still uses EWMA + Cornish-Fisher with **minute** √t scaling and is unchanged.

The research comparison (`src/risk/evaluation.py`) is a **daily** walk-forward:

1. Historical standard deviation × √h
2. Historical VaR (empirical percentile) × √h
3. EWMA volatility × Cornish-Fisher z × √h

At each T the predictor uses returns through T only. Realized vol or holding-period loss is measured on T+1 … T+h. Each row reports predicted risk, realized risk, MAE, VaR breach rate (VaR methods), n, and sample dates. **No method is declared better without that table.**

Segments and risk rows with fewer than **120 trading days** are flagged `low_sample`. Missing values render as dashes, not zeros.

## Train / validation / test

Chronological splits in `src/backtest/splits.py` (defaults ≈ 756 / 126 / 15 trading days ending at `as_of`). The control-panel backtest reports the full selected window; the agent loop scores proposals on the test split.

## Agent loop

`src/agents/horizon_agent.py` is research-only. It does **not** change `/api/run` live weights.

- Default `n_iterations=2` with `seed_baselines=True` runs **2 baseline slots + 2 discovery** backtests.
- Each discovery proposal is validated against `AgentProposal` (bounded TP/SL, lookbacks, sizing, risk method), then **backtested before it is logged**.
- LLM (optional `OPENAI_API_KEY`) must return JSON; parse failures fall back to heuristic mutation. No LangChain.
- Ranking uses **test utility**, not Sharpe.

## Reproducibility

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
python -m unittest src.backtest.test_execution src.risk.test_evaluation src.agents.test_proposal
python -m examples.run_backtest --horizon 10d --portfolio --no-industry
```

Artifacts: `reports/<run_id>/{trades.csv,trades.json,config.json,manifest.json,risk.json}`.
Price cache: `data/cache/`. Agent runs: `runs/`.

## Known limitations

- Daily OHLC only; TP/SL fills are bar-level assumptions.
- Close-only panels skip true T+1 open.
- yfinance gaps, adjustments, and survivorship are not corrected.
- Minute-bar VaR functions are **not** the daily comparison table; do not mix the two scalings.
- Backtest equity is not a live track record.
