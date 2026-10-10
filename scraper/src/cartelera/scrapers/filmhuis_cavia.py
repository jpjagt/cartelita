from __future__ import annotations
import copy
import datetime as dt
import html as html_module
import re
from urllib.parse import urldefrag, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Filmhuis Cavia (Van Hallstraat, Amsterdam-West) — a volunteer-run arthouse
# cinema. The site is a Concrete CMS install whose programme is ONE hand-edited
# WYSIWYG page per month (`/programma/<maand>-<yyyy>`, e.g. `oktober-2026`),
# linked from the "Programma" nav. Past months are taken down (404), so the nav
# is the only index. Each screening is a section opened by an `<hr id="...">`:
# a header `<p>` "Donderdag 1 oktober, 20:00<br><br>DOCU", optional `<h3>`
# series kicker, the `<h2>` title, a `<strong>` credits line
# "Director | 1984 | Brazil | 119’ | EN subtitles", an image, and NL/EN blurbs
# with an optional "MEER→"/"MORE→" link to a per-event detail page.
#
# Price: the sidebar states "Toegang 5 euro, tenzij anders vermeld" (entrance
# 5€ unless stated otherwise). Overrides are stated in prose as a line starting
# with "Tickets"/"Entrance"/"Toegang" — on the month page itself or on the
# linked detail page — so we fetch the (few) detail pages. See
# filmhuis_cavia_SOURCE.md.
BASE_URL = "https://www.filmhuiscavia.nl"
HOME_URL = BASE_URL + "/"
VENUE_SLUG = "filmhuis-cavia"

_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}
_MONTH_ALT = "|".join(_MONTHS)
_MONTH_SLUG = re.compile(rf"/programma/({_MONTH_ALT})-(\d{{4}})/?$")
# Header line: "Donderdag 1 oktober, 20:00" / "Vrijdag 6 en zaterdag 7 november,
# 20:30" / "Zaterdag 17 oktober" (no time). Day numbers precede the month name;
# an optional year and the time follow it.
_HEADER_MONTH = re.compile(rf"\b({_MONTH_ALT})\b", re.IGNORECASE)
_HEADER_TAIL = re.compile(r"^\s*(\d{4})?\s*,?\s*(?:(\d{1,2})[:.](\d{2}))?")
_PRICE_LINE = re.compile(
    r"^\s*(?:(?:NL|EN)\s+)?(tickets?|kaartjes?|entrance|entree|entrée|toegang)\b",
    re.IGNORECASE,
)
_AMOUNT = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?\b)")
_LANG_SEGMENT = re.compile(
    r"subtit|ondertit|dialog|no language|silent|stil\b|spoken|gesproken|taal|language",
    re.IGNORECASE,
)
_DEFAULT_PRICE = re.compile(
    r"(?:toegang|entrance)\s+(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)", re.IGNORECASE
)


def _clean(text: str) -> str:
    text = html_module.unescape(text).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _lines(el: Tag) -> list[str]:
    """Text of an element split on `<br>`, inline markup joined (not split)."""
    el = copy.copy(el)
    for br in el.find_all("br"):
        br.replace_with("\n")
    return [c for c in (_clean(x) for x in el.get_text("").split("\n")) if c]


def _section(hr: Tag) -> list[Tag]:
    out: list[Tag] = []
    for sib in hr.find_next_siblings():
        if sib.name == "hr":
            break
        out.append(sib)
    return out


def _format_amount(raw: str) -> str:
    raw = raw.replace(".", ",")
    if raw.endswith(",00"):
        raw = raw[:-3]
    return f"{raw}€"


def _price_from_line(line: str) -> str | None:
    """Normalize one stated price line ("Tickets : €8 (or Cineville)")."""
    low = line.lower()
    if "uitverkocht" in low or "sold out" in low or "sold-out" in low:
        return "sold-out"
    amounts = [a or b for a, b in _AMOUNT.findall(line)]
    if amounts:
        # Several tiers (e.g. with/without meal): show the highest public price.
        best = max(amounts, key=lambda s: float(s.replace(",", ".")))
        if float(best.replace(",", ".")) == 0:
            return "free"
        return _format_amount(best)
    # "Ticket: free (donations are welcome)" is free; "Donation-based" is not.
    if "gratis" in low or "free" in low or "vrije toegang" in low:
        return "free"
    if "donat" in low:
        return "donation"
    return None


def _stated_price(elements: list[Tag]) -> str | None:
    for el in elements:
        for line in _lines(el):
            if _PRICE_LINE.match(line):
                price = _price_from_line(line)
                if price:
                    return price
    return None


def default_price(html: str) -> str | None:
    """The sidebar's house price ("Toegang 5 euro, tenzij anders vermeld")."""
    soup = BeautifulSoup(html, "html.parser")
    side = soup.select_one(".col-sidebar") or soup
    m = _DEFAULT_PRICE.search(_clean(side.get_text(" ")))
    return _format_amount(m.group(1)) if m else None


def month_urls(html: str) -> list[str]:
    """Month programme pages linked from the site nav, in nav order."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for a in soup.select("a[href]"):
        url = urljoin(BASE_URL, a["href"]).split("#")[0]
        if _MONTH_SLUG.search(url) and url not in urls:
            urls.append(url)
    return urls


def _more_link(elements: list[Tag]) -> str | None:
    for el in elements:
        for a in el.select("a[href]") if isinstance(el, Tag) else []:
            text = _clean(a.get_text(" ")).upper()
            if text.startswith("MEER") or text.startswith("MORE"):
                url = urljoin(BASE_URL, a["href"])
                if url.startswith(BASE_URL + "/programma/"):
                    return url
    return None


def detail_urls(html: str) -> list[str]:
    """Same-site detail pages linked via MEER→/MORE→ (fragment stripped)."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".col-content") or soup
    urls: list[str] = []
    for hr in content.find_all("hr"):
        link = _more_link(_section(hr))
        if link:
            base = urldefrag(link)[0]
            if base not in urls:
                urls.append(base)
    return urls


def detail_price(html: str, fragment: str = "") -> str | None:
    """A stated price on a detail page, restricted to `#fragment`'s section."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".col-content") or soup
    if fragment:
        hr = content.find("hr", id=fragment)
        if hr is None:
            return None
        return _stated_price(_section(hr))
    return _stated_price([c for c in content.children if isinstance(c, Tag)])


def _page_month_year(page_url: str) -> tuple[int, int] | None:
    m = _MONTH_SLUG.search(page_url.split("#")[0])
    if not m:
        return None
    return _MONTHS[m.group(1).lower()], int(m.group(2))


def _language(credits: str | None) -> str | None:
    if not credits:
        return None
    for seg in (s.strip() for s in credits.split("|")):
        if seg and _LANG_SEGMENT.search(seg):
            return seg
    return None


def parse_month(
    html: str,
    page_url: str,
    details: dict[str, str] | None = None,
) -> list[ScrapedEvent]:
    """Parse one month programme page into one ScrapedEvent per screening.

    `details` maps detail-page URL (no fragment) → HTML, used only to find a
    stated price override; pure function, no network."""
    details = details or {}
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".col-content") or soup
    house_price = default_price(html)
    page_my = _page_month_year(page_url)

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for hr in content.find_all("hr"):
        elements = [e for e in _section(hr) if isinstance(e, Tag)]
        if not elements:
            continue
        header_lines = _lines(elements[0])
        if not header_lines:
            continue
        line = header_lines[0]
        m = _HEADER_MONTH.search(line)
        days = [int(d) for d in re.findall(r"\b(\d{1,2})\b", line[: m.start()])] if m else []
        if not days:
            continue  # not a screening section
        month = _MONTHS[m.group(1).lower()]
        tail = _HEADER_TAIL.match(line[m.end():])
        if tail.group(1):
            year = int(tail.group(1))
        elif page_my:
            year = page_my[1]
            if month < page_my[0] - 6:  # e.g. "januari" on a december page
                year += 1
        else:
            continue
        start_time = None
        if tail.group(2):
            hh, mm = int(tail.group(2)), int(tail.group(3))
            if 0 <= hh < 24 and 0 <= mm < 60:
                start_time = dt.time(hh, mm)

        h2 = next((e for e in elements if e.name == "h2"), None)
        title = _clean(h2.get_text(" ")) if h2 else ""
        if not title:
            continue

        annotations: list[str] = []
        kind = next((ln for ln in header_lines[1:] if ln.isupper()), None)
        if kind:
            annotations.append(kind.title())
        for e in elements:
            if e is h2:
                break
            if e.name == "h3":
                kicker = _clean(e.get_text(" "))
                if kicker:
                    annotations.append(kicker)

        credits = None
        after_h2 = elements[elements.index(h2) + 1:]
        for e in after_h2:
            if e.name == "p" and "|" in e.get_text():
                credits = _clean(e.get_text(" "))
                break

        img = next((i for e in elements for i in e.select("img[src]")), None)
        image_url = urljoin(BASE_URL, img["src"]) if img else None

        more = _more_link(elements)
        source_url = more or f"{page_url.split('#')[0]}#{hr.get('id') or ''}".rstrip("#")

        price = _stated_price(elements[1:])
        if price is None and more:
            base, frag = urldefrag(more)
            if base in details:
                price = detail_price(details[base], frag)
        if price is None:
            price = house_price

        key = hr.get("id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        for day in days:
            try:
                start_date = dt.date(year, month, day)
            except ValueError:
                continue
            time_part = start_time.strftime("%H%M") if start_time else "0000"
            external_id = f"{key}@{start_date.isoformat()}T{time_part}"
            if external_id in seen:
                continue
            seen.add(external_id)
            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=["film"],
                    price=price,
                    language=_language(credits),
                    image_url=image_url,
                    external_id=external_id,
                    annotations=list(annotations),
                )
            )
    return events


class FilmhuisCaviaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; cartelera)"}
        events: list[ScrapedEvent] = []
        with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as client:
            home = client.get(HOME_URL)
            home.raise_for_status()
            for url in month_urls(home.text):
                resp = client.get(url)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                details: dict[str, str] = {}
                for durl in detail_urls(resp.text):
                    d = client.get(durl)
                    if d.status_code == 200:
                        details[durl] = d.text
                events.extend(parse_month(resp.text, url, details))
        # Guard against a screening repeated on two month pages.
        unique: dict[str, ScrapedEvent] = {}
        for ev in events:
            unique.setdefault(ev.external_id, ev)
        return list(unique.values())


register(
    scraper=FilmhuisCaviaScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Filmhuis Cavia",
        city_slug="amsterdam",
        address="Van Hallstraat 52-1, 1051 HH Amsterdam",
        site_url=HOME_URL,
        instagram_url="https://www.instagram.com/filmhuiscavia",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film", whitelist_category_slug="film"),
        ],
    ),
)
