# Source map — Basílica de Santa Maria del Mar

**Venue slug:** `santa-maria-del-mar`
**Module:** `santa_maria_del_mar`
**Category:** `classical` (organ recitals, choral/medieval works, classical concerts)
**List membership:** `classical`

## Domain / URLs

- The original `santamariadelmarbarcelona.org` is now a meta-refresh redirect to the
  **new domain**: `https://www.santamariadelmar.barcelona`. (`/concerts` on the old
  domain 404s; an unrelated CMS even bounced it to Palau de la Música during recon —
  do NOT trust the old `.org/concerts` path.)
- There is **no dedicated "concerts" page**. The venue publishes a single WordPress
  **Agenda** that mixes cultural concerts with parish events (retreats, masses, etc.).
- **List URL:** `https://www.santamariadelmar.barcelona/ca/agenda/`
  Paginated: `/ca/agenda/page/2/`, `/page/3/`, ... The scraper walks pages until a
  page yields no article cards (bounded to a small max).

## Agenda list — fields per card (`article.grve-blog-item`)

- **detail URL:** `a.grve-item-url[href]`
- **title:** `h3.grve-post-title` (text). Concert titles often carry a cycle suffix,
  e.g. `… – Cicle «L'Orgue del Mar» de 2026`.
- **event date:** `.grve-post-date p` as `dd/mm/yyyy`. Verified field-by-field that
  this list date equals the detail page's `Data:` for concerts (Joan Seguí, Roberto
  Fresco, Cant de la Sibil·la all matched). So the list date IS the event date — no
  detail fetch needed for the date.
- **image:** `span[itemprop=image] span[itemprop=url]` (structured-data block).

The list does NOT carry **time** or **price** — those live only on the detail page.

## Detail page — fields (only fetched for kept concerts)

Scoped to `.elementor-widget-theme-post-content`. Body is WordPress
`<p class="wp-block-paragraph">` lines:

- **time:** `Hora: 20:30h` → `20:30` (regex `(\d{1,2})[:.h](\d{2})?`; bare `10h` → 10:00).
- **price:** `Entrada: 9€` (main public price). `Entrada reduïda*: 7€` is a discount
  tier and is **skipped** (we keep the highest public price per the price convention).
  Free-entry phrases ("entrada gratuïta/lliure", "gratis", "concert gratuït") → `"free"`.
- `Data:` / `Lloc:` are present too; we already have the date from the list.

## Category rule

All kept events are `classical`. The agenda mixes in **non-concert parish events**
(Recés/retreats, standalone Misses, Trobades, "Inici de curs", "Celebració
eucarística") which are NOT cultural concerts — these are **excluded** by a title
filter. An event is kept when its title matches a concert keyword:
`concert`, `cant de la sibil` (medieval choral), `coral`, `gòspel`/`gospel`,
`rèquiem`/`requiem`, `escolania`, `capella de música`. The "Cant de la Sibil·la i
Missa del Gall" contains "missa" but is a concert — the sibil·la rule includes it
before the exclusion would matter (we only exclude by absence of an include match).

**New category recommendation:** none required. `classical` fits every concert this
venue programmes (organ + choral). No need for a new top-level category.

## external_id

Per OCCURRENCE: detail-page slug (last path segment) qualified with the ISO date,
`f"{slug}@{YYYY-MM-DD}"`. Each agenda post is a single concert occurrence, so the
slug is already 1:1 with the occurrence, but the date qualifier is added defensively
to match the per-occurrence convention.

## Quirks / caveats

- The agenda is a **historical archive** (events back to 2021). As of the verify date
  it contained **no future-dated events** (latest = 21/02/2026; today 2026-06-02). The
  scraper still emits every concert it finds; downstream date-filtering handles past
  events. This is normal for a venue with a seasonal "L'Orgue del Mar" cycle that had
  finished its run.
- The host occasionally returns transient TLS `UNEXPECTED_EOF` errors — the scraper
  retries detail fetches.

last verified: 2026-06-02
