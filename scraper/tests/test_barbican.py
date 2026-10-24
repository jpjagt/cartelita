"""Barbican (multi-venue Spektrix source) against saved API responses — a
hand-picked subset of the 2026-10-24 programme covering every category and
every exclusion — and trimmed barbican.org.uk pages."""

import datetime as dt
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import barbican
from cartelera.types import ScrapedEvent

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def _programme():
    events = _load("barbican_spektrix_events.json")
    instances = _load("barbican_spektrix_instances.json")
    by_plan = _load("barbican_spektrix_plan_venues.json")
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    pages, titles = barbican.join_pages(_load("barbican_site_pages.json"))
    selected = spk.select(events, instances, barbican.curate(pages), barbican.venue)
    return spk.build(
        barbican.CLIENT, selected, {},
        url=lambda e: pages.get(e["id"]),
        title=lambda e: titles.get(e["id"]) or barbican._norm(e["name"]),
        venue=barbican.venue,
    )


def _raw_names(events) -> dict[str, str]:
    """Instance id (external_id) → the box-office event name, for the kept
    performances (titles may come from the site, so tests match on these)."""
    raw = {e["id"]: e["name"] for e in _load("barbican_spektrix_events.json")}
    by_inst = {i["id"]: raw[i["event"]["id"]] for i in _load("barbican_spektrix_instances.json")}
    return {e.external_id: by_inst[e.external_id] for e in events}


def test_categories_and_buildings():
    events = _programme()
    got = {(n.strip(), e.venue_slug, tuple(e.category_slugs))
           for e, n in zip(events, _raw_names(events).values())}
    expected = {
        ("London Symphony Orchestra", "barbican", ("classical",)),
        ("BBC Symphony Orchestra", "barbican", ("classical",)),
        ("Academy of Ancient Music", "milton-court", ("classical",)),
        ("Guildhall School Big Band: Harlem Renaissance", "milton-court", ("classical",)),
        ("Aris String Quartet", "lso-st-lukes", ("classical",)),
        ("Drake Artist Music Showcase 2026", "lso-st-lukes", ("classical",)),
        ("Opera Double Bill: Menotti & Bernstein", "guildhall-school-silk-street", ("classical",)),
        ("NAZA (15)", "barbican", ("film",)),
        ("Parent & Baby Screening: NAZA (15)", "barbican", ("film",)),
        ("Hamlet Hail to the Thief", "barbican", ("theater",)),
        ("A Night With Boy Blue", "barbican", ("theater",)),  # dance: filed under Theatre
        ("Tiger Country", "milton-court", ("theater",)),
        ("Jaga Jazzist", "milton-court", ("jazz",)),
        ("Billy Cobham", "barbican", ("jazz",)),
        ("Sarathy Korwar", "barbican", ("jazz",)),  # a gig in the Art Gallery
        ("Caroline", "barbican", ("pop",)),
        ("Squid", "barbican", ("alternative",)),
        ("Bess Atwell", "barbican", ("folk",)),
    }
    assert got == expected


def test_exclusions():
    kept = set(n.strip() for n in _raw_names(_programme()).values())
    for dropped in (
        "Georgia's Test Screen",  # unpublished test screening (not on the site)
        "Members' Screening: NAZA (15)",  # MembersOnly
        "Touch Tour Hamlet Hail to the Thief",  # SuppEvent
        "Hamlet Champagne Treat",  # SuppEvent / BasketAddOn
        "Candlelit Carols",  # SeasonPromoter Raymond Gubbay
        "Annual Staff Christmas Lunch - Barbican Centre",  # PrimaryArtForm Other
        "Barbican Ghost Tour",  # Other / Tour
        "Blue Badge Parking",  # no art form
        "Darbar Festival Talk / The Benaras Gharana by Sunanda Sharma",  # Talk
        "Ringdown",  # St Giles Cripplegate: off-site
        "Carols from Temple Church with the BBC Singers",  # Temple Church: off-site
        "Robert Ryman: The Real Thing",  # exhibition
        "Punch Brothers",  # Americana and Country: no category
        "Robert Henke",  # Electronica: no category
        "Always Already There: Society of Black Composers and beyond",  # no EventType (a lecture)
        "Screen FYC London",  # Cinema without a screening type
    ):
        assert dropped not in kept, dropped


def test_virtual_instances_dropped():
    events = _programme()
    names = _raw_names(events)
    # The LSO concert's "Wildcard" twin and the Drake showcase's stream are not seats.
    assert sum(1 for n in names.values() if n == "London Symphony Orchestra") == 1
    assert sum(1 for n in names.values() if n == "Drake Artist Music Showcase 2026") == 1
    assert len({e.external_id for e in events}) == len(events)


def test_site_join_urls_and_titles():
    events = _programme()
    names = _raw_names(events)
    by_raw = {names[e.external_id].strip(): e for e in events}
    lso = by_raw["London Symphony Orchestra"]
    assert lso.source_url == "https://www.barbican.org.uk/whats-on/2026/event/london-symphony-orchestrathomas-ades"
    assert lso.title == "London Symphony Orchestra/Thomas Adès"
    naza = sorted((e for e in events if names[e.external_id] == "NAZA (15)"), key=lambda e: e.start_time)
    assert [e.title for e in naza] == ["NAZA", "NAZA"]
    assert [(e.start_date, e.start_time) for e in naza] == [
        (dt.date(2026, 10, 24), dt.time(14, 10)), (dt.date(2026, 10, 24), dt.time(16, 5))]
    assert naza[0].source_url == "https://www.barbican.org.uk/whats-on/2026/event/naza"
    # Not on barbican.org.uk (lso.co.uk sells it): the Spektrix event page.
    assert "EventDetails.aspx?EventId=" in by_raw["Aris String Quartet"].source_url
    assert by_raw["Aris String Quartet"].source_url.startswith("https://spektrix.barbican.org.uk/")


def test_join_pages_prefers_specific_page_and_keeps_variant_names():
    infos = {
        "a": {"title": "Show", "eventInfo": [{"name": "Show", "id": "1A"}, {"name": "Show", "id": "2A"}]},
        "b": {"title": "Show (relaxed)", "eventInfo": [{"name": "Relaxed: Show", "id": "2A"}]},
        "c": {"title": "Two Nights", "eventInfo": [{"name": "Night 1", "id": "3A"}, {"name": "Night 2", "id": "4A"}]},
    }
    pages, titles = barbican.join_pages(infos)
    assert pages == {"1A": "a", "2A": "b", "3A": "c", "4A": "c"}
    assert titles == {"1A": "Show", "2A": "Show (relaxed)"}


def test_listing_and_show_page_parsers():
    links = barbican.listing_links((FIXTURES / "barbican_listing.html").read_text())
    assert links == [
        "https://www.barbican.org.uk/whats-on/2026/event/guildhall-school-chaos",
        "https://www.barbican.org.uk/whats-on/2026/event/guildhall-school-tiger-country",
        "https://www.barbican.org.uk/whats-on/2026/event/hamlet-hail-to-the-thief",
    ]
    info = barbican.page_info((FIXTURES / "barbican_show_page.html").read_text())
    assert info["title"] == "London Symphony Orchestra/Sir Antonio Pappano"
    assert info["eventInfo"] == [{"name": "London Symphony Orchestra", "id": "1238601ASLCGVGHJVMVKSDMSQRQVVKMCD"}]
    assert info["image"].startswith("https://www.barbican.org.uk/sites/default/files/")
    assert barbican.page_description(info) == (
        "Bruckner and Edmund Finnis with Sheku Kanneh-Mason\n\n"
        "The quiet intensity of Edmund Finnis’ Cello Concerto paves the way for "
        "Bruckner’s monumental, visionary Ninth Symphony."
    )
    assert barbican.page_info("<html></html>") is None


def _band(name: str, amount: float, default: bool = True, ticket: str = "Standard") -> dict:
    return {"amount": amount, "isBandDefault": default,
            "ticketType": {"name": ticket}, "priceBand": {"name": name}}


def test_young_barbican_band_does_not_widen_the_range():
    # Squid's live price list (2026-10-24); the site says "From £22.50",
    # "Young Barbican £12".
    squid = {"prices": [_band("A", 27.5), _band("B", 25.0), _band("C", 22.5),
                        _band("W", 27.5), _band("Y", 12.0),
                        _band("W", 27.5, False, "Wheelchair User")]}
    assert spk.price_text(squid, barbican.public_band) == "£27.50"
    bbc = {"prices": [_band("A", 50.0), _band("B", 42.0), _band("C", 34.0), _band("D", 25.0),
                      _band("E", 18.0), _band("W", 42.0), _band("Y", 12.0)]}
    assert spk.price_text(bbc, barbican.public_band) == "£18–50"
    # A Young Barbican-only performance: its band is the price.
    assert spk.price_text({"prices": [_band("Y", 12.0)]}, barbican.public_band) == "£12"


def test_page_content_fills_description_and_image():
    url = "https://www.barbican.org.uk/whats-on/2026/event/x"
    info = {"subtitle": "", "description": "A film.", "image": "https://img/x.avif"}
    event = ScrapedEvent(title="X", start_date=dt.date(2026, 11, 1), source_url=url, category_slugs=["film"])
    barbican.page_content({url: info})(event, {}, {})
    assert (event.description, event.image_url) == ("A film.", "https://img/x.avif")


def test_listing_url_window_and_art_forms():
    url = barbican.listing_url(dt.date(2026, 10, 24), 3)
    q = parse_qs(urlparse(url).query)
    assert q["dates[min]"] == ["2026-10-24"]
    assert q["page"] == ["3"]
    assert {k for k in q if k.startswith("af[")} == {"af[6]", "af[11]", "af[16]", "af[21]"}


def test_venue_mapping():
    assert barbican.venue({}, {"venue": {"name": "The Pit"}}) == "barbican"
    assert barbican.venue({}, {"venue": {"name": "Milton Court Studio"}}) == "milton-court"
    assert barbican.venue({}, {"venue": {"name": "St Giles Cripplegate"}}) is None
    assert barbican.venue({}, {"venue": {"name": "Barbican Hall"},
                               "attribute_InstanceType": "wildcard"}) is None
