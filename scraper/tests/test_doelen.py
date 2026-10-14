import datetime as dt
from pathlib import Path

import httpx
import pytest

from cartelera.scrapers import doelen as D

FIX = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)  # fixture capture date


def _parse(name, site):
    return D.parse_agenda((FIX / name).read_text(), D.SITES[site], today=TODAY)


@pytest.fixture(scope="module")
def doelen():
    return _parse("doelen_agenda_p1.html", D.DOELEN) + _parse("doelen_agenda_p2.html", D.DOELEN)


@pytest.fixture(scope="module")
def zuidplein():
    return [
        e
        for n in ("doelen_zuidplein_p1.html", "doelen_zuidplein_p2.html", "doelen_zuidplein_p10.html")
        for e in _parse(n, D.ZUIDPLEIN)
    ]


def test_doelen_parses_occurrences_with_dates_and_times(doelen):
    assert len(doelen) > 80
    for e in doelen:
        assert e.title and e.source_url.startswith("https://www.dedoelen.nl/")
        assert e.start_date >= TODAY
        assert e.venue_slug == D.DOELEN
        assert set(e.category_slugs) <= {"classical", "jazz", "pop", "folk"}
    assert sum(e.start_time is not None for e in doelen) / len(doelen) > 0.95
    ids = [e.external_id for e in doelen]
    assert len(ids) == len(set(ids))


def test_doelen_multi_date_production_splits_into_occurrences(doelen):
    # One card, two subshows (Oct 15 + 16), each its own occurrence + id.
    yuja = [e for e in doelen if e.title.startswith("Yuja Wang speelt Brahms")]
    assert {e.start_date for e in yuja} == {dt.date(2026, 10, 15), dt.date(2026, 10, 16)}
    assert all(e.start_time == dt.time(20, 15) for e in yuja)
    # Same-day double show: two occurrences, distinct times.
    sint = [e for e in doelen if e.title.startswith("Sint Sing Along")]
    assert sorted(e.start_time for e in sint) == [dt.time(13, 30), dt.time(16, 0)]
    # A "live in concert"-only production (Intouchables) is excluded.
    assert not [e for e in doelen if "Intouchables" in e.title]


def test_doelen_annotations_drop_marketing_labels(doelen):
    labo = next(e for e in doelen if e.title.startswith("Bach Collegium Japan"))
    assert labo.annotations == ["orkest", "Jurriaanse Zaal"]
    assert labo.price == "sold-out"


def test_doelen_categories_come_from_genre_labels(doelen):
    cats = {c for e in doelen for c in e.category_slugs}
    assert {"classical", "pop"} <= cats
    # talk (book presentations / podcasts) is not programme we list
    assert not [e for e in doelen if "Hagelslag" in e.title]
    assert not [e for e in doelen if "TEST" == e.title]
    assert all("klassiek" not in e.annotations for e in doelen)


def test_doelen_title_status_prefixes(doelen):
    assert not [e for e in doelen if e.title.lower().startswith(("geannuleerd", "uitverkocht"))]
    assert not [e for e in doelen if "Catching Cultures" in e.title]  # geannuleerd


def test_doelen_price_coverage(doelen):
    # Resident-orchestra concerts sold on the orchestras' own sites
    # ("externe verkoop") carry no price on the list; everything else does.
    own = [e for e in doelen if e.price is not None]
    assert len(own) / len(doelen) > 0.4
    for e in own:
        assert e.price in ("free", "sold-out", "pay what you can") or e.price.endswith("€")


def test_zuidplein_parses_and_filters(zuidplein):
    assert len(zuidplein) > 15
    titles = {e.title for e in zuidplein}
    assert all(e.venue_slug == D.ZUIDPLEIN for e in zuidplein)
    assert not [t for t in titles if "Sip & Paint" in t]  # Overig: workshop
    assert not [t for t in titles if "Moving Adventures" in t]  # Gastprogramma: hire
    for e in zuidplein:
        assert e.start_date >= TODAY and e.start_time is not None
    ids = [e.external_id for e in zuidplein]
    assert len(ids) == len(set(ids))


def test_zuidplein_kids_is_exclusive(zuidplein):
    kids = [e for e in zuidplein if "kids" in e.category_slugs]
    assert kids and all(e.category_slugs == ["kids"] for e in kids)


def test_zuidplein_prices(zuidplein):
    priced = [e for e in zuidplein if e.price]
    assert len(priced) / len(zuidplein) > 0.8
    mata = next(e for e in zuidplein if e.title.startswith("Mata Hari Returns"))
    assert mata.price == "14€"
    assert mata.title == "Mata Hari Returns — Tafel van Vijf"
    assert mata.start_time == dt.time(19, 30)
    assert "Kleine Zaal" in mata.annotations


def test_format_price():
    assert D.format_price([14.0]) == "14€"
    assert D.format_price([7.5]) == "7,50€"
    assert D.format_price([30.0, 45.0]) == "45€"
    assert D.format_price([25.0, 92.0]) == "25–92€"
    assert D.format_price([0.0]) == "free"


def test_yearless_date_uses_weekday():
    assert D._parse_date_text("wo 14 okt", TODAY) == dt.date(2026, 10, 14)
    assert D._parse_date_text("zo 30 mei", TODAY) == dt.date(2027, 5, 30)
    assert D._parse_date_text("do 1 jul 27", TODAY) == dt.date(2027, 7, 1)


def test_pagination():
    html = (FIX / "doelen_agenda_p1.html").read_text()
    assert D.next_page_url(html, D.SITES[D.DOELEN]) == "https://www.dedoelen.nl/nl/agenda?p54_page=2"


def test_gate_triggers_one_browser_pass(monkeypatch):
    calls = {"browser": 0, "get": []}
    page_html = (FIX / "doelen_zuidplein_p1.html").read_text()

    def fake_get(self, url, **kw):
        calls["get"].append((url, self.headers.get("cookie")))
        if self.headers.get("cookie") != "csq_token=t":
            return httpx.Response(307, headers={"location": "https://x/csq/"}, request=httpx.Request("GET", url))
        return httpx.Response(200, text=page_html, request=httpx.Request("GET", url))

    class FakePage:
        user_agent = "UA Cartelita"
        cookie_header = "csq_token=t"

    def fake_browser(url, **kw):
        calls["browser"] += 1
        return FakePage()

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(D, "browser_page", fake_browser)
    f = D._Fetcher(D.SITES[D.ZUIDPLEIN])
    assert "eventCard" in f.get("https://www.theaterzuidplein.nl/agenda")
    assert "eventCard" in f.get("https://www.theaterzuidplein.nl/agenda?p54_page=2")
    assert calls["browser"] == 1
