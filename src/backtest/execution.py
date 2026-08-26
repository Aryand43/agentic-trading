"""Point-in-time trade execution: T+1 open, TP/SL, horizon exit, costs, audit.

This module is the shared backtest loop. ``run_signal_backtest`` and
``run_portfolio_backtest`` wrap it so existing callers keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult
from src.backtest.trades import (
    ExitReason,
    PositionDirection,
    SignalEvent,
    SignalSide,
    TradeRecord,
    classify_side,
    new_trade_id,
    write_run_artifacts,
)
from src.backtest.trading_rules import TradingRules, default_trading_rules
from src.portfolio.construction import combine_horizon_signals, construct_portfolio
from src.signals.strategies import get_signal

SignalFn = Callable[[pd.Series], float]


def _fmt(ts: Any) -> str:
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d")
    return str(ts)[:10]


def _bar_price(frame: pd.DataFrame | None, i: int, ticker: str) -> float | None:
    if frame is None or ticker not in frame.columns:
        return None
    val = frame.iloc[i][ticker]
    if pd.isna(val) or float(val) <= 0:
        return None
    return float(val)


def _daily_vol(returns: pd.Series, window: int = 63) -> float:
    clean = returns.dropna()
    if len(clean) < 5:
        return 0.20
    w = min(window, len(clean))
    return float(clean.tail(w).std() * np.sqrt(252))


def _abs_portfolio_vol(weights: dict[str, float], returns: pd.DataFrame, window: int = 63) -> float:
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return 0.0
    w = np.array([weights[t] for t in tickers], dtype=float)
    ret = returns[tickers].dropna(how="all").fillna(0.0)
    if len(ret) < 5:
        return float(np.sqrt(np.dot(w, w)) * 0.20)
    sample = ret.tail(min(window, len(ret)))
    cov = sample.cov().values
    var = float(np.dot(w, np.dot(cov, w)))
    return float(np.sqrt(max(var, 0.0)) * np.sqrt(252))


def make_run_id(prefix: str = "bt") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


@dataclass
class _Lot:
    trade: TradeRecord
    signal_idx: int
    fill_idx: int
    max_exit_idx: int
    direction: int
    pending: bool = True
    quantity: float = 0.0


@dataclass
class ExecutionResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
    per_ticker_positions: pd.DataFrame
    per_ticker_returns: pd.DataFrame
    weights_history: pd.DataFrame
    conviction_history: pd.DataFrame
    trades: list[TradeRecord] = field(default_factory=list)
    signal_events: list[SignalEvent] = field(default_factory=list)
    trading_rules: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    artifact_paths: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def _tp_sl_prices(entry: float, direction: int, rules: TradingRules) -> tuple[float | None, float | None]:
    tp = sl = None
    if rules.take_profit_pct > 0:
        tp = entry * (1.0 + direction * rules.take_profit_pct)
    if rules.stop_loss_pct > 0:
        sl = entry * (1.0 - direction * rules.stop_loss_pct)
    return tp, sl


def _intraday_exit(
    *,
    direction: int,
    open_px: float,
    high: float | None,
    low: float | None,
    close_px: float,
    tp: float | None,
    sl: float | None,
) -> tuple[float, ExitReason] | None:
    """Conservative same-bar TP/SL. Stop-loss wins if both levels trade."""
    high_px = high if high is not None else close_px
    low_px = low if low is not None else close_px

    hit_sl = False
    hit_tp = False
    sl_fill = sl
    tp_fill = tp

    if sl is not None:
        if direction > 0:
            if open_px <= sl:
                hit_sl, sl_fill = True, open_px
            elif low_px <= sl:
                hit_sl, sl_fill = True, sl
        else:
            if open_px >= sl:
                hit_sl, sl_fill = True, open_px
            elif high_px >= sl:
                hit_sl, sl_fill = True, sl
    if tp is not None:
        if direction > 0:
            if open_px >= tp:
                hit_tp, tp_fill = True, open_px
            elif high_px >= tp:
                hit_tp, tp_fill = True, tp
        else:
            if open_px <= tp:
                hit_tp, tp_fill = True, open_px
            elif low_px <= tp:
                hit_tp, tp_fill = True, tp

    if hit_sl:
        return float(sl_fill), ExitReason.stop_loss
    if hit_tp:
        return float(tp_fill), ExitReason.take_profit
    return None


def _sleeve_weights(
    *,
    tickers: list[str],
    signals: dict[str, dict[str, float]],
    ticker_weights: dict[str, float],
    rules: TradingRules,
) -> dict[tuple[str, str], float]:
    """Split each ticker's constructed weight across active agreeing horizons."""
    sleeves: dict[tuple[str, str], float] = {}
    for ticker in tickers:
        tw = float(ticker_weights.get(ticker, 0.0))
        if abs(tw) < 1e-12:
            continue
        parts: list[tuple[str, float]] = []
        for horizon, score in (signals.get(ticker) or {}).items():
            side = classify_side(
                score,
                long_threshold=rules.long_threshold,
                short_threshold=rules.short_threshold,
                side_mode=rules.side_mode.value,
            )
            if side is SignalSide.neutral:
                continue
            signed = 1.0 if side is SignalSide.buy else -1.0
            if signed * tw < 0:
                continue
            parts.append((horizon, abs(float(score))))
        total = sum(p[1] for p in parts) or len(parts)
        for horizon, mag in parts:
            sleeves[(ticker, horizon)] = tw * (mag / total if total else 1.0)
    return sleeves


def simulate(
    close: pd.DataFrame,
    *,
    rules: TradingRules | None = None,
    signal_fn: SignalFn | None = None,
    horizon: str | None = None,
    open_px: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
    use_multi_horizon: bool = False,
    run_id: str | None = None,
    label: str = "",
    write_artifacts: bool = False,
    data_version: str | None = None,
) -> ExecutionResult:
    """Walk daily bars with T+1 fills, TP/SL, horizon exits, and an audit log."""
    if close is None or close.empty:
        raise ValueError("prices panel is empty")

    close = close.sort_index().astype(float)
    tickers = list(close.columns)
    n = len(tickers)
    rules = rules or default_trading_rules()
    run_id = run_id or make_run_id()
    config_version = "trading_rules.v1"
    has_open = open_px is not None and not open_px.empty
    price_source_default = "open" if has_open else "close"

    if use_multi_horizon:
        horizons = list(rules.horizons)
    else:
        horizons = [horizon or (rules.horizons[0] if rules.horizons else "10d")]
        if signal_fn is None:
            h = horizons[0]

            def signal_fn(prices: pd.Series, _h: str = h) -> float:
                return get_signal("", _h, prices)

    warmup = min(int(rules.warmup_bars), max(5, len(close) - 3))
    dates = list(close.index)
    if len(dates) <= warmup + 2:
        raise ValueError(
            f"Need more history than warmup ({warmup}); only have {len(dates)} bars."
        )

    log_ret = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan)

    cash = float(rules.initial_capital)
    lots: list[_Lot] = []
    closed: list[TradeRecord] = []
    events: list[SignalEvent] = []
    seq = 0
    cost_rate = rules.cost_rate()

    equity_vals: list[float] = []
    ret_vals: list[float] = []
    pos_vals: list[float] = []
    pos_matrix: list[np.ndarray] = []
    ret_matrix: list[np.ndarray] = []
    w_hist: list[dict[str, float]] = []
    conv_hist: list[dict[str, float]] = []
    equity_index: list = []
    prev_equity = float(rules.initial_capital)
    prev_close = {t: float(close.iloc[0][t]) if pd.notna(close.iloc[0][t]) else 0.0 for t in tickers}
    last_conviction: dict[str, float] = {t: 0.0 for t in tickers}

    def marked_equity() -> float:
        total = cash
        for lot in lots:
            if lot.pending or lot.quantity == 0:
                continue
            px = _bar_price(close, i, lot.trade.ticker)
            if px is None:
                continue
            total += lot.quantity * px
        return float(total)

    def close_lot(lot: _Lot, exit_idx: int, exit_price: float, reason: ExitReason, src: str) -> None:
        nonlocal cash, seq
        trade = lot.trade
        if lot.pending:
            trade.exit_reason = ExitReason.rejected
            trade.exit_date = _fmt(dates[exit_idx])
            trade.gross_pnl = 0.0
            trade.net_pnl = -float(trade.transaction_cost)
            trade.return_ = 0.0
            closed.append(trade)
            return
        qty = lot.quantity
        exit_cost = cost_rate * abs(qty * exit_price)
        cash += qty * exit_price - exit_cost
        gross = qty * (exit_price - float(trade.entry_price or exit_price))
        trade.exit_date = _fmt(dates[exit_idx])
        trade.exit_price = float(exit_price)
        trade.exit_reason = reason
        trade.gross_pnl = float(gross)
        trade.transaction_cost = float(trade.transaction_cost + exit_cost)
        trade.net_pnl = float(gross - trade.transaction_cost)
        denom = abs(float(trade.notional) or abs(qty * float(trade.entry_price or 1.0)))
        trade.return_ = float(gross / denom) if denom else 0.0
        trade.price_source = src
        closed.append(trade)

    for i, dt in enumerate(dates):
        if i == 0:
            continue

        # --- Fill pending entries at this bar ---
        still: list[_Lot] = []
        for lot in lots:
            if lot.pending and i == lot.fill_idx:
                ticker = lot.trade.ticker
                fill = _bar_price(open_px, i, ticker) if has_open else None
                src = "open"
                if fill is None:
                    fill = _bar_price(close, i, ticker)
                    src = "close"
                if fill is None:
                    close_lot(lot, i, 0.0, ExitReason.rejected, src)
                    continue
                equity_now = marked_equity()
                notional = abs(lot.trade.portfolio_weight) * max(equity_now, 0.0)
                if notional <= 0:
                    close_lot(lot, i, fill, ExitReason.rejected, src)
                    continue
                qty = lot.direction * notional / fill
                entry_cost = cost_rate * notional
                cash -= qty * fill + entry_cost
                lot.pending = False
                lot.quantity = qty
                tp, sl = _tp_sl_prices(fill, lot.direction, rules)
                lot.trade.entry_date = _fmt(dt)
                lot.trade.entry_price = fill
                lot.trade.quantity = qty
                lot.trade.notional = notional
                lot.trade.take_profit_threshold = tp
                lot.trade.stop_loss_threshold = sl
                lot.trade.transaction_cost = entry_cost
                lot.trade.price_source = src
                still.append(lot)
            elif lot.pending and i > lot.fill_idx:
                close_lot(lot, i, _bar_price(close, i, lot.trade.ticker) or 0.0, ExitReason.rejected, "close")
            else:
                still.append(lot)
        lots = still

        # --- TP / SL on open lots (including entry bar) ---
        still = []
        for lot in lots:
            if lot.pending:
                still.append(lot)
                continue
            ticker = lot.trade.ticker
            o = _bar_price(open_px, i, ticker) if has_open else _bar_price(close, i, ticker)
            c = _bar_price(close, i, ticker)
            if o is None or c is None:
                still.append(lot)
                continue
            hit = _intraday_exit(
                direction=lot.direction,
                open_px=o,
                high=_bar_price(high, i, ticker),
                low=_bar_price(low, i, ticker),
                close_px=c,
                tp=lot.trade.take_profit_threshold,
                sl=lot.trade.stop_loss_threshold,
            )
            if hit is not None:
                px, reason = hit
                src = lot.trade.price_source or price_source_default
                if reason is ExitReason.take_profit and _bar_price(high, i, ticker) is None:
                    src = "close"
                if reason is ExitReason.stop_loss and _bar_price(low, i, ticker) is None:
                    src = "close"
                if (reason is ExitReason.take_profit and o == px) or (
                    reason is ExitReason.stop_loss and o == px
                ):
                    src = "open" if has_open else "close"
                close_lot(lot, i, px, reason, src)
            else:
                still.append(lot)
        lots = still

        # --- Forced horizon / end-of-data at close ---
        last_bar = i == len(dates) - 1
        still = []
        for lot in lots:
            if lot.pending:
                if last_bar:
                    close_lot(lot, i, _bar_price(close, i, lot.trade.ticker) or 0.0, ExitReason.rejected, "close")
                else:
                    still.append(lot)
                continue
            c = _bar_price(close, i, lot.trade.ticker)
            if c is None:
                if last_bar:
                    close_lot(lot, i, float(lot.trade.entry_price or 0.0), ExitReason.end_of_data, "close")
                else:
                    still.append(lot)
                continue
            if last_bar:
                close_lot(lot, i, c, ExitReason.end_of_data, "close")
            elif i >= lot.max_exit_idx:
                close_lot(lot, i, c, ExitReason.horizon_end, "close")
            else:
                still.append(lot)
        lots = still

        equity = marked_equity()
        port_ret = float(equity / prev_equity - 1.0) if prev_equity else 0.0
        asset_pnl = np.zeros(n)
        weights_now = np.zeros(n)
        for lot in lots:
            if lot.pending:
                continue
            j = tickers.index(lot.trade.ticker)
            px = _bar_price(close, i, lot.trade.ticker) or 0.0
            prev = prev_close.get(lot.trade.ticker) or px
            if prev > 0 and px > 0:
                asset_pnl[j] += lot.quantity * (px - prev)
            if equity > 0 and px > 0:
                weights_now[j] += lot.quantity * px / equity

        equity_vals.append(equity)
        ret_vals.append(port_ret)
        pos_vals.append(float(weights_now.sum()))
        pos_matrix.append(weights_now.copy())
        ret_matrix.append(asset_pnl.copy() / prev_equity if prev_equity else asset_pnl.copy())
        equity_index.append(dt)
        w_hist.append({"date": dt, **{t: float(weights_now[j]) for j, t in enumerate(tickers)}})
        conv_hist.append({"date": dt, **last_conviction})
        prev_equity = equity
        prev_close = {
            t: float(close.iloc[i][t]) if pd.notna(close.iloc[i][t]) else prev_close[t]
            for t in tickers
        }

        # --- Signals and rebalance after close (data through i only) ---
        if i >= warmup and (i - warmup) % rules.rebalance_every == 0 and not last_bar:
            hist_prices = close.iloc[: i + 1]
            hist_returns = log_ret.iloc[: i + 1].fillna(0.0)
            signals: dict[str, dict[str, float]] = {t: {} for t in tickers}
            vols: dict[str, float] = {}
            for t in tickers:
                series = hist_prices[t].dropna()
                for h in horizons:
                    try:
                        if use_multi_horizon:
                            score = float(np.clip(get_signal(t, h, series), -1.0, 1.0))
                        else:
                            score = float(np.clip(signal_fn(series), -1.0, 1.0))
                    except (ValueError, ZeroDivisionError, KeyError):
                        score = 0.0
                    if rules.side_mode.value == "long_only" and score < 0:
                        score = 0.0
                    signals[t][h] = score
                vols[t] = _daily_vol(hist_returns[t])

            last_conviction = {t: combine_horizon_signals(signals[t]) for t in tickers}

            if use_multi_horizon:
                prelim = construct_portfolio(
                    signals,
                    vols,
                    max_position=rules.max_position,
                    gross_exposure=rules.gross_exposure,
                )
                port_vol = _abs_portfolio_vol(prelim, hist_returns)
                ticker_weights = construct_portfolio(
                    signals,
                    vols,
                    max_position=rules.max_position,
                    gross_exposure=rules.gross_exposure,
                    portfolio_volatility=port_vol if port_vol > 0 else None,
                    target_volatility=rules.target_volatility if port_vol > 0 else None,
                    max_leverage=rules.max_leverage,
                )
            else:
                ticker_weights = {}
                for t in tickers:
                    score = signals[t][horizons[0]]
                    ticker_weights[t] = float(np.clip(score, -1.0, 1.0)) / n
                    if rules.side_mode.value == "long_only":
                        ticker_weights[t] = max(ticker_weights[t], 0.0)

            new_sleeves = _sleeve_weights(
                tickers=tickers,
                signals=signals,
                ticker_weights=ticker_weights,
                rules=rules,
            )

            for t in tickers:
                for h, score in signals[t].items():
                    side = classify_side(
                        score,
                        long_threshold=rules.long_threshold,
                        short_threshold=rules.short_threshold,
                        side_mode=rules.side_mode.value,
                    )
                    events.append(
                        SignalEvent(
                            date=_fmt(dt),
                            ticker=t,
                            horizon=h,
                            signal_value=float(score),
                            signal_side=side,
                            conviction=last_conviction.get(t),
                            weight=new_sleeves.get((t, h), 0.0),
                        )
                    )

            open_keys = {(lot.trade.ticker, lot.trade.signal_horizon) for lot in lots}
            desired_keys = set(new_sleeves.keys())

            still = []
            for lot in lots:
                key = (lot.trade.ticker, lot.trade.signal_horizon)
                if key not in desired_keys:
                    c = _bar_price(close, i, lot.trade.ticker)
                    if lot.pending:
                        close_lot(lot, i, c or 0.0, ExitReason.rejected, "close")
                    elif c is not None:
                        close_lot(lot, i, c, ExitReason.rebalance, "close")
                    else:
                        still.append(lot)
                else:
                    still.append(lot)
            lots = still
            open_keys = {(lot.trade.ticker, lot.trade.signal_horizon) for lot in lots}

            fill_idx = i + int(rules.signal_lag_bars)
            for key, weight in new_sleeves.items():
                if key in open_keys:
                    continue
                ticker, h = key
                if abs(weight) < 1e-12:
                    continue
                if fill_idx >= len(dates):
                    seq += 1
                    closed.append(
                        TradeRecord(
                            trade_id=new_trade_id(run_id, seq),
                            ticker=ticker,
                            signal_date=_fmt(dt),
                            signal_horizon=h,
                            signal_value=float(signals[ticker][h]),
                            signal_side=classify_side(
                                signals[ticker][h],
                                long_threshold=rules.long_threshold,
                                short_threshold=rules.short_threshold,
                                side_mode=rules.side_mode.value,
                            ),
                            exit_reason=ExitReason.rejected,
                            portfolio_weight=float(weight),
                            data_version=data_version,
                            config_version=config_version,
                            price_source=price_source_default,
                        )
                    )
                    continue
                score = float(signals[ticker][h])
                side = classify_side(
                    score,
                    long_threshold=rules.long_threshold,
                    short_threshold=rules.short_threshold,
                    side_mode=rules.side_mode.value,
                )
                direction = 1 if weight > 0 else -1
                seq += 1
                holding = rules.holding_bars(h)
                max_exit_idx = min(i + holding, len(dates) - 1)
                rec = TradeRecord(
                    trade_id=new_trade_id(run_id, seq),
                    ticker=ticker,
                    signal_date=_fmt(dt),
                    signal_horizon=h,
                    signal_value=score,
                    signal_side=side,
                    position_direction=PositionDirection.long if direction > 0 else PositionDirection.short,
                    portfolio_weight=float(weight),
                    data_version=data_version,
                    config_version=config_version,
                    price_source=price_source_default,
                )
                lots.append(
                    _Lot(
                        trade=rec,
                        signal_idx=i,
                        fill_idx=fill_idx,
                        max_exit_idx=max_exit_idx,
                        direction=direction,
                        pending=True,
                    )
                )

    idx = pd.DatetimeIndex(equity_index)
    artifacts: dict[str, str] = {}
    if write_artifacts:
        artifacts = write_run_artifacts(
            run_id,
            trades=closed,
            config=rules.to_jsonable(),
            extra={
                "label": label,
                "tickers": tickers,
                "n_signal_events": len(events),
            },
        )

    return ExecutionResult(
        equity=pd.Series(equity_vals, index=idx, name="equity"),
        returns=pd.Series(ret_vals, index=idx, name="returns"),
        positions=pd.Series(pos_vals, index=idx, name="net_exposure"),
        per_ticker_positions=pd.DataFrame(pos_matrix, index=idx, columns=tickers),
        per_ticker_returns=pd.DataFrame(ret_matrix, index=idx, columns=tickers),
        weights_history=pd.DataFrame(w_hist).set_index("date") if w_hist else pd.DataFrame(),
        conviction_history=pd.DataFrame(conv_hist).set_index("date") if conv_hist else pd.DataFrame(),
        trades=closed,
        signal_events=events,
        trading_rules=rules.to_jsonable(),
        run_id=run_id,
        artifact_paths=artifacts,
        meta={
            "horizon": horizons[0] if len(horizons) == 1 else "multi",
            "horizons": horizons,
            "initial_capital": rules.initial_capital,
            "cost_bps": rules.cost_bps,
            "slippage_bps": rules.slippage_bps,
            "warmup": warmup,
            "rebalance_every": rules.rebalance_every,
            "max_position": rules.max_position,
            "gross_exposure": rules.gross_exposure,
            "target_volatility": rules.target_volatility,
            "tickers": tickers,
            "run_id": run_id,
            "price_source": price_source_default,
            "n_trades": len(closed),
        },
    )


def result_from_execution(ex: ExecutionResult, prices: pd.DataFrame, label: str = "") -> BacktestResult:
    return BacktestResult(
        equity=ex.equity,
        returns=ex.returns,
        positions=ex.positions,
        per_ticker_positions=ex.per_ticker_positions,
        per_ticker_returns=ex.per_ticker_returns,
        prices=prices,
        label=label,
        meta=ex.meta,
        trades=ex.trades,
        signal_events=ex.signal_events,
        trading_rules=ex.trading_rules,
        run_id=ex.run_id,
        artifact_paths=ex.artifact_paths,
        weights_history=ex.weights_history,
    )
