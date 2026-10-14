"""Shared HTTP fetch for scrapers: httpx by default, curl_cffi when a site's
bot protection (Cloudflare & co.) rejects a plain client.

Most venue sites answer a plain `httpx.get` with a desktop User-Agent. Some sit
behind a TLS/HTTP2-fingerprinting challenge that 403s httpx no matter the
headers; `curl_cffi` with `impersonate="chrome"` presents a real Chrome
fingerprint and gets through — a valid production client, not a recon-only
trick. `tools/recon.py` reports which of the two a site needs; record the choice
in the scraper's SOURCE.md.

Existing scrapers keep their own clients; use this for new ones.
"""

from __future__ import annotations

import httpx

# A current desktop Chrome UA. Sites that 403 the default httpx UA usually
# accept this one.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

# Honest, stable identification of our crawler (docs/nl-cities-plan.md). The
# single source of truth for the Cartelita marker; build site-specific variants
# from it rather than re-typing the string.
CARTELITA_UA = "Cartelita (+https://cartelita.july.dev)"
# "Mozilla/5.0 (compatible; ...)" keeps naive UA filters happy without
# pretending to be a browser.
CARTELITA_COMPAT_UA = f"Mozilla/5.0 (compatible; {CARTELITA_UA})"
# A browser token for sites that gate on one, plus the Cartelita marker.
CARTELITA_BROWSER_UA = f"{BROWSER_UA} {CARTELITA_UA}"
CARTELITA_BROWSER_HEADERS = {"User-Agent": CARTELITA_BROWSER_UA}


def fetch(
    url: str,
    *,
    impersonate: bool = False,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> str:
    """GET `url` and return the body text; raise on a non-2xx status.

    `impersonate=False` uses httpx with a browser User-Agent (plus `headers`).
    `impersonate=True` uses curl_cffi impersonating Chrome — its own UA and
    header order are part of the fingerprint, so only extra `headers` are sent.
    """
    if impersonate:
        from curl_cffi import requests as curl_requests

        r = curl_requests.get(
            url, impersonate="chrome", headers=headers, timeout=timeout,
            allow_redirects=True,
        )
        r.raise_for_status()
        return r.text
    resp = httpx.get(
        url,
        headers={"User-Agent": BROWSER_UA, **(headers or {})},
        follow_redirects=True,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text
