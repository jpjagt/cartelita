"""Offline tests for the pure parts of tools/recon.py (no network, no browser)."""

import json
from pathlib import Path

import pytest

import recon
from recon import (
    Candidate,
    ProbeResult,
    client_verdict,
    extract_embedded,
    has_content,
    internal_links,
    is_challenge,
    is_noise,
    object_arrays,
    render_verdict,
    score_html_fragment,
    score_json,
    structure_sketch,
    try_json,
    unwrap_astro,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def embedded() -> dict[str, list[Candidate]]:
    html = (FIXTURES / "recon_embedded.html").read_text()
    by_label: dict[str, list[Candidate]] = {}
    for c in extract_embedded(html):
        by_label.setdefault(c.label, []).append(c)
    return by_label


# --- JSON helpers -----------------------------------------------------------


def test_try_json_tolerates_trailing_semicolon_and_rejects_non_json():
    assert try_json(' {"a": 1}; ') == {"a": 1}
    assert try_json("[1,2]") == [1, 2]
    assert try_json("function(){}") is None
    assert try_json("{broken") is None
    assert try_json("") is None


def test_structure_sketch_compacts_nested_arrays():
    data = {"total": 2, "items": [{"id": 1, "title": "a", "tags": ["x"]}, {"id": 2}]}
    assert structure_sketch(data) == "{total,items:[{id,title,tags:…}]×2}"
    assert structure_sketch([]) == "[]"
    assert structure_sketch("s") == "str"


def test_structure_sketch_truncates_wide_objects():
    wide = {f"k{i}": i for i in range(15)}
    assert structure_sketch(wide).endswith(",k11,+3}")


def test_structure_sketch_collapses_id_keyed_dicts():
    data = {"productions": {"28818": {"id": 1, "title": "x"}, "28823": {"id": 2}, "28824": {"id": 3}}}
    assert structure_sketch(data) == "{productions:{<id>:{id,title}}×3}"


def test_object_arrays_counts_id_keyed_dicts_as_arrays():
    liceu = json.loads((FIXTURES / "liceu_programme.json").read_text())
    arrays = {a.path: a.length for a in object_arrays(liceu)}
    assert arrays["$.productions.*"] == len(liceu["productions"])


# --- scoring ----------------------------------------------------------------


def test_score_json_prefers_event_list_and_reports_it():
    body = (FIXTURES / "recon_auditori_sessions.json").read_text()
    score, notes = score_json(json.loads(body), body)
    assert score > 10
    assert notes[0].startswith("best obj-array $ ×4")
    # event-ish keys are found one level down (wp_post.post_title)
    assert "post_title" in notes[0] and "start_datetime" in notes[0]
    assert any("date-like strings" in n for n in notes)


def test_score_json_ranks_events_above_config():
    events = json.loads((FIXTURES / "recon_auditori_sessions.json").read_text())
    config = {"path": {"baseUrl": "/", "currentLanguage": "ca"}, "user": {"uid": 0}}
    assert score_json(events, json.dumps(events))[0] > score_json(config, json.dumps(config))[0]


def test_score_json_picks_the_production_list_in_liceu_programme():
    body = (FIXTURES / "liceu_programme.json").read_text()
    _, notes = score_json(json.loads(body), body)
    assert "$.productions.*" in notes[0]


def test_score_html_fragment_counts_dates_and_markup():
    score, notes = score_html_fragment("<li>05/09/2026</li><li>2026-09-06</li>")
    assert score == pytest.approx(2.2)
    assert notes[0] == "2 date-like strings"


def test_date_regex_matches_month_names():
    assert recon.count_dates("za 17 okt 2026 · 5 de setembre de 2026 · 3 Dec. 2026") == 3


# --- embedded state ---------------------------------------------------------


def test_jsonld_events_get_a_bonus_over_page_metadata(embedded):
    meta, events = sorted(embedded["JSON-LD"], key=lambda c: c.score)
    assert "3 *Event" in events.notes[0]
    assert "MusicEvent" in events.notes[0]
    assert "*Event" not in meta.notes[0]
    assert events.score > meta.score + 10


def test_next_data_is_parsed_and_scored(embedded):
    (nd,) = embedded["__NEXT_DATA__"]
    assert nd.kind == "EMBED"
    assert nd.shape == "{props:{pageProps:{agenda:…}},page,buildId}"
    assert "$.props.pageProps.agenda.items ×4" in nd.notes[0]


def test_astro_island_props_are_unescaped_and_unwrapped(embedded):
    (astro,) = embedded["Astro island props"]
    assert astro.shape == "{events:[{slug,title,date}]×3}"


def test_unwrap_astro():
    assert unwrap_astro({"a": [0, "x"], "b": [1, [[0, 1], [0, 2]]]}) == {"a": "x", "b": [1, 2]}


def test_data_attribute_json_is_found(embedded):
    (attr,) = embedded["data-* JSON attr"]
    assert attr.shape == "[{id,title,start,price}]×3"


def test_window_state_and_application_json(embedded):
    assert embedded["window.__*_STATE__"][0].shape == "{ui:{menuOpen},filters:{genre}}"
    (cfg,) = embedded["application/json script"]
    assert cfg.score < 5


def test_rsc_flight_chunks_are_joined(embedded):
    (rsc,) = embedded["RSC flight (self.__next_f)"]
    assert rsc.kind == "EMBED(raw)"
    assert "2 chunks" in rsc.notes[0]
    assert "2 date-like strings" in rsc.notes[0]


def test_embedded_ranking_puts_event_sources_first():
    html = (FIXTURES / "recon_embedded.html").read_text()
    ranked = sorted(extract_embedded(html), key=lambda c: -c.score)
    assert ranked[0].label in {"JSON-LD", "__NEXT_DATA__"}
    assert ranked[-1].label in {"application/json script", "window.__*_STATE__"}


# --- filtering --------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google-analytics.com/g/collect?v=2",
        "https://consent.cookiebot.com/uc.js",
        "https://www.tivolivredenburg.nl/cdn-cgi/rum?",
        "https://forms-eu1.hscollectedforms.net/collected-forms/v1/config/json",
        "https://venue.example/wp-content/themes/x/img/sprite.svg",
        "https://venue.example/fonts/inter.woff2?v=3",
    ],
)
def test_noise_is_dropped(url):
    assert is_noise(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://liceubarcelona.cat/sites/default/files/programme.json?t=1791967940722",
        "https://www.auditori.cat/wp-admin/admin-ajax.php?action=get_auditori_sessions_query",
        "https://barcelona.cines-verdi.com/api/get-events",
    ],
)
def test_event_endpoints_are_kept(url):
    assert not is_noise(url)


# --- verdicts ---------------------------------------------------------------


def test_cloudflare_challenge_is_detected():
    assert is_challenge((FIXTURES / "recon_cloudflare_challenge.html").read_text())
    assert not is_challenge((FIXTURES / "recon_embedded.html").read_text())


def test_internal_links_counts_distinct_same_site_deep_links():
    html = (FIXTURES / "recon_embedded.html").read_text()
    assert internal_links(html, "www.venue.example") == 3


def _page(n_links: int) -> str:
    return "".join(f'<a href="/agenda/event-{i}/">e</a>' for i in range(n_links)) + "x" * 3000


def test_has_content_requires_200_and_the_real_page():
    challenge = (FIXTURES / "recon_cloudflare_challenge.html").read_text()
    host = "venue.example"
    assert has_content(ProbeResult("httpx", 200, _page(40)), 40, host)
    assert not has_content(ProbeResult("httpx", 403, _page(40)), 40, host)
    assert not has_content(ProbeResult("httpx", 200, challenge), 40, host)
    # 200 but a stub (far fewer links than the browser saw)
    assert not has_content(ProbeResult("httpx", 200, _page(5)), 40, host)
    assert not has_content(ProbeResult("httpx", None, error="ConnectError: boom"), 40, host)
    # no browser reference: any non-trivial, non-challenge body
    assert has_content(ProbeResult("httpx", 200, _page(0)), 0, host)


def test_client_verdict_only_credits_httpx_when_httpx_got_the_page():
    assert client_verdict(True, True) == "plain HTTP (httpx) is enough"
    assert client_verdict(True, False) == "plain HTTP (httpx) is enough"
    assert "use curl_cffi" in client_verdict(False, True)
    assert client_verdict(False, False).startswith("browser-only / blocked")
    assert "TLS certificate" in client_verdict(False, False, tls_error=True)


def test_tls_error_detection():
    assert ProbeResult("httpx", error="ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED]").tls_error
    assert ProbeResult("curl_cffi", error="CertificateVerifyError: ...").tls_error
    assert not ProbeResult("httpx", error="ReadTimeout: timed out").tls_error
    assert not ProbeResult("httpx", 403, "x").tls_error


def test_render_verdict():
    assert render_verdict(111, 116).startswith("SERVER-RENDERED")
    assert render_verdict(33, 81).startswith("JS-RENDERED")
    assert render_verdict(0, 0).startswith("SERVER-RENDERED")
