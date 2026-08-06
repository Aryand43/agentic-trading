"""Historical backtesting, performance metrics, and classic baselines."""

from src.backtest.engine import BacktestResult, run_signal_backtest
from src.backtest.metrics import compute_metrics
from src.backtest.report import build_report, write_report

__all__ = [
    "BacktestResult",
    "run_signal_backtest",
    "compute_metrics",
    "build_report",
    "write_report",
]
