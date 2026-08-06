"""Orchestrates pipeline, backtest, and agent modules for the control panel API."""

from __future__ import annotations

import os

from src.agents.horizon_agent import run_horizon_agent
from src.backtest.baselines import BASELINE_SIGNAL_FNS, run_baseline
from src.backtest.metrics import compute_metrics, metrics_to_jsonable, strategy_utility
from src.backtest.portfolio_sim import run_portfolio_backtest
from src.backtest.report import build_report
from src.backtest.splits import split_train_val_test
from src.config import HORIZONS, RESEARCH, TRADING
from src.portfolio.construction import combine_horizon_signals, construct_portfolio
from src.risk.engine.data_loader import fetch_benchmark, fetch_research_prices

from examples.load_pipeline_data import load_pipeline_data

from api.schemas import (
    AgentIteration,
    AgentRequest,
    AgentResponse,
    BacktestRequest,
    BacktestResponse,
    EquityPoint,
    LeaderboardRow,
    MetricsBlock,
    ResearchWindows,
    RunRequest,
    RunResponse,
    SplitWindow,
    WindowInfo,
)


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


def run_backtest(request: BacktestRequest) -> BacktestResponse:
    tickers = request.tickers or list(RESEARCH["tickers"][:6])
    prices, period_used = _fetch_prices(
        tickers,
        period=request.period,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if prices.empty or len(prices) < 30:
        raise ValueError("Not enough price history in the selected window (need ~30+ days).")

    result = run_portfolio_backtest(
        prices,
        initial_capital=request.initial_capital,
        max_position=request.max_position,
        gross_exposure=request.gross_exposure,
        target_volatility=request.target_volatility,
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
                )
                baseline_results[name] = br
                baselines[name] = _metrics_block(
                    metrics_to_jsonable(compute_metrics(br.equity, br.returns, br.positions))
                )
                baseline_curves[name] = _equity_points(br.equity, name)
            except Exception:
                continue

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
            # Align benchmark to price index
            benchmark = benchmark.reindex(prices.index).ffill().dropna()
        except Exception:
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
