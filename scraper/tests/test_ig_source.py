"""The IG source glue: capture -> extract -> emit, end to end against the test DB.

No Instagram and no LLM anywhere: `capture_new_posts` and `extract_post` are
monkeypatched at their ig.source import site, so what is exercised here is
exactly the orchestration + mapping this module owns.
"""
import datetime as dt
import logging

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from cartelera.ig import archive
from cartelera.ig import source as ig_source
from cartelera.ig.source import IgProfileScraper, IgSourceConfig
from cartelera.ig.types import CapturedPost, RawImage
from cartelera.models import IgPost
from cartelera.types import SourceDefinition, VenueDefinition

HANDLE = "mezzo.test"
SOURCE_SLUG = "mezzo-ig"
TODAY = dt.date(2026, 9, 1)
STATE = {"cookies": [{"name": "sessionid", "value": "x"}]}


# --------------------------------------------------------------------------
# fixtures & doubles
# --------------------------------------------------------------------------

@pytest.fixture()
def factory(session, engine):
    """A session factory bound to the test engine.

    Depends on `session` so the schema is freshly applied for each test; the
    scraper opens (and commits in) its own session from this factory."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def _venue(slug, name, categories):
    return VenueDefinition(
        slug=slug, name=name, city_slug="yerevan", category_slugs=categories
    )


MEZZO = _venue("mezzo", "Mezzo Classic House Club", ["classical", "jazz", "rock"])
CINEMA = _venue("cinema-house", "Cinema House", ["film"])


def _source(*venues):
    return SourceDefinition(
        slug=SOURCE_SLUG, name="Mezzo (Instagram)", venues=list(venues or [MEZZO])
    )


def _config(*venues, **kw):
    kw.setdefault("canonical_lang", "hy")
    kw.setdefault("hints_by_venue", {"mezzo": "Nightly line-up posts."})
    return IgSourceConfig(handle=HANDLE, source=_source(*venues), **kw)


def _post(shortcode, images=("https://cdn.example/a.jpg", "https://cdn.example/b.jpg")):
    return CapturedPost(
        shortcode=shortcode,
        handle=HANDLE,
        caption=f"caption for {shortcode}",
        posted_at=dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc),
        image_urls=list(images),
        images=[
            RawImage(url=url, content_type="image/jpeg", data=b"\xff\xd8jpeg")
            for url in images
        ],
    )


def _event(date=TODAY + dt.timedelta(days=7), **kw):
    """One entry of a stored extraction (the shape IgExtraction.model_dump gives)."""
    event = {
        "venue_slug": "mezzo",
        "category": "jazz",
        "contents": [{"lang": "hy", "title": "Ջազ երեկո", "description": "Մեզզոյում"}],
        "day": date.day, "month": date.month, "year": date.year,
        "time": "21:00", "price": "5000֏", "language": None, "confidence": 0.9,
    }
    event.update(kw)
    return event


def _extraction(*events):
    return {"events": list(events)}


class FakeCapture:
    """Stands in for capture.capture_new_posts; serves one batch per call."""

    def __init__(self, *batches):
        self.batches = [list(b) for b in batches]
        self.calls = []

    def __call__(self, handles_with_known, storage_state, proxy_url, limit_per_profile=12):
        self.calls.append({
            "handles_with_known": [(h, set(k)) for h, k in handles_with_known],
            "storage_state": storage_state,
            "proxy_url": proxy_url,
            "limit_per_profile": limit_per_profile,
        })
        batch = self.batches.pop(0) if self.batches else []
        return {handle: batch for handle, _known in handles_with_known}


class FakeExtract:
    """Stands in for extract.extract_post; canned per shortcode, or explodes."""

    def __init__(self, by_shortcode, failing=()):
        self.by_shortcode = by_shortcode
        self.failing = set(failing)
        self.calls = []

    def __call__(self, post, roster, model):
        self.calls.append({"shortcode": post.shortcode, "roster": roster, "model": model})
        if post.shortcode in self.failing:
            raise RuntimeError("the model provider is down")
        return self.by_shortcode[post.shortcode]

    @property
    def shortcodes(self):
        return [c["shortcode"] for c in self.calls]


def _install(monkeypatch, capture, extract, today=TODAY):
    monkeypatch.setattr(ig_source, "capture_new_posts", capture)
    monkeypatch.setattr(ig_source, "extract_post", extract)
    monkeypatch.setattr(ig_source, "_today", lambda tz: today)
    monkeypatch.setattr(ig_source, "confidence_threshold", lambda: 0.75)
    monkeypatch.setattr(ig_source, "extract_model", lambda: "test/model")


def _store_session_state(session):
    archive.set_session_state(session, STATE)
    session.commit()


def _by_id(events):
    return {e.external_id: e for e in events}


# --------------------------------------------------------------------------
# first run: capture -> extract -> emit
# --------------------------------------------------------------------------

@pytest.fixture()
def first_run(monkeypatch, session, factory):
    """One completed run over two posts: a single-event one and a 3-event line-up."""
    _store_session_state(session)
    capture = FakeCapture([_post("AAA"), _post("BBB")])
    extract = FakeExtract({
        "AAA": _extraction(_event(contents=[
            {"lang": "hy", "title": "Ջազ երեկո", "description": "Մեզզոյում"},
            {"lang": "en", "title": "Jazz night", "description": "At Mezzo"},
        ])),
        "BBB": _extraction(
            _event(date=TODAY - dt.timedelta(days=3)),          # 0: already past
            _event(date=TODAY + dt.timedelta(days=30), category="classical",
                   contents=[{"lang": "hy", "title": "Դասական երեկո", "description": None}],
                   price=None, time=None, language="hy"),        # 1: publishable
            _event(confidence=0.3),                              # 2: below threshold
        ),
    })
    _install(monkeypatch, capture, extract)
    events = IgProfileScraper(_config(), session_factory=factory).scrape()
    return events, capture, extract


def test_first_run_emits_only_the_gated_events(first_run):
    events, _capture, _extract = first_run
    assert sorted(e.external_id for e in events) == ["ig-AAA", "ig-BBB-1"]


def test_external_id_is_bare_for_a_single_event_post_and_indexed_otherwise(first_run):
    events, _capture, _extract = first_run
    assert _by_id(events)["ig-AAA"].title == "Ջազ երեկո"
    # index 1 of the stored list, even though it is the only survivor of that post
    assert _by_id(events)["ig-BBB-1"].title == "Դասական երեկո"


def test_canonical_content_is_the_configured_language(first_run):
    events, _capture, _extract = first_run
    event = _by_id(events)["ig-AAA"]
    assert event.title == "Ջազ երեկո"
    assert event.description == "Մեզզոյում"


def test_other_languages_become_translations_pointing_at_the_post(first_run):
    events, _capture, _extract = first_run
    event = _by_id(events)["ig-AAA"]
    assert [(t.lang, t.title, t.description) for t in event.translations] == [
        ("en", "Jazz night", "At Mezzo")
    ]
    assert event.translations[0].source_url == "https://www.instagram.com/p/AAA/"
    assert _by_id(events)["ig-BBB-1"].translations == []


def test_events_carry_the_post_url_and_its_first_image(first_run):
    events, _capture, _extract = first_run
    assert _by_id(events)["ig-AAA"].source_url == "https://www.instagram.com/p/AAA/"
    assert _by_id(events)["ig-AAA"].image_url == "https://cdn.example/a.jpg"


def test_date_time_price_language_and_category_pass_through(first_run):
    events, _capture, _extract = first_run
    aaa = _by_id(events)["ig-AAA"]
    assert aaa.start_date == TODAY + dt.timedelta(days=7)
    assert aaa.start_time == dt.time(21, 0)
    assert aaa.start_times == [dt.time(21, 0)]
    assert aaa.price == "5000֏"
    assert aaa.language is None
    assert aaa.category_slugs == ["jazz"]
    assert aaa.venue_slug == "mezzo"

    bbb = _by_id(events)["ig-BBB-1"]
    assert bbb.start_time is None and bbb.start_times == []
    assert bbb.price is None
    assert bbb.language == "hy"
    assert bbb.category_slugs == ["classical"]


def test_capture_is_asked_for_the_handle_with_what_is_already_archived(first_run):
    _events, capture, _extract = first_run
    call = capture.calls[0]
    assert call["handles_with_known"] == [(HANDLE, set())]
    assert call["storage_state"] == STATE
    assert call["limit_per_profile"] == 12


def test_every_captured_post_is_archived_under_the_source_slug(first_run, session):
    session.expire_all()
    rows = session.scalars(select(IgPost).order_by(IgPost.shortcode)).all()
    assert [r.shortcode for r in rows] == ["AAA", "BBB"]
    assert {r.source_slug for r in rows} == {SOURCE_SLUG}
    assert all(r.extraction is not None for r in rows)
    assert {r.model_id for r in rows} == {"test/model"}


def test_extraction_is_given_the_configured_model_and_the_source_roster(first_run):
    _events, _capture, extract = first_run
    call = extract.calls[0]
    assert call["model"] == "test/model"
    roster = call["roster"]
    assert [v.slug for v in roster] == ["mezzo"]
    assert roster[0].name == "Mezzo Classic House Club"
    assert roster[0].category_slugs == ["classical", "jazz", "rock"]
    assert roster[0].hints == "Nightly line-up posts."


# --------------------------------------------------------------------------
# second run: emission from the archive, one parse per post, stable ids
# --------------------------------------------------------------------------

def test_second_run_reparses_nothing_and_keeps_the_same_ids(monkeypatch, session, factory, first_run):
    _events, _capture, extract = first_run
    already = list(extract.shortcodes)

    later = TODAY + dt.timedelta(days=10)  # the AAA event's date has now passed
    capture = FakeCapture([])  # nothing new on the profile
    _install(monkeypatch, capture, extract, today=later)
    events = IgProfileScraper(_config(), session_factory=factory).scrape()

    assert extract.shortcodes == already  # a post is parsed at most once, ever
    assert [e.external_id for e in events] == ["ig-BBB-1"]  # index frozen, not re-numbered
    assert capture.calls[0]["handles_with_known"] == [(HANDLE, {"AAA", "BBB"})]


# --------------------------------------------------------------------------
# failure modes
# --------------------------------------------------------------------------

def test_missing_session_state_tells_the_operator_to_run_ig_login(monkeypatch, session, factory):
    capture = FakeCapture([_post("AAA")])
    _install(monkeypatch, capture, FakeExtract({}))
    with pytest.raises(RuntimeError, match="ig-login"):
        IgProfileScraper(_config(), session_factory=factory).scrape()
    assert capture.calls == []


def test_a_failing_extraction_costs_only_its_own_post(monkeypatch, session, factory, caplog):
    _store_session_state(session)
    capture = FakeCapture([_post("AAA"), _post("BBB")])
    extract = FakeExtract({"BBB": _extraction(_event())}, failing={"AAA"})
    _install(monkeypatch, capture, extract)
    with caplog.at_level(logging.WARNING, logger="cartelera.ig.source"):
        events = IgProfileScraper(_config(), session_factory=factory).scrape()

    assert [e.external_id for e in events] == ["ig-BBB"]
    assert "AAA" in caplog.text
    session.expire_all()
    pending = session.get(IgPost, "AAA")
    assert pending.extraction is None  # still extraction-less, so it retries


def test_a_post_whose_extraction_failed_is_retried_on_the_next_run(monkeypatch, session, factory):
    _store_session_state(session)
    capture = FakeCapture([_post("AAA"), _post("BBB")], [])
    extract = FakeExtract({"BBB": _extraction(_event())}, failing={"AAA"})
    _install(monkeypatch, capture, extract)
    IgProfileScraper(_config(), session_factory=factory).scrape()

    extract.failing = set()
    extract.by_shortcode["AAA"] = _extraction(_event(category="rock"))
    events = IgProfileScraper(_config(), session_factory=factory).scrape()

    assert extract.shortcodes == ["AAA", "BBB", "AAA"]
    assert sorted(e.external_id for e in events) == ["ig-AAA", "ig-BBB"]


def test_every_extraction_failing_fails_the_source(monkeypatch, session, factory):
    _store_session_state(session)
    capture = FakeCapture([_post("AAA"), _post("BBB")])
    extract = FakeExtract({}, failing={"AAA", "BBB"})
    _install(monkeypatch, capture, extract)
    with pytest.raises(RuntimeError, match="extraction"):
        IgProfileScraper(_config(), session_factory=factory).scrape()


def test_capture_failures_propagate(monkeypatch, session, factory):
    _store_session_state(session)

    def boom(*args, **kwargs):
        raise RuntimeError("instagram is unreachable")

    _install(monkeypatch, boom, FakeExtract({}))
    with pytest.raises(RuntimeError, match="unreachable"):
        IgProfileScraper(_config(), session_factory=factory).scrape()


# --------------------------------------------------------------------------
# whitelist semantics: drop + log, never reach the runner's fail-fast
# --------------------------------------------------------------------------

def _run_one_post(monkeypatch, session, factory, extraction, *venues, caplog=None):
    _store_session_state(session)
    capture = FakeCapture([_post("AAA")])
    extract = FakeExtract({"AAA": extraction})
    _install(monkeypatch, capture, extract)
    scraper = IgProfileScraper(_config(*venues), session_factory=factory)
    if caplog is None:
        return scraper.scrape()
    with caplog.at_level(logging.INFO, logger="cartelera.ig.source"):
        return scraper.scrape()


def test_an_event_naming_a_venue_outside_the_source_is_dropped_and_logged(
    monkeypatch, session, factory, caplog
):
    extraction = _extraction(_event(venue_slug="malkhas-jazz-club"), _event())
    events = _run_one_post(monkeypatch, session, factory, extraction, MEZZO, CINEMA, caplog=caplog)
    assert [e.external_id for e in events] == ["ig-AAA-1"]
    assert "malkhas-jazz-club" in caplog.text


def test_a_category_outside_the_venues_roster_is_dropped_and_logged(
    monkeypatch, session, factory, caplog
):
    extraction = _extraction(_event(category="theater"), _event())
    events = _run_one_post(monkeypatch, session, factory, extraction, caplog=caplog)
    assert [e.external_id for e in events] == ["ig-AAA-1"]
    assert "theater" in caplog.text


def test_a_single_venue_source_tolerates_an_unset_venue_slug(monkeypatch, session, factory):
    events = _run_one_post(monkeypatch, session, factory, _extraction(_event(venue_slug=None)))
    assert [e.venue_slug for e in events] == [None]


def test_a_multi_venue_source_drops_an_event_with_no_venue(
    monkeypatch, session, factory, caplog
):
    extraction = _extraction(_event(venue_slug=None), _event())
    events = _run_one_post(monkeypatch, session, factory, extraction, MEZZO, CINEMA, caplog=caplog)
    assert [e.external_id for e in events] == ["ig-AAA-1"]
    assert "venue" in caplog.text


def test_multiple_contents_in_one_language_yield_one_translation(monkeypatch, session, factory):
    extraction = _extraction(_event(contents=[
        {"lang": "hy", "title": "Ջազ", "description": None},
        {"lang": "en", "title": "Jazz", "description": None},
        {"lang": "en", "title": "Jazz (again)", "description": None},
        {"lang": "hy", "title": "Ջազ (again)", "description": None},
    ]))
    events = _run_one_post(monkeypatch, session, factory, extraction)
    assert events[0].title == "Ջազ"
    assert [(t.lang, t.title) for t in events[0].translations] == [("en", "Jazz")]


def test_the_first_content_is_canonical_when_the_configured_language_is_absent(
    monkeypatch, session, factory
):
    extraction = _extraction(_event(contents=[
        {"lang": "ru", "title": "Джаз", "description": None},
        {"lang": "en", "title": "Jazz", "description": None},
    ]))
    events = _run_one_post(monkeypatch, session, factory, extraction)
    assert events[0].title == "Джаз"
    assert [t.lang for t in events[0].translations] == ["en"]


def test_an_untitled_event_is_dropped_and_logged(monkeypatch, session, factory, caplog):
    extraction = _extraction(
        _event(contents=[{"lang": "hy", "title": "  ", "description": "no title"}]),
        _event(),
    )
    events = _run_one_post(monkeypatch, session, factory, extraction, caplog=caplog)
    assert [e.external_id for e in events] == ["ig-AAA-1"]
    assert "title" in caplog.text


def test_a_post_with_no_events_emits_nothing(monkeypatch, session, factory):
    assert _run_one_post(monkeypatch, session, factory, _extraction()) == []


def test_an_imageless_post_emits_events_without_an_image(monkeypatch, session, factory):
    _store_session_state(session)
    capture = FakeCapture([_post("AAA", images=())])
    extract = FakeExtract({"AAA": _extraction(_event())})
    _install(monkeypatch, capture, extract)
    events = IgProfileScraper(_config(), session_factory=factory).scrape()
    assert [e.image_url for e in events] == [None]


# --------------------------------------------------------------------------
# the two first-wave sources
# --------------------------------------------------------------------------

def _registered(slug):
    from cartelera.scrapers import REGISTRY, load_all

    load_all()
    return REGISTRY[slug]


def test_cinema_house_is_registered_as_an_ig_source():
    scraper, source = _registered("cinema-house")
    assert isinstance(scraper, IgProfileScraper)
    assert scraper.config.handle == "cinemahouse.evn"
    assert scraper.config.canonical_lang == "hy"
    assert scraper.config.tz == "Asia/Yerevan"
    venue = source.venues[0]
    assert (venue.slug, venue.city_slug) == ("cinema-house", "yerevan")
    assert venue.category_slugs == ["film"]
    assert [(m.list_slug, m.whitelist_category_slug) for m in venue.list_memberships] == [
        ("film", None)
    ]
    assert venue.instagram_url == "https://www.instagram.com/cinemahouse.evn/"
    assert venue.site_url is None
    assert scraper.config.hints_by_venue["cinema-house"]


def test_mezzo_is_registered_with_its_three_whitelisted_lists():
    scraper, source = _registered("mezzo")
    assert isinstance(scraper, IgProfileScraper)
    assert scraper.config.canonical_lang == "hy"
    venue = source.venues[0]
    assert (venue.slug, venue.name, venue.city_slug) == (
        "mezzo", "Mezzo Classic House Club", "yerevan"
    )
    assert venue.category_slugs == ["classical", "jazz", "rock"]
    assert [(m.list_slug, m.whitelist_category_slug) for m in venue.list_memberships] == [
        ("classical", "classical"), ("jazz", "jazz"), ("rock", "rock")
    ]
    assert venue.instagram_url == f"https://www.instagram.com/{scraper.config.handle}/"
    assert scraper.config.hints_by_venue["mezzo"]


def test_both_ig_sources_are_single_venue_and_carry_a_venue_slug():
    for slug in ("cinema-house", "mezzo"):
        scraper, source = _registered(slug)
        assert len(source.venues) == 1
        assert scraper.venue_slug == slug
