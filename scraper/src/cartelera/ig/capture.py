"""Instagram capture: timeline JSON parser + a thin Playwright driver.

Two clearly separated halves:

- **Pure functions** (`parse_timeline`, `select_new_posts`, `proxy_settings`,
  `is_session_invalid`) — all the logic that decides *what* we keep. Unit
  tested against a hand-built fixture; no browser needed.
- **The driver** (`capture_new_posts`, `login_interactively`) — the thinnest
  possible Playwright wrapper around those decisions. It is deliberately dumb
  and inspectable because it can only be verified against the live site with a
  real logged-in session.

We read the profile timeline from the XHR JSON the web app itself fetches
rather than scraping the DOM: the JSON carries the shortcode, the full
caption, the timestamp and every carousel image URL, and it changes far less
often than the markup.
"""
from __future__ import annotations
import datetime as dt
import json
import logging
import random
import time
from typing import Any
from urllib.parse import unquote, urlsplit

from cartelera.ig.types import CapturedPost, RawImage

logger = logging.getLogger(__name__)

# The connection key of the profile-timeline response in the current web app.
# The request URL is not stable (the same /graphql/query endpoint serves every
# query, keyed by an opaque doc_id), so this key in the *body* is how we
# recognise a timeline response.
TIMELINE_CONNECTION_KEY = "xdt_api__v1__feed__user_timeline_graphql_connection"

PROFILE_URL = "https://www.instagram.com/{handle}/"
LOGIN_URL = "https://www.instagram.com/accounts/login/"
INSTAGRAM_URL = "https://www.instagram.com/"

# A real desktop Chrome UA — Playwright's default headless UA advertises
# "HeadlessChrome", which Instagram treats as a bot signal.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}
LOCALE = "en-US"
LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]
# Playwright's Chromium sets navigator.webdriver = true; hide it before any
# page script runs.
STEALTH_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)

# URL fragments that mean Instagram bounced us off the profile.
LOGIN_WALL_MARKERS = ("/accounts/login", "/accounts/suspended", "/challenge")
# Selector for the login form, used only as corroboration when no timeline
# response arrived at all.
LOGIN_FORM_SELECTOR = "input[name='password']"

DEFAULT_LIMIT_PER_PROFILE = 12
DEFAULT_IMAGE_CONTENT_TYPE = "image/jpeg"
PAGE_TIMEOUT_MS = 45_000
# How long to keep waiting for the timeline XHR after the page fires `load`.
TIMELINE_SETTLE_MS = 6_000
# Human-shaped pause between profiles (seconds).
PROFILE_JITTER_S = (5.0, 15.0)

# ig-login bootstrap: how long the human gets, and how often we look.
LOGIN_TIMEOUT_S = 600
LOGIN_POLL_INTERVAL_S = 3.0
SESSION_COOKIE_NAME = "sessionid"


class IgSessionInvalid(Exception):
    """Instagram served a login/challenge wall instead of the profile.

    The stored storage_state is dead (or the account is blocked); re-run
    `cartelera ig-login`. Never raised for an ordinary empty/slow page."""


# --------------------------------------------------------------------------
# Pure parsing
# --------------------------------------------------------------------------

def parse_timeline(payload: dict, handle: str) -> list[CapturedPost]:
    """Turn one profile-timeline JSON body into `CapturedPost`s, in feed order.

    Defensive by construction: anything we cannot read confidently is skipped,
    never guessed. A post needs a shortcode to be worth anything; everything
    else degrades to None/empty. `images` stays empty — downloading is the
    driver's job. Pinned posts arrive like any other post and need no special
    handling."""
    posts: list[CapturedPost] = []
    for node in _timeline_nodes(payload):
        post = _parse_node(node, handle)
        if post is not None:
            posts.append(post)
    return posts


def _timeline_nodes(payload: Any) -> list[dict]:
    """The `node` dicts of the timeline connection, or [] for any other shape."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    connection = data.get(TIMELINE_CONNECTION_KEY)
    if not isinstance(connection, dict):
        return []
    edges = connection.get("edges")
    if not isinstance(edges, list):
        return []
    nodes = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if isinstance(node, dict):
            nodes.append(node)
    return nodes


def _parse_node(node: dict, handle: str) -> CapturedPost | None:
    shortcode = node.get("code")
    if not isinstance(shortcode, str) or not shortcode:
        return None
    return CapturedPost(
        shortcode=shortcode,
        handle=handle,
        caption=_caption_text(node),
        posted_at=_taken_at_utc(node),
        image_urls=_image_urls(node),
    )


def _caption_text(node: dict) -> str | None:
    caption = node.get("caption")
    if not isinstance(caption, dict):
        return None
    text = caption.get("text")
    return text if isinstance(text, str) else None


def _taken_at_utc(node: dict) -> dt.datetime | None:
    """`taken_at` is unix seconds; return it as a tz-aware UTC datetime."""
    taken_at = node.get("taken_at")
    if not isinstance(taken_at, (int, float)) or isinstance(taken_at, bool):
        return None
    try:
        return dt.datetime.fromtimestamp(taken_at, tz=dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _image_urls(node: dict) -> list[str]:
    """Every still image of a post, in posted order.

    A carousel yields one URL per child (its cover image for video children —
    we keep the cover, never the video); a single-media post yields its own
    best candidate, which for a video post is its cover frame."""
    carousel = node.get("carousel_media")
    if isinstance(carousel, list) and carousel:
        urls = []
        for child in carousel:
            if not isinstance(child, dict):
                continue
            url = _best_candidate_url(child)
            if url:
                urls.append(url)
        return urls
    url = _best_candidate_url(node)
    return [url] if url else []


def _best_candidate_url(media: dict) -> str | None:
    """The first `image_versions2.candidates` entry — Instagram serves them
    largest-first, so the first one is the highest resolution available."""
    versions = media.get("image_versions2")
    if not isinstance(versions, dict):
        return None
    candidates = versions.get("candidates")
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if isinstance(candidate, dict):
            url = candidate.get("url")
            if isinstance(url, str) and url:
                return url
    return None


# --------------------------------------------------------------------------
# Pure driver decisions
# --------------------------------------------------------------------------

def select_new_posts(
    posts: list[CapturedPost], known_shortcodes: set[str], limit: int
) -> list[CapturedPost]:
    """The feed window we act on: dedupe, take the newest `limit`, drop known.

    A profile load can produce several overlapping timeline responses, hence
    the dedupe (first occurrence wins, feed order preserved). The limit is
    applied *before* the known-shortcode filter on purpose: it defines how far
    back down the feed we look, so archived posts inside the window do not pull
    older posts into view."""
    seen: set[str] = set()
    window: list[CapturedPost] = []
    for post in posts:
        if post.shortcode in seen:
            continue
        seen.add(post.shortcode)
        window.append(post)
        if len(window) >= limit:
            break
    return [p for p in window if p.shortcode not in known_shortcodes]


def proxy_settings(proxy_url: str | None) -> dict | None:
    """Playwright's `proxy` option from a `scheme://user:pass@host:port` URL.

    Playwright wants credentials as separate fields, not inline in `server`,
    so we split them out (and percent-decode them — proxy passwords routinely
    contain reserved characters)."""
    if not proxy_url:
        return None
    parsed = urlsplit(proxy_url)
    if not parsed.hostname:
        raise ValueError(f"IG_PROXY_URL is not a usable proxy URL: {proxy_url!r}")
    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    settings = {"server": server}
    if parsed.username:
        settings["username"] = unquote(parsed.username)
    if parsed.password:
        settings["password"] = unquote(parsed.password)
    return settings


def is_session_invalid(
    final_url: str, saw_timeline: bool, has_login_form: bool
) -> bool:
    """Did Instagram bounce us to a wall rather than serve the profile?

    Two signals: the URL we ended up on, and — only when no timeline response
    arrived at all — a visible login form. A quiet page on its own is not
    proof of a dead session (an empty profile looks the same), so we never
    fail a source on that alone."""
    if any(marker in final_url for marker in LOGIN_WALL_MARKERS):
        return True
    return not saw_timeline and has_login_form


def timeline_payloads(bodies: list[str]) -> list[dict]:
    """Parse the response bodies that look like timeline responses.

    Kept separate from the browser so the body→payload step stays testable."""
    payloads = []
    for body in bodies:
        if TIMELINE_CONNECTION_KEY not in body:
            continue
        try:
            payload = json.loads(body)
        except ValueError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def capture_new_posts(
    handles_with_known: list[tuple[str, set[str]]],
    storage_state: dict,
    proxy_url: str | None,
    limit_per_profile: int = DEFAULT_LIMIT_PER_PROFILE,
) -> dict[str, list[CapturedPost]]:
    """Capture the new posts of each handle in one browser session.

    One Chromium launch for the whole call, profiles visited sequentially with
    a human-shaped pause in between. Returns `{handle: [CapturedPost, ...]}`
    with images already downloaded. Raises `IgSessionInvalid` as soon as any
    profile shows a login/challenge wall — the session is shared, so the rest
    of the run would fail the same way. We never attempt an automated login
    here; that is `cartelera ig-login`'s human-driven job."""
    from playwright.sync_api import sync_playwright

    results: dict[str, list[CapturedPost]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=LAUNCH_ARGS,
                                     proxy=proxy_settings(proxy_url))
        try:
            context = _new_context(browser, storage_state=storage_state)
            page = context.new_page()
            page.set_default_timeout(PAGE_TIMEOUT_MS)
            for idx, (handle, known) in enumerate(handles_with_known):
                if idx:
                    time.sleep(random.uniform(*PROFILE_JITTER_S))
                posts = _capture_profile(context, page, handle, known, limit_per_profile)
                results[handle] = posts
        finally:
            browser.close()
    return results


def _new_context(browser, storage_state: dict | None):
    """A context that looks like an ordinary desktop Chrome."""
    context = browser.new_context(
        storage_state=storage_state or None,
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        locale=LOCALE,
    )
    context.add_init_script(STEALTH_INIT_SCRIPT)
    return context


def _capture_profile(
    context, page, handle: str, known: set[str], limit: int
) -> list[CapturedPost]:
    """Load one profile, parse its timeline XHRs, download the new posts' images."""
    bodies = _load_profile(page, handle)
    if not bodies:
        # One reload, no more: a single missed XHR is common, a loop is a ban.
        logger.info("no timeline response for %r; reloading once", handle)
        bodies = _load_profile(page, handle, reload=True)

    if is_session_invalid(page.url, bool(bodies), _has_login_form(page)):
        raise IgSessionInvalid(
            f"Instagram served a login/challenge wall for {handle!r} "
            f"(landed on {page.url!r}); run `cartelera ig-login`"
        )

    posts: list[CapturedPost] = []
    for payload in timeline_payloads(bodies):
        posts.extend(parse_timeline(payload, handle))
    new_posts = select_new_posts(posts, known, limit)
    logger.info("%s: %d timeline posts, %d new", handle, len(posts), len(new_posts))
    for post in new_posts:
        post.images = _download_images(context, post.image_urls)
    return new_posts


def _load_profile(page, handle: str, reload: bool = False) -> list[str]:
    """Navigate (or reload) and return the bodies of the timeline responses.

    Bodies are read after the page settles rather than inside the response
    handler: Playwright's sync API forbids calling into the browser from an
    event callback."""
    responses = []
    handler = lambda response: responses.append(response)  # noqa: E731
    page.on("response", handler)
    try:
        if reload:
            page.reload(wait_until="domcontentloaded")
        else:
            page.goto(PROFILE_URL.format(handle=handle), wait_until="domcontentloaded")
        page.wait_for_timeout(TIMELINE_SETTLE_MS)
    finally:
        page.remove_listener("response", handler)
    return _json_bodies(responses)


def _json_bodies(responses) -> list[str]:
    """Bodies of the JSON responses that mention the timeline connection.

    Non-JSON responses (images above all) are skipped without being read, and
    any body that is no longer retrievable is skipped rather than fatal."""
    bodies = []
    for response in responses:
        try:
            if "json" not in response.headers.get("content-type", ""):
                continue
            body = response.text()
        except Exception:  # noqa: BLE001 - a body we can't read is simply not a post
            continue
        if TIMELINE_CONNECTION_KEY in body:
            bodies.append(body)
    return bodies


def _has_login_form(page) -> bool:
    try:
        return page.query_selector(LOGIN_FORM_SELECTOR) is not None
    except Exception:  # noqa: BLE001 - a page we can't query is not evidence
        return False


def _download_images(context, urls: list[str]) -> list[RawImage]:
    """Fetch each image through the browser context — same cookies, same proxy.

    A single image that won't download is logged and skipped; losing one frame
    of a carousel is not a reason to lose the post."""
    images = []
    for url in urls:
        try:
            response = context.request.get(url)
            if not response.ok:
                logger.warning("image %s returned HTTP %s", url, response.status)
                continue
            content_type = response.headers.get("content-type") or DEFAULT_IMAGE_CONTENT_TYPE
            images.append(RawImage(url=url, content_type=content_type, data=response.body()))
        except Exception as exc:  # noqa: BLE001 - one lost image, not one lost post
            logger.warning("image download failed for %s: %s", url, exc)
    return images


def login_interactively(
    proxy_url: str | None,
    timeout_s: int = LOGIN_TIMEOUT_S,
    poll_interval_s: float = LOGIN_POLL_INTERVAL_S,
) -> dict:
    """Open a headed Chromium and wait for a human to log in; return storage_state.

    Deliberately human-driven: checkpoints, 2FA and "was this you?" prompts are
    exactly what an automated login trips over, and a human handles them in
    seconds. We only watch for the `sessionid` cookie to appear, then snapshot
    the context. Raises TimeoutError if nobody logs in within `timeout_s`."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=LAUNCH_ARGS,
                                     proxy=proxy_settings(proxy_url))
        try:
            context = _new_context(browser, storage_state=None)
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                if _has_session_cookie(context):
                    return context.storage_state()
                page.wait_for_timeout(int(poll_interval_s * 1000))
            raise TimeoutError(
                f"no {SESSION_COOKIE_NAME} cookie after {timeout_s}s; login was not completed"
            )
        finally:
            browser.close()


def _has_session_cookie(context) -> bool:
    return any(
        c.get("name") == SESSION_COOKIE_NAME and c.get("value")
        for c in context.cookies(INSTAGRAM_URL)
    )
