import datetime as dt

import pytest

from cartelera import geocode, run
from cartelera.geocode import (
    CITY_CENTRES, CityCentre, Hit, Nominatim, accept, build_queries, distance_km,
    geocode_venues, parse_response,
)
from cartelera.models import City, Category, Venue
from cartelera.seed import CITIES, _upsert_venue
from cartelera.scrapers import load_all
from cartelera.types import VenueDefinition

AMS = CITY_CENTRES["amsterdam"]
NOW = dt.datetime(2026, 10, 15, 3, 0, tzinfo=dt.timezone.utc)


def _result(lat, lng, rank=30, name="x"):
    return [{"lat": str(lat), "lon": str(lng), "place_rank": rank, "display_name": name}]


class FakeHttp:
    """Answers queries from a {query: payload} map (default: no result)."""

    def __init__(self, answers=None, error=None):
        self.answers, self.error = answers or {}, error
        self.calls: list[dict] = []

    def __call__(self, url, params):
        self.calls.append(params)
        if self.error:
            raise self.error
        return self.answers.get(params.get("q"), [])


def _nominatim(http, sleeps=None, clock=None):
    return Nominatim(get=http, sleep=(sleeps.append if sleeps is not None else lambda s: None),
                     clock=clock or (lambda: 0.0))


# --- pure parts -------------------------------------------------------------

def test_every_seeded_city_has_a_centre():
    assert {slug for slug, _ in CITIES} <= set(CITY_CENTRES)


def test_build_queries_appends_city_when_address_lacks_it():
    assert build_queries("Bimhuis", "Piet Heinkade 3", "Amsterdam") == [
        "Piet Heinkade 3, Amsterdam", {"street": "Piet Heinkade 3", "city": "Amsterdam"},
        "Piet Heinkade 3", "Bimhuis, Amsterdam"]


def test_build_queries_keeps_address_naming_the_city():
    assert build_queries("Bimhuis", "Piet Heinkade 3, 1019 BR Amsterdam", "Amsterdam") == [
        "Piet Heinkade 3, 1019 BR Amsterdam",
        {"street": "Piet Heinkade 3", "city": "Amsterdam"}, "Bimhuis, Amsterdam"]


def test_build_queries_city_match_ignores_accents_and_case():
    assert build_queries("CCE", "Tacuary 745, ASUNCION", "Asunción")[0] == "Tacuary 745, ASUNCION"


def test_build_queries_without_address_uses_name():
    assert build_queries("Arten", None, "Yerevan") == ["Arten, Yerevan"]
    assert build_queries("Arten", "  ", "Yerevan") == ["Arten, Yerevan"]


def test_address_variants_drop_house_suffix_and_leading_place():
    assert build_queries("Club Up", "Korte Leidsedwarsstraat 26-1, Amsterdam", "Amsterdam") == [
        "Korte Leidsedwarsstraat 26-1, Amsterdam", "Korte Leidsedwarsstraat 26, Amsterdam",
        {"street": "Korte Leidsedwarsstraat 26", "city": "Amsterdam"}, "Club Up, Amsterdam"]
    assert build_queries("K", "Westergas, Pazzanistraat 4, Amsterdam", "Amsterdam")[:2] == [
        "Westergas, Pazzanistraat 4, Amsterdam", "Pazzanistraat 4, Amsterdam"]
    assert "Carretera de Montjuïc, 66, 08038 Barcelona" in build_queries(
        "S", "Castell de Montjuïc, Carretera de Montjuïc, 66, 08038 Barcelona", "Barcelona")
    # postcodes are not house-number suffixes
    assert build_queries("X", "Leidseplein 12, 1017 PT Amsterdam", "Amsterdam")[0] == \
        "Leidseplein 12, 1017 PT Amsterdam"
    assert geocode._plain_house_number("Van Ostadestraat 55hs") == "Van Ostadestraat 55"
    assert geocode._plain_house_number("52/1 Pushkin St, 0002 Yerevan") == "52 Pushkin St, 0002 Yerevan"


def test_structured_street_part():
    sp = geocode._street_part
    assert sp("Elementenstraat 16, Amsterdam Westpoort") == "Elementenstraat 16"
    assert sp("C/ de les Hondures, 30, 08027 Barcelona") == "C/ de les Hondures 30"
    assert sp("Defensa Nacional 737 casi Washington, Asunción") == "Defensa Nacional 737"
    assert sp("Rigakade 10 1013 BC Amsterdam, Netherlands") == "Rigakade 10"
    assert sp("52/1 Pushkin St, 0002 Yerevan") == "52 Pushkin St"
    assert sp("Westergas, Pazzanistraat 4, Amsterdam") == "Pazzanistraat 4"
    assert sp("Gothic Quarter, Barcelona") is None


def test_name_matches_needs_a_distinctive_shared_word():
    assert geocode.name_matches("Big Bang Bar", Hit(0, 0, 30, "Big Bang Bar, Carrer x"))
    assert geocode.name_matches("Van Houtenkerk (Weesp)", Hit(0, 0, 30, "Van Houtenkerk, Weesp"))
    assert not geocode.name_matches("Sala Montjuïc", Hit(0, 0, 30, "Sala Apolo, Carrer Nou"))
    assert not geocode.name_matches("Eixample Teatre", Hit(0, 0, 30, "BIG: Barcelona Improv Group"))
    # any of the place's own names counts (display_name may be translated)
    assert geocode.name_matches("Alianza Francesa de Asunción", Hit(
        0, 0, 30, "French Alliance Paraguay, 1039", ("Alianza Francesa", "French Alliance Paraguay")))


def _locate(answers, name, address):
    return geocode.locate(_nominatim(FakeHttp(answers)), name, address, "Amsterdam", AMS)


def test_locate_prefers_precise_address_hit():
    hit = _locate({"Nes 75, Amsterdam": _result(52.37, 4.89, rank=30)}, "Tobacco", "Nes 75")
    assert hit.place_rank == 30


def test_locate_upgrades_street_hit_with_nearby_named_poi():
    answers = {"Nes 75, Amsterdam": _result(52.370, 4.895, rank=26),
               "Tobacco Theater, Amsterdam": _result(52.371, 4.894, rank=30, name="Tobacco Theater, 75, Nes")}
    assert _locate(answers, "Tobacco Theater", "Nes 75").place_rank == 30


def test_locate_keeps_street_when_named_poi_is_elsewhere_or_unrelated():
    far = {"Nes 75, Amsterdam": _result(52.370, 4.895, rank=26),
           "Tobacco Theater, Amsterdam": _result(52.30, 4.95, rank=30, name="Tobacco Theater")}
    assert _locate(far, "Tobacco Theater", "Nes 75").place_rank == 26
    other = {"Tobacco Theater, Amsterdam": _result(52.37, 4.89, rank=30, name="Sala Apolo")}
    assert _locate(other, "Tobacco Theater", None) is None


def test_locate_trusts_named_poi_on_the_same_street_over_a_far_street_segment():
    # the address resolved to a same-named street in a neighbouring town; the
    # venue's own POI sits on the city's street of that name
    answers = {"46 Mashtots street, Yerevan": _result(40.25, 44.60, rank=26,
                                                      name="Mesrop Mashtots Street, Arinj"),
               "Khachaturian Hall, Yerevan": _result(40.186, 44.515, rank=30,
                                                     name="Aram Khachaturian Concert Hall, 46, Mesrop Mashtots Avenue")}
    hit = geocode.locate(_nominatim(FakeHttp(answers)), "Khachaturian Hall",
                         "46 Mashtots street, Yerevan", "Yerevan", CITY_CENTRES["yerevan"])
    assert hit.place_rank == 30


def test_parse_response():
    hit = parse_response(_result(52.37, 4.9, rank=30, name="Bimhuis"))
    assert hit == Hit(52.37, 4.9, 30, "Bimhuis")
    named = [{**_result(1, 2)[0], "namedetails": {"name": "Մոսկվա", "name:en": "Moscow", "x": None}}]
    assert parse_response(named).names == ("Մոսկվա", "Moscow")
    assert parse_response([]) is None
    assert parse_response({"error": "x"}) is None
    assert parse_response([{"lat": "nope", "lon": "1"}]) is None


def test_distance_km():
    # Amsterdam centre → Rotterdam centre is ~57 km
    r = CITY_CENTRES["rotterdam"]
    assert 55 < distance_km(AMS.lat, AMS.lng, r.lat, r.lng) < 60
    assert distance_km(1, 2, 1, 2) == 0


def test_accept_rejects_far_hits():
    r = CITY_CENTRES["rotterdam"]
    assert not accept(Hit(r.lat, r.lng, 30), AMS)
    assert accept(Hit(52.30, 4.85, 30), AMS)  # ~9 km out


def test_accept_rejects_coarse_hits():
    # Nominatim matching the city (rank 16) or a postcode area is not a venue
    assert not accept(Hit(52.3730796, 4.8924534, 16), AMS)
    assert not accept(Hit(52.36, 4.88, 21), AMS)
    assert accept(Hit(52.36, 4.88, 26), AMS)  # a street is good enough
    assert not accept(None, AMS)


def test_accept_rejects_unranked_hit_on_the_city_centre():
    assert not accept(Hit(AMS.lat, AMS.lng, None), AMS)
    assert accept(Hit(AMS.lat + 0.01, AMS.lng, None), AMS)


def test_nominatim_rate_limits_and_sends_country():
    t = [0.0]
    sleeps: list[float] = []
    http = FakeHttp()
    n = Nominatim(get=http, sleep=lambda s: (sleeps.append(s), t.__setitem__(0, t[0] + s)),
                  clock=lambda: t[0])
    n.search("a", "nl")
    t[0] += 0.3
    n.search("b", "nl")
    assert sleeps == [pytest.approx(geocode.MIN_INTERVAL_S - 0.3)]
    assert http.calls[0] == {"q": "a", "format": "jsonv2", "limit": 1, "countrycodes": "nl",
                             "namedetails": 1}


def test_user_agent_is_cartelita():
    assert "Cartelita" in geocode.USER_AGENT and "cartelita.co" in geocode.USER_AGENT


# --- DB ---------------------------------------------------------------------

def _city(session, slug="amsterdam", name="Amsterdam"):
    city = City(slug=slug, name=name)
    session.add(city)
    session.flush()
    return city


def _venue(session, city, slug, name, address=None, **kw):
    v = Venue(slug=slug, name=name, city_id=city.id, address=address, **kw)
    session.add(v)
    session.flush()
    return v


def test_geocode_hit_miss_and_fallback(session):
    city = _city(session)
    _venue(session, city, "bimhuis", "Bimhuis", "Piet Heinkade 3")
    _venue(session, city, "nowhere", "Nowhere", "Fake 1")
    _venue(session, city, "named", "Named Place")
    http = FakeHttp({
        "Piet Heinkade 3, Amsterdam": _result(52.3785, 4.9128),
        # name fallback hits the city itself first → rejected
        "Named Place, Amsterdam": _result(52.3731, 4.8925, rank=16),
    })
    report = geocode_venues(session, nominatim=_nominatim(http), explicit=set(), now=lambda: NOW)
    assert [s for _c, s, _h in report.hits] == ["bimhuis"]
    assert sorted(s for _c, s, _n in report.misses) == ["named", "nowhere"]
    b = session.query(Venue).filter_by(slug="bimhuis").one()
    assert (b.lat, b.lng, b.geocoded_at) == (52.3785, 4.9128, NOW)
    n = session.query(Venue).filter_by(slug="nowhere").one()
    assert (n.lat, n.lng, n.geocoded_at) == (None, None, NOW)
    # tried address+city, bare address, then name+city
    assert [c.get("q", c.get("street")) for c in http.calls[-4:]] == [
        "Fake 1, Amsterdam", "Fake 1", "Fake 1", "Nowhere, Amsterdam"]
    assert http.calls[-3]["city"] == "Amsterdam"  # the structured one


def test_geocode_is_cached_unless_forced(session):
    city = _city(session)
    _venue(session, city, "done", "Done", "A 1", lat=1.0, lng=2.0, geocoded_at=NOW)
    _venue(session, city, "missed", "Missed", "B 1", geocoded_at=NOW)
    http = FakeHttp()
    geocode_venues(session, nominatim=_nominatim(http), explicit=set(), now=lambda: NOW)
    assert http.calls == []
    geocode_venues(session, nominatim=_nominatim(http), explicit=set(), force=True,
                   now=lambda: NOW)
    assert {c.get("q") for c in http.calls} >= {"A 1, Amsterdam", "B 1, Amsterdam"}


def test_geocode_skips_explicit_venues_even_forced(session):
    city = _city(session)
    _venue(session, city, "pinned", "Pinned", "A 1", lat=1.0, lng=2.0)
    http = FakeHttp()
    geocode_venues(session, nominatim=_nominatim(http), explicit={"pinned"}, force=True)
    assert http.calls == []
    assert session.query(Venue).filter_by(slug="pinned").one().lat == 1.0


def test_geocode_city_filter_and_budget(session):
    ams, utr = _city(session), _city(session, "utrecht", "Utrecht")
    for i in range(3):
        _venue(session, ams, f"a{i}", f"A{i}")
    _venue(session, utr, "u", "U")
    http = FakeHttp()
    report = geocode_venues(session, city_slug="amsterdam", max_venues=2,
                            nominatim=_nominatim(http), explicit=set())
    assert len(report.misses) == 2 and report.skipped == 1
    assert all("Utrecht" not in str(c) for c in http.calls)


def test_geocode_http_error_leaves_venue_pending(session):
    city = _city(session)
    _venue(session, city, "v", "V", "A 1")
    session.commit()
    with pytest.raises(RuntimeError):
        geocode_venues(session, nominatim=_nominatim(FakeHttp(error=RuntimeError("down"))),
                       explicit=set())
    session.rollback()
    assert session.query(Venue).filter_by(slug="v").one().geocoded_at is None


def test_geocode_after_run_is_non_fatal(session, monkeypatch, capsys):
    def boom(*a, **kw):
        raise RuntimeError("nominatim down")
    monkeypatch.setattr(geocode, "geocode_venues", boom)
    run._geocode_after_run(session)  # must not raise


def test_geocode_after_run_is_bounded(session, monkeypatch):
    seen = {}
    monkeypatch.setattr(geocode, "geocode_venues",
                        lambda s, **kw: seen.update(kw) or geocode.GeocodeReport())
    run._geocode_after_run(session)
    assert seen["max_venues"] == run.GEOCODE_AFTER_RUN_MAX


def test_geocode_cli_rejects_unknown_city(session):
    assert geocode.main(session, ["--city", "atlantis"]) == 1
    assert geocode.main(session, ["--bogus"]) == 1


# --- explicit coordinates in venue definitions ------------------------------

def test_definition_coords_must_come_in_pairs():
    with pytest.raises(ValueError):
        VenueDefinition(slug="x", name="X", city_slug="amsterdam", lat=52.0)


def test_seed_writes_explicit_coords_and_resets_on_address_change(session):
    city = _city(session)
    cats: dict[str, Category] = {}
    pinned = VenueDefinition(slug="p", name="P", city_slug="amsterdam", address="A 1",
                             lat=52.1, lng=4.9)
    _upsert_venue(session, pinned, city.id, cats)
    v = session.query(Venue).filter_by(slug="p").one()
    assert (v.lat, v.lng, v.geocoded_at) == (52.1, 4.9, None)

    plain = VenueDefinition(slug="q", name="Q", city_slug="amsterdam", address="B 1")
    _upsert_venue(session, plain, city.id, cats)
    q = session.query(Venue).filter_by(slug="q").one()
    q.lat, q.lng, q.geocoded_at = 52.2, 4.8, NOW
    _upsert_venue(session, plain, city.id, cats)  # same address: kept
    assert (q.lat, q.geocoded_at) == (52.2, NOW)
    _upsert_venue(session, plain.model_copy(update={"address": "C 2"}), city.id, cats)
    assert (q.lat, q.lng, q.geocoded_at) == (None, None, None)  # moved: look up again


def test_explicit_coordinates_sit_in_their_city():
    for _s, source in load_all().values():
        for v in source.venues:
            if v.lat is not None:
                c = CITY_CENTRES[v.city_slug]
                assert distance_km(v.lat, v.lng, c.lat, c.lng) <= geocode.MAX_DISTANCE_KM, v.slug


def test_nominatim_retries_on_429(monkeypatch):
    import httpx
    responses = [httpx.Response(429, headers={"Retry-After": "0"}),
                 httpx.Response(429, headers={"Retry-After": "500"}),
                 httpx.Response(200, json=_result(52.37, 4.9))]

    def handler(request):
        assert request.headers["User-Agent"] == geocode.USER_AGENT
        return responses.pop(0)

    sleeps: list[float] = []
    n = Nominatim(sleep=sleeps.append, clock=lambda: 0.0)
    n._client = httpx.Client(transport=httpx.MockTransport(handler),
                             headers={"User-Agent": geocode.USER_AGENT})
    assert n.search("Bimhuis, Amsterdam", "nl") == Hit(52.37, 4.9, 30, "x")
    assert sleeps == [geocode.BACKOFF_429_S, 500.0]
