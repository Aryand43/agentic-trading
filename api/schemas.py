"""Request / response shapes for the research control panel API."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RunRequest(BaseModel):
    tickers: list[str] | None = Field(
        default=None,
        description="Optional override; defaults to TRADING tickers in config.",
    )
    max_position: float = Field(default=0.15, ge=0.01, le=1.0)
    gross_exposure: float = Field(default=1.0, ge=0.01, le=5.0)
    target_volatility: float | None = Field(
        default=None,
        description="Optional override of pipeline default target volatility.",
    )


class RunResponse(BaseModel):
    tickers: list[str]
    horizons: list[str]
    signals: dict[str, dict[str, float]]
    conviction: dict[str, float]
    volatilities: dict[str, float]
    portfolio_volatility: float
    target_volatility: float
    weights: dict[str, float]


class EquityPoint(BaseModel):
    date: str
    equity: float
    series: str = "strategy"


class MetricsBlock(BaseModel):
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    hit_rate: float = 0.0
    signal_hit_rate: float = 0.0
    utility: float = 0.0
    turnover: float = 0.0
    n_days: float = 0.0
    final_equity: float = 0.0
    start_equity: float = 0.0


class WindowInfo(BaseModel):
    start: str
    end: str
    n_days: int
    period_used: str | None = None


class SplitWindow(BaseModel):
    start: str | None = None
    end: str | None = None
    n_days: int | None = None


class ResearchWindows(BaseModel):
    as_of: str | None = None
    train: SplitWindow | None = None
    val: SplitWindow | None = None
    test: SplitWindow | None = None


class BacktestRequest(BaseModel):
    tickers: list[str] | None = Field(
        default=None,
        description="Research universe override; defaults to a liquid NASDAQ subset.",
    )
    period: str = Field(default="3y", description="yfinance period when dates omitted.")
    start_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    initial_capital: float = Field(default=10_000.0, ge=100.0)
    max_position: float = Field(default=0.15, ge=0.01, le=1.0)
    gross_exposure: float = Field(default=1.0, ge=0.01, le=5.0)
    target_volatility: float = Field(default=0.15, ge=0.01, le=1.0)
    include_baselines: bool = True
    include_segments: bool = True
    baselines: list[str] = Field(
        default_factory=lambda: ["buy_and_hold", "sma_cross"],
    )

    @model_validator(mode="after")
    def _dates_pair(self) -> BacktestRequest:
        if (self.start_date and not self.end_date) or (self.end_date and not self.start_date):
            raise ValueError("Provide both start_date and end_date, or neither (use period).")
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date.")
        return self


class BacktestResponse(BaseModel):
    tickers: list[str]
    initial_capital: float
    window: WindowInfo
    research_windows: ResearchWindows | None = None
    metrics: MetricsBlock
    baselines: dict[str, MetricsBlock] = Field(default_factory=dict)
    equity_curve: list[EquityPoint]
    baseline_curves: dict[str, list[EquityPoint]] = Field(default_factory=dict)
    segments: dict = Field(default_factory=dict)
    portfolios: dict = Field(default_factory=dict)


class AgentRequest(BaseModel):
    tickers: list[str] | None = None
    period: str = "3y"
    start_date: str | None = None
    end_date: str | None = None
    horizon: str = Field(default="10d")
    n_iterations: int = Field(default=2, ge=1, le=5)
    initial_capital: float = Field(default=10_000.0, ge=100.0)
    seed_baselines: bool = True

    @model_validator(mode="after")
    def _dates_pair(self) -> AgentRequest:
        if (self.start_date and not self.end_date) or (self.end_date and not self.start_date):
            raise ValueError("Provide both start_date and end_date, or neither (use period).")
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date.")
        return self


class AgentIteration(BaseModel):
    iteration: int
    hypothesis: str
    template: str
    params: dict[str, float]
    name: str = ""
    train_sharpe: float | None = None
    val_sharpe: float | None = None
    test_sharpe: float | None = None
    utility: float | None = None
    insights: str = ""
    code_hash: str = ""
    portfolios: dict = Field(default_factory=dict)
    test_summary: dict = Field(default_factory=dict)


class LeaderboardRow(BaseModel):
    iteration: int
    name: str = ""
    template: str = ""
    test_utility: float | None = None
    test_sharpe: float | None = None
    test_hit: float | None = None
    code_hash: str = ""


class AgentResponse(BaseModel):
    horizon: str
    window: WindowInfo
    research_windows: ResearchWindows | None = None
    tickers: list[str]
    run_dir: str
    best_iteration: int
    best_test_sharpe: float
    best_test_utility: float = 0.0
    iterations: list[AgentIteration]
    leaderboard: list[LeaderboardRow] = Field(default_factory=list)
    utility_curve: list[dict] = Field(default_factory=list)
    catalog_path: str = ""
