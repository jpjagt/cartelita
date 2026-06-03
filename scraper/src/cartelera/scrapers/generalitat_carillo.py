from __future__ import annotations
import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Carilló del Palau de la Generalitat — free public carillon (bell) concerts at
# the Palau de la Generalitat in the Barri Gòtic, Barcelona. The page is plain
# server-rendered HTML (Adobe AEM): NO event JSON-LD and no JSON blob. The page
# describes a recurring cadence in prose ("un concert cada primer diumenge de
# mes, a les 12h, excepte agost i setembre"; July festival; Mercè + Sant Esteve)
# but also lists the concrete upcoming dates discretely in two content blocks,
# which is what we parse — we do NOT synthesise the recurrence and do NOT chase
# the full-season PDF. Every concert is `classical` and free.
LIST_URL = "https://presidencia.gencat.cat/ca/carillo"
VENUE_SLUG = "generalitat-carillo"

# Catalan month names -> month number.
_MONTHS = {
    "gener": 1, "febrer": 2, "març": 3, "marc": 3, "abril": 4, "maig": 5,
    "juny": 6, "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10,
    "novembre": 11, "desembre": 12,
}
_MONTH_RE = re.compile("|".join(_MONTHS), re.IGNORECASE)
# A day-of-month header like "Divendres 17 de juliol" or "diumenge 7".
_DAY_NUM = re.compile(r"\b(\d{1,2})\b")
# A clock time like "12h", "12 h", "21:00 h", "a les 12 del migdia".
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*h\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(20\d{2})\b")

_DEFAULT_MONTHLY_TIME = dt.time(12, 0)  # the venue's standard midday slot


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_time(text: str, default: dt.time | None = None) -> dt.time | None:
    m = _TIME.search(text)
    if not m:
        return default
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    if hour > 23 or minute > 59:
        return default
    return dt.time(hour, minute)


def _infer_year(month: int, today: dt.date) -> int:
    """The page lists upcoming concerts without a year. Pick the next occurrence
    of `month` on/after today (so a Dec list shown in Dec rolls forward, and a
    Jan list shown in Dec rolls to next year)."""
    if month >= today.month:
        return today.year
    return today.year + 1


def _section_for(soup: BeautifulSoup, predicate) -> Tag | None:
    """Return the `.highlighted-content` (or nearest container) whose
    `h2.section-heading__title` satisfies `predicate(text)`."""
    for h2 in soup.select("h2.section-heading__title"):
        if predicate(h2.get_text(strip=True)):
            node: Tag | None = h2
            for _ in range(5):
                if node is None:
                    break
                node = node.parent
                if node is not None and "highlighted-content" in (node.get("class") or []):
                    return node
            return h2.parent
    return None


def _parse_temporada(soup: BeautifulSoup, today: dt.date) -> list[ScrapedEvent]:
    """Parse the 'Temporada 20xx-20xx' block's 'Pròxims concerts' <ul><li> list.
    Each <li> = one monthly concert: month (bold), day (bold), time, blurb, and
    a programme link."""
    sec = _section_for(soup, lambda t: t.lower().startswith("temporada"))
    if sec is None:
        return []
    season = ""
    h2 = sec.select_one("h2.section-heading__title") or sec.find_previous("h2")
    if h2:
        season = _norm(h2.get_text(strip=True))

    events: list[ScrapedEvent] = []
    for li in sec.select("ul li"):
        bolds = li.find_all("b")
        if len(bolds) < 2:
            continue
        month_text = bolds[0].get_text(strip=True)
        mm = _MONTH_RE.search(month_text)
        if not mm:
            continue
        month = _MONTHS[mm.group(0).lower()]
        day_m = _DAY_NUM.search(bolds[1].get_text(strip=True))
        if not day_m:
            continue
        day = int(day_m.group(1))
        year = _infer_year(month, today)
        try:
            date = dt.date(year, month, day)
        except ValueError:
            continue

        full = _norm(li.get_text(" ", strip=True))
        start_time = _parse_time(full, default=_DEFAULT_MONTHLY_TIME)

        link = li.select_one("a")
        programme = _norm(link.get_text(" ", strip=True)).strip(" .") if link else None
        programme = programme or None

        # Description: the <li> text after the day, sans the bold labels.
        desc = full
        title = "Concert de Carilló del Palau"
        if programme:
            title = f"{title}: {programme}"

        annotations: list[str] = []
        if season:
            annotations.append(season)
        if programme:
            annotations.append(programme)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=date,
                start_time=start_time,
                source_url=LIST_URL,
                category_slugs=["classical"],
                price="free",
                description=desc or None,
                external_id=f"{VENUE_SLUG}-{date.isoformat()}",
                annotations=annotations,
            )
        )
    return events


def _parse_festival(soup: BeautifulSoup) -> list[ScrapedEvent]:
    """Parse the 'Festival Internacional de Carilló' block. The 'Dates:' line
    carries the year; the 'Hora:' line the time (21:00); the 'Programa' <p> has
    one <b> day header per concert (e.g. 'Divendres 17 de juliol') followed by an
    <i> programme title and the carillonist sentence."""
    sec = _section_for(soup, lambda t: "festival internacional de caril" in t.lower())
    if sec is None:
        return []
    edition = ""
    h2 = sec.select_one("h2.section-heading__title")
    if h2:
        edition = _norm(h2.get_text(strip=True))

    block_text = sec.get_text(" ", strip=True)
    ym = _YEAR.search(block_text)
    if not ym:
        return []
    year = int(ym.group(1))

    # Time from the "Hora:" list item, default 21:00.
    start_time = dt.time(21, 0)
    for li in sec.select("ul li"):
        t = li.get_text(" ", strip=True)
        if t.lower().startswith("hora"):
            start_time = _parse_time(t, default=start_time)
            break

    # The programme <p>: a single <p> with multiple <b> day headers separated by
    # <br>. Walk its children, attributing each <b> header to the text that
    # follows it (until the next <b>).
    prog_p = None
    found_label = False
    for el in sec.find_all(["p"]):
        txt = el.get_text(" ", strip=True)
        if found_label and el.find("b"):
            prog_p = el
            break
        if txt.lower() == "programa":
            found_label = True
    if prog_p is None:
        # Fallback: the first <p> that has both a <b> day and an <i> title.
        for el in sec.find_all("p"):
            if el.find("b") and el.find("i"):
                prog_p = el
                break
    if prog_p is None:
        return []

    events: list[ScrapedEvent] = []
    # Build (day-header-text, following-text) segments from the <p>'s children.
    segments: list[tuple[str, str]] = []
    cur_header: str | None = None
    cur_rest: list[str] = []
    for child in prog_p.children:
        if isinstance(child, Tag) and child.name == "b":
            if cur_header is not None:
                segments.append((cur_header, _norm(" ".join(cur_rest))))
            cur_header = _norm(child.get_text(" ", strip=True))
            cur_rest = []
        else:
            text = child.get_text(" ", strip=True) if isinstance(child, Tag) else str(child).strip()
            if text:
                cur_rest.append(text)
    if cur_header is not None:
        segments.append((cur_header, _norm(" ".join(cur_rest))))

    for header, rest in segments:
        day_m = _DAY_NUM.search(header)
        mm = _MONTH_RE.search(header)
        if not day_m or not mm:
            continue
        day = int(day_m.group(1))
        month = _MONTHS[mm.group(0).lower()]
        try:
            date = dt.date(year, month, day)
        except ValueError:
            continue

        # The programme title is the leading italic phrase; the rest names the
        # carillonist. rest looks like ". <title> , amb <carillonist>." — split
        # on the first comma after the title.
        programme = None
        carillonist = None
        cleaned = rest.lstrip(". ").strip()
        if cleaned:
            parts = cleaned.split(", amb ", 1)
            programme = _norm(parts[0].strip(" .,"))
            if len(parts) == 2:
                carillonist = _norm(parts[1].strip(" .,"))

        title = "Festival Internacional de Carilló de Barcelona"
        if programme:
            title = f"{title}: {programme}"

        annotations: list[str] = []
        if edition:
            annotations.append(edition)
        if carillonist:
            annotations.append(carillonist)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=date,
                start_time=start_time,
                source_url=LIST_URL,
                category_slugs=["classical"],
                price="free",
                description=cleaned or None,
                external_id=f"{VENUE_SLUG}-festival-{date.isoformat()}",
                annotations=annotations,
            )
        )
    return events


def parse_agenda(html: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    """Parse the Carilló del Palau page into ScrapedEvents. Two discrete dated
    listings are read: the 'Temporada' block's upcoming monthly concerts and the
    'Festival Internacional' programme. Every concert is `classical` and free.
    The page's prose recurrence (first Sunday of each month) is NOT synthesised."""
    if today is None:
        today = dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    events = _parse_temporada(soup, today)
    events += _parse_festival(soup)
    # De-dup defensively on external_id (the two blocks shouldn't overlap).
    seen: set[str] = set()
    out: list[ScrapedEvent] = []
    for ev in events:
        key = ev.external_id or f"{ev.title}@{ev.start_date}"
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


class GeneralitatCarilloScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(
            LIST_URL,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (cartelera scraper)"},
        ).text
        return parse_agenda(html)


register(
    scraper=GeneralitatCarilloScraper(),
    venue=VenueDefinition(
        slug="generalitat-carillo",
        name="Carilló del Palau de la Generalitat",
        city_slug="barcelona",
        address="Plaça de Sant Jaume, s/n, 08002 Barcelona",
        site_url="https://presidencia.gencat.cat/ca/carillo",
        category_slugs=["classical"],
        list_memberships=[
            ListMembership(list_slug="classical"),
        ],
    ),
)
