import datetime as dt
from cartelera.seed import seed
from cartelera.upsert import upsert_venue_events
from cartelera.models import Event
from cartelera.types import ScrapedEvent


def _ev(**kw):
    base = dict(title="Show", start_date=dt.date(2026, 6, 2),
                source_url="https://jamboreejazz.com/agenda/", category_slugs=["jazz"])
    base.update(kw)
    return ScrapedEvent(**base)


def test_insert_then_update_by_external_id_no_duplicate(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="41306", title="Jam")])
    session.commit()
    upsert_venue_events(session, "jamboree", [_ev(external_id="41306", title="Jam Renamed")])
    session.commit()
    rows = session.query(Event).all()
    assert len(rows) == 1
    assert rows[0].title == "Jam Renamed"


def test_reschedule_updates_date_in_place(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="9", start_date=dt.date(2026, 6, 2))])
    session.commit()
    upsert_venue_events(session, "jamboree", [_ev(external_id="9", start_date=dt.date(2026, 6, 9))])
    session.commit()
    rows = session.query(Event).all()
    assert len(rows) == 1
    assert rows[0].start_date == dt.date(2026, 6, 9)


def test_events_get_jazz_category(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="1")])
    session.commit()
    ev = session.query(Event).one()
    assert [c.slug for c in ev.categories] == ["jazz"]


def test_distinct_external_ids_create_distinct_rows(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="1"), _ev(external_id="2")])
    session.commit()
    assert session.query(Event).count() == 2


def test_translations_are_written_and_replaced(session):
    from cartelera.types import ScrapedTranslation
    from cartelera.models import EventTranslation
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(
        external_id="t", translations=[ScrapedTranslation(lang="en", title="EN title")])])
    session.commit()
    assert session.query(EventTranslation).count() == 1
    # re-scrape with a different set replaces wholesale
    upsert_venue_events(session, "jamboree", [_ev(
        external_id="t", translations=[ScrapedTranslation(lang="ca", title="CA title")])])
    session.commit()
    rows = session.query(EventTranslation).all()
    assert len(rows) == 1 and rows[0].lang == "ca"
