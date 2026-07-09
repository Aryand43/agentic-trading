# Agentic Trading

Multi-horizon trading pipeline that combines signal generation, risk metrics, and portfolio construction.

## Structure

- `src/signals/` — per-horizon trading signals (1d–3m)
- `src/risk/` — volatility and portfolio risk
- `src/portfolio/` — combines signals and risk into position weights
- `examples/` — demo scripts with fake data

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m examples.run_portfolio_demo
```
