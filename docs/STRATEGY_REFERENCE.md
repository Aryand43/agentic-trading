# Strategy Reference

Catalog of quantitative trading strategies organized by target holding period. Each entry lists the strategy name, core rule or formula, and a short description of the underlying edge.

---

## 1-Day (1d) — Intraday Microstructure and Execution

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Opening Range Breakout (ORB)** | Enter Long if `P_t > max(P[0:N])` on high volume. Stop = `(high + low) / 2`. | Captures directional consensus after the market digests overnight news. Requires a catalyst and above-average relative volume to filter noise. |
| **VWAP Breakout / Momentum** | `VWAP = Σ(P_i × V_i) / ΣV_i`. Long if `P_close > VWAP` and `V_current > 1.5 × V_avg`. | Signals institutional buyer control when price closes above the daily VWAP with confirming volume. |
| **Order Book Imbalance (OBI) Scalping** | `ρ(t) = (V_bid − V_ask) / (V_bid + V_ask)`. Long if `ρ(t) > 0.60`. | Skewed resting liquidity predicts short-term price pressure: a heavy bid side makes upward moves easier and downward moves harder. |
| **Intraday VWAP Mean Reversion** | Short if `P_t > VWAP + 2σ` and `RSI > 70`. Target = VWAP. | Fades excessive intraday deviation from fair value as institutional urgency fades and price snaps back. |
| **Almgren-Chriss Optimal Execution** | Minimize `E[C] + λ·Var[C]` subject to `C = ∫v_t·S_t dt + η·∫v_t² dt`. | Execution algorithm that optimally splits a large meta-order over the day, balancing market impact against timing risk. |

---

## 3-Day (3d) — Short-Term Mean Reversion and Options Mechanics

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **ConnorsRSI Reversion** | `CRSI = (RSI(3) + RSI_streak(2) + PercentRank(100)) / 3`. Buy if `CRSI < 5`, sell if `CRSI > 95`. | Composite oscillator combining price momentum, streak duration, and rate-of-change rank to identify extreme exhaustion. |
| **Gamma Scalping / Gamma Flip Fade** | `GEX = Σ(Γ_i × OI_i × S²)`. Fade extremes when `Spot > Gamma Flip`. | Above the Gamma Flip, dealers sell rallies and buy dips to stay delta-neutral, suppressing volatility and enforcing mean reversion. |
| **Options Max Pain Pinning** | `min_K Σ[max(0, S−K)·OI_c + max(0, K−S)·OI_p]`. | Price gravitates toward the strike minimizing total option intrinsic value (max pain) in the 72 hours before OPEX. |
| **Larry Connors Aggressive R3** | Buy if `CRSI < 10` and `P > SMA(200)`. Add on Day 2 if `P_t+1 < P_t`. Exit at `CRSI > 70`. | Scale-in reversal requiring a long-term uptrend with a severe 3-day capitulation pullback. |
| **Overnight Gap Reversal** | Short at open if `P_open >> P_close(t−1)` with no fundamental catalyst. Exit Day 3 close. | Fades retail-driven overnight gaps that lack institutional volume, which typically decay over the subsequent three sessions. |

---

## 5-Day (5d) — Calendar Anomalies and Statistical Arbitrage

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Turn of the Month (ToM) Effect** | Buy indices 1 day before last trading day of month. Sell on 3rd trading day of new month. | Exploits predictable institutional cash flows (pension reinvestments, salary autodebits) that systematically bid up equities over a 4–5 day window. |
| **Kalman Filter Pairs Trading** | `e_t = y_1t − (μ_t + γ_t·y_2t)`. Long spread if `e_t < −Q_t`. Exit when `e_t ≈ 0`. | Bayesian state-space model that dynamically estimates the hedge ratio; trades the residual forecast error when it exceeds a variance threshold. |
| **Short-Term EAR Reversal** | Short if Earnings Announcement Return `> 10%`. Hold 5 days. | Fades the immediate overreaction on an earnings day, isolating the liquidity premium and post-announcement profit-taking from the longer PEAD drift. |
| **Bollinger Band Volatility Squeeze** | Buy if BB width is at a 6-month low and price breaks the upper band on high volume. | Combines volatility compression with an expansion trigger; the subsequent directional swing typically unfolds over 5 days as trapped traders unwind. |
| **Broken Wing Butterfly Pin** | Buy 1 ITM, Sell 2 ATM, Buy 1 OTM (wider wing). 7–14 DTE. | Initiated for a net credit; profits from Theta decay as the underlying drifts toward the short body strikes over 5–10 days. |

---

## 10-Day (10d) — Volatility Term Structure and Fast Momentum

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **VIX Futures Roll Yield Harvest** | `Roll = (F_near − F_far) / Δt`. Short front-month VIX futures in steep contango. | Harvests the Volatility Risk Premium: the front-month future decays toward spot VIX at expiration, generating a positive return for the short seller. |
| **Ornstein-Uhlenbeck Pairs Trading** | `dS_t = λ(μ − S_t)dt + σ dW_t`. Enter at Z-score `> 2`; exit at `μ`. | Models the spread as a mean-reverting SDE; calibrated half-life determines the expected holding period. Position held until residual reverts to equilibrium. |
| **10-Day Moving Average Momentum** | Buy when `SMA(10) > SMA(50)` and `RSI(14) > 60`. | Fast trend-following crossover capturing aggressive inflows from fundamental shifts or broad market rallies. |
| **Variance Swap Arbitrage** | Payoff = `N_var × (σ²_realized − X²_strike)`. Short variance swap, delta-hedge spot. | Sells implied variance and dynamically hedges the underlying to lock in the spread between the implied variance strike and actual realized variance over two weeks. |
| **Directional ORB Swing** | If daily `P > VWAP` (uptrend), take 5-min ORB longs and hold for 10-day swing. | Contextualizes intraday breakouts within a higher-timeframe trend; holds rather than closing intraday to capture broader multi-day momentum. |

---

## 15-Day (15d) — Intermediate Cointegration and Rebalancing

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Bi-Weekly Inverse Volatility Rotation** | Allocate to SVXY during contango; hedge with long-term Treasuries. Rebalance every 15 days. | Harvests the constant roll decay of long-VIX futures; 15-day rebalancing manages compounding drift and maintains risk parity between equities and bonds. |
| **Fama-French Residual Reversal** | Sort stocks by trailing 15-day returns adjusted for FF factor exposures. Buy lowest residuals. | Strips out common risk factors to isolate idiosyncratic overreaction; the resulting pure signal exhibits higher-probability mean reversion. |
| **Intermediate Sector Momentum** | Rank sectors by 15-day Rate of Change. Buy top 2 sectors. | Captures rapid institutional capital rotation between cyclical and defensive sectors driven by shifting macroeconomic expectations. |
| **Mid-Frequency Statistical Arbitrage** | Hold 10–15 days; maximize spread capture while constraining implementation shortfall. | Simultaneous long/short of cointegrated equity portfolios; turnover is carefully managed to prevent market impact from eroding convergence alpha. |
| **Post-Earnings Announcement Flag Breakout** | Buy if price breaks a tight 15-day consolidation post-earnings on high volume. | After a major earnings gap, a 2–3 week bull flag forms; the breakout signals the secondary markup phase of the move. |

---

## 1-Month (1m) — Reversal, Liquidity, and Sector Flows

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Low-Turnover Short-Term Reversal** | Double-sort by 1-month return and turnover. Buy losers / short winners in bottom turnover decile. | Captures the liquidity premium: thinly traded stocks suffer temporary price pressure from non-informational trades and revert sharply the following month. |
| **High-Turnover 1-Month Momentum** | Double-sort by 1-month return and turnover. Buy winners / short losers in top turnover decile. | High-volume stocks move on fundamental news; investor underreaction to that news causes the price to trend for the following month. |
| **Short-Term Overreaction (STO)** | `SVOL_i,t = V_i,t if ret > 0, else −V_i,t`. Aggregate over 1 month, weight recent days more heavily. Buy low STO, sell high STO. | Uses signed volume to measure the magnitude and direction of investor overreaction; subsumes traditional price reversal and improves Sharpe. |
| **Monthly Sector Rotation** | Rank 11 GICS sectors by 12-month momentum (skip most recent month). Buy top 3. Rebalance monthly. | Dynamically shifts capital to highest relative-strength sectors, rotating out of lagging industries to mitigate drawdowns across the business cycle. |
| **Within-Industry Reversal** | Buy loser stocks / sell winners within the same industry over a 1-month formation period. | Remains sector-neutral to avoid the confounding effect of industry momentum; isolates idiosyncratic cash-flow shocks with cleaner risk-adjusted returns. |

---

## 3-Month (3m) — Fundamental Drift and Macro Momentum

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Post-Earnings Announcement Drift (PEAD / SUE)** | `SUE = (Actual EPS − Forecast EPS) / σ_estimate`. Long top SUE quintile. Hold 60 days. | Exploits investor underreaction to fundamental surprises; price drifts in the direction of the earnings beat for a full quarter as analysts revise forecasts. |
| **PEAD Two-Factor Approach (SUE + EAR)** | Long the intersection of top-quintile SUE and top-quintile Earnings Announcement Return. | Combines the fundamental surprise with the immediate market reaction; near-zero correlation between the two signals yields a superior drift trajectory. |
| **Traditional Price Momentum (JT Strategy)** | Rank universe on trailing J months (`3 ≤ J ≤ 12`). Buy top decile, hold K = 3 months. | Classic Jegadeesh-Titman factor; medium-term trends persist due to delayed information processing and institutional herding. |
| **Dual Momentum Asset Allocation** | If equity return `> T-Bill` (absolute), allocate to top-performing equity sector (relative). Else rotate to bonds. | Protects capital in macro downturns; negative absolute momentum over a 3–12 month lookback triggers a full pivot to risk-free assets. |
| **Term Structure Reversal** | Long portfolios where intermediate momentum (7–12 months ago) diverges from recent momentum (2–6 months). | Identifies momentum exhaustion; exploits a delayed short-term reversal that manifests as decay within the broader quarterly momentum term structure. |

---

## Second Derivative Strategies — Price Acceleration and Options Gamma

| Strategy | Core Rule / Formula | Description |
|---|---|---|
| **Gamma Scalping (Second-Order Convexity)** | `Γ = ∂²C / ∂S²`. Delta-hedge a long gamma position and scalp the underlying. | Exploits the convexity of options: as the underlying accelerates, the long gamma position generates P&L that outpaces the cost of delta hedging. |
| **MACD Histogram Acceleration** | `MACD_hist = MACD_line − Signal_line`. Buy when histogram turns positive. | Evaluates the second derivative of price momentum; a rising histogram signals that the rate of upward price change is actively accelerating. |
| **Taylor Expansion P&L Attribution** | `ΔC ≈ Δ·ΔS + 0.5·Γ·(ΔS)²`. Dynamically adjust hedges based on the Gamma correction. | Decomposes option P&L into delta (direction) and gamma (convexity) contributions to systematically isolate and trade each risk independently. |
