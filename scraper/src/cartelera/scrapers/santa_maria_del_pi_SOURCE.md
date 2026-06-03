# Source map — Basílica de Santa Maria del Pi

- **Venue slug:** `santa-maria-del-pi`
- **Module:** `santa_maria_del_pi.py`
- **City:** barcelona — Gothic basilica, Plaça del Pi 7, Barri Gòtic.
- **last verified: 2026-06-02**

## URLs

- Canonical site: **`https://basilicadelpi.cat`** (the `basilicadelpi.com` in the
  brief is a thin redirect host: `.com/en/concerts` 301s to a single `.cat` concert
  post, and `.com/` 301s to `.cat/ca/inici/`). There is no `/en/concerts` listing.
- Agenda (data source): **`https://basilicadelpi.cat/ca/agenda/`**

## Data source

WordPress **Simple Calendar (simcal)** month grid, fully server-rendered for the
**current month** (one HTTP GET; no JS needed). One occurrence = one
`<li class="simcal-event">`. Fields (schema.org microdata):

| Field         | Source |
|---------------|--------|
| title         | `span.simcal-event-title[itemprop=name]` (fallback: `span.simcal-event-title`) |
| start_date    | ISO `content` attr of `.simcal-event-start-date` |
| start_time    | ISO `content` attr of `.simcal-event-start-time` (fallback: time of start-date) |
| end_time      | ISO `content` attr of `.simcal-event-end-time` |
| description   | `.simcal-event-description` (free text; carries "Lloc:" + an optional "Més informació" link) |
| source_url    | "Més informació" `a[href*=basilicadelpi]` in the description; else the Google-Calendar "Més detalls" link |
| price         | parsed from the description free text (`N€` / free / sold-out phrases) — usually absent |
| external_id   | the Google-Calendar `eid` query param (stable, already per-occurrence); fallback `date+time-hash(title)` |

## Category mapping

All kept events → **`classical`**. The agenda is the parish **liturgical** calendar
(mostly daily "Missa"); we KEEP only concert/recital cultural events at the basilica
and DROP masses + off-site parish acts. Discriminator: title matches a concert word
(`concert|recital|coral|polifònic|música|orquestr|cobla|cor|vespres|gospel|nadales`)
AND not a liturgy word (`missa|eucaristia|pregària|rosari|via crucis`). Church
concerts here (choirs, early music, chamber, cobla) are classical/sacred music, so a
single `classical` category fits; no granular sub-genre tags surface in the agenda.

## Quirks / notes

- **Coverage is intrinsically thin.** This is a working parish, not a concert hall.
  June 2026 had 32 calendar entries but only **1** concert at the basilica
  ("Concert dels 425 anys dels Gegants del Pi", Cobla Sant Jordi). The rest are
  masses; one "Celebració…" act is at a *different* parish (el Prat de Llobregat) and
  is correctly dropped.
- The candlelight/Vivaldi/classical-guitar tourist concert series associated with
  this Gothic church is run by **third-party promoters/ticketing platforms**, NOT on
  the basilica's own site. Per the project guardrail we do not chase third parties;
  this scraper covers the basilica's own programme only.
- Month navigation (prev/next) is an `admin-ajax.php` simcal call. The current month
  renders server-side without it; the next month (July 2026) was **empty** at verify
  time, so we deliberately scrape only the server-rendered current month (robust,
  deterministic, matches the Zumzeig single-request approach).
- Price: none of the concerts expose a scrape-able ticket price today; `_normalize_price`
  is in place for when a description carries `Preu:`/`Entrada lliure`/sold-out text.

## Live verification — 2026-06-02

`uv run cartelera dry-run santa_maria_del_pi` returned **1** event:
"Concert dels 425 anys dels Gegants del Pi", 2026-06-02 20:00, category `classical`,
source_url → `…/la-cobla-sant-jordi-en-el-concert-dels-425-anys-dels-gegants-del-pi/`.
Cross-checked against the live `/ca/agenda/` DOM via browser-use (`li.simcal-event`):
32 total entries, exactly 1 concert — matches the scraper output field-for-field
(title, ISO date/time, basilica detail link). Masses correctly excluded.
