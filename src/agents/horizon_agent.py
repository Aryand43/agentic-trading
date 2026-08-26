"""Horizon strategy-discovery agent loop (Rui Mao).

  1. Baseline seeds + templated hypotheses
  2. Materialize validated signal
  3. Train / val / test backtest + P1–P4 portfolios
  4. Performance report (Aradia-style)
  5. Error analysis (LLM or heuristic)
  6. Catalog append + dual-report next proposal
  7. Ranking + utility curve; stagnation → complementary mutation
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.agents.catalog import (
    append_catalog_entry,
    catalog_summary_table,
    is_duplicate,
    write_leaderboard,
)
from src.agents.proposal import (
    AgentProposal,
    build_observation,
    clip_params_to_bounds,
    default_rules_from_proposal,
    parse_llm_proposal,
    validate_proposal,
)
from src.backtest.baselines import BASELINE_SIGNAL_FNS
from src.backtest.engine import run_signal_backtest
from src.backtest.metrics import metrics_to_jsonable, compute_metrics, strategy_utility
from src.backtest.performance_report import (
    TEMPLATE_META,
    build_strategy_performance_report,
    write_performance_report,
)
from src.backtest.portfolio_sim import run_portfolio_backtest
from src.backtest.splits import split_train_val_test
from src.config import RESEARCH, RUNS_DIR
from src.signals.strategies import STRATEGIES, _rsi, HORIZON_CATALOG, horizon_principle

SignalFn = Callable[[pd.Series], float]


@dataclass
class Hypothesis:
    iteration: int
    description: str
    template: str
    params: dict[str, float]
    source: str = "heuristic"
    name: str = ""


@dataclass
class IterationArtifact:
    iteration: int
    hypothesis: Hypothesis
    train_metrics: dict[str, float]
    val_metrics: dict[str, float]
    test_metrics: dict[str, float]
    insights: str
    report_path: str | None = None
    code_hash: str = ""
    utility: float = 0.0
    performance: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunSummary:
    horizon: str
    iterations: list[IterationArtifact] = field(default_factory=list)
    best_iteration: int = 0
    best_test_sharpe: float = float("-inf")
    best_test_utility: float = float("-inf")
    run_dir: str = ""
    windows: dict[str, Any] = field(default_factory=dict)
    leaderboard: list[dict[str, Any]] = field(default_factory=list)
    utility_curve: list[dict[str, Any]] = field(default_factory=list)
    catalog_path: str = ""


def _signal_sma_rsi(prices: pd.Series, fast: int, slow: int, rsi_period: int) -> float:
    if len(prices) < slow:
        return 0.0
    sma_f = prices.rolling(int(fast)).mean().iloc[-1]
    sma_s = prices.rolling(int(slow)).mean().iloc[-1]
    rsi = _rsi(prices, int(rsi_period)).iloc[-1]
    if any(np.isnan(x) for x in (sma_f, sma_s, rsi)):
        return 0.0
    ma_signal = float(np.tanh((sma_f - sma_s) / (sma_s * 0.02 + 1e-9)))
    rsi_signal = (float(rsi) - 50.0) / 50.0
    return float(np.clip(0.6 * ma_signal + 0.4 * rsi_signal, -1.0, 1.0))


def _signal_bollinger(prices: pd.Series, window: int, squeeze_lookback: int) -> float:
    window = int(window)
    squeeze_lookback = int(squeeze_lookback)
    if len(prices) < max(window, squeeze_lookback) + 5:
        return 0.0
    mid = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / (mid + 1e-9)
    min_w = width.rolling(squeeze_lookback).min().iloc[-1]
    squeeze = float(
        np.clip(1.0 - (width.iloc[-1] - min_w) / (min_w + 1e-9), 0.0, 1.0)
    )
    direction = float(np.sign(prices.iloc[-1] - mid.iloc[-1]))
    return float(np.clip(squeeze * direction, -1.0, 1.0))


def _signal_reversal(prices: pd.Series, lookback: int, z_window: int) -> float:
    lookback = int(lookback)
    z_window = int(z_window)
    if len(prices) < z_window + lookback:
        return 0.0
    ret = prices.pct_change(lookback).dropna()
    recent = ret.iloc[-z_window:]
    mu, sigma = recent.mean(), recent.std()
    z = (ret.iloc[-1] - mu) / (sigma + 1e-9)
    return float(np.clip(-z / 2.0, -1.0, 1.0))


def _signal_momentum_skip(prices: pd.Series, form: int, skip: int) -> float:
    form = int(form)
    skip = int(skip)
    need = form + skip + 5
    if len(prices) < need:
        return 0.0
    end = -skip - 1
    start = end - form
    ret_jt = (prices.iloc[end] - prices.iloc[start]) / (prices.iloc[start] + 1e-9)
    series = prices.pct_change(form).dropna()
    mu, sigma = series.mean(), series.std()
    z = (ret_jt - mu) / (sigma + 1e-9)
    return float(np.clip(z / 2.0, -1.0, 1.0))


TEMPLATES: dict[str, dict[str, Any]] = {
    "sma_rsi": {
        "params": {"fast": 10.0, "slow": 50.0, "rsi_period": 14.0},
        "bounds": {"fast": (3, 30), "slow": (20, 120), "rsi_period": (5, 30)},
        "build": lambda p: (
            lambda prices: _signal_sma_rsi(
                prices, int(p["fast"]), int(p["slow"]), int(p["rsi_period"])
            )
        ),
    },
    "bollinger_squeeze": {
        "params": {"window": 20.0, "squeeze_lookback": 126.0},
        "bounds": {"window": (10, 40), "squeeze_lookback": (40, 180)},
        "build": lambda p: (
            lambda prices: _signal_bollinger(
                prices, int(p["window"]), int(p["squeeze_lookback"])
            )
        ),
    },
    "reversal": {
        "params": {"lookback": 15.0, "z_window": 126.0},
        "bounds": {"lookback": (5, 40), "z_window": (40, 252)},
        "build": lambda p: (
            lambda prices: _signal_reversal(
                prices, int(p["lookback"]), int(p["z_window"])
            )
        ),
    },
    "momentum_skip": {
        "params": {"form": 63.0, "skip": 21.0},
        "bounds": {"form": (21, 126), "skip": (5, 42)},
        "build": lambda p: (
            lambda prices: _signal_momentum_skip(
                prices, int(p["form"]), int(p["skip"])
            )
        ),
    },
    # Baseline wrappers map into TEMPLATES for catalog continuity
    "buy_and_hold": {
        "params": {},
        "bounds": {},
        "build": lambda p: BASELINE_SIGNAL_FNS["buy_and_hold"],
    },
    "sma_cross": {
        "params": {},
        "bounds": {},
        "build": lambda p: BASELINE_SIGNAL_FNS["sma_cross"],
    },
    "rsi_mean_reversion": {
        "params": {},
        "bounds": {},
        "build": lambda p: BASELINE_SIGNAL_FNS["rsi_mean_reversion"],
    },
    "momentum_20d": {
        "params": {},
        "bounds": {},
        "build": lambda p: BASELINE_SIGNAL_FNS["momentum_20d"],
    },
}

HORIZON_SEED_TEMPLATE = {
    "1d": "sma_rsi",
    "3d": "reversal",
    "5d": "bollinger_squeeze",
    "10d": "sma_rsi",
    "15d": "reversal",
    "1m": "reversal",
    "3m": "momentum_skip",
}

MUTATABLE = {"sma_rsi", "bollinger_squeeze", "reversal", "momentum_skip"}
BASELINE_SEED_ORDER = ["buy_and_hold", "sma_cross", "rsi_mean_reversion", "momentum_20d"]


def _llm_chat(system: str, user: str, model: str = "gpt-4o-mini") -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL", model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        return payload["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError):
        return None


def _mutate_params(
    template: str,
    params: dict[str, float],
    insights: str,
    rng: np.random.Generator,
    *,
    scale: float = 0.25,
) -> dict[str, float]:
    if template not in MUTATABLE:
        template = "sma_rsi"
        params = dict(TEMPLATES[template]["params"])
    bounds = TEMPLATES[template]["bounds"]
    new_params = dict(params) if params else dict(TEMPLATES[template]["params"])
    if "underperform" in insights.lower() or "poor" in insights.lower() or "complementary" in insights.lower():
        scale = max(scale, 0.4)
    for key, (lo, hi) in bounds.items():
        center = new_params.get(key, (lo + hi) / 2)
        if "bear" in insights.lower() and key in {"lookback", "slow", "form"}:
            center = min(hi, center * 1.15)
        if "bull" in insights.lower() and key in {"fast", "window"}:
            center = max(lo, center * 0.9)
        noise = rng.normal(0, scale * (hi - lo) / 4)
        new_params[key] = float(np.clip(center + noise, lo, hi))
    if "fast" in new_params and "slow" in new_params:
        if new_params["fast"] >= new_params["slow"]:
            new_params["fast"] = max(bounds["fast"][0], new_params["slow"] * 0.4)
    return new_params


def _pick_complementary_template(current: str, insights: str, rng: np.random.Generator) -> str:
    """When stagnating, prefer a family different from the current one."""
    options = [t for t in MUTATABLE if t != current]
    low = insights.lower()
    if "momentum" in low or "trend" in low:
        preferred = [t for t in options if t in {"reversal", "bollinger_squeeze"}]
        if preferred:
            return str(rng.choice(preferred))
    if "mean" in low or "revert" in low or "bear" in low:
        preferred = [t for t in options if t in {"momentum_skip", "sma_rsi"}]
        if preferred:
            return str(rng.choice(preferred))
    return str(rng.choice(options)) if options else current


def _heuristic_insights(perf: dict, train: dict, val: dict, test: dict) -> str:
    ts = perf.get("test_summary") or {}
    lines = [
        f"Train util~{train.get('utility', 0):.3f}, Val util~{val.get('utility', 0):.3f}, "
        f"Test util={ts.get('utility', test.get('utility', 0)):.3f}.",
        f"Test signal-hit={ts.get('signal_hit_rate', 0):.2%}, ARR={ts.get('annualized_return', 0):.2%}, "
        f"Sharpe={ts.get('sharpe', 0):.3f}, MaxDD={ts.get('max_drawdown', 0):.2%}.",
    ]
    ports = perf.get("portfolios") or {}
    p4 = (ports.get("P4") or {}).get("test") or {}
    p1 = (ports.get("P1") or {}).get("test") or {}
    if p4 and p1:
        lines.append(
            f"P4 test hit={p4.get('signal_hit_rate', 0):.2%} vs P1 hit={p1.get('signal_hit_rate', 0):.2%} "
            f"(concentrated books)."
        )
    regime = (perf.get("segments") or {}).get("regime") or {}
    bull = regime.get("bull") or {}
    bear = regime.get("bear") or {}
    if bull or bear:
        lines.append(
            f"Bull Sharpe={bull.get('sharpe', 0):.3f}; Bear Sharpe={bear.get('sharpe', 0):.3f}."
        )
        if (bear.get("sharpe") or 0) < 0 and (bull.get("sharpe") or 0) > 0:
            lines.append("Bull-biased: next strategy should add defensiveness or short-side quality.")
    if (ts.get("utility") or 0) < 0.45:
        lines.append("Low overall utility — diversify entry principle or tighten selection (P3/P4).")
    return " ".join(lines)


def materialize_signal(hypothesis: Hypothesis) -> SignalFn:
    if hypothesis.template not in TEMPLATES:
        raise ValueError(f"Unknown template {hypothesis.template}")
    template = TEMPLATES[hypothesis.template]
    fn = template["build"](hypothesis.params or {})
    x = pd.Series(np.cumsum(np.random.default_rng(0).normal(0, 1, 300)) + 100)
    val = fn(x)
    if not np.isfinite(val) or val < -1.01 or val > 1.01:
        raise ValueError(f"Signal production out of range: {val}")
    return fn


def _code_hash(hypothesis: Hypothesis) -> str:
    blob = f"{hypothesis.template}:{json.dumps(hypothesis.params or {}, sort_keys=True)}"
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _p1_metrics(perf: dict, split: str) -> dict[str, float]:
    m = ((perf.get("portfolios") or {}).get("P1") or {}).get(split) or {}
    return dict(m)


def run_horizon_agent(
    prices: pd.DataFrame,
    horizon: str = "10d",
    *,
    n_iterations: int = 3,
    train_frac: float | None = None,  # legacy; ignored when day splits work
    train_days: int | None = None,
    val_days: int | None = None,
    test_days: int | None = None,
    as_of: str | None = None,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    warmup: int = 260,
    seed: int = 42,
    benchmark: pd.Series | None = None,
    use_llm: bool = True,
    output_dir: Path | None = None,
    seed_baselines: bool = True,
) -> AgentRunSummary:
    """Closed Rui discovery loop for a single horizon."""
    if horizon not in HORIZON_SEED_TEMPLATE and horizon not in STRATEGIES:
        raise ValueError(f"Unknown horizon: {horizon}")

    rng = np.random.default_rng(seed)
    splits = split_train_val_test(
        prices,
        as_of=as_of,
        train_days=train_days,
        val_days=val_days,
        test_days=test_days,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir or (RUNS_DIR / horizon / stamp))
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = AgentRunSummary(
        horizon=horizon,
        run_dir=str(run_dir),
        windows=splits.to_dict(),
    )

    horizon_template = HORIZON_SEED_TEMPLATE.get(horizon, "sma_rsi")
    template_name = horizon_template
    params: dict[str, float] = dict(TEMPLATES[horizon_template]["params"])
    insights = "Initial seed. No prior backtest."
    utility_curve: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    # Build iteration plan: optional baselines then discoveries
    plan: list[tuple[str, str, dict[str, float], str]] = []
    n_baselines = 0
    if seed_baselines:
        n_baselines = 2 if n_iterations <= 2 else len(BASELINE_SEED_ORDER)
        for bl in BASELINE_SEED_ORDER[:n_baselines]:
            plan.append((bl, "baseline", {}, f"baseline_{bl}"))
    for j in range(max(1, n_iterations)):
        plan.append(
            (
                horizon_template,
                "seed" if j == 0 else "pending",
                dict(params),
                f"{horizon}_{horizon_template}",
            )
        )

    last_perf: dict[str, Any] = {}
    last_observation: dict[str, Any] = {}
    exec_kwargs: dict[str, Any] = {
        "take_profit_pct": RESEARCH.get("take_profit_pct", 0.08),
        "stop_loss_pct": RESEARCH.get("stop_loss_pct", 0.04),
        "rebalance_every": 1,
    }
    stagnant = 0
    stagnate_k = int(RESEARCH.get("stagnation_iters", 3))

    for i, (tmpl, source, prm, name) in enumerate(plan):
        if source != "baseline":
            # Discovery / complementary proposals after at least one performance report
            if last_perf:
                catalog_txt = catalog_summary_table(horizon)
                plateau = stagnant >= stagnate_k
                if plateau:
                    insights = (
                        insights
                        + " Utility curve plateaus: seek complementary principle "
                        "(combine mean-reversion with trend or change family)."
                    )
                    tmpl = _pick_complementary_template(template_name, insights, rng)
                    prm = _mutate_params(
                        tmpl, dict(TEMPLATES[tmpl]["params"]), insights, rng, scale=0.45
                    )
                    source = "complementary"
                else:
                    llm_text = None
                    obs_txt = json.dumps(last_observation or {}, default=str)[:12_000]
                    if use_llm:
                        llm_text = _llm_chat(
                            "You are a quant researcher. Reply with JSON only matching "
                            '{"template": one of '
                            + json.dumps(sorted(MUTATABLE))
                            + ', "params": {}, "take_profit_pct": number, '
                            '"stop_loss_pct": number, "rebalance_every": int, '
                            '"max_position": number, "gross_exposure": number, '
                            '"target_volatility": number, "risk_method": '
                            '"historical_std"|"historical_var"|"ewma_cornish_fisher", '
                            '"description": string}. Stay inside safe ranges. '
                            "Do not propose live trading. Propose a NEW non-duplicate idea.",
                            f"Horizon={horizon}\n\n## Structured observation\n{obs_txt}\n\n"
                            f"## Catalog\n{catalog_txt}\n\nError analysis:\n{insights}",
                        )
                    tmpl = template_name if template_name in MUTATABLE else horizon_template
                    parsed = parse_llm_proposal(llm_text or "")
                    proposal: AgentProposal | None = None
                    if parsed:
                        try:
                            if "template" not in parsed:
                                parsed["template"] = tmpl
                            bounds = TEMPLATES.get(parsed.get("template") or tmpl, {}).get("bounds")
                            proposal = validate_proposal(parsed, template_bounds=bounds)
                            tmpl = proposal.template if proposal.template in MUTATABLE else tmpl
                            prm = clip_params_to_bounds(
                                tmpl,
                                proposal.params or dict(TEMPLATES[tmpl]["params"]),
                                TEMPLATES[tmpl]["bounds"],
                            )
                            exec_kwargs.update(default_rules_from_proposal(proposal))
                            source = "llm"
                        except (ValueError, TypeError):
                            proposal = None
                    if proposal is None:
                        if llm_text:
                            low = llm_text.lower()
                            for cand in MUTATABLE:
                                if cand.replace("_", " ") in low or cand in low:
                                    tmpl = cand
                                    break
                        base_params = (
                            params
                            if tmpl == template_name
                            else dict(TEMPLATES[tmpl]["params"])
                        )
                        prm = _mutate_params(tmpl, base_params, insights, rng)
                        source = "llm" if llm_text else "heuristic"
                    name = f"{horizon}_{tmpl}_i{i}"

                template_name = tmpl
                params = prm

                hyp_try = Hypothesis(i, "", tmpl, dict(prm), source=source, name=name)
                h = _code_hash(hyp_try)
                tries = 0
                while (h in seen_hashes or is_duplicate(h, horizon)) and tries < 6:
                    tmpl = _pick_complementary_template(tmpl, "duplicate avoid diversity", rng)
                    prm = _mutate_params(
                        tmpl, dict(TEMPLATES[tmpl]["params"]), "duplicate", rng, scale=0.5
                    )
                    hyp_try = Hypothesis(i, "", tmpl, dict(prm), source="dedup", name=name)
                    h = _code_hash(hyp_try)
                    tries += 1
                template_name = tmpl
                params = prm
                if tries:
                    source = "dedup"

                llm_desc = None
                if use_llm and source in {"llm", "complementary"}:
                    llm_desc = _llm_chat(
                        "Summarize the proposed trading strategy in 2 sentences (no code).",
                        f"Template={template_name} params={params} insights={insights[:500]}",
                    )
                desc = llm_desc or (
                    f"[{source}] `{template_name}` params="
                    f"{json.dumps({k: round(v, 2) for k, v in params.items()})}"
                )
            else:
                # First discovery without prior report: horizon seed template
                template_name = tmpl if tmpl in TEMPLATES else horizon_template
                params = dict(prm) if prm else dict(TEMPLATES[template_name]["params"])
                cat = HORIZON_CATALOG.get(horizon) or {}
                principle = horizon_principle(horizon)
                desc = (
                    f"Seed discovery `{template_name}` for {horizon} "
                    f"({cat.get('name', horizon)}). {principle} "
                    f"Rule: {cat.get('rule', '')}"
                ).strip()
                name = name or f"{horizon}_{template_name}"
                source = "seed"
        else:
            template_name = tmpl
            params = dict(prm) if prm else {}
            desc = f"Baseline seed `{template_name}` (Rui initial naïve strategies)."
            name = name or f"baseline_{template_name}"
            source = "baseline"

        hyp = Hypothesis(
            iteration=i,
            description=desc,
            template=template_name,
            params=dict(params),
            source=source,
            name=name or f"{horizon}_{template_name}_{i}",
        )
        ch = _code_hash(hyp)
        if ch in seen_hashes:
            insights = f"Skipped duplicate hash {ch}."
            stagnant += 1
            continue
        seen_hashes.add(ch)

        try:
            signal_fn = materialize_signal(hyp)
        except Exception as exc:
            insights = f"Implementation failed: {exc}."
            stagnant += 1
            continue

        warm = min(warmup, max(30, len(splits.train) // 4))
        try:
            train_res = run_signal_backtest(
                splits.train,
                signal_fn=signal_fn,
                horizon=horizon,
                initial_capital=initial_capital,
                cost_bps=cost_bps,
                warmup=warm,
                label=f"{horizon}_iter{i}_train",
                take_profit_pct=exec_kwargs.get("take_profit_pct"),
                stop_loss_pct=exec_kwargs.get("stop_loss_pct"),
                rebalance_every=int(exec_kwargs.get("rebalance_every") or 1),
            )
        except Exception as exc:
            insights = f"Train backtest failed: {exc}."
            stagnant += 1
            continue

        full = pd.concat([splits.train, splits.val, splits.test])
        full = full[~full.index.duplicated(keep="last")].sort_index()
        try:
            full_res = run_signal_backtest(
                full,
                signal_fn=signal_fn,
                horizon=horizon,
                initial_capital=initial_capital,
                cost_bps=cost_bps,
                warmup=warm,
                label=f"{horizon}_iter{i}_full",
                take_profit_pct=exec_kwargs.get("take_profit_pct"),
                stop_loss_pct=exec_kwargs.get("stop_loss_pct"),
                rebalance_every=int(exec_kwargs.get("rebalance_every") or 1),
            )
        except Exception:
            full_res = train_res

        meta = TEMPLATE_META.get(hyp.template, {})
        perf = build_strategy_performance_report(
            name=hyp.name or f"{horizon}_iter{i}",
            template=hyp.template,
            params=hyp.params,
            principle=meta.get("principle"),
            signal_fn=signal_fn,
            splits=splits,
            train_result=train_res,
            full_result=full_res,
            benchmark=benchmark,
            initial_capital=initial_capital,
            cost_bps=cost_bps,
            warmup=warm,
        )
        last_perf = perf

        train_m = _p1_metrics(perf, "train")
        val_m = _p1_metrics(perf, "val")
        test_m = _p1_metrics(perf, "test")
        util = float((perf.get("test_summary") or {}).get("utility") or test_m.get("utility") or 0.0)
        last_observation = build_observation(
            test_metrics=test_m,
            train_metrics=train_m,
            val_metrics=val_m,
            trades=list(getattr(full_res, "trades", None) or getattr(train_res, "trades", None) or []),
            trading_rules=getattr(full_res, "trading_rules", None) or exec_kwargs,
            prior=[
                {
                    "iteration": a.iteration,
                    "template": a.hypothesis.template,
                    "params": a.hypothesis.params,
                    "utility": a.utility,
                }
                for a in summary.iterations[-5:]
            ],
        )

        iter_dir = run_dir / f"iter_{i:02d}"
        iter_dir.mkdir(exist_ok=True)
        perf_path = write_performance_report(perf, iter_dir, stem="performance")

        insights = _heuristic_insights(perf, train_m, val_m, test_m)
        if use_llm:
            llm_ins = _llm_chat(
                "You perform error analysis on a trading strategy performance report. "
                "List strengths, weaknesses, and a concrete next-strategy principle. 4-6 sentences.",
                json.dumps(
                    {
                        "performance_summary": perf.get("test_summary"),
                        "strategy": perf.get("strategy"),
                        "portfolios_test": {
                            k: (v or {}).get("test")
                            for k, v in (perf.get("portfolios") or {}).items()
                        },
                        "catalog": catalog_summary_table(horizon, limit=20),
                    },
                    default=str,
                )[:12_000],
            )
            if llm_ins:
                insights = llm_ins

        (iter_dir / "hypothesis.json").write_text(
            json.dumps(
                {
                    "name": hyp.name,
                    "description": hyp.description,
                    "template": hyp.template,
                    "params": hyp.params,
                    "source": hyp.source,
                },
                indent=2,
            )
        )
        (iter_dir / "metrics.json").write_text(
            json.dumps({"train": train_m, "val": val_m, "test": test_m, "utility": util}, indent=2)
        )
        (iter_dir / "insights.txt").write_text(insights)
        (iter_dir / "code_hash.txt").write_text(ch)
        (iter_dir / "observation.json").write_text(
            json.dumps(last_observation, indent=2, default=str)
        )

        append_catalog_entry(
            {
                "name": hyp.name,
                "family": meta.get("family") or hyp.template,
                "template": hyp.template,
                "params": hyp.params,
                "principle": meta.get("principle") or hyp.description[:200],
                "code_hash": ch,
                "horizon": horizon,
                "test_utility": util,
                "test_hit": float((perf.get("test_summary") or {}).get("signal_hit_rate") or 0),
                "test_arr": float((perf.get("test_summary") or {}).get("annualized_return") or 0),
                "test_sharpe": float((perf.get("test_summary") or {}).get("sharpe") or 0),
            },
            horizon=horizon,
        )

        art = IterationArtifact(
            iteration=i,
            hypothesis=hyp,
            train_metrics=train_m,
            val_metrics=val_m,
            test_metrics=test_m,
            insights=insights,
            report_path=str(perf_path),
            code_hash=ch,
            utility=util,
            performance=perf,
        )
        summary.iterations.append(art)

        utility_curve.append(
            {"iteration": i, "name": hyp.name, "utility": util, "template": hyp.template}
        )

        if len(utility_curve) >= 2:
            if util <= utility_curve[-2]["utility"] + 1e-4:
                stagnant += 1
            else:
                stagnant = 0

        test_sharpe = float(test_m.get("sharpe") or float("-inf"))
        if util > summary.best_test_utility:
            summary.best_test_utility = util
            summary.best_iteration = i
        if test_sharpe > summary.best_test_sharpe:
            summary.best_test_sharpe = test_sharpe

    # Leaderboard across this run + sort by utility
    ranked = sorted(
        [
            {
                "iteration": a.iteration,
                "name": a.hypothesis.name,
                "template": a.hypothesis.template,
                "params": a.hypothesis.params,
                "test_utility": a.utility,
                "test_sharpe": a.test_metrics.get("sharpe"),
                "test_hit": a.test_metrics.get("signal_hit_rate") or a.test_metrics.get("hit_rate"),
                "code_hash": a.code_hash,
            }
            for a in summary.iterations
        ],
        key=lambda r: r.get("test_utility") or -999,
        reverse=True,
    )
    summary.leaderboard = ranked
    summary.utility_curve = utility_curve
    lb_path = write_leaderboard(horizon, ranked, utility_curve)
    summary.catalog_path = str(lb_path)

    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "horizon": summary.horizon,
                "windows": summary.windows,
                "best_iteration": summary.best_iteration,
                "best_test_sharpe": summary.best_test_sharpe
                if summary.best_test_sharpe != float("-inf")
                else None,
                "best_test_utility": summary.best_test_utility
                if summary.best_test_utility != float("-inf")
                else None,
                "utility_curve": utility_curve,
                "leaderboard": ranked,
                "iterations": [
                    {
                        "iteration": a.iteration,
                        "name": a.hypothesis.name,
                        "hypothesis": a.hypothesis.description,
                        "template": a.hypothesis.template,
                        "params": a.hypothesis.params,
                        "train_sharpe": a.train_metrics.get("sharpe"),
                        "val_sharpe": a.val_metrics.get("sharpe"),
                        "test_sharpe": a.test_metrics.get("sharpe"),
                        "utility": a.utility,
                        "insights": a.insights,
                        "code_hash": a.code_hash,
                        "report_path": a.report_path,
                    }
                    for a in summary.iterations
                ],
            },
            indent=2,
            default=str,
        )
    )
    return summary


def risk_agent_experiment(
    prices: pd.DataFrame,
    *,
    ewma_lambdas: list[float] | None = None,
    target_vols: list[float] | None = None,
    initial_capital: float = 10_000.0,
) -> dict[str, Any]:
    """Rank conventional target-vol risk variants on portfolio equity / drawdown."""
    ewma_lambdas = ewma_lambdas or [0.94, 0.97, 0.99]
    target_vols = target_vols or [0.10, 0.15, 0.20]
    results: list[dict[str, Any]] = []

    for tv in target_vols:
        try:
            res = run_portfolio_backtest(
                prices,
                initial_capital=initial_capital,
                target_volatility=tv,
                label=f"target_vol_{tv}",
            )
            m = metrics_to_jsonable(compute_metrics(res.equity, res.returns, res.positions))
            results.append({"variant": f"target_vol={tv}", "metrics": m})
        except Exception as exc:
            results.append({"variant": f"target_vol={tv}", "error": str(exc)})

    results.append(
        {
            "variant": "ewma_lambda_candidates",
            "note": "Candidates for risk engine experiments vs conventional fixed-window vol",
            "lambdas": ewma_lambdas,
        }
    )
    ranked = sorted(
        [r for r in results if "metrics" in r],
        key=lambda r: r["metrics"].get("sharpe") or -999,
        reverse=True,
    )
    return {"ranked": ranked, "all": results}
