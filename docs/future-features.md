# Cartelera — Future Features

A living record of directions we are **built toward but have deliberately not
built**. This is not a committed roadmap; it is a polestar-adjacent list that
keeps the MVP honest about what its foundations should not preclude. See
[`MANIFESTO.md`](../MANIFESTO.md) for the philosophy these serve.

Each item notes *why it's deferred* and *what foundation already supports it*, so
we resist building it early but don't accidentally design it out.

## Personalization (account-free)

- **Favorites + "my list"** — favorite venues (localStorage, no backend), and a
  "my list" view showing only their events.
  - *Deferred because:* only useful once there are enough venues that filtering
    to favorites matters. With a small curated launch set, every category list is
    already short and browsable.
  - *Foundation:* "my list" is just a list with no category whitelist; the list
    primitive already supports it.

## User / curator / group curation

- **User-authored lists** — anyone can create a curated venue-list (the shared
  Google-Maps-list habit: "nice places in Gràcia").
- **Trusted human curators** — tastemakers (cincentims-style), critics, venue
  programmers as *authors* whose lists Cartelera chooses to surface. A
  content-acquisition strategy: we don't have to hold all the taste ourselves.
- **Bluesky-style composable curation** — subscribe to others' lists; curation as
  a swappable layer, not a single central authority.
  - *Deferred because:* requires accounts, identity, and a real product surface;
    unproven demand beyond the MVP's single `cartelera` author.
  - *Foundation:* lists already have an `author` field; the only MVP author is
    `cartelera`. Author can later be a person, curator, or group.

## Social / belonging

- **Group cultural agenda** — a shared venue-list for a friend group, possibly
  with per-event annotations. The "replace the group chat with a shared agenda"
  idea.
  - *Deferred — and treated cautiously, not just later.* Likes/comment-threads
    are feed mechanics that directly fight Manifesto Principle 1 (the real world
    over the feed) and risk turning the product into another reason to stay on
    your phone. If ever built, it must be designed to *reduce* phone time (a
    planning artifact you consult and leave, not a chat you live in).
  - *Foundation:* reachable via group-authored lists + (future) list-item
    annotations, **without** any like/comment/notification machinery, which we
    explicitly refuse to design in now.
- **Social signals** — "I'm going [alone / with friends]" with a counter, lowering
  the stakes of going out alone (Principle 5).
  - *Deferred because:* needs identity and a social surface.

## Occurrence grouping (series)

- **`series_key` / `series` table** — link the occurrence rows of a recurring
  night or a multi-edition cycle so they can be grouped, and so a cycle can carry
  its own identity (title, description, image).
  - *Deferred because:* the MVP display is purely per-occurrence and date-driven;
    a nullable `recurrence_hint` text label covers the only UI need (marking that
    an event recurs). Grouping earns its place only when cycles need shared
    identity or "see all dates of this series" views.
  - *Foundation:* events are already flat per-occurrence rows; a `series_key`
    column (then a `series` fk) can be added without reshaping existing data.

## Hardware / ambient triggers

- **The beacon** — alternative hardware you subscribe to venues through; it
  pushes a signal when something is happening *now*, prompting you to step
  outside. The long-term, world-changing bet.
  - *Deferred because:* far-horizon; a hardware product, not a web feature.
  - *Foundation:* venue-first model and the "tonight/now" default view are the
    software ancestors of this trigger.

## Scale & infrastructure

- **Multi-city expansion** — beyond Barcelona.
  - *Foundation:* city is already a scoping layer; Barcelona is not hardcoded.
- **Standalone API** — a real read/write API service.
  - *Deferred because:* nothing at MVP needs request-time dynamic reads.
  - *Foundation:* documented extension point; frontend currently reads Postgres
    server-side at regeneration time.
- **LLM categorization-filter layer** — for genuinely ambiguous multi-category
  sources, beyond per-venue rules/heuristics.
  - *Deferred because:* single-category auto-tagging + per-venue scraper rules
    cover launch needs.
  - *Foundation:* categorization already lives inside each venue's scraper; a
    scraper can graduate to LLM classification without changing the data model.
- **Autonomous scraper auto-repair** — fully automated LLM detect-fix-deploy.
  - *Deferred because:* an LLM silently rewriting scrapers and deploying data
    erodes the trust Principle 3 depends on. The chosen flow is human-in-the-loop,
    agent-assisted (automated detection + notification, human-triggered
    agent-authored fix, normal git deploy).
  - *Foundation:* scraper service is repair-flow-ready (isolation, structured
    reporting, isolated local/prod runs) without coupling to a repair workflow.
