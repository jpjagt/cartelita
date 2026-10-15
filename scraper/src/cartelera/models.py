from __future__ import annotations
import datetime as dt
from typing import Any
from sqlalchemy import (
    Text, Date, Time, DateTime, ForeignKey, Table, Column, UniqueConstraint, func,
    Integer, Boolean, Float,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


venue_category = Table(
    "venue_category", Base.metadata,
    Column("venue_id", ForeignKey("venue.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
)

event_category = Table(
    "event_category", Base.metadata,
    Column("event_id", ForeignKey("event.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class City(Base):
    __tablename__ = "city"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class Venue(Base):
    __tablename__ = "venue"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"))
    address: Mapped[str | None] = mapped_column(Text)
    site_url: Mapped[str | None] = mapped_column(Text)
    instagram_url: Mapped[str | None] = mapped_column(Text)
    # Coordinates for the Today map (migration 0008); NULL = unknown.
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    geocoded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # The source that created this venue at run time (an opt-out aggregator,
    # see cartelera.discovery); NULL for venues defined in code.
    discovered_by: Mapped[str | None] = mapped_column(Text)
    city: Mapped[City] = relationship()
    categories: Mapped[list[Category]] = relationship(secondary=venue_category)
    events: Mapped[list["Event"]] = relationship(back_populates="venue", passive_deletes=True)


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[dt.date] = mapped_column(Date)
    start_time: Mapped[dt.time | None] = mapped_column(Time)  # earliest session, for ordering
    start_times: Mapped[list[dt.time]] = mapped_column(ARRAY(Time), server_default="{}")
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    end_time: Mapped[dt.time | None] = mapped_column(Time)
    price: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    recurrence_hint: Mapped[str | None] = mapped_column(Text)
    # Display-only performance/source language ("VOSE", "hy", "non-verbal");
    # free text on the price convention, never parsed. NULL = unknown.
    language: Mapped[str | None] = mapped_column(Text)
    annotations: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    scraped_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Liveness (scraper health): stamped by every upsert; after a healthy run,
    # upcoming events the run missed count up and are hidden (never deleted) at
    # health.HIDE_AFTER_MISSES. Web queries filter `hidden_at IS NULL`.
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    missed_runs: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    hidden_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    venue: Mapped[Venue] = relationship(back_populates="events")
    categories: Mapped[list[Category]] = relationship(secondary=event_category)
    translations: Mapped[list["EventTranslation"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True)


class EventTranslation(Base):
    __tablename__ = "event_translation"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    lang: Mapped[str] = mapped_column(Text)        # 'ca' / 'es' / 'en'
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    event: Mapped[Event] = relationship(back_populates="translations")


class List(Base):
    __tablename__ = "list"
    # Slugs are unique PER CITY, not globally: every city has its own "jazz".
    __table_args__ = (UniqueConstraint("city_id", "slug", name="list_city_slug_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text, default="cartelera")
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"))
    city: Mapped[City] = relationship()


class ListVenue(Base):
    __tablename__ = "list_venue"
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("list.id", ondelete="CASCADE"))
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id", ondelete="CASCADE"))
    whitelist_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="CASCADE")
    )


class ScrapeRun(Base):
    """One row per source per `cartelera run` (see cartelera.health)."""
    __tablename__ = "scrape_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_slug: Mapped[str] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    verdict: Mapped[str] = mapped_column(Text)  # healthy | degraded | broken | site_down
    error_kind: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    # {"source": {...}, "venues": {slug: {..., "verdict"}}, "degraded_venues":
    # [slug], "fired": [{...}], "acked_venues": [slug] (health ack <source>
    # <venue>)}; NULL when the scrape raised (no metrics to record).
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    acked: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)


class SourceHealth(Base):
    """Per-source GitHub issue bookkeeping (one open issue per source)."""
    __tablename__ = "source_health"
    source_slug: Mapped[str] = mapped_column(Text, primary_key=True)
    issue_number: Mapped[int | None] = mapped_column(Integer)
    issue_kind: Mapped[str | None] = mapped_column(Text)
    last_comment_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_signature: Mapped[str | None] = mapped_column(Text)
    # The rolling "venues to review" issue (new discovered + long-degraded venues).
    review_issue_number: Mapped[int | None] = mapped_column(Integer)
    # Long-degraded venues listed on that review issue: what was last posted
    # (health.venue_review_signature) and when (comment-on-change, weekly cap).
    venue_review_signature: Mapped[str | None] = mapped_column(Text)
    venue_review_comment_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
