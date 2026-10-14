"""Scraper recon: where does a venue site's event data actually live?

    uv run python tools/recon.py <url> [--scroll] [--click SEL]... [--wait MS]
                                       [--top N] [--dump DIR] [--no-browser]

One-time local setup (the browser binary; the prod image installs it itself):

    uv run playwright install chromium-headless-shell

What it does, in order:

1. **Reachability probe** — plain `httpx` (browser UA) and `curl_cffi`
   (`impersonate="chrome"`), the two production-grade clients.
2. **One headless page load** in an isolated Playwright Chromium (never the
   user's browser; parallel-safe), waiting for network idle, optionally
   scrolling / clicking load-more buttons, recording every response.
3. **Filters** the responses to XHR/fetch/document/JSON, dropping analytics,
   consent and tracker hosts plus static assets.
4. **Scans the raw HTML for embedded state** (`__NEXT_DATA__`, Nuxt, RSC
   flight, `window.__*_STATE__`, `application/json` scripts, JSON-LD, Astro
   island props, JSON in `data-*` attributes).
5. **Scores** every JSON/HTML candidate by how much it looks like an event list.
6. **Verdict** — server-rendered vs JS-rendered, and which HTTP client works.
7. Prints a compact ranked report (a few hundred to ~1.5k tokens). `--dump DIR`
   saves every captured body plus raw/rendered HTML for a closer look or for
   the Phase-4 independent cross-check.

The parsing/scoring/verdict functions are pure and tested offline in
`tests/test_recon.py`; only `probe_http` and `browse` touch the network.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cartelera.scrapers.http import BROWSER_UA

# --------------------------------------------------------------------------
# Heuristics
# --------------------------------------------------------------------------

_MONTHS = (
    r"jan|feb|mar|apr|may|mai|jun|jul|aug|ago|sep|set|oct|okt|out|nov|dec|dic|des|"
    r"gen|ene|abr|maa|mrt|mei"
)
DATE_RE = re.compile(
    r"\b20\d\d-[01]\d-[0-3]\d"  # ISO
    r"|\b[0-3]?\d[/.][01]?\d[/.]20\d\d"  # 05/09/2026, 5.9.2026
    rf"|\b[0-3]?\d\.?\s+(?:de\s+)?(?:{_MONTHS})[a-zç]*\.?\s+(?:de\s+)?20\d\d",  # 5 sep 2026
    re.I,
)
EVENTY_KEYS = {
    "title", "name", "start", "startdate", "start_date", "date", "datetime",
    "starttime", "start_time", "time", "price", "prices", "venue", "location",
    "url", "slug", "image", "genre", "category", "categories", "tickets",
    "performances", "sessions", "showtimes", "events", "doors",
}
EVENTY_SUBSTR = re.compile(
    r"title|date|time|price|venue|start|ticket|session|perform|genre|categor"
)
NOISE_RE = re.compile(
    r"google|doubleclick|doubletag|gtm|analytics|facebook|hotjar|clarity|"
    r"cookiebot|onetrust|sentry|newrelic|nr-data|tiktok|linkedin|pinterest|"
    r"matomo|plausible|youtube|vimeo|recaptcha|hcaptcha|hubspot|hs-sites|"
    r"hscollectedforms|hsforms|hs-scripts|hs-analytics|intercom|"
    r"segment|cloudflareinsights|/cdn-cgi/|usercentrics|cookielaw|consent|"
    r"cookieyes|complianz|didomi|trustarc|bing\.com|snapchat|twitter|x\.com/i|"
    r"adservice|criteo|taboola|quantserve|scorecardresearch|mixpanel|amplitude|"
    r"fullstory|mouseflow|crazyegg|smartlook|leadinfo|trustpilot"
)
STATIC_EXT_RE = re.compile(
    r"\.(?:png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|otf|eot|css|js|mjs|map|mp4|webm|mp3)(?:\?|$)",
    re.I,
)
# Text a bot-protection interstitial serves instead of the page. (Cloudflare's
# `challenge-platform` script is NOT here: it also sits on pages it let through.)
CHALLENGE_MARKERS = (
    "Just a moment...",
    "cf-chl-",
    "challenges.cloudflare.com",
    "Attention Required! | Cloudflare",
    "_Incapsula_Resource",
    "captcha-delivery.com",
    "px-captcha",
)

_SCRIPT = r"<script\b[^>]*?"
STATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("__NEXT_DATA__", re.compile(_SCRIPT + r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)),
    ("__NUXT_DATA__", re.compile(_SCRIPT + r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)),
    ("window.__NUXT__", re.compile(r"window\.__NUXT__\s*=\s*(.*?)</script>", re.S)),
    (
        "window.__*_STATE__",
        re.compile(
            r"window\.__(?:INITIAL_STATE|APOLLO_STATE|PRELOADED_STATE|STATE|DATA)__\s*=\s*(.*?)</script>",
            re.S,
        ),
    ),
    ("application/json script", re.compile(_SCRIPT + r'type="application/json"[^>]*>(.*?)</script>', re.S)),
    ("JSON-LD", re.compile(_SCRIPT + r'type="application/ld\+json"[^>]*>(.*?)</script>', re.S)),
    ("Astro island props", re.compile(r'<astro-island\b[^>]*?\sprops="([^"]{200,})"', re.S)),
    ("data-* JSON attr", re.compile(r'\sdata-[\w-]+="((?:\[\s*)?\{&quot;[^"]{200,})"', re.S)),
    ("data-* JSON attr", re.compile(r"\sdata-[\w-]+='((?:\[\s*)?\{\"[^']{200,})'", re.S)),
]
RSC_RE = re.compile(r"self\.__next_f\.push\((\[.*?\])\)\s*;?\s*</script>", re.S)
_HTML_ESCAPED = {"Astro island props", "data-* JSON attr"}


@dataclass
class Candidate:
    """One place event data might live, with its event-likeness score."""

    kind: str  # "XHR/JSON", "XHR/HTML", "EMBED", "EMBED(raw)"
    label: str  # request line or embedded-state name
    size: int
    score: float = 0.0
    shape: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class ProbeResult:
    """What one plain HTTP client got for the page URL."""

    client: str  # "httpx" | "curl_cffi"
    status: int | None = None  # None when the request errored
    body: str = ""
    error: str = ""

    def summary(self) -> str:
        if self.status is None:
            return f"{self.client} error {self.error.split(':')[0]}"
        return f"{self.client} {self.status} {len(self.body):,}B"

    @property
    def tls_error(self) -> bool:
        """Certificate verification failed — a server misconfiguration (often
        a missing intermediate), not bot protection."""
        return self.status is None and bool(re.search(r"certif|ssl", self.error, re.I))


@dataclass
class ObjectArray:
    path: str
    length: int
    sample: dict[str, Any]


# --------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------


def try_json(text: str) -> Any | None:
    """Parse `text` as JSON (tolerating a trailing `;`), else None."""
    text = text.strip().rstrip(";").strip()
    if not text or text[0] not in "[{":
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _is_id_keyed(d: dict[str, Any]) -> bool:
    """A dict used as a list: {"28818": {...}, "28823": {...}, ...}."""
    if len(d) < 3:
        return False
    keys = list(d)[:20]
    return all(isinstance(d[k], dict) for k in keys) and all(
        re.fullmatch(r"[\w-]*\d[\w-]*", str(k)) for k in keys
    )


def structure_sketch(value: Any, depth: int = 0, max_depth: int = 3, max_keys: int = 12) -> str:
    """Compact type sketch, e.g. `{a,b,c:[{x,y}]×42}`; id-keyed dicts collapse
    to `{<id>:{x,y}}×N`."""
    if depth >= max_depth:
        return "…"
    if isinstance(value, dict):
        if _is_id_keyed(value):
            first = next(iter(value.values()))
            return "{<id>:" + structure_sketch(first, depth + 1, max_depth, max_keys) + f"}}×{len(value)}"
        parts = []
        for k in list(value)[:max_keys]:
            v = value[k]
            parts.append(
                k + (":" + structure_sketch(v, depth + 1, max_depth, max_keys) if isinstance(v, (dict, list)) and v else "")
            )
        more = f",+{len(value) - max_keys}" if len(value) > max_keys else ""
        return "{" + ",".join(parts) + more + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + structure_sketch(value[0], depth + 1, max_depth, max_keys) + f"]×{len(value)}"
    return type(value).__name__


def object_arrays(value: Any, path: str = "$", depth: int = 0) -> list[ObjectArray]:
    """Every array of objects in `value` (id-keyed dicts count as arrays)."""
    out: list[ObjectArray] = []
    if depth > 12:
        return out
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            out.append(ObjectArray(path, len(value), value[0]))
        for item in value[:3]:
            out.extend(object_arrays(item, f"{path}[0]", depth + 1))
    elif isinstance(value, dict):
        if _is_id_keyed(value):
            out.append(ObjectArray(f"{path}.*", len(value), next(iter(value.values()))))
            for item in list(value.values())[:3]:
                out.extend(object_arrays(item, f"{path}.*", depth + 1))
        else:
            for k, v in list(value.items())[:200]:
                out.extend(object_arrays(v, f"{path}.{k}", depth + 1))
    return out


def eventy_keys(sample: dict[str, Any]) -> set[str]:
    """Event-like keys of `sample` and of its nested objects one level down
    (WordPress's `wp_post.post_title` etc.)."""
    keys = {str(k).lower() for k in sample}
    for v in sample.values():
        if isinstance(v, dict):
            keys |= {str(k).lower() for k in v}
    return {k for k in keys if k in EVENTY_KEYS or EVENTY_SUBSTR.search(k)}


def _array_score(arr: ObjectArray) -> float:
    return min(arr.length, 200) / 10 + 3 * len(eventy_keys(arr.sample))


def count_dates(text: str) -> int:
    return len(DATE_RE.findall(text[:500_000]))


def score_json(data: Any, raw: str) -> tuple[float, list[str]]:
    """Event-likeness of a JSON document: its best object array (length +
    event-like keys) plus date-like strings in the raw text."""
    notes: list[str] = []
    score = 0.0
    arrays = [a for a in object_arrays(data) if a.length >= 2] or object_arrays(data)
    if arrays:
        best = max(arrays, key=_array_score)
        score += _array_score(best)
        notes.append(
            f"best obj-array {best.path} ×{best.length}; event-ish keys: {sorted(eventy_keys(best.sample))}"
        )
        notes.append("sample: " + json.dumps(best.sample, ensure_ascii=False, default=str)[:300])
    dates = count_dates(raw)
    if dates:
        score += min(dates, 300) / 10
        notes.append(f"{dates} date-like strings")
    return score, notes


def unwrap_astro(value: Any) -> Any:
    """Undo Astro's island-prop serialization (`[0, v]` value, `[1, [...]]`
    array, other tags = special types) so the scorer sees plain objects."""
    if isinstance(value, dict):
        return {k: unwrap_astro(v) for k, v in value.items()}
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int) and 0 <= value[0] <= 11:
        tag, inner = value
        if tag == 1 and isinstance(inner, list):
            return [unwrap_astro(x) for x in inner]
        if tag == 0:
            return unwrap_astro(inner)
        return inner
    if isinstance(value, list):
        return [unwrap_astro(x) for x in value]
    return value


def jsonld_types(data: Any) -> list[str]:
    """All `@type` values anywhere in a JSON-LD document."""
    found: list[str] = []
    if isinstance(data, dict):
        t = data.get("@type")
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found.extend(x for x in t if isinstance(x, str))
        for v in data.values():
            found.extend(jsonld_types(v))
    elif isinstance(data, list):
        for v in data:
            found.extend(jsonld_types(v))
    return found


def _raw_candidate(name: str, blob: str, extra: str = "") -> Candidate:
    dates = count_dates(blob)
    title_keys = len(re.findall(r'\\?"(?:title|name|start\w*|date)\\?"\s*:', blob))
    return Candidate(
        "EMBED(raw)",
        name,
        len(blob),
        dates / 10 + min(title_keys, 200) / 20,
        notes=[
            f"not plain JSON{extra}; {dates} date-like strings, {title_keys} title/date-ish keys",
            blob[:160].replace("\n", " "),
        ],
    )


def extract_embedded(raw_html: str) -> list[Candidate]:
    """Find and score embedded state in the server-sent HTML."""
    out: list[Candidate] = []
    seen: set[int] = set()  # blob offsets; __NEXT_DATA__ is also an application/json script
    for name, rx in STATE_PATTERNS:
        for m in rx.finditer(raw_html):
            if m.start(1) in seen:
                continue
            seen.add(m.start(1))
            blob = m.group(1)
            if name in _HTML_ESCAPED:
                blob = html_lib.unescape(blob)
            data = try_json(blob)
            if data is None:
                if len(blob) > 500:
                    out.append(_raw_candidate(name, blob))
                continue
            if name == "Astro island props":
                data = unwrap_astro(data)
            score, notes = score_json(data, blob)
            if name == "JSON-LD":
                types = jsonld_types(data)
                n_events = sum(1 for t in types if t.endswith("Event"))
                notes.insert(0, f"@types: {sorted(set(types))[:8]}" + (f"; {n_events} *Event" if n_events else ""))
                if n_events:
                    score += 10 + min(n_events, 100) / 5
            out.append(Candidate("EMBED", name, len(blob), score, structure_sketch(data), notes))
    # Next.js RSC flight: many `self.__next_f.push([1,"..."])` chunks forming one stream.
    chunks: list[str] = []
    for m in RSC_RE.finditer(raw_html):
        data = try_json(m.group(1))
        if isinstance(data, list):
            chunks.extend(x for x in data if isinstance(x, str))
    if chunks:
        out.append(_raw_candidate("RSC flight (self.__next_f)", "".join(chunks), f", {len(chunks)} chunks"))
    return out


def is_noise(url: str) -> bool:
    """Analytics/consent/tracker endpoints and static assets."""
    return bool(NOISE_RE.search(url)) or bool(STATIC_EXT_RE.search(urlparse(url).path + "?"))


def is_challenge(body: str) -> bool:
    """Is this a bot-protection interstitial rather than the page?"""
    head = body[:20_000]
    return any(m in head for m in CHALLENGE_MARKERS)


def internal_links(page_html: str, host: str) -> int:
    """Distinct same-site links with a non-trivial path (event pages are deep)."""
    host_rx = re.escape(host.removeprefix("www."))
    rx = re.compile(r'href="(?:https?://(?:www\.)?' + host_rx + r')?(/[^"#]{8,})"')
    return len(set(rx.findall(page_html)))


def has_content(probe: ProbeResult, reference_links: int, host: str) -> bool:
    """Did a plain client get the real page, not a challenge or a stub?

    With a browser reference (internal links in the browser's raw HTML), the
    client must see at least half of them; without one, a non-trivial body."""
    if probe.status != 200 or is_challenge(probe.body):
        return False
    if reference_links > 0:
        return internal_links(probe.body, host) >= 0.5 * reference_links
    return len(probe.body) > 2_000


def client_verdict(httpx_ok: bool, curl_ok: bool, tls_error: bool = False) -> str:
    """Which production HTTP client can fetch the page. `httpx_ok`/`curl_ok`
    come from `has_content` — a 200 carrying the real page, not just any 200."""
    if httpx_ok:
        return "plain HTTP (httpx) is enough"
    if curl_ok:
        return "httpx is blocked → use curl_cffi (requests.get(url, impersonate='chrome'))"
    if tls_error:
        return (
            "TLS certificate verification failed (incomplete chain?) — not bot "
            "protection: pin the missing intermediate (see scrapers/certs/, auditori.py)"
        )
    return "browser-only / blocked: neither httpx nor curl_cffi got the page"


def render_verdict(raw_links: int, rendered_links: int) -> str:
    if rendered_links == 0 or raw_links >= 0.8 * rendered_links:
        return "SERVER-RENDERED (raw ≈ rendered)"
    return "JS-RENDERED (rendered DOM ≫ raw HTML) → use the API/embedded candidate below"


def score_html_fragment(body: str) -> tuple[float, list[str]]:
    """XHR that returns HTML (admin-ajax, htmx, load-more): dates + markup."""
    dates = count_dates(body)
    score = dates / 10 + (2 if body.lstrip()[:1] == "<" else 0)
    return score, [f"{dates} date-like strings", body[:160].replace("\n", " ")]


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------


def probe_http(url: str) -> tuple[ProbeResult, ProbeResult]:
    """GET `url` with httpx (browser UA) and curl_cffi (Chrome impersonation)."""
    import httpx

    hx = ProbeResult("httpx")
    try:
        r = httpx.get(url, headers={"User-Agent": BROWSER_UA}, follow_redirects=True, timeout=20)
        hx.status, hx.body = r.status_code, r.text
    except Exception as e:  # noqa: BLE001 — report any client failure
        hx.error = f"{e.__class__.__name__}: {e}"
    cc = ProbeResult("curl_cffi")
    try:
        from curl_cffi import requests as curl_requests

        r2 = curl_requests.get(url, impersonate="chrome", timeout=20, allow_redirects=True)
        cc.status, cc.body = r2.status_code, r2.text
    except Exception as e:  # noqa: BLE001
        cc.error = f"{e.__class__.__name__}: {e}"
    return hx, cc


@dataclass
class BrowseResult:
    raw_html: str = ""
    rendered: str = ""
    main_status: int = 0
    n_responses: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    other: list[str] = field(default_factory=list)
    error: str = ""


def browse(
    url: str, *, scroll: bool, clicks: list[str], wait_ms: int, dump: Path | None
) -> BrowseResult:
    """One isolated headless Chromium page load, capturing responses."""
    res = BrowseResult()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        res.error = "playwright not installed (`uv sync`)"
        return res
    page_host = urlparse(url).hostname or ""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            res.error = (
                f"{e.__class__.__name__} launching Chromium — run "
                "`uv run playwright install chromium-headless-shell`"
            )
            return res
        try:
            ua = re.sub(r"Chrome/[\d.]+", f"Chrome/{browser.version}", BROWSER_UA)
            ctx = browser.new_context(locale="en-US", user_agent=ua)
            page = ctx.new_page()
            responses: list[Any] = []
            page.on("response", lambda r: responses.append(r))
            main = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            res.main_status = main.status if main else 0
            try:
                res.raw_html = main.text() if main else ""
            except Exception:  # noqa: BLE001 — redirects/no body
                res.raw_html = ""
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:  # noqa: BLE001 — chatty pages never idle
                pass
            if scroll:
                for _ in range(15):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(300)
            for sel in clicks:
                try:
                    page.locator(sel).first.click(timeout=5_000)
                    page.wait_for_timeout(1_500)
                except Exception as e:  # noqa: BLE001
                    print(f"! click {sel!r} failed: {e.__class__.__name__}", file=sys.stderr)
            page.wait_for_timeout(wait_ms)
            res.rendered = page.content()
            res.n_responses = len(responses)
            main_url = (main.url if main else url).rstrip("/")
            for i, r in enumerate(responses):
                _classify_response(i, r, res, page_host, main_url, dump)
        finally:
            browser.close()
    return res


def _classify_response(
    i: int, r: Any, res: BrowseResult, page_host: str, main_url: str, dump: Path | None
) -> None:
    req = r.request
    rt = req.resource_type
    ct = (r.headers.get("content-type") or "").split(";")[0].strip()
    rurl: str = r.url
    if rt not in ("xhr", "fetch", "document", "other") and "json" not in ct:
        return
    if is_noise(rurl) or ct.startswith(("image/", "font/", "text/css")):
        return
    if rt == "document" and rurl.rstrip("/") == main_url:
        return
    try:
        body = r.text()
    except Exception:  # noqa: BLE001 — redirects, aborted requests
        body = ""
    label = f"{req.method} {r.status} {rt} {ct or '?'} {rurl[:300]}"
    if req.method != "GET" and req.post_data:
        label += f"\n      POST body: {req.post_data[:200]}"
    if (urlparse(rurl).hostname or "").removeprefix("www.") != page_host.removeprefix("www."):
        label += "  [3rd-party]"
    data = try_json(body)
    saved = ""
    if dump and body:
        path = dump / f"resp_{i:03d}.{'json' if data is not None else 'txt'}"
        path.write_text(body)
        saved = f"saved: {path}"
    if data is not None:
        score, notes = score_json(data, body)
        cand = Candidate("XHR/JSON", label, len(body), score, structure_sketch(data), notes)
    elif rt in ("xhr", "fetch") and body:
        score, notes = score_html_fragment(body)
        cand = Candidate("XHR/HTML", label, len(body), score, notes=notes)
    else:
        res.other.append(label)
        return
    if saved:
        cand.notes.append(saved)
    res.candidates.append(cand)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--scroll", action="store_true", help="scroll to the bottom to trigger lazy loads")
    ap.add_argument(
        "--click", action="append", default=[], metavar="SEL",
        help="selector to click after load (e.g. a load-more button); repeatable",
    )
    ap.add_argument("--wait", type=int, default=2500, metavar="MS", help="ms to wait for late XHRs (default 2500)")
    ap.add_argument("--top", type=int, default=8, metavar="N", help="candidates to show (default 8)")
    ap.add_argument("--dump", metavar="DIR", help="save captured bodies + raw/rendered/httpx HTML here")
    ap.add_argument("--no-browser", action="store_true", help="HTTP probe + embedded-state scan only")
    a = ap.parse_args(argv)

    t0 = time.time()
    host = urlparse(a.url).hostname or ""
    dump = Path(a.dump) if a.dump else None
    if dump:
        dump.mkdir(parents=True, exist_ok=True)

    hx, cc = probe_http(a.url)
    br = BrowseResult(error="--no-browser") if a.no_browser else browse(
        a.url, scroll=a.scroll, clicks=a.click, wait_ms=a.wait, dump=dump
    )
    browser_ok = bool(not br.error and br.raw_html and not is_challenge(br.raw_html))
    # The server-sent HTML to scan for embedded state: the browser's, else the
    # best plain-client body, else (the browser solved a challenge) the
    # rendered DOM.
    raw_html = br.raw_html if browser_ok else next(
        (p.body for p in (hx, cc) if p.status == 200 and not is_challenge(p.body)),
        br.rendered if br.rendered and not is_challenge(br.rendered) else br.raw_html,
    )
    ref_links = internal_links(br.raw_html, host) if browser_ok else 0
    httpx_ok, curl_ok = has_content(hx, ref_links, host), has_content(cc, ref_links, host)

    candidates = br.candidates + extract_embedded(raw_html)
    candidates.sort(key=lambda c: -c.score)

    if dump:
        for name, text in (("raw.html", br.raw_html), ("rendered.html", br.rendered), ("httpx.html", hx.body)):
            if text:
                (dump / name).write_text(text)

    print(f"# recon {a.url}  ({time.time() - t0:.1f}s, {br.n_responses} responses)")
    tls = hx.tls_error and (cc.tls_error or cc.status is None)
    print(f"plain HTTP: {hx.summary()} | {cc.summary()} → {client_verdict(httpx_ok, curl_ok, tls)}")
    if br.error:
        print(f"! no browser pass: {br.error}")
    else:
        raw_links, rend_links = internal_links(br.raw_html, host), internal_links(br.rendered, host)
        print(
            f"browser: main doc {br.main_status}; raw HTML {raw_links} internal links / "
            f"{count_dates(br.raw_html)} dates, rendered {rend_links} links / "
            f"{count_dates(br.rendered)} dates → {render_verdict(raw_links, rend_links)}"
        )
        if br.main_status >= 400 or br.main_status == 0:
            print(f"! main document status {br.main_status} even in a real browser")
    blocked = [p.client for p in (hx, cc) if p.status in (403, 429, 503) or is_challenge(p.body)]
    if is_challenge(br.raw_html):
        blocked.append("browser (first response)")
        if br.rendered and not is_challenge(br.rendered):
            print("! the browser passed a challenge: raw-vs-rendered comparison is meaningless; scanned the rendered DOM")
    if blocked:
        print(f"! bot protection (403/429/503/challenge) for: {', '.join(blocked)}")

    print(f"\n## candidates (top {min(a.top, len(candidates))} of {len(candidates)}, by event-likeness)")
    for c in candidates[: a.top]:
        print(f"\n[{c.score:5.1f}] {c.kind}  {c.size:,}B  {c.label}")
        if c.shape:
            print(f"      shape: {c.shape[:400]}")
        for n in c.notes:
            print(f"      {n[:400]}")
    if br.other:
        print(f"\n## other non-static requests ({len(br.other)}), first 10")
        for o in br.other[:10]:
            print("  " + o[:200])


if __name__ == "__main__":
    main()
