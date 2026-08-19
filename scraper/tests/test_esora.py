import datetime as dt
from pathlib import Path

import httpx

from cartelera.scrapers.esora import EsoraFeedScraper, parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "esora_feed.json"

# The fixture's occurrences span 2026-08-20 (past) through 2026-08-30; TODAY
# sits between the past occurrence and the rest so both branches of the
# past-date filter are exercised.
TODAY = dt.date(2026, 8, 25)


def _events(category_slugs=("theater",), excluded_tags=("excluded-tag",)):
    return parse_feed(
        FIXTURE.read_text(),
        category_slugs=list(category_slugs),
        excluded_tags=excluded_tags,
        today=TODAY,
    )


def test_normal_occurrence_parses_date_time_title_price_image_translations():
    events = _events()
    normal = next(ev for ev in events if ev.external_id == "esora-occ-occ-normal")
    assert normal.start_date == dt.date(2026, 8, 26)
    assert normal.start_time == dt.time(20, 0)
    assert normal.start_times == [dt.time(20, 0)]
    assert normal.title == "Սովորական ներկայացում"
    assert normal.price == "5000֏"
    assert normal.image_url == (
        "https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)"
        "/events/ev-normal/normal.jpg"
    )
    langs = {t.lang for t in normal.translations}
    assert langs == {"ru", "en"}
    for t in normal.translations:
        assert t.title and t.title.strip()
        assert t.source_url == f"https://esora.app/{t.lang}/yerevan/events/ev-normal"


def test_category_slugs_are_filed_as_given():
    events = _events(category_slugs=("dance",))
    assert all(ev.category_slugs == ["dance"] for ev in events)


def test_past_occurrences_are_filtered():
    events = _events()
    assert all(ev.start_date >= TODAY for ev in events)
    assert not any(ev.external_id == "esora-occ-occ-past" for ev in events)
    assert not parse_feed(
        FIXTURE.read_text(),
        category_slugs=["theater"],
        today=dt.date(2027, 1, 1),
    )


def test_disabled_occurrence_is_skipped():
    events = _events()
    assert not any(ev.external_id == "esora-occ-occ-disabled-occ" for ev in events)


def test_disabled_event_is_skipped():
    events = _events()
    assert not any("Disabled Show" in ev.title for ev in events)


def test_excluded_tags_are_stripped_from_annotations():
    events = _events(excluded_tags=("excluded-tag",))
    normal = next(ev for ev in events if ev.external_id == "esora-occ-occ-normal")
    assert "excluded-tag" not in normal.annotations
    assert normal.annotations == ["genre-a"]


def test_excluded_tags_defaults_to_empty():
    # Without an explicit excluded_tags, nothing is stripped.
    events = parse_feed(FIXTURE.read_text(), category_slugs=["theater"], today=TODAY)
    normal = next(ev for ev in events if ev.external_id == "esora-occ-occ-normal")
    assert normal.annotations == ["excluded-tag", "genre-a"]


def test_exact_datetime_duplicate_collapses_preferring_priced_copy():
    events = [
        ev
        for ev in _events()
        if ev.start_date == dt.date(2026, 8, 29) and ev.start_time == dt.time(21, 30)
    ]
    assert len(events) == 1
    assert events[0].price == "3000֏"
    assert events[0].title == "Dup Show B (priced copy)"


def test_different_showtimes_same_night_both_kept():
    events = [ev for ev in _events() if ev.start_date == dt.date(2026, 8, 30)]
    assert len(events) == 2
    assert {ev.start_time for ev in events} == {dt.time(19, 0), dt.time(21, 0)}


def test_total_event_count_after_filtering_and_dedup():
    # 8 raw occurrences: 1 past, 1 disabled-occurrence, 1 disabled-event, one
    # exact duplicate pair collapsing to 1 -> 8 - 1 - 1 - 1 - 1 = 4.
    assert len(_events()) == 4


def test_language_is_never_inferred():
    for ev in _events():
        assert ev.language is None


class _FakeTransport(httpx.BaseTransport):
    """Serves the fixture across N pages so scrape()'s pagination loop can be
    exercised without a live network call."""

    def __init__(self, pages: list[dict]):
        self._pages = pages

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=self._pages[page - 1])


def _page(occurrence_id: str, event_id: str, date: str, page: int, total_pages: int) -> dict:
    return {
        "result": {
            "eventOccurrenceIds": [occurrence_id],
            "pagination": {"page": page, "limit": 100, "total": total_pages, "totalPages": total_pages},
        },
        "entities": {
            "events": {
                event_id: {
                    "eventId": event_id,
                    "title": f"Show {page}",
                    "description": None,
                    "i18n": {"title": {"hy": {"origin": "source", "content": f"Show {page}"}}, "description": {}},
                    "category": "standard",
                    "tags": [],
                    "media": [],
                    "disabledAt": None,
                }
            },
            "eventOccurrences": {
                occurrence_id: {
                    "eventOccurrenceId": occurrence_id,
                    "startDate": date,
                    "startTime": "20:00:00",
                    "endDate": None,
                    "endTime": None,
                    "price": None,
                    "eventId": event_id,
                    "disabledAt": None,
                }
            },
        },
    }


def test_scrape_follows_pagination_across_pages(monkeypatch):
    pages = [
        _page("occ-p1", "ev-p1", "2099-01-01", 1, 2),
        _page("occ-p2", "ev-p2", "2099-01-02", 2, 2),
    ]
    scraper = EsoraFeedScraper(
        venue_slug="fake-venue",
        event_source_id="fake-source-id",
        category_slugs=["theater"],
    )
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: real_client(transport=_FakeTransport(pages), **{k: v for k, v in kw.items() if k != "transport"}),
    )
    events = scraper.scrape()
    assert {ev.title for ev in events} == {"Show 1", "Show 2"}
    assert len(events) == 2


def test_scrape_stops_at_max_pages_cap(monkeypatch):
    # totalPages says 99, far beyond _MAX_PAGES=10 — scrape() must not loop
    # unboundedly.
    pages = [_page(f"occ-p{i}", f"ev-p{i}", f"2099-02-{i:02d}", i, 99) for i in range(1, 11)]
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: real_client(transport=_FakeTransport(pages), **{k: v for k, v in kw.items() if k != "transport"}),
    )
    scraper = EsoraFeedScraper(
        venue_slug="fake-venue",
        event_source_id="fake-source-id",
        category_slugs=["theater"],
    )
    events = scraper.scrape()
    assert len(events) == 10
