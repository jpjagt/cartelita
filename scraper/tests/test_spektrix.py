import datetime as dt

import httpx

from cartelera.scrapers import _spektrix as spk

CLIENT = spk.Client("acme")


def _event(id_="1000AAAA", name="Show", **attrs):
    ev = {"id": id_, "name": name, "description": "About it.", "htmlDescription": "",
          "imageUrl": "https://img/x.jpg", "webUrl": ""}
    ev.update({f"attribute_{k}": v for k, v in attrs.items()})
    return ev


def _inst(id_, event_id="1000AAAA", start="2026-10-30T19:30:00", pl="PL1", **extra):
    return {"id": id_, "event": {"id": event_id}, "start": start, "cancelled": False,
            "isOnSale": True, "priceList": {"id": pl}, **extra}


def test_numeric_id_and_booking_url():
    assert spk.numeric_id("118056AKTSMRLCGMVPKPCRQTBNJSGPJQG") == "118056"
    assert (spk.Client("royalcourt").booking_url({"id": "118056AKTS"})
            == "https://system.spektrix.com/royalcourt/website/EventDetails.aspx?EventId=118056")
    custom = spk.Client("kingsplace", "https://ticketing.purchase.kingsplace.co.uk")
    assert custom.api == "https://ticketing.purchase.kingsplace.co.uk/kingsplace/api/v3"


def test_attr_is_stripped_text():
    ev = _event(Type=" Show ", Empty=None, Flag=False)
    assert spk.attr(ev, "Type") == "Show"
    assert spk.attr(ev, "Empty") == "" and spk.attr(ev, "Flag") == ""
    assert spk.attr(ev, "Missing") == ""


def _price(amount, default=True):
    return {"amount": amount, "isBandDefault": default}


def test_price_text_uses_band_defaults_and_the_2x_rule():
    # Concession tiers (non-default) don't widen the range.
    assert spk.price_text({"prices": [_price(25), _price(12, default=False)]}) == "£25"
    assert spk.price_text({"prices": [_price(10), _price(29.5)]}) == "£10–29.50"
    assert spk.price_text({"prices": [_price(18), _price(16)]}) == "£18"
    assert spk.price_text({"prices": [_price(0)]}) == "free"
    assert spk.price_text({"prices": [_price(0), _price(5)]}) == "£5"
    assert spk.price_text({"prices": []}) is None
    # No band default at all → every price counts.
    assert spk.price_text({"prices": [_price(8, False), _price(20, False)]}) == "£8–20"


def test_select_keeps_programme_in_start_order_and_drops_the_rest():
    events = [_event("1A", "Play", Type="Show"), _event("2B", "Ice cream", Type="Ancillary")]
    instances = [
        _inst("12X", "1A", "2026-11-01T14:00:00"),
        _inst("11X", "1A", "2026-10-31T19:30:00"),
        _inst("13X", "1A", "2026-11-02T19:30:00", cancelled=True),
        _inst("21X", "2B"),
        _inst("99X", "9Z"),  # instance of an event outside the window/list
    ]
    calls = []

    def categorize(ev):
        calls.append(ev["id"])
        return ["theater"] if spk.attr(ev, "Type") == "Show" else []

    selected = spk.select(events, instances, categorize)
    assert [i["id"] for _e, i, _c in selected] == ["11X", "12X"]
    assert sorted(calls) == ["1A", "2B"]  # categorized once per event


def test_build_fields():
    ev = _event("1000AAAA", "  The   Play ")
    inst = _inst("5555BBBB", attribute_Captioned=True, attribute_Preview=False)
    [out] = spk.build(CLIENT, [(ev, inst, ["theater"])], {"PL1": "£20"})
    assert out.title == "The Play"
    assert out.start_date == dt.date(2026, 10, 30) and out.start_time == dt.time(19, 30)
    assert out.source_url == "https://system.spektrix.com/acme/website/EventDetails.aspx?EventId=1000"
    assert out.price == "£20" and out.external_id == "5555BBBB"
    assert out.description == "About it." and out.image_url == "https://img/x.jpg"
    assert out.annotations == ["captioned"] and out.venue_slug is None


def test_build_overrides_and_web_url():
    ev = _event(name="Season 26: Play")
    ev["webUrl"] = "https://venue/play"
    inst = _inst("5555BBBB")
    [plain] = spk.build(CLIENT, [(ev, inst, ["kids"])], {})
    assert plain.source_url == "https://venue/play" and plain.price is None
    [custom] = spk.build(
        CLIENT, [(ev, inst, ["kids"])], {},
        title=lambda e: e["name"].split(": ", 1)[1],
        url=lambda e: "https://venue/own-page",
        venue=lambda e, i: "acme-studio",
    )
    assert custom.title == "Play" and custom.source_url == "https://venue/own-page"
    assert custom.venue_slug == "acme-studio"


def test_description_falls_back_to_html():
    ev = _event()
    ev["description"] = ""
    ev["htmlDescription"] = "<p>One</p>\r\n\r\n<p>Two   words</p>"
    assert spk.description(ev) == "One\n\nTwo words"
    ev["htmlDescription"] = "<div id>\r\n\r\n</div>"
    assert spk.description(ev) is None


def test_fetch_prices_skips_off_sale_404s():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        inst_id = request.url.path.split("/")[-2]
        asked.append(inst_id)
        if inst_id == "1OFF":
            return httpx.Response(404)
        return httpx.Response(200, json={"prices": [_price(15)]})

    instances = [
        _inst("1OFF", pl="PL1", isOnSale=False),
        _inst("2ON", pl="PL1"),
        _inst("3OFF", pl="PL2", isOnSale=False),
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        prices = spk.fetch_prices(CLIENT, instances, http)
    assert prices == {"PL1": "£15", "PL2": "£15"}
    assert "1OFF" not in asked  # the on-sale instance answered first


def test_fetch_prices_gives_up_quietly():
    def handler(request):
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert spk.fetch_prices(CLIENT, [_inst("1X")], http) == {"PL1": None}


def test_fetch_programme_sends_the_date_window():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.path.rsplit("/", 1)[-1]] = dict(request.url.params)
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert spk.fetch_programme(CLIENT, dt.date(2026, 10, 24), http) == ([], [])
    assert seen["events"] == {"instanceStart_from": "2026-10-24", "instanceStart_to": "2027-04-25"}
    assert seen["instances"] == {"startFrom": "2026-10-24", "startTo": "2027-04-25"}


def test_select_drops_performances_at_other_venues():
    events = [_event("1A", "Play")]
    instances = [_inst("11X", "1A", venue={"name": "Main"}), _inst("12X", "1A", venue={"name": "Online"})]
    selected = spk.select(events, instances, lambda e: ["theater"],
                          lambda e, i: "acme" if i["venue"]["name"] == "Main" else None)
    assert [i["id"] for _e, i, _c in selected] == ["11X"]


def test_fetch_plan_venues():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/venues"):
            return httpx.Response(200, json=[{"id": "V1", "name": "Main", "address": "1 St"}])
        return httpx.Response(200, json={"id": "P1", "venue": {"id": "V1"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        got = spk.fetch_plan_venues(CLIENT, [_inst("1X", planId="P1"), _inst("2X", planId="P1")], http)
    assert got == {"P1": {"id": "V1", "name": "Main", "address": "1 St"}}


def test_site_urls_pick_the_page_with_most_of_an_events_ids():
    events = [_event("100AAAA"), _event("200BBBB")]
    instances = [_inst("101" + "A" * 25, "100AAAA"), _inst("102" + "A" * 25, "100AAAA"),
                 _inst("201" + "B" * 25, "200BBBB"), _inst("202" + "B" * 25, "200BBBB")]
    pages = {
        "https://v/show-a/": {"101", "102", "201"},  # also links one of B's ("you may also like")
        "https://v/show-b/": {"201", "202"},
        "https://v/other/": {"999"},
    }
    assert spk.site_urls(pages, events, instances) == {
        "100AAAA": "https://v/show-a/", "200BBBB": "https://v/show-b/",
    }


def test_site_page_ids_follow_matching_links(monkeypatch):
    pages = {
        "https://v/whats-on/": '<a href="https://v/event/a/">A</a> <a href="https://v/event/a/book/5">x</a>'
                               ' <a href="https://v/about/">About</a>',
        "https://v/event/a/": 'id="571766ANTDSKQCCHPCLVTGGPTTCSBMVDV" <a href="/x/book/543497">'
                              ' EventInstanceId=12345',
    }
    monkeypatch.setattr(spk, "fetch", lambda url, headers=None, impersonate=False: pages[url])
    got = spk.site_page_ids(spk.Site("https://v/whats-on/", r"https://v/event/[^/]+/"))
    assert got == {"https://v/event/a/": {"571766", "543497", "12345"}}
