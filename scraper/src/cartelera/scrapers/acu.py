from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers._eur import HEADERS, eur_amounts
from cartelera.scrapers.http import fetch
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# ACU (Voorstraat 71, Utrecht) — political-cultural centre in a former squat:
# punk/hardcore/noise gigs, dance nights, experimental electronics, films.
# WordPress, server-rendered. `/agenda` lists every upcoming event as
# `li.AgendaEntry` whose CLASS LIST carries the venue's own filter labels
# ("bands", "dance-nights", "movies", "food", "quiz", …; same labels as the
# page's `#filter=.xxx` buttons), with date spans (year in a hidden span), the
# title/subtitle, and Door/Start/Entry details. See acu_SOURCE.md.
BASE_URL = "https://acu.nl"
AGENDA_URL = f"{BASE_URL}/agenda"
VENUE_SLUG = "acu"

# Venue filter label → our category. An entry is programme iff it carries at
# least one of these; entries with only community/side labels (daytime coffee,
# D&D, food/Barricade, info-talks, quiz, karaoke, workshops, tables, jam
# sessions, open stage & poetry, theater/drag, art, "timetravelers") are left
# out. Unlabelled entries (freshly added, not yet tagged) are treated as the
# house default: alternative.
LABEL_CATEGORIES = {
    "bands": "alternative",
    "loud": "alternative",
    "noise": "alternative",
    "folkpunk": "alternative",
    "table-gazing": "alternative",  # experimental electronics / noise
    "dance-nights": "club",
    "electronic": "club",
    "movies": "film",
}
# Participatory formats: even when also labelled "bands", an entry with one of
# these labels is an open jam/stage, not a programmed show.
PARTICIPATORY = {"jam-sessions", "open-stage-and-poetry", "workshops", "quiz"}
_STRUCTURAL = {"AgendaEntry", "recurrent", "weekly"}
_MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], start=1)
}
_URL_DATE = re.compile(r"/events/(\d{4})(\d{2})(\d{2})/")
_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
# Joke/placeholder entries dated decades ahead ("The meeting that never
# happened", 2040/2057) — anything this far out is not a real listing.
_MAX_AHEAD = dt.timedelta(days=2 * 366)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def categorize(labels: list[str]) -> list[str] | None:
    """Our categories from the venue labels; None = not programme."""
    known = [lbl for lbl in labels if lbl not in _STRUCTURAL]
    if set(known) & PARTICIPATORY:
        return None
    cats: list[str] = []
    for lbl in known:
        cat = LABEL_CATEGORIES.get(lbl)
        if cat and cat not in cats:
            cats.append(cat)
    if cats:
        return cats
    return ["alternative"] if not known else None


def format_price(text: str) -> str | None:
    """"€ 8/12" → "12€" (minor spread), "€ 5/15" → "5–15€", "It’s Free!" →
    "free", "Donation based" → "donation"."""
    low = text.lower()
    if "free" in low or "gratis" in low:
        return "free"
    if "donation" in low or "donatie" in low:
        return "donation"
    if "sold out" in low or "uitverkocht" in low:
        return "sold-out"
    nums = [float(n) for n in re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", "."))]
    if not nums and eur_amounts(text):
        nums = eur_amounts(text)
    if not nums:
        return None
    lo, hi = min(nums), max(nums)
    if lo == int(lo) and hi == int(hi):
        return format_eur_range(int(lo), int(hi))
    return f"{hi:.2f}".replace(".", ",") + "€"


def _date(entry, url: str) -> dt.date | None:
    m = _URL_DATE.search(url)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    month = entry.select_one(".AgendaMonth")
    day = entry.select_one(".AgendaDay")
    year = entry.select_one(".AgendaYear")
    if not (month and day and year):
        return None
    try:
        return dt.date(
            int(_clean(year.get_text())),
            _MONTHS[_clean(month.get_text()).lower()],
            int(re.sub(r"\D", "", day.get_text())),
        )
    except (KeyError, ValueError):
        return None


def parse_agenda(html: str, today: dt.date) -> list[ScrapedEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for entry in soup.select("li.AgendaEntry"):
        a = entry.find("a", href=True)
        if a is None:
            continue
        url = a["href"]
        external_id = url.rstrip("/").split("/events/", 1)[-1]
        if external_id in seen:
            continue
        labels = [c for c in entry.get("class") or []]
        categories = categorize(labels)
        if categories is None:
            continue
        date = _date(entry, url)
        if date is None or date > today + _MAX_AHEAD:
            continue
        title_el = entry.select_one(".pseudo-h2")
        title = _clean(title_el.get_text(" ")) if title_el else ""
        if not title:
            continue
        details: dict[str, str] = {}
        price_text = None
        for li in entry.select("ul.AgendaDetails li"):
            spans = li.find_all("span")
            if any("EntranceFee" in (s.get("class") or []) for s in spans):
                price_text = _clean(spans[-1].get_text(" "))
            elif len(spans) == 2:
                details[_clean(spans[0].get_text()).rstrip(":").lower()] = _clean(spans[1].get_text())
        start_time = None
        for key in ("start", "door"):
            m = _TIME.search(details.get(key, ""))
            if m and int(m.group(1)) < 24:
                start_time = dt.time(int(m.group(1)), int(m.group(2)))
                break
        # The site sometimes holds two posts for one occurrence (same title,
        # date and time under "-23"/"-24" slugs): keep the first.
        occurrence = f"{title.lower()}@{date.isoformat()}T{start_time}"
        if occurrence in seen:
            continue
        seen.add(occurrence)
        subtitle = entry.select_one(".pseudo-h3")
        seen.add(external_id)
        events.append(
            ScrapedEvent(
                title=title,
                start_date=date,
                start_time=start_time,
                source_url=url,
                category_slugs=categories,
                price=format_price(price_text) if price_text else None,
                description=_clean(subtitle.get_text(" ")) if subtitle else None,
                external_id=external_id,
                annotations=[c for c in labels if c not in _STRUCTURAL],
            )
        )
    return events


class AcuScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_agenda(fetch(AGENDA_URL, headers=HEADERS), dt.date.today())


register(
    scraper=AcuScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="ACU",
        city_slug="utrecht",
        address="Voorstraat 71, 3512 AK Utrecht",
        site_url=BASE_URL,
        instagram_url="https://www.instagram.com/acu.nl",
        category_slugs=["alternative", "club", "film"],
        list_memberships=[
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
            ListMembership(list_slug="film", whitelist_category_slug="film"),
        ],
    ),
)
