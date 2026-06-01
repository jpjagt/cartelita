import datetime as dt
from cartelera.models import City, Category, Venue, Event, EventTranslation


def test_can_create_venue_with_category_and_event(session):
    city = City(slug="barcelona", name="Barcelona")
    jazz = Category(slug="jazz", name="Jazz")
    session.add_all([city, jazz])
    session.flush()

    venue = Venue(slug="jamboree", name="Jamboree", city_id=city.id, categories=[jazz])
    session.add(venue)
    session.flush()

    ev = Event(
        venue_id=venue.id, title="Jam Session", start_date=dt.date(2026, 6, 1),
        start_time=dt.time(19, 0), price="€12", source_url="https://x/agenda/",
        external_id="41306", recurrence_hint="every Monday", categories=[jazz],
    )
    session.add(ev)
    session.commit()

    loaded = session.get(Event, ev.id)
    assert loaded.title == "Jam Session"
    assert loaded.venue.name == "Jamboree"
    assert [c.slug for c in loaded.categories] == ["jazz"]
    assert loaded.recurrence_hint == "every Monday"


def test_event_translations_relationship(session):
    city = City(slug="barcelona", name="Barcelona")
    session.add(city)
    session.flush()
    venue = Venue(slug="cccb", name="CCCB", city_id=city.id)
    session.add(venue)
    session.flush()
    ev = Event(
        venue_id=venue.id, title="Canonical title", start_date=dt.date(2026, 6, 1),
        source_url="https://cccb/es/event",
        translations=[
            EventTranslation(lang="en", title="EN title", source_url="https://cccb/en/event"),
            EventTranslation(lang="ca", title="CA title"),
        ],
    )
    session.add(ev)
    session.commit()

    loaded = session.get(Event, ev.id)
    langs = sorted(t.lang for t in loaded.translations)
    assert langs == ["ca", "en"]
    en = next(t for t in loaded.translations if t.lang == "en")
    assert en.title == "EN title" and en.source_url == "https://cccb/en/event"
