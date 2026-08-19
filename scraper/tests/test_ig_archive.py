import datetime as dt
import pytest
from cartelera.ig.types import CapturedPost, RawImage
from cartelera.ig.archive import (
    upsert_posts,
    archived_shortcodes,
    posts_missing_extraction,
    save_extraction,
    extracted_posts,
    get_session_state,
    set_session_state,
)
from cartelera.models import IgPost


def _post(shortcode="abc123", handle="cinemahouse.evn", posted_at=None, images=None, **kw):
    base = dict(
        shortcode=shortcode,
        handle=handle,
        caption="A flyer caption",
        posted_at=posted_at or dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        image_urls=[img.url for img in images] if images else [],
        images=images or [],
    )
    base.update(kw)
    return CapturedPost(**base)


def _image(idx, url="https://cdn.example.com/a.jpg", content_type="image/jpeg", data=b"\x00\x01"):
    return RawImage(url=url, content_type=content_type, data=data)


def test_upsert_posts_inserts_new_and_returns_count(session):
    n = upsert_posts(session, "cinemahouse", [_post()])
    session.commit()
    assert n == 1
    row = session.get(IgPost, "abc123")
    assert row is not None
    assert row.source_slug == "cinemahouse"
    assert row.handle == "cinemahouse.evn"
    assert row.caption == "A flyer caption"
    assert row.posted_at == dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def test_upsert_posts_round_trips_images_bytes_and_order(session):
    images = [
        _image(0, url="https://cdn.example.com/0.jpg", data=b"first-bytes"),
        _image(1, url="https://cdn.example.com/1.jpg", data=b"second-bytes"),
        _image(2, url="https://cdn.example.com/2.jpg", data=b"third-bytes"),
    ]
    upsert_posts(session, "cinemahouse", [_post(images=images)])
    session.commit()
    row = session.get(IgPost, "abc123")
    assert [img.url for img in row.images] == [
        "https://cdn.example.com/0.jpg",
        "https://cdn.example.com/1.jpg",
        "https://cdn.example.com/2.jpg",
    ]
    assert [img.data for img in row.images] == [b"first-bytes", b"second-bytes", b"third-bytes"]
    assert [img.idx for img in row.images] == [0, 1, 2]
    assert all(img.content_type == "image/jpeg" for img in row.images)


def test_upsert_posts_reupsert_existing_shortcode_is_noop(session):
    upsert_posts(session, "cinemahouse", [_post(caption="original")])
    session.commit()
    n = upsert_posts(session, "cinemahouse", [_post(caption="different caption now")])
    session.commit()
    assert n == 0
    row = session.get(IgPost, "abc123")
    assert row.caption == "original"
    assert session.query(IgPost).count() == 1


def test_upsert_posts_mixed_batch_counts_only_new(session):
    upsert_posts(session, "cinemahouse", [_post(shortcode="existing")])
    session.commit()
    n = upsert_posts(session, "cinemahouse", [
        _post(shortcode="existing", caption="ignored"),
        _post(shortcode="new-one"),
    ])
    session.commit()
    assert n == 1
    assert session.query(IgPost).count() == 2


def test_archived_shortcodes_scoped_to_handle(session):
    upsert_posts(session, "cinemahouse", [_post(shortcode="a", handle="cinemahouse.evn")])
    upsert_posts(session, "mezzo", [_post(shortcode="b", handle="mezzo.yerevan")])
    session.commit()
    assert archived_shortcodes(session, "cinemahouse.evn") == {"a"}
    assert archived_shortcodes(session, "mezzo.yerevan") == {"b"}
    assert archived_shortcodes(session, "unknown.handle") == set()


def test_missing_and_extracted_partition_and_order_by_posted_at(session):
    upsert_posts(session, "cinemahouse", [
        _post(shortcode="mid", posted_at=dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)),
        _post(shortcode="early", posted_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)),
        _post(shortcode="late", posted_at=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)),
    ])
    session.commit()
    save_extraction(session, "mid", {"events": []}, "gemini/gemini-2.5-flash", 1)
    session.commit()

    missing = posts_missing_extraction(session, "cinemahouse")
    assert [p.shortcode for p in missing] == ["early", "late"]

    extracted = extracted_posts(session, "cinemahouse")
    assert [p.shortcode for p in extracted] == ["mid"]


def test_save_extraction_round_trips_dict(session):
    upsert_posts(session, "cinemahouse", [_post()])
    session.commit()
    extraction = {"events": [{"title": "Screening", "confidence": 0.9}]}
    save_extraction(session, "abc123", extraction, "gemini/gemini-2.5-flash", 3)
    session.commit()
    row = session.get(IgPost, "abc123")
    assert row.extraction == extraction
    assert row.model_id == "gemini/gemini-2.5-flash"
    assert row.prompt_version == 3
    assert row.extracted_at is not None


def test_save_extraction_raises_on_double_save(session):
    upsert_posts(session, "cinemahouse", [_post()])
    session.commit()
    save_extraction(session, "abc123", {"events": []}, "model-a", 1)
    session.commit()
    with pytest.raises(ValueError):
        save_extraction(session, "abc123", {"events": []}, "model-b", 2)


def test_save_extraction_raises_on_unknown_shortcode(session):
    with pytest.raises(ValueError):
        save_extraction(session, "does-not-exist", {"events": []}, "model-a", 1)


def test_session_state_get_returns_none_when_unset(session):
    assert get_session_state(session) is None


def test_session_state_set_then_get_round_trips(session):
    set_session_state(session, {"cookies": ["a"], "origins": []})
    session.commit()
    assert get_session_state(session) == {"cookies": ["a"], "origins": []}


def test_session_state_set_overwrites(session):
    set_session_state(session, {"cookies": ["a"]})
    session.commit()
    set_session_state(session, {"cookies": ["b"]})
    session.commit()
    assert get_session_state(session) == {"cookies": ["b"]}
    from cartelera.models import IgSession
    assert session.query(IgSession).count() == 1
