"""Chronological train / validation / test splits (Rui scientific windows)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config import RESEARCH


@dataclass
class SplitWindows:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    as_of: str
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str
    n_train: int
    n_val: int
    n_test: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "train": {"start": self.train_start, "end": self.train_end, "n_days": self.n_train},
            "val": {"start": self.val_start, "end": self.val_end, "n_days": self.n_val},
            "test": {"start": self.test_start, "end": self.test_end, "n_days": self.n_test},
        }


def _fmt(ts) -> str:
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d")
    return str(ts)[:10]


def split_train_val_test(
    prices: pd.DataFrame,
    *,
    as_of: str | None = None,
    train_days: int | None = None,
    val_days: int | None = None,
    test_days: int | None = None,
    min_train: int = 40,
    min_val: int = 10,
    min_test: int = 5,
) -> SplitWindows:
    """Split a sorted price panel into train | val | test ending at ``as_of``.

    Windows are trading-day counts from the right:
      [... train ...][ val ][ test ]
    with ``test`` ending on the last bar on or before ``as_of``.
    """
    if prices is None or prices.empty:
        raise ValueError("prices panel is empty")

    frame = prices.sort_index()
    train_days = int(train_days if train_days is not None else RESEARCH["train_days"])
    val_days = int(val_days if val_days is not None else RESEARCH["val_days"])
    test_days = int(test_days if test_days is not None else RESEARCH["test_days"])

    if as_of is None:
        as_of = RESEARCH.get("as_of")
    if as_of:
        end_ts = pd.Timestamp(as_of)
        frame = frame.loc[frame.index <= end_ts]
        if frame.empty:
            raise ValueError(f"No rows on or before as_of={as_of!r}")
    as_of_s = _fmt(frame.index.max())

    n = len(frame)
    need = train_days + val_days + test_days
    if n < need:
        # Shrink proportionally but keep minimums when possible
        test_n = max(min_test, min(test_days, max(min_test, n // 10)))
        val_n = max(min_val, min(val_days, max(min_val, n // 5)))
        train_n = n - test_n - val_n
        if train_n < min_train:
            # Fall back to fractions of available length
            test_n = max(min_test, int(n * 0.1))
            val_n = max(min_val, int(n * 0.2))
            train_n = n - test_n - val_n
        if train_n < min_train:
            raise ValueError(
                f"Need more history for train/val/test (have {n} bars, "
                f"need ~{need} or at least {min_train + min_val + min_test})."
            )
    else:
        test_n = test_days
        val_n = val_days
        train_n = train_days

    test = frame.iloc[-test_n:]
    val = frame.iloc[-(test_n + val_n) : -test_n]
    # train is the contiguous block immediately before val, length train_n
    train_end_i = n - test_n - val_n
    train_start_i = max(0, train_end_i - train_n)
    train = frame.iloc[train_start_i:train_end_i]

    if train.empty or val.empty or test.empty:
        raise ValueError("Empty train/val/test slice after split")

    return SplitWindows(
        train=train,
        val=val,
        test=test,
        as_of=as_of_s,
        train_start=_fmt(train.index.min()),
        train_end=_fmt(train.index.max()),
        val_start=_fmt(val.index.min()),
        val_end=_fmt(val.index.max()),
        test_start=_fmt(test.index.min()),
        test_end=_fmt(test.index.max()),
        n_train=len(train),
        n_val=len(val),
        n_test=len(test),
    )
