"""Lightweight Locust load against backtest API (not browser).

  locust -f tests/load/locustfile.py --host http://127.0.0.1:8000
"""

from __future__ import annotations

from locust import HttpUser, between, task


class ResearchDeskUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(1)
    def backtest(self):
        self.client.post(
            "/api/backtest",
            json={
                "tickers": ["AAPL", "MSFT", "NVDA"],
                "start_date": "2023-08-07",
                "end_date": "2026-08-05",
                "include_baselines": False,
                "include_segments": False,
                "initial_capital": 10_000,
            },
            name="/api/backtest",
        )
