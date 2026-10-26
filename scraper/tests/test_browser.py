"""The production browser helper, with Playwright mocked (no browser, no network)."""

from __future__ import annotations

import sys
import types

import pytest

from cartelera.scrapers import browser as B


class FakeContext:
    def __init__(self, cookie_after: int | None):
        self.cookie_after = cookie_after  # cookies() calls until the cookie appears
        self.calls = 0
        self.kwargs: dict = {}

    def cookies(self):
        self.calls += 1
        if self.cookie_after is not None and self.calls > self.cookie_after:
            return [{"name": "csq_token", "value": "abc"}, {"name": "x", "value": "1"}]
        return [{"name": "x", "value": "1"}]

    def new_page(self):
        return FakePage()


class FakePage:
    url = "https://example.org/final"

    def goto(self, url, **kw):
        self.goto_url = url

    def wait_for_selector(self, sel, timeout):
        if sel == ".missing":
            raise TimeoutError("nope")

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, *a, **kw):
        pass

    def content(self):
        return "<html><body><ul class='events'></ul></body></html>"


class FakeBrowser:
    version = "142.0.1.2"

    def __init__(self, ctx):
        self.ctx = ctx
        self.closed = False

    def new_context(self, **kw):
        self.ctx.kwargs = kw
        return self.ctx

    def close(self):
        self.closed = True


@pytest.fixture()
def fake_playwright(monkeypatch):
    state: dict = {}

    def install(cookie_after: int | None = 0):
        ctx = FakeContext(cookie_after)
        brw = FakeBrowser(ctx)
        state["browser"] = brw

        class PW:
            def __enter__(self):
                return types.SimpleNamespace(
                    chromium=types.SimpleNamespace(launch=lambda **kw: brw)
                )

            def __exit__(self, *a):
                return False

        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = PW
        pkg = types.ModuleType("playwright")
        pkg.sync_api = sync_api
        monkeypatch.setitem(sys.modules, "playwright", pkg)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
        return state

    return install


def test_browser_page_returns_html_cookies_and_honest_ua(fake_playwright):
    state = fake_playwright(cookie_after=0)
    page = B.browser_page("https://example.org/", wait_for_cookie="csq_token")
    assert page.cookies["csq_token"] == "abc"
    assert "csq_token=abc" in page.cookie_header
    assert "class='events'" in page.html
    assert page.url == "https://example.org/final"
    assert "Cartelita (+https://cartelita.co)" in page.user_agent
    assert "Chrome/142.0.1.2" in page.user_agent  # real browser version
    assert state["browser"].ctx.kwargs["user_agent"] == page.user_agent
    assert state["browser"].closed


def test_waits_until_cookie_is_set(fake_playwright):
    state = fake_playwright(cookie_after=3)
    assert B.browser_cookies("https://example.org/", wait_for_cookie="csq_token")["csq_token"] == "abc"
    assert state["browser"].ctx.calls > 3


def test_cookie_timeout_raises_and_closes(fake_playwright):
    state = fake_playwright(cookie_after=None)
    with pytest.raises(B.BrowserError):
        B.browser_page("https://example.org/", wait_for_cookie="csq_token", timeout=0.01)
    assert state["browser"].closed


def test_missing_selector_raises_and_closes(fake_playwright):
    state = fake_playwright()
    with pytest.raises(B.BrowserError):
        B.browser_html("https://example.org/", wait_for=".missing")
    assert state["browser"].closed


def test_html_helper_with_selector(fake_playwright):
    fake_playwright()
    assert "events" in B.browser_html("https://example.org/", wait_for=".events")


def test_browser_module_is_not_a_scraper():
    from cartelera.scrapers import _NON_SCRAPER_MODULES
    assert "browser" in _NON_SCRAPER_MODULES
