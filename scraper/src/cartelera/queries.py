from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from cartelera.models import List, ListVenue, Event, event_category


def events_for_list(session: Session, list_slug: str, on_or_after: dt.date) -> list[Event]:
    """Events from a list's venues, applying each venue's optional category
    whitelist, from `on_or_after` onward, chronological."""
    lst = session.scalars(select(List).where(List.slug == list_slug)).one()
    memberships = session.scalars(select(ListVenue).where(ListVenue.list_id == lst.id)).all()

    results: dict[int, Event] = {}
    for m in memberships:
        q = select(Event).where(Event.venue_id == m.venue_id, Event.start_date >= on_or_after)
        if m.whitelist_category_id is not None:
            q = q.join(event_category, event_category.c.event_id == Event.id).where(
                event_category.c.category_id == m.whitelist_category_id)
        for ev in session.scalars(q).all():
            results[ev.id] = ev  # dedupe across overlapping memberships

    return sorted(results.values(), key=lambda e: (e.start_date, e.start_time or dt.time.min))
