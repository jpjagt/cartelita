# Komitas Chamber Music House — source map

last verified: 2026-08-18 (verified via HTTP fetch — browser session request needed
manual approval to attach to the user's real Chrome, declined per instructions;
confirmed instead with direct `httpx` fetches of the live pages)

## Venue
- slug: `komitas-chamber-hall`
- name: Komitas Chamber Music House
- city: yerevan
- address: 1 Isahakyan St, Yerevan — 300-seat chamber hall with a Baroque organ,
  operated by the National Center for Chamber Music SNCO.
- site: the venue has no independent website; its programme is ticketed
  through **toms.am** (Impresario Productions' Armenian ticketing platform,
  also seen as tomsarkgh.am).

## Why toms.am

toms.am runs a dedicated venue ("place") page listing every upcoming event at
Komitas Chamber Music House, in two languages (`am` = Armenian, `en` =
English — no `ru`). Each listing links to a per-event "ticket" detail page
that additionally exposes the *exact* scheduled date/time via a `<select
id="id_samo">` of ticketable sessions. This is the only structured,
per-occurrence listing found for the venue (recon by a prior agent; this pass
picked up from its saved fixtures — no venue-native or aggregator alternative
was pursued since the toms.am page already covers every field needed).

## List URLs (one page per language, no pagination — the "MOST IMPORTANT"
## slideshow at the top of the page is a **site-wide** promo carousel across
## ALL venues and must be ignored; only `.ticked_block` divs inside `.div_cont`
## are this venue's own listing, confirmed by their `.ticked_links` second
## `<a>` always reading "Komitas Chamber Music House"/"Կոմիտասի ...")

- Armenian (**canonical** — `hy` is Yerevan's default locale, see
  `web/src/lib/cities.ts`): `https://www.toms.am/am/place/Komitas+Chamber+Music+House`
- English (translation): `https://www.toms.am/en/place/Komitas+Chamber+Music+House`

## Per-event fields (place page, `.ticked_block`)
- **title** ← `.ticked_title` text.
- **category label** (WHAT taxonomy, e.g. "Concert, Festival, Contest" /
  "Play or Event for Kids and Teens") ← first `<a>` inside `.ticked_links`.
  Not used for `category_slugs` (this venue is single-category per the task
  brief) — kept as an `annotations` entry instead.
- **date** ← first line of `.ticked_date` (`YYYY-MM-DD`). Used only as a
  **fallback** when the ticket detail page's schedule can't be fetched/parsed
  (see below — the detail page is the authoritative time source).
- **price (raw)** ← second line of `.ticked_date`, e.g. `"Price 3000, 4000,
  5000 AMD"` (en) / `"Տոմսերի արժեքը` 3000, 4000, 5000 դրամ"` (am). All digit
  runs are extracted with a regex (language-agnostic) and reduced to the
  project's price convention by hand (see below — NOT the euro `format_eur_range`
  helper, since these are AMD, not EUR).
- **description** ← `.ticked_desc` text, with the trailing `.ticked_order`
  ("ORDER TICKETS" / "ՊԱՏՎԻՐԵԼ ՏՈՄՍ") link stripped before extracting text (that
  link only appears in the listing-page markup, not on the ticket detail page).
- **image_url** ← first `<img src>` inside `.ticked_desc`.
- **ticket id** ← the numeric id in the `.ticked_order a[href]` URL
  (`/ticket/{id}`). Stable across languages (same numeric id under `/am/` and
  `/en/`) — used to match an event across the two language pages and to build
  the ticket detail page URL.

## Per-event fields (ticket detail page, `/{lang}/ticket/{id}`)
The detail page repeats the same `.ticked_block` (title/date/price/description
match the listing) but its purpose here is solely the **authoritative
schedule**: a `<select id="id_samo" class="id_schedule">` with one `<option
value="{schedule_id}">{YYYY-MM-DD HH:MM}</option>` per sellable session.

**This is the source of `start_date`/`start_time`, not the free-text "Time:
HH:MM." sentence embedded in the description.** Cross-checked on ticket 5904
("Gurdjieff and Armenian Medieval Sacred and Ritual Music"): the description
prose says "Time: 19:00." but the schedule select says `2026-09-04 19:30` — the
box-office system's real start time is 30 minutes later than the announced
text. The schedule select is the box-office system of record, so it wins.

`external_id` ← `komitas-schedule-{schedule_id}` (the schedule id is already a
stable per-occurrence primary key issued by toms.am's booking system — no need
to hand-qualify with date+time). If a ticket's detail page can't be fetched or
its schedule select is empty/unparseable, fall back to the listing page's date
with `external_id = komitas-ticket-{ticket_id}@{date}` and `start_time = None`.

Both fixture ticket pages (5713, 5904) carry exactly one `<option>`; the
scraper handles multiple (a ticket with several sellable sessions) by emitting
one `ScrapedEvent` per option, all sharing the same title/description/price/
translations.

## Category rule
Fixed: every event is `category_slugs=["classical"]` (per the task brief — this
is a single-purpose classical/chamber-music hall). The site's own WHAT
taxonomy is not a genre split we need; it's preserved as an `annotations` entry
instead (Armenian label, canonical-language convention, matching how other
scrapers keep genre tags in the canonical language — see `liceu.py`).

## Price
AMD, free text, hand-formatted (not `cartelera.scrapers.price.format_eur_range`,
which is EUR-specific). Extract all digit-runs (≥3 digits, to skip stray
values) from the raw price text; let `lo`/`hi` be their min/max:
- `hi >= 2 * lo` → range `"{lo}–{hi} AMD"` (matches the task's own example,
  `"2000–5000 AMD"`, produced by the piano-recital event's tiers
  2000/3000/4000/5000).
- otherwise → the single highest tier, `"{hi} AMD"`.
- no digits found → `None` (no free/sold-out wording observed in the fixtures;
  not implemented since untested — would need re-recon if it appears).

## Translations
Canonical = Armenian (`hy`; Yerevan's default locale — matches
`malkhas_jazz_club.py`'s convention, even though the *URL* path segment is
`am`, not `hy`). One `en` translation per event when the English listing has a
matching ticket id, with its own title/description/`source_url` (the English
ticket page). `language` (the display field, e.g. "VOSE"/"non-verbal") is
always `None` — the source never states a performance language, and per the
task brief this is instrumental music, so it should never be inferred.

## Quirks
- The listing page's slideshow at the top ("MOST IMPORTANT") is NOT
  venue-scoped — it mixes events from every toms.am venue. Only `.div_cont
  .ticked_block` is this venue's actual programme.
- No pagination on the place page; it appears to show the full upcoming
  programme (9 events on both language fixtures, 2026-09-04 through 2026-09-26).
- Browser automation could not be used this pass (would have attached to the
  user's live Chrome and needed manual approval, which was declined per
  instructions); verification instead re-fetched the live place pages and one
  live ticket page via `httpx` and diffed field-by-field against the scraper's
  parsed output.

## Verification (2026-08-18)
Browser automation was not usable this pass: `browser-use` on this machine is
CLI v3.0, which dropped `--session`-based isolated sessions entirely (local
runs now share one default daemon) — incompatible with the skill's
per-venue-session requirement and risks colliding with sibling agents' tabs.
Per instructions, verified instead with direct `httpx` fetches of the live
pages, comparing the scraper's parsed output against the raw HTML field by
field.

Live `KomitasChamberHallScraper().scrape()` (2026-08-18): **9 events**, all
09-04 through 09-26 2026. Coverage: price 9/9 (100%), start_time 9/9 (100%,
all resolved via the authoritative schedule select — none fell back to the
bare listing date), image_url 9/9, description 9/9, annotations 9/9,
en translation 9/9. Cross-checked `parse_place()` against a fresh live fetch
of the English place page: all 9 (ticket_id, title, date, raw price text)
tuples matched the scraper's merged output exactly (titles verbatim, dates
identical, price tiers identical → same formatted price string).
