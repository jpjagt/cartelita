# TivoliVredenburg — source map

Venue slug: `tivolivredenburg` (Utrecht), Vredenburgkade 11. One venue for the
whole building; the hall ("Grote zaal", "Hertz", "Pandora", "Ronda", "Cloud
Nine", "Club Nine", …) is the first entry of `annotations`.
Categories: pop, jazz, classical, club, folk, kids — each its own list with a
same-category whitelist.

Own site: `https://www.tivolivredenburg.nl/` (WordPress, server-rendered).

## Client

Plain **httpx** with the honest UA `Cartelita (+https://cartelita.co)`
works (2026-10-14: 43 list pages + 850 detail pages, all 200). The site sits
behind Cloudflare: plain `curl` (any UA) gets the "Just a moment…" challenge,
httpx and curl_cffi pass — it's TLS-fingerprint based. If httpx starts getting
403s, switch `_get` to `cartelera.scrapers.http.fetch(..., impersonate=True)`
first, then `cartelera.scrapers.browser`. Polite: 0.5 s sleep after every
request, ≤ 2 concurrent detail fetches, each detail fetched once per run.
A full run takes ~5 min (~43 list + ~770 detail requests).

## List: `/agenda/`, `/agenda/page/N/` (20 cards/page; follow while the page links `page/N+1/`)

| Field | Source |
|---|---|
| `external_id` | numeric id in the card URL `/agenda/<id>/<slug>-<dd-mm-yyyy>` (one id per occurrence) |
| `source_url` | `a.agenda-list-item__title-link[href]` |
| `title` | that link's text |
| `start_date` | `time.agenda-list-item__time` ("wo 14 okt 2026", Dutch month abbreviations) |
| genres | `button[data-genre]` — comma-separated genre term slugs (category discriminator) |
| free | card ticket link text "Gratis" |

Genre hierarchy: the agenda's genre filter menu (`.filter-categories
div.filter--genre`): the head `a[data-term_id]` is the top-level group, the
`ul.filter-subitems a` are its sub-genres — keyed by both `data-term_id` and the
`?sf_genre=` slug (cards use the latter, e.g. `hiphop-rb-1`). Parsed at run time
from page 1, so new sub-genres are picked up automatically.

## Category mapping (top-level group → category)

| TivoliVredenburg group | category |
|---|---|
| Pop / Rock (`pop-rock`, incl. its sub-genres Global, Soul/Funk/Jazz, Neoklassiek, Electronic, Hiphop/R&B…) | pop |
| Klassiek (`klassiek`: symfonisch, kamermuziek, oude muziek, vocaal, …) | classical |
| Jazz (`jazz`) | jazz |
| Dance / By Night (`dance-by-night`) | club |
| Global (`global`: Turks, Koerdisch, Latijns-Amerikaans, MENA) | folk (world music — closest existing category) |
| Familie (`familie`) | **kids only** (overrides the others: family concerts don't go on adult lists) |
| Kennis & Debat, Comedy | none |

A card may carry several groups → several categories (e.g. pop + jazz). The
sub-genre labels (e.g. "Kamermuziek", "Metal/Punk/Heavy") go to `annotations`
after the hall. Never derived from titles.

## Detail: `/agenda/<id>/<slug>` — `.event__info dl.description-list` + `.event-cta`

| Field | Source |
|---|---|
| `start_time` | time row labelled "Aanvang"/"Start" (also "Aanvang concert 1", "Ochtendshow: aanvang"…; several → `start_times`). Time rows render value-first: `<dd><time>20:15</time></dd><dt>Aanvang</dt>`. Fallbacks: per-act set-time rows (label = act name, e.g. "Amber Run 19:45") → the first act; `Aanvang: 10.00 uur` lines in the "Programma" prose (family shows' multiple sessions); "Deuren open" (club nights only list doors); JSON-LD time. **JSON-LD `startDate` is the DOORS time** — not used for the start. |
| `end_time`/`end_date` | "Verwachte eindtijd"; ≤ start ⇒ next day |
| hall | "Locatie" `dd` (→ `annotations[0]`) |
| `price` | see below |
| `description` | `.event-cta .event__subtitle` (one-line kicker) |
| `image_url` | JSON-LD `image` (else the card image) |
| `language` | not stated → None |

### Price
1. `.event-cta a.btn-group__link[data-status="Sold out"]` → `"sold-out"`.
2. Badge or card "Gratis" → `"free"`.
3. Tier tables `dl.description-list--price` (Rang 1–3 × Regulier/Onder 30 jaar;
   Volwassene/Kind; Early/Regular/Late Ticket): discounts and upsells are
   skipped (Onder 30, Kind, U-pas, Student, Jongere, Groeps-/Duo-/Gezinsticket,
   Ouder, VIP, Meet & Greet, packages); the rest → 2× rule (range only if
   hi ≥ 2·lo, else the highest): `"43€"`, `"26,50€"`.
4. Else `.btn-group__price` ("€ 33,-", "v.a. € 48,-" = the only figure shown
   → `"48€"`); `€ 0,-` (lunch concerts, free-with-reservation) → `"free"`.

## Curation — what is left out, and why (owner: programme, not every booking)

Live 2026-10-14: 850 agenda items → **691 kept**.

| Rule (venue's own labels/data only) | Count | Examples |
|---|---|---|
| No genre on the card (`data-genre=""`) — the venue doesn't file it under any programme | 53 | backstage tours, Metal Yoga, linedance, NKK children's choir rehearsals, schoolconcerts, Tafel van Utrecht talks, Sencity. Also loses a few real but untagged concerts (Eric Vloeimans trio, New European Ensemble, Metropole Orkest "De stem van Water", 3 lunch concerts) — accepted: no label to go on. |
| Only Kennis & Debat / Comedy | 24 | lectures, debates, stand-up |
| Off-site: "Locatie" is not a TivoliVredenburg space (in-house = links to tivolivredenburg.nl, or is one of the known halls/foyers in `IN_HOUSE_SPACES`) | 53 | dB's and De Helling gigs (owned by those venues' sources — would double-count), UJazz's Buitenwereld, Stadsklooster, churches, libraries, living-room concerts, "Danel" |
| Non-programme series (`.event-collection-cta a[href]` path) | 20 | `/de-vrije-ruimte` (community activities), `/connect/schoolconcerten`, `/studio/podcast` (podcast recordings), `/park6` (the free foyer hangout bar) |
| Badge "Afgelast" / "Verplaatst" | 9 | cancelled or moved |

Genre-only exclusions are decided before fetching details (saves ~80 requests).
Known leak: "Schoolconcert VO: Walk the Line" is tagged pop-rock + familie with
no series link — kept (as kids); there is no non-title signal to drop it.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live scrape: 691 events,
2026-10-14 → 2027-12-01; start_time 691/691, price 691/691 (94 sold-out, 47
free), language 0 (not stated). Categories: pop 386, classical 203, jazz 67,
folk 54, club 42, kids 28. Independent check: fresh httpx of agenda page 1 —
all 10 kept/10 excluded cards match the rules above (Jhariah → De Helling,
Krallice → Buitenwereld, Pete Murray → Stadsklooster, Kita Alexander
cancelled, podcasts series); 10 random kept events re-fetched and regexed
("HH:MM Aanvang/Start", Regulier/price text, data-status, Locatie): start time,
price, sold-out and hall agree on all 10 (Hush: Early 18/Regular 24/Late 29 →
"29€" per the 2× rule).
