from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    Text, Date, Time, DateTime, Integer, ForeignKey, Table, Column, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, BYTEA
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


class IgPost(Base):
    """One row per Instagram post ever captured, keyed by shortcode.

    Invariants: capture is append-only — an archived post's raw columns
    (caption/posted_at/images) are never modified after insert, a captured
    post is immutable history. The extraction columns (extraction/model_id/
    prompt_version/extracted_at) stay NULL until an LLM parses the post, and
    in production a post is parsed at most once ever: prompt_version records
    which prompt produced the extraction (provenance), it is not a cache key
    that triggers re-extraction when bumped.
    """
    __tablename__ = "ig_post"
    shortcode: Mapped[str] = mapped_column(Text, primary_key=True)
    source_slug: Mapped[str] = mapped_column(Text)
    handle: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extraction: Mapped[dict | None] = mapped_column(JSONB)
    model_id: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    extracted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    images: Mapped[list["IgPostImage"]] = relationship(
        back_populates="post", order_by="IgPostImage.idx",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class IgPostImage(Base):
    __tablename__ = "ig_post_image"
    shortcode: Mapped[str] = mapped_column(
        Text, ForeignKey("ig_post.shortcode", ondelete="CASCADE"), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text)  # CDN URL the image was downloaded from
    content_type: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(BYTEA)
    post: Mapped[IgPost] = relationship(back_populates="images")


class IgSession(Base):
    """Single-row (id=1) storage of the Playwright login session state."""
    __tablename__ = "ig_session"
    id: Mapped[int] = mapped_column(primary_key=True)
    storage_state: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
