"""Append-only strategy catalog (Rui: avoid repeat proposals)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import CATALOG_DIR, RUNS_DIR


def catalog_path(horizon: str | None = None) -> Path:
    root = Path(CATALOG_DIR)
    root.mkdir(parents=True, exist_ok=True)
    if horizon:
        return root / f"strategy_catalog_{horizon}.jsonl"
    return root / "strategy_catalog.jsonl"


def leaderboard_path(horizon: str) -> Path:
    root = Path(CATALOG_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"leaderboard_{horizon}.json"


def load_catalog(horizon: str | None = None) -> list[dict[str, Any]]:
    path = catalog_path(horizon)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def is_duplicate(code_hash: str, horizon: str | None = None) -> bool:
    if not code_hash:
        return False
    return any(r.get("code_hash") == code_hash for r in load_catalog(horizon))


def append_catalog_entry(entry: dict[str, Any], horizon: str | None = None) -> None:
    path = catalog_path(horizon)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(entry)
    row.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    with path.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def catalog_summary_table(horizon: str | None = None, limit: int = 40) -> str:
    """Plain-text table of principles for LLM dual-report prompting."""
    rows = load_catalog(horizon)
    if not rows:
        return "(empty catalog — no strategies tested yet)"
    # newest last for append order; show unique hashes, max limit
    seen = set()
    lines = ["name | family | principle | test_utility | hit | ARR"]
    for r in rows:
        h = r.get("code_hash") or ""
        if h in seen:
            continue
        seen.add(h)
        lines.append(
            f"{r.get('name', '?')} | {r.get('family', r.get('template', ''))} | "
            f"{(r.get('principle') or '')[:80]} | "
            f"{r.get('test_utility', 0):.3f} | "
            f"{r.get('test_hit', 0):.2%} | "
            f"{r.get('test_arr', 0):.2%}"
        )
        if len(lines) > limit:
            break
    return "\n".join(lines)


def write_leaderboard(
    horizon: str,
    ranked: list[dict[str, Any]],
    utility_curve: list[dict[str, Any]],
) -> Path:
    path = leaderboard_path(horizon)
    path.write_text(
        json.dumps(
            {
                "horizon": horizon,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "ranked": ranked,
                "utility_curve": utility_curve,
            },
            indent=2,
            default=str,
        )
    )
    return path


def load_leaderboard(horizon: str) -> dict[str, Any]:
    path = leaderboard_path(horizon)
    if not path.exists():
        return {"horizon": horizon, "ranked": [], "utility_curve": []}
    return json.loads(path.read_text())
