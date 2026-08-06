"""Market data ingestion for live desk and research/backtest modes.

Live: daily multi-month history first (cache-friendly); intraday last.
Research: multi-year daily bars with on-disk caching; supports explicit
start/end date windows for the research control panel.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.config import DATA_CACHE_DIR, RESEARCH, TRADING

# Live desk prefers daily history first (signals + cache). Intraday is last resort.
_LIVE_FALLBACKS: list[tuple[str, str]] = [
    ("1y", "1d"),
    ("3y", "1d"),
    ("5y", "1d"),
    ("3mo", "1d"),
    ("1mo", "1h"),
    ("10d", "15m"),
    ("5d", "5m"),
    ("5d", "1m"),
]


def _normalize_close(raw: pd.DataFrame | pd.Series, tickers: list[str]) -> pd.DataFrame:
    """Return a clean DateIndex x ticker Close panel."""
    if isinstance(raw, pd.Series):
        frame = raw.to_frame(name=tickers[0] if tickers else "Close")
    else:
        if isinstance(raw.columns, pd.MultiIndex):
            level0 = raw.columns.get_level_values(0)
            level1 = raw.columns.get_level_values(1)
            if "Close" in level0:
                frame = raw["Close"].copy()
            elif "Close" in level1:
                frame = raw.xs("Close", axis=1, level=1).copy()
            else:
                frame = raw.copy()
        else:
            frame = raw.copy()
            if "Close" in frame.columns and len(tickers) == 1:
                frame = frame[["Close"]].rename(columns={"Close": tickers[0]})
            elif len(tickers) == 1 and frame.shape[1] == 1:
                frame.columns = tickers

    frame.columns = [str(c) for c in frame.columns]
    missing = [t for t in tickers if t not in frame.columns]
    if missing and len(frame.columns) == len(tickers) and not any(
        c in frame.columns for c in tickers
    ):
        frame.columns = tickers
        missing = []
    if missing:
        present = [t for t in tickers if t in frame.columns]
        if not present:
            raise ValueError(f"No data returned for requested tickers. Missing: {missing}")
        tickers = present

    frame = frame[tickers].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(how="all")
    if frame.empty:
        raise ValueError(f"Close panel empty after cleaning for {tickers}")
    if isinstance(frame.index, pd.DatetimeIndex):
        frame.index = frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
    return frame.sort_index()


def _slice_window(
    frame: pd.DataFrame,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    """Restrict panel to [start, end] inclusive when dates are provided."""
    if frame.empty or (not start and not end):
        return frame
    out = frame
    if start:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end:
        # include end calendar day fully
        out = out.loc[out.index <= pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    if out.empty:
        raise ValueError(f"No rows in window start={start!r} end={end!r}")
    return out


def _cache_key(
    tickers: list[str],
    period: str | None,
    interval: str,
    provider: str,
    start: str | None = None,
    end: str | None = None,
) -> str:
    payload = json.dumps(
        {
            "tickers": sorted(tickers),
            "period": period,
            "interval": interval,
            "provider": provider,
            "start": start,
            "end": end,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _cache_paths(key: str) -> tuple[Path, Path]:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_CACHE_DIR / f"{key}.pkl", DATA_CACHE_DIR / f"{key}.json"


def _try_read_cache(
    tickers: list[str],
    period: str | None,
    interval: str,
    provider: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame | None:
    cache_file, _ = _cache_paths(_cache_key(tickers, period, interval, provider, start, end))
    if not cache_file.exists():
        return None
    try:
        cached = pd.read_pickle(cache_file)
        frame = _normalize_close(cached, tickers)
        return _slice_window(frame, start, end)
    except Exception:
        return None


def _write_cache(
    frame: pd.DataFrame,
    tickers: list[str],
    period: str | None,
    interval: str,
    provider: str,
    start: str | None = None,
    end: str | None = None,
) -> None:
    cache_file, meta_file = _cache_paths(
        _cache_key(tickers, period, interval, provider, start, end)
    )
    try:
        frame.to_pickle(cache_file)
        meta_file.write_text(
            json.dumps(
                {
                    "tickers": list(frame.columns),
                    "period": period,
                    "interval": interval,
                    "provider": provider,
                    "start": start,
                    "end": end,
                    "rows": len(frame),
                    "data_start": str(frame.index.min()),
                    "data_end": str(frame.index.max()),
                },
                indent=2,
            )
        )
    except Exception:
        pass


def _clear_proxies() -> None:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(key, None)


def _extract_close_series(piece: pd.DataFrame | pd.Series, ticker: str) -> pd.Series | None:
    if piece is None or (hasattr(piece, "empty") and piece.empty):
        return None
    if isinstance(piece, pd.Series):
        return piece.rename(ticker)
    if isinstance(piece.columns, pd.MultiIndex):
        if "Close" in piece.columns.get_level_values(0):
            s = piece["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
        else:
            s = piece.iloc[:, 0]
    elif "Close" in piece.columns:
        s = piece["Close"]
    else:
        s = piece.iloc[:, 0]
    return s.rename(ticker)


def _yf_download(
    tickers: list[str],
    *,
    period: str | None = None,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Download with optional calendar window; avoid broken local HTTPS proxies."""
    _clear_proxies()

    kwargs: dict = {
        "interval": interval,
        "auto_adjust": True,
        "threads": False,
        "progress": False,
        "group_by": "column",
    }
    if start and end:
        # yfinance treats `end` as exclusive (calendar day); +1 day keeps UI end inclusive.
        kwargs["start"] = start
        kwargs["end"] = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    elif period:
        kwargs["period"] = period
    else:
        kwargs["period"] = "5y"

    symbol = tickers if len(tickers) > 1 else tickers[0]
    data = yf.download(symbol, **kwargs)

    if data is None or data.empty:
        frames = []
        for t in tickers:
            piece = yf.download(t, **{k: v for k, v in kwargs.items() if k != "group_by"})
            s = _extract_close_series(piece, t)
            if s is not None:
                frames.append(s)
        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, axis=1)
    return data


def _close_from_download(data: pd.DataFrame | pd.Series, tickers: list[str]) -> pd.DataFrame | pd.Series:
    if isinstance(data, pd.Series):
        return data.to_frame(name=tickers[0]) if len(tickers) else data
    if "Close" in getattr(data, "columns", []) or (
        isinstance(data.columns, pd.MultiIndex)
        and (
            "Close" in data.columns.get_level_values(0)
            or "Close" in data.columns.get_level_values(1)
        )
    ):
        if isinstance(data.columns, pd.MultiIndex):
            if "Close" in data.columns.get_level_values(0):
                return data["Close"]
            return data.xs("Close", axis=1, level=1)
        return data["Close"] if "Close" in data.columns else data
    return data


def fetch_market_data(
    tickers: list | None = None,
    provider: str = "yfinance",
    *,
    period: str | None = None,
    interval: str | None = None,
    mode: str = "live",
    use_cache: bool = True,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Download Close prices for `tickers`.

    Parameters
    ----------
    mode:
        ``"live"`` uses TRADING defaults (5d / 1m) with fallbacks.
        ``"research"`` uses RESEARCH defaults (5y / 1d) and disk cache.
    period / interval:
        Optional overrides of the mode defaults.
    start / end:
        ISO date strings (YYYY-MM-DD). When both are set, research mode uses
        calendar download instead of relative ``period``. If only one is set,
        raises ValueError (caller should validate).
    """
    if mode not in {"live", "research"}:
        raise ValueError(f"Unknown mode: {mode!r}. Use 'live' or 'research'.")

    if (start and not end) or (end and not start):
        raise ValueError("Provide both start and end dates, or neither (use period).")

    defaults = TRADING if mode == "live" else RESEARCH
    tickers = list(tickers or defaults["tickers"])
    interval = interval or defaults["interval"]
    # Explicit window wins over period for research; live still uses period ladders
    use_dates = bool(start and end)
    period = None if use_dates else (period or defaults["period"])

    if provider == "alpha_vantage":
        raise NotImplementedError("Alpha Vantage wrapper coming soon.")
    if provider != "yfinance":
        raise ValueError(f"Unknown data provider profile: {provider}")

    if use_cache:
        cached = _try_read_cache(tickers, period, interval, provider, start, end)
        if cached is not None and not cached.empty:
            return cached

    errors: list[str] = []

    if use_dates and mode == "research":
        try:
            data = _yf_download(tickers, interval=interval, start=start, end=end)
            if data is not None and not data.empty:
                frame = _normalize_close(_close_from_download(data, tickers), tickers)
                frame = _slice_window(frame, start, end)
                if use_cache:
                    _write_cache(frame, list(frame.columns), period, interval, provider, start, end)
                return frame
            errors.append(f"{start}/{end}/{interval}: empty")
        except Exception as exc:
            errors.append(f"{start}/{end}: {exc}")

        # Fall back: download long period then slice
        for per in (period or "5y", "5y", "max"):
            if use_cache:
                cached = _try_read_cache(tickers, per, interval, provider, None, None)
                if cached is not None and not cached.empty:
                    try:
                        return _slice_window(cached, start, end)
                    except Exception as exc:
                        errors.append(f"slice cache {per}: {exc}")
            try:
                data = _yf_download(tickers, period=per, interval=interval)
                if data is None or data.empty:
                    errors.append(f"{per}/{interval}: empty")
                    continue
                frame = _normalize_close(_close_from_download(data, tickers), tickers)
                if use_cache:
                    _write_cache(frame, list(frame.columns), per, interval, provider, None, None)
                return _slice_window(frame, start, end)
            except Exception as exc:
                errors.append(f"{per}: {exc}")

    attempts: list[tuple[str | None, str]] = [(period, interval)]
    if mode == "live":
        for pair in _LIVE_FALLBACKS:
            if pair not in attempts:
                attempts.append(pair)
        research_pair = (RESEARCH["period"], "1d")
        if research_pair not in attempts:
            attempts.append(research_pair)

    for per, itv in attempts:
        if per is None:
            continue
        if use_cache:
            cached = _try_read_cache(tickers, per, itv, provider, start, end)
            if cached is not None and not cached.empty:
                return cached
            # Wider cache without exact window
            cached = _try_read_cache(tickers, per, itv, provider, None, None)
            if cached is not None and not cached.empty:
                try:
                    return _slice_window(cached, start, end) if (start or end) else cached
                except Exception:
                    pass
        try:
            data = _yf_download(tickers, period=per, interval=itv)
            if data is None or data.empty:
                errors.append(f"{per}/{itv}: empty")
                continue
            frame = _normalize_close(_close_from_download(data, tickers), tickers)
            if use_cache:
                _write_cache(frame, list(frame.columns), per, itv, provider, None, None)
            if start or end:
                frame = _slice_window(frame, start, end)
            return frame
        except Exception as exc:
            errors.append(f"{per}/{itv}: {exc}")
            continue

    # Any research cache for these tickers can still power the desk
    if use_cache and DATA_CACHE_DIR.exists():
        for pkl in sorted(DATA_CACHE_DIR.glob("*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                cached = pd.read_pickle(pkl)
                frame = _normalize_close(cached, tickers)
                if start or end:
                    frame = _slice_window(frame, start, end)
                if not frame.empty:
                    return frame
            except Exception:
                continue

    label = f"{start}→{end}" if use_dates else f"{period}/{interval}"
    detail = "; ".join(errors[-4:]) if errors else "unknown"
    raise ValueError(
        f"yfinance returned no data for {tickers} ({label}). "
        f"Tried fallbacks. Last errors: {detail}. "
        "If you are offline, run a research backtest once to populate data/cache/."
    )


def fetch_research_prices(
    tickers: list[str] | None = None,
    period: str | None = None,
    use_cache: bool = True,
    *,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Convenience wrapper for multi-year daily Close panel."""
    return fetch_market_data(
        tickers=tickers,
        mode="research",
        period=period,
        interval="1d",
        use_cache=use_cache,
        start=start,
        end=end,
    )


def fetch_benchmark(
    symbol: str | None = None,
    period: str | None = None,
    use_cache: bool = True,
    *,
    start: str | None = None,
    end: str | None = None,
) -> pd.Series:
    """Daily Close for the research benchmark (default QQQ)."""
    symbol = symbol or RESEARCH["benchmark"]
    frame = fetch_research_prices(
        tickers=[symbol],
        period=period,
        use_cache=use_cache,
        start=start,
        end=end,
    )
    return frame[symbol].dropna()
