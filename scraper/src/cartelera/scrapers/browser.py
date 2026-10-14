"""Shared production browser helper: one headless Chromium page load, for the
few sites that plain HTTP (httpx / curl_cffi) can't get past.

Use ONLY when `cartelera.scrapers.http.fetch` (incl. `impersonate=True`)
fails — typically a JavaScript queue gate or bot check that sets a cookie
(De Doelen's `csq_token`, TivoliVredenburg). The intended pattern is: one
headless pass to obtain the gate cookie(s), then plain HTTP for the actual
pages, sending those cookies with the SAME User-Agent (gates often bind the
token to it):

    page = browser_page(url, wait_for_cookie="csq_token")
    html = fetch(other_url, headers={
        "User-Agent": page.user_agent, "Cookie": page.cookie_header})

Each call launches its own isolated browser (parallel-safe, never the user's
Chrome) and always closes it. In production the image ships Playwright's
`chromium-headless-shell` (see scraper/Dockerfile); locally run
`uv run playwright install chromium-headless-shell` once.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from cartelera.scrapers.http import CARTELITA_UA

# Honest identification with a browser token (gates reject non-browser UAs).
# The Chrome version is rewritten to the launched browser's real version.
BROWSER_HELPER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/141.0.0.0 Safari/537.36 {CARTELITA_UA}"
)


@dataclass
class BrowserPage:
    """What one headless page load yields."""
    url: str                                   # final URL after redirects
    html: str                                  # rendered DOM (page.content())
    cookies: dict[str, str] = field(default_factory=dict)
    user_agent: str = BROWSER_HELPER_UA

    @property
    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


class BrowserError(RuntimeError):
    """The page could not be loaded or the wait condition never held."""


def browser_page(
    url: str,
    *,
    wait_for: str | None = None,
    wait_for_cookie: str | None = None,
    timeout: float = 60,
    locale: str = "nl-NL",
) -> BrowserPage:
    """Load `url` in a fresh headless Chromium and return HTML + cookies.

    `wait_for`: a CSS selector that must appear (e.g. the event list, i.e.
    "the gate has let us through"). `wait_for_cookie`: a cookie name that must
    be set (e.g. a queue token). Both are optional; without them the call
    waits for the network to settle (best effort). Raises `BrowserError` when
    a requested condition isn't met within `timeout` seconds.
    """
    from playwright.sync_api import sync_playwright

    deadline = time.monotonic() + timeout
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ua = re.sub(r"Chrome/[\d.]+", f"Chrome/{browser.version}", BROWSER_HELPER_UA)
            ctx = browser.new_context(locale=locale, user_agent=ua)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            if wait_for:
                remaining = max(deadline - time.monotonic(), 1)
                try:
                    page.wait_for_selector(wait_for, timeout=remaining * 1000)
                except Exception as e:  # noqa: BLE001 — playwright TimeoutError
                    raise BrowserError(f"{url}: selector {wait_for!r} never appeared") from e
            if wait_for_cookie:
                while not any(c["name"] == wait_for_cookie for c in ctx.cookies()):
                    if time.monotonic() > deadline:
                        raise BrowserError(f"{url}: cookie {wait_for_cookie!r} never set")
                    page.wait_for_timeout(500)
            if not wait_for and not wait_for_cookie:
                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=max(min(deadline - time.monotonic(), 15), 1) * 1000,
                    )
                except Exception:  # noqa: BLE001 — chatty pages never idle
                    pass
            return BrowserPage(
                url=page.url,
                html=page.content(),
                cookies={c["name"]: c["value"] for c in ctx.cookies()},
                user_agent=ua,
            )
        finally:
            browser.close()


def browser_cookies(url: str, **kwargs) -> dict[str, str]:
    """Cookies set by loading `url` (see `browser_page` for kwargs). To reuse
    them over HTTP, prefer `browser_page` so you also get the User-Agent."""
    return browser_page(url, **kwargs).cookies


def browser_html(url: str, **kwargs) -> str:
    """The rendered HTML of `url` (see `browser_page` for kwargs)."""
    return browser_page(url, **kwargs).html
