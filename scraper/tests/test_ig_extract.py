import base64
import datetime as dt
import json
from types import SimpleNamespace

import litellm
import pytest

from cartelera.ig.types import RosterVenue
from cartelera.ig.extract import (
    PROMPT_VERSION,
    ExtractedContent,
    ExtractedEvent,
    IgExtraction,
    ExtractionError,
    GatedEvent,
    build_messages,
    confidence_threshold,
    extract_model,
    extract_post,
    gate_events,
)
from cartelera.models import IgPost, IgPostImage


ROSTER = [
    RosterVenue(
        slug="mezzo",
        name="Mezzo Classic House Club",
        category_slugs=["jazz", "classical", "music"],
        hints="Posts a weekly line-up carousel every Monday.",
    ),
    RosterVenue(slug="cinema-house", name="Cinema House", category_slugs=["cinema"]),
]


def _post(caption="Concert tonight", images=(("image/jpeg", b"\xff\xd8flyer"),)):
    """A detached IgPost row — no DB needed for extraction."""
    row = IgPost(
        shortcode="ABC123",
        source_slug="mezzo-ig",
        handle="mezzo.yerevan",
        caption=caption,
        posted_at=dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc),
    )
    row.images = [
        IgPostImage(shortcode="ABC123", idx=idx, url=f"https://cdn.example/{idx}.jpg",
                    content_type=ct, data=data)
        for idx, (ct, data) in enumerate(images)
    ]
    return row


def _response(payload):
    """Minimal stand-in for a litellm ModelResponse."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


def _event(**kw):
    base = dict(
        venue_slug="mezzo",
        category="jazz",
        contents=[{"lang": "en", "title": "Trio night", "description": None}],
        day=12, month=9, year=2026, time="21:00",
        price="5000֏", language="non-verbal", confidence=0.9,
    )
    base.update(kw)
    return base


def _fake_completion(monkeypatch, *responses):
    """Install a litellm.completion returning `responses` in order; record calls."""
    calls = []
    queue = list(responses)

    def fake(**kwargs):
        calls.append(kwargs)
        item = queue.pop(0) if queue else responses[-1]
        if isinstance(item, Exception):
            raise item
        return _response(item)

    monkeypatch.setattr(litellm, "completion", fake)
    return calls


def _text_blocks(messages):
    return [
        part["text"]
        for message in messages
        for part in message["content"]
        if part["type"] == "text"
    ]


def _image_urls(messages):
    return [
        part["image_url"]["url"]
        for message in messages
        for part in message["content"]
        if part["type"] == "image_url"
    ]


# --------------------------------------------------------------------------
# message assembly
# --------------------------------------------------------------------------

def test_build_messages_includes_every_image_as_a_data_url():
    post = _post(images=[("image/jpeg", b"one"), ("image/png", b"two"), ("image/webp", b"three")])
    urls = _image_urls(build_messages(post, ROSTER))
    assert urls == [
        "data:image/jpeg;base64," + base64.b64encode(b"one").decode(),
        "data:image/png;base64," + base64.b64encode(b"two").decode(),
        "data:image/webp;base64," + base64.b64encode(b"three").decode(),
    ]


def test_build_messages_includes_the_caption_verbatim():
    post = _post(caption="Ջազ երեկո՝ 12 սեպտեմբերին, 21:00")
    assert any("Ջազ երեկո՝ 12 սեպտեմբերին, 21:00" in text for text in _text_blocks(build_messages(post, ROSTER)))


def test_build_messages_handles_a_captionless_post():
    post = _post(caption=None)
    messages = build_messages(post, ROSTER)
    assert _image_urls(messages)  # still carries the flyer
    assert all("None" not in text for text in _text_blocks(messages))


def test_build_messages_renders_the_roster_with_slugs_names_categories_and_hints():
    instructions = _text_blocks(build_messages(_post(), ROSTER))[0]
    assert "mezzo" in instructions
    assert "Mezzo Classic House Club" in instructions
    assert "jazz" in instructions and "classical" in instructions
    assert "Posts a weekly line-up carousel every Monday." in instructions
    assert "cinema-house" in instructions and "Cinema House" in instructions


def test_instructions_state_the_core_rules():
    instructions = _text_blocks(build_messages(_post(), ROSTER))[0].lower()
    assert "null" in instructions            # never invent unstated fields
    assert "translat" in instructions        # contents is extraction, not translation
    assert "confidence" in instructions
    assert "json" in instructions
    assert "weekly" in instructions          # line-up post => one event per date


def test_build_messages_is_a_single_multimodal_user_message():
    messages = build_messages(_post(), ROSTER)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


# --------------------------------------------------------------------------
# extract_post
# --------------------------------------------------------------------------

def test_extract_post_passes_the_configured_model_through(monkeypatch):
    calls = _fake_completion(monkeypatch, {"events": []})
    extract_post(_post(), ROSTER, "anthropic/claude-haiku-4-5")
    assert calls[0]["model"] == "anthropic/claude-haiku-4-5"


def test_extract_post_sends_the_assembled_messages(monkeypatch):
    calls = _fake_completion(monkeypatch, {"events": []})
    post = _post(caption="Tonight!")
    extract_post(post, ROSTER, "gemini/gemini-2.5-flash")
    assert calls[0]["messages"] == build_messages(post, ROSTER)


def test_extract_post_requests_the_schema_as_response_format(monkeypatch):
    calls = _fake_completion(monkeypatch, {"events": []})
    extract_post(_post(), ROSTER, "gemini/gemini-2.5-flash")
    assert calls[0]["response_format"] is IgExtraction


def test_extract_post_returns_a_plain_dict(monkeypatch):
    _fake_completion(monkeypatch, {"events": [_event()]})
    result = extract_post(_post(), ROSTER, "m")
    assert isinstance(result, dict)
    assert result["events"][0]["venue_slug"] == "mezzo"
    assert result["events"][0]["day"] == 12
    json.dumps(result)  # JSONB-storable as-is


def test_extract_post_round_trips_armenian_and_russian_contents(monkeypatch):
    payload = {"events": [_event(contents=[
        {"lang": "hy", "title": "Ջազ երեկո", "description": "Մեզզոյում"},
        {"lang": "ru", "title": "Джазовый вечер", "description": None},
        {"lang": "en", "title": "Jazz night", "description": "At Mezzo"},
    ])]}
    _fake_completion(monkeypatch, payload)
    contents = extract_post(_post(), ROSTER, "m")["events"][0]["contents"]
    assert [c["lang"] for c in contents] == ["hy", "ru", "en"]
    assert contents[0]["title"] == "Ջազ երեկո"
    assert contents[1]["title"] == "Джазовый вечер"


def test_extract_post_handles_a_multi_event_line_up(monkeypatch):
    payload = {"events": [
        _event(day=1, contents=[{"lang": "en", "title": "Mon", "description": None}]),
        _event(day=2, category="classical", contents=[{"lang": "en", "title": "Tue", "description": None}]),
        _event(day=3, venue_slug="cinema-house", category="cinema",
               contents=[{"lang": "en", "title": "Wed", "description": None}]),
    ]}
    _fake_completion(monkeypatch, payload)
    events = extract_post(_post(), ROSTER, "m")["events"]
    assert [e["day"] for e in events] == [1, 2, 3]
    assert events[2]["venue_slug"] == "cinema-house"


def test_extract_post_accepts_an_empty_event_list(monkeypatch):
    _fake_completion(monkeypatch, {"events": []})
    assert extract_post(_post(), ROSTER, "m") == {"events": []}


def test_extract_post_retries_once_on_invalid_json_and_succeeds(monkeypatch):
    calls = _fake_completion(monkeypatch, "not json at all", {"events": [_event()]})
    result = extract_post(_post(), ROSTER, "m")
    assert len(calls) == 2
    assert result["events"][0]["category"] == "jazz"


def test_the_retry_appends_the_validation_error_to_the_conversation(monkeypatch):
    calls = _fake_completion(monkeypatch, "not json at all", {"events": []})
    extract_post(_post(), ROSTER, "m")
    first, second = calls[0]["messages"], calls[1]["messages"]
    assert second[: len(first)] == first
    assert len(second) == len(first) + 1
    assert second[-1]["role"] == "user"
    assert "json" in second[-1]["content"].lower()


def test_extract_post_retries_once_on_schema_violation(monkeypatch):
    # contents must have at least one entry
    calls = _fake_completion(monkeypatch, {"events": [_event(contents=[])]}, {"events": []})
    extract_post(_post(), ROSTER, "m")
    assert len(calls) == 2


def test_extract_post_raises_after_exactly_one_retry(monkeypatch):
    calls = _fake_completion(monkeypatch, "nope", "still nope", {"events": []})
    with pytest.raises(ExtractionError):
        extract_post(_post(), ROSTER, "m")
    assert len(calls) == 2


def test_extract_post_falls_back_to_json_mode_when_the_provider_rejects_the_schema(monkeypatch):
    calls = _fake_completion(
        monkeypatch,
        litellm.exceptions.BadRequestError(
            message="response_format pydantic schema unsupported", model="m", llm_provider="x"
        ),
        {"events": [_event()]},
    )
    result = extract_post(_post(), ROSTER, "m")
    assert calls[0]["response_format"] is IgExtraction
    assert calls[1]["response_format"] == {"type": "json_object"}
    assert result["events"][0]["day"] == 12


def test_extract_post_reraises_when_json_mode_also_fails(monkeypatch):
    boom = litellm.exceptions.BadRequestError(message="no key", model="m", llm_provider="x")
    _fake_completion(monkeypatch, boom, boom)
    with pytest.raises(litellm.exceptions.BadRequestError):
        extract_post(_post(), ROSTER, "m")


def test_extract_post_tolerates_a_json_fenced_response(monkeypatch):
    _fake_completion(monkeypatch, "```json\n{\"events\": []}\n```")
    assert extract_post(_post(), ROSTER, "m") == {"events": []}


def test_prompt_version_is_an_int():
    assert isinstance(PROMPT_VERSION, int) and PROMPT_VERSION >= 1


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

def test_extracted_event_requires_at_least_one_content():
    with pytest.raises(Exception):
        ExtractedEvent(category="jazz", contents=[], confidence=0.9)


def test_extracted_event_defaults_every_optional_field_to_none():
    e = ExtractedEvent(
        category="jazz",
        contents=[ExtractedContent(lang="en", title="X")],
        confidence=0.5,
    )
    assert (e.venue_slug, e.day, e.month, e.year, e.time, e.price, e.language) == (
        None, None, None, None, None, None, None)


def test_ig_extraction_defaults_to_no_events():
    assert IgExtraction().events == []


# --------------------------------------------------------------------------
# gate_events
# --------------------------------------------------------------------------

TODAY = dt.date(2026, 8, 19)


def _gate(events, today=TODAY, threshold=0.75):
    return gate_events({"events": events}, today, threshold, label="mezzo ABC123")


def test_gate_keeps_a_well_formed_event_and_resolves_it():
    [g] = _gate([_event(day=12, month=9, year=2026, time="21:00")])
    assert isinstance(g, GatedEvent)
    assert g.date == dt.date(2026, 9, 12)
    assert g.time == dt.time(21, 0)
    assert g.venue_slug == "mezzo"
    assert g.category == "jazz"
    assert g.price == "5000֏"
    assert g.language == "non-verbal"
    assert g.confidence == 0.9


def test_gate_carries_the_index_of_the_event_in_the_stored_extraction():
    kept = _gate([
        _event(day=1, month=1, year=2026),   # 0: past, dropped
        _event(day=1, month=9, year=2026),   # 1: kept
        _event(day=2, month=9, confidence=0.1),  # 2: low confidence, dropped
        _event(day=3, month=9, year=2026),   # 3: kept
    ])
    assert [g.index for g in kept] == [1, 3]


def test_gate_keeps_contents_as_extracted_content_objects():
    [g] = _gate([_event(contents=[{"lang": "hy", "title": "Ջազ", "description": "երեկո"}])])
    assert [c.lang for c in g.contents] == ["hy"]
    assert g.contents[0].title == "Ջազ"


def test_gate_returns_nothing_for_an_empty_extraction():
    assert gate_events({"events": []}, TODAY, 0.75) == []
    assert gate_events({}, TODAY, 0.75) == []


# --- confidence ---

def test_gate_drops_below_threshold():
    assert _gate([_event(confidence=0.74)]) == []


def test_gate_keeps_exactly_at_threshold():
    assert len(_gate([_event(confidence=0.75)])) == 1


def test_gate_keeps_above_threshold():
    assert len(_gate([_event(confidence=0.751)])) == 1


def test_gate_threshold_is_a_parameter_not_a_constant():
    assert _gate([_event(confidence=0.5)], threshold=0.4)
    assert _gate([_event(confidence=0.5)], threshold=0.6) == []


# --- date completeness ---

def test_gate_drops_an_event_without_a_day():
    assert _gate([_event(day=None, month=9, year=2026)]) == []


def test_gate_drops_an_event_without_a_month():
    assert _gate([_event(day=12, month=None, year=2026)]) == []


def test_gate_drops_an_event_with_no_date_at_all():
    assert _gate([_event(day=None, month=None, year=None)]) == []


# --- year inference ---

def test_gate_infers_this_year_for_a_future_day_month():
    [g] = _gate([_event(day=1, month=12, year=None)])
    assert g.date == dt.date(2026, 12, 1)


def test_gate_infers_this_year_for_today_itself():
    [g] = _gate([_event(day=19, month=8, year=None)])
    assert g.date == dt.date(2026, 8, 19)


def test_gate_infers_next_year_for_a_day_month_already_past():
    [g] = _gate([_event(day=15, month=1, year=None)])
    assert g.date == dt.date(2027, 1, 15)


def test_gate_drops_yesterdays_day_month_rather_than_publishing_it_a_year_out():
    # A yearless "18 August" posted on the 19th infers to 2027-08-18, which
    # then falls outside the 6-month window — so it drops, as it should.
    assert _gate([_event(day=18, month=8, year=None)]) == []


def test_gate_keeps_a_stated_year_even_when_inference_would_disagree():
    [g] = _gate([_event(day=15, month=1, year=2027)])
    assert g.date == dt.date(2027, 1, 15)


def test_gate_drops_a_stated_past_year():
    assert _gate([_event(day=12, month=9, year=2025)]) == []


# --- window ---

def test_gate_keeps_the_near_edge_today():
    assert len(_gate([_event(day=19, month=8, year=2026)])) == 1


def test_gate_keeps_the_far_edge_exactly_six_months_out():
    assert len(_gate([_event(day=19, month=2, year=2027)])) == 1


def test_gate_drops_one_day_past_the_six_month_window():
    assert _gate([_event(day=20, month=2, year=2027)]) == []


def test_gate_drops_a_date_before_today():
    assert _gate([_event(day=18, month=8, year=2026)]) == []


def test_gate_six_month_window_clamps_to_a_short_month():
    # 2026-08-31 + 6 months has no 31st; the edge is 2027-02-28.
    today = dt.date(2026, 8, 31)
    assert len(_gate([_event(day=28, month=2, year=2027)], today=today)) == 1
    assert _gate([_event(day=1, month=3, year=2027)], today=today) == []


# --- invalid dates ---

def test_gate_drops_february_30_without_crashing():
    assert _gate([_event(day=30, month=2, year=2026)]) == []


def test_gate_drops_an_impossible_month():
    assert _gate([_event(day=1, month=13, year=2026)]) == []


def test_gate_drops_a_zero_day():
    assert _gate([_event(day=0, month=9, year=2026)]) == []


def test_gate_drops_february_29_of_a_non_leap_year_with_inference():
    assert _gate([_event(day=29, month=2, year=None)]) == []


# --- time parsing ---

def test_gate_parses_a_24h_time():
    [g] = _gate([_event(time="09:30")])
    assert g.time == dt.time(9, 30)


def test_gate_leaves_a_missing_time_as_none():
    [g] = _gate([_event(time=None)])
    assert g.time is None


def test_gate_keeps_the_event_but_drops_an_unparseable_time():
    [g] = _gate([_event(time="doors at nine")])
    assert g.time is None
    assert g.date == dt.date(2026, 9, 12)


# --- malformed events ---

def test_gate_drops_an_event_that_does_not_match_the_schema():
    assert _gate([{"category": "jazz"}]) == []


# --- logging ---

def test_gate_logs_every_drop_with_the_caller_label(caplog):
    with caplog.at_level("INFO", logger="cartelera.ig.extract"):
        _gate([_event(confidence=0.1), _event(day=None), _event(day=1, month=1, year=2020)])
    dropped = [r for r in caplog.records if "drop" in r.getMessage().lower()]
    assert len(dropped) == 3
    assert all("mezzo ABC123" in r.getMessage() for r in dropped)


def test_gate_logs_without_a_label(caplog):
    with caplog.at_level("INFO", logger="cartelera.ig.extract"):
        assert gate_events({"events": [_event(confidence=0.0)]}, TODAY, 0.75) == []
    assert any("drop" in r.getMessage().lower() for r in caplog.records)


# --------------------------------------------------------------------------
# config helpers
# --------------------------------------------------------------------------

def test_extract_model_defaults_to_gemini_flash():
    assert extract_model() == "gemini/gemini-2.5-flash"


def test_extract_model_is_configurable(monkeypatch):
    monkeypatch.setenv("IG_EXTRACT_MODEL", "anthropic/claude-haiku-4-5")
    assert extract_model() == "anthropic/claude-haiku-4-5"


def test_confidence_threshold_defaults_to_0_75():
    assert confidence_threshold() == 0.75


def test_confidence_threshold_is_configurable_and_cast_to_float(monkeypatch):
    monkeypatch.setenv("IG_CONFIDENCE_THRESHOLD", "0.9")
    value = confidence_threshold()
    assert value == 0.9 and isinstance(value, float)
