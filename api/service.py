"""Orchestrates pipeline, backtest, and agent modules for the control panel API."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from src.agents.horizon_agent import run_horizon_agent
from src.backtest.baselines import BASELINE_SIGNAL_FNS, run_baseline
from src.backtest.execution import make_run_id
from src.backtest.metrics import compute_metrics, metrics_to_jsonable, strategy_utility
from src.backtest.portfolio_sim import run_portfolio_backtest
from src.backtest.report import build_report
from src.backtest.splits import split_train_val_test
from src.backtest.trades import TradeRecord, load_run_manifest, load_run_trades, write_run_artifacts
from src.config import HORIZONS, REPORTS_DIR, RESEARCH, TRADING
from src.portfolio.construction import combine_horizon_signals, construct_portfolio
from src.risk.engine.data_loader import fetch_benchmark, fetch_research_ohlc, fetch_research_prices
from src.risk.evaluation import evaluate_risk_methods

from examples.load_pipeline_data import load_pipeline_data

from api.schemas import (
    AgentIteration,
    AgentRequest,
    AgentResponse,
    AuditResponse,
    BacktestRequest,
    BacktestResponse,
    EquityPoint,
    LeaderboardRow,
    MetricsBlock,
    PositionPoint,
    ResearchWindows,
    RiskAuditResponse,
    RiskComparisonRow,
    RunRequest,
    RunResponse,
    SignalEventRow,
    SplitWindow,
    TradeAuditRow,
    TradesResponse,
    WindowInfo,
)

logger = logging.getLogger(__name__)

TRADE_CAP = 500
SIGNAL_CAP = 500
POSITION_CAP = 800


def run_pipeline(request: RunRequest) -> RunResponse:
    tickers = request.tickers or list(TRADING["tickers"])

    kwargs: dict = {"tickers": tickers}
    if request.target_volatility is not None:
        kwargs["target_volatility"] = request.target_volatility

    signals, volatilities, port_vol, target_vol = load_pipeline_data(**kwargs)

    conviction = {
        ticker: combine_horizon_signals(horizons)
        for ticker, horizons in signals.items()
    }

    weights = construct_portfolio(
        signals,
        volatilities,
        max_position=request.max_position,
        gross_exposure=request.gross_exposure,
        portfolio_volatility=port_vol,
        target_volatility=target_vol,
    )

    return RunResponse(
        tickers=list(signals.keys()),
        horizons=list(HORIZONS),
        signals=signals,
        conviction=conviction,
        volatilities=volatilities,
        portfolio_volatility=port_vol,
        target_volatility=target_vol,
        weights=weights,
    )


def _metrics_block(metrics: dict) -> MetricsBlock:
    m = dict(metrics)
    hit = float(m.get("signal_hit_rate") if m.get("signal_hit_rate") is not None else m.get("hit_rate") or 0.0)
    arr = float(m.get("annualized_return") or 0.0)
    if m.get("utility") is None:
        m["utility"] = strategy_utility(hit, arr)
    m.setdefault("signal_hit_rate", hit)
    keys = MetricsBlock.model_fields
    return MetricsBlock(**{k: float(m.get(k, 0.0) or 0.0) for k in keys})


def _research_windows(prices) -> ResearchWindows | None:
    try:
        splits = split_train_val_test(prices)
        d = splits.to_dict()
        def sw(block):
            if not block:
                return None
            return SplitWindow(
                start=block.get("start"),
                end=block.get("end"),
                n_days=block.get("n_days"),
            )
        return ResearchWindows(
            as_of=d.get("as_of"),
            train=sw(d.get("train")),
            val=sw(d.get("val")),
            test=sw(d.get("test")),
        )
    except Exception:
        return None


def _equity_points(equity, series: str) -> list[EquityPoint]:
    n = len(equity)
    step = max(1, n // 400)
    points: list[EquityPoint] = []
    for i, (dt, val) in enumerate(equity.items()):
        if i % step == 0 or i == n - 1:
            points.append(
                EquityPoint(
                    date=dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10],
                    equity=float(val),
                    series=series,
                )
            )
    return points


def _window_from_prices(prices, period_used: str | None) -> WindowInfo:
    start = prices.index.min()
    end = prices.index.max()
    return WindowInfo(
        start=start.strftime("%Y-%m-%d") if hasattr(start, "strftime") else str(start)[:10],
        end=end.strftime("%Y-%m-%d") if hasattr(end, "strftime") else str(end)[:10],
        n_days=int(len(prices)),
        period_used=period_used,
    )


def _fetch_prices(
    tickers: list[str],
    *,
    period: str,
    start_date: str | None,
    end_date: str | None,
):
    if start_date and end_date:
        return fetch_research_prices(
            tickers, period=period, start=start_date, end=end_date
        ), None
    return fetch_research_prices(tickers, period=period), period


def _trade_row(trade: TradeRecord | dict) -> TradeAuditRow:
    payload = trade.to_audit_dict() if isinstance(trade, TradeRecord) else dict(trade)
    if "return_" in payload and "return" not in payload:
        payload["return"] = payload.pop("return_")
    return TradeAuditRow.model_validate(payload)


def _signal_row(event) -> SignalEventRow:
    payload = event.model_dump() if hasattr(event, "model_dump") else dict(event)
    if "signal_side" in payload and hasattr(payload["signal_side"], "value"):
        payload["signal_side"] = payload["signal_side"].value
    return SignalEventRow.model_validate(payload)


def _position_history(weights: object, cap: int = POSITION_CAP) -> list[PositionPoint]:
    if weights is None or getattr(weights, "empty", True):
        return []
    points: list[PositionPoint] = []
    for dt, row in weights.iterrows():
        date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        for ticker, val in row.items():
            w = float(val or 0.0)
            if abs(w) < 1e-8:
                continue
            points.append(PositionPoint(date=date, ticker=str(ticker), weight=w))
            if len(points) >= cap:
                return points
    return points


def run_backtest(request: BacktestRequest) -> BacktestResponse:
    tickers = request.tickers or list(RESEARCH["tickers"][:6])
    ohlc = fetch_research_ohlc(
        tickers,
        period=request.period,
        start=request.start_date,
        end=request.end_date,
    )
    prices = ohlc.get("Close")
    period_used = None if request.start_date and request.end_date else request.period
    if prices is None or prices.empty or len(prices) < 30:
        prices, period_used = _fetch_prices(
            tickers,
            period=request.period,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        ohlc = {"Close": prices}
    if prices.empty or len(prices) < 30:
        raise ValueError("Not enough price history in the selected window (need ~30+ days).")

    run_id = make_run_id("bt")
    result = run_portfolio_backtest(
        prices,
        initial_capital=request.initial_capital,
        max_position=request.max_position,
        gross_exposure=request.gross_exposure,
        target_volatility=request.target_volatility,
        open_px=ohlc.get("Open"),
        high=ohlc.get("High"),
        low=ohlc.get("Low"),
        rebalance_every=request.rebalance_every,
        take_profit_pct=request.take_profit_pct,
        stop_loss_pct=request.stop_loss_pct,
        side_mode=request.side_mode,
        cost_bps=request.cost_bps,
        slippage_bps=request.slippage_bps,
        write_artifacts=True,
        run_id=run_id,
    )
    metrics = metrics_to_jsonable(
        compute_metrics(result.equity, result.returns, result.positions)
    )

    baselines: dict[str, MetricsBlock] = {}
    baseline_curves: dict[str, list[EquityPoint]] = {}
    baseline_results = {}
    if request.include_baselines:
        names = [n for n in request.baselines if n in BASELINE_SIGNAL_FNS]
        if not names:
            names = ["buy_and_hold", "sma_cross"]
        for name in names:
            try:
                br = run_baseline(
                    prices,
                    name,
                    initial_capital=request.initial_capital,
                    open_px=ohlc.get("Open"),
                    high=ohlc.get("High"),
                    low=ohlc.get("Low"),
                )
                baseline_results[name] = br
                baselines[name] = _metrics_block(
                    metrics_to_jsonable(compute_metrics(br.equity, br.returns, br.positions))
                )
                baseline_curves[name] = _equity_points(br.equity, name)
            except (ValueError, KeyError) as exc:
                logger.warning("Baseline %s skipped: %s", name, exc)

    segments: dict = {}
    if request.include_segments:
        benchmark = None
        try:
            if request.start_date and request.end_date:
                benchmark = fetch_benchmark(
                    start=request.start_date, end=request.end_date
                )
            else:
                benchmark = fetch_benchmark(period=request.period)
            benchmark = benchmark.reindex(prices.index).ffill().dropna()
        except ValueError as exc:
            logger.warning("Benchmark unavailable: %s", exc)
            benchmark = None

        include_industry = len(list(prices.columns)) <= 10
        report = build_report(
            result,
            benchmark=benchmark,
            baseline_results=baseline_results or None,
            include_industry=include_industry,
            title="control_panel_backtest",
        )
        segments = report.get("segments") or {}

    daily_ret = prices.pct_change().dropna(how="all")
    risk_rows = evaluate_risk_methods(daily_ret)
    risk_models = [RiskComparisonRow.model_validate(r) for r in risk_rows]

    trades = [_trade_row(t) for t in (result.trades or [])]
    events = [_signal_row(e) for e in (result.signal_events or [])]
    trades_truncated = len(trades) > TRADE_CAP
    events_truncated = len(events) > SIGNAL_CAP

    extra = {
        "risk_comparison": [r.model_dump() for r in risk_models],
        "signal_events": [e.model_dump() for e in events],
        "n_signal_events": len(events),
        "label": "control_panel_backtest",
        "tickers": list(prices.columns),
    }
    artifacts = dict(result.artifact_paths or {})
    if not artifacts:
        artifacts = write_run_artifacts(
            run_id,
            trades=result.trades or [],
            config=result.trading_rules or {},
            extra=extra,
        )
    else:
        manifest_path = Path(artifacts.get("directory") or (REPORTS_DIR / run_id)) / "manifest.json"
        try:
            payload = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
            payload.update(extra)
            payload["run_id"] = run_id
            manifest_path.write_text(json.dumps(payload, indent=2, default=str))
        except OSError as exc:
            logger.warning("Could not update manifest: %s", exc)
        (REPORTS_DIR / run_id / "risk.json").write_text(
            json.dumps([r.model_dump() for r in risk_models], indent=2)
        )
        (REPORTS_DIR / run_id / "signals.json").write_text(
            json.dumps([e.model_dump() for e in events], indent=2)
        )

    rel_paths = {
        k: v
        for k, v in artifacts.items()
        if k != "directory" and isinstance(v, str)
    }

    return BacktestResponse(
        tickers=list(prices.columns),
        initial_capital=request.initial_capital,
        window=_window_from_prices(prices, period_used),
        research_windows=_research_windows(prices),
        metrics=_metrics_block(metrics),
        baselines=baselines,
        equity_curve=_equity_points(result.equity, "strategy"),
        baseline_curves=baseline_curves,
        segments=segments,
        portfolios={},
        run_id=run_id,
        trading_rules=result.trading_rules or {},
        trades=trades[:TRADE_CAP],
        trades_truncated=trades_truncated,
        signal_events=events[:SIGNAL_CAP],
        signal_events_truncated=events_truncated,
        position_history=_position_history(result.weights_history),
        risk_comparison=risk_models,
        artifact_paths=rel_paths,
    )


def get_backtest_trades(run_id: str) -> TradesResponse:
    rows = load_run_trades(run_id)
    return TradesResponse(run_id=run_id, trades=[_trade_row(r) for r in rows])


def get_backtest_audit(run_id: str) -> AuditResponse:
    manifest = load_run_manifest(run_id)
    trades = load_run_trades(run_id)
    signals_path = REPORTS_DIR / run_id / "signals.json"
    events: list[SignalEventRow] = []
    if signals_path.exists():
        raw = json.loads(signals_path.read_text())
        events = [_signal_row(e) for e in raw]
    config_path = REPORTS_DIR / run_id / "config.json"
    rules = json.loads(config_path.read_text()) if config_path.exists() else {}
    paths = manifest.get("paths") or {}
    return AuditResponse(
        run_id=run_id,
        trading_rules=rules,
        trades=[_trade_row(r) for r in trades],
        signal_events=events,
        artifact_paths={k: str(v) for k, v in paths.items()},
    )


def get_backtest_risk(run_id: str) -> RiskAuditResponse:
    path = REPORTS_DIR / run_id / "risk.json"
    if not path.exists():
        raise FileNotFoundError(f"No risk comparison for run_id={run_id!r}")
    rows = json.loads(path.read_text())
    return RiskAuditResponse(
        run_id=run_id,
        risk_comparison=[RiskComparisonRow.model_validate(r) for r in rows],
    )


def run_agent(request: AgentRequest) -> AgentResponse:
    if request.horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {request.horizon}. Choose from {HORIZONS}.")

    tickers = request.tickers or list(RESEARCH["tickers"][:6])
    prices, period_used = _fetch_prices(
        tickers,
        period=request.period,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if prices.empty or len(prices) < 80:
        raise ValueError("Not enough price history for agent loop (need ~80+ days).")

    bench_sym = RESEARCH.get("benchmark") or "SPY"
    benchmark = None
    try:
        if request.start_date and request.end_date:
            benchmark = fetch_benchmark(
                symbol=bench_sym, start=request.start_date, end=request.end_date
            )
        else:
            benchmark = fetch_benchmark(symbol=bench_sym, period=request.period)
        benchmark = benchmark.reindex(prices.index).ffill().dropna()
    except Exception:
        try:
            if request.start_date and request.end_date:
                benchmark = fetch_benchmark(start=request.start_date, end=request.end_date)
            else:
                benchmark = fetch_benchmark(period=request.period)
            benchmark = benchmark.reindex(prices.index).ffill().dropna()
        except Exception:
            benchmark = None

    summary = run_horizon_agent(
        prices,
        horizon=request.horizon,
        n_iterations=request.n_iterations,
        initial_capital=request.initial_capital,
        benchmark=benchmark,
        use_llm=bool(os.environ.get("OPENAI_API_KEY")),
        seed_baselines=request.seed_baselines,
        as_of=request.end_date,
    )

    rw = None
    if summary.windows:
        def sw(block):
            if not block:
                return None
            return SplitWindow(
                start=block.get("start"),
                end=block.get("end"),
                n_days=block.get("n_days"),
            )
        rw = ResearchWindows(
            as_of=summary.windows.get("as_of"),
            train=sw(summary.windows.get("train")),
            val=sw(summary.windows.get("val")),
            test=sw(summary.windows.get("test")),
        )

    iterations = [
        AgentIteration(
            iteration=a.iteration,
            hypothesis=a.hypothesis.description,
            template=a.hypothesis.template,
            params={k: float(v) for k, v in (a.hypothesis.params or {}).items()},
            name=a.hypothesis.name or "",
            train_sharpe=(
                float(a.train_metrics["sharpe"])
                if a.train_metrics.get("sharpe") is not None
                else None
            ),
            val_sharpe=(
                float(a.val_metrics["sharpe"])
                if a.val_metrics.get("sharpe") is not None
                else None
            ),
            test_sharpe=(
                float(a.test_metrics["sharpe"])
                if a.test_metrics.get("sharpe") is not None
                else None
            ),
            utility=float(a.utility) if a.utility is not None else None,
            insights=a.insights or "",
            code_hash=a.code_hash or "",
            portfolios=(a.performance or {}).get("portfolios") or {},
            test_summary=(a.performance or {}).get("test_summary") or {},
            source=getattr(a.hypothesis, "source", "") or "",
        )
        for a in summary.iterations
    ]

    leaderboard = [
        LeaderboardRow(
            iteration=int(r.get("iteration") or 0),
            name=str(r.get("name") or ""),
            template=str(r.get("template") or ""),
            test_utility=(
                float(r["test_utility"]) if r.get("test_utility") is not None else None
            ),
            test_sharpe=(
                float(r["test_sharpe"]) if r.get("test_sharpe") is not None else None
            ),
            test_hit=float(r["test_hit"]) if r.get("test_hit") is not None else None,
            code_hash=str(r.get("code_hash") or ""),
        )
        for r in (summary.leaderboard or [])
    ]

    return AgentResponse(
        horizon=request.horizon,
        window=_window_from_prices(prices, period_used),
        research_windows=rw,
        tickers=list(prices.columns),
        run_dir=summary.run_dir,
        best_iteration=summary.best_iteration,
        best_test_sharpe=float(summary.best_test_sharpe)
        if summary.best_test_sharpe != float("-inf")
        else 0.0,
        best_test_utility=float(summary.best_test_utility)
        if summary.best_test_utility != float("-inf")
        else 0.0,
        iterations=iterations,
        leaderboard=leaderboard,
        utility_curve=summary.utility_curve or [],
        catalog_path=summary.catalog_path or "",
    )
