"""IG extraction: one vision-LLM call per post, then a publish gate.

Two independent halves, deliberately kept apart:

- **The call** (`build_messages`, `extract_post`) — provider-independent via
  litellm; the model is *always* a config string, never hardcoded, and no
  provider SDK is imported here. Its output is validated against the pydantic
  schema below and stored verbatim (`archive.save_extraction`). A post is
  parsed at most once, ever: `PROMPT_VERSION` is provenance, not a cache key.
- **The gate** (`gate_events`) — a pure function over an already-stored
  extraction, run at *emission* time, every night, over every cached
  extraction. It resolves dates, applies the confidence threshold and drops
  (loudly, to the log) anything we would rather not publish. It is not part of
  the stored extraction, so its rules can change without re-parsing anything.

litellm is imported inside the functions that need it: importing it costs
seconds, and the gate — the half that runs on every emission — needs none of
it.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import re
from dataclasses import dataclass

from decouple import config
from pydantic import BaseModel, Field, ValidationError

from cartelera.ig.types import RosterVenue
from cartelera.models import IgPost

logger = logging.getLogger(__name__)

# Provenance stamp for the prompt that produced an extraction. Bumping it does
# NOT trigger re-extraction (see archive.save_extraction).
PROMPT_VERSION = 1

# How far ahead a resolved date may land to be publishable.
WINDOW_MONTHS = 6


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def extract_model() -> str:
    """The litellm model string, e.g. `gemini/gemini-2.5-flash`."""
    return config("IG_EXTRACT_MODEL", default="gemini/gemini-2.5-flash")


def confidence_threshold() -> float:
    """Minimum per-event confidence for an extracted event to be published."""
    return config("IG_CONFIDENCE_THRESHOLD", default=0.75, cast=float)


# --------------------------------------------------------------------------
# output schema
# --------------------------------------------------------------------------

class ExtractedContent(BaseModel):
    """The event's text in ONE language, as the post itself carries it."""
    lang: str  # ISO-ish code of the language this text is written in
    title: str
    description: str | None = None


class ExtractedEvent(BaseModel):
    venue_slug: str | None = None  # from the roster; None only for single-venue rosters
    category: str  # from that venue's allowed categories
    # One entry per language the POST carries the event in — extraction, never
    # translation. At least one.
    contents: list[ExtractedContent] = Field(min_length=1)
    # Exactly as stated on the flyer/caption; never inferred.
    day: int | None = None
    month: int | None = None
    year: int | None = None
    time: str | None = None  # "HH:MM", 24h
    price: str | None = None  # display string, free text ("free", "5000֏")
    language: str | None = None  # PERFORMANCE language, display-only, unrelated to contents[].lang
    confidence: float  # 0..1, the model's certainty this is a real, correctly-read event


class IgExtraction(BaseModel):
    # Empty = the post is not an event announcement.
    events: list[ExtractedEvent] = Field(default_factory=list)


class ExtractionError(RuntimeError):
    """The model's reply was not valid JSON matching IgExtraction."""


# --------------------------------------------------------------------------
# the LLM call
# --------------------------------------------------------------------------

_INSTRUCTIONS = """\
You extract events from Instagram posts published by or about a small roster \
of venues in a city guide. Captions and flyer images are often in Armenian or \
Russian, sometimes with an English version in the same caption. Read the \
caption AND every image: the date, time and price usually live on the flyer, \
not in the text.

The venue roster (pick `venue_slug` from these slugs, and `category` from that \
venue's allowed categories — never invent either):

{roster}

Rules:
- Return one entry in `events` per real, upcoming event. A weekly line-up post \
announces several events: emit one event per date, not one per post.
- If the post is not an event announcement (a photo recap, a greeting, a \
promotion), return an empty `events` list.
- Never invent a date, time or price. A field that is not visibly stated is \
null. In particular: do not guess a year that is not written down, and do not \
assume a price when none is shown. Use `price` only for what the post states \
("free" only when it explicitly says the event is free).
- `time` is "HH:MM" in 24-hour form.
- `contents` is multi-language EXTRACTION, not translation: add one entry per \
language the post itself writes the event in, each with that language's own \
title and description as written. If the post is in one language only, return \
exactly one entry. Never translate text the post does not contain.
- `language` is the language of the PERFORMANCE (e.g. "hy", "ru", \
"non-verbal") and only when the post says so. It is unrelated to \
`contents[].lang`.
- `confidence` is your overall certainty, from 0 to 1, that this is a real \
upcoming event at this venue and that you read its details correctly. Be \
honest: a blurry flyer with an ambiguous date is low confidence.

Reply with JSON matching the given schema and nothing else."""


def _render_roster(roster: list[RosterVenue]) -> str:
    lines = []
    for venue in roster:
        line = f"- {venue.slug}: {venue.name} (categories: {', '.join(venue.category_slugs)})"
        if venue.hints:
            line += f" — {venue.hints}"
        lines.append(line)
    return "\n".join(lines)


def _data_url(content_type: str, data: bytes) -> str:
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"


def build_messages(post: IgPost, roster: list[RosterVenue]) -> list[dict]:
    """One multimodal user message: instructions, the caption, every image.

    Everything goes in a single user message rather than a system+user pair:
    it is the shape every provider litellm fronts handles identically."""
    content: list[dict] = [
        {"type": "text", "text": _INSTRUCTIONS.format(roster=_render_roster(roster))},
    ]
    if post.caption:
        content.append({"type": "text", "text": f"Post caption:\n{post.caption}"})
    else:
        content.append({"type": "text", "text": "Post caption: (none)"})
    for image in post.images:  # ordered as posted
        content.append({
            "type": "image_url",
            "image_url": {"url": _data_url(image.content_type, image.data)},
        })
    return [{"role": "user", "content": content}]


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _parse(text: str | None) -> IgExtraction:
    """Validate a model reply, raising ExtractionError with a message the model
    can act on when it doesn't hold up."""
    if not text:
        raise ExtractionError("the reply was empty")
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise ExtractionError(f"the reply was not valid JSON: {err}") from err
    try:
        return IgExtraction.model_validate(payload)
    except ValidationError as err:
        raise ExtractionError(f"the JSON did not match the schema: {err}") from err


def _completion(model: str, messages: list[dict]):
    """One litellm call, schema-forced, with a JSON-mode fallback.

    litellm takes a pydantic model as `response_format` and translates it to
    whatever the provider supports. Providers that reject that outright get
    one retry in plain JSON mode — the reply is validated against the schema
    either way, so the only thing lost is the provider-side guarantee."""
    import litellm  # heavy import; only the call half needs it

    try:
        return litellm.completion(model=model, messages=messages, response_format=IgExtraction)
    except Exception as err:
        logger.warning(
            "%s rejected the schema response_format (%s); retrying in JSON mode", model, err
        )
        return litellm.completion(
            model=model, messages=messages, response_format={"type": "json_object"}
        )


def _complete_and_parse(model: str, messages: list[dict]) -> IgExtraction:
    response = _completion(model, messages)
    return _parse(response.choices[0].message.content)


def extract_post(post: IgPost, roster: list[RosterVenue], model: str) -> dict:
    """Parse one archived post into a stored extraction dict.

    Exactly one retry — with the validation error handed back to the model —
    before giving up. Returns `IgExtraction.model_dump()`, which is what
    `archive.save_extraction` writes to the `extraction` JSONB column."""
    messages = build_messages(post, roster)
    try:
        extraction = _complete_and_parse(model, messages)
    except ExtractionError as err:
        logger.warning("ig extraction for %s was invalid (%s); retrying once", post.shortcode, err)
        retry = messages + [{
            "role": "user",
            "content": (
                f"Your previous reply was rejected: {err}\n"
                "Reply again with JSON matching the schema and nothing else."
            ),
        }]
        extraction = _complete_and_parse(model, retry)
    return extraction.model_dump()


# --------------------------------------------------------------------------
# the publish gate
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GatedEvent:
    """An extracted event that passed the gate, with its date resolved.

    `index` is the event's position in the stored extraction's `events` list:
    together with the post's shortcode it is what makes a stable
    `external_id`, so it must survive the gate even though dropped siblings
    do not."""
    index: int
    venue_slug: str | None
    category: str
    contents: list[ExtractedContent]
    date: dt.date
    time: dt.time | None
    price: str | None
    language: str | None
    confidence: float


def _make_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except (ValueError, OverflowError):
        return None


def _resolve_date(event: ExtractedEvent, today: dt.date) -> dt.date | None:
    """Nearest-future year inference; a stated year is always kept as stated."""
    if event.day is None or event.month is None:
        return None
    if event.year is not None:
        return _make_date(event.year, event.month, event.day)
    this_year = _make_date(today.year, event.month, event.day)
    if this_year is not None and this_year >= today:
        return this_year
    return _make_date(today.year + 1, event.month, event.day)


def _window_end(today: dt.date) -> dt.date:
    """`today` + WINDOW_MONTHS, clamped to the last day of the target month."""
    month_index = today.month - 1 + WINDOW_MONTHS
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    day = today.day
    while (end := _make_date(year, month, day)) is None:
        day -= 1
    return end


_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def _parse_time(raw: str | None) -> dt.time | None:
    if not raw:
        return None
    match = _TIME_RE.match(raw)
    if not match:
        return None
    try:
        return dt.time(int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def gate_events(
    extraction: dict, today: dt.date, threshold: float, label: str = ""
) -> list[GatedEvent]:
    """Filter a stored extraction down to what we are willing to publish.

    Pure: no DB, no clock, no config — `today` and `threshold` are passed in so
    the caller (the nightly emission) fully determines the outcome. Silence
    over noise: every drop is logged at INFO with `label` prefixed, so a run
    log shows publishes and drops side by side."""
    prefix = f"{label}: " if label else ""
    kept: list[GatedEvent] = []
    for index, raw in enumerate(extraction.get("events") or []):
        try:
            event = ExtractedEvent.model_validate(raw)
        except ValidationError as err:
            logger.info("%sdrop event %d: does not match the schema (%s)", prefix, index, err)
            continue

        if event.confidence < threshold:
            logger.info(
                "%sdrop event %d: confidence %.2f < %.2f", prefix, index, event.confidence, threshold
            )
            continue

        date = _resolve_date(event, today)
        if date is None:
            logger.info(
                "%sdrop event %d: unresolvable date (day=%s month=%s year=%s)",
                prefix, index, event.day, event.month, event.year,
            )
            continue

        end = _window_end(today)
        if not (today <= date <= end):
            logger.info(
                "%sdrop event %d: %s is outside the publish window [%s, %s]",
                prefix, index, date, today, end,
            )
            continue

        time = _parse_time(event.time)
        if event.time and time is None:
            # Not worth dropping an otherwise good event over; the time is
            # display-only and the date is what places it on the calendar.
            logger.info("%sevent %d: unparseable time %r, kept without one", prefix, index, event.time)

        kept.append(GatedEvent(
            index=index,
            venue_slug=event.venue_slug,
            category=event.category,
            contents=event.contents,
            date=date,
            time=time,
            price=event.price,
            language=event.language,
            confidence=event.confidence,
        ))
    return kept
