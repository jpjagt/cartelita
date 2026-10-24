# St James's Church Piccadilly — source map

Venue slug: `st-james-piccadilly` (London) — 197 Piccadilly W1J 9LL.
Category `classical` (list `classical`).

## Data source

WordPress REST, open, plain httpx (`CARTELITA_COMPAT_UA`; robots allows
all):

- `GET /wp-json/wp/v2/event-category?slug=free-concerts,the-sixteen,past-events`
  → category ids (looked up each run; 165 / 205 / 122 on 2026-10-25);
- `GET /wp-json/wp/v2/event?event-category=<ids>&per_page=100&page=N`
  (`X-WP-TotalPages`) → the event posts. Only published, upcoming posts
  are returned (12 on 2026-10-25, although the category counts include
  history).

The posts' ACF fields are empty in REST; `content.rendered` is the page
body itself (identical to the event page HTML), so no page fetches.

## Curation

`event-category` **free-concerts** (the free lunchtime recitals, Mon/Wed/Fri
1.10pm, donations welcome) and **the-sixteen** (The Sixteen's residency) →
classical. Everything else is out because it isn't in those two
categories: the `music` category (779) holds the hired-in **"Vivaldi Four
Seasons by Candlelight"** tourist series (Piccadilly Sinfonietta) plus
other hires; services, talks, exhibitions, markets, Christmas/Pride
programmes likewise. Posts also in **past-events** are dropped.

## Fields

| Field | Source |
|---|---|
| `title` | `title.rendered` (unescaped) |
| `start_date` | `.hero__details` first `<p>`: "Wednesday 25 November 1.10pm" — **no year**: the first year on/after the post's publication date (`date`) whose weekday matches (`_yearless.parse`); past dates dropped |
| `start_time` | same paragraph ("1.10pm", "7pm", "6.15pm") |
| `price` | "Free admission"/"Free entry" in the body → "free"; else a "Ticket pricing: Adult £10/Child £5" line → `gbp_price` ("£5–10"); else None (The Sixteen concerts sell on thesixteen.com, not stated on the page) |
| `description` | the hero's second paragraph (the strapline) |
| `source_url` | `link` (`/whats-on/<slug>/`) |
| `external_id` | post `id` |
| `image_url` | the hero image |

## Verification

Last verified **2026-10-25** via HTTP cross-check with the site's own
listing `/whats-on/?_filter=music`: 12 events (10 free lunchtime recitals,
2 The Sixteen concerts + Christmas Choral Tots), 83% priced. Simo Sisevic
— listing "Wednesday 28 October 1.10pm" → scraper 28 Oct 13:10 "free";
Music for All Saints and All Souls — "Tuesday 27 October 7pm" → 27 Oct
19:00, price None (tickets via thesixteen.com). Cold-start DB: 12 rows.
