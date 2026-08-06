"""Smoke Playwright UI flows for the research desk (Rui-aligned)."""

from __future__ import annotations

import os
import re

import pytest

BASE = os.environ.get("DESK_URL", "http://127.0.0.1:5173")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"headless": True}


@pytest.mark.asyncio
async def test_desk_loads_backtest_mode():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        await page.goto(BASE, wait_until="networkidle")
        await page.get_by_text("Research desk").wait_for()
        assert await page.get_by_role("tab", name="Backtest").is_visible()
        stamp = page.locator("text=/v0\\.\\d+/")
        assert await stamp.count() >= 1

        # Control fields present
        await page.get_by_text("Start", exact=False).first.wait_for()
        await page.get_by_role("button", name="Run backtest").wait_for()

        await page.screenshot(path="frontend/e2e/artifacts/desk_empty.png", full_page=True)
        # Allow font noise; fail on hard pageerrors only
        hard = [e for e in errors if "favicon" not in e.lower()]
        assert not hard, hard
        await browser.close()


@pytest.mark.asyncio
async def test_backtest_run_shows_metrics():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.goto(BASE, wait_until="networkidle")
        await page.get_by_role("button", name="Run backtest").click()
        # Wait for metric strip
        await page.get_by_text("ARR", exact=True).first.wait_for(timeout=120_000)
        await page.get_by_text("Utility", exact=True).first.wait_for(timeout=10_000)
        # Window strip or trading days
        body = await page.content()
        assert "trading days" in body or re.search(r"\d{4}-\d{2}-\d{2}", body)
        await page.screenshot(path="frontend/e2e/artifacts/desk_backtest.png", full_page=True)
        await browser.close()


@pytest.mark.asyncio
async def test_agent_mode_iteration_list():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.goto(BASE, wait_until="networkidle")
        await page.get_by_role("tab", name="Agent").click()
        await page.get_by_role("button", name="Run discovery").click()
        # Visible agent results (avoid matching hidden tooltips)
        await page.locator("h3", has_text="Leaderboard").wait_for(timeout=180_000)
        await page.screenshot(path="frontend/e2e/artifacts/desk_agent.png", full_page=True)
        await browser.close()


@pytest.mark.asyncio
async def test_responsive_viewports():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for w, h, name in [(390, 844, "mobile"), (768, 900, "tablet"), (1440, 900, "desktop")]:
            page = await browser.new_page(viewport={"width": w, "height": h})
            await page.goto(BASE, wait_until="networkidle")
            await page.get_by_text("Research desk").wait_for()
            # No horizontal blowout of root content (soft check)
            overflow = await page.evaluate(
                """() => {
                  const el = document.documentElement;
                  return el.scrollWidth - el.clientWidth;
                }"""
            )
            assert overflow < 40, f"{name} overflow {overflow}"
            await page.screenshot(path=f"frontend/e2e/artifacts/desk_{name}.png")
            await page.close()
        await browser.close()


def test_api_health():
    import urllib.request

    with urllib.request.urlopen(f"{API}/health", timeout=10) as r:
        body = r.read().decode()
    assert "ok" in body
