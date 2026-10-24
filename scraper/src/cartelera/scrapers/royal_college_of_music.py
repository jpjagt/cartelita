"""Royal College of Music (South Kensington) — conservatoire concerts and
opera, many of them pay-what-you-can.

Spektrix client `royalcollegeofmusic` on tickets.rcm.ac.uk, via the shared
`_spektrix` helper (see royal_college_of_music_SOURCE.md). Curation on the
box office's own `Category`: Concert and Opera → classical. Masterclasses
(the label also covers participatory workshops), Junior Department, museum
events and tours, talks, participatory courses and external hires are
dropped.

Beyond the category:

- the building: a performance counts only when its seating plan's venue is
  at the College (address SW7 2BS — every hall and room); the client's other
  venue ("Imperial College") is dropped;
- each performance has its own page on rcm.ac.uk,
  `/events/details/?id=<webInstanceId>` (the what's-on page links them),
  and pay-what-you-can events (the box office's `AccountCode` says
  "PWYC"; the website says "Pay What You Can") get that as their price
  instead of the £5 suggested ticket (both set per performance by the
  helper's `finish` hook).
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "royal-college-of-music"
CLIENT = spk.Client("royalcollegeofmusic", "https://tickets.rcm.ac.uk")
CATEGORIES = {"Concert", "Opera"}
# Every RCM hall/room in the client's /venues shares the College's postcode.
POSTCODE = "SW7 2BS"
PAGE_URL = "https://www.rcm.ac.uk/events/details/?id={}"
PWYC_PRICE = "pay what you can"


def categorize(event: dict) -> list[str]:
    return ["classical"] if spk.attr(event, "Category") in CATEGORIES else []


def venue(event: dict, instance: dict) -> str | None:
    address = (instance.get("venue") or {}).get("address") or ""
    return VENUE_SLUG if POSTCODE in address else None


def is_pwyc(event: dict) -> bool:
    return "PWYC" in spk.attr(event, "AccountCode")


def finish(scraped: ScrapedEvent, event: dict, instance: dict) -> None:
    """The performance's own rcm.ac.uk page and the pay-what-you-can price."""
    if instance.get("webInstanceId"):
        scraped.source_url = PAGE_URL.format(instance["webInstanceId"])
    if is_pwyc(event):
        scraped.price = PWYC_PRICE


class RoyalCollegeOfMusicScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, venue=venue, plan_venues=True, finish=finish)


register(
    scraper=RoyalCollegeOfMusicScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Royal College of Music",
        city_slug="london",
        address="Prince Consort Road, London SW7 2BS",
        site_url="https://www.rcm.ac.uk",
        instagram_url="https://www.instagram.com/royalcollegeofmusic",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical")],
    ),
)
