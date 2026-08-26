"""Segmented backtest reports: aggregate + bull/bear + industry + vol terciles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from src.backtest.engine import BacktestResult
from src.backtest.metrics import compute_metrics, metrics_to_jsonable
from src.config import MIN_SAMPLE_TRADING_DAYS, REPORTS_DIR, RESEARCH


def _regime_labels(benchmark: pd.Series, window: int = 126) -> pd.Series:
    """Bull when price above MA(window), else bear."""
    ma = benchmark.reindex(benchmark.index).rolling(window, min_periods=max(20, window // 3)).mean()
    aligned = benchmark.reindex(ma.index)
    labels = pd.Series(np.where(aligned >= ma, "bull", "bear"), index=aligned.index, dtype=object)
    labels[ma.isna()] = "unknown"
    return labels


def _vol_tercile_labels(returns: pd.Series, window: int = 21) -> pd.Series:
    """Rolling realized vol → high / mid / low terciles over the sample."""
    vol = returns.rolling(window, min_periods=5).std()
    valid = vol.dropna()
    if valid.empty:
        return pd.Series("unknown", index=returns.index)
    q1, q2 = valid.quantile([1 / 3, 2 / 3])
    labels = pd.Series("mid", index=returns.index, dtype=object)
    labels[vol <= q1] = "low"
    labels[vol > q2] = "high"
    labels[vol.isna()] = "unknown"
    return labels


def _ticker_sectors(tickers: list[str]) -> dict[str, str]:
    sectors: dict[str, str] = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info or {}
            sectors[t] = info.get("sector") or info.get("industry") or "Unknown"
        except Exception:
            sectors[t] = "Unknown"
    return sectors


def _segment_metrics_from_returns(
    returns: pd.Series,
    mask: pd.Series,
    initial_capital: float,
) -> dict[str, float]:
    """Rebuild a mini equity curve on days matching mask and compute metrics."""
    aligned = mask.reindex(returns.index).fillna(False)
    n_active = int(aligned.sum())
    seg = returns.where(aligned, 0.0)
    if seg.abs().sum() == 0:
        out = metrics_to_jsonable(compute_metrics(pd.Series([initial_capital], dtype=float)))
        out["n_days"] = float(n_active)
        out["low_sample"] = True
        return out
    equity = (1.0 + seg).cumprod() * initial_capital
    out = metrics_to_jsonable(compute_metrics(equity, returns=seg))
    out["n_days"] = float(n_active)
    out["low_sample"] = n_active < MIN_SAMPLE_TRADING_DAYS
    return out


def build_report(
    result: BacktestResult,
    *,
    benchmark: pd.Series | None = None,
    baseline_results: dict[str, BacktestResult] | None = None,
    include_industry: bool = True,
    title: str | None = None,
) -> dict[str, Any]:
    """Build a structured performance report with Rui-style segmentations."""
    initial = float(result.meta.get("initial_capital", RESEARCH["initial_capital"]))
    overall = metrics_to_jsonable(
        compute_metrics(result.equity, returns=result.returns, positions=result.positions)
    )

    # --- Regime (bull / bear) ---
    regime_section: dict[str, Any] = {}
    if benchmark is not None and not benchmark.empty:
        regimes = _regime_labels(benchmark)
        regimes = regimes.reindex(result.returns.index).fillna("unknown")
        for name in ("bull", "bear"):
            regime_section[name] = _segment_metrics_from_returns(
                result.returns, regimes == name, initial
            )
        regime_section["label_counts"] = {
            k: int(v) for k, v in regimes.value_counts().to_dict().items()
        }

    # --- Vol terciles on portfolio returns ---
    vol_labels = _vol_tercile_labels(result.returns)
    vol_section = {
        name: _segment_metrics_from_returns(result.returns, vol_labels == name, initial)
        for name in ("low", "mid", "high")
    }

    # --- Industry / sector attribution via per-ticker contribution ---
    industry_section: dict[str, Any] = {}
    if include_industry and not result.per_ticker_returns.empty:
        tickers = list(result.per_ticker_returns.columns)
        sectors = _ticker_sectors(tickers)
        contrib = result.per_ticker_returns.fillna(0.0)
        sector_returns = pd.DataFrame(index=contrib.index)
        for sector in sorted(set(sectors.values())):
            cols = [t for t in tickers if sectors[t] == sector]
            if cols:
                sector_returns[sector] = contrib[cols].sum(axis=1)
        for sector in sector_returns.columns:
            industry_section[sector] = _segment_metrics_from_returns(
                sector_returns[sector],
                sector_returns[sector].abs() > 0,
                initial,
            )
        industry_section["_ticker_sector_map"] = sectors

    baselines_section: dict[str, Any] = {}
    if baseline_results:
        for name, br in baseline_results.items():
            baselines_section[name] = metrics_to_jsonable(
                compute_metrics(br.equity, returns=br.returns, positions=br.positions)
            )

    report: dict[str, Any] = {
        "title": title or result.label or "backtest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": result.meta,
        "overall": overall,
        "segments": {
            "regime": regime_section,
            "volatility": vol_section,
            "industry": industry_section,
        },
        "baselines": baselines_section,
        "equity_curve": [
            {"date": d.strftime("%Y-%m-%d"), "equity": float(v)}
            for d, v in result.equity.items()
        ],
    }
    return report


def write_report(
    report: dict[str, Any],
    *,
    name: str | None = None,
    directory: Path | None = None,
) -> Path:
    """Write JSON + markdown summary under reports/."""
    directory = Path(directory or REPORTS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = name or report.get("title") or "backtest"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(stem))[:60]
    json_path = directory / f"{safe}_{stamp}.json"
    md_path = directory / f"{safe}_{stamp}.md"
    latest_json = directory / f"latest_{safe}.json"
    latest_md = directory / f"latest_{safe}.md"

    # Equity can be large — keep full in timestamped, thin equity in latest
    json_path.write_text(json.dumps(report, indent=2))
    slim = {k: v for k, v in report.items() if k != "equity_curve"}
    slim["equity_curve_len"] = len(report.get("equity_curve") or [])
    slim["equity_start"] = (report.get("equity_curve") or [{}])[0]
    slim["equity_end"] = (report.get("equity_curve") or [{}])[-1]
    latest_json.write_text(json.dumps(slim, indent=2))

    md = report_to_markdown(report)
    md_path.write_text(md)
    latest_md.write_text(md)
    return json_path


def report_to_markdown(report: dict[str, Any]) -> str:
    o = report.get("overall") or {}
    lines = [
        f"# {report.get('title', 'Backtest Report')}",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        "",
        "## Overall",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total return | {o.get('total_return', 0):.2%} |",
        f"| Ann. return | {o.get('annualized_return', 0):.2%} |",
        f"| Sharpe | {o.get('sharpe', 0):.3f} |",
        f"| Max drawdown | {o.get('max_drawdown', 0):.2%} |",
        f"| Hit rate | {o.get('hit_rate', 0):.2%} |",
        f"| Turnover | {o.get('turnover', 0):.4f} |",
        f"| Final equity | {o.get('final_equity', 0):,.2f} |",
        "",
    ]

    baselines = report.get("baselines") or {}
    if baselines:
        lines += ["## Baselines", "", "| Name | Sharpe | Total ret | Max DD | Hit rate |", "|---|---:|---:|---:|---:|"]
        for name, m in baselines.items():
            lines.append(
                f"| {name} | {m.get('sharpe', 0):.3f} | {m.get('total_return', 0):.2%} | "
                f"{m.get('max_drawdown', 0):.2%} | {m.get('hit_rate', 0):.2%} |"
            )
        lines.append("")

    segs = report.get("segments") or {}
    regime = segs.get("regime") or {}
    if regime:
        lines += ["## Regime (bull / bear)", ""]
        for name in ("bull", "bear"):
            m = regime.get(name) or {}
            lines.append(
                f"- **{name}**: Sharpe={m.get('sharpe', 0):.3f}, "
                f"return={m.get('total_return', 0):.2%}, hit={m.get('hit_rate', 0):.2%}"
            )
        lines.append("")

    vol = segs.get("volatility") or {}
    if vol:
        lines += ["## Volatility buckets", ""]
        for name in ("low", "mid", "high"):
            m = vol.get(name) or {}
            lines.append(
                f"- **{name} vol**: Sharpe={m.get('sharpe', 0):.3f}, "
                f"return={m.get('total_return', 0):.2%}"
            )
        lines.append("")

    industry = segs.get("industry") or {}
    if industry:
        lines += ["## Industry / sector", ""]
        for name, m in industry.items():
            if name.startswith("_") or not isinstance(m, dict):
                continue
            lines.append(
                f"- **{name}**: Sharpe={m.get('sharpe', 0):.3f}, "
                f"return={m.get('total_return', 0):.2%}"
            )
        lines.append("")

    return "\n".join(lines)
