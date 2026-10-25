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


def test_embedded_ids_booking_link_shapes():
    page = (
        '<a href="/book/instance/882636">'  # The Place
        ' <a href="https://brixtonhouse.co.uk/book-online/41235">'  # Brixton House
        " <button onclick=\"location.href='https://cptheatre.co.uk/tickets/351844'\">"  # CPT
        ' <a href="/x/book/543497"> EventInstanceId=12345 id="571766ANTDSKQCCHPCLVTGGPTTCSBMVDV"'
    )
    assert spk.embedded_ids(page) == {"882636", "41235", "351844", "543497", "12345", "571766"}
    # Not booking links: short numbers, other paths, digits run into words.
    assert spk.embedded_ids('<a href="/tickets/12"> /tickets/info /ticketsx/123456 /book/123456789') == set()


def test_listing_links_absolute_relative_and_sitemaps():
    listing = ('<a href="https://v/event/a/">A</a> <a href="/event/b/">B</a> <a href="event/c/">C</a>'
               ' <a href="/event/a/#dates">A again</a> <a href="/about/">About</a>')
    assert spk.listing_links(listing, "https://v/whats-on", r"https://v/event/[^/]+/") == [
        "https://v/event/a/", "https://v/event/b/", "https://v/event/c/",
    ]
    sitemap = "<urlset><url><loc>https://v/events/x</loc></url><url><loc>https://v/news/y</loc></url></urlset>"
    assert spk.listing_links(sitemap, "https://v/sitemap.xml", r"https://v/events/[^/]+") == ["https://v/events/x"]


def _fake_fetch(monkeypatch, pages):
    def fetch(url, headers=None, impersonate=False):
        if url not in pages:
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url),
                                        response=httpx.Response(404))
        return pages[url]

    monkeypatch.setattr(spk, "fetch", fetch)


def test_site_page_ids_several_listings_and_dead_pages(monkeypatch, caplog):
    _fake_fetch(monkeypatch, {
        "https://v/whats-on/": '<a href="/event/a/">A</a> <a href="/event/dead/">gone</a>',
        "https://v/cinema/": '<a href="https://v/event/a/">A</a> <a href="/event/b/">B</a>',
        "https://v/event/a/": '<a href="/book/1111">',
        "https://v/event/b/": '<a href="/book/instance/2222">',
    })
    site = spk.Site(("https://v/whats-on/", "https://v/cinema/"), r"https://v/event/[^/]+/")
    assert spk.site_page_ids(site) == {"https://v/event/a/": {"1111"}, "https://v/event/b/": {"2222"}}
    assert "https://v/event/dead/" in caplog.text  # skipped, with a warning


def test_site_page_ids_fail_when_a_required_listing_fails(monkeypatch):
    _fake_fetch(monkeypatch, {"https://v/whats-on/": '<a href="/event/a/">A</a>'})
    site = spk.Site(("https://v/whats-on/", "https://v/missing/"), r"https://v/event/[^/]+/", required=True)
    try:
        spk.site_page_ids(site)
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("a failed listing must fail the run when the join is curation")


def test_site_page_ids_skip_a_failed_listing_when_links_only(monkeypatch, caplog):
    _fake_fetch(monkeypatch, {
        "https://v/whats-on/": '<a href="/event/a/">A</a>',
        "https://v/event/a/": '<a href="/book/1111">',
    })
    site = spk.Site(("https://v/missing/", "https://v/whats-on/"), r"https://v/event/[^/]+/")
    assert spk.site_page_ids(site) == {"https://v/event/a/": {"1111"}}
    assert "https://v/missing/" in caplog.text  # skipped, with a warning


def test_scrape_without_the_site_links_the_spektrix_page(monkeypatch):
    # A links-only Site whose listing is unreachable (Cloudflare challenging
    # the production IP): same programme, Spektrix event pages.
    _fake_fetch(monkeypatch, {})
    events = [_event("100AAAA")]
    instances = [_inst("101" + "A" * 25, "100AAAA")]
    monkeypatch.setattr(spk, "fetch_programme", lambda client, today, http: (events, instances))
    monkeypatch.setattr(spk, "fetch_prices", lambda client, insts, http, bands=None: {})
    out = spk.scrape(spk.Client("v"), lambda e: ["theater"], site=spk.Site("https://v/whats-on/", r"https://v/e/.+"))
    assert [e.source_url for e in out] == ["https://system.spektrix.com/v/website/EventDetails.aspx?EventId=100"]


SEARCH_DOCS = [
    {"title": "Capriccio", "uri": "/events/capriccio", "type": "events",
     "emImportData": {"importId": "131401", "importUrl": "https://ticketing.v/client"}},
    {"title": "Trio  Avant", "uri": "/events/trio-avant", "type": "events", "emImportData": []},
    {"title": "No page", "type": "events"},
]


def test_search_page_ids_and_title_pages():
    index = spk.SearchIndex("v_main_production", "https://www.v.org")
    assert spk.search_page_ids(SEARCH_DOCS, index) == {"https://www.v.org/events/capriccio": {"131401"}}
    assert spk.search_title_pages(SEARCH_DOCS, index) == {
        "capriccio": "https://www.v.org/events/capriccio",
        "trio avant": "https://www.v.org/events/trio-avant",
    }
    assert spk.title_key("  TRIO\tAvant ") == "trio avant"


def _search_transport(pages, calls):
    def handler(request):
        calls.append(request)
        assert request.headers["X-TYPESENSE-API-KEY"] == spk.SEARCH_KEY
        assert request.url.params["filter_by"] == "type:=events"
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"found": sum(len(p) for p in pages),
                                         "hits": [{"document": d} for d in pages[page - 1]]})
    return httpx.MockTransport(handler)


def test_search_events_pages_through_the_index(monkeypatch):
    calls = []
    transport = _search_transport([SEARCH_DOCS[:2], SEARCH_DOCS[2:]], calls)
    real = httpx.Client
    monkeypatch.setattr(spk.httpx, "Client", lambda **kw: real(transport=transport, **kw))
    assert spk.search_events(spk.SearchIndex("v_main_production", "https://www.v.org")) == SEARCH_DOCS
    assert [c.url.params["page"] for c in calls] == ["1", "2"]
    assert calls[0].url.path == "/collections/v_main_production/documents/search"


def test_search_events_fails_on_an_empty_index(monkeypatch):
    transport = _search_transport([[]], [])
    real = httpx.Client
    monkeypatch.setattr(spk.httpx, "Client", lambda **kw: real(transport=transport, **kw))
    try:
        spk.search_events(spk.SearchIndex("gone", "https://www.v.org"))
    except ValueError:
        pass
    else:
        raise AssertionError("an empty index must fail the run")


def _band_price(band, amount, default=True):
    return {"amount": amount, "isBandDefault": default, "priceBand": {"name": band}}


def test_price_text_band_filter():
    prices = {"prices": [_band_price("A", 74.5), _band_price("D", 25.0), _band_price("Standing", 0.1)]}
    assert spk.price_text(prices) == "£0.10–74.50"
    assert spk.price_text(prices, lambda p: spk.band(p) != "Standing") == "£25–74.50"
    # A filter that keeps no paid price falls back to the whole list (a press
    # night selling only 10p standing tickets is not "free").
    assert spk.price_text({"prices": [_band_price("Y", 12.0)]}, lambda p: spk.band(p) != "Y") == "£12"
    press_night = {"prices": [_band_price("Standing", 0.1), _band_price("A", 0.0)]}
    assert spk.price_text(press_night, lambda p: spk.band(p) != "Standing") == "£0.10"
    assert spk.band({"priceBand": {"name": "Standard "}}) == "Standard" and spk.band({}) == ""


def test_access_annotations_flags_and_text_attributes():
    inst = _inst("1X", attribute_CaptionedPerformance=True, attribute_Captioned=True,
                 attribute_SignedBSLPerformance=True, attribute_PreviewPerformance=True,
                 attribute_SchoolPerformance=True, attribute_InstanceInfo=" BSL   Performance ",
                 attribute_Notes="")
    assert spk.access_annotations(inst) == ["captioned", "BSL interpreted", "preview"]
    assert spk.access_annotations(inst, ("InstanceInfo", "Notes", "Missing")) == [
        "captioned", "BSL interpreted", "preview", "BSL Performance"]


def test_build_annotation_attrs_and_finish():
    ev = _event(Price="Free")
    inst = _inst("5555BBBB", webInstanceId="77", attribute_AccessPerformance="Relaxed Performance")

    def finish(scraped, event, instance):
        scraped.source_url = f"https://venue/perf/{instance['webInstanceId']}"
        scraped.price = scraped.price or spk.attr(event, "Price").lower()

    [out] = spk.build(CLIENT, [(ev, inst, ["theater"])], {}, annotation_attrs=("AccessPerformance",),
                      finish=finish)
    assert out.annotations == ["Relaxed Performance"]
    assert out.source_url == "https://venue/perf/77" and out.price == "free"


def test_assign_plans_gives_venue_and_plan_name():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/venues"):
            return httpx.Response(200, json=[{"id": "V1", "name": "Main", "address": "1 St"}])
        plan_id = request.url.path.rsplit("/", 1)[-1]
        venue = {"id": "V1"} if plan_id == "P1" else {"id": "V9"}
        return httpx.Response(200, json={"id": plan_id, "name": f" Plan {plan_id} ", "venue": venue})

    instances = [_inst("1X", planId="P1"), _inst("2X", planId="P2"), _inst("3X")]
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        spk.assign_plans(CLIENT, instances, http)
    assert instances[0]["venue"]["name"] == "Main" and instances[0]["plan"] == {"name": "Plan P1"}
    assert instances[1]["venue"] == {} and instances[1]["plan"] == {"name": "Plan P2"}
    assert instances[2]["venue"] == {} and instances[2]["plan"] == {}


def test_scrape_pipeline_hooks(monkeypatch):
    events = [_event("1000AAAA", "Play"), _event("2000BBBB", "Gig")]
    instances = [_inst("1001" + "A" * 25, "1000AAAA", pl="PL1"), _inst("2001" + "B" * 25, "2000BBBB", pl="PL2")]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/events"):
            return httpx.Response(200, json=events)
        if path.endswith("/instances"):
            return httpx.Response(200, json=instances)
        return httpx.Response(200, json={"prices": [_band_price("A", 30.0), _band_price("M", 5.0)]})

    monkeypatch.setattr(spk, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    seen = []

    def prepare(evs, insts):
        seen.append((len(evs), len(insts)))
        evs[1]["attribute_Type"] = "Show"  # e.g. a label copied from the instances

    got = spk.scrape(
        CLIENT, lambda e: ["theater"] if spk.attr(e, "Type") == "Show" else [],
        today=dt.date(2026, 10, 24),
        page_ids={"https://v/gig/": {"2001"}},
        prepare=prepare,
        price_bands=lambda p: spk.band(p) != "M",
        finish=lambda s, e, i: s.annotations.append("finished"),
    )
    assert seen == [(2, 2)]
    [gig] = got
    assert gig.title == "Gig" and gig.source_url == "https://v/gig/"
    assert gig.price == "£30" and gig.annotations == ["finished"]
