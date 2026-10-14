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

A source with `SourceDefinition.extends_venue_categories` (also jazzin) grows
its code-defined venues' categories from its feed (run._extend_categories,
seed.extend_venue_categories); the (venue, category) pairs a run adds are
reported the same way (`scrape_run.metrics["new_categories"]`, same issue).

That rolling review issue also lists venues of any multi-venue source that
have been degraded on their own for VENUE_REVIEW_STREAK+ runs
(health_ops.sync_degraded_venues, render_degraded_review).
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from cartelera.github import IssueTracker
from cartelera.health import VENUE_REVIEW_STREAK
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
    # Holds new venues (opt-out discovery) and long-degraded venues of any
    # multi-venue source.
    return f"{source_slug}: venues to review"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")  # "ITA | Internationaal Theater"


def _table(new_venues: list[dict]) -> str:
    rows = ["| venue | slug | address | categories | events |", "|---|---|---|---|---|"]
    for v in new_venues:
        rows.append(f"| {_cell(v['name'])} | `{v['slug']}` | {_cell(v.get('address') or '—')} | "
                    f"{', '.join(v.get('categories') or [])} | {v.get('events', 0)} |")
    return "\n".join(rows)


def _categories_table(new_categories: list[dict]) -> str:
    rows = ["| venue | slug | category | events |", "|---|---|---|---|"]
    for c in new_categories:
        rows.append(f"| {_cell(c['name'])} | `{c['slug']}` | {c['category']} | "
                    f"{c.get('events', 0)} |")
    return "\n".join(rows)


def render_review(source_slug: str, module: str | None, new_venues: list[dict],
                  today: dt.date, *, first: bool,
                  new_categories: list[dict] | None = None) -> str:
    path = f"scraper/src/cartelera/scrapers/{module or '<module>'}.py"
    parts: list[str] = []
    if new_venues:
        parts += [
            f"`{source_slug}` created {len(new_venues)} new venue(s) from its feed "
            f"on {today.isoformat()}. They are live (opt-out: unknown venue names become "
            "venues automatically).",
            _table(new_venues)]
    if new_categories:
        parts += [
            f"`{source_slug}` added {len(new_categories)} categor"
            f"{'y' if len(new_categories) == 1 else 'ies'} to code-defined venues on "
            f"{today.isoformat()}, from its feed's own categorization. They are live: "
            "each venue is now on that category's list (never removed automatically). "
            f"Fine as is → optionally add the category to the venue's `VENUES` row in "
            f"`{path}` so code matches; wrong → fix the feed mapping in code and remove "
            "the venue's category + list membership by hand.",
            _categories_table(new_categories)]
    if first and new_venues:
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


def render_degraded_review(source_slug: str, module: str | None, alerts: list[dict],
                           kind: str, *, first: bool) -> str:
    """The long-degraded-venues section. `alerts`: {slug, name, streak, rules:
    [detail]}; `kind`: health.plan_venue_review's "update" | "weekly" |
    "cleared"."""
    if kind == "cleared":
        return (f"No `{source_slug}` venue is degraded for {VENUE_REVIEW_STREAK}+ runs any "
                "more (recovered, acked, merged or denied).")
    path = f"scraper/src/cartelera/scrapers/{module or '<module>'}.py"
    head = {"weekly": "Still degraded (weekly reminder):"}.get(
        kind, f"Venues degraded on their own for {VENUE_REVIEW_STREAK}+ consecutive runs:")
    rows = ["| venue | slug | runs | rules |", "|---|---|---|---|"]
    for a in alerts:
        rows.append(f"| {_cell(a['name'])} | `{a['slug']}` | {a['streak']} | "
                    f"{_cell('; '.join(a['rules']))} |")
    parts = [head, "\n".join(rows),
             "These venues don't degrade the source; their events are kept as last seen "
             "and are neither missed nor hidden while they're degraded. For an aggregator "
             "this usually means the upstream feed lost them. **To decide**, per venue: "
             f"wait (it recovers by itself); **deny** / **merge** it (or drop it) in `{path}` "
             "if it shouldn't come from this source; or accept the new state (e.g. no programme any more) with "
             f"`cartelera health ack {source_slug} <slug>` — that makes this run its "
             "baseline and hides its upcoming events the run didn't see. "
             f"Details: `cartelera health {source_slug}`."]
    if first:
        parts.insert(0, f"Scraper health flagged venues of `{source_slug}`.")
    return "\n\n".join(parts)


def post_review(
    session: Session, source_slug: str, tracker: IssueTracker, first_body: str,
    comment_body: str,
) -> str:
    """Post to the source's rolling review issue: comment when one is open,
    else open one with `first_body`. Commits. Returns "opened" / "commented"."""
    sh = session.get(SourceHealth, source_slug) or SourceHealth(source_slug=source_slug)
    number = sh.review_issue_number
    if number is not None and tracker.is_open(number):
        tracker.comment(number, comment_body)
        action = "commented"
    else:
        sh.review_issue_number = tracker.open_issue(
            review_title(source_slug), first_body, [REVIEW_LABEL])
        action = "opened"
    session.add(sh)
    session.commit()
    return action


def sync_venue_review(
    session: Session, source_slug: str, module: str | None, new_venues: list[dict],
    tracker: IssueTracker, today: dt.date | None = None,
    new_categories: list[dict] | None = None,
) -> str | None:
    """Post a run's new venues and new venue categories to the source's
    rolling review issue: comment when one is open, else open one. Returns
    "opened" / "commented" / None (nothing new)."""
    if not new_venues and not new_categories:
        return None
    today = today or dt.date.today()
    return post_review(
        session, source_slug, tracker,
        render_review(source_slug, module, new_venues, today, first=True,
                      new_categories=new_categories),
        render_review(source_slug, module, new_venues, today, first=False,
                      new_categories=new_categories))
