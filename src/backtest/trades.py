"""Trade-level audit trail models and artifact writers."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from src.config import REPORTS_DIR


class ExitReason(str, Enum):
    take_profit = "take_profit"
    stop_loss = "stop_loss"
    horizon_end = "horizon_end"
    end_of_data = "end_of_data"
    rebalance = "rebalance"
    rejected = "rejected"


class SignalSide(str, Enum):
    buy = "buy"
    neutral = "neutral"
    sell = "sell"


class PositionDirection(str, Enum):
    long = "long"
    short = "short"
    flat = "flat"


class SignalEvent(BaseModel):
    """Point-in-time signal recorded at T (no future bars)."""

    date: str
    ticker: str
    horizon: str
    signal_value: float
    signal_side: SignalSide
    conviction: Optional[float] = None
    weight: Optional[float] = None


class TradeRecord(BaseModel):
    """One opened (or rejected) position with full audit fields."""

    trade_id: str
    ticker: str
    signal_date: str
    signal_horizon: str
    signal_value: float
    signal_side: SignalSide
    entry_date: Optional[str] = None
    entry_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    quantity: float = 0.0
    notional: float = 0.0
    position_direction: PositionDirection = PositionDirection.flat
    take_profit_threshold: Optional[float] = None
    stop_loss_threshold: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    gross_pnl: Optional[float] = None
    transaction_cost: float = 0.0
    net_pnl: Optional[float] = None
    return_: Optional[float] = Field(default=None, alias="return")
    portfolio_weight: float = 0.0
    price_source: str = "open"
    data_version: Optional[str] = None
    config_version: Optional[str] = None

    model_config = {"populate_by_name": True}

    def to_audit_dict(self) -> dict[str, Any]:
        payload = self.model_dump(by_alias=True)
        for key, value in list(payload.items()):
            if isinstance(value, Enum):
                payload[key] = value.value
        return payload


def classify_side(
    score: float,
    *,
    long_threshold: float = 0.05,
    short_threshold: float = 0.05,
    side_mode: str = "long_short",
) -> SignalSide:
    """Map a continuous score in [-1, 1] to buy / neutral / sell."""
    if score >= float(long_threshold):
        return SignalSide.buy
    mode = side_mode.value if isinstance(side_mode, Enum) else str(side_mode)
    if mode != "long_only" and score <= -float(short_threshold):
        return SignalSide.sell
    return SignalSide.neutral


def new_trade_id(run_id: str, seq: int) -> str:
    return f"{run_id}-{seq:06d}"


def write_run_artifacts(
    run_id: str,
    *,
    trades: Iterable[TradeRecord],
    config: dict[str, Any],
    extra: dict[str, Any] | None = None,
    directory: Path | None = None,
) -> dict[str, str]:
    """Write trades.csv, trades.json, config.json, and manifest.json."""
    root = Path(directory or REPORTS_DIR) / run_id
    root.mkdir(parents=True, exist_ok=True)

    records = [t.to_audit_dict() if isinstance(t, TradeRecord) else dict(t) for t in trades]
    trades_json = root / "trades.json"
    trades_csv = root / "trades.csv"
    config_path = root / "config.json"
    manifest_path = root / "manifest.json"

    trades_json.write_text(json.dumps(records, indent=2, default=str))
    config_path.write_text(json.dumps(config, indent=2, default=str))

    fieldnames = [
        "trade_id",
        "ticker",
        "signal_date",
        "signal_horizon",
        "signal_value",
        "signal_side",
        "entry_date",
        "entry_price",
        "exit_date",
        "exit_price",
        "quantity",
        "notional",
        "position_direction",
        "take_profit_threshold",
        "stop_loss_threshold",
        "exit_reason",
        "gross_pnl",
        "transaction_cost",
        "net_pnl",
        "return",
        "portfolio_weight",
        "price_source",
        "data_version",
        "config_version",
    ]
    with trades_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            writer.writerow({k: "" if row.get(k) is None else row.get(k) for k in fieldnames})

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_trades": len(records),
        "paths": {
            "trades_csv": str(trades_csv),
            "trades_json": str(trades_json),
            "config_json": str(config_path),
        },
    }
    if extra:
        manifest.update(extra)
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    return {
        "run_id": run_id,
        "trades_csv": str(trades_csv),
        "trades_json": str(trades_json),
        "config_json": str(config_path),
        "manifest_json": str(manifest_path),
        "directory": str(root),
    }


def load_run_trades(run_id: str, directory: Path | None = None) -> list[dict[str, Any]]:
    path = Path(directory or REPORTS_DIR) / run_id / "trades.json"
    if not path.exists():
        raise FileNotFoundError(f"No trade audit for run_id={run_id!r}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"trades.json for {run_id} is not a list")
    return payload


def load_run_manifest(run_id: str, directory: Path | None = None) -> dict[str, Any]:
    path = Path(directory or REPORTS_DIR) / run_id / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No audit manifest for run_id={run_id!r}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"manifest.json for {run_id} is not an object")
    return payload
