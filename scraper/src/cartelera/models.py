from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    Text, Date, Time, DateTime, ForeignKey, Table, Column, func,
)
from sqlalchemy.dialects.postgresql import ARRAY
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
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
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
