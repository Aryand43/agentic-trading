"""Walk-forward risk-method comparison on daily returns.

Does not modify the minute-bar EWMA / Cornish-Fisher functions in
``src.risk.volatility``. Those remain the live/intraday engine and are
covered by existing tests.

This module scales by trading-day horizon (``HORIZON_TRADING_DAYS``), never
by minutes. Predictions at T use returns through T only.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.config import HORIZON_TRADING_DAYS, HORIZONS, MIN_SAMPLE_TRADING_DAYS, RISK
from src.risk.engine.advanced_risk import calculate_cornish_fisher_multiplier
from src.risk.engine.baseline_metrics import calculate_historical_var


def _portfolio_returns(returns: pd.DataFrame | pd.Series) -> pd.Series:
    if isinstance(returns, pd.Series):
        return returns.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    clean = returns.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty:
        return pd.Series(dtype=float)
    return clean.mean(axis=1)


def _cf_z(windowed: pd.Series, confidence: float) -> float:
    frame = windowed.to_frame(name="r")
    z = calculate_cornish_fisher_multiplier(frame, window_size=len(frame), confidence=confidence)
    val = float(z.iloc[-1]["r"])
    if not np.isfinite(val):
        return float(norm.ppf(1 - confidence))
    return val


def evaluate_risk_methods(
    returns: pd.DataFrame | pd.Series,
    *,
    horizons: list[str] | None = None,
    window: int | None = None,
    ewma_lambda: float | None = None,
    confidences: tuple[float, ...] = (0.95, 0.99),
    min_obs: int = 20,
) -> list[dict[str, Any]]:
    """Compare historical std, historical VaR, and EWMA/Cornish-Fisher.

    Returns one row per method × horizon (× confidence for VaR methods).
    Does not claim any method is superior.
    """
    port = _portfolio_returns(returns)
    if port.empty or len(port) < min_obs + 5:
        return []

    horizons = horizons or list(HORIZONS)
    window = int(window if window is not None else RISK.get("daily_estimation_days", 63))
    lam = float(ewma_lambda if ewma_lambda is not None else RISK.get("ewma_lambda", 0.99))
    alpha = 1.0 - lam

    rows: list[dict[str, Any]] = []
    idx = port.index

    for horizon in horizons:
        h = int(HORIZON_TRADING_DAYS.get(horizon, 1))
        if h < 1:
            continue

        pred_std: list[float] = []
        real_vol: list[float] = []
        pred_hvar: dict[float, list[float]] = {c: [] for c in confidences}
        pred_cf: dict[float, list[float]] = {c: [] for c in confidences}
        real_loss: list[float] = []
        breach_hvar: dict[float, list[int]] = {c: [] for c in confidences}
        breach_cf: dict[float, list[int]] = {c: [] for c in confidences}
        dates: list[Any] = []

        last_i = len(port) - h - 1
        start_i = max(window, min_obs)
        for i in range(start_i, last_i + 1):
            hist = port.iloc[: i + 1]
            windowed = hist.tail(window)
            if len(windowed) < min_obs:
                continue
            fwd = port.iloc[i + 1 : i + 1 + h]
            if len(fwd) < h:
                continue

            realized_ret = float((1.0 + fwd).prod() - 1.0)
            loss = float(-realized_ret)
            if h == 1:
                realized_vol = float(abs(fwd.iloc[0]))
            else:
                realized_vol = float(fwd.std(ddof=0) * np.sqrt(h))

            sigma = float(windowed.std(ddof=0))
            if not np.isfinite(sigma):
                continue
            pred_vol = sigma * np.sqrt(h)
            ewma_sigma = float(windowed.ewm(alpha=alpha, adjust=False).std().iloc[-1])
            if not np.isfinite(ewma_sigma):
                ewma_sigma = sigma

            pred_std.append(pred_vol)
            real_vol.append(realized_vol)
            real_loss.append(loss)
            dates.append(idx[i])

            for conf in confidences:
                hvar = float(calculate_historical_var(windowed, confidence=conf)) * np.sqrt(h)
                z = _cf_z(windowed, conf)
                cf = abs(z * ewma_sigma * np.sqrt(h))
                pred_hvar[conf].append(hvar)
                pred_cf[conf].append(cf)
                breach_hvar[conf].append(1 if loss > hvar else 0)
                breach_cf[conf].append(1 if loss > cf else 0)

        n = len(pred_std)
        if n == 0:
            rows.append(
                {
                    "method": "historical_std",
                    "horizon": horizon,
                    "confidence": None,
                    "predicted_risk": None,
                    "realized_risk": None,
                    "error": None,
                    "error_metric": "mae",
                    "breach_rate": None,
                    "n_obs": 0,
                    "sample_start": None,
                    "sample_end": None,
                    "low_sample": True,
                    "risk_type": "volatility",
                }
            )
            continue

        start = dates[0]
        end = dates[-1]
        sample_start = start.strftime("%Y-%m-%d") if hasattr(start, "strftime") else str(start)[:10]
        sample_end = end.strftime("%Y-%m-%d") if hasattr(end, "strftime") else str(end)[:10]
        low = n < MIN_SAMPLE_TRADING_DAYS

        std_err = float(np.mean(np.abs(np.array(pred_std) - np.array(real_vol))))
        rows.append(
            {
                "method": "historical_std",
                "horizon": horizon,
                "confidence": None,
                "predicted_risk": float(np.mean(pred_std)),
                "realized_risk": float(np.mean(real_vol)),
                "error": std_err,
                "error_metric": "mae",
                "breach_rate": None,
                "n_obs": n,
                "sample_start": sample_start,
                "sample_end": sample_end,
                "low_sample": low,
                "risk_type": "volatility",
            }
        )

        for conf in confidences:
            hvar_err = float(
                np.mean(np.abs(np.array(pred_hvar[conf]) - np.array(real_loss)))
            )
            rows.append(
                {
                    "method": "historical_var",
                    "horizon": horizon,
                    "confidence": conf,
                    "predicted_risk": float(np.mean(pred_hvar[conf])),
                    "realized_risk": float(np.mean(real_loss)),
                    "error": hvar_err,
                    "error_metric": "mae",
                    "breach_rate": float(np.mean(breach_hvar[conf])),
                    "n_obs": n,
                    "sample_start": sample_start,
                    "sample_end": sample_end,
                    "low_sample": low,
                    "risk_type": "var",
                }
            )
            cf_err = float(np.mean(np.abs(np.array(pred_cf[conf]) - np.array(real_loss))))
            rows.append(
                {
                    "method": "ewma_cornish_fisher",
                    "horizon": horizon,
                    "confidence": conf,
                    "predicted_risk": float(np.mean(pred_cf[conf])),
                    "realized_risk": float(np.mean(real_loss)),
                    "error": cf_err,
                    "error_metric": "mae",
                    "breach_rate": float(np.mean(breach_cf[conf])),
                    "n_obs": n,
                    "sample_start": sample_start,
                    "sample_end": sample_end,
                    "low_sample": low,
                    "risk_type": "var",
                }
            )

    return rows
