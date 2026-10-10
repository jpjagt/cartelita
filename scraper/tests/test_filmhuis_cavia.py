import datetime as dt
from pathlib import Path

from cartelera.scrapers.filmhuis_cavia import (
    BASE_URL,
    default_price,
    detail_urls,
    month_urls,
    parse_month,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "filmhuis_cavia_agenda.html"
HOME = FIXTURES / "filmhuis_cavia_home.html"
PAGE_URL = f"{BASE_URL}/programma/oktober-2026"
DETAIL_PREFIX = "filmhuis_cavia_detail_"


def _details() -> dict[str, str]:
    return {
        f"{BASE_URL}/programma/{p.stem[len(DETAIL_PREFIX):]}": p.read_text()
        for p in FIXTURES.glob(f"{DETAIL_PREFIX}*.html")
    }


def _events():
    return parse_month(AGENDA.read_text(), PAGE_URL, _details())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment in e.title)


def test_month_pages_discovered_from_nav():
    assert month_urls(HOME.read_text()) == [PAGE_URL]


def test_detail_urls_are_same_site_more_links():
    urls = detail_urls(AGENDA.read_text())
    assert urls
    assert all(u.startswith(f"{BASE_URL}/programma/") and "#" not in u for u in urls)
    # The month page itself and off-site links (podiumnassau.nl) are not details.
    assert PAGE_URL not in urls
    # Every detail page the scraper would fetch is in the fixture set.
    assert set(urls) <= set(_details())


def test_parses_one_event_per_screening():
    # The month page's index table lists 18 screenings for October.
    assert len(_events()) == 18


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert dt.date(2026, 10, 1) <= ev.start_date <= dt.date(2026, 10, 31)
        assert ev.title
        assert ev.source_url.startswith(f"{BASE_URL}/programma/")
        assert ev.category_slugs == ["film"]
        assert ev.image_url and ev.image_url.startswith(BASE_URL)


def test_every_event_has_a_showtime():
    assert all(ev.start_time is not None for ev in _events())


def test_house_price_and_stated_overrides():
    assert default_price(AGENDA.read_text()) == "5€"
    events = _events()
    assert all(e.price for e in events)  # 100% coverage: house price fallback
    # Overrides stated on the detail page ("Tickets : €8 (or Cineville)").
    assert _by_title("Révélateur").price == "8€"
    # "Tickets (€10) include a shared meal" vs "Regular tickets (€7)" → highest.
    assert _by_title("objects speak").price == "10€"
    # Month page: "Entrance: Donation-based (Cineville not valid)".
    assert _by_title("Myanmar").price == "donation"
    # Detail anchor section: "Ticket: free (donations are welcome)".
    assert _by_title("Closing event").price == "free"
    # "Free entrance to the party" is not an admission line → house price.
    assert _by_title("Ménilmontant").price == "5€"
    assert _by_title("Time of the Gypsies").price == "5€"


def test_language_only_when_stated():
    assert _by_title("Time of the Gypsies").language == "EN subtitles"
    assert _by_title("Heavy").language == "no dialogue"
    # The workshop evening has no credits line → no language.
    assert _by_title("objects speak").language is None
    stated = [e for e in _events() if e.language]
    assert len(stated) >= 15


def test_type_and_series_go_to_annotations_not_category():
    ev = _by_title("Ex-Shaman")
    assert ev.annotations == ["Docu", "Brazil Unfiltered"]
    assert ev.start_date == dt.date(2026, 10, 15)
    assert ev.start_time == dt.time(20, 0)
    for e in _events():
        assert e.category_slugs == ["film"]


def test_external_id_is_unique_per_occurrence():
    ids = [e.external_id for e in _events()]
    assert all(ids)
    assert len(ids) == len(set(ids))
    for i in ids:
        assert "@" in i and "T" in i.split("@", 1)[1]


def test_header_with_several_days_emits_one_row_per_day():
    html = """
    <div class="col-content">
      <hr id="x" />
      <p>Vrijdag 6 en zaterdag 7 november, 20:30<br/><br/>CLASSIC</p>
      <h2>Stalker</h2>
      <p><strong>Andrej Tarkovski | 1979 | USSR | 161’ | EN subtitles</strong></p>
    </div>
    <div class="col-sidebar"><h6>Toegang 5 euro, tenzij anders vermeld.</h6></div>
    """
    events = parse_month(html, f"{BASE_URL}/programma/november-2026")
    assert [e.start_date for e in events] == [dt.date(2026, 11, 6), dt.date(2026, 11, 7)]
    assert len({e.external_id for e in events}) == 2
    assert all(e.start_time == dt.time(20, 30) for e in events)
    assert all(e.price == "5€" and e.language == "EN subtitles" for e in events)


def test_january_on_a_december_page_rolls_the_year():
    html = """
    <div class="col-content">
      <hr id="y" /><p>Vrijdag 1 januari, 20:00</p><h2>Nieuwjaarsfilm</h2>
    </div>
    """
    (ev,) = parse_month(html, f"{BASE_URL}/programma/december-2026")
    assert ev.start_date == dt.date(2027, 1, 1)
    assert ev.price is None  # no house-price statement on this page
