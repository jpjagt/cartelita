from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import re
import unicodedata

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers import rotown
from cartelera.scrapers._nl_common import DUTCH_MONTHS, first_time, get, infer_year
from cartelera.scrapers.price import eur_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Maassilo (Maashaven, Rotterdam-Zuid) — former grain silo; big dance events
# and concerts. Two upstream pages feed this ONE source (see
# maassilo_SOURCE.md):
#
# 1. Maassilo's own WordPress agenda — `/agenda/` cards ("24 okt", no year;
#    title; link), each production page's "Info evenement" block ("Tijd: 13:00
#    - 22:00", "Prijs: vanaf 20,-", "Locatie: Maassilo | Now&Wow"), and the
#    REST API's `class_list` (`genre-*`, `location-*`) for Maassilo's own
#    genre taxonomy. Category from that genre: concert / rock / hiphop → pop;
#    the dance genres (techno, house, hardstyle, hard techno, drum & bass,
#    afro beat) → club.
# 2. The concerts Rotown programmes in the Maassilo (Chef'Special, Tramhaus,
#    Psychedelic Porn Crumpets …) are NOT on Maassilo's own agenda; Rotown's
#    homepage JSON-LD lists them with `location.name == "Maassilo"`. We take
#    those too (pop, Rotown's price/time) — the Rotown source drops them, so
#    each show still has exactly one owner.
AGENDA_URL = "https://maassilo.com/agenda/"
API_URL = "https://maassilo.com/wp-json/wp/v2/agenda?per_page=100&_fields=link,class_list"
VENUE_SLUG = "maassilo"
VENUE_NAME = "Maassilo"

GENRE_CATEGORY = {
    "concert": "pop", "rock": "pop", "hiphop": "pop",
    "techno": "club", "house": "club", "hardstyle": "club", "hard-techno": "club",
    "drum-base": "club", "afro-beat": "club",
}
GENRE_LABEL = {
    "concert": "Concert", "rock": "Rock", "hiphop": "Hiphop", "techno": "Techno",
    "house": "House", "hardstyle": "Hardstyle", "hard-techno": "Hard Techno",
    "drum-base": "Drum & Bass", "afro-beat": "Afro beat",
}
LOCATION_LABEL = {"location-now-en-wow": "Now&Wow"}

logger = logging.getLogger(__name__)

_DAY_MONTH = re.compile(r"(\d{1,2})\s+([A-Za-z]+)")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _key(title: str, date: dt.date) -> str:
    norm = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return f"{date.isoformat()}|{re.sub(r'[^a-z0-9]+', '', norm)}"


def parse_agenda(html: str, today: dt.date) -> list[dict]:
    """`/agenda/` cards → [{url, title, date}] (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for card in soup.select(".x-core-card--agenda"):
        link = card.select_one("a.x-core-card--agenda__link[href]")
        pre = card.select_one(".x-core-title--pre")
        title = card.select_one(".x-core-title--title")
        if not (link and pre and title):
            continue
        m = _DAY_MONTH.search(_clean(pre.get_text(" ")))
        if not m or m.group(2).lower() not in DUTCH_MONTHS:
            continue
        date = infer_year(DUTCH_MONTHS[m.group(2).lower()], int(m.group(1)), today)
        if date is None:
            continue
        items.append({"url": link["href"], "title": _clean(title.get_text(" ")), "date": date})
    return items


def parse_detail(html: str) -> dict[str, str]:
    """A production page's "Info evenement" block → {label: value} (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    # The page has several intro blocks; the info one is "<strong>Label:
    # </strong>value<br/>…" with direct <strong> children.
    for block in soup.select(".x-core-intro__content"):
        strongs = block.find_all("strong", recursive=False)
        if any(_clean(s.get_text()).lower().startswith("tijd") for s in strongs):
            break
    else:
        return out
    for strong in strongs:
        label = _clean(strong.get_text(" ")).rstrip(":").lower()
        value = []
        for sib in strong.next_siblings:
            if getattr(sib, "name", None) in ("strong", "br"):
                break
            value.append(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
        out[label] = _clean("".join(value))
    return out


def classes_by_url(posts: list[dict]) -> dict[str, list[str]]:
    return {p["link"]: list(p.get("class_list") or []) for p in posts if p.get("link")}


def _category(classes: list[str]) -> tuple[str, list[str]]:
    genres = [c[len("genre-"):] for c in classes if c.startswith("genre-")]
    cats = [GENRE_CATEGORY[g] for g in genres if g in GENRE_CATEGORY]
    for g in genres:
        if g not in GENRE_CATEGORY:
            logger.warning("maassilo: unknown genre %r", g)
    category = "pop" if "pop" in cats else "club"
    labels = [GENRE_LABEL.get(g, g) for g in genres]
    labels += [LOCATION_LABEL[c] for c in classes if c in LOCATION_LABEL]
    return category, labels


def _price(value: str | None) -> str | None:
    if not value:
        return None
    if re.search(r"uitverkocht|sold\s*out", value, re.IGNORECASE):
        return "sold-out"
    if re.search(r"\bgratis\b|\bfree\b", value, re.IGNORECASE):
        return "free"
    return eur_price(value)


def build_events(
    agenda_html: str,
    posts: list[dict],
    details: dict[str, str],
    rotown_html: str | None,
    today: dt.date,
) -> list[ScrapedEvent]:
    """Maassilo's own agenda (+ REST genres, + production pages url → html)
    and Rotown's Maassilo shows → ScrapedEvents (pure; no network)."""
    classes = classes_by_url(posts)
    events: dict[str, ScrapedEvent] = {}
    for item in parse_agenda(agenda_html, today):
        info = parse_detail(details[item["url"]]) if item["url"] in details else {}
        category, labels = _category(classes.get(item["url"], []))
        slug = item["url"].rstrip("/").rsplit("/", 1)[-1]
        events[_key(item["title"], item["date"])] = ScrapedEvent(
            title=item["title"],
            start_date=item["date"],
            start_time=first_time(info.get("tijd")),
            source_url=item["url"],
            category_slugs=[category],
            price=_price(info.get("prijs")),
            external_id=f"{slug}@{item['date'].isoformat()}",
            annotations=labels,
        )
    if rotown_html:
        for ev in rotown.parse_home(rotown_html, venue_name=VENUE_NAME):
            key = _key(ev.title, ev.start_date)
            if key in events:
                continue  # also on Maassilo's own agenda
            events[key] = dataclasses.replace(
                ev,
                category_slugs=["pop"],
                external_id=f"rotown:{ev.external_id}",
                annotations=["Rotown presents", *ev.annotations],
            )
    return list(events.values())


class MaassiloScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        agenda = get(AGENDA_URL)
        posts = json.loads(get(API_URL))
        details = {i["url"]: get(i["url"]) for i in parse_agenda(agenda, today)}
        rotown_html = get(rotown.HOME_URL)
        return build_events(agenda, posts, details, rotown_html, today)


register(
    scraper=MaassiloScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name=VENUE_NAME,
        city_slug="rotterdam",
        address="Maashaven Zuidzijde 1-2, 3081 AE Rotterdam",
        site_url="https://maassilo.com/",
        instagram_url="https://www.instagram.com/officialmaassilo",
        category_slugs=["club", "pop"],
        list_memberships=[
            ListMembership(list_slug="club", whitelist_category_slug="club"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
        ],
    ),
)
