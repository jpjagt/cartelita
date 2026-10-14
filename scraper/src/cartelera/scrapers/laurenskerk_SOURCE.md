# laurenskerk — Laurenskerk Rotterdam

Medieval city church; organ concerts, resident choir/orchestra (Laurens
Vocaal), visiting ensembles. WordPress (domain moved to laurenskerk.nl;
laurenskerkrotterdam.nl redirects), plain httpx.

## Data source

- List: `https://laurenskerk.nl/agenda/` → `.event-item` cards (date, title,
  tagline `.event-item__editor`, image `img[data-lazy-src]`, link to
  `/evenement/<slug>/`); pagination `nav.pagination a.next` (`?pagination=N`,
  ~3 pages, ~40 events). Category filter tabs exist (`?category=<slug>`) but we
  read categories from the detail page instead.
- Detail (one GET per event): `.event-single__sidebar`
  - date `.event-single__date span` ("zondag 18 oktober 2026", typos like
    "october", "november2026" handled; multiple dates → one event per date)
  - time `.event-single__time span` lines: door/walk-in times ("Deur open",
    "inloop", "kerk open") ignored; "tot HH:MM" = end time; two "Aanvang"
    times → `start_times`
  - price `.event-single__price span` lines: skip Vrienden / t/m 26 / tot 30 /
    korting tiers; "ipv € 90" (regular price behind an early-bird) → `90€`;
    "Toegang is vrij" → `free`; "Pay what you can"; early-bird-only → None
  - ticket button `.event-single__sidebar a.button`
  - categories `.event-single__categories a`
- external_id: `<slug>@<date>T<HHMM>`; category: classical.

## Curation (venue's own categories + ticketing structure)

Kept: events in the church's own programme lines **Orgelconcerten**,
**Laurenskerk Invites**, **Laurens Vocaal**, and **Concerten** events ticketed
by the church's own shop (tickets.laurenskerkrotterdam.nl) or by the
performing ensemble/producer's own site (RPhO, Laurens Vocaal, the Bach Choir
& Orchestra productions).

Excluded:
- **Church services**: "Herdenken en vieren" category, or a detail page
  crediting a *voorganger* (officiant) — the monthly Cantatedienst (Bach
  cantata within a service) is filed under Laurens Vocaal but is a service.
- **Hired-in franchises/tours** in "Concerten" ticketed through a generic
  ticket platform (feverup.com = Candlelight series; mticket.eu = pop tour;
  ticketmatic = tribute band; stager.co = Ligconcert; ticketmaster/eventbrite).
- **Non-music categories**: Ademruimte (yoga) unless also Orgelconcerten,
  Overig (roller disco, Halloween party, record fair, award ceremonies, winter
  terraces), Tentoonstellingen.

Last verified: 2026-10-14 via HTTP cross-check (independent read of each kept
event's detail sidebar text vs scraper output: dates, start/end times and
prices agree for the first 8 events). Live run: 13 events kept of 39
(2026-10-15 → 2027-05-22); time 13/13, price 8/13 (the rest state only an
early-bird price or "verkoop nog niet gestart").
