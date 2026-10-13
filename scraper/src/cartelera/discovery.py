"""Venues a source discovers at run time — the OPT-OUT aggregator model.

Most multi-venue sources are opt-in: their SourceDefinition's venue list is the
editorial whitelist. An opt-out source (today only jazzin.amsterdam) also
implements `scrapers.base.DiscoversVenues`: every venue its feed names that
code neither overrides nor denies becomes a venue automatically. The runner
(`run._write_source`) then:

1. refuses discovered slugs something else already owns — a code-defined venue
   of any source (REGISTRY), or a DB venue not created by this source — and
   skips their events with a warning (deny or merge that name deliberately);
2. creates/grows the rest in the run's transaction (seed.upsert_discovered_venue);
3. treats every venue the source created (`venue.discovered_by`) as one of its
   venues for metrics, miss counting/hiding and `health ack`;
4. reports the venues created for the first time: in the run output, in
   `scrape_run.metrics["new_venues"]`, and on one rolling GitHub issue per
   source (label `venue-review`) — see sync_venue_review.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from cartelera.github import IssueTracker
from cartelera.models import SourceHealth, Venue
from cartelera.scrapers import load_all
from cartelera.types import SourceDefinition, VenueDefinition

logger = logging.getLogger(__name__)

REVIEW_LABEL = "venue-review"


def accept_discovered(
    session: Session, source: SourceDefinition, discovered: list[VenueDefinition]
) -> tuple[list[VenueDefinition], dict[str, str]]:
    """Split discovered venues into (accepted, {refused slug: why})."""
    owners = {v.slug: slug for slug, (_s, src) in load_all().items() for v in src.venues}
    by_slug = {
        v.slug: v for v in session.scalars(
            select(Venue).where(Venue.slug.in_([d.slug for d in discovered])))
    }
    accepted: list[VenueDefinition] = []
    refused: dict[str, str] = {}
    for d in discovered:
        if d.slug in owners:
            refused[d.slug] = (f"{d.name!r}: slug {d.slug!r} is a code-defined venue of "
                               f"source {owners[d.slug]!r}")
        elif (v := by_slug.get(d.slug)) is not None and v.discovered_by != source.slug:
            refused[d.slug] = (f"{d.name!r}: slug {d.slug!r} is an existing venue "
                               f"({v.name!r}) not discovered by {source.slug!r}")
        else:
            accepted.append(d)
    return accepted, refused


def source_venue_slugs(session: Session, source: SourceDefinition) -> list[str]:
    """The source's code-defined venues, then every venue it discovered (in any
    run, so including ones absent from the latest feed)."""
    slugs = [v.slug for v in source.venues]
    known = set(slugs)
    for slug in session.scalars(
            select(Venue.slug).where(Venue.discovered_by == source.slug).order_by(Venue.slug)):
        if slug not in known:
            slugs.append(slug)
            known.add(slug)
    return slugs


# --- review issue -------------------------------------------------------------------

def review_title(source_slug: str) -> str:
    return f"{source_slug}: new venues to review"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")  # "ITA | Internationaal Theater"


def _table(new_venues: list[dict]) -> str:
    rows = ["| venue | slug | address | categories | events |", "|---|---|---|---|---|"]
    for v in new_venues:
        rows.append(f"| {_cell(v['name'])} | `{v['slug']}` | {_cell(v.get('address') or '—')} | "
                    f"{', '.join(v.get('categories') or [])} | {v.get('events', 0)} |")
    return "\n".join(rows)


def render_review(source_slug: str, module: str | None, new_venues: list[dict],
                  today: dt.date, *, first: bool) -> str:
    path = f"scraper/src/cartelera/scrapers/{module or '<module>'}.py"
    head = (f"`{source_slug}` created {len(new_venues)} new venue(s) from its feed "
            f"on {today.isoformat()}. They are live (opt-out: unknown venue names become "
            "venues automatically).")
    parts = [head, _table(new_venues)]
    if first:
        parts.append(
            "**To review** each one, in `" + path + "`:\n\n"
            "- fine as is → nothing to do;\n"
            "- a spelling variant of a known venue → **merge**: add the feed's name to "
            "that venue's aliases in `VENUES` (add a `VENUES` row to override a name, "
            "address or categories);\n"
            "- not a venue / outside the region / owned by another scraper → **deny**: "
            "add the name with its reason to `DENIED`.\n\n"
            "After a merge or deny the auto-created venue gets no new events, and its "
            "upcoming ones are hidden after 3 healthy runs; its row stays (remove it by "
            "hand: `DELETE FROM venue WHERE slug = '<slug>'`). New batches are added "
            "here as comments; close this issue once reviewed — the next batch opens "
            "a new one.")
    return "\n\n".join(parts)


def sync_venue_review(
    session: Session, source_slug: str, module: str | None, new_venues: list[dict],
    tracker: IssueTracker, today: dt.date | None = None,
) -> str | None:
    """Post a run's new venues to the source's rolling review issue: comment
    when one is open, else open one. Returns "opened" / "commented" / None."""
    if not new_venues:
        return None
    today = today or dt.date.today()
    sh = session.get(SourceHealth, source_slug) or SourceHealth(source_slug=source_slug)
    number = sh.review_issue_number
    if number is not None and tracker.is_open(number):
        tracker.comment(number, render_review(source_slug, module, new_venues, today, first=False))
        action = "commented"
    else:
        sh.review_issue_number = tracker.open_issue(
            review_title(source_slug),
            render_review(source_slug, module, new_venues, today, first=True),
            [REVIEW_LABEL])
        action = "opened"
    session.add(sh)
    session.commit()
    return action
