"""cartelera.scrapers.http.fetch picks the client; no network (clients stubbed)."""

import httpx
import pytest

from cartelera.scrapers import http


def test_fetch_uses_httpx_with_browser_ua_by_default(monkeypatch):
    seen = {}

    def fake_get(url, **kw):
        seen.update(kw, url=url)
        return httpx.Response(200, text="ok", request=httpx.Request("GET", url))

    monkeypatch.setattr(http.httpx, "get", fake_get)
    assert http.fetch("https://venue.example/agenda", headers={"Accept-Language": "nl"}) == "ok"
    assert seen["headers"] == {"User-Agent": http.BROWSER_UA, "Accept-Language": "nl"}
    assert seen["follow_redirects"] is True


def test_fetch_raises_on_error_status(monkeypatch):
    monkeypatch.setattr(
        http.httpx, "get",
        lambda url, **kw: httpx.Response(403, request=httpx.Request("GET", url)),
    )
    with pytest.raises(httpx.HTTPStatusError):
        http.fetch("https://venue.example/agenda")


def test_fetch_impersonate_uses_curl_cffi_chrome(monkeypatch):
    from curl_cffi import requests as curl_requests

    seen = {}

    class FakeResp:
        text = "challenge passed"

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        seen.update(kw)
        return FakeResp()

    monkeypatch.setattr(curl_requests, "get", fake_get)
    assert http.fetch("https://venue.example/", impersonate=True) == "challenge passed"
    assert seen["impersonate"] == "chrome"
