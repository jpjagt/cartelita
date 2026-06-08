from __future__ import annotations
import datetime as dt
import html as html_module
import re
from typing import Callable

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Cinemes Girona's cartelera server-renders the whole upcoming programme as
# `article.article-cartelera` cards (one per film). Each card carries the film's
# title/synopsis/poster/genres plus its showtimes, grouped by day in desktop tab
# panes (`.tabs-performances .tab-pane`, id = `<filmid>-<YYYYMMDD>`). We emit one
# ScrapedEvent per (film, date, time) occurrence. See cinemes_girona_SOURCE.md.
#
# The host returns 403 to a default httpx UA, so we send a desktop browser UA.
AGENDA_URL = "https://www.cinemesgirona.cat/es/cartelera"
BASE_URL = "https://www.cinemesgirona.cat"
VENUE_SLUG = "cinemes-girona"

# The cartelera carries no per-screening price. The venue's public (non-member)
# web ticket is 7€ on weekdays and 9€ on weekends/festives (día-del-espectador 5€
# and member/senior/youth tiers omitted per the price convention). The spread is
# minor (high < 2× low), so per the price convention we never show a range — but
# we DO know each occurrence's date, so we pick the single applicable tier per
# event: 7€ on weekdays, 9€ on weekends. (We have no festive calendar, so holidays
# falling on a weekday are priced at the weekday rate.)
WEEKDAY_PRICE = "7€"
WEEKEND_PRICE = "9€"


def _price_for_date(date: dt.date) -> str:
    # weekday() is 0=Mon … 5=Sat, 6=Sun.
    return WEEKEND_PRICE if date.weekday() >= 5 else WEEKDAY_PRICE

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Tab-pane id: "<filmid>-<YYYYMMDD>". Showtime anchor title: "YYYYMMDD HH:MM".
_PANE_ID = re.compile(r"^(?P<filmid>\d+)-(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})$")
_TIME = re.compile(r"(\d{1,2}):(\d{2})")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _article_title_and_url(article: Tag) -> tuple[str | None, str | None]:
    link = article.select_one("h2 a[href]")
    if not link:
        return None, None
    title = _clean(link.get_text(strip=True))
    href = link.get("href", "").split("?")[0].rstrip("/")
    return (title or None), (_absolutize(href) if href else None)


def _article_description(article: Tag) -> str | None:
    p = article.select_one(".col-md-8 > p")
    if not p:
        return None
    text = _clean(p.get_text(" ", strip=True))
    return text or None


def _article_image(article: Tag) -> str | None:
    img = article.select_one("figure img.d-md-block[src]") or article.select_one(
        "figure img[src]"
    )
    src = img.get("src", "") if img else ""
    return _absolutize(src) if src else None


def _article_genres(article: Tag) -> list[str]:
    genres: list[str] = []
    for a in article.select('table a[href*="/cartelera/"]'):
        g = _clean(a.get_text(strip=True))
        if g and g not in genres:
            genres.append(g)
    return genres


def _parse_pane_id(pane_id: str) -> tuple[str, dt.date] | None:
    m = _PANE_ID.match(pane_id.strip())
    if not m:
        return None
    try:
        date = dt.date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    except ValueError:
        return None
    return m.group("filmid"), date


def _parse_time(text: str) -> dt.time | None:
    m = _TIME.search(text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None


def parse_agenda(
    html: str,
    price_for_date: Callable[[dt.date], str | None] = _price_for_date,
) -> list[ScrapedEvent]:
    """Parse the Cinemes Girona cartelera into one ScrapedEvent per occurrence.

    One occurrence = one (film, date, showtime). Film fields come from the
    `article.article-cartelera` card; the date from each desktop tab-pane id
    (`<filmid>-<YYYYMMDD>`) and the time from each showtime anchor's
    `title="YYYYMMDD HH:MM"`. The version label (DIG/VOSE/CATALÀ/…) and the genre
    tags become free-form annotations. Every event is category `film`.

    `price_for_date` maps an occurrence's date to its display price (weekday vs.
    weekend tier by default); pass `lambda _: None` to clear prices."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for article in soup.select("article.article-cartelera"):
        title, source_url = _article_title_and_url(article)
        if not title or not source_url:
            continue
        film_slug = source_url.rstrip("/").rsplit("/", 1)[-1]
        description = _article_description(article)
        image_url = _article_image(article)
        genres = _article_genres(article)

        # Desktop tab panes carry the day-by-day showtimes. (A mobile `.horarios`
        # mirror has the same data; we read only `.tabs-performances` to avoid
        # double-counting.)
        for pane in article.select(".tabs-performances .tab-pane"):
            parsed = _parse_pane_id(pane.get("id", ""))
            if not parsed:
                continue
            filmid, start_date = parsed

            for row in pane.select(".row.pelicula"):
                version = row.select_one("span")
                version_label = _clean(version.get_text(strip=True)) if version else None
                annotations = list(genres)
                if version_label and version_label not in annotations:
                    annotations.append(version_label)

                for slot in row.select("a[title]"):
                    start_time = _parse_time(slot.get("title", "")) or _parse_time(
                        slot.get_text(strip=True)
                    )
                    if start_time is None:
                        continue

                    # external_id must be unique per OCCURRENCE: the film id is
                    # shared across every screening, and the upsert dedups on
                    # (venue, external_id), so qualify it with date+time. The same
                    # (film, date, time) can appear in two version rows (e.g. a
                    # VOSE and a CAT pass at the same hour is rare but a film with
                    # one version row is the norm) — dedup defensively.
                    external_id = (
                        f"{filmid}@{start_date.isoformat()}T{start_time.strftime('%H%M')}"
                    )
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
                            price=price_for_date(start_date),
                            description=description,
                            image_url=image_url,
                            external_id=external_id,
                            annotations=annotations,
                        )
                    )

    return events


class CinemesGironaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "es-ES,es;q=0.9"},
        ) as client:
            html = client.get(AGENDA_URL).text
        return parse_agenda(html)


register(
    scraper=CinemesGironaScraper(),
    venue=VenueDefinition(
        slug="cinemes-girona",
        name="Cinemes Girona",
        city_slug="barcelona",
        address="Carrer de Girona, 175, L'Eixample, 08037 Barcelona",
        site_url="https://www.cinemesgirona.cat",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
