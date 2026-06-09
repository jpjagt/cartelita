# Teatre Goya — Source Map

**Venue:** Teatre Goya, C/ Joaquín Costa 68, 08001 Barcelona (El Raval)
**Site:** https://www.teatregoya.cat
**Last verified:** 2026-06-09

## Data flow

Two HTTP requests per show (season page + detail page):

1. **Season list** `GET https://www.teatregoya.cat/ca/season/`
   WordPress page rendered with Isotope JS filter. All show cards are present
   in the initial HTML (no AJAX pagination). Scraped fields:
   - `title`      → `.espectacle-query__item .title a` text
   - `detail_url` → `.espectacle-query__item a.image-container[href]`
   - `image_url`  → `.espectacle-query__item img[src]` (poster thumbnail)
   - `category`   → Isotope filter class on the `article` element:
     - `dis_11` → Teatre → annotation "Teatre", category "theater"
     - `dis_7`  → Comèdia → annotation "Comèdia", category "theater"
     - `dis_12` → Monòlegs → annotation "Monòlegs", category "theater"

2. **Show detail** `GET https://www.teatregoya.cat/ca/ex/<slug>/`
   WordPress single post, server-rendered. Scraped fields:
   - `title`       → `h1` (overrides season-page title)
   - `description` → `#sinopsi .entry-content` plain text (truncated to 500 chars)
   - `image_url`   → `.espectacle_basic_data img.poster[src]`
   - Sessions      → `#single_ex_buy_modal ul.espectacle_funciones li:not(.other_dates)`
     - `start_date` + `start_time` → `span.date` text: `<weekday>, DD/MM/YYYY - HH:MM`
     - `external_id` → ticket session ID from `a[href]` matching `/select/(\d+)`
       e.g. `https://tickets.oneboxtds.com/teatregoya/select/2735825?hl=ca-ES` → `"2735825"`

## Category mapping

All genres (Teatre / Comèdia / Monòlegs) → `theater`.
The dis_ genre label is stored as a free-form annotation.

## Price

**Not available.** The venue website does not display ticket prices. Pricing
lives in the third-party ticket system (oneboxtds.com / proticketing.com),
which returns Cloudflare blocks to non-browser clients. All events have
`price=None`.

## External ID

The ticket session ID (`select/<id>`) is a per-occurrence stable integer.
Each session of a show has its own unique ID, so no date-qualification is
needed. Example: Tinder sorpresa on 12/06/2026 22:30 → `"2735825"`.

## Sessions window

The buy modal shows the next ~6–12 upcoming sessions per show. A
"Per a altres dates" fallback link appears when more sessions exist. The
scraper emits exactly the sessions visible in the modal; far-future sessions
outside that window are not visible and are not scraped.

## Caveats

- **Season page only**: the scraper only visits the current season page
  (`/ca/season/`), which shows 6 shows as of 2026-06-09. Archived/past shows
  are not scraped.
- **Spanish-language shows**: some shows (Tinder sorpresa, Buenrollistas) are
  in Castilian; the category is still `theater`.
- **Kids shows**: `Fills: no deu ser tan difícil!` appears to be a family show
  (Comèdia) but still maps to `theater` since the venue has no dedicated kids
  programming section.

## Verification (2026-06-09)

Live scrape returned 30 events across 6 shows.
Cross-checked first show (Tinder sorpresa) sessions against browser:
- 12/06/2026 22:30 → ticket id 2735825 ✓
- 13/06/2026 20:00 → ticket id 2735826 ✓
- 19/06/2026 22:30 → ticket id 2735827 ✓
All events have description and image_url. Price=None (confirmed expected).
