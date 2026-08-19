import datetime as dt
import pytest
from cartelera.ig.capture import (
    TIMELINE_CONNECTION_KEY,
    parse_timeline,
    select_new_posts,
    proxy_settings,
    is_session_invalid,
)


# --- fixture builders: mirror the real timeline-connection shape -------------
# The web app's profile timeline response is
#   {"data": {"<TIMELINE_CONNECTION_KEY>": {"edges": [{"node": {...}}, ...]}}}
# and each node carries `code`, `caption.text`, `taken_at`, `image_versions2`
# and — for carousels — `carousel_media` (each child shaped like a node).


def _candidates(*urls):
    """image_versions2 with candidates largest-first, as Instagram serves them."""
    widths = [1080, 750, 640]
    return {"candidates": [
        {"url": u, "width": widths[i % len(widths)], "height": widths[i % len(widths)]}
        for i, u in enumerate(urls)
    ]}


def _node(code="Cxxx1", caption="a caption", taken_at=1767225600, **kw):
    node = {
        "pk": "1234567890",
        "code": code,
        "taken_at": taken_at,
        "media_type": 1,
        "image_versions2": _candidates(
            f"https://cdn.example.com/{code}_1080.jpg",
            f"https://cdn.example.com/{code}_750.jpg",
        ),
    }
    if caption is not None:
        node["caption"] = {"pk": "1", "text": caption}
    node.update(kw)
    return node


def _payload(*nodes):
    return {"data": {TIMELINE_CONNECTION_KEY: {
        "edges": [{"node": n} for n in nodes],
        "page_info": {"has_next_page": True, "end_cursor": "QVFE"},
    }}}


# --- parse_timeline ---------------------------------------------------------

def test_single_image_post_maps_all_fields():
    posts = parse_timeline(_payload(_node(code="CabC1", caption="Jazz tonight")), "mezzo.yerevan")
    assert len(posts) == 1
    p = posts[0]
    assert p.shortcode == "CabC1"
    assert p.handle == "mezzo.yerevan"
    assert p.caption == "Jazz tonight"
    assert p.image_urls == ["https://cdn.example.com/CabC1_1080.jpg"]
    assert p.images == []


def test_taken_at_becomes_tz_aware_utc():
    posts = parse_timeline(_payload(_node(taken_at=1767225600)), "h")
    assert posts[0].posted_at == dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)


def test_caption_less_post_has_none_caption():
    posts = parse_timeline(_payload(_node(caption=None)), "h")
    assert posts[0].caption is None


def test_caption_dict_without_text_is_none():
    node = _node(caption=None)
    node["caption"] = {"pk": "1"}  # present but textless, as IG sometimes serves
    posts = parse_timeline(_payload(node), "h")
    assert posts[0].caption is None


def test_carousel_keeps_child_order_and_best_candidate():
    node = _node(code="Ccar1", media_type=8, carousel_media=[
        {"image_versions2": _candidates("https://cdn.example.com/c1_big.jpg",
                                        "https://cdn.example.com/c1_small.jpg")},
        {"image_versions2": _candidates("https://cdn.example.com/c2_big.jpg",
                                        "https://cdn.example.com/c2_small.jpg")},
        {"image_versions2": _candidates("https://cdn.example.com/c3_big.jpg")},
    ])
    posts = parse_timeline(_payload(node), "h")
    assert posts[0].image_urls == [
        "https://cdn.example.com/c1_big.jpg",
        "https://cdn.example.com/c2_big.jpg",
        "https://cdn.example.com/c3_big.jpg",
    ]


def test_video_child_keeps_cover_image_and_drops_video_url():
    node = _node(code="Cvid1", media_type=8, carousel_media=[
        {"image_versions2": _candidates("https://cdn.example.com/photo.jpg")},
        {
            "media_type": 2,
            "video_versions": [{"url": "https://cdn.example.com/clip.mp4", "type": 101}],
            "image_versions2": _candidates("https://cdn.example.com/clip_cover.jpg"),
        },
        {  # a video child with no cover contributes nothing
            "media_type": 2,
            "video_versions": [{"url": "https://cdn.example.com/clip2.mp4", "type": 101}],
        },
    ])
    posts = parse_timeline(_payload(node), "h")
    assert posts[0].image_urls == [
        "https://cdn.example.com/photo.jpg",
        "https://cdn.example.com/clip_cover.jpg",
    ]


def test_single_video_post_keeps_cover_only():
    node = _node(code="Cvid2", media_type=2,
                 video_versions=[{"url": "https://cdn.example.com/reel.mp4"}])
    posts = parse_timeline(_payload(node), "h")
    assert posts[0].image_urls == ["https://cdn.example.com/Cvid2_1080.jpg"]


def test_post_without_shortcode_is_skipped_not_fabricated():
    bad = _node(code="Cgood")
    del bad["code"]
    posts = parse_timeline(_payload(bad, _node(code="Cgood2")), "h")
    assert [p.shortcode for p in posts] == ["Cgood2"]


def test_malformed_nodes_never_raise():
    payload = {"data": {TIMELINE_CONNECTION_KEY: {"edges": [
        {},                       # no node
        {"node": None},           # null node
        {"node": "nonsense"},     # wrong type
        {"node": {"code": "Cok", "image_versions2": {"candidates": "nope"}}},
        {"node": _node(code="Cfine")},
    ]}}}
    posts = parse_timeline(payload, "h")
    assert [p.shortcode for p in posts] == ["Cok", "Cfine"]
    assert posts[0].image_urls == []
    assert posts[0].posted_at is None


def test_unknown_payload_shape_returns_empty():
    assert parse_timeline({}, "h") == []
    assert parse_timeline({"data": {"something_else": {}}}, "h") == []
    assert parse_timeline({"data": None}, "h") == []


def test_feed_order_is_preserved():
    posts = parse_timeline(
        _payload(_node(code="C1"), _node(code="C2"), _node(code="C3")), "h"
    )
    assert [p.shortcode for p in posts] == ["C1", "C2", "C3"]


# --- select_new_posts (the driver's pure filtering step) --------------------

def _cap(code):
    from cartelera.ig.types import CapturedPost
    return CapturedPost(shortcode=code, handle="h", caption=None,
                        posted_at=None, image_urls=[])


def test_select_new_posts_drops_known_shortcodes():
    posts = [_cap("a"), _cap("b"), _cap("c")]
    assert [p.shortcode for p in select_new_posts(posts, {"b"}, 10)] == ["a", "c"]


def test_select_new_posts_limits_before_filtering():
    # The limit is the feed window we look at; known posts inside that window
    # are dropped, they do not pull older posts into view.
    posts = [_cap(c) for c in "abcde"]
    assert [p.shortcode for p in select_new_posts(posts, {"a", "b"}, 3)] == ["c"]


def test_select_new_posts_dedupes_overlapping_responses():
    posts = [_cap("a"), _cap("b"), _cap("a"), _cap("c")]
    assert [p.shortcode for p in select_new_posts(posts, set(), 10)] == ["a", "b", "c"]


def test_select_new_posts_handles_empty_input():
    assert select_new_posts([], {"a"}, 12) == []


def test_select_new_posts_with_a_zero_limit_looks_at_nothing():
    assert select_new_posts([_cap("a")], set(), 0) == []


# --- proxy_settings ---------------------------------------------------------

def test_proxy_settings_none_without_url():
    assert proxy_settings(None) is None
    assert proxy_settings("") is None


def test_proxy_settings_splits_credentials_out_of_server():
    assert proxy_settings("http://user:p%40ss@gate.proxy.io:7000") == {
        "server": "http://gate.proxy.io:7000",
        "username": "user",
        "password": "p@ss",
    }


def test_proxy_settings_without_credentials_or_port():
    assert proxy_settings("http://gate.proxy.io") == {"server": "http://gate.proxy.io"}


def test_proxy_settings_rejects_garbage():
    with pytest.raises(ValueError):
        proxy_settings("not a url")


# --- is_session_invalid -----------------------------------------------------

def test_login_redirect_is_an_invalid_session():
    assert is_session_invalid("https://www.instagram.com/accounts/login/?next=/x/", True, False)


def test_challenge_page_is_an_invalid_session():
    assert is_session_invalid("https://www.instagram.com/challenge/AbC/", True, False)


def test_no_timeline_plus_login_form_is_an_invalid_session():
    assert is_session_invalid("https://www.instagram.com/mezzo/", False, True)


def test_no_timeline_without_login_form_is_not_a_session_problem():
    # An empty profile or a slow load is not proof of a dead session.
    assert not is_session_invalid("https://www.instagram.com/mezzo/", False, False)


def test_healthy_profile_load_is_valid():
    assert not is_session_invalid("https://www.instagram.com/mezzo/", True, False)
