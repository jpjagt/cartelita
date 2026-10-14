"""LantarenVenster (Rotterdam, Kop van Zuid) — arthouse cinema + jazz/music venue.

WordPress with the "Theater for WP" plugin. The homepage carries the full
agenda (`.wpt_context_agenda .wp_theatre_event`): one element per screening /
concert whose CSS classes hold the date (`2026-10-14`), the group
(`film-groep` / `muziek-groep`) and series flags (`premierefilm`,
`familiefilm`, `filmspecial`, `muziek`, `global`, `special`, `english`…), and
whose `.wpt_production_dates_summary_times li` lists all of that production's
times that day. One ScrapedEvent per production per day (all times in
`start_times`). Price/language from the production's detail page; the house
film price from /kaartverkoop/. See lantarenvenster_SOURCE.md.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.browser import BROWSER_HELPER_UA
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

BASE_URL = "https://www.lantarenvenster.nl"
PRICES_URL = BASE_URL + "/kaartverkoop/"
VENUE_SLUG = "lantarenvenster"

_DATE_CLASS = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_EUR = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)")
# Venue flags for non-programme items (see SOURCE.md): yoga, quizzes and
# open-screen evenings ("special"), a salsa dance night ("dans"), book launches.
_EXCLUDE_FLAGS = {"special", "dans", "boekpresentatie"}
# Flags kept as annotations (display labels for the venue's series).
_FLAG_LABELS = {
    "premierefilm": "Première", "filmspecial": "Filmspecial", "familiefilm": "Familiefilm",
    "muziekspecial": "Muziekspecial", "english": "English friendly", "global": "Global",
}


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def _fmt_amount(raw: str) -> str:
    v = float(raw.replace(",", "."))
    return f"{int(v)}€" if v == int(v) else f"{v:.2f}€".replace(".", ",")


def house_film_price(html: str) -> str | None:
    """The regular film ticket ("Entreeprijzen film € 13,00 …") from /kaartverkoop/."""
    text = _text(BeautifulSoup(html, "html.parser"))
    m = re.search(r"Entreeprijzen film\s*€\s*(\d+(?:[.,]\d{1,2})?)", text)
    return _fmt_amount(m.group(1)) if m else None


def categories_for(classes: list[str]) -> list[str]:
    """[] = leave out. Film group wins (film concerts are films with live music)."""
    if _EXCLUDE_FLAGS & set(classes):
        return []
    if "film-groep" in classes:
        return ["kids"] if "familiefilm" in classes else ["film"]
    if "muziek-groep" in classes:
        return ["folk"] if "global" in classes else ["jazz"]
    return []


def parse_agenda(html: str, today: dt.date | None = None) -> list[dict]:
    """The homepage agenda -> one dict per (production, day). Pure.

    Keys: url, slug, title, subtitle, date, times, classes, image_url,
    excerpt, soldout, free."""
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    agenda = soup.select_one(".wpt_context_agenda") or soup
    out: dict[tuple[str, str], dict] = {}
    for ev in agenda.select(".wp_theatre_event"):
        classes = ev.get("class", [])
        date_cls = next((c for c in classes if _DATE_CLASS.match(c)), None)
        link = ev.select_one("a[href]")
        if not date_cls or not link:
            continue
        date = dt.date.fromisoformat(date_cls)
        if date < today:
            continue
        url = link["href"]
        key = (url, date_cls)
        times = sorted({
            dt.time(int(m.group(1)), int(m.group(2)))
            for li in ev.select(".wpt_production_dates_summary_times li")
            for m in [_TIME.search(_text(li))] if m and int(m.group(1)) < 24
        })
        if not times:
            continue  # "Verwacht vanaf do 22 okt": announced, no screenings yet
        status = ev.select_one(".wp_theatre_event_tickets_status")
        status_cls = status.get("class", []) if status else []
        item = out.get(key)
        if item:
            item["times"] = sorted(set(item["times"]) | set(times))
            item["soldout"] = item["soldout"] and "wp_theatre_event_tickets_status_soldout" in status_cls
            continue
        img = ev.select_one("img[src]")
        out[key] = {
            "url": url,
            "slug": urlparse(url).path.rstrip("/").rsplit("/", 1)[-1],
            "title": _text(ev.select_one(".wp_theatre_event_title")),
            "subtitle": _text(ev.select_one(".wp_theatre_event_subtitle")) or None,
            "date": date,
            "times": times,
            "classes": classes,
            "image_url": img["src"] if img else None,
            "excerpt": _text(ev.select_one(".wp_theatre_prod_excerpt")) or None,
            "serie": _text(ev.select_one(".wp_theatre_prod_serie")) or None,
            "soldout": "wp_theatre_event_tickets_status_soldout" in status_cls,
            "free": "gratis" in _text(status).lower(),
        }
    return list(out.values())


def parse_detail(html: str) -> dict:
    """Price text and languages from a production page."""
    soup = BeautifulSoup(html, "html.parser")
    details = soup.select_one(".wpt_context_details") or soup
    price_text = _text(details.select_one(".wp_theatre_prod_prices"))
    spoken = _text(details.select_one(".wp_theatre_prod_languages_spoken"))
    subs = _text(details.select_one(".wp_theatre_prod_languages_subtitles"))
    return {"price_text": price_text, "spoken": spoken, "subtitles": subs}


def detail_price(price_text: str, *, film: bool, house: str | None) -> str | None:
    """"€ 21 incl. € 3,00 servicekosten" -> "21€"; film "vanaf € 10" (the
    lowest tier) -> the house film price."""
    low = price_text.lower()
    if not low:
        return house if film else None
    if "gratis" in low or "vrij entree" in low:
        return "free"
    if "uitverkocht" in low:
        return "sold-out"
    if low.startswith("vanaf"):
        return house if film else None
    # Drop the service-cost aside, keep the main amount(s).
    main = re.split(r"incl", price_text, flags=re.I)[0]
    amounts = _EUR.findall(main)
    if not amounts:
        return house if film else None
    best = max(amounts, key=lambda a: float(a.replace(",", ".")))
    return "free" if float(best.replace(",", ".")) == 0 else _fmt_amount(best)


def _language(spoken: str, subs: str) -> str | None:
    spoken = re.sub(r"\s*gesproken$", "", spoken, flags=re.I).strip()
    subs = re.sub(r"\s*ondertiteld$", "", subs, flags=re.I).strip()
    if spoken and subs:
        return f"{spoken} ({subs} ondertiteld)"
    return spoken or (f"{subs} ondertiteld" if subs else None)


def build_events(
    items: list[dict], details: dict[str, dict], house: str | None
) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    for it in items:
        cats = categories_for(it["classes"])
        if not cats or not it["title"]:
            continue
        film = "film-groep" in it["classes"]
        d = details.get(it["url"], {})
        if it["soldout"]:
            price = "sold-out"
        elif it["free"]:
            price = "free"
        else:
            price = detail_price(d.get("price_text", ""), film=film, house=house)
        times = it["times"]
        title = it["title"]
        if it["subtitle"] and not film:
            title = f"{title} — {it['subtitle']}"
        events.append(ScrapedEvent(
            title=title,
            start_date=it["date"],
            start_time=times[0] if times else None,
            start_times=times,
            source_url=it["url"],
            category_slugs=cats,
            price=price,
            description=it["excerpt"],
            image_url=it["image_url"],
            external_id=f"{it['slug']}@{it['date'].isoformat()}",
            language=_language(d.get("spoken", ""), d.get("subtitles", "")) if film else None,
            annotations=[label for c, label in _FLAG_LABELS.items() if c in it["classes"]]
            + ([it["serie"]] if it.get("serie") else []),
        ))
    return events


class LantarenVensterScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": BROWSER_HELPER_UA}
        with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as c:
            home = c.get(BASE_URL + "/")
            home.raise_for_status()
            items = parse_agenda(home.text)
            prices = c.get(PRICES_URL)
            house = house_film_price(prices.text) if prices.status_code == 200 else None
            details: dict[str, dict] = {}
            for url in dict.fromkeys(it["url"] for it in items if categories_for(it["classes"])):
                r = c.get(url)
                if r.status_code == 200:
                    details[url] = parse_detail(r.text)
        return build_events(items, details, house)


register(
    scraper=LantarenVensterScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="LantarenVenster",
        city_slug="rotterdam",
        address="Otto Reuchlinweg 996, 3072 MD Rotterdam",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/lantarenvenster",
        category_slugs=["film", "jazz", "kids", "folk"],
        list_memberships=[
            ListMembership(list_slug=c, whitelist_category_slug=c)
            for c in ("film", "jazz", "kids", "folk")
        ],
    ),
)
