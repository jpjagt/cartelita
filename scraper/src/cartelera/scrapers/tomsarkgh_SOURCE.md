# tomsarkgh.am — source map

last verified: 2026-08-18 (verified via HTTP fetch — browser tooling unavailable
this pass, would have attached to the user's real Chrome and needed manual
approval, declined per instructions; verified instead by re-fetching live pages
with `httpx` and cross-checking the scraper's parsed output field by field)

## What this is

**Multi-venue aggregator source** (`register_source`, not `register`).
tomsarkgh.am is Yerevan's main event-ticketing site (~1,700+ events across
~1,900 venues city-wide), with a full English UI at `/en/*`. This source
scrapes only **five whitelisted venues**; `SourceDefinition.venues` is the
editorial whitelist and `ScrapedEvent.venue_slug` is set on every event (the
runner fails fast on any event naming a venue outside the list).

| venue_slug              | tomsarkgh venue id | name                                                     |
| ------------------------ | ------------------- | --------------------------------------------------------- |
| `khachaturian-hall`      | 20                   | Aram Khachaturian Concert Hall (Armenian National Philharmonic's hall) |
| `opera-ballet-theatre`   | 18                   | Armenian National Academic Theatre of Opera and Ballet (Spendiaryan) |
| `sundukyan-theatre`      | 8                    | Gabriel Sundukyan State Academic Theatre                   |
| `hamazgayin-theatre`     | 1                    | Hamazgayin State Theatre (Sos Sargsyan)                     |
| `stanislavski-theatre`   | 10                   | Stanislavski Russian Drama Theatre                          |

Komitas Chamber Music House is deliberately **not** included — it's a
separate source built by a sibling agent (`komitas_chamber_hall.py`).

Venue ids were found via `/sitemap/venues/{0..3}` (the site's own sitemap
shards — `robots.txt` lists `Sitemap: https://www.tomsarkgh.am/sitemap/venues`)
grepped for each venue's English name; `khachaturian-hall`/`opera-ballet-theatre`/
`sundukyan-theatre` were also directly linked from the homepage's `/en/category/*`
listings, `stanislavski-theatre` from `/en/category/Theater`.

## Page shape

- **Venue page**: `https://www.tomsarkgh.am/en/venue/{id}/{slug}.html` — a
  server-rendered list of `div.event-box-item` cards for that venue's upcoming
  programme, ~10 per page, with a "More (N)" link (`a.moreScope[href]`) to the
  next page (`.../{id}/{slug}.html/1/scopeKey/{n}/page/{n}/view/list4x`).
  `parse_venue_listing_page(html)` parses one such page (initial or "more"
  fragment — both have the same card markup) into `(cards, next_url)`;
  `TomsarkghScraper` follows the chain until no more link.

- **⚠️ Site-wide "related events" carousel trap** (the same trap
  `komitas_chamber_hall_SOURCE.md` hit): every venue page — and every "more"
  fragment — also embeds a **site-wide recommendation widget** with cards for
  OTHER venues' events (verified: Khachaturian Hall's page recommends "Coca-Cola
  Fest 2026" and a stand-up night, neither of which happens there; Sundukyan
  Theatre's page recommends the same). The discriminator: a genuine card for
  *this* venue has a `p.event-venue` element (linking back to the venue); the
  carousel cards don't. `parse_venue_listing_page` filters on
  `box.select_one(".event-venue")`. One venue (the opera-ballet theatre) was
  additionally observed rendering one of its own events **twice** on the same
  page (a "featured" slot duplicate) — both copies do carry `.event-venue`, so
  `parse_venue_listing_page` also dedupes by event id within a page.

- **Event detail page**: `https://www.tomsarkgh.am/en/event/{id}/{slug}.html`.
  `parse_event_detail(html)` extracts:
  - **title** ← `#eventName` (`h1`, `itemprop=name`).
  - **start_date/start_time** ← `[itemprop=startDate]`'s `content` attribute,
    `"YYYY-MM-DD HH:MM"` (24h, naive local Yerevan wall-clock time — no
    timezone offset in the markup, same convention as `arten.py`). **Every
    tomsarkgh event id is already one occurrence** — confirmed by recon: a
    production running several nights gets a *separate event id per night*
    (e.g. ids `51418`/`51419` for the same title on 2026-11-26 and -27
    respectively, each with its own single `startDate`). No multi-date
    session list was found on any detail page (unlike Komitas's ticket pages).
    So `external_id = f"tomsarkgh-{event_id}"` needs no date qualification.
  - **type label** (the categorization discriminator) ← `.scope-event-type`
    (an `<a href="/en/category/{Slug}">{Label}</a>` near the top of the page,
    e.g. `Classical`, `Jazz`, `Theater`, `Opera & Ballet`). **Preferred over
    the listing card's own `.event-type` text** when both are fetched (they
    normally agree, but the detail page is the more specific per-event
    source — same principle as Komitas's "the ticket detail page wins").
  - **price** ← extracted from the description text (see below); the
    page also carries a schema.org `[itemprop=offers][itemprop=price]` meta,
    but it was verified to hold only the *minimum* tier of a price range
    (e.g. an event whose description says "6000-12000 դր." has
    `itemprop=price content="6000.00"` only) — not usable alone, so we parse
    the free-text price line from the description instead.
  - **description** ← `#eventDesc`, newline-joined per its `<br>`-separated
    lines (kept as the description field verbatim, in whatever language the
    venue actually publishes it in — see Language below).
  - **image_url** ← `[itemprop=image]`'s `src`.

  A card whose detail page fails to fetch, or whose detail page has no
  parseable `startDate`, is silently dropped (nothing reliable to emit).

## Category mapping (the editorial rule — see `categorize()`)

tomsarkgh's own event-type taxonomy is used as the **only** discriminator —
never the title (never guess). Full type distribution actually observed
across the five venues' current programmes (2026-08-18, live via `httpx`):

- `khachaturian-hall` (26 events): Classical 14, Concert 6, Jazz 2, Rock 2,
  Pop 1, Folk 1.
- `opera-ballet-theatre` (36 events): Classical 8, Ballet 7, Opera 6,
  Opera & Ballet 4, Jazz 4, Pop 4, Concert 2, Dance 1.
- `sundukyan-theatre` (8 events): Theater 4, Tale 1, Tragicomedy 1, Drama 1,
  For kids 1.
- `hamazgayin-theatre` (18 events): Theater 16, Drama 2.
- `stanislavski-theatre` (24 events): Theater 22, Comedy 2.

Rules:

1. **`khachaturian-hall`** — the hall is a classical venue that also books
   mainstream programming (rooftop pop/rock/jazz/folk concerts, a Sinatra/
   Wonder/Bublé pops-orchestra tribute night tagged plain "Concert", etc.).
   Binary per the task brief: `type_label == "Classical"` → `["classical"]`;
   everything else → `["pop"]`. `pop` is a seeded category with no Yerevan
   list wired to it yet, so these events correctly render nowhere — that's
   the intended effect, not a bug. **0 events skipped** (all 26 kept).

2. **`opera-ballet-theatre`** — `Opera` → `["classical"]`; `Ballet` →
   `["dance"]`; `Classical` → `["classical"]` (direct); `Dance` → `["dance"]`
   (direct — verified this is the National Dance Ensemble's own programme,
   not a stray mislabel); `Opera & Ballet` → `["classical", "dance"]` (a
   combined gala/production genuinely spanning both — verified titles:
   Tchaikovsky's *Sleeping Beauty*, Adam's *Giselle*, an "International Opera
   Day" gala). `Jazz`/`Pop`/`Concert` bookings (10 events, all titled
   "Rooftop concert…" — the same promotional rooftop-concert series seen at
   Khachaturian Hall, evidently also using the opera house's rooftop) are
   **skipped**: the task brief gives no fallback category for this venue
   (unlike Khachaturian Hall's explicit "emit pop" instruction), and none of
   jazz/pop/concert maps confidently to classical/dance/theater — never
   guess. **10/36 skipped.**

3. **`sundukyan-theatre`, `hamazgayin-theatre`, `stanislavski-theatre`** —
   all map to `["theater"]` per the task brief. The apparent sub-genre labels
   (`Drama`, `Tale`, `Tragicomedy`, `Comedy`, `For kids`) are **not** separate
   event formats — they're literary/audience genres of the same thing, a
   staged play at a drama theatre. Verified by inspecting titles behind each
   label: `Tale`/`For kids` → children's plays (e.g. "Cinderella", "Ashgirl");
   `Comedy` → stage comedies (e.g. "Family Casting"); `Tragicomedy`/`Drama` →
   straight dramatic repertoire. So `{Theater, Drama, Tale, Tragicomedy,
   Comedy, "For kids"}` all → `["theater"]`. `Concert`/`Stand-up` bookings
   (venues renting out their stage for something that isn't a play) are
   **skipped** — none observed in the current programme at any of the three
   theatres (0 skipped this pass), but the rule exists defensively since the
   type was seen mixed into the site-wide carousel widget for these venues.

**Total this pass: 102 events kept, 10 skipped (all at `opera-ballet-theatre`).**

## Price

AMD, free text, hand-rolled (`parse_price`/`format_amd` — **not**
`cartelera.scrapers.price.format_eur_range`, which is EUR-specific). The
description's price line is found by a language-agnostic trigger word
(Armenian `Տոմս` "ticket(s)", Russian `Билет`/`Цена` "ticket(s)"/"price" — the
three actually observed; a venue may publish its price line in either
language regardless of which one its title/description defaults to). All
"number" tokens on that line are extracted (`\d{1,3}(?:[ .,]\d{3})+|\d+` —
matches thousands-grouped numbers like `25.000`/`4,000`/`10 000` as one token
*before* falling back to a bare digit run, so a **comma-separated list of
distinct prices** like `"25000, 30000"` doesn't get misread as one
thousands-grouped number and mangled into `2500030000` — a real bug caught
during authoring, see the regression test
`test_parse_price_comma_separated_list_not_merged_into_one_giant_number`).
Tokens under 3 digits are dropped (skips stray numbers like an age rating).
`lo`/`hi` = min/max of the surviving values; the usual 2× rule: `"{hi} AMD"`
when the spread is minor, `"{lo}–{hi} AMD"` when `hi >= 2*lo`. A trigger line
present with no usable digits (e.g. "Tickets on sale, don't miss it" — 51403
at Stanislavski Theatre) or no trigger line found at all (50868 at Sundukyan
Theatre) → `price = None`, never guessed. **Verified: a separate "children
under 4 enter free" clause, which appears on its own description line without
the trigger word, is correctly ignored** and does not turn the price into
`"free"` (see `test_parse_price_ignores_free_child_clause_on_a_different_line`
and the live cross-check on event 46087/43263).

**Coverage this pass: 100/102 events (98%) have a price.** The 2 without:
Sundukyan Theatre's "Թմկաբերդի առումը" (a theatre-studio in-house production
with an organizer credits block but no stated ticket price) and Stanislavski
Theatre's "Камиль Чалаев. один против музыки" (a promotional description with
no price line at all, just "tickets already on sale").

No "free"/"sold-out" wording was found anywhere in the sampled descriptions
this pass (unlike Komitas or Arten); not implemented since unobserved — would
need re-recon if it appears later.

## Language

The price-convention free-text `language` field is **fixed per venue**, not
inferred (per the task brief — "uniform-per-venue is the intended
convention"):

- `sundukyan-theatre`, `hamazgayin-theatre` → `"hy"` (Armenian).
- `stanislavski-theatre` → `"ru"` (Russian) — cross-checked: this venue's own
  description text on the site is genuinely written in Russian for some
  events (e.g. "Психоз.4.48. Исповедь души", "Цена билета: 8000 др"), unlike
  Sundukyan/Hamazgayin whose descriptions are Armenian throughout. So the
  fixed assignment matches what's actually on the page, not just an
  editorial label.
- `khachaturian-hall`, `opera-ballet-theatre` → `None` (no single spoken
  language for concerts/opera/ballet programming; never inferred).

## No translations emitted

tomsarkgh serves `/en/`, `/ru/`, and a default (no-prefix) Armenian URL for
every event, which looks at first glance like a translation opportunity (the
same shape as `arten.py`'s hy/ru/en afisha pages). **Verified this is a false
lead**: fetching the same event id under all three prefixes returns
**byte-identical title and description text** — only the site's own chrome
(nav, category label — e.g. "Concert"/"Համերգ"/"Концерты") is translated, the
event content itself is not. Emitting an `en`/`ru` `ScrapedTranslation` here
would misrepresent untranslated Armenian text as translated content, so none
are emitted; `source_url` always uses the `/en/` URL (arbitrary — content is
identical across prefixes, `/en/` chosen simply because English chrome is
easiest for a non-Armenian-reading maintainer to sanity-check against).

## Verification (2026-08-18)

Browser automation unavailable this pass (would attach to the user's live
Chrome, needs manual approval — declined per instructions). Verified via
direct `httpx` fetches instead:

- `TomsarkghScraper().scrape()` (live): **102 events**, 0 duplicate
  `external_id`s, 0 past-dated events (min start_date == today, 2026-08-18).
  Coverage: start_time 102/102 (100%), price 100/102 (98%), image_url 102/102
  (100%), annotations 102/102 (100%), external_id 102/102 (100%). Categories:
  `{pop: 12, classical: 32, dance: 12, theater: 50}` (matches the hand-count
  above: 12 = 6 khachaturian-non-classical... see breakdown below).
- Cross-checked 6 randomly sampled events' `(title, start_date, start_time,
  category)` against a **fresh, independent** live fetch of their detail
  pages: all 6 matched exactly (title text, `YYYY-MM-DD HH:MM`, and
  `.scope-event-type` label all identical to the scraper's parsed output).
- Verified the 10 opera-ballet-theatre Jazz/Pop/Concert events are correctly
  **absent** from the scraper's output (skip logic confirmed against the live
  listing, not just the categorize() unit tests).
- Verified the site-wide carousel filter against the live Sundukyan Theatre
  page: the naive "all `.event-box-item`" count is inflated by the carousel
  (9 boxes vs. 8 genuine events on this pass); "Coca-Cola Fest 2026" (a
  Khachaturian Hall rooftop event, id 51211, appearing in Sundukyan's
  carousel) is correctly excluded from Sundukyan's own event list.

Category count reconciliation: classical = 14 (khachaturian) + 8 (opera-ballet
Classical) + 6 (opera-ballet Opera) + 4 (opera-ballet Opera & Ballet, doubled
into both classical and dance) = 32. dance = 7 (Ballet) + 1 (Dance) + 4
(Opera & Ballet) = 12. pop = 26 − 14 = 12. theater = 8 + 18 + 24 = 50.

## Quirks

- The venue page's pagination fragment (the "more" link target) has no
  `.event-list-wrapper` container the way the initial page does — the
  `.event-venue` presence check works on both, so `parse_venue_listing_page`
  doesn't rely on the wrapper class.
- `.scope-event-type`'s text can differ from what a card's own `.event-type`
  shows if fetched at different moments (this is a live ticketing site, dates/
  categorization can change between page loads) — `build_event` prefers the
  detail page's label when present, falling back to the card's only if the
  detail page has none.
- This host was briefly unreachable (`Network is unreachable`) partway through
  this pass while saving supplementary fixtures; all reported figures above
  come from the successful scrape/verification runs completed just before
  that, and the saved HTML fixtures in `scraper/tests/fixtures/tomsarkgh_*`
  were captured during those same successful fetches.
